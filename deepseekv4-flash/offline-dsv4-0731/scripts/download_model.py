#!/usr/bin/env python3
"""Resume and verify the pinned ModelScope DeepSeek V4 0731 snapshot."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

REPO = "Eco-Tech/DeepSeek-V4-Flash-0731-w8a8"
REVISION = "9e8679a9db7eec11efed9925f7efb96549077545"
API_ROOT = f"https://modelscope.cn/api/v1/models/{REPO}"
USER_AGENT = "dsv4-0731-ascend-offline-deployer/1.0"
EXPECTED_SHARDS = 74
EXPECTED_INDEX_TOTAL = 314_621_886_200
print_lock = threading.Lock()


def api_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=90) as response:
        return json.load(response)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(16 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def log(message: str) -> None:
    with print_lock:
        print(message, flush=True)


def download_one(output: Path, item: dict) -> tuple[str, int]:
    relative = item["Path"]
    expected_size = int(item["Size"])
    expected_sha = item["Sha256"].lower()
    destination = output / relative
    partial = destination.with_name(destination.name + ".part")
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.is_file() and destination.stat().st_size == expected_size:
        if sha256_file(destination) == expected_sha:
            log(f"[ok] {relative}")
            return relative, expected_size
        log(f"[redo] checksum mismatch: {relative}")
        destination.unlink()

    if partial.exists() and partial.stat().st_size > expected_size:
        partial.unlink()
    if partial.is_file() and partial.stat().st_size == expected_size:
        if sha256_file(partial) == expected_sha:
            os.replace(partial, destination)
            log(f"[verified resumed] {relative}")
            return relative, expected_size
        log(f"[redo] partial checksum mismatch: {relative}")
        partial.unlink()

    url = (
        f"{API_ROOT}/repo?Revision={quote(REVISION, safe='')}"
        f"&FilePath={quote(relative, safe='')}"
    )
    log(f"[download] {relative} ({expected_size} bytes)")
    resume_from = partial.stat().st_size if partial.is_file() else 0
    command = [
        "curl",
        "--fail",
        "--location",
        "--retry",
        "20",
        "--retry-delay",
        "3",
        "--retry-all-errors",
        "--connect-timeout",
        "30",
        "--output",
        str(partial),
        url,
    ]
    # ModelScope's large-file CDN may stall a full GET or an open-ended range
    # starting at zero on some domestic network paths. Seed a new large file
    # with a finite 16 MiB range, then let curl append from that exact offset.
    seed_size = min(expected_size, 16 * 1024 * 1024)
    if resume_from == 0 and expected_size > seed_size:
        seed_command = command.copy()
        seed_command[1:1] = ["--range", f"0-{seed_size - 1}"]
        subprocess.run(seed_command, check=True)
        resume_from = partial.stat().st_size
        if resume_from != seed_size:
            raise RuntimeError(
                f"range seed mismatch for {relative}: {resume_from} != {seed_size}"
            )
    if resume_from:
        command[1:1] = ["--continue-at", "-"]
    subprocess.run(command, check=True)
    actual_size = partial.stat().st_size
    if actual_size != expected_size:
        raise RuntimeError(
            f"size mismatch for {relative}: {actual_size} != {expected_size}"
        )
    actual_sha = sha256_file(partial)
    if actual_sha != expected_sha:
        raise RuntimeError(
            f"SHA-256 mismatch for {relative}: {actual_sha} != {expected_sha}"
        )
    os.replace(partial, destination)
    log(f"[verified] {relative}")
    return relative, expected_size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if args.jobs < 1 or args.jobs > 8:
        parser.error("--jobs must be between 1 and 8")

    args.output.mkdir(parents=True, exist_ok=True)
    files_url = (
        f"{API_ROOT}/repo/files?Revision={quote(REVISION, safe='')}"
        "&Recursive=True"
    )
    payload = api_json(files_url)
    if payload.get("Code") != 200:
        raise RuntimeError(f"ModelScope API failure: {payload}")
    files = [
        item
        for item in payload["Data"]["Files"]
        if item.get("Type") == "blob" and item.get("Sha256")
    ]
    if not files:
        raise RuntimeError("Pinned revision returned no downloadable files")

    shards = [
        item
        for item in files
        if item["Path"].startswith("quant_model_weights-")
        and item["Path"].endswith(".safetensors")
    ]
    if len(shards) != EXPECTED_SHARDS:
        raise RuntimeError(
            f"expected {EXPECTED_SHARDS} weight shards, got {len(shards)}"
        )

    snapshot = {
        "repo": REPO,
        "revision": REVISION,
        "generated_at_unix": int(time.time()),
        "expected_index_total": EXPECTED_INDEX_TOTAL,
        "files": files,
    }
    (args.output / "MODEL-SNAPSHOT.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = "".join(
        f"{item['Sha256'].lower()}  {item['Path']}\n" for item in files
    )
    (args.output / "MODEL-MANIFEST.sha256").write_text(
        manifest, encoding="utf-8"
    )

    total = sum(int(item["Size"]) for item in files)
    log(
        f"Pinned snapshot: {REPO}@{REVISION}; "
        f"{len(files)} files; {total / 2**30:.2f} GiB"
    )
    failures: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(download_one, args.output, item): item["Path"]
            for item in files
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as error:  # report every failed shard
                failures.append(f"{futures[future]}: {error}")
                log(f"[failed] {failures[-1]}")

    if failures:
        print("Download incomplete; rerun the same command to resume:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    (args.output / ".download-complete").write_text(
        f"{REPO}@{REVISION}\n", encoding="utf-8"
    )
    log("All pinned files downloaded and SHA-256 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

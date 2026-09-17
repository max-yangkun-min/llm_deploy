#!/usr/bin/env python3
"""Validate the pinned Ascend W8A8 checkpoint before model loading."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

REPO = "Eco-Tech/DeepSeek-V4-Flash-0731-w8a8"
REVISION = "9e8679a9db7eec11efed9925f7efb96549077545"
EXPECTED_SHARDS = 74
EXPECTED_TOTAL = 314_621_886_200


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(16 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_dir", type=Path)
    parser.add_argument("--full", action="store_true", help="hash every file")
    args = parser.parse_args()
    root = args.model_dir.resolve()

    snapshot_path = root / "MODEL-SNAPSHOT.json"
    complete_path = root / ".download-complete"
    if not snapshot_path.is_file() or not complete_path.is_file():
        fail("download metadata is incomplete; run start.sh download")
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.get("repo") != REPO or snapshot.get("revision") != REVISION:
        fail("model source or revision does not match the pinned 0731 snapshot")
    if complete_path.read_text(encoding="utf-8").strip() != f"{REPO}@{REVISION}":
        fail("completion marker does not match the pinned snapshot")

    files = snapshot.get("files") or []
    for item in files:
        path = root / item["Path"]
        if not path.is_file():
            fail(f"missing file: {item['Path']}")
        if path.stat().st_size != int(item["Size"]):
            fail(f"size mismatch: {item['Path']}")
        if args.full and sha256_file(path) != item["Sha256"].lower():
            fail(f"SHA-256 mismatch: {item['Path']}")

    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    if config.get("architectures") != ["DeepseekV4ForCausalLM"]:
        fail("unexpected model architecture")
    if config.get("model_type") != "deepseek_v4":
        fail("unexpected model_type")
    if config.get("num_nextn_predict_layers") != 1:
        fail("0731 MTP layer is missing")
    if config.get("dspark_target_layer_ids") != [40, 41, 42]:
        fail("0731 DSpark configuration is missing")

    index = json.loads(
        (root / "quant_model_weights.safetensors.index.json").read_text(
            encoding="utf-8"
        )
    )
    if int(index.get("metadata", {}).get("total_size", -1)) != EXPECTED_TOTAL:
        fail("weight index total_size is unexpected")
    shards = {
        name
        for name in index.get("weight_map", {}).values()
        if name.startswith("quant_model_weights-") and name.endswith(".safetensors")
    }
    if len(shards) != EXPECTED_SHARDS:
        fail(f"expected {EXPECTED_SHARDS} indexed shards, got {len(shards)}")

    mode = "full SHA-256" if args.full else "size/config"
    print(
        f"OK: {REPO}@{REVISION}; {len(files)} files; "
        f"{EXPECTED_SHARDS} shards; validation={mode}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


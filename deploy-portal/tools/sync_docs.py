#!/usr/bin/env python3
"""抓取并验证权威部署文档来源。

只做两件事:确认 URL 真实可达,并记录当时的内容指纹。
不复制、不改写、不摘要——页面内容归原站,这里只保留可复核的出处。

用法:
    python deploy-portal/tools/sync_docs.py
    python deploy-portal/tools/sync_docs.py --check   # 只验证,不写文件(给 CI 用)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PORTAL_DIR = Path(__file__).resolve().parent.parent
SOURCES = PORTAL_DIR / "data" / "sources.json"
HF_CATALOG = PORTAL_DIR / "data" / "hf-catalog.json"
OUT = PORTAL_DIR / "data" / "doc-sources.json"

USER_AGENT = "Mozilla/5.0 (compatible; deploy-portal/0.1; local-model-catalog)"

TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
DESC_PATTERN = re.compile(
    r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"'](.*?)[\"']", re.I | re.S
)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()


def fetch(url, timeout=30, retries=3):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                return {
                    "status": response.status,
                    "final_url": response.geturl(),
                    "bytes": len(body.encode("utf-8")),
                    "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    "title": clean((TITLE_PATTERN.search(body) or [None, ""])[1])[:200],
                    "description": clean((DESC_PATTERN.search(body) or [None, ""])[1])[:300],
                    "text": body,
                }
        except urllib.error.HTTPError as error:
            last_error = "HTTP %s %s" % (error.code, error.reason)
            if error.code in (401, 403, 404):
                break
        except Exception as error:  # noqa: BLE001
            last_error = "%s: %s" % (type(error).__name__, error)
        if attempt < retries:
            time.sleep(1.5 * attempt)
    return {"status": None, "error": str(last_error)[:200]}


def model_card_entries():
    """用真实抓到的重点仓库补充官方模型卡链接,不凭记忆编造 URL。"""
    if not HF_CATALOG.is_file():
        return []
    catalog = json.loads(HF_CATALOG.read_text(encoding="utf-8"))
    entries = []
    for repo, record in (catalog.get("details") or {}).items():
        entries.append({
            "id": "model-card:" + repo,
            "title": repo + " 官方模型卡",
            "url": "https://hf-mirror.com/" + repo,
            "kind": "model-card",
            "profiles": record.get("profiles") or [],
            "revision": record.get("revision"),
        })
    return entries


def main(argv=None):
    parser = argparse.ArgumentParser(description="验证权威部署文档来源")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--no-model-cards", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="只验证可达性并报告,不覆写 data/doc-sources.json")
    args = parser.parse_args(argv)

    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    targets = list(sources["doc_sources"])
    if not args.no_model_cards:
        targets.extend(model_card_entries())

    results, errors = [], []
    print("验证 %d 个权威来源…" % len(targets))
    for position, target in enumerate(targets, 1):
        outcome = fetch(target["url"], timeout=args.timeout)
        text = outcome.pop("text", None)
        record = dict(target)
        record.update(outcome)
        record["checked_at"] = utc_now()
        if outcome.get("status") == 200:
            # 只留证据,不留全文:确认页面里确实提到引擎或模型名,证明链接没跑偏。
            markers = []
            for marker in ("vllm", "sglang", "llama.cpp", "transformers", "tensor-parallel"):
                if text and marker.lower() in text.lower():
                    markers.append(marker)
            record["engine_markers"] = markers
            results.append(record)
            print("  [%2d/%d] OK   %-58s %s" % (position, len(targets), target["id"], outcome.get("status")))
        else:
            errors.append(record)
            print("  [%2d/%d] FAIL %-58s %s" % (
                position, len(targets), target["id"], outcome.get("error") or outcome.get("status")))

    payload = {
        "schema": 1,
        "fetched_at": utc_now(),
        "counts": {"checked": len(targets), "ok": len(results), "failed": len(errors)},
        "note": "只记录可达性与内容指纹,正文版权归原站。failed 条目会保留在 errors 里,不会被隐藏。",
        "sources": results,
        "errors": errors,
    }
    if args.check:
        # 门禁只关心「链接是否还活着」;失败就非零退出,但不能让一次检查改动仓库状态。
        # 这里**不能**先写盘再打印「未写入」:原先正是那样,于是每次 `tools/ci.py --online`
        # 都会刷新 154 行 checked_at、把工作区弄脏,而输出还说没写。检查就只检查。
        print("\n--check:未写入 %s" % OUT)
        print("可达 %d / %d,失败 %d" % (len(results), len(targets), len(errors)))
        for record in errors:
            print("  FAIL %-58s %s" % (record.get("id"), record.get("error") or record.get("status")))
        return 1 if errors else 0
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n写入 %s" % OUT)
    print("可达 %d / %d,失败 %d" % (len(results), len(targets), len(errors)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

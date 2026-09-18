#!/usr/bin/env python3
"""从 vllm-ascend 官方文档抓取昇腾支持矩阵与逐模型教程命令,落成可核实的留痕数据。

背景(见 `.codex-specs/ascend-official-recipes/spec.md`):昇腾的部署方法必须来自
可公开核实的权威来源,不参考本工作区的现场资产。官方文档里有两样东西正好够用:

1. 支持矩阵(`user_guide/support_matrix/supported_models.md`)——按硬件族分表的
   **机器可读能力表**:Model / Support / BF16 / Supported Hardware / W8A8 /
   Chunked Prefill / ... / max-model-len / Doc;
2. 逐模型教程(`tutorials/models/<Model>.html`)——里面有**真实的启动命令**,
   并且按硬件族分成 tab(Atlas A2 / Atlas A3 / Atlas 300I DUO)。

本工具把这两样抓下来,连 URL + 文档版本 + 抓取时间 + sha256 一起写进
`data/ascend-support-matrix.json`。数据只由本工具写入,不许手改。

固定版本:引用官方**稳定版** v0.23.0(页面自述 "You are viewing the stable release
(v0.23.0) documentation")。固定版本让 sha256 漂移变成有意义的信号——上游改一个字
就报出来,而不是让引用悄悄变样。

用法:
    python deploy-portal/tools/sync_ascend.py --check   # 只核实 sha256 是否漂移
    python deploy-portal/tools/sync_ascend.py           # 抓取并写回
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
PORTAL_DIR = TOOLS_DIR.parent
WORKSPACE = PORTAL_DIR.parent
OUT = PORTAL_DIR / "data" / "ascend-support-matrix.json"

if str(PORTAL_DIR) not in sys.path:
    sys.path.insert(0, str(PORTAL_DIR))
import engine  # noqa: E402  (卡 ↔ 官方硬件族的匹配规则只有 engine 一份实现)

DOC_VERSION = "v0.23.0"
DOC_CHANNEL = "stable"
DOC_BASE = "https://docs.vllm.ai/projects/ascend/en/%s/" % DOC_VERSION
MATRIX_MD = DOC_BASE + "_sources/user_guide/support_matrix/supported_models.md"
MATRIX_HTML = DOC_BASE + "user_guide/support_matrix/supported_models.html"
PROJECT_URL = "https://github.com/vllm-project/vllm-ascend"

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) llm-deploy-portal/1.0 "
              "(+https://github.com/max-yangkun-min/llm_deploy)")

# 解析结果的下限。低于这个数说明上游结构变了(或被换了页),宁可报错也不写坏数据。
MIN_TABLES = 8
MIN_ROWS = 60

SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")
HEADING = re.compile(r"^(#{2,6})\s+(.*)$")
TAB_ITEM = re.compile(r"^:{3,5}\{tab-item\}\s*(.+?)\s*$")
TAB_ITEM_END = re.compile(r"^:{4}$")
TAB_SET_END = re.compile(r"^:{5,}$")
LEGEND_ROW = re.compile(r"^-\s*([^\s=]+)\s*=\s*(.+?)\s*$")

TOKEN = re.compile(
    r'<h([1-6])[^>]*>(.*?)</h\1>'
    r'|<label class="sd-tab-label"[^>]*>(.*?)</label>'
    r'|<div class="highlight-([\w-]+) notranslate"><div class="highlight"><pre>(.*?)</pre>',
    re.S)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, timeout=60, retries=3, sleep=3.0):
    """抓一个页面,返回带 sha256 / 字节数 / 抓取时间的字典。失败会重试后抛错。"""
    last = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                return {
                    "url": url,
                    "http_status": int(getattr(response, "status", 200)),
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "text": raw.decode("utf-8", errors="replace"),
                    "fetched_at": utc_now(),
                }
        except Exception as error:  # noqa: BLE001 - 网络异常统一重试
            last = error
            if attempt < retries:
                time.sleep(sleep)
    raise RuntimeError("抓取失败 %s:%s" % (url, last))


def plain(fragment):
    text = re.sub(r"<[^>]+>", "", fragment)
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def code_text(fragment):
    text = re.sub(r"<[^>]+>", "", fragment)
    return html_lib.unescape(text).strip("\n")


def split_cells(line):
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    return [cell.strip() for cell in text.split("|")]


def table_kind(path):
    joined = " / ".join(path)
    if "Pooling Models" in joined:
        return "pooling"
    if "Multimodal" in joined:
        return "multimodal"
    if "Text-Only" in joined:
        return "text-only"
    return "other"


def tutorial_ref(cell):
    """Doc 单元格 -> (教程键, 相对路径)。不是教程链接时返回 (None, None)。"""
    match = re.search(r"\[([^\]]*)\]\(([^)]+)\)", cell or "")
    if not match:
        return None, None
    href = re.sub(r"^(\.\./)+", "", match.group(2).strip())
    if not href.startswith("tutorials/") or not href.endswith(".md"):
        return None, None
    return href[len("tutorials/"):-len(".md")].split("/")[-1], href


def parse_matrix(markdown):
    """把官方支持矩阵的 markdown 拆成「按硬件族分表的能力表」。"""
    legend, section = {}, {}
    family, header, body = None, None, []
    tables = []

    def flush():
        nonlocal header, body
        if header and body:
            tables.append(build_table(header, body, section, family))
        header, body = None, []

    for raw in markdown.split("\n"):
        line = raw.rstrip("\n")
        stripped = line.strip()

        entry = LEGEND_ROW.match(stripped)
        if entry and entry.group(1) in ("✅", "🔵", "❌", "🟡"):
            legend[entry.group(1)] = entry.group(2)
            continue

        heading = HEADING.match(stripped)
        if heading:
            level = len(heading.group(1))
            section[level] = heading.group(2).strip().strip("#").strip()
            for key in [item for item in section if item > level]:
                del section[key]
            flush()
            continue

        tab = TAB_ITEM.match(stripped)
        if tab:
            flush()
            family = tab.group(1).strip()
            continue
        if TAB_ITEM_END.match(stripped):
            flush()
            family = None
            continue
        if TAB_SET_END.match(stripped):
            flush()
            family = None
            continue

        if stripped.startswith("|"):
            if header is None:
                if SEPARATOR.match(stripped):
                    continue
                header = split_cells(stripped)
                continue
            if SEPARATOR.match(stripped):
                continue
            body.append(split_cells(stripped))
            continue

        flush()

    flush()
    return legend, tables


def build_table(header, body, section, family):
    path = [section[key] for key in sorted(section) if key >= 2]
    rows = []
    for cells in body:
        cells = cells + [""] * (len(header) - len(cells))
        row = dict(zip(header, cells))
        key, href = tutorial_ref(row.get("Doc", ""))
        label = re.search(r"\[([^\]]*)\]", row.get("Doc", ""))
        rows.append({
            "model": row.get("Model", ""),
            "support": row.get("Support", ""),
            "note": row.get("Note", ""),
            "hardware": row.get("Supported Hardware", "") or family or "",
            "capabilities": {name: row[name] for name in header
                             if name not in ("Model", "Support", "Note", "Doc")},
            "doc_label": (label.group(1).strip() if label else ""),
            "tutorial": key,
            "tutorial_path": href,
        })
    return {
        "section": path,
        "kind": table_kind(path),
        "generative": any("Generative Models" in item for item in path),
        "hardware_family": family or "",
        "columns": header,
        "rows": rows,
    }


def parse_tutorial(html):
    """按文档顺序抽出「小节 + tab + 语言 + 代码」,命令逐字来自官方页面。"""
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S)
    heading, tab = {}, None
    blocks = []
    for match in TOKEN.finditer(body):
        if match.group(1):
            level = int(match.group(1))
            heading[level] = plain(match.group(2)).rstrip("#").strip()
            for key in [item for item in heading if item > level]:
                del heading[key]
            if level <= 3:
                tab = None
            continue
        if match.group(3) is not None:
            tab = plain(match.group(3))
            continue
        language = match.group(4)
        code = code_text(match.group(5))
        if not code:
            continue
        blocks.append({
            "section": " > ".join(heading[key] for key in sorted(heading) if key >= 2),
            "tab": tab or "",
            "language": language,
            "code": code,
        })
    title = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    return (plain(title.group(1)) if title else "", blocks)


def build(markdown_page, tutorials):
    legend, tables = parse_matrix(markdown_page["text"])
    rows = [row for table in tables for row in table["rows"]]
    if len(tables) < MIN_TABLES or len(rows) < MIN_ROWS:
        raise RuntimeError("支持矩阵结构变了:只解析出 %d 张表 / %d 行(下限 %d / %d)"
                           % (len(tables), len(rows), MIN_TABLES, MIN_ROWS))
    if not any("Supported Hardware" in table["columns"] for table in tables):
        raise RuntimeError("解析结果里没有 `Supported Hardware` 列,页面结构可能变了")
    families = sorted({row["hardware"] for row in rows if row["hardware"]})

    cards = json.loads((PORTAL_DIR / "data" / "gpu-catalog.json").read_text(
        encoding="utf-8"))["gpus"]
    matches = []
    for card in cards:
        if card.get("ecosystem") != "cann":
            continue
        family = engine.official_family_match(card, families)
        matches.append({"gpu_id": card["id"], "family": family,
                        "basis": engine.OFFICIAL_FAMILY_BASIS})

    return {
        "schema": 1,
        "note": ("vllm-ascend 官方支持矩阵与逐模型教程命令的快照。只由 "
                 "deploy-portal/tools/sync_ascend.py 写入,不要手改;"
                 "能力值与命令逐字来自官方页面,不在这里改写。"),
        "generated_at": markdown_page["fetched_at"],
        "source": {
            "project": "vLLM Ascend (vllm-project/vllm-ascend)",
            "project_url": PROJECT_URL,
            "doc_version": DOC_VERSION,
            "doc_channel": DOC_CHANNEL,
            "channel_quote": "You are viewing the stable release (%s) documentation."
                             % DOC_VERSION,
            "base_url": DOC_BASE,
            "matrix_page": MATRIX_HTML,
            "policy": ("只引用公开可核实的官方文档;每次抓取留痕 URL + 文档版本 + "
                       "抓取时间 + sha256。第三方能自己打开同一页面核对。"),
        },
        "legend": legend,
        "hardware_families": families,
        "tables": tables,
        "tutorials": tutorials,
        "card_matches": matches,
    }


def collect(tables):
    """抓取矩阵里每个 `Doc` 链接指向的官方教程。

    包括池化(embedding/reranker)模型的教程:矩阵是官方对这张卡的全部口径,
    漏掉一半会让「某行有 Doc 链接但平台没有对应命令」变成一句解释不清的空话。
    """
    keep = {}
    for table in tables:
        for row in table["rows"]:
            if row["tutorial"] and row["tutorial_path"]:
                keep[row["tutorial"]] = row["tutorial_path"]

    tutorials, pages = {}, []
    for key in sorted(keep):
        url = DOC_BASE + keep[key][:-len(".md")] + ".html"
        page = fetch(url)
        title, blocks = parse_tutorial(page["text"])
        tutorials[key] = {
            "title": title,
            "url": url,
            "sha256": page["sha256"],
            "bytes": page["bytes"],
            "fetched_at": page["fetched_at"],
            "blocks": blocks,
        }
        pages.append(page)
        print("   抓取 %-34s %d 字节 · %d 个代码块" % (key, page["bytes"], len(blocks)))
    return tutorials, pages


def main(argv=None):
    parser = argparse.ArgumentParser(description="抓取 vllm-ascend 官方支持矩阵(只写 data/)")
    parser.add_argument("--check", action="store_true", help="只核实 sha256 是否漂移,不写文件")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    previous = None
    if OUT.is_file():
        previous = json.loads(OUT.read_text(encoding="utf-8"))

    print("来源: %s(%s 稳定版)" % (MATRIX_HTML, DOC_VERSION))
    matrix = fetch(MATRIX_MD)
    print("   抓取支持矩阵 %d 字节 · sha256 %s" % (matrix["bytes"], matrix["sha256"][:16]))

    legend, tables = parse_matrix(matrix["text"])
    rows = [row for table in tables for row in table["rows"]]
    if len(tables) < MIN_TABLES or len(rows) < MIN_ROWS:
        print("FAIL 支持矩阵结构变了:只解析出 %d 张表 / %d 行" % (len(tables), len(rows)))
        return 1

    if args.check:
        if previous is None:
            print("FAIL 还没有 %s,先跑一次不带 --check 的同步" % OUT.name)
            return 1
        stored = previous["source"]
        drift = []
        if stored["doc_version"] != DOC_VERSION:
            drift.append("文档版本:%s -> %s" % (stored["doc_version"], DOC_VERSION))
        old_page = next((item for item in previous.get("pages", [])
                         if item["role"] == "support-matrix"), None)
        if old_page and old_page["sha256"] != matrix["sha256"]:
            drift.append("支持矩阵 sha256 变了(%s -> %s)"
                         % (old_page["sha256"][:12], matrix["sha256"][:12]))
        old_tables = len(previous.get("tables") or [])
        if old_tables != len(tables):
            drift.append("表数:%d -> %d" % (old_tables, len(tables)))
        for key, item in sorted((previous.get("tutorials") or {}).items()):
            if key not in {row["tutorial"] for table in tables for row in table["rows"]}:
                continue
            page = fetch(item["url"])
            if page["sha256"] != item["sha256"]:
                drift.append("教程 %s sha256 变了" % key)
        if drift:
            for line in drift:
                print("FAIL %s" % line)
            print("FAIL 官方文档已漂移;重跑 `python deploy-portal/tools/sync_ascend.py` 并复核差异")
            return 1
        print("可达 支持矩阵与 %d 份教程都可访问且 sha256 未漂移"
              % len(previous.get("tutorials") or {}))
        return 0

    families = sorted({row["hardware"] for row in rows if row["hardware"]})
    print("   硬件族:%s" % "、".join(families))
    tutorials, pages = collect(tables)

    payload = build(matrix, tutorials)
    payload["pages"] = ([{"role": "support-matrix", "url": MATRIX_MD,
                          "http_status": matrix["http_status"], "bytes": matrix["bytes"],
                          "sha256": matrix["sha256"], "fetched_at": matrix["fetched_at"]}]
                        + [{"role": "tutorial", "model": key, "url": item["url"],
                            "http_status": 200, "bytes": item["bytes"],
                            "sha256": item["sha256"], "fetched_at": item["fetched_at"]}
                           for key, item in sorted(tutorials.items())])
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    matched = [item for item in payload["card_matches"] if item["family"]]
    print("写回 %s" % OUT)
    print("   %d 张表 · %d 行能力 · %d 份教程 · 命中 %d/%d 张昇腾卡"
          % (len(payload["tables"]), len(rows), len(tutorials),
             len(matched), len(payload["card_matches"])))
    for item in payload["card_matches"]:
        print("   %-26s -> %s" % (item["gpu_id"], item["family"] or "(未命中,只报原因)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

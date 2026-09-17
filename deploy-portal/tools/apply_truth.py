#!/usr/bin/env python3
"""用实测值订正 models.csv / model-families.csv。

背景:目录里原先有相当一部分 `weight_gib` 是「社区典型估算」、`context_k` 是按印象填的,
`license` 也有几处与官方仓库不符。本工具把这三个字段换成实测/官方核实值,并给每一行
留下可追溯的凭据(repo + revision + endpoint + 抓取时间)。

数据来源优先级:

1. `data/catalog-verified.json`(本工具维护的核实缓存,离线可复现);
2. `data/hf-catalog.json`(sync_hf.py 的快照);
3. 直连镜像现抓(仅当上面两处都没有该仓库时)。

人工核实过的例外写在下面的常量表里,每条都注明依据,不用推测值。

用法:
    python deploy-portal/tools/apply_truth.py --check    # 只报告差异,不写文件
    python deploy-portal/tools/apply_truth.py            # 写回两个 CSV
    python deploy-portal/tools/apply_truth.py --refresh  # 重新抓取核实缓存
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
PORTAL_DIR = TOOLS_DIR.parent
WORKSPACE = PORTAL_DIR.parent
MODELS_CSV = WORKSPACE / "model-selector" / "models.csv"
FAMILIES_CSV = WORKSPACE / "model-selector" / "model-families.csv"
VERIFIED_JSON = PORTAL_DIR / "data" / "catalog-verified.json"
SNAPSHOT_JSON = PORTAL_DIR / "data" / "hf-catalog.json"
RECIPES_JSON = PORTAL_DIR / "data" / "recipes.json"

CACHE_FIELDS = (
    "repo", "endpoint", "revision", "last_modified", "license_id", "license_name",
    "total_params_b", "weight_gib", "context_k", "max_position_embeddings",
    "quant_method", "gated", "fetched_at", "params_by_dtype",
)

# 显存计算要用的 attention 结构。这些值决定 KV cache 随上下文增长多快,
# 不同架构口径不同(MLA / 混合线性 / GQA),所以必须逐仓库记录而不是套一个公式。
ATTENTION_FIELDS = (
    "attention_shape", "kv_lora_rank", "qk_rope_head_dim",
    "full_attention_layers", "linear_attention_layers",
)

# 部署档 -> 该档真正使用的 artifact 仓库。原目录多写成组织主页或基座仓库,
# 导致「声明值 vs 实测值」比的是另一个东西。
PROFILE_REPOS = {
    "deepseek-r1-bf16": "unsloth/DeepSeek-R1-BF16",
    "llama31-405b-bf16": "meta-llama/Meta-Llama-3.1-405B-Instruct",
    "glm52-int4-a100": "cyankiwi/GLM-5.2-AWQ-INT4",
    "kimi-k26-awq": "moonshotai/Kimi-K2.6",
    "deepseek-v31-int4": "QuantTrio/DeepSeek-V3.1-AWQ",
    "qwen35-397b-awq-a40": "QuantTrio/Qwen3.5-397B-A17B-AWQ",
    "qwen35-397b-awq": "QuantTrio/Qwen3.5-397B-A17B-AWQ",
    "minimax-m27-fp8": "MiniMaxAI/MiniMax-M2.7",
    "qwen3-235b-awq": "QuantTrio/Qwen3-235B-A22B-Instruct-2507-AWQ",
    "minimax-m27-awq-a40": "QuantTrio/MiniMax-M2.7-AWQ",
    "minimax-m27-awq": "QuantTrio/MiniMax-M2.7-AWQ",
    "qwen35-122b-fp8": "Qwen/Qwen3.5-122B-A10B-FP8",
    "qwen35-122b-awq": "QuantTrio/Qwen3.5-122B-A10B-AWQ",
    "qwen3-coder-30b-awq": "QuantTrio/Qwen3-Coder-30B-A3B-Instruct-AWQ",
    "qwen3-32b-awq": "Qwen/Qwen3-32B-AWQ",
    "qwen3-14b-awq": "Qwen/Qwen3-14B-AWQ",
    "qwen3-8b-bf16": "Qwen/Qwen3-8B",
    "qwen3-8b-awq": "Qwen/Qwen3-8B-AWQ",
    "qwen3-4b-bf16": "Qwen/Qwen3-4B",
}

# 家族库 -> 官方仓库。source 是组织主页的必须在这里显式指定。
FAMILY_REPOS = {
    "deepseek-v31": "deepseek-ai/DeepSeek-V3.1",
    "qwen35-397b": "Qwen/Qwen3.5-397B-A17B",
    "qwen35-122b": "Qwen/Qwen3.5-122B-A10B",
    "qwen3-coder-480b": "Qwen/Qwen3-Coder-480B-A35B-Instruct",
    "qwen3-coder-30b": "Qwen/Qwen3-Coder-30B-A3B-Instruct",
    "kimi-k2-thinking": "moonshotai/Kimi-K2-Thinking",
    "kimi-k26": "moonshotai/Kimi-K2.6",
    "minimax-m2": "MiniMaxAI/MiniMax-M2",
    "minimax-m21": "MiniMaxAI/MiniMax-M2.1",
    "minimax-m27": "MiniMaxAI/MiniMax-M2.7",
    "internvl3-78b": "OpenGVLab/InternVL3-78B",
    "internvl3-14b": "OpenGVLab/InternVL3-14B",
    # 官方 databricks/dbrx-instruct 是 gated(API 401),用社区镜像核实并如实标注。
    "dbrx-instruct": "alpindale/dbrx-instruct",
}

# 用镜像核实的仓库:必须在 notes 里写明,不能让读者以为数据来自官方仓库。
MIRROR_NOTES = {
    "alpindale/dbrx-instruct":
        "核实来源:官方 databricks/dbrx-instruct 为 gated(API 返回 401,config 也取不到),"
        "登记值改由社区镜像核实;另一镜像 LnL-AI/dbrx-base-converted-v2 给出相同的 "
        "131.6B / 245.1GiB,两处相互印证",
}

# 上下文:官方模型卡明确声明、但仓库 config.json 里没有打开的值。
#
# 这些**不是估算**——是「原生 N,配合 YaRN 等扩展可达 M」里的那个 M,官方模型卡逐条写明。
# 部署时必须在 config.json 里打开对应 rope_scaling,所以 notes 里如实标注。
_YARN_128 = "官方模型卡:32,768 原生 / 131,072(需在 config.json 打开 YaRN)"
_QWEN25_128 = "官方模型卡:131,072 全量 / 32,768 默认(需打开 YaRN)"
CONTEXT_FROM_CARD = {
    # Qwen2.5 文本与 VL 系列
    "Qwen/Qwen2.5-72B-Instruct": (128, _QWEN25_128),
    "Qwen/Qwen2.5-32B-Instruct": (128, _QWEN25_128),
    "Qwen/Qwen2.5-14B-Instruct": (128, _QWEN25_128),
    "Qwen/Qwen2.5-7B-Instruct": (128, _QWEN25_128),
    "Qwen/Qwen2.5-3B-Instruct": (32, "官方模型卡:32,768(需打开 YaRN)"),
    "Qwen/Qwen2.5-Coder-32B-Instruct": (128, _QWEN25_128),
    "Qwen/Qwen2.5-VL-72B-Instruct": (128, _QWEN25_128),
    "Qwen/Qwen2.5-VL-32B-Instruct": (128, _QWEN25_128),
    "Qwen/Qwen2.5-VL-7B-Instruct": (128, _QWEN25_128),
    # Qwen3 原生 32K 的一代
    "Qwen/Qwen3-8B": (128, _YARN_128),
    "Qwen/Qwen3-14B": (128, _YARN_128),
    "Qwen/Qwen3-32B": (128, _YARN_128),
    "Qwen/Qwen3-30B-A3B": (128, _YARN_128),
    "Qwen/Qwen3-4B": (128, _YARN_128),
    "Qwen/Qwen3-8B-AWQ": (128, _YARN_128),
    "Qwen/Qwen3-14B-AWQ": (128, _YARN_128),
    "Qwen/Qwen3-32B-AWQ": (128, _YARN_128),
    "Qwen/Qwen3-1.7B": (32, "官方模型卡:32,768") ,
    "Qwen/Qwen3-0.6B": (32, "官方模型卡:32,768"),
    "Qwen/Qwen3-Embedding-8B": (32, "官方模型卡:32k"),
    "Qwen/Qwen3-Embedding-4B": (32, "官方模型卡:32k"),
    "Qwen/Qwen3-Embedding-0.6B": (32, "官方模型卡:32k"),
    "Qwen/Qwen3-Reranker-8B": (32, "官方模型卡:32k"),
    "HuggingFaceTB/SmolLM3-3B": (128, "官方模型卡:64k 训练 / 128k(需打开 YaRN)"),
    "meta-llama/Meta-Llama-3.1-405B-Instruct": (128, "官方模型卡标称 128K;仓库 gated,config.json 无法直取"),
}

# 只加说明、不改值:模型卡声明的「可扩展上限」。
EXTENDED_NOTES = {
    "Qwen/Qwen3.5-397B-A17B": "模型卡:262,144 原生,可扩展到约 1,010,000;建议保持 ≥128K",
    "Qwen/Qwen3.5-122B-A10B": "模型卡:262,144 原生,可扩展到约 1,010,000",
    "Qwen/Qwen3.5-122B-A10B-FP8": "模型卡:262,144 原生,可扩展到约 1,010,000",
    "Qwen/Qwen3-235B-A22B-Instruct-2507": "模型卡:262,144 原生,可扩展到约 1,010,000",
    "Qwen/Qwen3-235B-A22B-Thinking-2507": "模型卡:262,144 原生",
    "Qwen/Qwen3-Coder-480B-A35B-Instruct": "模型卡:262,144 原生,可扩展到约 1M(YaRN)",
    "Qwen/Qwen3-Coder-30B-A3B-Instruct": "模型卡:262,144 原生,可扩展到约 1M(YaRN)",
    "QuantTrio/Qwen3-Coder-30B-A3B-Instruct-AWQ": "模型卡:262,144 原生,可扩展到约 1M(YaRN)",
    "QuantTrio/Qwen3-235B-A22B-Instruct-2507-AWQ": "模型卡:262,144 原生,可扩展到约 1,010,000",
}

# HF 的 cardData.license_name:只有这里列出的仓库才有,用来把 `other` 细分开。
# 值来自 2026-09-16 实测 /api/models 返回。
LICENSE_NAME_BY_REPO = {
    "moonshotai/Kimi-K2-Instruct": "modified-mit",
    "moonshotai/Kimi-K2-Thinking": "modified-mit",
    "moonshotai/Kimi-K2.6": "modified-mit",
    "MiniMaxAI/MiniMax-M2": "modified-mit",
    "MiniMaxAI/MiniMax-M2.1": "modified-mit",
    "MiniMaxAI/MiniMax-M2.7": "other",
    "OpenGVLab/InternVL3-78B": "qwen",
    "Qwen/Qwen2.5-72B-Instruct": "qwen",
    "Qwen/Qwen2.5-VL-72B-Instruct": "qwen",
    "Qwen/Qwen2.5-3B-Instruct": "qwen-research",
    "meta-llama/Llama-4-Maverick-17B-128E-Instruct": "llama4",
    "meta-llama/Llama-4-Scout-17B-16E-Instruct": "llama4",
    "mistralai/Mistral-Large-Instruct-2407": "mrl",
    "mistralai/Codestral-22B-v0.1": "mnpl",
}

# 许可:HF 没打 license 标签、但官方仓库/模型卡写明了的,按官方写明的登记。
LICENSE_OVERRIDE = {
    "deepseek-ai/DeepSeek-V3": (
        "other:deepseek-model-agreement", "DeepSeek Model Agreement",
        "HF 未打 license 标签;官方模型卡徽章写明 Model License = Model Agreement"),
    # 量化仓库自标的许可与官方不一致时,以官方权重许可为准(量化件是派生品)。
    "QuantTrio/MiniMax-M2.7-AWQ": (
        "other", "厂商自定义许可(HF: other)",
        "量化仓库自标 license_name=modified-mit,但权重许可随官方 MiniMax-M2.7"
        "(HF license=other,链接 MiniMax LICENSE),此处以官方为准"),
    "alpindale/dbrx-instruct": (
        "other", "DBRX License(未能核实)",
        "许可:官方仓库 gated、镜像未返回许可字段,未能核实;沿用原登记名并标注未核实"),
}

# 许可:HF 的 license 字段与模型卡 license_name 组合后的规范化显示名。
LICENSE_DISPLAY = {
    "mit": "MIT",
    "apache-2.0": "Apache-2.0",
    "bsd-3-clause": "BSD-3-Clause",
    "cc-by-4.0": "CC-BY-4.0",
    "cc-by-nc-4.0": "CC-BY-NC-4.0",
    "gemma": "Gemma License",
    "llama3.1": "Llama 3.1 Community",
    "llama3.2": "Llama 3.2 Community",
    "llama3.3": "Llama 3.3 Community",
    "llama4": "Llama 4 Community",
    "other:modified-mit": "Modified MIT",
    "other:qwen": "Qwen License",
    "other:qwen-research": "Qwen Research License",
    "other:mrl": "Mistral Research License",
    "other:mnpl": "MNPL",
    "other:gemma": "Gemma License",
    "other:llama4": "Llama 4 Community",
    "other": "厂商自定义许可(HF: other)",
    "other:other": "厂商自定义许可(HF: other)",
    "other:deepseek-model-agreement": "DeepSeek Model Agreement",
}

# 判定「宽松许可」只看这个机器可读的 id,不看展示名。
PERMISSIVE_LICENSE_IDS = {"mit", "apache-2.0", "bsd-3-clause", "cc-by-4.0"}


def resolve_license(facts, repo):
    """把 HF 的 license 字段 + cardData.license_name 归一成 <id> 与显示名。"""
    if repo in LICENSE_OVERRIDE:
        return LICENSE_OVERRIDE[repo]
    license_id = facts.get("license_id") or ""
    if license_id == "other":
        name = LICENSE_NAME_BY_REPO.get(repo) or facts.get("license_name")
        if name:
            license_id = "other:%s" % str(name).strip().lower()
    if license_id == "other":
        return license_id, LICENSE_DISPLAY["other"], \
            "HF license=other 且未给 license_name,按 HF 原样登记"
    if not license_id or license_id in ("unknown", "other"):
        return "", "", ""
    display = LICENSE_DISPLAY.get(license_id)
    if display is None:
        display = license_id
    return license_id, display, ""

READ_ME_NOTE = "本行数值由 deploy-portal/tools/apply_truth.py 按实测订正"


def _load_module(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync_hf = _load_module("sync_hf", TOOLS_DIR / "sync_hf.py")


def repo_from_source(source):
    """从 source 列解析出仓库 id;source 只写到组织时返回空串。"""
    text = str(source or "").strip().rstrip("/")
    for prefix in ("https://huggingface.co/", "https://hf-mirror.com/"):
        if text.startswith(prefix):
            rest = text[len(prefix):]
            return rest if rest.count("/") == 1 else ""
    return ""


def license_id_of(info):
    base = sync_hf.license_from(info.get("cardData"), info.get("tags")) or ""
    card = info.get("cardData") or {}
    name = card.get("license_name")
    if base == "other" and name:
        return "other:%s" % str(name).strip().lower()
    return base


def context_of(config, depth=0):
    if not isinstance(config, dict) or depth > 3:
        return None
    for key in ("max_position_embeddings", "seq_length", "n_positions", "max_seq_len"):
        value = config.get(key)
        if isinstance(value, int) and value > 0:
            return value
    for key in ("text_config", "language_config", "llm_config"):
        nested = context_of(config.get(key), depth + 1)
        if nested:
            return nested
    return None


def fetch_facts(fetcher, repo, want_weight):
    info, _, base = fetcher.get_json("/api/models/" + repo)
    config = {}
    try:
        raw = fetcher.get_raw("/%s/raw/main/config.json" % repo)
        if raw:
            config = json.loads(raw)
    except Exception:  # noqa: BLE001
        config = info.get("config") or {}
    if not config:
        config = info.get("config") or {}
    safetensors = info.get("safetensors") or {}
    total = safetensors.get("total")
    facts = {
        "repo": repo,
        "endpoint": base.replace("https://", ""),
        "revision": info.get("sha"),
        "last_modified": info.get("lastModified"),
        "license_id": license_id_of(info),
        "license_name": (info.get("cardData") or {}).get("license_name"),
        "params_by_dtype": safetensors.get("parameters") or {},
        "total_params_b": round(total / 1e9, 2) if total else None,
        "context_k": None,
        "max_position_embeddings": None,
        "quant_method": (config.get("quantization_config") or {}).get("quant_method")
                        if isinstance(config.get("quantization_config"), dict) else None,
        "gated": info.get("gated"),
        "fetched_at": sync_hf.utc_now(),
    }
    positions = context_of(config)
    if positions:
        facts["max_position_embeddings"] = positions
        facts["context_k"] = round(positions / 1024, 1)
    if want_weight:
        tree, _, _ = fetcher.get_json("/api/models/%s/tree/main?recursive=true" % repo)
        weights = [i for i in tree if i.get("type") == "file"
                   and (i.get("path") or "").endswith(".safetensors")]
        if weights:
            facts["weight_gib"] = round(
                sum(i.get("size") or 0 for i in weights) / 1024 ** 3, 1)
    return facts


def seed_cache_from_truth(cache):
    """把采集阶段的结果灌进缓存,避免重复抓取。"""
    truth_path = WORKSPACE / ".tmp" / "truth.json"
    if not truth_path.is_file():
        return 0
    data = json.loads(truth_path.read_text(encoding="utf-8"))
    entries = cache.setdefault("entries", {})
    seeded = 0
    for bucket in ("profiles", "families"):
        for entry in data.get(bucket) or []:
            truth = entry.get("truth")
            if not truth:
                continue
            repo = truth["repo"]
            facts = entries.get(repo) or {}
            incoming = {
                "repo": repo,
                "endpoint": "hf-mirror.com",
                "revision": truth.get("revision"),
                "last_modified": truth.get("last_modified"),
                "license_id": _license_id_from_truth(truth),
                "license_name": None,
                "total_params_b": truth.get("total_params_b"),
                "weight_gib": truth.get("weight_gib"),
                "context_k": truth.get("context_k"),
                "max_position_embeddings": truth.get("max_position_embeddings"),
                "quant_method": truth.get("quant_method"),
                "gated": truth.get("gated"),
                "params_by_dtype": truth.get("params_by_dtype") or {},
                "fetched_at": data.get("fetched_at") or "2026-09-16",
            }
            # 同一个仓库可能先以「部署档」采集(带权重)、后以「家族库」采集(不带权重),
            # 后者不能用 None 把先前的有效值冲掉。
            for key, value in incoming.items():
                if value in (None, "", {}, []) and facts.get(key):
                    continue
                facts[key] = value
            entries[repo] = facts
            seeded += 1
    return seeded


def _license_id_from_truth(truth):
    base = truth.get("license") or ""
    return base


def load_cache():
    if VERIFIED_JSON.is_file():
        return json.loads(VERIFIED_JSON.read_text(encoding="utf-8"))
    return {"schema": 1, "note": "apply_truth.py 维护的核实缓存;每条都带 repo/revision/endpoint。",
            "entries": {}}


def overlay_attention(cache):
    """把 sync_hf 快照里的 attention 结构补进核实缓存(纯本地读取,可离线复现)。"""
    if not SNAPSHOT_JSON.is_file():
        return 0
    try:
        details = (json.loads(SNAPSHOT_JSON.read_text(encoding="utf-8"))
                   .get("details") or {})
    except ValueError:
        return 0
    filled = 0
    for repo, facts in cache.setdefault("entries", {}).items():
        record = details.get(repo) or {}
        gained = False
        for field in ATTENTION_FIELDS:
            value = record.get(field)
            if value in (None, "", {}, []):
                continue
            if facts.get(field) in (None, "", {}, []):
                facts[field] = value
                gained = True
        if gained:
            filled += 1
    return filled


def save_cache(cache):
    VERIFIED_JSON.write_text(
        json.dumps(cache, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


INFER_RULES = (("int4", ("I32", "I8", "U8")), ("fp8", ("F8_E4M3", "F8_E5M2")),
               ("bf16", ("BF16",)), ("fp16", ("F16",)))


def infer_quant(dtypes):
    """从 safetensors 的 dtype 分布反推量化档,用来验证 artifact 是否名副其实。"""
    if not dtypes:
        return ""
    ranked = sorted(dtypes.items(), key=lambda item: item[1] or 0, reverse=True)
    for name, keys in INFER_RULES:
        if ranked[0][0] in keys:
            return name
    return ranked[0][0].lower()


def quant_class(text):
    lowered = str(text or "").lower()
    for name, keywords in (("int4", ("awq", "int4", "gptq", "w4a16")),
                           ("fp8", ("fp8", "w8a8")),
                           ("bf16", ("bf16", "bfloat16", "完整精度"))):
        if any(keyword in lowered for keyword in keywords):
            return name
    return ""


def recipe_profiles():
    """有可执行部署方法的部署档。

    写进 CSV 而不是只放在网站侧:推荐打分要按「有没有部署方法」加减分,命令行和
    网站必须用同一份判断,否则同一个硬件会得出不同的首选。
    """
    if not RECIPES_JSON.is_file():
        return set()
    try:
        data = json.loads(RECIPES_JSON.read_text(encoding="utf-8"))
    except ValueError:
        return set()
    return {item["profile_id"] for item in (data.get("recipes") or []) if item.get("profile_id")}
def read_rows(path):
    with io.open(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_rows(path, fieldnames, rows):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in fieldnames})
    path.write_text(buffer.getvalue(), encoding="utf-8")


def append_note(existing, addition):
    existing = (existing or "").strip().rstrip("；;")
    if addition in existing:
        return existing
    return (existing + "；" + addition).strip("；") if existing else addition


def as_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def reconcile_thresholds(row, note):
    """订正完权重后,把与显存/磁盘/主存门槛对不上的地方改到真实可行值。

    只做「抬高到实测权重放得下」这一件事:门槛是判断值,但低于权重就变成假话了。
    """
    weight = as_number(row.get("weight_gib"))
    if not weight:
        return
    gpu = as_number(row.get("min_gpu_count"))
    per = as_number(row.get("min_vram_per_gpu_gib"))
    floor = as_number(row.get("min_total_vram_gib"))
    if gpu and per:
        machine = gpu * per
        # 权重吃掉九成显存时,「最低总显存」必须按整机算,否则等于在说还留有余量。
        if machine >= weight and floor and weight / floor > 0.92 and floor < machine:
            row["min_total_vram_gib"] = "%g" % machine
            row["recommended_total_vram_gib"] = "%g" % machine
            note("权重占整机显存 %.0f%%,最低/推荐总显存按 %g×%gGiB 整机计;KV 与并发余量极小"
                 % (weight / machine * 100, gpu, per))
    for field, ratio, label in (("min_disk_gib", 1.25, "磁盘"),
                                ("min_host_ram_gib", 1.2, "主存")):
        current = as_number(row.get(field))
        if current and current < weight:
            raised = int(weight * ratio) + 1
            row[field] = "%d" % raised
            note("原登记%s门槛 %gGiB 低于实测权重,已抬高到 %dGiB" % (label, current, raised))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只报告差异,不写文件")
    parser.add_argument("--refresh", action="store_true", help="重新抓取核实缓存")
    parser.add_argument("--seed", action="store_true", help="从 .tmp/truth.json 灌入核实缓存")
    args = parser.parse_args(argv)

    cache = load_cache()
    seeded = seed_cache_from_truth(cache) if (args.seed or not cache["entries"]) else 0
    if seeded:
        print("从采集结果灌入核实缓存:%d 条" % seeded)
    filled = overlay_attention(cache)
    if filled:
        print("从 HF 快照补入 attention 结构:%d 个仓库" % filled)
    entries = cache.setdefault("entries", {})

    endpoints = json.loads((PORTAL_DIR / "data" / "sources.json").read_text(
        encoding="utf-8"))["endpoints"]
    fetcher = None

    report = {"changed": 0, "unverified": [], "quant_mismatch": [], "context_kept": []}

    for path, id_column, repo_map, weight_column in (
            (MODELS_CSV, "model_id", PROFILE_REPOS, True),
            (FAMILIES_CSV, "model_id", FAMILY_REPOS, False)):
        fieldnames, rows = read_rows(path)
        for extra in ("verified_repo", "verified_revision", "verified_endpoint",
                      "verified_at", "artifact_params_b", "license_id",
                      "context_source", "attention_kind", "kv_elems_per_token_per_layer",
                      "attention_layers", "attention_basis", "has_recipe"):
            if extra not in fieldnames:
                fieldnames.append(extra)
        with_recipes = recipe_profiles() if weight_column else set()
        for row in rows:
            row_id = row.get(id_column)
            repo = repo_map.get(row_id) or repo_from_source(row.get("source"))
            if not repo:
                report["unverified"].append("%s(无仓库)" % row_id)
                continue
            facts = entries.get(repo)
            if facts is None and (args.refresh or not args.check):
                if fetcher is None:
                    fetcher = sync_hf.Fetcher(endpoints, retries=3, sleep=6.0,
                                              timeout=45, verbose=False)
                try:
                    facts = fetch_facts(fetcher, repo, weight_column)
                except Exception as error:  # noqa: BLE001
                    report["unverified"].append("%s(%s: %s)" % (
                        row_id, repo, str(error)[:60]))
                    continue
                entries[repo] = facts
            if not facts:
                report["unverified"].append("%s(%s)" % (row_id, repo))
                continue

            before = (row.get("weight_gib"), row.get("context_k"), row.get("license"))
            row["verified_repo"] = repo
            row["verified_revision"] = facts.get("revision") or ""
            row["verified_endpoint"] = facts.get("endpoint") or ""
            row["verified_at"] = (facts.get("fetched_at") or "")[:10]
            if facts.get("total_params_b"):
                row["artifact_params_b"] = "%g" % facts["total_params_b"]
            else:
                row["artifact_params_b"] = ""
                row["notes"] = append_note(
                    row.get("notes"),
                    "参数量:该 artifact 未发布 safetensors 参数索引,无法从仓库独立核实,"
                    "沿用官方标称值")
            license_id, license_display, license_note = resolve_license(facts, repo)
            if license_id:
                row["license_id"] = license_id
                row["license"] = license_display
                if license_note:
                    row["notes"] = append_note(row.get("notes"), license_note)
            else:
                row["license_id"] = ""
                row["notes"] = append_note(
                    row.get("notes"),
                    "许可:HF 未给出可核实的许可名,沿用原登记值(未能核实)")

            if weight_column and facts.get("weight_gib"):
                row["weight_gib"] = "%g" % facts["weight_gib"]
            if weight_column:
                row["has_recipe"] = "true" if row_id in with_recipes else ""
            if facts.get("context_k"):
                row["context_k"] = "%d" % round(facts["context_k"])
            if repo in CONTEXT_FROM_CARD:
                value, why = CONTEXT_FROM_CARD[repo]
                row["context_k"] = "%d" % value
                row["context_source"] = "card"
                row["notes"] = append_note(row.get("notes"), "上下文:%s" % why)
                report["context_kept"].append("%s=%dK" % (row_id, value))
            elif facts.get("context_k"):
                raw = facts.get("max_position_embeddings")
                row["context_source"] = "config"
                row["notes"] = append_note(
                    row.get("notes"),
                    "上下文取自仓库 config.json(%s)" % raw)

            if repo in EXTENDED_NOTES:
                row["notes"] = append_note(row.get("notes"), EXTENDED_NOTES[repo])

            shape = facts.get("attention_shape") or {}
            if shape.get("kind") and shape.get("kind") != "unknown":
                row["attention_kind"] = shape["kind"]
                row["kv_elems_per_token_per_layer"] = "%g" % shape["elements_per_token_per_layer"]
                row["attention_layers"] = "%g" % shape["layers"]
                row["attention_basis"] = shape.get("basis") or ""
            else:
                # 拿不到就是拿不到,留空让推荐环节把它标成「无法核实」,
                # 不用一个凭印象的公式顶上去。
                row["attention_kind"] = ""
                row["kv_elems_per_token_per_layer"] = ""
                row["attention_layers"] = ""
                row["attention_basis"] = shape.get("basis") or "未记录"

            if repo in MIRROR_NOTES:
                row["notes"] = append_note(row.get("notes"), MIRROR_NOTES[repo])

            if "openness" in row:
                row["openness"] = (
                    "open-source" if row.get("license_id") in PERMISSIVE_LICENSE_IDS
                    else "open-weights")

            if weight_column:
                reconcile_thresholds(
                    row, lambda text: row.update(
                        {"notes": append_note(row.get("notes"), text)}))

            truth_quant = infer_quant(facts.get("params_by_dtype") or {})
            want_quant = quant_class(row.get("quantization") or row.get("workloads"))
            if truth_quant and want_quant and truth_quant != want_quant:
                report["quant_mismatch"].append(
                    "%s: 声明 %s / 实测 dtype %s" % (row_id, want_quant, truth_quant))

            after = (row.get("weight_gib"), row.get("context_k"), row.get("license"))
            if before != after:
                report["changed"] += 1
                print("%-28s 权重 %-9s→%-9s 上下文 %-6s→%-6s 许可 %s→%s" % (
                    row_id, before[0] or "-", after[0] or "-",
                    before[1] or "-", after[1] or "-", before[2], after[2]))
        if not args.check:
            write_rows(path, fieldnames, rows)
            print("已写回 %s(%d 行)" % (path.relative_to(WORKSPACE), len(rows)))

    if not args.check:
        save_cache(cache)
        print("已更新核实缓存 %s(%d 个仓库)" % (
            VERIFIED_JSON.relative_to(WORKSPACE), len(entries)))

    print("\n汇总:改动 %d 行;未能核实 %d 条;加密档位不符 %d 条;保留模型卡上下文 %d 条" % (
        report["changed"], len(report["unverified"]),
        len(report["quant_mismatch"]), len(report["context_kept"])))
    for label, items in (("未能核实", report["unverified"]),
                         ("档位不符", report["quant_mismatch"])):
        if items:
            print("%s: %s" % (label, "; ".join(items[:12])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

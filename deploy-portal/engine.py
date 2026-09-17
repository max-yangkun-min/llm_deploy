#!/usr/bin/env python3
"""部署管理台 · 推荐引擎适配层。

设计约束:筛选与打分规则只保留一份实现。本文件不重写任何业务规则,
而是把 `model-selector/recommend.py` 当作库导入,把它返回的结构整理成
Web API 需要的 JSON。这样命令行工具和网站永远给出同一个答案。

仅使用 Python 标准库。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PORTAL_DIR = Path(__file__).resolve().parent
WORKSPACE = PORTAL_DIR.parent
MODEL_SELECTOR = WORKSPACE / "model-selector"

MODELS_CSV = MODEL_SELECTOR / "models.csv"
FAMILIES_CSV = MODEL_SELECTOR / "model-families.csv"
RECIPES_JSON = PORTAL_DIR / "data" / "recipes.json"
DEPLOYMENTS_JSON = PORTAL_DIR / "data" / "deployments.json"
HF_CATALOG_JSON = PORTAL_DIR / "data" / "hf-catalog.json"
DOC_SOURCES_JSON = PORTAL_DIR / "data" / "doc-sources.json"
GPU_CATALOG_JSON = PORTAL_DIR / "data" / "gpu-catalog.json"
GPU_CATALOG = GPU_CATALOG_JSON

if not (MODEL_SELECTOR / "recommend.py").is_file():
    raise SystemExit(
        "找不到 model-selector/recommend.py。部署管理台必须与 model-selector 目录放在同一工作区。"
    )

if str(MODEL_SELECTOR) not in sys.path:
    sys.path.insert(0, str(MODEL_SELECTOR))

import recommend as core  # noqa: E402  路径注入后导入,复用同一套规则

PREFERENCES = ("balanced", "quality", "throughput")

# 非 CUDA 生态要单独说明的口径。昇腾没有 sm_xx,登记表里的算力门槛与 CUDA 栈的
# KV 精度公式都不适用,必须写在结果里,不能让页面默认沿用 CUDA 的说法。
ECOSYSTEM_NOTES = {
    "cann": (
        "所选卡是华为昇腾(CANN)生态:昇腾没有 CUDA 算力等级(sm_xx 是 NVIDIA 专有标度),"
        "登记表里的算力门槛、NVIDIA 驱动下限与 CUDA/vLLM 镜像三列对它都不适用,FP8 能力按"
        "厂商页标称值判断;昇腾的 KV cache 精度由 --quantization ascend 的专有量化决定,"
        "没有可核实的公开公式,因此只按权重下界核算。部署方案只在同一生态内关联。"
    ),
}

#: 部署档目录(models.csv)登记的实现属于哪个生态。它没有 ecosystem 列,现有条目
#: 全部是 CUDA 栈(vLLM + CUDA 镜像 + NVIDIA 驱动下限)。把这句如实写进结果,
#: 页面才能说清「匹配到的是 CUDA 栈的档,昇腾要用对应生态的实现」。
PROFILE_CATALOG_ECOSYSTEM = "cuda"


def catalog_ecosystem_note(ecosystem):
    """选卡生态与部署档目录生态不一致时,给出如实说明。"""
    if ecosystem == PROFILE_CATALOG_ECOSYSTEM:
        return ""
    return ("部署档目录登记的都是 %s 栈的实现(vLLM + CUDA 镜像 + NVIDIA 驱动下限),"
            "它没有 ecosystem 列,因此不存在 %s 生态的登记档。下面是按显存实测匹配出的"
            "候选模型,它们的部署方法需要在所选生态下另行核实,不能直接用目录里的 CUDA 栈方案。"
            % (PROFILE_CATALOG_ECOSYSTEM.upper(), ecosystem.upper()))

_cache = {"stamp": None, "rows": [], "families": []}


def rel(path):
    """工作区相对路径,统一正斜杠。"""
    return Path(path).relative_to(WORKSPACE).as_posix()


def _stamp(path):
    try:
        stat = path.stat()
    except OSError:
        return None
    return (str(path), stat.st_size, int(stat.st_mtime))


def load_tables():
    """读取 models.csv / model-families.csv,按文件时间戳缓存。"""
    stamp = (_stamp(MODELS_CSV), _stamp(FAMILIES_CSV))
    if _cache["stamp"] != stamp:
        _cache["rows"] = core.load_catalog(MODELS_CSV)
        _cache["families"] = core.load_catalog(FAMILIES_CSV) if FAMILIES_CSV.is_file() else []
        _cache["stamp"] = stamp
    return _cache["rows"], _cache["families"]


def load_recipes():
    if not RECIPES_JSON.is_file():
        return {"schema": 1, "recipes": [], "mirrors": {"entries": []}}
    with RECIPES_JSON.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_deployments():
    if not DEPLOYMENTS_JSON.is_file():
        return {"schema": 1, "environments": []}
    with DEPLOYMENTS_JSON.open("r", encoding="utf-8") as handle:
        return json.load(handle)


_snapshot_cache = {"hf": None, "docs": None, "hf_stamp": None, "docs_stamp": None}


def load_hf_catalog():
    """读取抓取快照。没有快照时返回空结构而不是报错,页面会提示去跑同步。"""
    stamp = _stamp(HF_CATALOG_JSON)
    if _snapshot_cache["hf_stamp"] != stamp:
        if HF_CATALOG_JSON.is_file():
            with HF_CATALOG_JSON.open("r", encoding="utf-8") as handle:
                _snapshot_cache["hf"] = json.load(handle)
        else:
            _snapshot_cache["hf"] = None
        _snapshot_cache["hf_stamp"] = stamp
    return _snapshot_cache["hf"]


def load_doc_sources():
    stamp = _stamp(DOC_SOURCES_JSON)
    if _snapshot_cache["docs_stamp"] != stamp:
        if DOC_SOURCES_JSON.is_file():
            with DOC_SOURCES_JSON.open("r", encoding="utf-8") as handle:
                _snapshot_cache["docs"] = json.load(handle)
        else:
            _snapshot_cache["docs"] = None
        _snapshot_cache["docs_stamp"] = stamp
    return _snapshot_cache["docs"]


_profile_index_cache = {"stamp": None, "details": None, "docs": None}


def _profile_indexes():
    """details_by_profile / docs_by_profile 的索引随快照缓存,避免每次请求重算。"""
    stamp = (_stamp(HF_CATALOG_JSON), _stamp(DOC_SOURCES_JSON))
    if _profile_index_cache["stamp"] != stamp:
        catalog = load_hf_catalog() or {}
        by_profile = {}
        for record in (catalog.get("details") or {}).values():
            for profile_id in record.get("profiles") or []:
                by_profile.setdefault(profile_id, []).append(record)
        docs = load_doc_sources() or {}
        docs_index = {}
        for record in docs.get("sources") or []:
            for profile_id in (record.get("profiles") or ["*"]):
                docs_index.setdefault(profile_id, []).append(record)
        _profile_index_cache.update({
            "stamp": stamp, "details": by_profile, "docs": docs_index,
        })
    return _profile_index_cache["details"], _profile_index_cache["docs"]


def details_by_profile():
    """profile_id -> [真实仓库记录],用于把目录声明值和抓到的事实对上。"""
    return _profile_indexes()[0]


def docs_by_profile():
    """profile_id -> [权威文档],含只对全局生效(profiles 为空)的引擎文档。"""
    return _profile_indexes()[1]


def _number_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


QUANT_RULES = (
    ("gguf", ("gguf", "q4_", "q5_", "q6_", "q8_", "q3_")),
    ("int4", ("awq", "int4", "gptq", "w4a16", "mxfp4")),
    ("fp8", ("fp8", "w8a8", "e4m3")),
    ("bf16", ("bf16", "bfloat16", "完整精度")),
)


def quant_class(text):
    """把量化描述归到可比较的档位,用于挑出该和哪个仓库对比。"""
    lowered = str(text or "").lower()
    for name, keywords in QUANT_RULES:
        if any(keyword in lowered for keyword in keywords):
            return name
    return ""


def compare(profile, record):
    """把 models.csv 的登记值与上游**当前**值逐项对比,即漂移检查。

    2026-09-16 起 models.csv 的权重/上下文已经是按实测订正过的值,所以这里的差异
    不再是「声明 vs 事实」,而是「当初核实的那份事实,和上游现在还是不是同一份」:
    上游改了权重或 config,这里就会亮出来。
    """
    checks = []

    declared_weight = _number_or_none(profile.get("weight_gib"))
    real_weight = record.get("weight_gib") or record.get("gguf_gib")
    if declared_weight and real_weight:
        delta = round((real_weight - declared_weight) / declared_weight * 100, 1)
        if abs(delta) <= 5:
            level = "match"
        elif abs(delta) <= 15:
            level = "close"
        else:
            level = "differ"
        checks.append({
            "field": "权重大小",
            "recorded": "%s GiB" % declared_weight,
            "upstream": "%s GiB" % real_weight,
            "declared": "%s GiB" % declared_weight,
            "real": "%s GiB" % real_weight,
            "delta_pct": delta,
            "level": level,
        })

    declared_params = _number_or_none(profile.get("total_params_b"))
    real_params = _number_or_none(record.get("total_params_b"))
    if declared_params and real_params:
        delta = round((real_params - declared_params) / declared_params * 100, 1)
        checks.append({
            "field": "参数量",
            "recorded": "%s B" % declared_params,
            "upstream": "%s B" % real_params,
            "declared": "%s B" % declared_params,
            "real": "%s B" % real_params,
            "delta_pct": delta,
            "level": "match" if abs(delta) <= 5 else ("close" if abs(delta) <= 15 else "differ"),
        })

    declared_context = _number_or_none(profile.get("context_k"))
    real_context = _number_or_none(record.get("context_k"))
    if declared_context and real_context:
        # 登记值可能来自官方模型卡的「可扩展上限」,而 config.json 里默认没打开 YaRN。
        # 这种情况不是漂移,是两回事,不能按百分比报差异。
        from_card = (profile.get("context_source") or "") == "card"
        if from_card and real_context < declared_context:
            checks.append({
                "field": "上下文长度",
                "recorded": "%s K(模型卡标称,需打开 YaRN 等扩展)" % declared_context,
                "upstream": "%s K(仓库 config.json 默认值)" % real_context,
                "declared": "%s K" % declared_context,
                "real": "%s K" % real_context,
                "delta_pct": None,
                "level": "match",
            })
        else:
            checks.append({
                "field": "上下文长度",
                "recorded": "%s K" % declared_context,
                "upstream": "%s K" % real_context,
                "declared": "%s K" % declared_context,
                "real": "%s K" % real_context,
                "delta_pct": round((real_context - declared_context) / declared_context * 100, 1),
                "level": "match" if real_context >= declared_context else "differ",
            })

    return checks


def verification_for(profile_id):
    """某个部署档的核对结果:真实仓库 + 与登记值的漂移检查。"""
    rows, _ = load_tables()
    profile = next((item for item in rows if item.get("model_id") == profile_id), None)
    records = details_by_profile().get(profile_id, [])
    if not records:
        return None
    verified = []
    target_quant = quant_class(profile.get("quantization")) if profile else ""
    # 登记值是从哪个仓库的哪个 revision 核实来的,页面上要能点回去看待查证。
    provenance = {
        "repo": (profile or {}).get("verified_repo") or "",
        "revision": (profile or {}).get("verified_revision") or "",
        "endpoint": (profile or {}).get("verified_endpoint") or "",
        "verified_at": (profile or {}).get("verified_at") or "",
        "license_id": (profile or {}).get("license_id") or "",
        "artifact_params_b": (profile or {}).get("artifact_params_b") or "",
    }
    for record in records:
        # 只有量化档位一致的仓库才拿来对权重;BF16 基座和 INT4 量化档直接比会得出无意义的偏差。
        is_reference = bool(target_quant) and record.get("quant") == target_quant
        verified.append({
            "repo": record.get("repo"),
            "revision": record.get("revision"),
            "license": record.get("license"),
            "source_url": record.get("source_url"),
            "total_params_b": record.get("total_params_b"),
            "weight_gib": record.get("weight_gib"),
            "gguf_gib": record.get("gguf_gib"),
            "context_k": record.get("context_k"),
            "last_modified": record.get("last_modified"),
            "downloads": record.get("downloads"),
            "role": record.get("role"),
            "quant": record.get("quant"),
            "is_reference": is_reference,
            "checks": compare(profile, record) if (profile and is_reference) else [],
        })
    return {
        "profile_id": profile_id,
        "target_quant": target_quant,
        "provenance": provenance,
        "repos": verified,
        "docs": docs_by_profile().get(profile_id, []),
    }


def recipe_ecosystem(recipe):
    """部署方案所属生态。没有标的一律按 cuda 处理:现有方案都是 CUDA 栈。"""
    return str(recipe.get("ecosystem") or "cuda").strip().lower()


def recipes_grouped(ecosystem=None):
    """profile_id -> [方案原始记录]。需要生态、硬件摘要等字段时用它。"""
    index = {}
    for recipe in load_recipes().get("recipes", []):
        profile_id = (recipe.get("profile_id") or "").strip()
        if not profile_id:
            continue
        if ecosystem and recipe_ecosystem(recipe) != ecosystem:
            continue
        index.setdefault(profile_id, []).append(recipe)
    return index


def recipes_by_profile(ecosystem=None):
    """profile_id -> [recipe_id],用于把推荐结果和已记录部署方案关联起来。

    传 ecosystem 时只保留同生态的方案:CUDA 栈的部署方法不能挂到昇腾卡上,
    冒充「这台机器可用的方法」。跨生态的方案由调用方另行如实列出。
    """
    return {profile_id: [recipe["id"] for recipe in items]
            for profile_id, items in recipes_grouped(ecosystem).items()}


def _entry(row, failures, warnings, score):
    return {
        "profile": row,
        "score": score,
        "failures": failures,
        "warnings": warnings,
        "recipes": recipes_by_profile().get(row.get("model_id", ""), []),
        "verification": verification_for(row.get("model_id", "")),
    }


def hardware_totals(hw):
    count = core.number(hw.get("gpu_count"))
    per_gpu = core.number(hw.get("vram_per_gpu_gib"))
    return {
        "gpu_count": int(count),
        "vram_per_gpu_gib": per_gpu,
        "total_vram_gib": round(count * per_gpu, 1),
    }


def recommend(hw, preference="balanced", top=5, include_estimates=True):
    """真实匹配:只按实测权重 + 算出的 KV cache + 选定 GPU 的显存核算。

    结果按「能不能跑」和「浪费多少显存」排序,不再给本地方案加分,也不再用
    登记表里的显存门槛当权威;同一模型的同一量化档只保留一条,保证 3-5 条都是
    不同模型。
    """
    if preference not in PREFERENCES:
        preference = "balanced"
    ecosystem = str(hw.get("ecosystem") or "cuda").strip().lower()
    rows, families = load_tables()
    grouped = recipes_grouped()
    compatible, rejected = [], []
    for row in rows:
        row = dict(row)
        candidates = grouped.get(row.get("model_id", ""), [])
        mine = [item for item in candidates if recipe_ecosystem(item) == ecosystem]
        other = [{"id": item["id"], "ecosystem": recipe_ecosystem(item)}
                 for item in candidates if recipe_ecosystem(item) != ecosystem]
        row["has_recipe"] = "true" if mine else ""
        result = core.assess(row, hw, preference)
        memory = result["memory"]
        entry = {
            "profile": row,
            "score": result["score"],
            "failures": result["failures"],
            "warnings": result["warnings"],
            "memory": memory,
            "recipes": [item["id"] for item in mine],
            "recipes_other_ecosystem": other,
            "verification": verification_for(row.get("model_id", "")),
        }
        (rejected if result["failures"] else compatible).append(entry)

    compatible.sort(key=lambda item: (item["score"], core.number(item["profile"]["quality_score"])),
                    reverse=True)
    rejected.sort(key=lambda item: (len(item["failures"]), -item["score"]))

    # 同一模型的同一量化档只留一条:优先留有部署方法的那条,避免 3-5 条里
    # 出现两个只是布局说明不同的同名方案。
    seen, distinct = set(), []
    for item in compatible:
        key = (item["profile"].get("model_name"), core.quant_class(item["profile"].get("quantization")))
        if key in seen:
            continue
        seen.add(key)
        distinct.append(item)

    limit = max(1, int(top))
    return {
        "hardware": hw,
        "preference": preference,
        "ecosystem": ecosystem,
        "ecosystem_note": ECOSYSTEM_NOTES.get(ecosystem, ""),
        "profile_catalog_ecosystem": PROFILE_CATALOG_ECOSYSTEM,
        "stack_note": catalog_ecosystem_note(ecosystem),
        "totals": hardware_totals(hw),
        "plans": distinct[:limit],
        "plans_total": len(distinct),
        "rejected": rejected[:limit],
        "rejected_total": len(rejected),
        "catalog_size": len(rows),
        "scoring_note": (
            "排序依据:质量/吞吐权重(登记值)+ 用途匹配 + 显存利用率(过低或过高都扣分)"
            "+ 是否有可执行部署方法(有则 +3)。是否在某一台机器上验证过不参与排序。"
        ),
    }


def evaluate_profile(hw, profile_id, preference="balanced"):
    """评估单个部署档,用于部署台账里的硬件达标检查。"""
    if preference not in PREFERENCES:
        preference = "balanced"
    rows, _ = load_tables()
    row = next((item for item in rows if item.get("model_id") == profile_id), None)
    if row is None:
        return None
    ecosystem = str(hw.get("ecosystem") or "cuda").strip().lower()
    candidates = recipes_grouped().get(profile_id, [])
    mine = [item for item in candidates if recipe_ecosystem(item) == ecosystem]
    row = dict(row)
    row["has_recipe"] = "true" if mine else ""
    result = core.assess(row, hw, preference)
    return {
        "profile": row,
        "score": result["score"],
        "failures": result["failures"],
        "warnings": result["warnings"],
        "memory": result["memory"],
        "pass": not result["failures"],
        "ecosystem": ecosystem,
        "recipes": [item["id"] for item in mine],
        "recipes_other_ecosystem": [{"id": item["id"], "ecosystem": recipe_ecosystem(item)}
                                    for item in candidates if recipe_ecosystem(item) != ecosystem],
    }


def catalog_payload():
    rows, families = load_tables()
    return {
        "models": rows,
        "families": families,
        "model_count": len(rows),
        "family_count": len(families),
    }


def gpu_catalog():
    """可选的 GPU 型号:只来自 sync_gpus.py 核实过的目录,不让用户手填型号。

    每张卡都带显存、算力、互联与核实凭据;核实失败的条目会被保留但标记出来,
    前端据此禁用而不是假装可用。
    """
    if not GPU_CATALOG.is_file():
        return []
    try:
        snapshot = json.loads(GPU_CATALOG.read_text(encoding="utf-8"))
    except ValueError:
        return []
    return snapshot.get("gpus") or []


def gpu_index():
    return {item["id"]: item for item in gpu_catalog()}


def gpu_snapshot_meta():
    if not GPU_CATALOG.is_file():
        return {"path": rel(GPU_CATALOG), "generated_at": None,
                "verified_count": 0, "gpu_count": 0}
    try:
        snapshot = json.loads(GPU_CATALOG.read_text(encoding="utf-8"))
    except ValueError:
        return {"path": rel(GPU_CATALOG), "generated_at": None,
                "verified_count": 0, "gpu_count": 0}
    return {
        "path": rel(GPU_CATALOG),
        "generated_at": snapshot.get("generated_at"),
        "verified_count": snapshot.get("verified_count"),
        "gpu_count": snapshot.get("gpu_count"),
        "cc_source": snapshot.get("cc_source"),
        "source_policy": snapshot.get("source_policy"),
    }


def hardware_from_gpu(gpu_id, gpu_count, **overrides):
    """把「选中的 GPU + 卡数」变成推荐引擎认识的硬件描述。显存与算力来自核实目录。

    FP8 能力直接读目录里核实过的值,不再用 cc >= 8.9 推导:昇腾没有 sm_xx,
    推导会把官方标注支持 HiF8/mxFP8 的 Atlas 350 误判成不支持 FP8。
    compute_capability 对非 CUDA 生态是 None(不是 0),下游据此跳过 sm 判断。
    """
    gpu = gpu_index().get(gpu_id)
    if gpu is None:
        return None, "未知的 GPU 型号:%s" % gpu_id
    try:
        count = int(gpu_count)
    except (TypeError, ValueError):
        return None, "GPU 数量必须是整数"
    if count < 1:
        return None, "GPU 数量至少为 1"
    hw = {
        "gpu_id": gpu["id"],
        "gpu_name": gpu["name"],
        "gpu_count": count,
        "vram_per_gpu_gib": gpu["vram_gib"],
        "compute_capability": gpu.get("compute_capability"),
        "compute_capability_basis": gpu.get("compute_capability_basis") or "",
        "vendor": gpu.get("vendor") or "nvidia",
        "ecosystem": gpu.get("ecosystem") or "cuda",
        "fp8_supported": bool(gpu.get("fp8_supported")),
        "fp8_basis": gpu.get("fp8_basis") or "",
        "interconnect": gpu.get("interconnect") or "",
    }
    hw.update({key: value for key, value in overrides.items() if value not in (None, "")})
    return hw, None


def meta():
    rows, families = load_tables()
    return {
        "catalog": {
            "models_csv": rel(MODELS_CSV),
            "families_csv": rel(FAMILIES_CSV),
            "model_count": len(rows),
            "family_count": len(families),
        },
        "recipes_json": rel(RECIPES_JSON),
        "deployments_json": rel(DEPLOYMENTS_JSON),
        "hf_catalog_json": rel(HF_CATALOG_JSON),
        "doc_sources_json": rel(DOC_SOURCES_JSON),
        "gpus": gpu_snapshot_meta(),
        "workspace": str(WORKSPACE),
    }


def hf_summary():
    catalog = load_hf_catalog()
    docs = load_doc_sources()
    if not catalog:
        return {
            "available": False,
            "hint": "还没有抓取快照。运行 python deploy-portal/tools/sync_hf.py 生成 data/hf-catalog.json。",
        }
    counts = catalog.get("counts") or {}
    return {
        "available": True,
        "fetched_at": catalog.get("fetched_at"),
        "endpoint_used": catalog.get("endpoint_used"),
        "endpoint_kind": catalog.get("endpoint_kind"),
        "endpoint_note": catalog.get("endpoint_note"),
        "counts": counts,
        "errors": catalog.get("errors") or [],
        "per_org_limit": catalog.get("per_org_limit"),
        "organizations": catalog.get("organizations") or [],
        "tracked_repos": catalog.get("tracked_repos") or [],
        "docs": {
            "available": bool(docs),
            "fetched_at": (docs or {}).get("fetched_at"),
            "counts": (docs or {}).get("counts"),
            "errors": (docs or {}).get("errors") or [],
        },
    }


def hf_query(keyword="", organization="", task="", license_filter="", sort="downloads",
             limit=100, offset=0):
    catalog = load_hf_catalog() or {}
    models = list(catalog.get("index") or [])
    keyword = (keyword or "").strip().lower()
    if keyword:
        models = [item for item in models if keyword in (item.get("id") or "").lower()]
    if organization:
        models = [item for item in models if item.get("organization") == organization]
    if task:
        models = [item for item in models if item.get("pipeline_tag") == task]
    if license_filter:
        models = [item for item in models if (item.get("license") or "") == license_filter]

    sorters = {
        "downloads": lambda item: -(item.get("downloads") or 0),
        "last_modified": lambda item: item.get("last_modified") or "",
        "likes": lambda item: -(item.get("likes") or 0),
        "id": lambda item: item.get("id") or "",
    }
    reverse = sort in ("last_modified",)
    models.sort(key=sorters.get(sort, sorters["downloads"]), reverse=reverse)

    total = len(models)
    limit = max(1, min(int(limit or 100), 500))
    offset = max(0, int(offset or 0))
    page = models[offset:offset + limit]

    all_models = catalog.get("index") or []
    return {
        "models": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "grand_total": len(all_models),
        "facets": {
            "organizations": sorted({
                item.get("organization") for item in all_models if item.get("organization")
            }),
            "tasks": sorted({
                item.get("pipeline_tag") for item in all_models if item.get("pipeline_tag")
            }),
            "licenses": sorted({
                item.get("license") for item in all_models if item.get("license")
            }),
        },
    }


def hf_detail(repo):
    catalog = load_hf_catalog() or {}
    record = (catalog.get("details") or {}).get(repo)
    if not record:
        return None
    detail = dict(record)
    detail["verification"] = verification_for((record.get("profiles") or [None])[0]) if record.get("profiles") else None
    return detail


def doc_sources(profile_id=""):
    data = load_doc_sources() or {}
    records = list(data.get("sources") or [])
    if profile_id:
        records = [
            item for item in records
            if not (item.get("profiles") or []) or profile_id in (item.get("profiles") or [])
        ]
    return {
        "available": bool(data),
        "fetched_at": data.get("fetched_at"),
        "counts": data.get("counts"),
        "note": data.get("note"),
        "sources": records,
        "errors": data.get("errors") or [],
    }


def global_docs():
    """只对全局生效的来源(不绑定具体部署档)。

    没有 profile_id 的方案(如 GGUF 路径)用它拿到引擎级权威出处,而不是留空。
    """
    data = load_doc_sources() or {}
    return [
        item for item in (data.get("sources") or [])
        if not (item.get("profiles") or [])
    ]

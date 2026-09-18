#!/usr/bin/env python3
"""根据硬件 JSON 从 models.csv 中筛选并排序本地部署模型。仅使用 Python 标准库。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent

# 宽松许可按机器可读的 license_id 判定;展示名会随厂商措辞变化,不能用它判。
PERMISSIVE_LICENSE_IDS = {"mit", "apache-2.0", "bsd-3-clause", "cc-by-4.0"}


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def version_tuple(value):
    return tuple(int(x) for x in re.findall(r"\d+", str(value))[:4])


def version_gte(actual, required):
    a, r = version_tuple(actual), version_tuple(required)
    width = max(len(a), len(r))
    return a + (0,) * (width - len(a)) >= r + (0,) * (width - len(r))


def truthy(value):
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是"}


def is_cuda(hw):
    """是否 CUDA 生态。现场登记的 NVIDIA 机器没有 ecosystem 字段,按 cuda 处理。"""
    return str(hw.get("ecosystem") or "cuda").strip().lower() == "cuda"


def fp8_capability(hw):
    """这张卡能不能跑 FP8 权重。返回 True / False / None(无法判定)。

    优先用厂商页核实过的 fp8_supported。只有这个字段确实不存在时才退回推导,而且
    退回推导只对 CUDA 生态成立:昇腾没有 sm_xx,拿 sm_89 去推会把官方页写明支持
    HiF8/mxFP8 的 Atlas 350 判成「不支持 FP8」——这正是要避免的假结论。
    非 CUDA 生态又拿不到厂商页标称值时返回 None,由调用方如实说「无法判定」,
    不能悄悄当成不支持。
    """
    if hw.get("fp8_supported") not in (None, ""):
        return truthy(hw.get("fp8_supported"))
    if not is_cuda(hw):
        return None
    return number(hw.get("compute_capability")) >= 8.9


def fp8_failure_reason(hw, capability):
    """FP8 门槛未通过时,如实说明依据来自哪里,不替厂商页下结论。"""
    if capability is None:
        return ("此档是 FP8 权重,但所选卡的 FP8 能力无法判定:"
                "既没有厂商页标称值,该生态也不能由算力推导,需先核实再上")
    if is_cuda(hw):
        return "此档是 FP8 权重,需要 sm_89 及以上"
    return "此档是 FP8 权重,%s 的厂商页未标注 FP8/HiF8 支持" % (hw.get("gpu_name") or "所选卡")


def compute_label(hw):
    """算力标签。非 CUDA 生态没有 sm_xx,显示生态名而不是编一个 sm 号出来。"""
    if not is_cuda(hw):
        return "%s 生态" % str(hw.get("ecosystem") or "").strip().upper()
    cc = hw.get("compute_capability")
    if cc in (None, ""):
        return "算力未登记"
    return "sm_%s" % str(cc).replace(".", "")


def driver_label(hw):
    """驱动这一行的说法。昇腾不适用 NVIDIA 驱动下限,写「驱动 None」是误导。"""
    if not is_cuda(hw):
        return "驱动下限不适用(NVIDIA 驱动下限与昇腾无关)"
    return "驱动 %s" % (hw.get("driver_version") or "未填")


def load_catalog(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalize_name(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def quant_class(value):
    """把量化描述归到可比较的档位;只有同档位的 artifact 才适合放在一起比。"""
    lowered = str(value or "").lower()
    for name, keywords in (("int4", ("awq", "int4", "gptq", "w4a16")),
                           ("fp8", ("fp8", "w8a8")),
                           ("bf16", ("bf16", "bfloat16", "完整精度"))):
        if any(keyword in lowered for keyword in keywords):
            return name
    return lowered


def estimate_family_candidates(families, profiles, hw):
    """Return capacity-only discoveries for families without a precise deployment profile."""
    represented = {normalize_name(row["model_name"]) for row in profiles}
    gpu_count = int(number(hw.get("gpu_count")))
    per_gpu = number(hw.get("vram_per_gpu_gib"))
    total = gpu_count * per_gpu
    cc = number(hw.get("compute_capability"))
    fp8_capable = fp8_capability(hw)
    wanted = workload_set(hw.get("workload", ""))
    require_mm = truthy(hw.get("require_multimodal"))
    require_permissive = truthy(hw.get("require_permissive_license"))
    min_context = number(hw.get("min_context_k"))
    results = []
    for row in families:
        if normalize_name(row["model_name"]) in represented:
            continue
        params = number(row.get("total_params_b"))
        if not params or not total or not per_gpu:
            continue
        modalities = workload_set(row.get("modalities", ""))
        if require_mm and "image" not in modalities:
            continue
        if require_permissive and row.get("openness") != "open-source":
            continue
        if min_context and number(row.get("context_k")) < min_context:
            continue

        # GiB estimates include common tensor metadata but not runtime/KV cache.
        choices = [("BF16容量估算", params * 1.92)]
        if fp8_capable:
            choices.append(("FP8容量估算", params * 0.98))
        choices.append(("INT4/AWQ容量估算", params * 0.58))
        selected = None
        for quant, weight in choices:
            required = weight * 1.22 + 4
            if required <= total * 0.90:
                selected = (quant, weight, required)
                break
        if not selected:
            continue
        quant, weight, required = selected
        min_cards = max(1, math.ceil(required / (per_gpu * 0.90)))
        if min_cards > gpu_count:
            continue
        supported = workload_set(row.get("workloads", ""))
        overlap = len(wanted & supported)
        active = number(row.get("active_params_b"), params) or params
        score = overlap * 8 + min(30, math.log2(max(params, 1)) * 3) - min(12, math.log2(max(active, 1)))
        if row.get("vllm_status") == "supported":
            score += 5
        results.append(
            {
                "row": row,
                "quant": quant,
                "weight": round(weight),
                "required": round(required),
                "min_cards": min_cards,
                "score": round(score, 1),
            }
        )
    return sorted(results, key=lambda x: x["score"], reverse=True)


def workload_set(value):
    return {x.strip().lower() for x in re.split(r"[,;，；]", str(value)) if x.strip()}


def evaluate(row, hw, preference):
    """判断这个部署档在给定硬件上能不能跑,以及跑起来浪费多少显存。

    返回 (failures, warnings, score);完整的显存核算见 assess()。
    """
    result = assess(row, hw, preference)
    return result["failures"], result["warnings"], result["score"]


# --- 显存核算 -----------------------------------------------------------------
#
# 权重是实测值(artifact 的 safetensors 字节数),KV cache 由真实 config 的
# attention 结构算出,两者都不是估算。只有下面两个系数是工程余量,明确标注:
#
#   KV_DTYPE_BYTES  vLLM 默认 KV cache 精度 fp16/bf16 = 2 字节;开启 fp8 KV 可减半
#   RUNTIME_OVERHEAD CUDA graph / 激活 / workspace / 显存碎片的预留比例
#   PER_CARD_BUDGET  单卡可用比例,留出 KV 随实测增长的空间
KV_DTYPE_BYTES = 2.0
RUNTIME_OVERHEAD = 0.10
PER_CARD_BUDGET = 0.92

# 单实例的健康占用区间。低于 LOW_UTILIZATION 说明这个档配这些卡太奢侈
# (该换更大的档,或把卡拿去跑更多副本),高于 HIGH_UTILIZATION 说明没给长
# 上下文和并发留余量。这两个阈值同时用于告警和排序,避免两处说法不一致。
LOW_UTILIZATION = 0.45
HIGH_UTILIZATION = 0.90


def kv_gib(row, context_k, dtype_bytes=KV_DTYPE_BYTES):
    """按真实 attention 结构算 KV cache 显存;结构缺失时返回 None,不猜。"""
    elems = number(row.get("kv_elems_per_token_per_layer"))
    layers = number(row.get("attention_layers"))
    if not elems or not layers or not context_k:
        return None
    tokens = number(context_k) * 1024
    return elems * layers * tokens * dtype_bytes / (1024 ** 3)


def max_context_for(row, hw, dtype_bytes=KV_DTYPE_BYTES):
    """反算「就这些卡、这个档,上下文最多能开到多长」。

    kv_gib() 对上下文是**线性**的,所以同一条公式倒过来就能用:并行组的总可用显存
    扣掉运行时余量与实测权重之后,剩下的 GiB 全给 KV,能换多少 K。

    复用正向核算的同一批系数(PER_CARD_BUDGET / RUNTIME_OVERHEAD / dtype_bytes),
    否则正算与反算会用两套假设,页面自相矛盾。

    返回 dict:
      value     上限(K);算不出时 None
      note      为什么是这个值 / 为什么算不出
      memory_k  显存反算出来的上限;算不出时 None
      kv_budget_gib  扣掉权重与运行时余量后、真正能分给 KV 的显存;算不出时 None
      model_k   该档自身标称的上下文上限(能取到时)
      limit     真正的限制来自哪边:"memory" / "model" / ""
    """
    vram = number(hw.get("vram_per_gpu_gib"))
    tp = max(1, int(number(row.get("min_gpu_count"), 1)))
    weight = number(row.get("weight_gib"))
    model_k = number(row.get("context_k"))
    result = {"value": None, "note": "", "memory_k": None, "kv_budget_gib": None,
              "model_k": model_k or None, "limit": ""}

    def give_up(reason):
        result["note"] = reason
        return result

    if not is_cuda(hw):
        # 与 assess() 里 kv_gib 的处理同一个理由:昇腾的 KV 精度由
        # --quantization ascend 的专有量化决定,没有可核实的公开公式。
        # 拿 CUDA 的 2 字节口径反算会得出一个看着精确的错数,所以留空。
        return give_up("昇腾的 KV cache 精度由 --quantization ascend 的专有量化决定,"
                       "没有可核实的公开公式,无法反算上下文上限;这里只按权重下界核算")
    if not vram:
        return give_up("没有已核实的单卡显存,无法反算上下文上限")
    if not weight:
        return give_up("缺少实测权重,无法反算上下文上限")
    elems = number(row.get("kv_elems_per_token_per_layer"))
    layers = number(row.get("attention_layers"))
    if not elems or not layers:
        return give_up("attention 结构无法核实(config 取不到),无法反算上下文上限;"
                       "这里只按下界(权重)核算")

    # 并行组的可用显存 → 扣掉运行时余量与权重 → 剩下的全给 KV。
    budget_total = vram * PER_CARD_BUDGET * tp
    weight_and_kv = budget_total / (1 + RUNTIME_OVERHEAD)
    kv_budget = weight_and_kv - weight
    if kv_budget <= 0:
        return give_up("权重(%.0fGiB)已经占满 %d 张卡扣掉余量后的可用显存,"
                       "没有任何空间留给 KV cache" % (weight, tp))

    # 1K token 的 KV 显存 = elems × layers × 1024 × dtype_bytes
    kv_per_k_gib = elems * layers * 1024 * dtype_bytes / (1024 ** 3)
    memory_k = kv_budget / kv_per_k_gib
    result["memory_k"] = memory_k
    result["kv_budget_gib"] = kv_budget
    # 向下取整:反算值本来就是上界(未计 vLLM 的 KV block 粒度与显存碎片),
    # 再向上取整就成了「保证开得到」的承诺,而它不是。
    memory_limit = int(memory_k)

    basis = row.get("attention_basis") or (row.get("attention_kind") or "已核实的 attention 结构")
    if model_k and model_k <= memory_limit:
        result["value"] = int(model_k)
        result["limit"] = "model"
        origin = "官方模型卡标称" if (row.get("context_source") or "") == "card" else "仓库 config"
        result["note"] = ("显存侧可反算出约 %dK,但该档自身标称上下文 %sK(%s)更紧,取 %dK。"
                          "反算按 %d 张卡共 %.0fGiB 可用显存、扣掉 %.0f%% 运行时余量与"
                          "实测权重 %.0fGiB 后全给 KV;未计 vLLM 的 KV block 粒度与显存碎片,"
                          "实际可开只会更低。"
                          % (memory_limit, row.get("context_k"), origin, int(model_k),
                             tp, vram * PER_CARD_BUDGET * tp, RUNTIME_OVERHEAD * 100, weight))
    else:
        result["value"] = memory_limit
        result["limit"] = "memory"
        detail = ""
        if model_k:
            detail = "该档自身标称 %sK 更高,不是限制。" % model_k
        result["note"] = ("由显存反算:%d 张卡共 %.0fGiB 可用显存,扣掉 %.0f%% 运行时余量与"
                          "实测权重 %.0fGiB 后剩 %.0fGiB 给 KV,按 %s 算出约 %dK。%s"
                          "未计 vLLM 的 KV block 粒度与显存碎片,实际可开只会更低。"
                          % (tp, vram * PER_CARD_BUDGET * tp, RUNTIME_OVERHEAD * 100,
                             weight, kv_budget, basis, memory_limit, detail))
    return result


def assess(row, hw, preference):
    """按「选定的真实 GPU + 卡数」核算一个部署档能不能跑、跑起来浪费多少显存。

    fit 判定只看实测权重 + 算出的 KV + 明确标注的余量,不再用登记表里的
    显存门槛当权威;登记门槛只作为交叉核对,冲突时如实报出来。
    """
    gpu_count = max(1, int(number(hw.get("gpu_count"), 1)))
    vram = number(hw.get("vram_per_gpu_gib"))
    nodes = max(1, int(number(hw.get("nodes"), 1)))
    cc = number(hw.get("compute_capability"))
    cuda = is_cuda(hw)
    fp8_capable = fp8_capability(hw)
    wanted_context = number(hw.get("context_k")) or number(hw.get("min_context_k"))

    failures, warnings = [], []
    weight = number(row.get("weight_gib"))
    tp = max(1, int(number(row.get("min_gpu_count"), 1)))
    context_used = wanted_context or number(row.get("context_k"))
    kv = kv_gib(row, context_used)
    kv_note = ""
    if kv is not None and not cuda:
        # 昇腾走 --quantization ascend 的专有 KV 量化,没有可核实的公开公式,
        # 不能沿用 CUDA 栈的 2 字节口径。宁可留空,也不套一个错的公式。
        kv = None
        kv_note = ("昇腾的 KV cache 精度由 --quantization ascend 的专有量化决定,"
                   "没有可核实的公开公式;这里只按下界(权重)核算")
    kv_known = kv is not None
    if kv is None:
        # 结构没核实到(例如官方仓库 gated),只用权重做下界,并如实说明。
        kv = 0.0
        if not kv_note:
            kv_note = "官方仓库 gated,KV cache 结构无法核实;这里只按下界(权重)核算"
    needed = (weight + kv) * (1 + RUNTIME_OVERHEAD)

    # 反算这张卡在这个档上的上下文上限。与上面的正算用的是同一条 KV 公式和同一批
    # 系数,所以「填的上下文 = 反算上限」时正算正好卡在可用显存上。
    max_context = max_context_for(row, hw)
    max_k = max_context["value"]

    per_card = needed / tp if tp else needed
    engaged_vram = tp * vram
    utilization = (needed / engaged_vram) if engaged_vram else 0.0
    replicas = gpu_count // tp

    if not weight:
        failures.append("缺少实测权重,无法核算显存")
    if gpu_count < tp:
        failures.append("此档需要 %d 卡并行(TP=%d),当前 %d 卡" % (tp, tp, gpu_count))
    if per_card > vram * PER_CARD_BUDGET:
        failures.append("单卡需 %.0fGiB(权重+KV+余量),超过 %gGiB 卡的可用 %.0fGiB"
                        % (per_card, vram, vram * PER_CARD_BUDGET))
    if nodes > 1 and not truthy(row.get("multi_node")) and tp > gpu_count // nodes:
        failures.append("此档不能跨机拆分,单机最多 %d 卡放不下 TP=%d" % (gpu_count // nodes, tp))
    # 算力门槛是 sm_xx,只对 CUDA 生态成立。昇腾没有 sm 等级,拿 NVIDIA 的标度
    # 去卡它只会得出假结论,所以这条对非 CUDA 卡不适用。
    if cuda and cc and cc < number(row.get("min_compute_capability")):
        failures.append("算力需≥sm_%s,当前 sm_%s"
                        % (str(row.get("min_compute_capability")).replace(".", ""),
                           str(cc).replace(".", "")))
    if truthy(row.get("fp8_required")) and not fp8_capable:
        failures.append(fp8_failure_reason(hw, fp8_capable))
    # NVIDIA 驱动下限同样只对 CUDA 栈成立;昇腾要核的是 CANN 版本,登记表里没有这一列。
    if cuda and hw.get("driver_version") and row.get("min_driver") and not version_gte(
            hw["driver_version"], row["min_driver"]):
        failures.append("驱动需≥%s,当前%s" % (row["min_driver"], hw["driver_version"]))
    elif cuda and row.get("min_driver") and not hw.get("driver_version"):
        # 没填驱动时不能默认满足:此档有明确驱动下限,必须让用户上线前自己核对,
        # 否则浏览器里选一台 A100 会默认把「要求驱动≥575」的档判成可行。
        warnings.append("此档要求驱动≥%s,当前未填驱动,上线前必须先核对" % row["min_driver"])
    if number(hw.get("host_ram_gib")) and number(hw["host_ram_gib"]) < number(row.get("min_host_ram_gib")):
        failures.append("主存需≥%sGiB,当前%gGiB"
                        % (row.get("min_host_ram_gib"), number(hw["host_ram_gib"])))
    if number(hw.get("disk_free_gib")) and number(hw["disk_free_gib"]) < number(row.get("min_disk_gib")):
        failures.append("可用磁盘需≥%sGiB,当前%gGiB"
                        % (row.get("min_disk_gib"), number(hw.get("disk_free_gib"))))
    if wanted_context and number(row.get("context_k")) < wanted_context:
        failures.append("此档上下文 %sK 低于需求 %gK" % (row.get("context_k"), wanted_context))
    # 需求上下文超过**显存反算出来的**KV 上限时要单独说一句。原先这种情况只落到
    # 「单卡需 X GiB…超过可用 Z GiB」,与「权重本身就装不下」共用同一句,读者分不清
    # 该换卡还是该把上下文调短——这两件事的处置完全不同。
    #
    # 判据是 memory_k 而不是 max_k:max_k 可能被「该档自身标称上下文」压住(limit=model),
    # 那时 max_k < memory_k,拿 max_k 作判据会把「其实显存够、是模型开不了那么长」
    # 说成「KV 超了」——一句看着精确的错话。
    memory_k = max_context["memory_k"]
    if wanted_context and memory_k is not None and wanted_context > memory_k:
        kv_wanted = kv_gib(row, wanted_context) or 0.0
        failures.append("需求上下文 %gK 超出这张卡在此档的 KV 上限 %dK:"
                        "该上下文要 %.0fGiB 的 KV cache,而扣除权重 %.0fGiB 与 %.0f%% 运行时余量后"
                        "只剩 %.0fGiB 给 KV(这是 KV 超了,不是权重放不下)"
                        % (wanted_context, int(memory_k), kv_wanted, weight,
                           RUNTIME_OVERHEAD * 100, max(0.0, max_context["kv_budget_gib"] or 0.0)))
    if truthy(hw.get("require_multimodal")) and not truthy(row.get("multimodal")):
        failures.append("需求为多模态,但此档标记为纯文本")
    if truthy(hw.get("require_permissive_license")) and row.get("license_id") not in PERMISSIVE_LICENSE_IDS:
        failures.append("需要宽松许可,但此档许可是 %s" % (row.get("license") or "未标注"))

    # 交叉核对:登记门槛与实测核算不一致时必须说出来,不能悄悄用其中一个。
    declared_per_card = number(row.get("min_vram_per_gpu_gib"))
    if declared_per_card and per_card > declared_per_card:
        warnings.append("实测核算单卡 %.0fGiB 高于登记门槛 %gGiB,以实测为准"
                        % (per_card, declared_per_card))
    declared_total = number(row.get("min_total_vram_gib"))
    if declared_total and needed > declared_total * 1.05:
        warnings.append("实测核算需 %.0fGiB 高于登记的 %gGiB,以实测为准"
                        % (needed, declared_total))
    if not kv_known:
        warnings.append(kv_note)
    if utilization > HIGH_UTILIZATION:
        warnings.append("显存占用 %.0f%% 偏高,长上下文或多并发时余量不足" % (utilization * 100))
    elif utilization < LOW_UTILIZATION:
        warnings.append("单副本只用到 %.0f%% 显存,这个档配这些卡偏小" % (utilization * 100))
    # 灵衢是华为的高速卡间互联(对标 NVLink),HCCS 同理;两者都算已确认的高速互联。
    if tp >= 4 and not any(x in str(hw.get("interconnect", "")).lower()
                           for x in ("nvlink", "nvswitch", "灵衢", "hccs")):
        warnings.append("大 TP 但未确认高速卡间互联(NVLink/NVSwitch 或灵衢/HCCS),PCIe 拓扑需压测")
    if replicas > 1:
        warnings.append("当前卡数可放 %d 个副本,按单副本核算显存" % replicas)

    score = _score(row, hw, preference, utilization, replicas)
    return {
        "failures": failures,
        "warnings": warnings,
        "score": round(score, 1),
        "memory": {
            "weight_gib": round(weight, 1),
            "kv_gib": round(kv, 1) if kv_known else None,
            "kv_context_k": context_used,
            "kv_basis": row.get("attention_basis") or "",
            "attention_kind": row.get("attention_kind") or "",
            "runtime_overhead_ratio": RUNTIME_OVERHEAD,
            "needed_gib": round(needed, 1),
            "per_card_gib": round(per_card, 1),
            "tp": tp,
            "cards": gpu_count,
            "engaged_vram_gib": round(engaged_vram, 1),
            "utilization": round(utilization, 3),
            "waste_gib": round(max(0.0, engaged_vram - needed), 1),
            "replicas": replicas,
            "kv_verified": kv_known,
            "kv_note": kv_note,
            # 反算的上下文上限。算不出时 value 必须是 None + note 说明原因,不许编一个数。
            "max_context_k": max_k,
            "max_context_note": max_context["note"],
            "max_context_memory_k": (round(max_context["memory_k"], 1)
                                     if max_context["memory_k"] is not None else None),
            "max_context_model_k": max_context["model_k"],
            "max_context_limit": max_context["limit"],
        },
    }


def _score(row, hw, preference, utilization, replicas):
    quality = number(row.get("quality_score"))
    throughput = number(row.get("throughput_score"))
    if preference == "quality":
        score = quality * 0.76 + throughput * 0.14
    elif preference == "throughput":
        score = quality * 0.42 + throughput * 0.48
    else:
        score = quality * 0.60 + throughput * 0.30

    wanted = workload_set(hw.get("workload", ""))
    supported = workload_set(row.get("workloads", ""))
    score += min(9, 3 * len(wanted & supported))
    if wanted and not (wanted & supported):
        score -= 8

    # 「不浪费显存」:占用太低说明这个档配这些卡太奢侈,占用过高说明没有余量。
    # 阈值与 assess() 的告警共用,扣分要重到能把「26% 占用的小档」压到
    # 「76% 占用的大档」之后,否则推荐结果仍然会浪费显存。
    if utilization < LOW_UTILIZATION:
        score -= min(20.0, (LOW_UTILIZATION - utilization) * 70)
    elif utilization > HIGH_UTILIZATION:
        score -= min(10.0, (utilization - HIGH_UTILIZATION) * 60)

    # 有可执行部署方法是真的加分项;是否在本机验证过不参与排序,
    # 否则推荐会天然偏向本地方案。
    if truthy(row.get("has_recipe")):
        score += 3
    return score



def print_report(hw, compatible, rejected, estimates, top):
    print("# 本地开源模型硬件匹配报告\n")
    print(
        f"硬件：{hw.get('gpu_count')}× {hw.get('gpu_name')} "
        f"({hw.get('vram_per_gpu_gib')}GiB/卡，总计约"
        f"{number(hw.get('gpu_count')) * number(hw.get('vram_per_gpu_gib')):g}GiB)，"
        f"{compute_label(hw)}，{driver_label(hw)}，"
        f"按 {hw.get('context_k') or hw.get('min_context_k')}K 上下文核算。\n"
    )
    if compatible:
        print("## 推荐结果\n")
        print("| 排名 | 模型 / 部署档 | 量化 | 布局 | 实测权重GiB | KV GiB | 合计GiB | 单卡GiB | 占用率 | 得分 | 风险提示 |")
        print("|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|")
        for rank, item in enumerate(compatible[:top], 1):
            row, warnings, score = item
            memory = row.get("memory") or {}
            warning = "；".join(warnings) if warnings else "硬约束全部满足，仍需业务压测"
            kv = memory.get("kv_gib")
            print(
                f"| {rank} | {row['model_name']} · {row['profile']} | {row['quantization']} | "
                f"{row['recommended_layout']} | {memory.get('weight_gib')} | "
                f"{'无法核实' if kv is None else kv} | {memory.get('needed_gib')} | "
                f"{memory.get('per_card_gib')} | {round((memory.get('utilization') or 0) * 100)}% | "
                f"{score:.1f} | {warning} |"
            )
        print()
        winner = compatible[0][0]
        winner_memory = winner.get("memory") or {}
        print(
            f"首选：**{winner['model_name']}（{winner['profile']}）**。"
            f"实测权重 {winner_memory.get('weight_gib')}GiB + KV {winner_memory.get('kv_gib')}GiB "
            f"→ 单卡需 {winner_memory.get('per_card_gib')}GiB，占卡内显存 "
            f"{round((winner_memory.get('utilization') or 0) * 100)}%；"
            f"建议先按 `{winner['recommended_layout']}` 冒烟，"
            "再用启动日志里的 KV cache 容量校准并发。\n"
        )
    else:
        print("## 推荐结果\n\n没有模型档通过全部硬约束。请看最接近的候选及缺口。\n")
    if rejected:
        print("## 最接近但不满足的候选\n")
        print("| 模型 / 部署档 | 主要缺口 |")
        print("|---|---|")
        for row, failures, score in rejected[:5]:
            print(f"| {row['model_name']} · {row['profile']} | {'；'.join(failures)} |")
        print()
    if estimates:
        print("## 尚未建立精确部署档、但容量可能匹配的模型\n")
        print("| 模型 | 估算量化 | 估算权重 | 估算最低卡数 | 许可证/开放性 | vLLM状态 |")
        print("|---|---|---:|---:|---|---|")
        for item in estimates[:top]:
            row = item["row"]
            print(
                f"| {row['model_name']} | {item['quant']} | ~{item['weight']}GiB | "
                f"~{item['min_cards']}卡 | {row['license']} / {row['openness']} | {row['vllm_status']} |"
            )
        print(
            "\n这些只是按参数量估算的发现项，**不会覆盖上面的精确部署推荐**。"
            "具体量化权重是否存在、视觉编码器额外显存、特殊内核、驱动/CUDA/vLLM版本和输出质量都还要验证。\n"
        )
    print("> 结果是部署预筛选，不替代实机验收。模型revision、量化仓库、镜像ID/SHA256、tool/reasoning parser、输出质量和压力测试通过后才可上线。")


def main():
    parser = argparse.ArgumentParser(description="根据硬件JSON推荐本地开源模型")
    parser.add_argument("hardware", type=Path, help="硬件JSON，例如 hardware.example.json")
    parser.add_argument("--catalog", type=Path, default=ROOT / "models.csv")
    parser.add_argument("--families", type=Path, default=ROOT / "model-families.csv")
    parser.add_argument("--preference", choices=("balanced", "quality", "throughput"), default="balanced")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--no-estimates", action="store_true", help="不显示尚未建立精确部署档的容量估算候选")
    args = parser.parse_args()

    with args.hardware.open("r", encoding="utf-8-sig") as f:
        hw = json.load(f)
    rows = load_catalog(args.catalog)
    families = load_catalog(args.families) if args.families.exists() else []
    compatible, rejected = [], []
    compatible, rejected = [], []
    for row in rows:
        result = assess(row, hw, args.preference)
        # 显存核算结果挂在行上,报告里直接读,避免再算一遍算错。
        row = dict(row)
        row["memory"] = result["memory"]
        if result["failures"]:
            rejected.append((row, result["failures"], result["score"]))
        else:
            compatible.append((row, result["warnings"], result["score"]))
    compatible.sort(key=lambda x: (x[2], number(x[0]["quality_score"])), reverse=True)
    rejected.sort(key=lambda x: (len(x[1]), -x[2]))
    estimates = [] if args.no_estimates else estimate_family_candidates(families, rows, hw)
    print_report(hw, compatible, rejected, estimates, max(1, args.top))
    return 0 if compatible else 2


if __name__ == "__main__":
    sys.exit(main())

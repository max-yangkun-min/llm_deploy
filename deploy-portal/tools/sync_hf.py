#!/usr/bin/env python3
"""从 HF 兼容 API 抓取真实模型元数据,生成带出处的快照。

设计要点(都是实测踩出来的):
  * 必须带 User-Agent,默认 Python-urllib 的 UA 会被镜像返回 403。
  * 分页 Link 头会指回 huggingface.co,必须把主机名重写回当前端点,否则超时。
  * 端点按 sources.json 顺序尝试:先国内镜像,全部失败才回退官方上游。
  * 抓取失败会写进快照的 errors,不会静默丢弃。

用法:
    python deploy-portal/tools/sync_hf.py
    python deploy-portal/tools/sync_hf.py --orgs-only
    python deploy-portal/tools/sync_hf.py --repos-only
    python deploy-portal/tools/sync_hf.py --per-org-limit 300
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PORTAL_DIR = Path(__file__).resolve().parent.parent
SOURCES = PORTAL_DIR / "data" / "sources.json"
OUT = PORTAL_DIR / "data" / "hf-catalog.json"

USER_AGENT = "Mozilla/5.0 (compatible; deploy-portal/0.1; local-model-catalog)"

# 列表接口的 expand 是一份「白名单」:不在其中的字段一律不返回,而且连 tags /
# pipeline_tag / likes 这类 HF 官方默认会带的字段也拿不到。实测漏掉它们的后果是
# 站点上「任务类型」筛选、「点赞数」排序和许可证显示全部退化成空值。
# 实测覆盖率:sha 100%、safetensors 约 85%、license 约 97%(tags 补齐后更高)。
EXPAND_FIELDS = (
    "sha", "safetensors", "lastModified", "cardData", "gated",
    "pipeline_tag", "library_name", "tags", "likes",
)

# cardData 会把整张模型卡塞进列表响应。实测 nvidia 按下载量排序时,即使缩到最小页大小
# 也会在同一个字节位置被镜像截断,去掉 cardData 才能取全;许可证仍可从 tags 的
# license: 前缀取到,所以精简模式必须保留 tags。
LEAN_EXPAND_FIELDS = tuple(name for name in EXPAND_FIELDS if name != "cardData")


def expand_query(fields):
    return "".join("&expand[]=%s" % name for name in fields)


EXPAND_QUERY = expand_query(EXPAND_FIELDS)
LEAN_EXPAND_QUERY = expand_query(LEAN_EXPAND_FIELDS)

# 这些 tag 对部署判断没有价值,丢掉可以让快照小很多。
TAG_NOISE = {
    "region:us", "endpoints_compatible", "text-generation-inference",
    "autotrain_compatible", "custom_code", "arxiv:2309.00071",
}


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class TruncatedPayload(RuntimeError):
    """镜像对大响应会在约 360KB 处截断,表现为 JSON 解析失败而不是 HTTP 错误。

    这种情况重试同一请求只会拿到同样被截断的结果,必须改用更小的 limit 重新分页。
    """


class Fetcher:
    def __init__(self, endpoints, timeout=30, retries=3, sleep=1.5, verbose=True,
                 truncation_budget=4, rate_limit_sleep=20.0):
        self.endpoints = [item["base"].rstrip("/") for item in endpoints]
        self.endpoint_meta = {item["base"].rstrip("/"): item for item in endpoints}
        self.timeout = timeout
        self.retries = retries
        self.sleep = sleep
        self.verbose = verbose
        # 实测镜像会偶发返回不完整 body(35KB 就被切断,与响应大小无关),这种是瞬时的,
        # 重试往往能拿到完整响应;预算用尽才说明是真的超大响应截断。
        self.truncation_budget = truncation_budget
        self.rate_limit_sleep = rate_limit_sleep
        self.used = None

    def _open(self, url, base):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            raw = response.read()
            try:
                return response.headers.get("Link"), json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as error:
                raise TruncatedPayload(
                    "响应被截断(%d 字节): %s" % (len(raw), error)
                )

    def get_json(self, path, raw_url=None):
        """取 JSON。raw_url 用于已经带完整地址的分页链接。"""
        last_error = None
        truncations = 0
        for base in self.endpoints:
            url = raw_url or (base + path)
            for attempt in range(1, self.retries + 1):
                try:
                    link, data = self._open(url, base)
                    self.used = base
                    return data, link, base
                except TruncatedPayload as error:
                    truncations += 1
                    last_error = "响应截断(%s)" % error
                    if truncations >= self.truncation_budget:
                        # 重试也拿不完整,只能交给调用方换更小的 limit 重新分页。
                        raise
                except urllib.error.HTTPError as error:
                    last_error = "HTTP %s %s" % (error.code, error.reason)
                    if error.code == 429:
                        # 镜像会限速。实测按 1.5s 的常规退避重试仍然全被拒,必须等更久。
                        time.sleep(self.rate_limit_sleep * attempt)
                        continue
                    if error.code in (400, 401, 403, 404):
                        # 403 多半是 UA 或端点拒绝;400/404 是路径问题,重试无意义。
                        break
                except Exception as error:  # noqa: BLE001  网络异常统一重试
                    last_error = "%s: %s" % (type(error).__name__, error)
                if attempt < self.retries:
                    time.sleep(self.sleep * attempt)
        raise RuntimeError("所有端点都失败 (%s): %s" % (last_error, raw_url or path))

    def get_raw(self, path):
        """取原始文本(如 config.json)。404 直接返回 None,由调用方判定是否算错误。"""
        last_error = None
        for base in self.endpoints:
            for attempt in range(1, self.retries + 1):
                try:
                    request = urllib.request.Request(base + path, headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(request, timeout=self.timeout) as response:
                        self.used = base
                        return response.read().decode("utf-8")
                except urllib.error.HTTPError as error:
                    if error.code == 404:
                        return None
                    last_error = "HTTP %s %s" % (error.code, error.reason)
                    if error.code == 429:
                        time.sleep(self.rate_limit_sleep * attempt)
                        continue
                    if error.code in (400, 401, 403):
                        break
                except Exception as error:  # noqa: BLE001  冷启动超时在镜像上很常见,必须重试
                    last_error = "%s: %s" % (type(error).__name__, error)
                if attempt < self.retries:
                    time.sleep(self.sleep * attempt)
        raise RuntimeError("取原始文件失败 (%s): %s" % (last_error, path))


def rewrite_host(link, base):
    """把分页 Link 里的官方域名换回当前端点,否则会打到超时的海外站。"""
    if not link:
        return None
    start = link.find("<")
    end = link.find(">")
    if start == -1 or end == -1:
        return None
    url = link[start + 1:end]
    parsed = urllib.parse.urlsplit(url)
    target = urllib.parse.urlsplit(base)
    return urllib.parse.urlunsplit((target.scheme, target.netloc, parsed.path, parsed.query, parsed.fragment))


def compact_tags(tags):
    keep = [tag for tag in (tags or []) if tag not in TAG_NOISE]
    return keep[:24]


def license_from(card_data, tags):
    value = (card_data or {}).get("license")
    if value:
        return value if isinstance(value, str) else "/".join(value)
    for tag in tags or []:
        if tag.startswith("license:"):
            return tag.split(":", 1)[1]
    return None


def compact_quant(config):
    """压缩 quantization_config。

    原始值里的 ignore 列表可能列上百个张量名(实测单个 GLM-5.2 AWQ 就有几万字符),
    直接存进快照会让文件膨胀几十倍。这里只保留判断部署所需的字段。
    """
    if not config:
        return None
    keys = ("quant_method", "format", "activation_scheme", "fmt", "weight_block_size",
            "bits", "group_size", "quantization_status", "version")
    out = {key: config[key] for key in keys if key in config}
    groups = config.get("config_groups") or {}
    for group in groups.values():
        weights = (group or {}).get("weights") or {}
        if weights:
            out["weights"] = {
                key: weights[key] for key in ("num_bits", "group_size", "type", "strategy", "symmetric")
                if key in weights
            }
            break
    ignored = config.get("ignore")
    if isinstance(ignored, list):
        out["ignored_tensor_count"] = len(ignored)
    return out


def attention_shape(config, shape_config):
    """推导「每层每 token 的 KV cache 元素数」及其依据,供显存计算使用。

    不同架构的 KV 口径差异极大,用同一个公式会把 MLA 算大到二十多倍:

    - MLA(DeepSeek 系 / GLM-5.2 / Kimi-K2.6):KV 只缓存压缩后的潜在向量,
      即 kv_lora_rank + qk_rope_head_dim,且各头共享,不乘 2;
    - 混合线性注意力(Qwen3.5 系):layer_types 里只有 full_attention 层随上下文增长;
    - 常规 GQA/MHA:2(K+V) x num_key_value_heads x head_dim。
    """
    layers = shape_config.get("num_hidden_layers")
    kv_lora = shape_config.get("kv_lora_rank")
    if kv_lora and layers:
        rope = shape_config.get("qk_rope_head_dim") or 0
        return {
            "kind": "mla",
            "layers": layers,
            "elements_per_token_per_layer": int(kv_lora) + int(rope),
            "basis": "MLA:kv_lora_rank %s + qk_rope_head_dim %s,各头共享不乘 2" % (kv_lora, rope),
        }

    layer_types = shape_config.get("layer_types") or config.get("layer_types") or []
    if not isinstance(layer_types, list):
        layer_types = []
    full = [item for item in layer_types if item == "full_attention"]
    heads = shape_config.get("num_key_value_heads") or shape_config.get("num_attention_heads")
    head_dim = shape_config.get("head_dim")
    attention_heads = shape_config.get("num_attention_heads")
    if not head_dim and shape_config.get("hidden_size") and attention_heads:
        head_dim = int(shape_config["hidden_size"]) // int(attention_heads)
    if full and heads and head_dim:
        return {
            "kind": "hybrid-linear",
            "layers": len(full),
            "total_layers": layers,
            "elements_per_token_per_layer": 2 * int(heads) * int(head_dim),
            "basis": ("混合线性注意力:%s 层里只有 %d 层是 full_attention,"
                      "其余线性层的状态不随上下文增长" % (layers, len(full))),
        }
    if heads and head_dim and layers:
        return {
            "kind": "gqa",
            "layers": layers,
            "elements_per_token_per_layer": 2 * int(heads) * int(head_dim),
            "basis": "GQA/MHA:2 x %s 个 KV 头 x %s 维,共 %s 层" % (heads, head_dim, layers),
        }
    return {"kind": "unknown", "basis": "config 里缺少 attention 结构字段,无法计算"}


def group_gguf(files):
    """GGUF 仓库通常放几十种量化档,按目录聚合才看得懂哪个档多大。"""
    buckets = {}
    for item in files:
        path = item.get("path") or ""
        folder = path.rsplit("/", 1)[0] if "/" in path else "(root)"
        bucket = buckets.setdefault(folder, {"files": 0, "bytes": 0})
        bucket["files"] += 1
        bucket["bytes"] += item.get("size") or 0
    return [
        {"dir": folder, "files": data["files"], "gib": round(data["bytes"] / (1024 ** 3), 2)}
        for folder, data in sorted(buckets.items(), key=lambda pair: -pair[1]["bytes"])
    ]


def index_record(model):
    params = (model.get("safetensors") or {}).get("total")
    return {
        "id": model.get("id"),
        "sha": model.get("sha"),
        "downloads": model.get("downloads"),
        "likes": model.get("likes"),
        "last_modified": model.get("lastModified"),
        "pipeline_tag": model.get("pipeline_tag"),
        "library_name": model.get("library_name"),
        "license": license_from(model.get("cardData"), model.get("tags")),
        "gated": model.get("gated"),
        "private": model.get("private"),
        "total_params": params,
        "total_params_b": round(params / 1e9, 2) if params else None,
        "tags": compact_tags(model.get("tags")),
    }


MIN_PAGE_LIMIT = 25


def sync_org(fetcher, org, per_org_limit, errors, max_pages=24):
    """每个组织抓两遍(热门 + 最新),合并去重,尽量不漏新模型。

    镜像会在约 360KB 处截断响应,所以 limit 要自适应:命中截断就把页大小减半,
    再靠游标翻页把剩下的取回来。
    """
    collected = {}

    def page_url(size, order, variant="full"):
        query = EXPAND_QUERY if variant == "full" else LEAN_EXPAND_QUERY
        return "/api/models?author=%s&limit=%d&sort=%s&direction=-1" % (
            urllib.parse.quote(org), size, order,
        ) + query

    for sort in ("downloads", "lastModified"):
        limit = max(MIN_PAGE_LIMIT, min(per_org_limit, 200))
        variant = "full"
        template = page_url(limit, sort, variant)

        link, base, pages = None, None, 0
        while True:
            try:
                if link:
                    data, link, base = fetcher.get_json(None, raw_url=link)
                else:
                    data, link, base = fetcher.get_json(template)
            except TruncatedPayload as error:
                if limit // 2 >= MIN_PAGE_LIMIT:
                    limit //= 2
                elif variant == "full":
                    # 缩到最小页还是被截断,说明瓶颈是单条记录的 cardData 体积,不是分页。
                    # 去掉 cardData 重来一遍;许可证仍可从 tags 的 license: 前缀取到。
                    variant = "lean"
                    limit = max(MIN_PAGE_LIMIT, min(per_org_limit, 200))
                else:
                    errors.append({"scope": "org:" + org, "sort": sort,
                                   "error": "响应持续截断(已去掉 cardData 字段): %s"
                                            % str(error)[:160]})
                    break
                template = page_url(limit, sort, variant)
                link = None
                continue
            except Exception as error:  # noqa: BLE001
                # 首屏就超时基本是「这一页太大」而不是组织不存在,减半重来比直接放弃更有价值。
                if pages == 0 and limit // 2 >= MIN_PAGE_LIMIT:
                    limit //= 2
                    template = page_url(limit, sort, variant)
                    link = None
                    continue
                errors.append({"scope": "org:" + org, "sort": sort,
                               "page": pages + 1, "error": str(error)[:200]})
                break

            for model in data:
                record = index_record(model)
                previous = collected.get(record["id"])
                if previous and not record.get("license") and previous.get("license"):
                    # 精简模式拿不到 cardData,不能把已经取到的许可证覆盖成空。
                    record["license"] = previous["license"]
                collected[record["id"]] = record
            pages += 1
            if not link or pages >= max_pages:
                break
            link = rewrite_host(link, base)
            if not link:
                break
    return list(collected.values())


def sync_repo(fetcher, entry, errors):
    """重点仓库:拿完整元数据 + config.json + 文件树。"""
    repo = entry["repo"]
    record = {
        "repo": repo,
        "profiles": entry.get("profiles", []),
        "role": entry.get("role", ""),
        "quant": entry.get("quant", ""),
        "source_url": None,
    }
    try:
        info, _, base = fetcher.get_json("/api/models/" + repo)
        record["source_url"] = base + "/" + repo
        record["revision"] = info.get("sha")
        record["last_modified"] = info.get("lastModified")
        record["downloads"] = info.get("downloads")
        record["likes"] = info.get("likes")
        record["pipeline_tag"] = info.get("pipeline_tag")
        record["library_name"] = info.get("library_name")
        record["tags"] = compact_tags(info.get("tags"))
        record["license"] = license_from(info.get("cardData"), info.get("tags"))
        record["gated"] = info.get("gated")
        safetensors = info.get("safetensors") or {}
        dtypes = safetensors.get("parameters") or {}
        record["total_params"] = safetensors.get("total")
        record["params_by_dtype"] = dtypes
        if record.get("total_params"):
            record["total_params_b"] = round(record["total_params"] / 1e9, 2)
        config = info.get("config") or {}
        record["architectures"] = config.get("architectures")
        record["model_type"] = config.get("model_type")
        info_config = config
    except Exception as error:  # noqa: BLE001
        errors.append({"scope": "repo:" + repo, "stage": "info", "error": str(error)[:200]})
        return record

    config = None
    try:
        raw = fetcher.get_raw("/%s/raw/main/config.json" % repo)
        if raw is not None:
            config = json.loads(raw)
    except Exception as error:  # noqa: BLE001
        errors.append({"scope": "repo:" + repo, "stage": "config",
                       "error": "config.json 直取失败,已改用 info 接口的 config 兜底: %s"
                                % str(error)[:160]})

    if not config:
        # 镜像的 /raw/ 路径会偶发整段超时(重试也救不回来)。但 info 接口返回的就是同一份
        # config.json,直接兜底;否则该仓库会被 --repair 永远判成「记录不完整」反复重抓。
        config = info_config or None

    if not config:
        # GGUF 仓库普遍没有 transformers config.json,这不算错误。
        record["config_missing"] = True
    else:
        record["config_missing"] = False
        # 多模态 / MoE 仓库把语言模型参数放在 text_config 里,顶层既没有层数也没有 KV 头数。
        # 不解析这一层就会把「拿不到」误当成「没有」,显存就算不准。
        shape_config = config
        for nested_key in ("text_config", "llm_config", "language_config", "decoder_config"):
            nested = config.get(nested_key)
            if isinstance(nested, dict) and nested.get("num_hidden_layers"):
                shape_config = nested
                record["shape_config_key"] = nested_key
                break
        max_positions = shape_config.get("max_position_embeddings") or config.get("max_position_embeddings")
        record["max_position_embeddings"] = max_positions
        record["context_k"] = round(max_positions / 1024, 1) if max_positions else None
        record["num_hidden_layers"] = shape_config.get("num_hidden_layers")
        record["hidden_size"] = shape_config.get("hidden_size")
        record["num_experts"] = (shape_config.get("num_experts")
                                or shape_config.get("num_local_experts")
                                or shape_config.get("n_routed_experts")
                                or shape_config.get("moe_num_experts"))
        record["num_experts_per_tok"] = (shape_config.get("num_experts_per_tok")
                                        or shape_config.get("num_experts_per_token")
                                        or shape_config.get("moe_top_k"))
        # KV cache 才是长上下文真正吃掉显存的部分,按真实 config 记录,
        # 不做「按参数量估」这种无法复核的推算。
        heads = shape_config.get("num_attention_heads")
        record["num_attention_heads"] = heads
        record["num_key_value_heads"] = shape_config.get("num_key_value_heads") or heads
        declared_head_dim = shape_config.get("head_dim")
        if not declared_head_dim and shape_config.get("hidden_size") and heads:
            # config 没写 head_dim 时按 hidden_size/heads 推导,并标明是推导值。
            declared_head_dim = int(shape_config["hidden_size"]) // int(heads)
            record["head_dim_derived"] = True
        else:
            record["head_dim_derived"] = False
        record["head_dim"] = declared_head_dim
        record["vocab_size"] = shape_config.get("vocab_size") or config.get("vocab_size")
        record["torch_dtype"] = shape_config.get("torch_dtype") or config.get("torch_dtype")
        record["quantization_config"] = compact_quant(config.get("quantization_config"))
        record["rope_scaling"] = shape_config.get("rope_scaling") or config.get("rope_scaling")
        record["kv_lora_rank"] = shape_config.get("kv_lora_rank")
        record["qk_rope_head_dim"] = shape_config.get("qk_rope_head_dim")
        layer_types = shape_config.get("layer_types") or config.get("layer_types") or []
        if isinstance(layer_types, list) and layer_types:
            record["full_attention_layers"] = sum(1 for item in layer_types if item == "full_attention")
            record["linear_attention_layers"] = sum(1 for item in layer_types if item == "linear_attention")
        record["attention_shape"] = attention_shape(config, shape_config)

    try:
        tree, _, _ = fetcher.get_json("/api/models/%s/tree/main?recursive=true" % repo)
        files = [item for item in tree if item.get("type") == "file"]
        weights = [item for item in files if (item.get("path") or "").endswith(".safetensors")]
        gguf = [item for item in files if (item.get("path") or "").endswith(".gguf")]
        record["file_count"] = len(files)
        record["weight_bytes"] = sum(item.get("size") or 0 for item in weights)
        record["gguf_bytes"] = sum(item.get("size") or 0 for item in gguf)
        record["weight_gib"] = round(record["weight_bytes"] / (1024 ** 3), 1) if record["weight_bytes"] else None
        record["gguf_gib"] = round(record["gguf_bytes"] / (1024 ** 3), 1) if record["gguf_bytes"] else None
        record["weight_shards"] = len(weights)
        record["has_gguf"] = bool(gguf)
        record["weight_files"] = [item.get("path") for item in weights][:40]
        record["gguf_dirs"] = group_gguf(gguf)
        record["gguf_file_count"] = len(gguf)
    except Exception as error:  # noqa: BLE001
        errors.append({"scope": "repo:" + repo, "stage": "tree", "error": str(error)[:200]})

    return record


def repo_incomplete(record):
    """重点仓库记录缺关键字段才值得重抓,避免无谓的整轮网络开销。"""
    if not record.get("revision"):
        return True                                   # info 那一步就没成功
    if record.get("weight_bytes") is None and record.get("gguf_bytes") is None:
        return True                                   # 文件树没拿到
    if "config_missing" not in record:
        return True                                   # config.json 那一步没跑完
    if not record.get("config_missing") and record.get("num_hidden_layers") is None:
        # config 拿到了但模型形状没解出来:多模态嵌套 config 没识别,或旧记录缺 KV 字段。
        return True
    if not record.get("config_missing") and "attention_shape" not in record:
        # 显存计算要用的 KV 结构还没记录,值得重抓一次。
        return True
    return False


def repair_plan(sources, previous):
    """挑出真正需要补抓的目标:上一轮失败过的组织 + 记录不完整的重点仓库。"""
    scopes = [str(item.get("scope", "")) for item in (previous.get("errors") or [])]
    failed_orgs = {scope.split(":", 1)[1] for scope in scopes if scope.startswith("org:")}
    failed_repos = {scope.split(":", 1)[1] for scope in scopes if scope.startswith("repo:")}
    orgs = [org for org in sources["organizations"] if org["id"] in failed_orgs]
    details = previous.get("details") or {}
    repos = [
        entry for entry in sources["tracked_repos"]
        if entry["repo"] in failed_repos or repo_incomplete(details.get(entry["repo"]) or {})
    ]
    return orgs, repos


def main(argv=None):
    parser = argparse.ArgumentParser(description="抓取 HF 真实模型元数据")
    parser.add_argument("--orgs-only", action="store_true")
    parser.add_argument("--repos-only", action="store_true")
    parser.add_argument("--repair", action="store_true",
                        help="只补抓上一轮失败的组织和不完整的重点仓库,不清空已有数据")
    parser.add_argument("--org", action="append", default=[], metavar="ORG_ID",
                        help="只重抓指定组织(可重复),用于定向刷新某个组织的索引")
    parser.add_argument("--org-pause", type=float, default=1.0,
                        help="组织之间的间隔秒数,降低触发镜像限速的概率")
    parser.add_argument("--per-org-limit", type=int, default=1000)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args(argv)

    if not SOURCES.is_file():
        raise SystemExit("缺少 %s" % SOURCES)
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    fetcher = Fetcher(sources["endpoints"], timeout=args.timeout)
    errors = []
    started = utc_now()

    previous = {}
    if OUT.is_file():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8"))
        except ValueError:
            previous = {}

    index, details = [], previous.get("details") or {}
    repair_orgs, repair_repos = None, None
    forced_orgs = [value.strip() for value in (args.org or []) if value.strip()]
    # 定向模式下绝不能回落到全量组织/仓库列表,否则一次 --org 会变成十分钟的全量重抓。
    targeted = bool(args.repair or forced_orgs)

    if args.repair or forced_orgs:
        if not previous:
            raise SystemExit("没有可修补的快照,先跑一次全量同步。")
        index = list(previous.get("index") or [])
        repair_orgs, repair_repos = repair_plan(sources, previous) if args.repair else ([], [])
        if forced_orgs:
            declared = {org["id"]: org for org in sources["organizations"]}
            unknown = [org_id for org_id in forced_orgs if org_id not in declared]
            if unknown:
                raise SystemExit("sources.json 的 organizations 里没有登记:%s" % ", ".join(unknown))
            pending = {org_id: declared[org_id] for org_id in forced_orgs}
            for org in repair_orgs:
                pending.setdefault(org["id"], org)
            repair_orgs = [pending[org_id] for org_id in sorted(pending)]
        repair_org_ids = {org["id"] for org in repair_orgs}
        repair_repo_ids = {entry["repo"] for entry in repair_repos}
        # 只丢掉马上要重抓的旧错误;其余旧错误原样保留,不掩盖没修好的部分。
        errors[:] = [
            item for item in (previous.get("errors") or [])
            if not (item.get("scope", "").startswith("org:")
                    and item["scope"].split(":", 1)[1] in repair_org_ids)
            and not (item.get("scope", "").startswith("repo:")
                     and item["scope"].split(":", 1)[1] in repair_repo_ids)
        ]
        print("%s:重抓 %d 个组织(%s)、%d 个重点仓库"
              % ("定向刷新" if forced_orgs else "修补模式", len(repair_orgs),
                 ", ".join(sorted(repair_org_ids)) or "无", len(repair_repos)))
    elif args.repos_only:
        # 只重抓重点仓库时索引沿用上一轮结果,不整轮重拉组织列表。
        index = list(previous.get("index") or [])

    # merged 是唯一数据源:全量模式从空开始,修补/仅仓库模式先装入上一轮索引再按 id 覆盖。
    merged = {record.get("id"): record for record in index}

    if not args.repos_only:
        orgs = repair_orgs if targeted else sources["organizations"]
        print("抓取 %d 个组织的模型索引…" % len(orgs))
        failed_orgs = []
        for position, org in enumerate(orgs, 1):
            records = sync_org(fetcher, org["id"], args.per_org_limit, errors)
            if not records:
                failed_orgs.append(org)
            for record in records:
                record["organization"] = org["id"]
                record["organization_name"] = org["name"]
                record["organization_kind"] = org["kind"]
                merged[record["id"]] = record
            print("  [%2d/%d] %-16s %4d 个模型" % (position, len(orgs), org["id"], len(records)))
            if position < len(orgs) and args.org_pause > 0:
                time.sleep(args.org_pause)

        # 大组织在镜像上偶发整轮超时。隔一会儿再补一轮,避免整块数据静默缺失。
        if failed_orgs:
            print("\n%d 个组织整轮失败,等待后重试一次:%s"
                  % (len(failed_orgs), ", ".join(item["id"] for item in failed_orgs)))
            time.sleep(10)
            recovered = 0
            for org in failed_orgs:
                records = sync_org(fetcher, org["id"], args.per_org_limit, errors)
                if not records:
                    continue
                recovered += 1
                for record in records:
                    record["organization"] = org["id"]
                    record["organization_name"] = org["name"]
                    record["organization_kind"] = org["kind"]
                    merged[record["id"]] = record
                print("  重试成功 %-16s %4d 个模型" % (org["id"], len(records)))
            print("  重试恢复 %d / %d 个组织" % (recovered, len(failed_orgs)))
            # 只清掉「整轮失败且现在已有数据」的组织对应的错误;
            # 若某组织只有一遍抓取失败,仍保留错误提示,不掩盖部分失败。
            recovered_ids = {record.get("organization") for record in merged.values()}
            cleared = {item["id"] for item in failed_orgs if item["id"] in recovered_ids}
            errors[:] = [
                item for item in errors
                if not (item.get("scope", "").startswith("org:")
                        and item["scope"][4:] in cleared)
            ]

    if not args.orgs_only:
        repos = repair_repos if targeted else sources["tracked_repos"]
        print("\n抓取 %d 个重点仓库的完整元数据…" % len(repos))
        for position, entry in enumerate(repos, 1):
            record = sync_repo(fetcher, entry, errors)
            details[entry["repo"]] = record
            print("  [%2d/%d] %-46s %s" % (
                position, len(repos), entry["repo"],
                ("%s B" % record.get("total_params_b")) if record.get("total_params_b") else "无参数量",
            ))

    index = sorted(merged.values(),
                   key=lambda item: (item.get("organization") or "", -(item.get("downloads") or 0)))
    used = fetcher.used or (sources["endpoints"][0]["base"])
    meta = next((item for item in sources["endpoints"] if item["base"].rstrip("/") == used), {})

    payload = {
        "schema": 1,
        "fetched_at": utc_now(),
        "started_at": started,
        "endpoint_used": used,
        "endpoint_kind": meta.get("kind", "unknown"),
        "endpoint_note": meta.get("note", ""),
        "per_org_limit": args.per_org_limit,
        "organizations": sources["organizations"],
        "tracked_repos": sources["tracked_repos"],
        "index": index,
        "details": details,
        "counts": {
            "index": len(index),
            "details": len(details),
            "organizations": len({item.get("organization") for item in index}),
            "errors": len(errors),
        },
        "errors": errors,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n写入 %s" % OUT)
    print("索引 %d 条,重点仓库 %d 个,覆盖组织 %d 个,错误 %d 条"
          % (payload["counts"]["index"], payload["counts"]["details"],
             payload["counts"]["organizations"], payload["counts"]["errors"]))
    print("使用端点: %s (%s)" % (used, payload["endpoint_kind"]))
    if errors:
        print("错误明细已写入快照的 errors 字段。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

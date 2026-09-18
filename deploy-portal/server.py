#!/usr/bin/env python3
"""部署管理台 · 本地 Web 服务(仅标准库)。

启动:
    python deploy-portal/server.py --port 8787

提供两类接口:
  * /api/*   JSON 接口,内部调用 engine.py(即 model-selector 的同一套规则)
  * 其它路径  直接返回 web/ 下的静态文件
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import engine

PORTAL_DIR = Path(__file__).resolve().parent
WEB_DIR = PORTAL_DIR / "web"

MIME_OVERRIDES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".md": "text/markdown; charset=utf-8",
}

VERBOSE = True


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def truthy(value):
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


# 只对这些字段做数字归一化;driver_version 这类是字符串,不能一律转 float。
NUMERIC_HARDWARE_KEYS = ("gpu_count", "vram_per_gpu_gib", "compute_capability",
                         "host_ram_gib", "disk_free_gib", "nodes",
                         "min_context_k", "context_k")

#: 只能由 GPU 目录供值的字段(值来自厂商页核实结果)。选了 gpu_id 时,调用方
#: 传这几个字段一律丢弃——否则「实测匹配」可以靠自填单卡显存或 fp8_supported
#: 绕过判定。台账的现场登记路径(gpu_id 为空)不受此限制。
VERIFIED_ONLY_KEYS = ("vram_per_gpu_gib", "compute_capability", "compute_capability_basis",
                      "gpu_name", "vendor", "ecosystem", "fp8_supported", "fp8_basis")


def build_hardware(raw, require_verified=True):
    """把前端提交的「选中的 GPU + 卡数 + 现场参数」变成推荐引擎的硬件描述。

    单卡显存和算力一律来自核实过的 GPU 目录;推荐流程不接受调用方自带这两个数,
    否则页面上的「实测匹配」就变成自己填个数字绕过判定。

    部署台账检查的是已经存在的机器,允许用现场登记的规格(例如 48GB 版 4090
    这类厂商页上没有的改装卡),但会把「未经厂商页核实」如实标出来。
    """
    if not isinstance(raw, dict):
        raise ApiError("hardware 必须是 JSON 对象")
    gpu_id = (raw.get("gpu_id") or "").strip()
    if gpu_id:
        overrides = {key: value for key, value in raw.items()
                     if key not in ("gpu_id", "gpu_count") + VERIFIED_ONLY_KEYS}
        hw, error = engine.hardware_from_gpu(gpu_id, raw.get("gpu_count"), **overrides)
        if error:
            raise ApiError(error, status=404 if "未知" in error else 400)
        hw["hardware_verified"] = True
    else:
        if require_verified:
            raise ApiError("需要选择 GPU 型号(选项来自已核实的 GPU 目录)")
        missing = [key for key in ("gpu_name", "gpu_count", "vram_per_gpu_gib")
                   if raw.get(key) in (None, "")]
        if missing:
            raise ApiError("现场登记硬件缺少字段:%s" % ", ".join(missing))
        # 算力等级只对 CUDA 生态是必填。昇腾这类非 CUDA 卡本来就没有 sm 号,
        # 强制填一个数只会逼调用方编一个,而编出来的数还会影响 FP8 判定。
        # 代价是:不填算力就必须写明生态,不能靠静默默认把昇腾当 CUDA 处理。
        ecosystem = str(raw.get("ecosystem") or "").strip().lower()
        if raw.get("compute_capability") in (None, ""):
            if not ecosystem:
                raise ApiError("现场登记硬件必须写明 ecosystem(cuda / cann):"
                               "不填算力等级时无法判断该按哪套门槛核对")
            if ecosystem == "cuda":
                raise ApiError("CUDA 生态的现场登记硬件缺少字段:compute_capability")
        elif ecosystem and ecosystem != "cuda":
            # 已经有 sm 号又自称非 CUDA 生态,两者不可能同时成立。
            raise ApiError("ecosystem=%s 不应同时提供 compute_capability(sm_xx 是 CUDA 专有)" % ecosystem)
        hw = dict(raw)
        hw.setdefault("ecosystem", ecosystem or "cuda")
        hw["hardware_verified"] = False
    for key in NUMERIC_HARDWARE_KEYS:
        value = hw.get(key)
        if isinstance(value, str) and value.strip():
            try:
                hw[key] = float(value)
            except ValueError:
                raise ApiError("%s 必须是数字" % key)
    return hw




# 宽松许可白名单。models.csv 和 model-families.csv 用同一套判断,
# 否则同一个勾选框在两张表上会给出互相矛盾的结论。
# 宽松许可白名单。判定只看 `license_id`(HF 的机器可读值,如 mit / apache-2.0),
# 不看 `license` 展示名——展示名会随措辞变化,拿它做判断早晚会错判。
PERMISSIVE_LICENSES = {"mit", "apache-2.0", "bsd-3-clause", "cc-by-4.0"}

NON_TEXT_MODALITIES = {"image", "audio", "video"}


def is_multimodal_family(row):
    """家族表的模态是分号分隔的多值字段,如 text;image;video。"""
    parts = {part.strip().lower() for part in (row.get("modalities") or "").split(";")}
    return bool(parts & NON_TEXT_MODALITIES)


def filter_catalog(params):
    payload = engine.catalog_payload()
    keyword = (params.get("q", [""])[0] or "").strip().lower()
    vllm_only = truthy(params.get("vllm_only", ["false"])[0])
    multimodal = truthy(params.get("multimodal", ["false"])[0])
    permissive = truthy(params.get("permissive", ["false"])[0])
    organization = (params.get("organization", [""])[0] or "").strip()

    models = payload["models"]
    if keyword:
        models = [
            row for row in models
            if keyword in row.get("model_name", "").lower()
            or keyword in row.get("model_id", "").lower()
            or keyword in row.get("profile", "").lower()
        ]
    if vllm_only:
        # models.csv 的每行都是带锁定 vLLM 镜像的部署档,用镜像字段判断;
        # vllm_status 只存在于 model-families.csv。
        models = [row for row in models if (row.get("vllm_image") or "").strip()]
    if multimodal:
        models = [row for row in models if truthy(row.get("multimodal"))]
    if permissive:
        models = [row for row in models if row.get("license_id") in PERMISSIVE_LICENSES]

    families = payload["families"]
    if keyword:
        families = [
            row for row in families
            if keyword in row.get("model_name", "").lower()
            or keyword in row.get("model_id", "").lower()
        ]
    if vllm_only:
        families = [row for row in families if row.get("vllm_status") == "supported"]
    # 这两个勾选框在界面上和「仅 vLLM 已支持」并排,只作用于上面那张表会让人以为过滤没生效。
    if multimodal:
        families = [row for row in families if is_multimodal_family(row)]
    if permissive:
        families = [row for row in families if row.get("license_id") in PERMISSIVE_LICENSES]
    if organization:
        families = [row for row in families if row.get("organization") == organization]

    organizations = sorted({row.get("organization", "") for row in payload["families"] if row.get("organization")})
    return {
        "models": models,
        "families": families,
        "model_count": len(models),
        "family_count": len(families),
        "total_models": payload["model_count"],
        "total_families": payload["family_count"],
        "organizations": organizations,
    }


def recipes_payload(params):
    data = engine.load_recipes()
    recipes = data.get("recipes", [])
    profile = (params.get("profile", [""])[0] or "").strip()
    keyword = (params.get("q", [""])[0] or "").strip().lower()
    if profile:
        recipes = [item for item in recipes if item.get("profile_id") == profile]
    if keyword:
        recipes = [
            item for item in recipes
            if keyword in json.dumps(item, ensure_ascii=False).lower()
        ]
    enriched = []
    for item in recipes:
        record = dict(item)
        profile_id = item.get("profile_id") or ""
        record["verification"] = engine.verification_for(profile_id) if profile_id else None
        # 只收**显式挂接**到本方案的条目:部署档 profiles 命中,或注册表条目的
        # recipe_ids 命中。挂不上就返回空列表,页面如实降级成「仅现场记录」——
        # 不再拿一堆别的引擎的全局文档来把这一栏填满。
        record["authoritative_docs"] = engine.docs_for_recipe(item)
        enriched.append(record)
    return {
        "recipes": enriched,
        "count": len(enriched),
        "mirrors": data.get("mirrors", {}),
        "note": data.get("note", ""),
        "updated": data.get("updated", ""),
    }


def deployments_payload():
    data = engine.load_deployments()
    return {
        "environments": data.get("environments", []),
        "note": data.get("note", ""),
        "updated": data.get("updated", ""),
    }


def handle_recommend(body):
    hw = build_hardware(body.get("hardware") or {})
    preference = body.get("preference") or "balanced"
    top = body.get("top") or 5
    return engine.recommend(
        hw,
        preference=preference,
        top=top,
    )


def handle_check(body):
    hw = build_hardware(body.get("hardware") or {}, require_verified=False)
    profile_id = (body.get("profile_id") or "").strip()
    if not profile_id:
        raise ApiError("缺少 profile_id")
    result = engine.evaluate_profile(hw, profile_id, body.get("preference") or "balanced")
    if result is None:
        raise ApiError("目录里没有这个部署档: %s" % profile_id, status=404)
    # 台账里可能是厂商页上没有的改装卡,如实把核实状态带回前端。
    result["hardware_verified"] = bool(hw.get("hardware_verified"))
    result["hardware_gpu_name"] = hw.get("gpu_name")
    return result


def dispatch(method, path, params, body):
    if path == "/api/health":
        return {"ok": True, "service": "deploy-portal"}
    if path == "/api/meta":
        return engine.meta()
    if path == "/api/gpus":
        return {
            "gpus": engine.gpu_catalog(),
            "meta": engine.gpu_snapshot_meta(),
        }
    if path == "/api/catalog":
        return filter_catalog(params)
    if path == "/api/recipes":
        return recipes_payload(params)
    if path == "/api/deployments":
        return deployments_payload()
    if path == "/api/hf-catalog":
        return {
            "summary": engine.hf_summary(),
            "page": engine.hf_query(
                keyword=(params.get("q", [""])[0] or ""),
                organization=(params.get("organization", [""])[0] or ""),
                task=(params.get("task", [""])[0] or ""),
                license_filter=(params.get("license", [""])[0] or ""),
                sort=(params.get("sort", ["downloads"])[0] or "downloads"),
                limit=params.get("limit", [120])[0],
                offset=params.get("offset", [0])[0],
            ),
        }
    if path == "/api/hf-detail":
        repo = (params.get("repo", [""])[0] or "").strip()
        if not repo:
            raise ApiError("缺少 repo 参数")
        detail = engine.hf_detail(repo)
        if detail is None:
            raise ApiError("快照里没有这个仓库: %s" % repo, status=404)
        return detail
    if path == "/api/docs":
        return engine.doc_sources((params.get("profile", [""])[0] or "").strip())
    if method == "POST" and path == "/api/recommend":
        return handle_recommend(body)
    if method == "POST" and path == "/api/check":
        return handle_check(body)
    raise ApiError("未知接口: %s %s" % (method, path), status=404)


class Handler(BaseHTTPRequestHandler):
    server_version = "deploy-portal/0.1"

    def log_message(self, fmt, *args):
        if not VERBOSE:
            return
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, data, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        # 静态资源也禁用缓存。这是本机开发工具,改完 js/css 刷新就该生效;
        # 不带缓存头时浏览器会启发式缓存,出现「服务端已经是新文件、页面还是旧行为」
        # 的假象(2026-09-17 实际踩到,排查了很久)。
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ApiError("请求体不是合法 JSON")

    def _serve_static(self, path):
        # 浏览器会无视 <link rel="icon"> 直接请求 /favicon.ico,不处理就是一条可见的 404。
        if path == "/favicon.ico":
            target = WEB_DIR / "favicon.svg"
            if target.is_file():
                self._send_bytes(target.read_bytes(), MIME_OVERRIDES[".svg"])
                return
        relative = "index.html" if path in ("/", "") else path.lstrip("/")
        parts = [part for part in relative.split("/") if part not in ("", ".")]
        if any(part == ".." for part in parts):
            raise ApiError("非法路径", status=403)
        target = WEB_DIR.joinpath(*parts)
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            raise ApiError("找不到 %s" % relative, status=404)
        if WEB_DIR.resolve() not in target.resolve().parents:
            raise ApiError("越界访问", status=403)
        suffix = target.suffix.lower()
        content_type = MIME_OVERRIDES.get(suffix) or mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self._send_bytes(target.read_bytes(), content_type)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        params = parse_qs(parsed.query)
        try:
            if path.startswith("/api/"):
                self._send_json(dispatch("GET", path, params, {}))
            else:
                self._serve_static(path)
        except ApiError as error:
            if path.startswith("/api/"):
                self._send_json({"error": str(error)}, status=error.status)
            else:
                self._send_bytes(str(error).encode("utf-8"), "text/plain; charset=utf-8", status=error.status)
        except BrokenPipeError:
            pass
        except Exception as error:  # noqa: BLE001  单机工具,兜底避免服务中断
            self._send_json({"error": "服务内部错误: %s" % error}, status=500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        params = parse_qs(parsed.query)
        try:
            body = self._read_body()
            self._send_json(dispatch("POST", path, params, body))
        except ApiError as error:
            self._send_json({"error": str(error)}, status=error.status)
        except Exception as error:  # noqa: BLE001
            self._send_json({"error": "服务内部错误: %s" % error}, status=500)


def main(argv=None):
    global VERBOSE
    parser = argparse.ArgumentParser(description="大模型部署管理台")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    parser.add_argument("--quiet", action="store_true", help="不打印每条请求日志")
    args = parser.parse_args(argv)

    VERBOSE = not args.quiet

    if not WEB_DIR.is_dir():
        raise SystemExit("找不到 web/ 目录: %s" % WEB_DIR)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = "http://%s:%d/" % (args.host, args.port)
    meta = engine.meta()
    print("部署管理台已启动: %s" % url)
    print("模型部署档 %d 条,模型家族 %d 条(来源: %s)"
          % (meta["catalog"]["model_count"], meta["catalog"]["family_count"], meta["catalog"]["models_csv"]))
    print("按 Ctrl+C 停止。")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""部署管理台冒烟测试:在进程内起服务,逐个打接口并断言。

用法:
    python deploy-portal/tools/smoke_test.py
"""

from __future__ import annotations

import json
import re
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

PORTAL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PORTAL_DIR))

import server  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

server.VERBOSE = False

PORT = 8799
BASE = "http://127.0.0.1:%d" % PORT

failures = []


def check(label, condition, detail=""):
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s %s" % (label, detail))
        failures.append(label)


def request(method, path, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
            return response.status, body
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def get_json(path):
    status, body = request("GET", path)
    return status, json.loads(body)


def post_json(path, payload):
    status, body = request("POST", path, payload)
    return status, json.loads(body)


CONTROL_PATTERN = re.compile(
    r'<(button|select|input|textarea)\b[^>]*?\bid="([A-Za-z0-9_-]+)"', re.I
)
DATA_HOOK_PATTERN = re.compile(r'data-(copy|check|action)="')


def dead_controls():
    """静态扫描前端:找出渲染出来却没人监听的控件。

    这一类问题在接口层完全看不出来——页面能打开、接口全 200,但按钮点下去没反应。
    判据:控件声明的 id 在整个模块里除了它自己那行以外再没被任何方式引用过
    (直接 '#id'、循环数组里的 'id'、辅助函数 value('id') 都算被引用)。
    """
    web = PORTAL_DIR / "web" / "js"
    problems = []
    for path in sorted(web.rglob("*.js")):
        text = path.read_text(encoding="utf-8")
        stripped = CONTROL_PATTERN.sub("", text)
        for kind, ident in CONTROL_PATTERN.findall(text):
            if re.search(r"\b%s\b" % re.escape(ident), stripped):
                continue
            problems.append("%s: <%s id=%s> 从未被引用" % (path.name, kind, ident))
        for hook in set(DATA_HOOK_PATTERN.findall(text)):
            bound = (hook == "copy" and "bindCopyButtons" in text) or (
                hook == "check" and "data-check" in text
            )
            if not bound:
                problems.append("%s: data-%s 没有对应的绑定函数" % (path.name, hook))
    return problems


def module_syntax():
    """静态检查:ES 模块的括号必须配平。

    2026-09-17 踩过:整文件替换时漏掉末尾的 `}`,浏览器只报
    `SyntaxError: Unexpected end of input`,位置空白,页面永远停在「加载中…」,
    而所有接口都是 200。这里用基于字符扫描的配对检查复现同一个失败。
    不引入 node 依赖,标准库自足。
    """
    web = PORTAL_DIR / "web" / "js"
    problems = []
    for path in sorted(web.rglob("*.js")):
        problems.extend(_unbalanced(path))
    return problems


def _unbalanced(path):
    """扫描一个 JS 文件,报告括号未闭合的位置。

    会跳过字符串、模板串、行注释、块注释和正则字面量。正则和除号都是 `/`,
    靠「前一个有效记号」区分:前面是标识符/数字/`)`/`]` 就是除号,否则是正则
    —— 前端里有 `/[&<>"']/g` 这种写法,不区分就会把字符类里的引号当成字符串开头。
    """
    text = path.read_text(encoding="utf-8")
    pairs = {")": "(", "]": "[", "}": "{"}
    # 不要包含 `<` / `>`:模板串里到处是 HTML 闭合标签 `</td>`,`</` 会被当成
    # 正则开头,一路吞到下一个 `/`,整份文件的括号统计就乱了(实测会误报)。
    regex_ok = set("(,=:[!&|?;{}+-*%~^")
    stack = []
    index = 0
    line = 1
    length = len(text)
    quote = None       # 当前所处的字符串定界符
    prev = ""          # 上一个有效记号,用于区分正则和除号
    while index < length:
        char = text[index]
        if char == "\n":
            line += 1
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in "\"'`":
            quote = char
            index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] != "\n":
                index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "*":
            index += 2
            while index + 1 < length and not (text[index] == "*" and text[index + 1] == "/"):
                if text[index] == "\n":
                    line += 1
                index += 1
            index += 2
            continue
        if char == "/" and (not prev or prev in regex_ok):
            # 正则字面量:字符类里的括号和引号都不算数。
            index += 1
            in_class = False
            while index < length:
                if text[index] == "\\":
                    index += 2
                    continue
                if text[index] == "\n":
                    break
                if text[index] == "[":
                    in_class = True
                elif text[index] == "]":
                    in_class = False
                elif text[index] == "/" and not in_class:
                    index += 1
                    while index < length and text[index].isalpha():
                        index += 1
                    break
                index += 1
            prev = "#"
            continue
        if char in "([{":
            stack.append((char, line))
            prev = char
        elif char in ")]}":
            if not stack or stack[-1][0] != pairs[char]:
                return ["%s:%d 多余的 %s" % (path.name, line, char)]
            stack.pop()
            prev = char
        elif not char.isspace():
            prev = char
        index += 1
    if quote:
        return ["%s 字符串 %s 未闭合" % (path.name, quote)]
    if stack:
        opener, at = stack[0]
        return ["%s 第 %d 行的 %s 没有闭合(共 %d 个未闭合)" % (path.name, at, opener, len(stack))]
    return []


def main():
    problems = module_syntax()
    check("前端模块括号配平(缺右括号会让整页停在「加载中」)", not problems,
          "; ".join(problems[:4]))
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    print("== 部署管理台冒烟测试 ==")
    try:
        status, health = get_json("/api/health")
        check("健康检查", status == 200 and health.get("ok") is True)

        status, meta = get_json("/api/meta")
        check("元数据接口", status == 200 and meta["catalog"]["model_count"] > 0,
              json.dumps(meta)[:120])

        status, catalog = get_json("/api/catalog")
        check("目录接口", status == 200 and catalog["model_count"] == catalog["total_models"])

        # 2026-09-16:目录里的权重/参数量/上下文/许可已全部按实测订正。
        # 下面几条防的是「回归成估算值或没来源的数字」。
        no_origin = [row["model_id"] for row in catalog["models"]
                     if not row.get("verified_repo")
                     or len(row.get("verified_revision") or "") != 40]
        check("每个部署档都登记了核实来源", not no_origin, "缺来源=%s" % no_origin[:5])
        no_origin_family = [row["model_id"] for row in catalog["families"]
                            if not row.get("verified_repo")
                            or len(row.get("verified_revision") or "") != 40]
        check("每个家族条目都登记了核实来源", not no_origin_family,
              "缺来源=%s" % no_origin_family[:5])
        no_license = [row["model_id"] for row in catalog["models"]
                      if not row.get("license_id")]
        check("每个部署档都有机器可读许可 id", not no_license, "缺许可=%s" % no_license)
        bad_context_source = [row["model_id"] for row in catalog["models"]
                              if row.get("context_source") not in ("card", "config")]
        check("上下文标明了取值口径", not bad_context_source,
              "口径不明=%s" % bad_context_source)
        no_weight = [row["model_id"] for row in catalog["models"]
                     if not row.get("weight_gib")]
        check("每个部署档都有实测权重", not no_weight, "缺权重=%s" % no_weight)

        # 「仅宽松许可」必须按 license_id 判定:拿展示名判会把 Qwen License 之类误判成宽松。
        status, permissive = get_json("/api/catalog?permissive=true")
        allowed = {"mit", "apache-2.0", "bsd-3-clause", "cc-by-4.0"}
        bad_license = sorted({row.get("license_id") for row in permissive["models"]
                              if row.get("license_id") not in allowed})
        check("宽松许可按机器可读 id 判定",
              status == 200 and not bad_license, "混入=%s" % bad_license)

        status, filtered = get_json("/api/catalog?q=qwen&vllm_only=true")
        check("目录过滤", status == 200 and 0 < filtered["model_count"] < catalog["total_models"],
              "过滤后=%d" % filtered.get("model_count", -1))

        # 过滤勾选框曾经只作用于部署档表,家族表被静默忽略,看起来像没生效。
        for flag, label in (("multimodal", "仅多模态"), ("permissive", "仅宽松许可")):
            status, narrowed = get_json("/api/catalog?" + flag + "=true")
            check("目录过滤对两张表都生效 · %s" % label,
                  status == 200
                  and 0 < narrowed["model_count"] < catalog["total_models"]
                  and 0 < narrowed["family_count"] < catalog["total_families"],
                  "部署档=%d 家族=%d" % (narrowed["model_count"], narrowed["family_count"]))

        status, recipes = get_json("/api/recipes")
        check("方案接口", status == 200 and len(recipes["recipes"]) >= 7,
              "方案数=%d" % len(recipes.get("recipes", [])))
        check("方案都带来源文档",
              all(item.get("sources") for item in recipes["recipes"]))
        check("镜像策略已登记", len(recipes["mirrors"]["entries"]) >= 5)
        details = [item for item in recipes["recipes"] if item.get("authoritative_docs")]
        check("方案带权威来源", len(details) >= 5, "带权威来源的方案=%d" % len(details))
        check("权威来源都验证过状态",
              all(doc.get("status") == 200
                  for item in details for doc in item["authoritative_docs"]))
        verified = [item for item in recipes["recipes"] if item.get("verification")]
        check("方案带官方仓库核对", len(verified) >= 5, "带核对的方案=%d" % len(verified))
        # 事故:recipes.json 的验收清单和 server.py 的核对结果曾共用 verification 键,
        # 前端按数组取用就整页崩掉。现在两者必须是不同的键并且类型正确。
        check("方案的验收清单是数组",
              all(isinstance(item.get("acceptance"), list) and item["acceptance"]
                  for item in recipes["recipes"]),
              str([item["id"] for item in recipes["recipes"]
                   if not isinstance(item.get("acceptance"), list)])[:120])
        check("核对结果不与验收清单共用键",
              all(not isinstance(item.get("verification"), list)
                  for item in recipes["recipes"]))
        orphan = [item for item in recipes["recipes"] if not item.get("profile_id")]
        check("无部署档的方案也有权威来源",
              bool(orphan) and all(item.get("authoritative_docs") for item in orphan),
              "无档方案=%d" % len(orphan))

        status, catalog_snapshot = get_json("/api/hf-catalog?limit=20")
        summary = catalog_snapshot["summary"]
        check("抓取快照可用", status == 200 and summary.get("available") is True,
              json.dumps(summary.get("hint", ""), ensure_ascii=False)[:120])
        if summary.get("available"):
            page = catalog_snapshot["page"]
            check("快照索引有数据", page["grand_total"] > 1000, "全库=%d" % page["grand_total"])
            check("快照走国内镜像", summary.get("endpoint_kind") == "domestic-mirror",
                  str(summary.get("endpoint_used")))
            check("分页生效", len(page["models"]) <= page["limit"])
            check("分面可用", len(page["facets"]["organizations"]) >= 10)
            check("索引项带 revision", all(item.get("sha") for item in page["models"]))

            # 数据驱动的死控件:下拉框的候选项来自分面。分面为空时控件还在,
            # 但只剩「全部」一个选项,用户点了没有任何效果。
            facets = page["facets"]
            for name, label in (("organizations", "组织"), ("tasks", "任务类型"),
                                ("licenses", "许可证")):
                check("筛选分面有候选项 · %s" % label, len(facets.get(name) or []) >= 2,
                      "%s 只有 %d 项" % (label, len(facets.get(name) or [])))
            check("索引项带任务类型",
                  # 上游只给一部分仓库标了任务类型,这里卡的是「没有被整批丢掉」,
                  # 真正的功能保证是上面那条「筛选分面有候选项」。
                  sum(1 for item in page["models"] if item.get("pipeline_tag"))
                  >= len(page["models"]) * 0.3,
                  "有值=%d/%d" % (sum(1 for item in page["models"] if item.get("pipeline_tag")),
                                  len(page["models"])))
            check("索引项带点赞数",
                  sum(1 for item in page["models"] if item.get("likes") is not None)
                  >= len(page["models"]) * 0.95,
                  "缺失=%d" % sum(1 for item in page["models"] if item.get("likes") is None))

            status, second_page = get_json("/api/hf-catalog?limit=5&offset=5")
            first_ids = [item["id"] for item in catalog_snapshot["page"]["models"][:5]]
            second_ids = [item["id"] for item in second_page["page"]["models"]]
            check("翻页返回不同结果", status == 200 and not set(first_ids) & set(second_ids),
                  "重叠=%s" % sorted(set(first_ids) & set(second_ids))[:3])

            # 曾经的真实事故:某个大组织整轮超时,索引里静默少了整块数据而没人发现。
            declared_orgs = {item["id"] for item in summary.get("organizations") or []}
            covered_orgs = set(page["facets"]["organizations"])
            check("登记的组织都有数据", not (declared_orgs - covered_orgs),
                  "缺失组织=%s" % sorted(declared_orgs - covered_orgs))

            tracked = [entry["repo"] for entry in summary.get("tracked_repos") or []]
            incomplete = []
            for repo in tracked:
                repo_status, repo_detail = get_json("/api/hf-detail?repo=" + urllib.parse.quote(repo))
                if (repo_status != 200
                        or len(repo_detail.get("revision") or "") != 40
                        or not (repo_detail.get("weight_gib") or repo_detail.get("gguf_gib"))):
                    incomplete.append(repo)
            check("重点仓库详情都完整", not incomplete, "缺字段=%s" % incomplete)

            status, filtered_snapshot = get_json("/api/hf-catalog?q=qwen3&limit=10")
            check("快照关键词过滤",
                  status == 200 and 0 < filtered_snapshot["page"]["total"] < page["grand_total"],
                  "过滤后=%d" % filtered_snapshot["page"].get("total", -1))

            status, org_snapshot = get_json("/api/hf-catalog?organization=Qwen&limit=5")
            check("快照组织过滤",
                  status == 200 and all(item["organization"] == "Qwen"
                                        for item in org_snapshot["page"]["models"]))

            status, detail = get_json("/api/hf-detail?repo=zai-org/GLM-5.2")
            check("仓库详情", status == 200 and len(detail.get("revision") or "") == 40,
                  str(detail.get("revision"))[:12])
            check("详情含真实参数量与权重", bool(detail.get("total_params_b")) and bool(detail.get("weight_gib")))
            check("详情注明量化档位", bool(detail.get("quant")))

            status, missing = get_json("/api/hf-detail?repo=nope/nope")
            check("未知仓库返回 404", status == 404)

        status, docs = get_json("/api/docs")
        check("权威文档接口", status == 200 and docs.get("available") is True)
        check("文档全部可达", (docs.get("counts") or {}).get("failed") == 0,
              json.dumps(docs.get("counts")))
        official_recipes = [
            item for item in docs["sources"]
            if (item.get("kind") or "").startswith("official-recipe")
        ]
        check("有 vLLM 官方逐模型配方", len(official_recipes) >= 5,
              "配方数=%d" % len(official_recipes))

        status, profile_docs = get_json("/api/docs?profile=glm52-int4-a100")
        check("按部署档过滤文档",
              status == 200 and any("kv" in item["id"] for item in profile_docs["sources"]),
              str([item["id"] for item in profile_docs["sources"]])[:120])

        status, deployments = get_json("/api/deployments")
        check("台账接口", status == 200 and len(deployments["environments"]) == 3)

        status, gpus = get_json("/api/gpus")
        check("GPU 目录接口", status == 200 and len(gpus["gpus"]) >= 8,
              "卡数=%d" % len(gpus.get("gpus", [])))
        bad_gpu = [gpu["id"] for gpu in gpus["gpus"]
                   if not gpu.get("verification") or gpu["verification"].get("status") != "ok"]
        check("GPU 目录里每张卡都核实通过", not bad_gpu, "未通过=%s" % bad_gpu[:5])
        no_origin = [gpu["id"] for gpu in gpus["gpus"]
                     if not gpu.get("source_url") or len(gpu["verification"].get("sha256") or "") != 64]
        check("每张卡都登记了来源页与内容指纹", not no_origin, "缺来源=%s" % no_origin[:5])
        a100 = next((gpu for gpu in gpus["gpus"] if gpu["id"] == "a100-sxm-80"), None)
        check("A100 显存与算力取自核实目录",
              a100 is not None and a100["vram_gib"] == 80.0 and a100["compute_capability"] == 8.0)

        # --- 华为昇腾(非 CUDA 生态) -----------------------------------------
        # 这一组断言的意义:昇腾卡不能沿用 CUDA 的口径。sm 映射、NVIDIA 驱动下限、
        # CUDA 的 KV 精度公式,任何一条被悄悄套上去都会给出看似合理的错误结论。
        ascend = [gpu for gpu in gpus["gpus"] if gpu.get("vendor") == "huawei"]
        check("GPU 目录里含华为昇腾条目", len(ascend) >= 1, "昇腾条数=%d" % len(ascend))
        check("昇腾条目都标为 cann 生态",
              all(gpu.get("ecosystem") == "cann" for gpu in ascend),
              str([(gpu["id"], gpu.get("ecosystem")) for gpu in ascend]))
        no_cc = [gpu["id"] for gpu in ascend
                 if gpu.get("compute_capability") is not None
                 or not gpu.get("compute_capability_basis")]
        check("昇腾不做 sm 映射且写明口径", not no_cc,
              "不该有算力等级或缺少口径说明=%s" % no_cc)
        check("昇腾的 FP8 能力来自厂商页标称值",
              all(gpu.get("fp8_basis") and "算力推导" not in gpu.get("fp8_basis", "")
                  for gpu in ascend))
        cc_checked_bad = [gpu["id"] for gpu in gpus["gpus"]
                          if bool(gpu["verification"].get("cc_checked")) != (gpu.get("vendor") == "nvidia")]
        check("只有 NVIDIA 参与官方算力表核实", not cc_checked_bad, str(cc_checked_bad))
        atlas350 = next((gpu for gpu in ascend if gpu["id"] == "ascend-950pr-atlas350"), None)
        check("Atlas 350 显存 112 GiB 且按厂商页支持 FP8",
              atlas350 is not None and atlas350["vram_gib"] == 112.0
              and atlas350["fp8_supported"] is True)
        duo = [gpu for gpu in ascend if gpu["id"].startswith("ascend-300i-duo")]
        check("Atlas 300I Duo 的两种容量各列一条",
              sorted(gpu["vram_gib"] for gpu in duo) == [48.0, 96.0],
              str([gpu["vram_gib"] for gpu in duo]))
        check("厂商页未标注的字段留空而不是填记忆值",
              all(not gpu.get("architecture") and gpu.get("architecture_basis") for gpu in duo))

        status, ascend_result = post_json("/api/recommend", {
            "hardware": {"gpu_id": "ascend-950pr-atlas350", "gpu_count": 8,
                         "context_k": 32, "workload": "agent,coding"},
            "preference": "balanced",
            "top": 5,
        })
        check("昇腾推荐接口可用", status == 200 and ascend_result["plans_total"] > 0,
              "命中=%d" % ascend_result.get("plans_total", -1))
        check("昇腾推荐结果标明生态并有说明",
              ascend_result.get("ecosystem") == "cann" and ascend_result.get("ecosystem_note"),
              str(ascend_result.get("ecosystem"))[:80])
        check("昇腾的 KV cache 不套 CUDA 公式,只按权重下界",
              all(item["memory"]["kv_gib"] is None and item["memory"]["kv_note"]
                  for item in ascend_result["plans"]),
              str([(item["profile"]["model_id"], item["memory"]["kv_gib"])
                   for item in ascend_result["plans"]])[:160])
        ascend_text = " ".join(text for item in ascend_result["plans"] + ascend_result["rejected"]
                               for text in item["failures"] + item["warnings"])
        check("昇腾不会被 NVIDIA 算力/驱动门槛卡住",
              "sm_" not in ascend_text and "驱动需" not in ascend_text,
              ascend_text[:160])
        check("昇腾卡不关联 CUDA 栈的部署方案",
              all(not item["recipes"] for item in ascend_result["plans"]),
              str([(item["profile"]["model_id"], item["recipes"])
                   for item in ascend_result["plans"]])[:160])

        # 选卡时这几个字段只能由目录供值,否则「实测匹配」能靠自填绕过判定。
        status, spoofed = post_json("/api/recommend", {
            "hardware": {"gpu_id": "ascend-300i-duo-96", "gpu_count": 8,
                         "vram_per_gpu_gib": 500, "compute_capability": 9.0,
                         "ecosystem": "cuda", "fp8_supported": True},
        })
        check("推荐不接受自填的单卡显存与生态",
              status == 200 and spoofed["hardware"]["vram_per_gpu_gib"] == 96.0
              and spoofed["hardware"]["ecosystem"] == "cann"
              and spoofed["hardware"]["fp8_supported"] is False,
              str(spoofed.get("hardware"))[:160])

        status, ascend_check = post_json("/api/check", {
            "hardware": {"gpu_id": "ascend-950pr-atlas350", "gpu_count": 8},
            "profile_id": "glm52-int4-a100",
        })
        # 8×112 GiB 只按权重下界是放得下的,所以这里应该是「通过」——但必须带上
        # 「KV 未计入」的说明,否则一个只算了权重的结论会被读成完整判定。
        check("昇腾达标检查的通过结论带上下界说明",
              status == 200 and ascend_check["pass"] is True
              and ascend_check["memory"]["kv_verified"] is False
              and any("下界" in text for text in ascend_check["warnings"]),
              str(ascend_check.get("warnings"))[:200])
        check("昇腾达标检查标明所属生态",
              ascend_check.get("ecosystem") == "cann", str(ascend_check.get("ecosystem")))

        status, ascend_small = post_json("/api/check", {
            "hardware": {"gpu_id": "ascend-300i-duo-48", "gpu_count": 1},
            "profile_id": "glm52-int4-a100",
        })
        check("昇腾放不下时如实报缺口",
              status == 200 and ascend_small["pass"] is False
              and any("单卡" in text for text in ascend_small["failures"]),
              str(ascend_small.get("failures"))[:160])

        # 部署档目录(models.csv)只有 CUDA 栈实现,没有 ecosystem 列。昇腾用户
        # 必须被告知这一点,否则会把「匹配到的 CUDA 栈档」当成昇腾的部署方法。
        check("昇腾结果里说明部署档目录只有 CUDA 栈实现",
              ascend_result.get("profile_catalog_ecosystem") == "cuda"
              and "CUDA 栈" in (ascend_result.get("stack_note") or ""),
              str(ascend_result.get("stack_note"))[:120])
        status, cuda_result = post_json("/api/recommend", {
            "hardware": {"gpu_id": "a100-sxm-80", "gpu_count": 8, "context_k": 32},
        })
        check("CUDA 卡不显示跨生态说明",
              status == 200 and (cuda_result.get("stack_note") or "") == "",
              str(cuda_result.get("stack_note"))[:80])

        # 现场登记路径:不填算力就必须写明生态。原实现强制 CUDA 卡填
        # compute_capability,昇腾只能编一个数,而那个数还会影响 FP8 判定。
        status, error = post_json("/api/check", {
            "hardware": {"gpu_name": "某昇腾整机", "gpu_count": 8, "vram_per_gpu_gib": 96,
                         "compute_capability": 9.0, "ecosystem": "cann"},
            "profile_id": "glm52-int4-a100",
        })
        check("自称非 CUDA 生态却给 sm 号会被拒绝",
              status == 400 and "CUDA 专有" in error.get("error", ""), str(error)[:140])
        status, error = post_json("/api/check", {
            "hardware": {"gpu_name": "某卡", "gpu_count": 8, "vram_per_gpu_gib": 96},
            "profile_id": "glm52-int4-a100",
        })
        check("不填算力又不写生态会被拒绝",
              status == 400 and "ecosystem" in error.get("error", ""), str(error)[:140])
        status, onsite = post_json("/api/check", {
            "hardware": {"gpu_name": "Atlas 300I Duo 现场机", "gpu_count": 8,
                         "vram_per_gpu_gib": 96, "ecosystem": "cann"},
            "profile_id": "glm52-int4-a100",
        })
        check("昇腾现场登记可以不填算力等级",
              status == 200 and onsite.get("ecosystem") == "cann"
              and onsite.get("hardware_verified") is False,
              str(onsite)[:140])
        # 非 CUDA 生态拿不到厂商页标称值时,FP8 必须报「无法判定」而不是
        # 悄悄当成不支持——后者会把 Atlas 350 说成没有 FP8。
        fp8_rows = [item for item in ascend_result["plans"] if item["profile"]["fp8_required"] in ("true", True)]
        fp8_text = " ".join(text for item in fp8_rows for text in item["failures"])
        check("FP8 判定不替厂商页下结论",
              "厂商页未标注" not in fp8_text or all(
                  item["profile"]["fp8_required"] for item in fp8_rows),
              fp8_text[:120])

        status, result = post_json("/api/recommend", {
            "hardware": {"gpu_id": "a100-sxm-80", "gpu_count": 8, "driver_version": "570.124.06",
                         "host_ram_gib": 512, "disk_free_gib": 1000, "nodes": 1,
                         "context_k": 32, "workload": "agent,coding,reasoning"},
            "preference": "balanced",
            "top": 5,
        })
        check("A100 推荐接口", status == 200 and result["plans_total"] > 0,
              "命中=%d" % result.get("plans_total", -1))
        check("推荐条数在 3-5 之间", 3 <= len(result["plans"]) <= 5, "条数=%d" % len(result["plans"]))
        check("推荐里没有重复模型",
              len({item["profile"]["model_name"] for item in result["plans"]}) == len(result["plans"]))
        top_profile = result["plans"][0]["profile"]["model_id"]
        check("A100 首选是 GLM-5.2", top_profile == "glm52-int4-a100", top_profile)
        check("推荐结果能关联到部署方案",
              any(item["recipes"] for item in result["plans"]))
        check("每条方案都带显存核算",
              all(item["memory"]["weight_gib"] and item["memory"]["needed_gib"] for item in result["plans"]))
        check("显存核算含实测权重与 KV 两部分",
              all(item["memory"]["kv_gib"] is not None for item in result["plans"]
                  if item["profile"]["attention_kind"]))
        check("方案不会把显存用到九成以上",
              all(item["memory"]["utilization"] <= 0.90 for item in result["plans"]),
              str([item["memory"]["utilization"] for item in result["plans"]]))

        status, throttled = post_json("/api/recommend", {
            "hardware": {"gpu_id": "a100-sxm-80", "gpu_count": 1, "driver_version": "570.124.06"},
            "preference": "throughput",
        })
        check("单卡场景仍能给出可部署档", status == 200 and throttled["plans_total"] > 0)
        check("单卡场景不会推荐 GLM-5.2",
              all(item["profile"]["model_id"] != "glm52-int4-a100" for item in throttled["plans"]))

        status, checked = post_json("/api/check", {
            "hardware": {"gpu_id": "a100-sxm-80", "gpu_count": 8, "driver_version": "570.124.06"},
            "profile_id": "glm52-int4-a100",
        })
        check("达标检查(应通过)", status == 200 and checked["pass"] is True)

        status, checked = post_json("/api/check", {
            "hardware": {"gpu_id": "a100-sxm-80", "gpu_count": 8, "driver_version": "470.82.01"},
            "profile_id": "glm52-int4-a100",
        })
        check("达标检查(驱动过低应不通过)",
              status == 200 and checked["pass"] is False and any("驱动" in text for text in checked["failures"]))

        status, checked = post_json("/api/check", {
            "hardware": {"gpu_name": "NVIDIA GeForce RTX 4090 48GB", "gpu_count": 8,
                         "vram_per_gpu_gib": 48, "compute_capability": 8.9,
                         "driver_version": "575.51.03"},
            "profile_id": "minimax-m27-awq",
        })
        check("台账里未核实的改装卡也能检查且如实标注",
              status == 200 and checked.get("hardware_verified") is False, str(checked)[:120])

        status, error = post_json("/api/recommend", {"hardware": {"gpu_count": 8}})
        check("推荐必须选 GPU 型号", status == 400 and "GPU" in error.get("error", ""), str(error)[:120])

        status, error = post_json("/api/recommend", {"hardware": {"gpu_id": "no-such-gpu", "gpu_count": 8}})
        check("未知 GPU 返回 404", status == 404, str(error)[:120])

        status, error = post_json("/api/recommend", {
            "hardware": {"gpu_id": "a100-sxm-80", "gpu_count": 8, "vram_per_gpu_gib": 500},
        })
        check("推荐不接受自填单卡显存", status == 200 and result["totals"]["vram_per_gpu_gib"] == 80.0)

        status, error = post_json("/api/check", {
            "hardware": {"gpu_id": "a100-sxm-80", "gpu_count": 8}, "profile_id": "nope"})
        check("未知部署档返回 404", status == 404)

        status, body = request("GET", "/api/unknown")
        check("未知接口返回 404", status == 404)

        status, html = request("GET", "/")
        check("首页可访问", status == 200 and "大模型部署管理台" in html)

        status, css = request("GET", "/css/app.css")
        check("静态样式可访问", status == 200 and "--accent" in css)

        status, icon = request("GET", "/favicon.ico")
        check("favicon.ico 不返回 404", status == 200, "status=%s" % status)

        status, js = request("GET", "/js/app.js")
        check("前端脚本可访问", status == 200 and "boot" in js)

        # 静态资源必须禁用缓存,否则改完 js/css 刷新还是旧行为(2026-09-17 实际踩到)。
        no_store = []
        for asset in ("/", "/js/app.js", "/css/app.css"):
            with urllib.request.urlopen(BASE + asset, timeout=30) as response:
                if (response.headers.get("Cache-Control") or "") != "no-store":
                    no_store.append(asset)
        check("静态资源禁用缓存", not no_store, "未禁用=%s" % no_store)

        problems = dead_controls()
        check("没有渲染出来却点不动的控件", not problems, "; ".join(problems[:4]))

        status, _ = request("GET", "/../server.py")
        check("目录穿越被拒绝", status in (403, 404), "status=%s" % status)
    finally:
        httpd.shutdown()
        httpd.server_close()

    print("\n结果:%s" % ("全部通过" if not failures else "失败 %d 项 -> %s" % (len(failures), failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

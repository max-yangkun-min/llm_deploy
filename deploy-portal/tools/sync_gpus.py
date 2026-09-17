#!/usr/bin/env python3
"""核实 GPU 规格并生成 data/gpu-catalog.json。

每个数字都要能在权威页面上逐字命中;命不中就报失败、把原因写进快照,
绝不用记忆里的值顶替。

- 显存容量 / 显存类型 / 互联:必须出现在厂商产品页正文里(markers 全部命中);
- 算力(compute capability):NVIDIA 卡必须出现在 NVIDIA 官方 CUDA-Enabled GPUs 表
  对应档位里;昇腾等非 CUDA 生态**不做 sm 映射**(sm_xx 是 NVIDIA 专有标度),
  该字段留空并写明口径。

只收录「官方产品页还活着、且单卡显存能在页面正文逐字命中」的卡。产品页已下线
的旧卡(如 A800/H800/L20)不收录,避免为了凑列表而填记忆值;厂商页没写明的字段
(如 Atlas 300I Duo 的芯片型号)同样留空,不填记忆值。

用法:
    python deploy-portal/tools/sync_gpus.py            # 联网核实并写快照
    python deploy-portal/tools/sync_gpus.py --check     # 只核实,不写文件
    python deploy-portal/tools/sync_gpus.py --offline   # 离线:沿用上次核实结果重建 JSON
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
PORTAL_DIR = TOOLS_DIR.parent
OUT = PORTAL_DIR / "data" / "gpu-catalog.json"
CC_URL = "https://developer.nvidia.com/cuda-gpus"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# vram_capacity: 单卡显存 GiB。markers 里的容量写法是该页真实字样。
# cc_name 必须与官方算力表里的名字完全一致,否则算力无法核实。
GPUS = [
    {
        "id": "h100-sxm-80",
        "vendor": "nvidia",
        "ecosystem": "cuda",
        "name": "NVIDIA H100 SXM 80GB",
        "architecture": "Hopper",
        "form_factor": "SXM",
        "vram_gib": 80.0,
        "memory_type": "HBM3",
        "compute_capability": 9.0,
        "cc_name": "NVIDIA H100",
        "interconnect": "NVLink",
        "source_url": "https://www.nvidia.com/en-us/data-center/h100/",
        "markers": ["GPU Memory 80GB", "HBM3", "NVLink"],
    },
    {
        "id": "h100-nvl-94",
        "vendor": "nvidia",
        "ecosystem": "cuda",
        "name": "NVIDIA H100 NVL 94GB",
        "architecture": "Hopper",
        "form_factor": "PCIe 双卡 NVLink 桥",
        "vram_gib": 94.0,
        "memory_type": "HBM3",
        "compute_capability": 9.0,
        "cc_name": "NVIDIA H100",
        "interconnect": "NVLink",
        "source_url": "https://www.nvidia.com/en-us/data-center/h100/",
        "markers": ["GPU Memory 80GB 94GB", "188GB HBM3 memory", "NVLink bridge"],
        "vram_basis": ("官方页规格表同一行给出 H100 SXM 80GB 与 H100 NVL 94GB,故 NVL 单卡为 94GB;"
                       "正文另述 NVLink 桥接双卡合计 188GB HBM3,即 2 x 94GB。"),
    },
    {
        "id": "h200-sxm-141",
        "vendor": "nvidia",
        "ecosystem": "cuda",
        "name": "NVIDIA H200 SXM 141GB",
        "architecture": "Hopper",
        "form_factor": "SXM",
        "vram_gib": 141.0,
        "memory_type": "HBM3e",
        "compute_capability": 9.0,
        "cc_name": "NVIDIA H200",
        "interconnect": "NVLink",
        "source_url": "https://www.nvidia.com/en-us/data-center/h200/",
        "markers": ["GPU Memory 141GB", "HBM3e", "NVLink"],
    },
    {
        "id": "b200-180",
        "vendor": "nvidia",
        "ecosystem": "cuda",
        "name": "NVIDIA B200 180GB",
        "architecture": "Blackwell",
        "form_factor": "SXM",
        "vram_gib": 180.0,
        "memory_type": "HBM3e",
        "compute_capability": 10.0,
        "cc_name": "NVIDIA B200",
        "interconnect": "NVLink",
        "source_url": "https://www.nvidia.com/en-us/data-center/dgx-b200/",
        "markers": ["1,440 GB total", "HBM3e", "NVLink"],
        "vram_basis": "DGX B200 8 卡整机 1,440 GB HBM3e 总显存 ÷ 8 卡,官方页给的是整机值",
    },
    {
        "id": "l40s-48",
        "vendor": "nvidia",
        "ecosystem": "cuda",
        "name": "NVIDIA L40S 48GB",
        "architecture": "Ada Lovelace",
        "form_factor": "PCIe 双槽",
        "vram_gib": 48.0,
        "memory_type": "GDDR6 ECC",
        "compute_capability": 8.9,
        "cc_name": "NVIDIA L40S",
        "interconnect": "PCIe",
        "source_url": "https://www.nvidia.com/en-us/data-center/l40s/",
        "markers": ["GPU Memory 48GB GDDR6 with ECC", "PCIe Gen4 x16"],
    },
    {
        "id": "l4-24",
        "vendor": "nvidia",
        "ecosystem": "cuda",
        "name": "NVIDIA L4 24GB",
        "architecture": "Ada Lovelace",
        "form_factor": "PCIe 单槽半高",
        "vram_gib": 24.0,
        "memory_type": "GDDR6",
        "compute_capability": 8.9,
        "cc_name": "NVIDIA L4",
        "interconnect": "PCIe",
        "source_url": "https://www.nvidia.com/en-us/data-center/l4/",
        "markers": ["GPU memory 24GB", "PCIe Gen4 x16"],
    },
    {
        "id": "a40-48",
        "vendor": "nvidia",
        "ecosystem": "cuda",
        "name": "NVIDIA A40 48GB",
        "architecture": "Ampere",
        "form_factor": "PCIe 双槽",
        "vram_gib": 48.0,
        "memory_type": "GDDR6 ECC",
        "compute_capability": 8.6,
        "cc_name": "NVIDIA A40",
        "interconnect": "NVLink",
        "source_url": "https://www.nvidia.com/en-us/data-center/a40/",
        "markers": ["GPU Memory 48 GB GDDR6", "NVLink 112.5 GB/s"],
    },
    {
        "id": "a100-sxm-80",
        "vendor": "nvidia",
        "ecosystem": "cuda",
        "name": "NVIDIA A100 SXM 80GB",
        "architecture": "Ampere",
        "form_factor": "SXM",
        "vram_gib": 80.0,
        "memory_type": "HBM2e",
        "compute_capability": 8.0,
        "cc_name": "NVIDIA A100",
        "interconnect": "NVLink",
        "source_url": "https://www.nvidia.com/en-us/data-center/a100/",
        "markers": ["GPU Memory 80GB HBM2e", "NVLink"],
    },
    {
        "id": "a100-pcie-80",
        "vendor": "nvidia",
        "ecosystem": "cuda",
        "name": "NVIDIA A100 PCIe 80GB",
        "architecture": "Ampere",
        "form_factor": "PCIe 双槽",
        "vram_gib": 80.0,
        "memory_type": "HBM2e",
        "compute_capability": 8.0,
        "cc_name": "NVIDIA A100",
        "interconnect": "PCIe",
        "source_url": "https://www.nvidia.com/en-us/data-center/a100/",
        "markers": ["GPU Memory 80GB HBM2e", "PCIe Gen4"],
    },
    {
        "id": "rtx-6000-ada-48",
        "vendor": "nvidia",
        "ecosystem": "cuda",
        "name": "NVIDIA RTX 6000 Ada 48GB",
        "architecture": "Ada Lovelace",
        "form_factor": "PCIe 双槽",
        "vram_gib": 48.0,
        "memory_type": "GDDR6 ECC",
        "compute_capability": 8.9,
        "cc_name": "NVIDIA RTX 6000 Ada",
        "interconnect": "PCIe",
        "source_url": "https://www.nvidia.com/en-us/design-visualization/rtx-6000/",
        "markers": ["GPU Memory 48GB GDDR6 with error-correcting code"],
    },
    {
        "id": "rtx-4090-24",
        "vendor": "nvidia",
        "ecosystem": "cuda",
        "name": "NVIDIA GeForce RTX 4090 24GB",
        "architecture": "Ada Lovelace",
        "form_factor": "PCIe 三槽",
        "vram_gib": 24.0,
        "memory_type": "GDDR6X",
        "compute_capability": 8.9,
        "cc_name": "GeForce RTX 4090",
        "interconnect": "PCIe",
        "source_url": "https://www.nvidia.com/en-us/geforce/graphics-cards/40-series/rtx-4090/",
        "markers": ["Standard Memory Config 24 GB GDDR6X"],
    },
    {
        "id": "rtx-5090-32",
        "vendor": "nvidia",
        "ecosystem": "cuda",
        "name": "NVIDIA GeForce RTX 5090 32GB",
        "architecture": "Blackwell",
        "form_factor": "PCIe 三槽",
        "vram_gib": 32.0,
        "memory_type": "GDDR7",
        "compute_capability": 12.0,
        "cc_name": "GeForce RTX 5090",
        "interconnect": "PCIe",
        "source_url": "https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/",
        "markers": ["Standard Memory Config 32 GB GDDR7"],
    },

    # ---- 华为昇腾(CANN 生态)-----------------------------------------------
    #
    # 昇腾没有 CUDA 算力等级(sm_xx 是 NVIDIA 专有标度),所以 compute_capability
    # 留空并写明口径,不做 sm 映射;可用性由芯片型号 + CANN/驱动版本决定。
    # 厂商页没写的字段(如 300I Duo 的芯片型号)同样留空,不填记忆值。
    {
        "id": "ascend-950pr-atlas350",
        "name": "华为 Atlas 350 加速卡(Ascend 950PR)",
        "vendor": "huawei",
        "ecosystem": "cann",
        "architecture": "Ascend 950PR",
        "form_factor": "PCIe 标卡(扩高全长双宽)",
        "vram_gib": 112.0,
        "memory_type": "HBM",
        "compute_capability": None,
        "compute_capability_basis": ("昇腾不使用 CUDA 算力等级(sm_xx 是 NVIDIA 专有标度),"
                                     "该卡能力由芯片型号与 CANN 版本决定,故不做 sm 映射"),
        "interconnect": "灵衢(卡间互联)",
        "fp8_supported": True,
        "fp8_basis": "官方页标注支持 HiF8/mxFP8/mxFP4 数据格式",
        "source_url": "https://www.hiascend.com/hardware/accelerator-card",
        "markers": ["112 GB HBM", "PCIe 5.0 x16", "灵衢连接器实现多卡互联"],
    },
    {
        "id": "ascend-300i-duo-96",
        "name": "华为 Atlas 300I Duo 推理卡 96GB",
        "vendor": "huawei",
        "ecosystem": "cann",
        "architecture": None,
        "architecture_basis": "官方产品页只写卡型号,未标注芯片型号,故留空",
        "form_factor": "PCIe 标卡(集成于服务器)",
        "vram_gib": 96.0,
        "memory_type": "LPDDR4X",
        "compute_capability": None,
        "compute_capability_basis": ("昇腾不使用 CUDA 算力等级(sm_xx 是 NVIDIA 专有标度),"
                                     "该卡能力由芯片型号与 CANN 版本决定,故不做 sm 映射"),
        "interconnect": "PCIe",
        "fp8_supported": False,
        "fp8_basis": "官方页未标注 FP8/HiF8 支持",
        "source_url": "https://e.huawei.com/cn/products/computing/ascend/atlas-300i-duo",
        "markers": ["LPDDR4X 96GB或48GB", "280 TOPS INT8", "408GB/s"],
        "vram_basis": ("官方页把两种出货配置写在同一行:内存规格 LPDDR4X 96GB或48GB。"
                       "本条目对应 96GB 配置,48GB 配置另列一条,两个容量并存不合并。"),
    },
    {
        "id": "ascend-300i-duo-48",
        "name": "华为 Atlas 300I Duo 推理卡 48GB",
        "vendor": "huawei",
        "ecosystem": "cann",
        "architecture": None,
        "architecture_basis": "官方产品页只写卡型号,未标注芯片型号,故留空",
        "form_factor": "PCIe 标卡(集成于服务器)",
        "vram_gib": 48.0,
        "memory_type": "LPDDR4X",
        "compute_capability": None,
        "compute_capability_basis": ("昇腾不使用 CUDA 算力等级(sm_xx 是 NVIDIA 专有标度),"
                                     "该卡能力由芯片型号与 CANN 版本决定,故不做 sm 映射"),
        "interconnect": "PCIe",
        "fp8_supported": False,
        "fp8_basis": "官方页未标注 FP8/HiF8 支持",
        "source_url": "https://e.huawei.com/cn/products/computing/ascend/atlas-300i-duo",
        "markers": ["LPDDR4X 96GB或48GB", "280 TOPS INT8", "408GB/s"],
        "vram_basis": ("官方页把两种出货配置写在同一行:内存规格 LPDDR4X 96GB或48GB。"
                       "本条目对应 48GB 配置,96GB 配置另列一条,两个容量并存不合并。"),
    },
]


def utc_now():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def compact(value):
    """去掉所有空白后再比,避免页面上 "48 GB" 与记录里 "48GB" 的排版差异造成误判。"""
    return re.sub(r"\s+", "", value or "")


def page_text(raw_html):
    text = raw_html.decode("utf-8", "replace")
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def is_certificate_error(error):
    """判断是不是「本机证书链验不过」,而不是页面不存在之类的错误。"""
    reason = getattr(error, "reason", error)
    text = "%s: %s" % (type(reason).__name__, reason)
    return "CERTIFICATE_VERIFY_FAILED" in text or "SSLCertVerificationError" in text


def fetch_once(url, timeout):
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def fetch(url, timeout=30, retries=3):
    """取页面,返回 (状态码, 正文, 传输方式)。

    先按原 URL 走 https,证书校验照常开启。只有 https 因**本机证书链验不过**时
    才回落到同主机的官方 http 入口——这不是关掉校验,而是改用官方同样提供、且
    不涉及 TLS 的入口。回落事实会随 transport 字段写进快照,不静默发生。
    非证书类错误(404、超时等)一律不回落,免得把「页面没了」伪装成成功。
    """
    last = ""
    for attempt in range(1, retries + 1):
        try:
            status, raw = fetch_once(url, timeout)
            return status, raw, "https"
        except urllib.error.HTTPError as error:
            last = "HTTP %s %s" % (error.code, error.reason)
            if error.code in (400, 401, 403, 404):
                break
        except Exception as error:  # noqa: BLE001
            last = "%s: %s" % (type(error).__name__, error)
            if is_certificate_error(error) and url.startswith("https://"):
                plain = "http://" + url[len("https://"):]
                try:
                    status, raw = fetch_once(plain, timeout)
                    return status, raw, "http(https 证书本机验不过,按官方 http 入口取)"
                except Exception as fallback_error:  # noqa: BLE001
                    last = "%s: %s" % (type(fallback_error).__name__, fallback_error)
        if attempt < retries:
            import time
            time.sleep(2 * attempt)
    raise RuntimeError("取页面失败 (%s): %s" % (last, url))


def parse_cc_table(raw_html):
    """解析官方算力表 -> {算力: {名字}}。"""
    text = raw_html.decode("utf-8", "replace")
    if "<table" not in text:
        raise RuntimeError("官方算力表页面里找不到 <table>")
    body = text.split("<table", 1)[1].split("</table>", 1)[0]
    table = {}
    for row in re.findall(r"(?s)<tr.*?</tr>", body):
        cells = re.findall(r"(?s)<t[dh][^>]*>(.*?)</t[dh]>", row)
        if len(cells) < 2:
            continue

        def names(cell):
            cell = re.sub(r"(?i)<br\s*/?>", "\n", cell)
            cell = re.sub(r"(?s)<[^>]+>", "", cell)
            return [re.sub(r"\s+", " ", item).strip()
                    for item in html.unescape(cell).split("\n") if item.strip()]

        head = names(cells[0])
        if not head or not re.fullmatch(r"\d+\.\d+", head[0]):
            continue
        collected = set()
        for cell in cells[1:]:
            collected.update(names(cell))
        table.setdefault(head[0], set()).update(collected)
    if not table:
        raise RuntimeError("官方算力表没有解析出任何行")
    return table


def verify(previous):
    """返回 (快照, 失败清单)。

    两条核实路径,按厂商分开:

    - NVIDIA:显存/类型/互联逐字命中厂商产品页正文,且算力必须出现在 NVIDIA 官方
      CUDA-Enabled GPUs 算力表对应档位里。
    - 华为昇腾:显存/类型/互联逐字命中华为官方产品页正文。**不去 NVIDIA 算力表里
      找**——昇腾没有 sm_xx,拿 NVIDIA 标度去套是伪核实;芯片厂商页没写的字段
      (如 300I Duo 的芯片型号)一律留空,不填记忆值。
    """
    checked_at = utc_now()
    cc_status, cc_raw, cc_transport = fetch(CC_URL)
    cc_table = parse_cc_table(cc_raw)
    cc_record = {
        "url": CC_URL,
        "http_status": cc_status,
        "sha256": hashlib.sha256(cc_raw).hexdigest(),
        "levels": sorted(cc_table, key=lambda item: float(item)),
        "verified_at": checked_at,
        "transport": cc_transport,
        "note": ("算力取自 NVIDIA 官方 CUDA-Enabled GPUs 表,该表把同架构各型号归并到"
                 "同一档;**只用于 NVIDIA 卡**,昇腾等非 CUDA 生态不做 sm 映射。"),
    }

    cache = {}
    for page in sorted({gpu["source_url"] for gpu in GPUS}):
        status, raw, transport = fetch(page)
        cache[page] = (status, page_text(raw), hashlib.sha256(raw).hexdigest(), transport)

    entries, failures = [], []
    for gpu in GPUS:
        vendor = gpu.get("vendor", "nvidia")
        status, text, digest, transport = cache[gpu["source_url"]]
        missing = [marker for marker in gpu["markers"] if compact(marker) not in compact(text)]
        problems = []
        if missing:
            problems.append("产品页上没有出现:%s" % "、".join(missing))

        cc_checked = vendor == "nvidia"
        if cc_checked:
            level = str(gpu["compute_capability"])
            listed = cc_table.get(level) or set()
            if gpu["cc_name"] not in listed:
                problems.append("官方算力表 %s 档里没有 %s" % (level, gpu["cc_name"]))

        entry = dict(gpu)
        if vendor == "nvidia":
            entry["fp8_supported"] = gpu["compute_capability"] >= 8.9
            entry["fp8_basis"] = "由算力推导(sm_89 及以上才有 FP8),不是厂商页标称值"
        else:
            # 昇腾不能由算力推导,只能用厂商页写明的值;缺了就报错,不猜。
            if "fp8_supported" not in gpu or not gpu.get("fp8_basis"):
                problems.append("非 CUDA 生态必须写明 fp8_supported / fp8_basis")
        entry["verification"] = {
            "status": "ok" if not problems else "failed",
            "http_status": status,
            "sha256": digest,
            "checked_at": checked_at,
            "cc_checked": cc_checked,
            "transport": transport,
            "failures": problems,
        }
        entries.append(entry)
        if problems:
            failures.append((gpu["id"], problems))

    ids = [gpu["id"] for gpu in GPUS]
    names = [gpu["name"] for gpu in GPUS]
    if len(set(ids)) != len(ids):
        raise RuntimeError("GPU id 有重复")
    if len(set(names)) != len(names):
        raise RuntimeError("GPU 名称有重复")

    snapshot = {
        "schema": 1,
        "generated_at": checked_at,
        "cc_source": cc_record,
        "source_policy": ("每张卡的显存容量/类型/互联都在**自家厂商产品页正文里逐字命中**;"
                          "NVIDIA 卡另外要求算力命中 NVIDIA 官方算力表对应档位,"
                          "华为昇腾卡不去套 NVIDIA 算力表。任一条不满足就标 failed 并列出原因;"
                          "厂商页没写的字段留空,绝不填记忆值。"),
        "gpu_count": len(entries),
        "verified_count": sum(1 for item in entries if item["verification"]["status"] == "ok"),
        "gpus": entries,
    }
    return snapshot, failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="核实 GPU 规格并生成 GPU 目录")
    parser.add_argument("--check", action="store_true", help="只核实,不写文件")
    parser.add_argument("--offline", action="store_true",
                        help="不联网,沿用上次快照里的核实结果,只重建结构")
    args = parser.parse_args(argv)

    if args.offline:
        if not OUT.is_file():
            raise SystemExit("离线模式需要已有 %s" % OUT)
        snapshot = json.loads(OUT.read_text(encoding="utf-8"))
        print("离线模式:沿用 %s 中 %d 张卡的核实结果(未重新联网)"
              % (OUT.name, snapshot.get("verified_count", 0)))
        return 0

    try:
        snapshot, failures = verify(None)
    except Exception as error:  # noqa: BLE001
        print("核实失败:%s" % error, file=sys.stderr)
        return 2

    print("核实 %d 张卡,通过 %d 张,失败 %d 张"
          % (snapshot["gpu_count"], snapshot["verified_count"], len(failures)))
    for gpu_id, problems in failures:
        print("  FAIL %-20s %s" % (gpu_id, "; ".join(problems)))
    if not failures:
        by_level, cann = {}, []
        for item in snapshot["gpus"]:
            if item.get("vendor") == "nvidia":
                by_level.setdefault(item["compute_capability"], []).append(item["id"])
            else:
                cann.append("%s(%g GiB)" % (item["id"], item["vram_gib"]))
        for level in sorted(by_level, reverse=True):
            print("  sm_%-6s %s" % (str(level).replace(".", ""), ", ".join(by_level[level])))
        if cann:
            print("  %-9s %s" % ("cann", ", ".join(cann)))

    if args.check:
        print("--check:未写入文件")
        return 1 if failures else 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("写入 %s" % OUT)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

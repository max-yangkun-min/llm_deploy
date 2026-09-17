#!/usr/bin/env bash
set -euo pipefail

output="${1:-hardware.json}"
if ! command -v nvidia-smi >/dev/null; then
    # 昇腾机器没有 nvidia-smi,这里如实指路,不去猜 npu-smi 的输出格式。
    if command -v npu-smi >/dev/null; then
        {
            echo "本机是昇腾(NPU)环境:本脚本只采集 NVIDIA 卡(nvidia-smi)。"
            echo "昇腾请走部署台账的「现场登记」路径提交硬件,并在 JSON 里写明:"
            echo "  ecosystem=cann,不填 compute_capability(昇腾没有 sm 号),"
            echo "  vram_per_gpu_gib 按厂商产品页的显存容量填写。"
            echo "对照条目见 deploy-portal/data/gpu-catalog.json 里的 ascend-* 条目。"
        } >&2
        exit 2
    fi
    echo "未找到 nvidia-smi(也没有 npu-smi)。" >&2
    exit 1
fi

mapfile -t rows < <(nvidia-smi --query-gpu=name,memory.total,compute_cap,driver_version --format=csv,noheader,nounits)
((${#rows[@]} > 0)) || { echo "未检测到GPU" >&2; exit 1; }

IFS=',' read -r gpu_name memory_mib compute_cap driver_version <<<"${rows[0]}"
trim() { local x="$1"; x="${x#"${x%%[![:space:]]*}"}"; x="${x%"${x##*[![:space:]]}"}"; printf '%s' "$x"; }
gpu_name="$(trim "$gpu_name")"
memory_mib="$(trim "$memory_mib")"
compute_cap="$(trim "$compute_cap")"
driver_version="$(trim "$driver_version")"
vram_gib=$(( (memory_mib + 1023) / 1024 ))
ram_gib=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)
disk_gib=$(df -BG . | awk 'NR==2 {gsub(/G/,"",$4); print $4}')

python3 - "$output" "$gpu_name" "${#rows[@]}" "$vram_gib" "$compute_cap" "$driver_version" "$ram_gib" "$disk_gib" <<'PY'
import json, sys
out, name, count, vram, cc, driver, ram, disk = sys.argv[1:]
data = {
    "gpu_name": name,
    "gpu_count": int(count),
    "vram_per_gpu_gib": int(vram),
    "compute_capability": float(cc),
    "driver_version": driver,
    "host_ram_gib": int(ram),
    "disk_free_gib": int(disk),
    "interconnect": "UNKNOWN - 请用 nvidia-smi topo -m 补充",
    "nodes": 1,
    "workload": "coding,agent",
    "require_multimodal": False,
    "require_permissive_license": False,
    "min_context_k": 32,
}
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(json.dumps(data, ensure_ascii=False, indent=2))
PY

echo "已写入 $output；请核对 interconnect、nodes、workload、上下文和磁盘字段。"

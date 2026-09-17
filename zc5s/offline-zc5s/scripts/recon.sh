#!/usr/bin/env bash
# ============================================================================
# zc5s 现场核对(只读)· 单机 8×4090 · 银河麒麟 V10
# 用法:  bash recon.sh   →  带出 recon-report.txt
# ============================================================================
OUT="recon-report.txt"
exec > >(tee "${OUT}") 2>&1
line(){ echo; echo "===== $* ====="; }
have(){ command -v "$1" >/dev/null 2>&1; }

echo "zc5s 核对报告  ($(hostname 2>/dev/null))  ($(date 2>/dev/null))"

line "A1 OS / 架构 (麒麟 V10;应 x86_64)"
cat /etc/os-release 2>/dev/null | grep -E '^(NAME|VERSION|ID|VERSION_ID)='; uname -m; uname -r
line "A2 ★包管理器 (决定 system/ 备 deb 还是 rpm;也判断容器栈能否装)"
have dpkg && echo "有 dpkg(deb 系)"; have rpm && echo "有 rpm(rpm 系)"; have apt && echo "有 apt"; have dnf && echo "有 dnf"; have yum && echo "有 yum"

line "B1 GPU (应 8×RTX4090 48G;CUDA 12.9镜像要求驱动>=575.51.03;Ada sm_89)"
have nvidia-smi && nvidia-smi || echo "!! 无 nvidia-smi —— 驱动/CUDA 是麒麟第一道关"
line "B2 卡清单"; have nvidia-smi && nvidia-smi -L
line "B3 ★PCIe 拓扑 (4090无NVLink,只PCIe;看是否同root/跨NUMA,定TP组)"
have nvidia-smi && nvidia-smi topo -m
line "B4 驱动/显存/CUDA"
have nvidia-smi && nvidia-smi --query-gpu=driver_version,memory.total --format=csv
have nvcc && nvcc --version | grep release || echo "(无独立 nvcc,容器自带)"

line "C1 ★容器栈能否用 (麒麟上 docker+nvidia runtime 常装不上→走裸机pip备案C)"
have docker && docker version 2>/dev/null | grep -E 'Version' || echo "!! 无 docker"
have docker && (docker info 2>/dev/null | grep -i nvidia || echo "!! 无 nvidia runtime")
echo "判断:docker + nvidia runtime 都在 → 走容器(install-offline.sh);"
echo "      装不上/装不了 → 走裸机 pip(install-baremetal.sh,需 system/wheels/)"

line "D1 磁盘 (仅M2.7 AWQ，当前权重约121GiB；另留缓存和日志余量，放SSD)"
df -h | grep -vE 'tmpfs|overlay|udev'
line "D2 内存"; free -g 2>/dev/null || free -h
line "D3 CPU/NUMA"; nproc; lscpu 2>/dev/null | grep -E 'Socket|NUMA'

line "E1 供电/散热 (8×4090满载≈3.6-4kW,常需双电源;确认PSU+配电+风道)"
have nvidia-smi && nvidia-smi --query-gpu=power.limit,power.draw,temperature.gpu --format=csv

line "F1 是否真离线"
timeout 5 curl -sI https://huggingface.co >/dev/null 2>&1 && echo "能出网" || echo "出不了网 → 离线包"

echo; echo "===== 完成,带出 ${OUT}。重点:A2包管理器 / B1驱动>=575.51.03 / C1容器能否用 ====="

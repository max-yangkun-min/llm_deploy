#!/usr/bin/env bash
# ============================================================================
# xt 现场核对(只读)。★ 两台机器【都要】各跑一遍,各带出 recon-report.txt。
# 用法:  bash recon.sh
# ============================================================================
OUT="recon-report-$(hostname 2>/dev/null || echo host).txt"
exec > >(tee "${OUT}") 2>&1
line(){ echo; echo "===== $* ====="; }
have(){ command -v "$1" >/dev/null 2>&1; }

echo "xt 离线机核对报告  ($(hostname 2>/dev/null))  ($(date 2>/dev/null))"

line "A1 发行版/架构 (deb/rpm 与镜像架构;应 x86_64)"
cat /etc/os-release 2>/dev/null | grep -E '^(NAME|VERSION|ID|VERSION_ID|VERSION_CODENAME)='; uname -m

line "B1 GPU概览(7+7应各7张;备用8+6应分别8/6张A40 48GB / cu129 Forward Compatibility驱动>=545 / sm_86)"
have nvidia-smi && nvidia-smi || echo "!! 无 nvidia-smi,驱动没装"
line "B2 卡清单"
have nvidia-smi && nvidia-smi -L
line "B3 ★拓扑 topo -m (A40 只有2-way桥;TP组挑同根桥的卡,避开 PHB/NODE/SYS)"
have nvidia-smi && nvidia-smi topo -m
line "B4 驱动/显存/ECC"
have nvidia-smi && nvidia-smi --query-gpu=driver_version,memory.total,ecc.mode.current --format=csv
if have nvidia-smi; then
  driver="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n1 | tr -d '[:space:]')"
  if [ "$(printf '%s\n%s\n' "545.0" "${driver}" | sort -V | head -n1)" = "545.0" ]; then
    echo "PASS:驱动${driver}满足Forward Compatibility策略下限545.0"
    if [ "$(printf '%s\n%s\n' "575.51.03" "${driver}" | sort -V | head -n1)" = "575.51.03" ]; then
      echo "PASS:驱动达到CUDA 12.9原生基线575.51.03"
    else
      echo "INFO:驱动低于575.51.03,必须由镜像内cuda-compat-12-9提供PTX JIT兼容"
    fi
  else
    echo "!! 驱动${driver}<545.0,不进入本方案"
  fi
fi
line "B5 备用8+6硬件门槛 (8卡机须确认槽位/8-pin供电/PSU/风道/Above 4G Decoding)"
have lspci && echo "PCIe NVIDIA设备数: $(lspci -nn | grep -ic nvidia || true)" || true

line "C1 ★万兆网卡接口名 (PP 跨机必须锁它 NCCL_SOCKET_IFNAME;填进 run.sh 的 NIC)"
ip -br addr 2>/dev/null || ip addr
line "C2 到对端机器连通/带宽 (换成对端IP;PP 走这条链路)"
echo "手动: ping <对端IP> ; iperf3 若装了可测带宽"

line "D1 容器栈 (docker + nvidia runtime;两台都要有,镜像两台都要 load)"
have docker && docker version 2>/dev/null | grep -E 'Version|API' || echo "!! 无 docker,需备 system/docker/"
have docker && (docker info 2>/dev/null | grep -i nvidia || echo "!! 无 nvidia runtime,需备 nvidia-container-toolkit")
echo "安装镜像后执行:IMAGE=xt-vllm:0.24.0-cu129-compat545 ./verify-cu129-compat.sh"

line "E1 磁盘 (权重放 SSD:M2.7~115G / 397B~200G / K2.6~500G,按要部署的方案备够)"
df -h | grep -vE 'tmpfs|overlay|udev'
line "E2 内存 (512G;加载大权重期需要)"
free -g 2>/dev/null || free -h
line "E3 CPU/NUMA"
nproc; lscpu 2>/dev/null | grep -E 'Socket|NUMA node\(s\)'

line "F1 配电/散热提醒 (7卡约2.5-3kW/台;8卡机接近3kW以上;确认 PSU/线束/风道+机柜配电)"
have nvidia-smi && nvidia-smi --query-gpu=power.limit,power.draw,temperature.gpu --format=csv

line "G1 是否真离线"
timeout 5 curl -sI https://huggingface.co >/dev/null 2>&1 && echo "能出网" || echo "出不了网 → 离线包"

echo; echo "===== 完成,把 ${OUT} 带出来(两台各一份)====="

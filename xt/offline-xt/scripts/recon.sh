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

line "B1 GPU 概览 (应 7×A40 48GB / 驱动>=535 / sm_86)"
have nvidia-smi && nvidia-smi || echo "!! 无 nvidia-smi,驱动没装"
line "B2 卡清单"
have nvidia-smi && nvidia-smi -L
line "B3 ★拓扑 topo -m (A40 只有2-way桥;TP组挑同根桥的卡,避开 PHB/NODE/SYS)"
have nvidia-smi && nvidia-smi topo -m
line "B4 驱动/显存/ECC"
have nvidia-smi && nvidia-smi --query-gpu=driver_version,memory.total,ecc.mode.current --format=csv

line "C1 ★万兆网卡接口名 (PP 跨机必须锁它 NCCL_SOCKET_IFNAME;填进 run.sh 的 NIC)"
ip -br addr 2>/dev/null || ip addr
line "C2 到对端机器连通/带宽 (换成对端IP;PP 走这条链路)"
echo "手动: ping <对端IP> ; iperf3 若装了可测带宽"

line "D1 容器栈 (docker + nvidia runtime;两台都要有,镜像两台都要 load)"
have docker && docker version 2>/dev/null | grep -E 'Version|API' || echo "!! 无 docker,需备 system/docker/"
have docker && (docker info 2>/dev/null | grep -i nvidia || echo "!! 无 nvidia runtime,需备 nvidia-container-toolkit")

line "E1 磁盘 (权重放 SSD:M2.7~115G / 397B~200G / K2.6~500G,按要部署的方案备够)"
df -h | grep -vE 'tmpfs|overlay|udev'
line "E2 内存 (512G;加载大权重期需要)"
free -g 2>/dev/null || free -h
line "E3 CPU/NUMA"
nproc; lscpu 2>/dev/null | grep -E 'Socket|NUMA node\(s\)'

line "F1 配电/散热提醒 (7×A40 满载≈2.5-3kW/台,PP方案两台都满载;确认 PSU 冗余+机柜配电)"
have nvidia-smi && nvidia-smi --query-gpu=power.limit,power.draw,temperature.gpu --format=csv

line "G1 是否真离线"
timeout 5 curl -sI https://huggingface.co >/dev/null 2>&1 && echo "能出网" || echo "出不了网 → 离线包"

echo; echo "===== 完成,把 ${OUT} 带出来(两台各一份)====="

#!/usr/bin/env bash
# ============================================================================
# 离线机现场核对(只读,不改任何东西)。跑一遍,把 recon-report.txt 带出来。
# 用法:  bash recon.sh    (无 root 也能跑大部分;装东西才需要 root)
# ============================================================================
OUT="recon-report.txt"
exec > >(tee "${OUT}") 2>&1
line(){ echo; echo "===== $* ====="; }
have(){ command -v "$1" >/dev/null 2>&1; }

echo "GLM-5.2 离线机核对报告  ($(date 2>/dev/null))"

# ── A. 系统身份:决定 toolkit 用 deb/rpm、镜像架构是否匹配 ──
line "A1 发行版 (决定 toolkit deb/rpm)"
cat /etc/os-release 2>/dev/null | grep -E '^(NAME|VERSION|ID|VERSION_ID)=' || true
line "A2 架构 (必须 x86_64,否则镜像跑不了)"
uname -m
line "A3 内核"
uname -r

# ── B. GPU / 驱动:决定要不要备驱动;拓扑决定 PCIe 打几折 ──
line "B1 nvidia-smi 概览 (驱动>=550? 8卡? 80G? 右上CUDA Version?)"
if have nvidia-smi; then nvidia-smi; else echo "!! 没有 nvidia-smi —— 驱动可能没装,是大问题"; fi
line "B2 卡清单 (应 8×A100 80GB)"
have nvidia-smi && nvidia-smi -L || true
line "B3 ★拓扑 topo -m (最关键:NV=理想 / PIX/PXB=可上打折 / SYS=跨socket需挪卡)"
have nvidia-smi && nvidia-smi topo -m || true
line "B4 驱动/CUDA 版本号"
have nvidia-smi && nvidia-smi --query-gpu=driver_version,memory.total,ecc.mode.current --format=csv || true

# ── C. 容器栈:决定要不要备 Docker / toolkit ──
line "C1 Docker 在不在"
if have docker; then docker version 2>/dev/null | grep -E 'Version|API' ; else echo "!! 无 docker —— 需备 system/docker/"; fi
line "C2 nvidia runtime 在不在 (--gpus 靠它;最常缺)"
have docker && (docker info 2>/dev/null | grep -i -A2 -E 'runtimes|nvidia' || echo "!! docker info 里没看到 nvidia runtime —— 需备 nvidia-container-toolkit")
line "C3 nvidia-container-toolkit 版本"
have nvidia-ctk && nvidia-ctk --version || echo "(无 nvidia-ctk)"
line "C4 当前用户能否直接用 docker (在不在 docker 组)"
id | grep -q docker && echo "在 docker 组" || echo "不在 docker 组(需 sudo 或加组)"

# ── D. 资源:权重 410G 放得下吗、内存够加载吗 ──
line "D1 磁盘 (权重需 ≥500G 可用,记下打算放哪个挂载点)"
df -h | grep -vE 'tmpfs|overlay|udev' || true
line "D2 内存 (建议 ≥512G)"
free -g 2>/dev/null || free -h || true
line "D3 CPU"
nproc 2>/dev/null; echo "sockets:"; lscpu 2>/dev/null | grep -E 'Socket|NUMA node\(s\)' || true

# ── E. 确认"真离线"& 内网可达 ──
line "E1 是否真的不能出网 (超时=确认离线,通=其实能联网)"
timeout 5 curl -sI https://download.docker.com >/dev/null 2>&1 && echo "能出网(也许不用离线包?)" || echo "出不了网 → 确认离线"
line "E2 权限:有没有 sudo/root (装 docker/toolkit 要)"
[ "$(id -u)" = 0 ] && echo "当前是 root" || (sudo -n true 2>/dev/null && echo "有免密 sudo" || echo "需确认 sudo 权限")

# ── F. 已装的 CUDA toolkit(次要,容器自带,仅供参考)──
line "F1 系统 CUDA toolkit (仅参考,容器不依赖它)"
ls -d /usr/local/cuda* 2>/dev/null || echo "(无独立 toolkit,无所谓)"
have nvcc && nvcc --version | grep release || true

echo
echo "===== 核对完成,请把 ${OUT} 带出来 ====="

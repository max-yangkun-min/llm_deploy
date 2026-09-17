#!/usr/bin/env bash
# ============================================================================
# 离线机上运行:校验 + docker load 镜像。★ 两台机器都要跑一遍。
# 假定硬盘已拷到 /offline-xt。exFAT不保证执行位,统一用bash调用:
#   cd /offline-xt && bash scripts/install-offline.sh
# ============================================================================
set -euo pipefail
PKG="${PKG:-/offline-xt}"
IMAGE="${IMAGE:-xt-vllm:0.24.0-cu129-compat545}"
mapfile -t IMG_TARS < <(find "${PKG}/images" -maxdepth 1 -type f -name '*.tar' -print | sort)
chmod +x "${PKG}/scripts/"*.sh 2>/dev/null || true

echo "== 0. 自检 =="
nvidia-smi -L || { echo "!! 看不到 GPU/驱动,先装驱动"; exit 1; }
docker version >/dev/null 2>&1 || {
  echo "!! Docker不可用,先执行:sudo env PKG=${PKG} bash ${PKG}/scripts/install-system-deps.sh"
  exit 1
}
docker info 2>/dev/null | grep -qi nvidia || {
  echo "!! 无nvidia runtime,先执行:sudo env PKG=${PKG} bash ${PKG}/scripts/install-system-deps.sh"
  exit 1
}

echo "== 1. 校验完整性 =="
if [ -f "${PKG}/MANIFEST.sha256" ]; then
  ( cd "${PKG}" && sha256sum -c MANIFEST.sha256 ) || {
    echo "!! MANIFEST.sha256校验失败,拒绝加载镜像"
    exit 1
  }
else
  echo "!! 无MANIFEST.sha256,拒绝安装未校验的离线包"
  exit 1
fi

echo "== 2. docker load =="
[ "${#IMG_TARS[@]}" -gt 0 ] || { echo "!! images/ 下没有 tar"; exit 1; }
for tar in "${IMG_TARS[@]}"; do
  echo "   load ${tar}"
  docker load -i "${tar}"
done
docker images | grep -E 'xt-vllm' || true

echo "== 3. CUDA 12.9 Forward Compatibility + A40运行验收 =="
IMAGE="${IMAGE}" bash "${PKG}/scripts/verify-cu129-compat.sh"

echo
echo "== 完成(${IMAGE} 已通过cu129+cuda-compat-12-9验收)。改 scripts/run.sh 顶部(MODELS_DIR / NIC / HEAD_IP),按方案起: =="
echo "   方案三 M2.7:两台各 bash scripts/run.sh m2.7 ; 任一台 bash scripts/run.sh lb-nginx(统一入口:9000)"
echo "   方案二 397B:两台 RAY_GPU_DEVICES=0,1,2,3 启动Ray → A bash scripts/run.sh 397b"
echo "   方案一 K2.6:两台 RAY_GPU_DEVICES=0,1,2,3,4,5 启动Ray → A bash scripts/run.sh k2.6"
echo "   备用四 8+6:8卡机 bash scripts/run.sh 397b-8gpu ; 6卡机 bash scripts/run.sh m2.7"
echo "   详见 大模型部署方案对比-2x7xA40.md"

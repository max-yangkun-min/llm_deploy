#!/usr/bin/env bash
# ============================================================================
# zc5s 离线机(麒麟 V10)· 容器路径安装。假定硬盘拷到 /offline-zc5s。
# 若容器栈装不上 → 改用 ./scripts/install-baremetal.sh(裸机 pip 备案C)。
# 用法:  cd /offline-zc5s && ./scripts/install-offline.sh
# ============================================================================
set -euo pipefail
PKG="${PKG:-/offline-zc5s}"
IMG_TAR="$(ls "${PKG}"/images/*.tar 2>/dev/null | head -1 || true)"

echo "== 0. 自检 =="
nvidia-smi -L || { echo "!! 无 GPU/驱动 —— 麒麟第一道关,先解决驱动+CUDA"; exit 1; }
if ! docker version >/dev/null 2>&1; then
  echo "!! 无 Docker。麒麟上装 system/docker/(按 recon 的 deb/rpm);装不上就走裸机:"
  echo "   ./scripts/install-baremetal.sh"; exit 1; fi
if ! docker info 2>/dev/null | grep -qi nvidia; then
  echo "!! 无 nvidia runtime → 装 system/container-toolkit/ 后:"
  echo "   sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker"
  echo "   (麒麟上 toolkit 装不上 → 走裸机 install-baremetal.sh)"; exit 1; fi

echo "== 1. 校验 =="
[ -f "${PKG}/MANIFEST.sha256" ] && ( cd "${PKG}" && sha256sum -c MANIFEST.sha256 ) || echo "   (无 MANIFEST 或权重未全,跳过)"

echo "== 2. docker load =="
[ -n "${IMG_TAR}" ] || { echo "!! images/ 无 tar"; exit 1; }
docker load -i "${IMG_TAR}"; docker images | grep zc5s-vllm || true

echo
echo "== 完成。改 scripts/run.sh 顶部 MODELS_DIR,按选型起: =="
echo "   ./run.sh m2.7      # M2.7 INT4 双副本 + ./run.sh lb-nginx"
echo "   ./run.sh m2.7-fp8  # M2.7 FP8 单副本(质量)"
echo "   ./run.sh 397b      # Qwen3.5-397B"
echo "   详见 大模型选型方案-8x4090-48G.md"

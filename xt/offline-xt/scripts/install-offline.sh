#!/usr/bin/env bash
# ============================================================================
# 离线机上运行:校验 + docker load 镜像。★ 两台机器都要跑一遍。
# 假定硬盘已拷到 /offline-xt。用法: cd /offline-xt && ./scripts/install-offline.sh
# ============================================================================
set -euo pipefail
PKG="${PKG:-/offline-xt}"
IMG_TAR="$(ls "${PKG}"/images/*.tar 2>/dev/null | head -1 || true)"

echo "== 0. 自检 =="
nvidia-smi -L || { echo "!! 看不到 GPU/驱动,先装驱动"; exit 1; }
docker version >/dev/null 2>&1 || { echo "!! 无 Docker,先装 system/docker/"; exit 1; }
docker info 2>/dev/null | grep -qi nvidia || {
  echo "!! 无 nvidia runtime → 装 system/nvidia-container-toolkit/ 后:"
  echo "   sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker"; exit 1; }

echo "== 1. 校验完整性 =="
[ -f "${PKG}/MANIFEST.sha256" ] && ( cd "${PKG}" && sha256sum -c MANIFEST.sha256 ) \
  || echo "   (无 MANIFEST 或部分权重未下,跳过整体校验)"

echo "== 2. docker load =="
[ -n "${IMG_TAR}" ] || { echo "!! images/ 下没有 tar"; exit 1; }
docker load -i "${IMG_TAR}"
docker images | grep xt-vllm || true

echo
echo "== 完成。改 scripts/run.sh 顶部(MODELS_DIR / NIC / HEAD_IP),按方案起: =="
echo "   方案三 M2.7:两台各 ./run.sh m2.7 ; 网关 ./run.sh lb-nginx"
echo "   方案二 397B:A ./run.sh ray-head → B ./run.sh ray-worker → A ./run.sh 397b"
echo "   方案一 K2.6:同上,最后 ./run.sh k2.6"
echo "   详见 大模型部署方案对比-2x7xA40.md"

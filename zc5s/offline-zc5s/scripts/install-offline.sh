#!/usr/bin/env bash
# zc5s 银河麒麟 V10 · 单镜像/单模型离线安装
set -euo pipefail

PKG="${PKG:-/offline-zc5s}"
IMAGE="zc5s-vllm:0.24.0-cu129"
MIN_DRIVER="575.51.03"
IMG_TAR="${PKG}/images/zc5s-vllm-0.24.0-cu129.tar"
MODEL_SOURCE="${MODEL_SOURCE:-$(dirname "${PKG}")/offline-xt/models/MiniMax-M2.7-AWQ}"

version_ge() { test "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" = "$2"; }

echo "== 0. 宿主检查 =="
command -v nvidia-smi >/dev/null || { echo "!! 未找到 nvidia-smi"; exit 1; }
DRIVER="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n1 | tr -d ' ')"
version_ge "${DRIVER}" "${MIN_DRIVER}" || {
  echo "!! 当前驱动 ${DRIVER}，RTX 4090 + CUDA 12.9 镜像要求 >= ${MIN_DRIVER}"
  echo "!! GeForce 4090 不使用 cuda-compat 绕过驱动要求"; exit 1; }
test "$(nvidia-smi -L | grep -ci '4090')" -eq 8 || echo "!! GPU 未识别为 8×4090，请核对 recon 报告"
docker version >/dev/null 2>&1 || { echo "!! Docker 不可用"; exit 1; }
docker info 2>/dev/null | grep -qi nvidia || { echo "!! NVIDIA Container Toolkit/runtime 不可用"; exit 1; }

echo "== 1. 离线包检查 =="
test -f "${IMG_TAR}" || { echo "!! 缺少 ${IMG_TAR}"; exit 1; }
test -f "${MODEL_SOURCE}/config.json" || {
  echo "!! 共享 M2.7 路径不存在: ${MODEL_SOURCE}"
  echo "!! 若离线介质挂载位置不同，请设置 MODEL_SOURCE=/实际路径/MiniMax-M2.7-AWQ"; exit 1; }
SHARDS="$(find "${MODEL_SOURCE}" -maxdepth 1 -name 'model-*.safetensors' -type f | wc -l)"
test "${SHARDS}" -eq 44 || { echo "!! M2.7 权重应有44片，当前${SHARDS}片"; exit 1; }
if test -f "${PKG}/MANIFEST.sha256"; then
  (cd "${PKG}" && sha256sum -c MANIFEST.sha256)
else
  echo "!! 未提供 MANIFEST.sha256"; exit 1
fi

echo "== 2. 导入并检查镜像 =="
docker load -i "${IMG_TAR}"
docker image inspect "${IMAGE}" --format \
  'image={{.RepoTags}} min-driver={{index .Config.Labels "org.blade-agent.min-host-driver"}} cuda={{index .Config.Labels "org.blade-agent.cuda-runtime"}}'

echo "== 完成 =="
echo "共享模型: ${MODEL_SOURCE}"
echo "先运行: cd ${PKG}/scripts && ./run.sh verify"
echo "再设置 MODELS_DIR=$(dirname "${MODEL_SOURCE}") 后启动: ./run.sh m2.7 && ./run.sh lb-nginx"

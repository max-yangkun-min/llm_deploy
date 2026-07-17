#!/usr/bin/env bash
# ============================================================================
# 离线机上运行:加载镜像并做基本自检。假定硬盘已拷到 /offline-glm52。
# 权重不动(太大),部署时由 run.sh 挂载。
# 用法:
#   cd /offline-glm52 && ./scripts/install-offline.sh
# ============================================================================
set -euo pipefail

PKG="${PKG:-/offline-glm52}"
IMG_TAR="$(ls "${PKG}"/images/*.tar 2>/dev/null | head -1 || true)"

echo "== 0. 离线机现状自检 =="
nvidia-smi -L || { echo "!! 看不到 GPU/驱动,先解决驱动再继续"; exit 1; }
docker version >/dev/null 2>&1 || { echo "!! 无 Docker,先装 system/docker/"; exit 1; }
if ! docker info 2>/dev/null | grep -qi nvidia; then
  echo "!! 未检测到 nvidia container runtime。"
  echo "   装 system/nvidia-container-toolkit/ 后执行:"
  echo "     sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker"
  exit 1
fi

echo "== 1. 校验离线包完整性(强烈建议)=="
if [ -f "${PKG}/MANIFEST.sha256" ]; then
  ( cd "${PKG}" && sha256sum -c MANIFEST.sha256 ) \
    || { echo "!! 校验失败,拷贝可能损坏,别继续"; exit 1; }
else
  echo "   (无 MANIFEST.sha256,跳过——建议补上)"
fi

echo "== 2. docker load 镜像 =="
[ -n "${IMG_TAR}" ] || { echo "!! images/ 下没有 tar"; exit 1; }
docker load -i "${IMG_TAR}"
docker images | grep glm52-vllm || true

echo
echo "== 完成。下一步:=="
echo "  cd ${PKG}/scripts"
echo "  # 改 run.sh 顶部: MODEL_DIR=${PKG}/models/GLM-5.2-AWQ-INT4"
echo "  ./run.sh smoke    # 阶段1 先验 TP=8/NCCL(Qwen3-8B,验完 stop)"
echo "  ./run.sh stage3   # 阶段3 已验证 32K 基准(冷启动 ~7 分钟)"
echo "  ./run.sh logs     # 验证兜底两行 + 记 GPU KV cache size"
echo "  详见 GLM-5.2-部署步骤-8xA100.md"

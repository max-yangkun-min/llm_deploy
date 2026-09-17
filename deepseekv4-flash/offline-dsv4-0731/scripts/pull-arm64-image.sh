#!/usr/bin/env bash
#
# pull-arm64-image.sh — 在目标 ARM64 服务器上离线拉取并打包 vLLM Ascend ARM64 镜像
#
# 用途：当交付包内只有 amd64 镜像 tar 而目标机是 ARM64 时，在目标机上运行
#       此脚本从 DaoCloud 国内代理拉取固定的 ARM64 manifest，docker save
#       成 tar 并校验 SHA-256 与架构。
#
# 前提：目标机能访问 m.daocloud.io 且已安装 docker。
#
set -euo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
IMAGE_DIR="$ROOT_DIR/images"

# ── 固定引用（与 MODEL-SOURCE.md 一致）──────────────────────────
OCI_INDEX_DIGEST="sha256:ade04e75aa4a888df5dfb7917f21e7d9178014d5f5e52b358f2cd1d8897f46ce"
ARM64_MANIFEST_DIGEST="sha256:8dd01aa0e0e5c4b04d3d715f483351af24c626c30373215e74238cf389fc2a93"
REMOTE_IMAGE="m.daocloud.io/quay.io/ascend/vllm-ascend@${OCI_INDEX_DIGEST}"
LOCAL_TAG="deepseek-v4-flash/vllm-ascend:20260804-arm64"
TAR_NAME="vllm-ascend-nightly-main-20260804-arm64.tar"
TAR_PATH="$IMAGE_DIR/$TAR_NAME"

die() { echo "ERROR: $*" >&2; exit 1; }

require() { command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"; }

echo "=== ARM64 离线镜像拉取脚本 ==="
echo "目标架构: linux/arm64"
echo "远程镜像: $REMOTE_IMAGE"
echo "ARM64 manifest: $ARM64_MANIFEST_DIGEST"
echo "输出文件: $TAR_PATH"
echo ""

require docker
docker info >/dev/null 2>&1 || die "Docker daemon 不可用，请先启动 docker"

mkdir -p "$IMAGE_DIR"

# ── 1. 拉取固定 multi-arch index（docker 会自动选择当前平台 arm64）──
echo "[1/4] 拉取镜像..."
docker pull "$REMOTE_IMAGE"

# ── 2. 校验镜像架构 ──────────────────────────────────────────────
echo "[2/4] 校验架构..."
IMAGE_ID=$(docker image inspect "$REMOTE_IMAGE" --format '{{.Id}}')
ARCH=$(docker image inspect "$REMOTE_IMAGE" --format '{{.Architecture}}')
OS=$(docker image inspect "$REMOTE_IMAGE" --format '{{.Os}}')
echo "  镜像 ID: $IMAGE_ID"
echo "  架构:    $OS/$ARCH"

if [[ "$ARCH" != "arm64" ]]; then
  die "拉取到的镜像架构不是 arm64（实际: $ARCH）。目标机可能不是 ARM64，或 docker 未正确选择平台。"
fi
if [[ "$OS" != "linux" ]]; then
  die "拉取到的镜像 OS 不是 linux（实际: $OS）"
fi

# ── 3. 创建本地标签并 docker save ────────────────────────────────
echo "[3/4] 创建本地标签并导出 tar..."
docker image tag "$IMAGE_ID" "$LOCAL_TAG"

# 如果已存在旧 tar 则先删除
if [[ -f "$TAR_PATH" ]]; then
  echo "  已存在旧 tar，覆盖中..."
  rm -f "$TAR_PATH"
fi

docker save --output "$TAR_PATH" "$LOCAL_TAG"

# ── 4. 计算 SHA-256 并输出清单 ───────────────────────────────────
echo "[4/4] 计算 SHA-256..."
TAR_SIZE=$(stat -c%s "$TAR_PATH" 2>/dev/null || stat -f%z "$TAR_PATH")
TAR_SHA256=$(sha256sum "$TAR_PATH" | awk '{print $1}')

echo ""
echo "=== 完成 ==="
echo "文件: $TAR_PATH"
echo "大小: $TAR_SIZE bytes"
echo "SHA-256: $TAR_SHA256"
echo "本地标签: $LOCAL_TAG"
echo "镜像 ID: $IMAGE_ID"
echo ""
echo "请将以上 SHA-256 写入 PACKAGE-SHA256SUMS，并更新 README.md 和 start.sh"
echo "中的架构引用从 amd64 改为 arm64。"
echo ""
echo "验证命令："
echo "  docker load --input $TAR_PATH"
echo "  docker image inspect $IMAGE_ID --format '{{.Architecture}}'  # 应为 arm64"
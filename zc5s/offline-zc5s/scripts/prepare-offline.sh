#!/usr/bin/env bash
# zc5s 离线包制作：只构建镜像；模型复用同盘 offline-xt，不复制、不下载。
set -euo pipefail

OUT="${OUT:?请先 export OUT=硬盘挂载点}"
VLLM_TAG="${VLLM_TAG:-v0.24.0}"
IMAGE="zc5s-vllm:${VLLM_TAG#v}-cu129"
PKG="${OUT}/offline-zc5s"

mkdir -p "${PKG}"/{images,models,scripts} "${PKG}"/system/{container-toolkit,docker,driver}

step_build() {
  docker build -f "${DOCKERFILE:-Dockerfile}" \
    --build-arg VLLM_TAG="${VLLM_TAG}" \
    --build-arg VLLM_BASE_IMAGE="${VLLM_BASE_IMAGE:-vllm/vllm-openai:v0.24.0-cu129}" \
    -t "${IMAGE}" .
}

step_save() {
  local target="${PKG}/images/zc5s-vllm-${VLLM_TAG#v}-cu129.tar"
  docker save "${IMAGE}" -o "${target}"
  du -h "${target}"
}

step_scripts() {
  cp -f Dockerfile Dockerfile.cn run.sh recon.sh install-offline.sh prepare-offline.sh "${PKG}/scripts/"
  cp -rf lb "${PKG}/scripts/"
  cp -f ../README-安装.md ../下载清单-FILL-ME.md ../大模型选型方案-8x4090-48G.md "${PKG}/"
}

step_manifest() {
  (cd "${PKG}" && find . -type f ! -path './models/*/.cache/*' ! -name MANIFEST.sha256 -print0 \
    | sort -z | xargs -0 sha256sum > MANIFEST.sha256)
  echo "校验条目: $(wc -l < "${PKG}/MANIFEST.sha256")"
}

case "${1:-}" in
  build) step_build ;;
  save) step_save ;;
  scripts) step_scripts ;;
  manifest) step_scripts; step_manifest ;;
  all) step_build; step_save; step_scripts; step_manifest ;;
  *) echo "用法: $0 {build|save|scripts|manifest|all}"; exit 1 ;;
esac

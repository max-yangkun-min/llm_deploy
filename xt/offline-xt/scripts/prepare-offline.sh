#!/usr/bin/env bash
# ============================================================================
# 联网机上运行:备齐 xt 完整离线包(镜像 + 系统依赖 + 三个模型 + 校验和)
# 前提:x86_64 Linux + Docker + huggingface_hub[hf_transfer],硬盘已挂载。
#
# 正式交付固定准备三个模型。可一键 all,也可分段下载以便断点续做:
#   ① 非权重部分:
#        export OUT=/mnt/drive VLLM_TAG=v0.24.0 SYS_DISTRO=ubuntu
#        # VLLM_TAG 对应的官方镜像必须是 torch CUDA 12.4;构建会硬校验
#        ./prepare-offline.sh base
#   ② 三个权重全部执行:
#        ./prepare-offline.sh m2.7     # 方案三 ~115GB
#        ./prepare-offline.sh 397b     # 方案二 ~200GB
#        ./prepare-offline.sh k2.6     # 方案一 ~500GB
#        ./prepare-offline.sh manifest # 补校验和
#   或:  ./prepare-offline.sh all      # 从镜像到三模型一次完成
#
# 国内:export HF_ENDPOINT=https://hf-mirror.com ; 构建用 DOCKERFILE=Dockerfile.cn REGISTRY=...
# ============================================================================
set -euo pipefail
OUT="${OUT:?请先 export OUT=硬盘挂载点}"
VLLM_TAG="${VLLM_TAG:-v0.24.0}"
VLLM_BASE_IMAGE="${VLLM_BASE_IMAGE:-${REGISTRY:-}vllm/vllm-openai:${VLLM_TAG}}"
CUDA_COMPAT="${CUDA_COMPAT:-12.4}"
CUDA_PROFILE="cu124"
IMAGE="${IMAGE:-xt-vllm:${VLLM_TAG#v}-${CUDA_PROFILE}}"
NGINX_IMAGE="${NGINX_IMAGE:-nginx:stable}"
PKG="${OUT}/offline-xt"
SYS_DISTRO="${SYS_DISTRO:-ubuntu}"

# 三种权重仓库(都是 AWQ INT4;8+6备用复用397B+M2.7,无需新增权重)
M27_REPO="${M27_REPO:-QuantTrio/MiniMax-M2.7-AWQ}"
Q397_REPO="${Q397_REPO:-QuantTrio/Qwen3.5-397B-A17B-AWQ}"
K2_REPO="${K2_REPO:-<org>/Kimi-K2.6-AWQ}"

export HF_HUB_ENABLE_HF_TRANSFER=1
mkdir -p "${PKG}"/{images,models,scripts} \
         "${PKG}"/system/{docker,nvidia-container-toolkit,driver}

step_build() {
  [ "${CUDA_COMPAT}" = "12.4" ] || { echo "!! XT cu124档位只接受 CUDA_COMPAT=12.4"; exit 1; }
  echo "== 构建镜像 ${IMAGE}(base=${VLLM_BASE_IMAGE},要求torch CUDA=${CUDA_COMPAT})=="
  docker build -f "${DOCKERFILE:-Dockerfile}" \
    --build-arg VLLM_TAG="${VLLM_TAG}" \
    --build-arg VLLM_BASE_IMAGE="${VLLM_BASE_IMAGE}" \
    --build-arg CUDA_COMPAT="${CUDA_COMPAT}" \
    -t "${IMAGE}" .
  IMAGE="${IMAGE}" EXPECTED_CUDA="${CUDA_COMPAT}" bash ./verify-cuda124.sh --image-only
  echo "== 拉取M2.7双副本网关镜像 ${NGINX_IMAGE} =="
  docker pull "${NGINX_IMAGE}"
  [ "${NGINX_IMAGE}" = "nginx:stable" ] || docker tag "${NGINX_IMAGE}" nginx:stable
}
step_save() {
  local vllm_tar="${PKG}/images/xt-vllm-${VLLM_TAG#v}-${CUDA_PROFILE}.tar"
  local nginx_tar="${PKG}/images/nginx-stable.tar"
  docker save "${IMAGE}" -o "${vllm_tar}"; echo "   -> ${vllm_tar} ($(du -h "${vllm_tar}"|cut -f1))"
  docker save nginx:stable -o "${nginx_tar}"; echo "   -> ${nginx_tar} ($(du -h "${nginx_tar}"|cut -f1))"
}
step_system() {
  echo "== 系统依赖 deb(发行版=${SYS_DISTRO},须匹配离线机;两台同款)=="
  if [ "${SYS_DISTRO}" = "ubuntu" ] || [ "${SYS_DISTRO}" = "debian" ]; then
    ( cd "${PKG}/system/nvidia-container-toolkit" && apt-get download \
        nvidia-container-toolkit nvidia-container-toolkit-base \
        libnvidia-container1 libnvidia-container-tools ) || echo "   !! 先配 nvidia 源"
    ( cd "${PKG}/system/docker" && apt-get download docker-ce docker-ce-cli containerd.io ) \
      || echo "   !! 先配 docker 源(离线机已装 docker 则不用)"
  else echo "   !! 非 deb 系,按离线机实际发行版自备"; fi
  echo "   CUDA 12.4档位要求驱动>=550.54.15;更低版本须备 system/driver/*.run + 内核头"
}
step_scripts() {
  cp -f Dockerfile Dockerfile.cn run.sh recon.sh verify-cuda124.sh install-offline.sh prepare-offline.sh "${PKG}/scripts/" 2>/dev/null || true
  chmod +x "${PKG}/scripts/"*.sh 2>/dev/null || true
  cp -rf lb "${PKG}/scripts/" 2>/dev/null || true
  cp -f ../大模型部署方案对比-2x7xA40.md "${PKG}/" 2>/dev/null || true
  for model in MiniMax-M2.7-AWQ Qwen3.5-397B-A17B-AWQ Kimi-K2.6-AWQ; do
    mkdir -p "${PKG}/models/${model}"
    cp -f "../models/${model}/README-部署.md" "${PKG}/models/${model}/" 2>/dev/null || true
  done
}
step_manifest() {
  ( cd "${PKG}" && find . -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256 )
  echo "   条目: $(wc -l < "${PKG}/MANIFEST.sha256")"
}
dl() { echo "== 下载 $1 -> $2 =="; huggingface-cli download "$1" --local-dir "${PKG}/models/$2"; du -sh "${PKG}/models/$2"; }
step_m27()  { dl "${M27_REPO}"  "MiniMax-M2.7-AWQ"; }
step_397b() { dl "${Q397_REPO}" "Qwen3.5-397B-A17B-AWQ"; }
step_k26()  { dl "${K2_REPO}"   "Kimi-K2.6-AWQ"; }

case "${1:-base}" in
  base)     step_build; step_save; step_system; step_scripts; step_manifest
            echo "== base 完成(不含权重)。正式交付还需依次下载:m2.7 / 397b / k2.6 ==" ;;
  build)    step_build ;;
  save)     step_save ;;
  system)   step_system ;;
  m2.7)     step_m27;  step_manifest ;;
  397b)     step_397b; step_manifest ;;
  k2.6)     step_k26;  step_manifest ;;
  manifest) step_scripts; step_manifest ;;
  all)      step_build; step_save; step_system; step_scripts
            step_m27; step_397b; step_k26; step_manifest ;;
  *) echo "用法: $0 {base|all|build|save|system|m2.7|397b|k2.6|manifest}"; exit 1 ;;
esac

#!/usr/bin/env bash
# ============================================================================
# 联网机上运行:备齐 xt 完整离线包(镜像 + 系统依赖 + 三个模型 + 校验和)
# 前提:x86_64 Linux + Docker + huggingface_hub[hf_transfer],硬盘已挂载。
#
# 正式交付固定准备三个模型。可一键 all,也可分段下载以便断点续做:
#   ① 非权重部分:
#        export OUT=/mnt/drive VLLM_TAG=v0.24.0 SYS_DISTRO=ubuntu
#        # 显式使用官方cu129变体;镜像内加入cuda-compat-12-9和锁定Ray
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
VLLM_BASE_IMAGE="${VLLM_BASE_IMAGE:-${REGISTRY:-}vllm/vllm-openai:${VLLM_TAG}-cu129}"
CUDA_COMPAT="${CUDA_COMPAT:-12.9}"
CUDA_PROFILE="cu129-compat545"
RAY_VERSION="${RAY_VERSION:-2.56.1}"
IMAGE="${IMAGE:-xt-vllm:${VLLM_TAG#v}-${CUDA_PROFILE}}"
PKG="${OUT}/offline-xt"
SYS_DISTRO="${SYS_DISTRO:-ubuntu}"

# 三种权重仓库(都是 AWQ INT4;8+6备用复用397B+M2.7,无需新增权重)
M27_REPO="${M27_REPO:-QuantTrio/MiniMax-M2.7-AWQ}"
Q397_REPO="${Q397_REPO:-QuantTrio/Qwen3.5-397B-A17B-AWQ}"
K2_REPO="${K2_REPO:-<org>/Kimi-K2.6-AWQ}"

export HF_HUB_ENABLE_HF_TRANSFER=1
mkdir -p "${PKG}"/{images,models,scripts} \
         "${PKG}"/system/docker/{focal,jammy,noble} \
         "${PKG}"/system/{nvidia-container-toolkit,driver}

step_build() {
  [ "${CUDA_COMPAT}" = "12.9" ] || { echo "!! XT Forward Compatibility档位只接受CUDA_COMPAT=12.9"; exit 1; }
  echo "== 构建镜像 ${IMAGE}(base=${VLLM_BASE_IMAGE},要求torch CUDA=${CUDA_COMPAT})=="
  docker build -f "${DOCKERFILE:-Dockerfile}" \
    --build-arg VLLM_TAG="${VLLM_TAG}" \
    --build-arg VLLM_BASE_IMAGE="${VLLM_BASE_IMAGE}" \
    --build-arg CUDA_COMPAT="${CUDA_COMPAT}" \
    --build-arg RAY_VERSION="${RAY_VERSION}" \
    -t "${IMAGE}" .
  IMAGE="${IMAGE}" EXPECTED_CUDA="${CUDA_COMPAT}" EXPECTED_RAY="${RAY_VERSION}" bash ./verify-cu129-compat.sh --image-only
}
step_save() {
  local vllm_tar="${PKG}/images/xt-vllm-${VLLM_TAG#v}-${CUDA_PROFILE}.tar"
  docker save "${IMAGE}" -o "${vllm_tar}"; echo "   -> ${vllm_tar} ($(du -h "${vllm_tar}"|cut -f1))"
}
step_system() {
  echo "== 校验多Ubuntu系统应急包 =="
  local codename count
  for codename in focal jammy noble; do
    count="$(find "${PKG}/system/docker/${codename}" -maxdepth 1 -type f -name '*.deb' | wc -l)"
    [ "${count}" -ge 5 ] || { echo "!! docker/${codename}只有${count}个deb"; exit 1; }
  done
  count="$(find "${PKG}/system/nvidia-container-toolkit" -maxdepth 1 -type f -name '*.deb' | wc -l)"
  [ "${count}" -ge 4 ] || { echo "!! NVIDIA Toolkit只有${count}个deb"; exit 1; }
  find "${PKG}/system/driver" -maxdepth 1 -type f -name 'NVIDIA-Linux-x86_64-*.run' | grep -q . \
    || { echo "!! 缺少驱动兜底.run"; exit 1; }
  echo "PASS:focal/jammy/noble Docker、Toolkit与驱动兜底齐全"
  echo "   Windows准备机使用:prepare-system-windows.ps1 -OutRoot <盘>\offline-xt\system"
}
step_scripts() {
  cp -f Dockerfile Dockerfile.cn run.sh recon.sh verify-cu129-compat.sh install-offline.sh \
    install-system-deps.sh prepare-offline.sh prepare-system-windows.ps1 "${PKG}/scripts/" 2>/dev/null || true
  chmod +x "${PKG}/scripts/"*.sh 2>/dev/null || true
  cp -rf lb "${PKG}/scripts/" 2>/dev/null || true
  cp -f ../大模型部署方案对比-2x7xA40.md "${PKG}/" 2>/dev/null || true
  cp -f ../README-安装.md "${PKG}/" 2>/dev/null || true
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

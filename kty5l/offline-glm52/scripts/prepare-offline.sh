#!/usr/bin/env bash
# ============================================================================
# 联网机上运行:备齐 GLM-5.2 离线包(镜像 + 系统依赖 + 诊断小模型 + 大权重 + 校验和)
# 前提:本机已装 Docker、huggingface_hub[hf_transfer];硬盘已挂载。
#
# 两段式(大权重 410/388GB 单独一段,可先跳过):
#   ① 先备非权重部分(镜像 + 系统依赖 + 诊断小模型 + 脚本):
#        export OUT=/mnt/drive VLLM_REF=v0.24.0
#        ./prepare-offline.sh base
#   ② 大权重就绪后再下(几小时):
#        ./prepare-offline.sh weights          # GLM-5.2 权重(唯一,只此一个)
#
# 其他:
#   export HF_ENDPOINT=https://hf-mirror.com   # 国内下不动 HF 时用镜像
#   export SYS_DISTRO=ubuntu                    # 系统依赖按"离线机"发行版(见 recon 的 A1)
#   export DOCKERFILE=Dockerfile.cn             # 国内源版构建(配合 CUDA_REGISTRY / GH_PROXY)
#   ./prepare-offline.sh all                    # 一把梭(含大权重)
# ============================================================================
set -euo pipefail

OUT="${OUT:?请先 export OUT=硬盘挂载点}"
VLLM_REF="${VLLM_REF:-v0.24.0}"
IMAGE="glm52-vllm:${VLLM_REF#v}-pr38476"
PKG="${OUT}/offline-glm52"
SYS_DISTRO="${SYS_DISTRO:-ubuntu}"           # 系统依赖发行版(deb/rpm 必须匹配离线机)

# 权重仓库:唯一一个 GLM-5.2 权重,不带备用量化
MAIN_WEIGHTS_REPO="cyankiwi/GLM-5.2-AWQ-INT4"
VALID_MODEL_REPO="Qwen/Qwen3-8B"             # 仅阶段1 验 TP 通路的诊断小模型,不服务

export HF_HUB_ENABLE_HF_TRANSFER=1
# HF_ENDPOINT 若已 export(hf-mirror),huggingface-cli 自动走镜像,无需改命令

mkdir -p "${PKG}"/{images,models,system,scripts}
mkdir -p "${PKG}"/system/{docker,nvidia-container-toolkit,driver,wheels}

# ── 非权重部分 ──────────────────────────────────────────────────────
step_build() {
  echo "== 构建镜像 ${IMAGE}(会拉 CUDA base + vLLM 源 + torch,几 GB)=="
  # 国内网慢:export DOCKERFILE=Dockerfile.cn,并按需 export CUDA_REGISTRY=docker.m.daocloud.io/ GH_PROXY=https://ghfast.top/
  # 若在 ARM 机上构建,取消注释下一行强制 amd64(离线机是 x86_64)
  # export DOCKER_DEFAULT_PLATFORM=linux/amd64
  docker build -f "${DOCKERFILE:-Dockerfile}" \
    --build-arg VLLM_REF="${VLLM_REF}" \
    ${CUDA_REGISTRY:+--build-arg CUDA_REGISTRY="${CUDA_REGISTRY}"} \
    ${GH_PROXY:+--build-arg GH_PROXY="${GH_PROXY}"} \
    -t "${IMAGE}" .
}

step_save() {
  echo "== docker save 镜像 =="
  local tar="${PKG}/images/glm52-vllm-${VLLM_REF#v}-pr38476.tar"
  docker save "${IMAGE}" -o "${tar}"
  echo "   -> ${tar} ($(du -h "${tar}" | cut -f1))"
}

step_validmodel() {
  echo "== 下载阶段1 诊断小模型 ${VALID_MODEL_REPO}(~16GB,不是大权重)=="
  huggingface-cli download "${VALID_MODEL_REPO}" \
    --local-dir "${PKG}/models/Qwen3-8B"
}

step_system() {
  echo "== 系统依赖离线包(发行版=${SYS_DISTRO},必须与离线机一致!以 recon 的 A1 为准)=="
  if [ "${SYS_DISTRO}" = "ubuntu" ] || [ "${SYS_DISTRO}" = "debian" ]; then
    echo "   [toolkit] nvidia-container-toolkit(需先配好 nvidia 源)"
    ( cd "${PKG}/system/nvidia-container-toolkit" && \
      apt-get download nvidia-container-toolkit nvidia-container-toolkit-base \
                       libnvidia-container1 libnvidia-container-tools ) \
      || echo "   !! toolkit 下载失败:先按 nvidia 官方配 apt 源再重跑本步"
    echo "   [docker] docker-ce(离线机若已装 docker 可跳过)"
    ( cd "${PKG}/system/docker" && \
      apt-get download docker-ce docker-ce-cli containerd.io ) \
      || echo "   !! docker 下载失败:确认 docker apt 源已配"
  else
    echo "   !! SYS_DISTRO=${SYS_DISTRO} 非 deb 系(国产麒麟/UOS 等):"
    echo "      官方 deb/rpm 大概率不匹配 → 走部署步骤的备案 C(裸机 pip wheels,见 step_wheels)"
  fi
  echo "   [驱动] 若 recon 显示驱动<550:手动从 nvidia.com 下 NVIDIA-Linux-x86_64-<版本>.run"
  echo "          + 内核头(linux-headers/kernel-devel),放 system/driver/。本脚本不自动下驱动。"
}

step_wheels() {
  # 备案 C:国产 OS 容器装不上时,裸机 pip 跑 vLLM。默认不执行,需显式调用。
  echo "== [备案C] 下载 pip 离线轮子到 system/wheels/(裸机 pip 兜底,仅国产 OS 需要)=="
  pip download "vllm==${VLLM_REF#v}" torch \
    --dest "${PKG}/system/wheels" \
    || echo "   !! 轮子下载失败:确认 pip 可用、版本号存在;裸机路径还需另打 PR#38476 patch"
}

step_scripts() {
  echo "   拷贝脚本与文档"
  cp -f Dockerfile Dockerfile.cn run.sh prepare-offline.sh install-offline.sh recon.sh "${PKG}/scripts/" 2>/dev/null || true
  cp -rf patches wheels "${PKG}/scripts/" 2>/dev/null || true
  cp -f ../GLM-5.2-部署步骤-8xA100.md "${PKG}/" 2>/dev/null || true
}

# ── 大权重(单独一段,可先跳过)──────────────────────────────────────
step_weights() {
  echo "== 下载 GLM-5.2 主权重 ${MAIN_WEIGHTS_REPO}(~410GB,数小时)=="
  huggingface-cli download "${MAIN_WEIGHTS_REPO}" \
    --local-dir "${PKG}/models/GLM-5.2-AWQ-INT4"
  du -sh "${PKG}/models/GLM-5.2-AWQ-INT4"      # 应约 410GB
}

step_manifest() {
  echo "== 生成 MANIFEST.sha256(全量校验和,防拷贝损坏)=="
  ( cd "${PKG}" && find . -type f ! -name MANIFEST.sha256 -print0 \
      | sort -z | xargs -0 sha256sum > MANIFEST.sha256 )
  echo "   条目数: $(wc -l < "${PKG}/MANIFEST.sha256")"
}

case "${1:-base}" in
  # 非权重部分一把备齐(先跑这个)
  base)      step_build; step_save; step_validmodel; step_system; step_scripts; step_manifest
             echo; echo "== base 完成(不含大权重)。当前大小: $(du -sh "${PKG}" | cut -f1) =="
             echo "   大权重就绪后:./prepare-offline.sh weights && ./prepare-offline.sh manifest" ;;
  build)     step_build ;;
  save)      step_save ;;
  validmodel) step_validmodel ;;
  system)    step_system ;;
  wheels)    step_wheels ;;
  weights)   step_weights; step_manifest ;;
  manifest)  step_scripts; step_manifest ;;
  # 全量(含大权重)
  all)       step_build; step_save; step_validmodel; step_system; step_scripts
             step_weights; step_manifest
             echo; echo "== 完成。总大小: $(du -sh "${PKG}" | cut -f1) =="
             echo "   umount 硬盘,插到离线机,先跑 sha256sum -c MANIFEST.sha256" ;;
  *) echo "用法: $0 {base|all|build|save|validmodel|system|wheels|weights|manifest}"; exit 1 ;;
esac

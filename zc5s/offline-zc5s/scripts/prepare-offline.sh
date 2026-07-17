#!/usr/bin/env bash
# ============================================================================
# 联网机上运行:备齐 zc5s 离线包(镜像 + 系统依赖 + 权重按需 + 裸机wheels + 校验和)
# 前提:x86_64 Linux + Docker + huggingface_hub[hf_transfer]。
#
#   export OUT=/mnt/drive VLLM_TAG=v0.24.0
#   ./prepare-offline.sh base            # 镜像 + system deps + 裸机wheels + 脚本 + 校验和
#   ./prepare-offline.sh m2.7            # 🥇 M2.7 INT4 ~115G(稳健默认)
#   ./prepare-offline.sh m2.7-fp8        # 🥇 M2.7 FP8  ~230G(质量,4090专属)
#   ./prepare-offline.sh 397b            # 🥈 Qwen3.5-397B INT4 ~200G
#   ./prepare-offline.sh manifest
# 国内:export HF_ENDPOINT=https://hf-mirror.com ; 构建 DOCKERFILE=Dockerfile.cn REGISTRY=...
# ============================================================================
set -euo pipefail
OUT="${OUT:?请先 export OUT=硬盘挂载点}"
VLLM_TAG="${VLLM_TAG:-v0.24.0}"
IMAGE="zc5s-vllm:${VLLM_TAG#v}"
PKG="${OUT}/offline-zc5s"

M27_REPO="${M27_REPO:-QuantTrio/MiniMax-M2.7-AWQ}"
M27_FP8_REPO="${M27_FP8_REPO:-<org>/MiniMax-M2.7-FP8}"      # FP8 仓库现场确认
Q397_REPO="${Q397_REPO:-QuantTrio/Qwen3.5-397B-A17B-AWQ}"

export HF_HUB_ENABLE_HF_TRANSFER=1
mkdir -p "${PKG}"/{images,models,scripts} \
         "${PKG}"/system/{container-toolkit,docker,driver,wheels}

step_build() {
  echo "== 构建镜像 ${IMAGE}(FROM vllm/vllm-openai)=="
  docker build -f "${DOCKERFILE:-Dockerfile}" --build-arg VLLM_TAG="${VLLM_TAG}" \
    ${REGISTRY:+--build-arg REGISTRY="${REGISTRY}"} -t "${IMAGE}" .
}
step_save() { local t="${PKG}/images/zc5s-vllm-${VLLM_TAG#v}.tar"; docker save "${IMAGE}" -o "$t"; echo "   -> $t ($(du -h "$t"|cut -f1))"; }

step_wheels() {
  echo "== 备案C:裸机 pip 轮子(麒麟容器装不上时用)=="
  echo "   在 x86_64 Linux 上下 manylinux 轮子(麒麟通用):"
  pip download vllm "huggingface_hub[hf_transfer]" -d "${PKG}/system/wheels" \
    || echo "   !! 下载失败:确认 pip 可用;或指定 vllm==${VLLM_TAG#v}"
}
step_system() {
  echo "== 系统依赖:★麒麟按 recon 的 A2 判 deb/rpm,取对应 nvidia-container-toolkit/docker =="
  echo "   deb 系:apt-get download nvidia-container-toolkit ... 放 system/container-toolkit/"
  echo "   rpm 系:yumdownloader/dnf download nvidia-container-toolkit ... 放 system/container-toolkit/"
  echo "   (本脚本不自动下——发行版差异大,以 recon 结果手动备;容器装不上就用 step_wheels 裸机)"
}
step_scripts() {
  cp -f Dockerfile Dockerfile.cn run.sh recon.sh install-offline.sh install-baremetal.sh prepare-offline.sh "${PKG}/scripts/" 2>/dev/null || true
  cp -rf lb "${PKG}/scripts/" 2>/dev/null || true
  cp -f ../大模型选型方案-8x4090-48G.md "${PKG}/" 2>/dev/null || true
}
step_manifest() { ( cd "${PKG}" && find . -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256 ); echo "   条目 $(wc -l < "${PKG}/MANIFEST.sha256")"; }
dl(){ echo "== 下载 $1 -> $2 =="; huggingface-cli download "$1" --local-dir "${PKG}/models/$2"; du -sh "${PKG}/models/$2"; }

case "${1:-base}" in
  base)      step_build; step_save; step_wheels; step_system; step_scripts; step_manifest
             echo "== base 完成(不含权重)。按方案下:m2.7 / m2.7-fp8 / 397b ==" ;;
  build)     step_build ;;
  save)      step_save ;;
  wheels)    step_wheels ;;
  m2.7)      dl "${M27_REPO}"     "MiniMax-M2.7-AWQ";        step_manifest ;;
  m2.7-fp8)  dl "${M27_FP8_REPO}" "MiniMax-M2.7-FP8";        step_manifest ;;
  397b)      dl "${Q397_REPO}"    "Qwen3.5-397B-A17B-AWQ";   step_manifest ;;
  manifest)  step_scripts; step_manifest ;;
  all)       step_build; step_save; step_wheels; step_system; step_scripts
             dl "${M27_REPO}" "MiniMax-M2.7-AWQ"; dl "${Q397_REPO}" "Qwen3.5-397B-A17B-AWQ"; step_manifest ;;
  *) echo "用法: $0 {base|all|build|save|wheels|m2.7|m2.7-fp8|397b|manifest}"; exit 1 ;;
esac

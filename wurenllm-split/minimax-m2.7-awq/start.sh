#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="wurenllm/minimax-m2.7:vllm0.24.0-cu129"
IMAGE_TAR="${ROOT}/images/wurenllm-minimax-m2.7-vllm0.24.0-cu129.tar"
MODEL_DIR="${ROOT}/models/MiniMax-M2.7-AWQ"
CONTAINER="minimax-m2.7"

GPU_DEVICES="${GPU_DEVICES:-0,1,2,3}"
PORT="${PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-65536}"

check_model() {
  test -f "${MODEL_DIR}/config.json" || { echo "缺少 ${MODEL_DIR}/config.json" >&2; exit 1; }
  ! find "${MODEL_DIR}" -type f \( -name '*.incomplete' -o -name '*.lock' \) -print -quit | grep -q . \
    || { echo "模型仍有未完成下载文件" >&2; exit 1; }
}

case "${1:-}" in
  load)
    docker load -i "${IMAGE_TAR}"
    ;;
  start)
    check_model
    docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
    docker run -d --name "${CONTAINER}" \
      --gpus all --ipc=host \
      -e CUDA_VISIBLE_DEVICES="${GPU_DEVICES}" \
      -p "${PORT}:8000" \
      -v "${MODEL_DIR}:/model:ro" \
      "${IMAGE}" \
      vllm serve /model \
        --served-model-name minimax-m2.7 \
        --tensor-parallel-size 4 \
        --enable-expert-parallel \
        --quantization awq_marlin \
        --max-model-len "${MAX_MODEL_LEN}" \
        --trust-remote-code
    ;;
  logs) docker logs -f "${CONTAINER}" ;;
  stop) docker rm -f "${CONTAINER}" ;;
  *) echo "用法: $0 load | start | logs | stop" >&2; exit 1 ;;
esac

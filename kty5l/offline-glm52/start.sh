#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="glm52-vllm:0.24.0-pr38476-cu128-native-r570-a100"
IMAGE_TAR="${ROOT}/images/glm52-vllm-0.24.0-pr38476-cu128-native-r570-a100.tar"
MODEL_DIR="${ROOT}/models/GLM-5.2-AWQ-INT4"
CONTAINER="glm52"

GPU_DEVICES="${GPU_DEVICES:-0,1,2,3,4,5,6,7}"
PORT="${PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-16}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
NCCL_P2P_DISABLE="${NCCL_P2P_DISABLE:-0}"

check_model() {
  test -f "${MODEL_DIR}/config.json" \
    || { echo "缺少 ${MODEL_DIR}/config.json" >&2; exit 1; }
  ! find "${MODEL_DIR}" -type f \
      \( -name '*.incomplete' -o -name '*.lock' -o -name '*.part' \) \
      -print -quit | grep -q . \
    || { echo "模型目录仍有未完成下载文件" >&2; exit 1; }
}

case "${1:-}" in
  load)
    (cd "${ROOT}/images" && sha256sum -c "$(basename "${IMAGE_TAR}").sha256")
    docker load -i "${IMAGE_TAR}"
    ;;
  start)
    check_model
    docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
    docker run -d --name "${CONTAINER}" \
      --gpus all --ipc=host \
      --ulimit memlock=-1 --ulimit stack=67108864 \
      --restart no \
      --log-driver local --log-opt max-size=50m --log-opt max-file=3 \
      -e CUDA_VISIBLE_DEVICES="${GPU_DEVICES}" \
      -e NCCL_P2P_DISABLE="${NCCL_P2P_DISABLE}" \
      -e VLLM_ATTENTION_BACKEND=TRITON_MLA_SPARSE \
      -p "${PORT}:8000" \
      -v "${MODEL_DIR}:/model:ro" \
      "${IMAGE}" \
      vllm serve /model \
        --served-model-name glm-5.2 \
        --tensor-parallel-size 8 \
        --no-async-scheduling \
        --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" \
        --max-model-len "${MAX_MODEL_LEN}" \
        --max-num-seqs "${MAX_NUM_SEQS}" \
        --kv-cache-dtype auto \
        --enable-prefix-caching \
        --enable-chunked-prefill \
        --max-num-batched-tokens 8192 \
        --enable-auto-tool-choice \
        --tool-call-parser glm47 \
        --reasoning-parser glm45 \
        --trust-remote-code \
        --port 8000
    echo "GLM-5.2 启动中；查看日志：./start.sh logs"
    ;;
  logs)
    docker logs -f "${CONTAINER}"
    ;;
  test)
    curl "http://localhost:${PORT}/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -d '{"model":"glm-5.2","messages":[{"role":"user","content":"你好"}],"max_tokens":64}'
    ;;
  stop)
    docker rm -f "${CONTAINER}" 2>/dev/null || true
    ;;
  *)
    echo "用法：$0 load | start | logs | test | stop" >&2
    exit 1
    ;;
esac

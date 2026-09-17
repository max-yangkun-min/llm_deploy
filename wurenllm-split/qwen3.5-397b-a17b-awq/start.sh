#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="wurenllm/qwen3.5-397b-a17b:vllm0.24.0-cu129"
IMAGE_TAR="${ROOT}/images/wurenllm-qwen3.5-397b-a17b-vllm0.24.0-cu129.tar"
MODEL_DIR="${ROOT}/models/Qwen3.5-397B-A17B-AWQ"
HEAD_CONTAINER="qwen-ray-head"
WORKER_CONTAINER="qwen-ray-worker"
LOCAL_CONTAINER="qwen-local-8gpu"

PORT="${PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-65536}"

network_env() {
  test -n "${NIC:-}" || { echo "请设置 NIC=万兆网卡名" >&2; exit 1; }
}

case "${1:-}" in
  load)
    docker load -i "${IMAGE_TAR}"
    ;;
  head)
    network_env
    test -n "${NODE_IP:-}" || { echo "请设置 NODE_IP=本机万兆IP" >&2; exit 1; }
    GPU_DEVICES="${GPU_DEVICES:-0,1,2,3}"
    docker rm -f "${HEAD_CONTAINER}" >/dev/null 2>&1 || true
    docker run -d --name "${HEAD_CONTAINER}" --gpus all --ipc=host --network host \
      -e CUDA_VISIBLE_DEVICES="${GPU_DEVICES}" -v "${MODEL_DIR}:/model:ro" \
      -e VLLM_HOST_IP="${NODE_IP}" \
      -e NCCL_SOCKET_IFNAME="${NIC}" -e GLOO_SOCKET_IFNAME="${NIC}" -e NCCL_IB_DISABLE=1 \
      "${IMAGE}" ray start --head --node-ip-address="${NODE_IP}" --port=6379 --block
    ;;
  worker)
    network_env
    test -n "${NODE_IP:-}" || { echo "请设置 NODE_IP=本机万兆IP" >&2; exit 1; }
    test -n "${HEAD_IP:-}" || { echo "请设置 HEAD_IP=主节点万兆IP" >&2; exit 1; }
    GPU_DEVICES="${GPU_DEVICES:-0,1,2,3}"
    docker rm -f "${WORKER_CONTAINER}" >/dev/null 2>&1 || true
    docker run -d --name "${WORKER_CONTAINER}" --gpus all --ipc=host --network host \
      -e CUDA_VISIBLE_DEVICES="${GPU_DEVICES}" -v "${MODEL_DIR}:/model:ro" \
      -e VLLM_HOST_IP="${NODE_IP}" \
      -e NCCL_SOCKET_IFNAME="${NIC}" -e GLOO_SOCKET_IFNAME="${NIC}" -e NCCL_IB_DISABLE=1 \
      "${IMAGE}" ray start --address="${HEAD_IP}:6379" --node-ip-address="${NODE_IP}" --block
    ;;
  serve)
    docker exec -d "${HEAD_CONTAINER}" bash -lc \
      "vllm serve /model --served-model-name qwen3.5-397b --tensor-parallel-size 4 --pipeline-parallel-size 2 --distributed-executor-backend ray --enable-expert-parallel --quantization awq_marlin --max-model-len ${MAX_MODEL_LEN} --trust-remote-code --port ${PORT} >/tmp/vllm.log 2>&1"
    ;;
  local)
    GPU_DEVICES="${GPU_DEVICES:-0,1,2,3,4,5,6,7}"
    docker rm -f "${LOCAL_CONTAINER}" >/dev/null 2>&1 || true
    docker run -d --name "${LOCAL_CONTAINER}" \
      --gpus all --ipc=host \
      -e CUDA_VISIBLE_DEVICES="${GPU_DEVICES}" \
      -p "${PORT}:8000" \
      -v "${MODEL_DIR}:/model:ro" \
      "${IMAGE}" \
      vllm serve /model \
        --served-model-name qwen3.5-397b \
        --tensor-parallel-size 4 \
        --pipeline-parallel-size 2 \
        --distributed-executor-backend mp \
        --enable-expert-parallel \
        --quantization awq_marlin \
        --max-model-len "${MAX_MODEL_LEN}" \
        --trust-remote-code
    ;;
  local-logs) docker logs -f "${LOCAL_CONTAINER}" ;;
  logs) docker exec "${HEAD_CONTAINER}" tail -f /tmp/vllm.log ;;
  stop) docker rm -f "${HEAD_CONTAINER}" "${WORKER_CONTAINER}" "${LOCAL_CONTAINER}" 2>/dev/null || true ;;
  *) echo "用法: $0 load | local | local-logs | head | worker | serve | logs | stop" >&2; exit 1 ;;
esac

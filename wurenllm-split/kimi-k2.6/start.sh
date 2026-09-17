#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="wurenllm/kimi-k2.6:vllm0.24.0-cu129"
IMAGE_TAR="${ROOT}/images/wurenllm-kimi-k2.6-vllm0.24.0-cu129.tar"
MODEL_DIR="${ROOT}/models/Kimi-K2.6"
HEAD_CONTAINER="kimi-ray-head"
WORKER_CONTAINER="kimi-ray-worker"

GPU_DEVICES="${GPU_DEVICES:-0,1,2,3,4,5}"
PORT="${PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-65536}"

network_env() {
  test -n "${NIC:-}" || { echo "请设置 NIC=万兆网卡名" >&2; exit 1; }
}

common=(--gpus all --ipc=host --network host
  -e CUDA_VISIBLE_DEVICES="${GPU_DEVICES}"
  -v "${MODEL_DIR}:/model:ro")

case "${1:-}" in
  load)
    docker load -i "${IMAGE_TAR}"
    ;;
  head)
    network_env
    test -n "${NODE_IP:-}" || { echo "请设置 NODE_IP=本机万兆IP" >&2; exit 1; }
    docker rm -f "${HEAD_CONTAINER}" >/dev/null 2>&1 || true
    docker run -d --name "${HEAD_CONTAINER}" "${common[@]}" \
      -e VLLM_HOST_IP="${NODE_IP}" \
      -e NCCL_SOCKET_IFNAME="${NIC}" -e GLOO_SOCKET_IFNAME="${NIC}" -e NCCL_IB_DISABLE=1 \
      "${IMAGE}" ray start --head --node-ip-address="${NODE_IP}" --port=6379 --block
    ;;
  worker)
    network_env
    test -n "${NODE_IP:-}" || { echo "请设置 NODE_IP=本机万兆IP" >&2; exit 1; }
    test -n "${HEAD_IP:-}" || { echo "请设置 HEAD_IP=主节点万兆IP" >&2; exit 1; }
    docker rm -f "${WORKER_CONTAINER}" >/dev/null 2>&1 || true
    docker run -d --name "${WORKER_CONTAINER}" "${common[@]}" \
      -e VLLM_HOST_IP="${NODE_IP}" \
      -e NCCL_SOCKET_IFNAME="${NIC}" -e GLOO_SOCKET_IFNAME="${NIC}" -e NCCL_IB_DISABLE=1 \
      "${IMAGE}" ray start --address="${HEAD_IP}:6379" --node-ip-address="${NODE_IP}" --block
    ;;
  serve)
    docker exec -d "${HEAD_CONTAINER}" bash -lc \
      "vllm serve /model --served-model-name kimi-k2.6 --tensor-parallel-size 2 --pipeline-parallel-size 6 --distributed-executor-backend ray --enable-expert-parallel --quantization compressed-tensors --max-model-len ${MAX_MODEL_LEN} --trust-remote-code --port ${PORT} >/tmp/vllm.log 2>&1"
    ;;
  logs) docker exec "${HEAD_CONTAINER}" tail -f /tmp/vllm.log ;;
  stop) docker rm -f "${HEAD_CONTAINER}" "${WORKER_CONTAINER}" 2>/dev/null || true ;;
  *) echo "用法: $0 load | head | worker | serve | logs | stop" >&2; exit 1 ;;
esac

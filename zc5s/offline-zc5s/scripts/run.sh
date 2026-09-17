#!/usr/bin/env bash
# zc5s · 单机 8×RTX4090 · MiniMax M2.7 AWQ · TP=4 双副本
set -euo pipefail

IMAGE="${IMAGE:-zc5s-vllm:0.24.0-cu129}"
# 默认复用同一离线介质上的 /offline-xt/models；若介质挂载位置不同，现场覆盖 MODELS_DIR。
MODELS_DIR="${MODELS_DIR:-/offline-xt/models}"
HF_CACHE="${HF_CACHE:-/data/hf-cache}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GPU_COMMON=(--ipc=host --ulimit memlock=-1 --ulimit stack=67108864 --restart no
  --log-driver local --log-opt max-size=50m --log-opt max-file=3
  -v "${MODELS_DIR}:/models:ro" -v "${HF_CACHE}:/root/.cache/huggingface")

start_replica() {
  local name="$1" devices="$2" port="$3"
  docker run -d --name "zc5s-m2.7-${name}" "${GPU_COMMON[@]}" \
    --gpus '"device='"${devices}"'"' -p "${port}:8000" \
    "${IMAGE}" vllm serve /models/MiniMax-M2.7-AWQ \
      --served-model-name minimax-m2.7 \
      --tensor-parallel-size 4 --enable-expert-parallel --quantization awq_marlin \
      --speculative-config '{"method":"mtp","num_speculative_tokens":2}' \
      --gpu-memory-utilization 0.90 --max-model-len 65536 --max-num-seqs 32 \
      --kv-cache-dtype auto --enable-prefix-caching --enable-chunked-prefill \
      --enable-auto-tool-choice --tool-call-parser minimax_m2 \
      --reasoning-parser minimax_m2_append_think --trust-remote-code --port 8000
}

case "${1:-}" in
  verify)
    docker run --rm --gpus all "${IMAGE}" python3 -c \
      'import torch,vllm; assert torch.cuda.is_available(); assert all(torch.cuda.get_device_capability(i)==(8,9) for i in range(torch.cuda.device_count())); print("vllm",vllm.__version__,"cuda",torch.version.cuda,"gpus",torch.cuda.device_count())'
    ;;
  replica-a) start_replica a "${GPU_A:-0,1,2,3}" 8001 ;;
  replica-b) start_replica b "${GPU_B:-4,5,6,7}" 8002 ;;
  m2.7)
    start_replica a "${GPU_A:-0,1,2,3}" 8001
    start_replica b "${GPU_B:-4,5,6,7}" 8002
    echo "M2.7 双副本已启动(:8001/:8002)；再执行 $0 lb-nginx"
    ;;
  lb-nginx)
    docker run -d --name zc5s-lb --network host --restart no \
      --log-driver local --log-opt max-size=10m --log-opt max-file=3 \
      -v "${SCRIPT_DIR}/lb/nginx.conf:/etc/nginx/nginx.conf:ro" \
      "${IMAGE}" nginx -g 'daemon off;'
    echo "nginx LB 已启动，统一入口 :8000"
    ;;
  logs) docker logs -f "${2:-zc5s-m2.7-a}" ;;
  test)
    curl "http://localhost:${2:-8000}/v1/chat/completions" \
      -H 'Content-Type: application/json' \
      -d '{"model":"minimax-m2.7","messages":[{"role":"user","content":"你好"}],"max_tokens":32}'
    ;;
  stop) docker rm -f zc5s-m2.7-a zc5s-m2.7-b zc5s-lb 2>/dev/null || true ;;
  *) echo "用法: $0 {verify|replica-a|replica-b|m2.7|lb-nginx|logs [容器]|test [端口]|stop}"; exit 1 ;;
esac

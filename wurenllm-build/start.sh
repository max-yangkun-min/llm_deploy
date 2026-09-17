#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="${MODELS_DIR:-${ROOT_DIR}/models}"
IMAGE_TAR="${IMAGE_TAR:-${ROOT_DIR}/images/wurenllm-images-vllm0.24.0-cu129.tar}"
HF_CACHE="${HF_CACHE:-${ROOT_DIR}/.runtime-hf-cache}"

M2_IMAGE="wurenllm/minimax-m2.7:vllm0.24.0-cu129"
QWEN_IMAGE="wurenllm/qwen3.5-397b-a17b:vllm0.24.0-cu129"
KIMI_IMAGE="wurenllm/kimi-k2.6:vllm0.24.0-cu129"

M2_MODEL="${MODELS_DIR}/MiniMax-M2.7-AWQ"
QWEN_MODEL="${MODELS_DIR}/Qwen3.5-397B-A17B-AWQ"
KIMI_MODEL="${MODELS_DIR}/Kimi-K2.6"

PORT="${PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-65536}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"

die() { echo "错误: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "缺少命令: $1"; }

check_one_model() {
  local dir="$1"
  test -f "${dir}/config.json" || die "${dir}/config.json 不存在"
  test -f "${dir}/model.safetensors.index.json" || die "${dir}/model.safetensors.index.json 不存在"
  if find "${dir}" -type f \( -name '*.incomplete' -o -name '*.lock' \) -print -quit | grep -q .; then
    die "${dir} 含未完成下载文件"
  fi
}

common_run=(--gpus all --ipc=host --ulimit memlock=-1 --ulimit stack=67108864
  --restart unless-stopped --log-driver local --log-opt max-size=50m --log-opt max-file=3
  -v "${MODELS_DIR}:/models:ro" -v "${HF_CACHE}:/root/.cache/huggingface")

profile_image() {
  case "$1" in
    qwen) echo "${QWEN_IMAGE}" ;;
    kimi) echo "${KIMI_IMAGE}" ;;
    *) die "profile 只能是 qwen 或 kimi" ;;
  esac
}

case "${1:-}" in
  load)
    need docker
    test -f "${IMAGE_TAR}" || die "镜像归档不存在: ${IMAGE_TAR}"
    docker load -i "${IMAGE_TAR}"
    ;;

  check-models)
    check_one_model "${M2_MODEL}"
    check_one_model "${QWEN_MODEL}"
    check_one_model "${KIMI_MODEL}"
    echo "三个模型目录的关键文件与下载状态检查通过"
    ;;

  check-gpu)
    need docker
    docker run --rm --gpus all --entrypoint python3 "${M2_IMAGE}" -c \
      'import torch; assert torch.cuda.is_available(); p=torch.cuda.get_device_properties(0); print(torch.__version__, torch.version.cuda, p.name, p.major, p.minor); assert (p.major,p.minor)==(8,6)'
    ;;

  m2.7)
    check_one_model "${M2_MODEL}"
    GPU_DEVICES="${GPU_DEVICES:-0,1,2,3}"
    MTP_ARGS=()
    if [[ "${ENABLE_MTP:-0}" == "1" ]]; then
      MTP_ARGS=(--speculative-config '{"method":"mtp","num_speculative_tokens":2}')
    fi
    docker rm -f wurenllm-m2.7 >/dev/null 2>&1 || true
    docker run -d --name wurenllm-m2.7 "${common_run[@]}" -p "${PORT}:8000" \
      -e CUDA_VISIBLE_DEVICES="${GPU_DEVICES}" "${M2_IMAGE}" \
      vllm serve /models/MiniMax-M2.7-AWQ --served-model-name minimax-m2.7 \
        --tensor-parallel-size 4 --enable-expert-parallel --quantization awq_marlin \
        --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" --max-model-len "${MAX_MODEL_LEN}" --max-num-seqs 32 \
        --kv-cache-dtype auto --enable-prefix-caching --enable-chunked-prefill \
        --enable-auto-tool-choice --tool-call-parser minimax_m2 \
        --reasoning-parser minimax_m2_append_think --trust-remote-code \
        "${MTP_ARGS[@]}" --port 8000
    echo "MiniMax M2.7 已提交启动: http://本机:${PORT}/v1"
    ;;

  qwen-local)
    check_one_model "${QWEN_MODEL}"
    GPU_DEVICES="${GPU_DEVICES:-0,1,2,3,4,5,6,7}"
    docker rm -f wurenllm-qwen >/dev/null 2>&1 || true
    docker run -d --name wurenllm-qwen "${common_run[@]}" -p "${PORT}:8000" \
      -e CUDA_VISIBLE_DEVICES="${GPU_DEVICES}" "${QWEN_IMAGE}" \
      vllm serve /models/Qwen3.5-397B-A17B-AWQ --served-model-name qwen3.5-397b \
        --tensor-parallel-size 4 --pipeline-parallel-size 2 --distributed-executor-backend mp \
        --enable-expert-parallel --quantization awq_marlin \
        --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" --max-model-len "${MAX_MODEL_LEN}" --max-num-seqs 48 \
        --kv-cache-dtype auto --enable-prefix-caching --enable-chunked-prefill \
        --enable-auto-tool-choice --tool-call-parser hermes --reasoning-parser qwen3 \
        --trust-remote-code --port 8000
    echo "Qwen3.5-397B 已提交单机 8 卡启动: http://本机:${PORT}/v1"
    ;;

  ray-head)
    PROFILE="${2:-}"
    IMAGE="$(profile_image "${PROFILE}")"
    GPU_DEVICES="${GPU_DEVICES:-$([[ "${PROFILE}" == kimi ]] && echo 0,1,2,3,4,5 || echo 0,1,2,3)}"
    NIC="${NIC:?请设置 NIC=万兆网卡名}"
    docker rm -f wurenllm-ray-head >/dev/null 2>&1 || true
    docker run -d --name wurenllm-ray-head --network host "${common_run[@]}" \
      -e CUDA_VISIBLE_DEVICES="${GPU_DEVICES}" -e NCCL_SOCKET_IFNAME="${NIC}" \
      -e GLOO_SOCKET_IFNAME="${NIC}" -e NCCL_IB_DISABLE=1 "${IMAGE}" \
      ray start --head --port=6379 --block
    echo "Ray head 已提交启动，profile=${PROFILE}，GPU=${GPU_DEVICES}"
    ;;

  ray-worker)
    PROFILE="${2:-}"
    IMAGE="$(profile_image "${PROFILE}")"
    GPU_DEVICES="${GPU_DEVICES:-$([[ "${PROFILE}" == kimi ]] && echo 0,1,2,3,4,5 || echo 0,1,2,3)}"
    NIC="${NIC:?请设置 NIC=万兆网卡名}"
    HEAD_IP="${HEAD_IP:?请设置 HEAD_IP=机器A万兆IP}"
    docker rm -f wurenllm-ray-worker >/dev/null 2>&1 || true
    docker run -d --name wurenllm-ray-worker --network host "${common_run[@]}" \
      -e CUDA_VISIBLE_DEVICES="${GPU_DEVICES}" -e NCCL_SOCKET_IFNAME="${NIC}" \
      -e GLOO_SOCKET_IFNAME="${NIC}" -e NCCL_IB_DISABLE=1 "${IMAGE}" \
      ray start --address="${HEAD_IP}:6379" --block
    echo "Ray worker 已提交加入 ${HEAD_IP}:6379，profile=${PROFILE}"
    ;;

  serve-qwen)
    check_one_model "${QWEN_MODEL}"
    docker exec -d wurenllm-ray-head bash -lc \
      "vllm serve /models/Qwen3.5-397B-A17B-AWQ --served-model-name qwen3.5-397b \
      --tensor-parallel-size 4 --pipeline-parallel-size 2 --enable-expert-parallel --quantization awq_marlin \
      --gpu-memory-utilization ${GPU_MEMORY_UTILIZATION} --max-model-len ${MAX_MODEL_LEN} --max-num-seqs 48 \
      --kv-cache-dtype auto --enable-prefix-caching --enable-chunked-prefill \
      --enable-auto-tool-choice --tool-call-parser hermes --reasoning-parser qwen3 \
      --trust-remote-code --port ${PORT} >/tmp/vllm.log 2>&1"
    echo "Qwen3.5-397B 跨机服务已提交启动；查看: $0 pp-logs"
    ;;

  serve-kimi)
    check_one_model "${KIMI_MODEL}"
    docker exec -d wurenllm-ray-head bash -lc \
      "vllm serve /models/Kimi-K2.6 --served-model-name kimi-k2.6 \
      --tensor-parallel-size 2 --pipeline-parallel-size 6 --enable-expert-parallel --quantization compressed-tensors \
      --gpu-memory-utilization ${GPU_MEMORY_UTILIZATION} --max-model-len ${MAX_MODEL_LEN} --max-num-seqs 64 \
      --kv-cache-dtype auto --enable-prefix-caching --enable-chunked-prefill \
      --enable-auto-tool-choice --tool-call-parser kimi_k2 --reasoning-parser kimi_k2 \
      --trust-remote-code --port ${PORT} >/tmp/vllm.log 2>&1"
    echo "Kimi K2.6 跨机服务已提交启动；查看: $0 pp-logs"
    ;;

  lb-m2)
    NODE_A="${NODE_A:?请设置 NODE_A=机器A模型IP:端口}"
    NODE_B="${NODE_B:?请设置 NODE_B=机器B模型IP:端口}"
    LB_PORT="${LB_PORT:-9000}"
    CONF="${TMPDIR:-/tmp}/wurenllm-nginx.conf"
    cat >"${CONF}" <<EOF
events {}
http {
  upstream m2 { least_conn; server ${NODE_A}; server ${NODE_B}; }
  server { listen 8000; client_max_body_size 64m;
    location / { proxy_pass http://m2; proxy_http_version 1.1;
      proxy_set_header Connection ""; proxy_buffering off; proxy_read_timeout 600s; }
  }
}
EOF
    docker rm -f wurenllm-lb >/dev/null 2>&1 || true
    docker run -d --name wurenllm-lb --restart unless-stopped -p "${LB_PORT}:8000" \
      -v "${CONF}:/etc/nginx/nginx.conf:ro" --entrypoint nginx "${M2_IMAGE}" -g 'daemon off;'
    echo "M2.7 双副本入口: http://本机:${LB_PORT}/v1"
    ;;

  status)
    docker ps --filter 'name=wurenllm-' --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
    ;;

  logs)
    docker logs -f "${2:?请给容器名，例如 wurenllm-m2.7}"
    ;;

  pp-logs)
    docker exec wurenllm-ray-head bash -lc 'test -f /tmp/vllm.log && tail -f /tmp/vllm.log || echo 等待模型日志'
    ;;

  test)
    MODEL="${2:?请给模型名: minimax-m2.7 / qwen3.5-397b / kimi-k2.6}"
    BASE_URL="${BASE_URL:-http://127.0.0.1:${PORT}/v1}"
    curl -fsS "${BASE_URL}/models"
    echo
    curl -fsS "${BASE_URL}/chat/completions" -H 'Content-Type: application/json' -d \
      "{\"model\":\"${MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"只回复 OK\"}],\"max_tokens\":16,\"temperature\":0}"
    echo
    ;;

  stop)
    docker rm -f wurenllm-m2.7 wurenllm-qwen wurenllm-ray-head wurenllm-ray-worker wurenllm-lb 2>/dev/null || true
    ;;

  *)
    cat <<'EOF'
用法:
  ./start.sh load | check-models | check-gpu
  ./start.sh m2.7 | qwen-local
  NIC=ens6f0 ./start.sh ray-head qwen|kimi
  NIC=ens6f0 HEAD_IP=10.0.0.1 ./start.sh ray-worker qwen|kimi
  ./start.sh serve-qwen | serve-kimi
  NODE_A=10.0.0.1:8000 NODE_B=10.0.0.2:8000 ./start.sh lb-m2
  ./start.sh status | logs <容器> | pp-logs | test <模型名> | stop
EOF
    exit 1
    ;;
esac

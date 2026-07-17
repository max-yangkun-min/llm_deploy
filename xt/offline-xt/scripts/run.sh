#!/usr/bin/env bash
# ============================================================================
# xt · 2×7×A40 · 三方案启动脚本
# ----------------------------------------------------------------------------
# 三方案(详见 大模型部署方案对比-2x7xA40.md):
#   方案一 Kimi K2.6 · PP    TP=2×PP=6=12卡(跨两台),能力天花板,最慢
#   方案二 Qwen3.5-397B · PP  TP=4×PP=2=8卡(跨两台),★推荐,强且相对稳
#   方案三 M2.7 双副本         每台1×M2.7 TP=4,最快最稳,唯一有冗余
#
# 【哪条命令在哪台机器跑】
#   方案三:两台【各自】 ./run.sh m2.7 ;  再在网关跑 ./run.sh lb-nginx
#   方案一/二:机器A ./run.sh ray-head → 机器B ./run.sh ray-worker
#             → 回机器A ./run.sh 397b(或 k2.6)→ 该 :8000 即统一入口
# ============================================================================
set -euo pipefail

# ── 按现场改这几行 ──────────────────────────────────────────────────
IMAGE="xt-vllm:0.24.0"
MODELS_DIR="/data/models"            # 三个权重的父目录(权重放 SSD)
HF_CACHE="/data/hf-cache"
NIC="ens6f0"                         # ★ 万兆光口接口名(recon 查);PP 跨机通信必须锁它
HEAD_IP="10.0.0.1"                   # 机器A(Ray head / PP stage0)IP
PORT="8000"
# ────────────────────────────────────────────────────────────────────

GPU_COMMON=(--gpus all --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 --restart no
  --log-driver local --log-opt max-size=50m --log-opt max-file=3
  -v "${MODELS_DIR}:/models:ro" -v "${HF_CACHE}:/root/.cache/huggingface")
# PP 跨机:必须 --network host 让 Ray/NCCL 走 10GbE;并锁网卡 + 关 IB
PP_ENV=(-e NCCL_SOCKET_IFNAME="${NIC}" -e GLOO_SOCKET_IFNAME="${NIC}" -e NCCL_IB_DISABLE=1)

case "${1:-}" in
  build) docker build -t "${IMAGE}" . ;;

  # ══ 方案三:M2.7 双副本(两台各跑一次,无需 Ray)══════════════════
  m2.7)
    docker run -d --name xt-m2.7 "${GPU_COMMON[@]}" -p "${PORT}:8000" \
      -e CUDA_VISIBLE_DEVICES=0,1,2,3 "${IMAGE}" \
      vllm serve /models/MiniMax-M2.7-AWQ --served-model-name minimax-m2.7 \
        --tensor-parallel-size 4 --enable-expert-parallel --quantization awq_marlin \
        --speculative-config '{"method":"mtp","num_speculative_tokens":2}' \
        --gpu-memory-utilization 0.90 --max-model-len 65536 --max-num-seqs 32 \
        --kv-cache-dtype auto --enable-prefix-caching --enable-chunked-prefill \
        --enable-auto-tool-choice --tool-call-parser minimax_m2 \
        --reasoning-parser minimax_m2_append_think --trust-remote-code --port 8000
    echo "M2.7 副本启动(卡0-3,:${PORT})。两台都起后,网关 ./run.sh lb-nginx" ;;

  # ══ 方案一/二:先起 Ray 集群(A=head,B=worker)══════════════════
  ray-head)
    docker run -d --name ray-head --network host "${GPU_COMMON[@]}" "${PP_ENV[@]}" \
      "${IMAGE}" ray start --head --port=6379 --block
    echo "Ray head 起于本机(:6379)。去机器B ./run.sh ray-worker" ;;
  ray-worker)
    docker run -d --name ray-worker --network host "${GPU_COMMON[@]}" "${PP_ENV[@]}" \
      "${IMAGE}" ray start --address="${HEAD_IP}:6379" --block
    echo "Ray worker 已加入 ${HEAD_IP}:6379。回机器A ./run.sh 397b(或 k2.6)" ;;

  # ── 方案二:Qwen3.5-397B(TP=4×PP=2=8卡),在 head 容器里 serve ──
  397b)
    docker exec -d ray-head \
      vllm serve /models/Qwen3.5-397B-A17B-AWQ --served-model-name qwen3.5-397b \
        --tensor-parallel-size 4 --pipeline-parallel-size 2 \
        --enable-expert-parallel --quantization awq_marlin \
        --gpu-memory-utilization 0.90 --max-model-len 65536 --max-num-seqs 48 \
        --kv-cache-dtype auto --enable-prefix-caching --enable-chunked-prefill \
        --enable-auto-tool-choice --tool-call-parser hermes \
        --reasoning-parser qwen3 --trust-remote-code --port 8000
    echo "397B PP 启动中(8卡)。日志:docker logs -f ray-head。入口 head:${PORT}" ;;

  # ── 方案一:Kimi K2.6(TP=2×PP=6=12卡)──
  k2.6)
    docker exec -d ray-head \
      vllm serve /models/Kimi-K2.6-AWQ --served-model-name kimi-k2.6 \
        --tensor-parallel-size 2 --pipeline-parallel-size 6 \
        --enable-expert-parallel --quantization awq_marlin \
        --gpu-memory-utilization 0.92 --max-model-len 65536 --max-num-seqs 64 \
        --kv-cache-dtype auto --enable-prefix-caching --enable-chunked-prefill \
        --enable-auto-tool-choice --tool-call-parser kimi_k2 \
        --trust-remote-code --port 8000
    echo "K2.6 PP 启动中(12卡,6段流水线,冷启动久)。日志:docker logs -f ray-head" ;;

  # ══ 方案三专用:nginx 负载均衡(在网关/其中一台跑)══════════════════
  lb-nginx)
    docker run -d --name xt-lb --network host \
      --log-driver local --log-opt max-size=10m \
      -v "$(pwd)/lb/nginx.conf:/etc/nginx/nginx.conf:ro" nginx:stable
    echo "nginx LB 起于本机 :8000(改 lb/nginx.conf 里的两台 upstream IP)" ;;

  # ══ 通用 ══
  logs)  docker logs -f "${2:-ray-head}" ;;
  test)  curl "http://localhost:${PORT}/v1/chat/completions" -H "Content-Type: application/json" \
           -d '{"model":"'"${2:-minimax-m2.7}"'","messages":[{"role":"user","content":"你好"}],"max_tokens":32}' ;;
  stop)  docker rm -f xt-m2.7 ray-head ray-worker xt-lb 2>/dev/null || true ;;

  *) echo "用法: $0 {build | m2.7 | ray-head | ray-worker | 397b | k2.6 | lb-nginx | logs [容器] | test [模型名] | stop}"; exit 1 ;;
esac

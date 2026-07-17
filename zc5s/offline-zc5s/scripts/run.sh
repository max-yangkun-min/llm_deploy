#!/usr/bin/env bash
# ============================================================================
# zc5s · 单机 8×RTX4090 48GB(Ada sm_89 / 有FP8 / 无NVLink只PCIe)· 启动脚本
# ----------------------------------------------------------------------------
# 选型(详见 大模型选型方案-8x4090-48G.md):
#   m2.7      = 🥇 M2.7 INT4 · TP=4 ×2副本(卡0-3 + 卡4-7)+ LB —— 稳健默认,有冗余,PCIe友好
#   m2.7-fp8  = 🥇 M2.7 FP8  · TP=8 ×1(8卡)—— 质量最好(FP8权重+FP8 KV,4090独有),无冗余
#   397b      = 🥈 Qwen3.5-397B INT4 · TP=8 ×1 —— 更强通用推理,TP=8走PCIe需压测
# 单机,无跨机/无Ray。无NVLink→小TP多副本比大TP更划算(故 m2.7 默认双副本)。
# ============================================================================
set -euo pipefail

IMAGE="zc5s-vllm:0.24.0"
MODELS_DIR="/data/models"            # 权重父目录(放 SSD)
HF_CACHE="/data/hf-cache"
# ────────────────────────────────────────────────────────────────────
GPU_COMMON=(--ipc=host --ulimit memlock=-1 --ulimit stack=67108864 --restart no
  --log-driver local --log-opt max-size=50m --log-opt max-file=3
  -v "${MODELS_DIR}:/models:ro" -v "${HF_CACHE}:/root/.cache/huggingface")

case "${1:-}" in
  build) docker build -t "${IMAGE}" . ;;

  # ══ 🥇 M2.7 INT4 · 双副本(卡0-3 :8001 / 卡4-7 :8002)══════════════
  m2.7)
    for r in "a 0,1,2,3 8001" "b 4,5,6,7 8002"; do set -- $r
      docker run -d --name "zc5s-m2.7-$1" "${GPU_COMMON[@]}" --gpus '"device='"$2"'"' -p "$3:8000" \
        "${IMAGE}" vllm serve /models/MiniMax-M2.7-AWQ --served-model-name minimax-m2.7 \
          --tensor-parallel-size 4 --enable-expert-parallel --quantization awq_marlin \
          --speculative-config '{"method":"mtp","num_speculative_tokens":2}' \
          --gpu-memory-utilization 0.90 --max-model-len 65536 --max-num-seqs 32 \
          --kv-cache-dtype auto --enable-prefix-caching --enable-chunked-prefill \
          --enable-auto-tool-choice --tool-call-parser minimax_m2 \
          --reasoning-parser minimax_m2_append_think --trust-remote-code --port 8000
    done
    echo "M2.7 双副本起(:8001 :8002)。再 ./run.sh lb-nginx 聚成 :8000" ;;

  # ══ 🥇 M2.7 FP8 · 单副本 8卡(质量优先,用上4090的FP8)══════════════
  m2.7-fp8)
    docker run -d --name zc5s-m2.7 "${GPU_COMMON[@]}" --gpus all -p 8000:8000 \
      "${IMAGE}" vllm serve /models/MiniMax-M2.7-FP8 --served-model-name minimax-m2.7 \
        --tensor-parallel-size 8 --enable-expert-parallel --quantization fp8 \
        --kv-cache-dtype fp8 \
        --gpu-memory-utilization 0.90 --max-model-len 65536 --max-num-seqs 32 \
        --enable-prefix-caching --enable-chunked-prefill \
        --enable-auto-tool-choice --tool-call-parser minimax_m2 \
        --reasoning-parser minimax_m2_append_think --trust-remote-code --port 8000
    echo "M2.7 FP8 单副本起(8卡,:8000)。质量最好、无冗余;TP=8走PCIe,压测单路" ;;

  # ══ 🥈 Qwen3.5-397B INT4 · 单副本 8卡 ══════════════════════════════
  397b)
    docker run -d --name zc5s-397b "${GPU_COMMON[@]}" --gpus all -p 8000:8000 \
      "${IMAGE}" vllm serve /models/Qwen3.5-397B-A17B-AWQ --served-model-name qwen3.5-397b \
        --tensor-parallel-size 8 --enable-expert-parallel --quantization awq_marlin \
        --gpu-memory-utilization 0.90 --max-model-len 65536 --max-num-seqs 48 \
        --kv-cache-dtype fp8 --enable-prefix-caching --enable-chunked-prefill \
        --enable-auto-tool-choice --tool-call-parser hermes \
        --reasoning-parser qwen3 --trust-remote-code --port 8000
    echo "397B 起(8卡,:8000)。TP=8纯PCIe通信重,务必压测单路tok/s" ;;

  # ══ M2.7 双副本的负载均衡 ══
  lb-nginx)
    docker run -d --name zc5s-lb --network host --log-driver local --log-opt max-size=10m \
      -v "$(pwd)/lb/nginx.conf:/etc/nginx/nginx.conf:ro" nginx:stable
    echo "nginx LB 起 :8000(聚合本机 :8001 :8002)" ;;

  logs)  docker logs -f "${2:-zc5s-397b}" ;;
  test)  curl "http://localhost:${2:-8000}/v1/chat/completions" -H "Content-Type: application/json" \
           -d '{"model":"minimax-m2.7","messages":[{"role":"user","content":"你好"}],"max_tokens":32}' ;;
  stop)  docker rm -f zc5s-m2.7-a zc5s-m2.7-b zc5s-m2.7 zc5s-397b zc5s-lb 2>/dev/null || true ;;

  *) echo "用法: $0 {build | m2.7 | m2.7-fp8 | 397b | lb-nginx | logs [容器] | test [端口] | stop}"; exit 1 ;;
esac

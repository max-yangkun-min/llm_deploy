#!/usr/bin/env bash
# ============================================================================
# xt · 14×A40 双机 · 7+7 三个主方案 + 8+6 备用方案启动脚本
# ----------------------------------------------------------------------------
# 主方案(详见 大模型部署方案对比-2x7xA40.md):
#   方案一 Kimi K2.6 · PP    TP=2×PP=6=12卡(跨两台),能力天花板,最慢
#   方案二 Qwen3.5-397B · PP  TP=4×PP=2=8卡(跨两台),★推荐,强且相对稳
#   方案三 M2.7 双副本         每台1×M2.7 TP=4,最快最稳,唯一有冗余
#   备用四 8+6 双层模型        8卡机397B本地TP=4×PP=2;6卡机M2.7 TP=4
#
# 【哪条命令在哪台机器跑】
#   方案三:两台【各自】 ./run.sh m2.7 ;  再在网关跑 ./run.sh lb-nginx
#   方案一/二:机器A ./run.sh ray-head → 机器B ./run.sh ray-worker
#             → 回机器A ./run.sh 397b(或 k2.6)→ 该 :8000 即统一入口
#   备用四:8卡机 ./run.sh 397b-8gpu ; 6卡机 ./run.sh m2.7
# ============================================================================
set -euo pipefail

# ── 按现场改这几行 ──────────────────────────────────────────────────
VLLM_TAG="${VLLM_TAG:-v0.24.0}"
VLLM_BASE_IMAGE="${VLLM_BASE_IMAGE:-vllm/vllm-openai:${VLLM_TAG}}"
IMAGE="${IMAGE:-xt-vllm:${VLLM_TAG#v}-cu124}" # CUDA 12.4验收镜像;两台必须相同
MODELS_DIR="/data/models"            # 三个权重的父目录(权重放 SSD)
HF_CACHE="/data/hf-cache"
NIC="ens6f0"                         # ★ 万兆光口接口名(recon 查);PP 跨机通信必须锁它
HEAD_IP="10.0.0.1"                   # 机器A(Ray head / PP stage0)IP
PORT="8000"
LB_PORT="${LB_PORT:-9000}"              # M2.7双副本统一入口;避开本机模型的8000端口
# 跨机Ray参与建模的物理卡编号。K2.6两台各6卡;397B两台各4卡。
# 必须按 recon.sh 的 topo 结果选择,不要默认认为前N张卡拓扑最好。
RAY_GPU_DEVICES="${RAY_GPU_DEVICES:-0,1,2,3,4,5}"
# ────────────────────────────────────────────────────────────────────

GPU_COMMON=(--gpus all --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 --restart no
  --log-driver local --log-opt max-size=50m --log-opt max-file=3
  -v "${MODELS_DIR}:/models:ro" -v "${HF_CACHE}:/root/.cache/huggingface")
# PP 跨机:必须 --network host 让 Ray/NCCL 走 10GbE;并锁网卡 + 关 IB
PP_ENV=(-e CUDA_VISIBLE_DEVICES="${RAY_GPU_DEVICES}"
  -e NCCL_SOCKET_IFNAME="${NIC}" -e GLOO_SOCKET_IFNAME="${NIC}" -e NCCL_IB_DISABLE=1)

case "${1:-}" in
  build) docker build --build-arg VLLM_TAG="${VLLM_TAG}" \
           --build-arg VLLM_BASE_IMAGE="${VLLM_BASE_IMAGE}" \
           --build-arg CUDA_COMPAT=12.4 -t "${IMAGE}" . \
         && IMAGE="${IMAGE}" bash ./verify-cuda124.sh --image-only ;;

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
    echo "M2.7 已启动(卡0-3,:${PORT})。方案三需两台都起后再启动LB;备用四只在6卡机起一个实例" ;;

  # ══ 备用方案四:8卡机单机397B,本机TP=4×PP=2,无需跨机Ray ══
  397b-8gpu)
    docker run -d --name xt-397b-8gpu "${GPU_COMMON[@]}" -p "${PORT}:8000" \
      -e CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 "${IMAGE}" \
      vllm serve /models/Qwen3.5-397B-A17B-AWQ --served-model-name qwen3.5-397b \
        --tensor-parallel-size 4 --pipeline-parallel-size 2 \
        --distributed-executor-backend mp \
        --enable-expert-parallel --quantization awq_marlin \
        --gpu-memory-utilization 0.90 --max-model-len 65536 --max-num-seqs 48 \
        --kv-cache-dtype auto --enable-prefix-caching --enable-chunked-prefill \
        --enable-auto-tool-choice --tool-call-parser hermes \
        --reasoning-parser qwen3 --trust-remote-code --port 8000
    echo "397B 单机8卡启动中(TP=4×PP=2,:${PORT})。日志:docker logs -f xt-397b-8gpu" ;;

  # ══ 方案一/二:先起 Ray 集群(A=head,B=worker)══════════════════
  ray-head)
    docker run -d --name ray-head --network host "${GPU_COMMON[@]}" "${PP_ENV[@]}" \
      "${IMAGE}" ray start --head --port=6379 --block
    echo "Ray head 起于本机(:6379),可见卡=${RAY_GPU_DEVICES}。去机器B用相同卡数启动ray-worker" ;;
  ray-worker)
    docker run -d --name ray-worker --network host "${GPU_COMMON[@]}" "${PP_ENV[@]}" \
      "${IMAGE}" ray start --address="${HEAD_IP}:6379" --block
    echo "Ray worker 已加入 ${HEAD_IP}:6379,可见卡=${RAY_GPU_DEVICES}。回机器A启动模型" ;;

  # ── 方案二:Qwen3.5-397B(TP=4×PP=2=8卡),在 head 容器里 serve ──
  397b)
    docker exec -d ray-head bash -lc '
      exec vllm serve /models/Qwen3.5-397B-A17B-AWQ --served-model-name qwen3.5-397b \
        --tensor-parallel-size 4 --pipeline-parallel-size 2 \
        --enable-expert-parallel --quantization awq_marlin \
        --gpu-memory-utilization 0.90 --max-model-len 65536 --max-num-seqs 48 \
        --kv-cache-dtype auto --enable-prefix-caching --enable-chunked-prefill \
        --enable-auto-tool-choice --tool-call-parser hermes \
        --reasoning-parser qwen3 --trust-remote-code --port 8000 \
        > /tmp/vllm-serve.log 2>&1'
    echo "397B PP 启动中(8卡)。模型日志:./run.sh pp-logs。入口 head:${PORT}" ;;

  # ── 方案一:Kimi K2.6(TP=2×PP=6=12卡)──
  k2.6)
    docker exec -d ray-head bash -lc '
      exec vllm serve /models/Kimi-K2.6-AWQ --served-model-name kimi-k2.6 \
        --tensor-parallel-size 2 --pipeline-parallel-size 6 \
        --enable-expert-parallel --quantization awq_marlin \
        --gpu-memory-utilization 0.92 --max-model-len 65536 --max-num-seqs 64 \
        --kv-cache-dtype auto --enable-prefix-caching --enable-chunked-prefill \
        --enable-auto-tool-choice --tool-call-parser kimi_k2 \
        --trust-remote-code --port 8000 \
        > /tmp/vllm-serve.log 2>&1'
    echo "K2.6 PP 启动中(12卡,6段流水线,冷启动久)。模型日志:./run.sh pp-logs" ;;

  # ══ 方案三专用:nginx 负载均衡(在网关/其中一台跑)══════════════════
  lb-nginx)
    docker run -d --name xt-lb -p "${LB_PORT}:8000" \
      --log-driver local --log-opt max-size=10m \
      -v "$(pwd)/lb/nginx.conf:/etc/nginx/nginx.conf:ro" nginx:stable
    echo "nginx LB 起于本机 :${LB_PORT}(改 lb/nginx.conf 里的两台 upstream IP)" ;;

  # ══ 通用 ══
  logs)  docker logs -f "${2:-ray-head}" ;;
  pp-logs) docker exec ray-head bash -lc '
             while [ ! -f /tmp/vllm-serve.log ]; do sleep 1; done
             tail -f /tmp/vllm-serve.log' ;;
  test)  curl "http://localhost:${PORT}/v1/chat/completions" -H "Content-Type: application/json" \
           -d '{"model":"'"${2:-minimax-m2.7}"'","messages":[{"role":"user","content":"你好"}],"max_tokens":32}' ;;
  stop)  docker rm -f xt-m2.7 xt-397b-8gpu ray-head ray-worker xt-lb 2>/dev/null || true ;;

  *) echo "用法: $0 {build | m2.7 | 397b-8gpu | ray-head | ray-worker | 397b | k2.6 | lb-nginx | logs [容器] | pp-logs | test [模型名] | stop}"; exit 1 ;;
esac

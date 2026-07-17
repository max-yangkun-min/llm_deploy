#!/usr/bin/env bash
# ============================================================================
# GLM-5.2 · 8×A100 80GB PCIe · 构建 + 分阶段启动
# 用法:
#   ./run.sh build            # 构建镜像
#   ./run.sh smoke            # 阶段1:Qwen3-8B 只验 TP=8/NCCL 通路(诊断用,2 分钟即弃,不对外服务)
#   ./run.sh stage3           # 阶段3:原样复现已验证配置(32K/util0.90)—— 已知 good
#   ./run.sh target           # 目标档:64K/16 路 + prefix cache + 工具调用
#   ./run.sh logs / test / stop
# ============================================================================
set -euo pipefail

# ── 按你的机器改这几行 ──────────────────────────────────────────────
IMAGE="glm52-vllm:0.24.0-pr38476"
VLLM_REF="v0.24.0"                                   # 锁定的 vLLM tag,与 Dockerfile 一致
MODEL_DIR="/data/models/GLM-5.2-AWQ-INT4"            # GLM-5.2 权重(唯一)
SMOKE_DIR="/data/models/Qwen3-8B"                    # 阶段1 诊断小模型(只验通路,不服务)
HF_CACHE="/data/hf-cache"
NAME="glm52"
PORT="8000"
# 拓扑定了再决定:PIX/PXB 保持 0;topo=SYS 或 P2P 有问题时置 1(备案 A)
NCCL_P2P_DISABLE="${NCCL_P2P_DISABLE:-0}"
# ────────────────────────────────────────────────────────────────────

# 统一的 docker run 封装。
#   $1 宿主权重目录  $2 容器内挂载路径  $3 注意力后端(""=置空让 vLLM 自动选)
#   其后所有参数 = 传给容器的完整启动命令(vllm serve ...)
# 日志用 local 驱动 + 轮转封顶:既能看启动必须验证的兜底两行 + KV cache size,
# 又不会让 vLLM 的大 stdout 全量落盘撑爆系统盘(全局硬规则)。
run_vllm() {
  local host="$1" cpath="$2" attn="$3"; shift 3
  docker run -d --name "${NAME}" \
    --gpus all --ipc=host \
    --ulimit memlock=-1 --ulimit stack=67108864 \
    --restart no \
    --log-driver local --log-opt max-size=50m --log-opt max-file=3 \
    -p "${PORT}:8000" \
    -v "${host}:${cpath}:ro" \
    -v "${HF_CACHE}:/root/.cache/huggingface" \
    -e NCCL_P2P_DISABLE="${NCCL_P2P_DISABLE}" \
    -e VLLM_ATTENTION_BACKEND="${attn}" \
    "${IMAGE}" "$@"
  echo "启动中。跟日志:./run.sh logs"
}

case "${1:-}" in
  build)
    docker build --build-arg VLLM_REF="${VLLM_REF}" -t "${IMAGE}" .
    ;;

  # ── 阶段1:小模型只验 TP=8 / NCCL / 拓扑,是诊断手段不是服务 ──
  # Qwen3-8B 非稀疏模型,后端置空让 vLLM 自动选(别套 GLM 的 TRITON_MLA_SPARSE);验完即 stop。
  smoke)
    run_vllm "${SMOKE_DIR}" /models/Qwen3-8B "" \
      vllm serve /models/Qwen3-8B --tensor-parallel-size 8 --port 8000
    echo "smoke:能对话=NCCL/TP=8 通;卡死=拓扑/NCCL 问题(见备案 A)。验完 ./run.sh stop 再上 GLM"
    ;;

  # ── 阶段3:一个字都别改的"已知 good"基准(部署步骤阶段5)──
  # GLM 必须用镜像里写死的 TRITON_MLA_SPARSE,这里显式再传一遍以防被覆盖。
  stage3)
    run_vllm "${MODEL_DIR}" /models/GLM-5.2-AWQ-INT4 TRITON_MLA_SPARSE \
      vllm serve /models/GLM-5.2-AWQ-INT4 \
        --served-model-name glm-5.2 \
        --tensor-parallel-size 8 \
        --no-async-scheduling \
        --gpu-memory-utilization 0.90 \
        --max-model-len 32768 \
        --trust-remote-code \
        --kv-cache-dtype auto \
        --port 8000
    echo "冷启动 ~7 分钟。日志必须有兜底两行,否则停(见部署步骤阶段5)"
    ;;

  # ── 目标档:64K/16 路 + prefix cache + chunked prefill + 工具调用三件套 ──
  target)
    run_vllm "${MODEL_DIR}" /models/GLM-5.2-AWQ-INT4 TRITON_MLA_SPARSE \
      vllm serve /models/GLM-5.2-AWQ-INT4 \
        --served-model-name glm-5.2 \
        --tensor-parallel-size 8 \
        --no-async-scheduling \
        --gpu-memory-utilization 0.90 \
        --max-model-len 65536 \
        --max-num-seqs 16 \
        --trust-remote-code \
        --kv-cache-dtype auto \
        --enable-prefix-caching \
        --enable-chunked-prefill \
        --max-num-batched-tokens 8192 \
        --enable-auto-tool-choice \
        --tool-call-parser glm47 \
        --reasoning-parser glm45 \
        --port 8000
    echo "冷启动 ~7 分钟。仅在 stage3 跑通、KV 够用后再上"
    ;;

  logs)
    # GLM 必须看到:
    #   [cuda.py] Using TRITON_MLA_SPARSE attention backend
    #   [sparse_attn_indexer.py] DeepGEMM not supported ...; using Triton fallback
    #   GPU KV cache size: XXX tokens   ← 反推并发 = 这个数 / max-model-len
    docker logs -f "${NAME}"
    ;;

  test)
    curl "http://localhost:${PORT}/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -d '{"model":"glm-5.2","messages":[{"role":"user","content":"你好"}],"max_tokens":64}'
    ;;

  stop)
    docker rm -f "${NAME}" 2>/dev/null || true
    ;;

  *)
    echo "用法: $0 {build|smoke|stage3|target|logs|test|stop}"
    exit 1
    ;;
esac

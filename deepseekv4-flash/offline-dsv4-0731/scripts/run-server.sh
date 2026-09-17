#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH=${MODEL_PATH:-/models/DeepSeek-V4-Flash-0731-w8a8}
PORT=${PORT:-8000}
MAX_MODEL_LEN=${MAX_MODEL_LEN:-65536}
MAX_NUM_SEQS=${MAX_NUM_SEQS:-4}
MAX_BATCHED_TOKENS=${MAX_BATCHED_TOKENS:-4096}
GPU_MEMORY_UTILIZATION=${GPU_MEMORY_UTILIZATION:-0.90}
SPECULATIVE_METHOD=${SPECULATIVE_METHOD:-dspark}
NUM_SPECULATIVE_TOKENS=${NUM_SPECULATIVE_TOKENS:-7}

for candidate in \
  /usr/lib/aarch64-linux-gnu/libjemalloc.so.2 \
  /usr/lib/x86_64-linux-gnu/libjemalloc.so.2; do
  if [[ -f "$candidate" ]]; then
    export LD_PRELOAD="$candidate${LD_PRELOAD:+:$LD_PRELOAD}"
    break
  fi
done

export OMP_PROC_BIND=${OMP_PROC_BIND:-false}
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-10}
export PYTORCH_NPU_ALLOC_CONF=${PYTORCH_NPU_ALLOC_CONF:-expandable_segments:True}
export HCCL_BUFFSIZE=${HCCL_BUFFSIZE:-1024}
export VLLM_ASCEND_ENABLE_FLASHCOMM1=${VLLM_ASCEND_ENABLE_FLASHCOMM1:-0}
export VLLM_ASCEND_ENABLE_FUSED_MC2=${VLLM_ASCEND_ENABLE_FUSED_MC2:-0}
export TASK_QUEUE_ENABLE=${TASK_QUEUE_ENABLE:-1}
export HCCL_OP_EXPANSION_MODE=${HCCL_OP_EXPANSION_MODE:-AIV}

exec vllm serve "$MODEL_PATH" \
  --host 0.0.0.0 \
  --port "$PORT" \
  --served-model-name deepseek-v4-flash-0731 \
  --trust-remote-code \
  --max-model-len "$MAX_MODEL_LEN" \
  --max-num-batched-tokens "$MAX_BATCHED_TOKENS" \
  --max-num-seqs "$MAX_NUM_SEQS" \
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
  --data-parallel-size 1 \
  --tensor-parallel-size 8 \
  --enable-expert-parallel \
  --tokenizer-mode deepseek_v4 \
  --tool-call-parser deepseek_v4 \
  --enable-auto-tool-choice \
  --reasoning-parser deepseek_v4 \
  --safetensors-load-strategy prefetch \
  --model-loader-extra-config '{"num_threads":128}' \
  --quantization ascend \
  --block-size 128 \
  --no-enable-prefix-caching \
  --no-disable-hybrid-kv-cache-manager \
  --speculative-config "{\"num_speculative_tokens\":${NUM_SPECULATIVE_TOKENS},\"method\":\"${SPECULATIVE_METHOD}\",\"enforce_eager\":true}" \
  --compilation-config '{"cudagraph_mode":"FULL_DECODE_ONLY"}'

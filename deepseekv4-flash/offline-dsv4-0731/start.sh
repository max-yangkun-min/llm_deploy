#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MODEL_DIR=${MODEL_DIR:-$ROOT_DIR/models/DeepSeek-V4-Flash-0731-w8a8}
CONTAINER_NAME=${CONTAINER_NAME:-deepseek-v4-flash-0731}
OCI_INDEX_DIGEST=sha256:ade04e75aa4a888df5dfb7917f21e7d9178014d5f5e52b358f2cd1d8897f46ce
ARM64_MANIFEST_DIGEST=sha256:8dd01aa0e0e5c4b04d3d715f483351af24c626c30373215e74238cf389fc2a93
AMD64_MANIFEST_DIGEST=sha256:05dab76f136f78db6bdf5c1e6d5cb1f6085d451fbcd219e0e6b37768f43f7227
REMOTE_IMAGE=${REMOTE_IMAGE:-m.daocloud.io/quay.io/ascend/vllm-ascend@${OCI_INDEX_DIGEST}}
IMAGE_ID=${IMAGE_ID:-${OCI_INDEX_DIGEST}}
ARCH=${ARCH:-arm64}
IMAGE=${IMAGE:-deepseek-v4-flash/vllm-ascend:20260804-${ARCH}}
IMAGE_TAR=${IMAGE_TAR:-$ROOT_DIR/images/vllm-ascend-nightly-main-20260804-${ARCH}.tar}
PORT=${PORT:-8000}
MAX_MODEL_LEN=${MAX_MODEL_LEN:-65536}
MAX_NUM_SEQS=${MAX_NUM_SEQS:-4}
MAX_BATCHED_TOKENS=${MAX_BATCHED_TOKENS:-4096}
GPU_MEMORY_UTILIZATION=${GPU_MEMORY_UTILIZATION:-0.90}
SPECULATIVE_METHOD=${SPECULATIVE_METHOD:-dspark}
NUM_SPECULATIVE_TOKENS=${NUM_SPECULATIVE_TOKENS:-7}
DOWNLOAD_JOBS=${DOWNLOAD_JOBS:-2}
ALLOW_BUSY_NPU=${ALLOW_BUSY_NPU:-0}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

device_args=()
mount_args=()

build_runtime_args() {
  device_args=()
  mount_args=()
  local i
  for i in $(seq 0 7); do
    [[ -c "/dev/davinci$i" ]] || die "missing /dev/davinci$i"
    device_args+=(--device "/dev/davinci$i")
  done
  for node in /dev/davinci_manager /dev/devmm_svm /dev/hisi_hdc; do
    [[ -e "$node" ]] && device_args+=(--device "$node")
  done
  [[ -e /dev/davinci_manager ]] || die "missing /dev/davinci_manager"
  [[ -e /dev/devmm_svm ]] || die "missing /dev/devmm_svm"

  local source target
  while IFS='|' read -r source target; do
    [[ -e "$source" ]] && mount_args+=(-v "$source:$target:ro")
  done <<'EOF'
/usr/local/dcmi|/usr/local/dcmi
/usr/local/Ascend/driver/tools/hccn_tool|/usr/local/Ascend/driver/tools/hccn_tool
/usr/local/bin/npu-smi|/usr/local/bin/npu-smi
/usr/local/Ascend/driver/lib64|/usr/local/Ascend/driver/lib64
/usr/local/Ascend/driver/version.info|/usr/local/Ascend/driver/version.info
/etc/ascend_install.info|/etc/ascend_install.info
/etc/hccn.conf|/etc/hccn.conf
EOF
}

model_verify() {
  require python3
  python3 "$ROOT_DIR/scripts/verify_model.py" "$MODEL_DIR" "$@"
}

check_busy_npu() {
  local info
  info=$(npu-smi info 2>/dev/null || true)
  if grep -qE 'VLLMWorker|python|mindie|ray::' <<<"$info"; then
    if [[ "$ALLOW_BUSY_NPU" != "1" ]]; then
      echo "$info"
      die "other NPU processes are active; stop them or explicitly set ALLOW_BUSY_NPU=1"
    fi
    echo "WARNING: continuing although other NPU processes were detected"
  fi
}

cmd_pull() {
  require docker
  docker pull --platform "linux/${ARCH}" "$REMOTE_IMAGE"
  local image_id architecture
  image_id=$(docker image inspect "$REMOTE_IMAGE" --format '{{.Id}}')
  architecture=$(docker image inspect "$REMOTE_IMAGE" --format '{{.Architecture}}')
  [[ "$architecture" == "$ARCH" ]] || \
    die "pulled image architecture ($architecture) does not match ARCH=$ARCH"
  [[ "$image_id" == "$IMAGE_ID" ]] || die "pulled image ID does not match: $image_id"
  docker image tag "$IMAGE_ID" "$IMAGE"
  echo "OK: pulled and tagged pinned image as $IMAGE ($architecture)"
}

cmd_load() {
  require docker
  [[ -f "$IMAGE_TAR" ]] || die "missing offline image archive: $IMAGE_TAR"
  docker load --input "$IMAGE_TAR"
  local image_id architecture
  image_id=$(docker image inspect "$IMAGE_ID" --format '{{.Id}}')
  architecture=$(docker image inspect "$IMAGE_ID" --format '{{.Architecture}}')
  [[ "$image_id" == "$IMAGE_ID" ]] || \
    die "loaded image ID does not match the pinned OCI digest: $image_id"
  [[ "$architecture" == "$ARCH" ]] || \
    die "expected $ARCH image, found: $architecture"
  docker image tag "$IMAGE_ID" "$IMAGE"
  echo "OK: loaded pinned vLLM Ascend image $image_id ($architecture) as $IMAGE"
}

cmd_download() {
  require python3
  require curl
  mkdir -p "$MODEL_DIR"
  python3 "$ROOT_DIR/scripts/download_model.py" \
    --output "$MODEL_DIR" --jobs "$DOWNLOAD_JOBS"
}

cmd_verify() {
  model_verify --full
}

cmd_preflight() {
  require docker
  require npu-smi
  docker info >/dev/null
  build_runtime_args
  local count
  count=$(npu-smi info 2>/dev/null | grep -c '910B4-1' || true)
  [[ "$count" -ge 8 ]] || die "expected 8 Ascend 910B4-1 devices, found $count"
  check_busy_npu
  model_verify
  echo "OK: preflight passed for 8x910B4-1"
}

cmd_diagnose() {
  require docker
  build_runtime_args
  docker run --rm --privileged --net=host \
    "${device_args[@]}" "${mount_args[@]}" \
    "$IMAGE" python3 -c \
    'import torch, torch_npu, vllm, vllm_ascend; print("torch", torch.__version__); print("torch_npu", torch_npu.__version__); print("vllm", vllm.__version__); print("vllm_ascend", getattr(vllm_ascend, "__version__", "unknown")); print("npu_count", torch.npu.device_count()); assert torch.npu.device_count() == 8'
}

cmd_start() {
  cmd_preflight
  if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    docker rm -f "$CONTAINER_NAME" >/dev/null
  fi
  docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    --privileged \
    --net=host \
    --shm-size=512g \
    "${device_args[@]}" \
    "${mount_args[@]}" \
    -v "$MODEL_DIR:/models/DeepSeek-V4-Flash-0731-w8a8:ro" \
    -v "$ROOT_DIR/scripts/run-server.sh:/opt/dsv4/run-server.sh:ro" \
    -e PORT="$PORT" \
    -e MAX_MODEL_LEN="$MAX_MODEL_LEN" \
    -e MAX_NUM_SEQS="$MAX_NUM_SEQS" \
    -e MAX_BATCHED_TOKENS="$MAX_BATCHED_TOKENS" \
    -e GPU_MEMORY_UTILIZATION="$GPU_MEMORY_UTILIZATION" \
    -e SPECULATIVE_METHOD="$SPECULATIVE_METHOD" \
    -e NUM_SPECULATIVE_TOKENS="$NUM_SPECULATIVE_TOKENS" \
    "$IMAGE" bash /opt/dsv4/run-server.sh
  echo "Started $CONTAINER_NAME; follow model loading with: ./start.sh logs"
}

cmd_logs() {
  require docker
  docker logs -f --tail 200 "$CONTAINER_NAME"
}

cmd_status() {
  require docker
  docker ps -a --filter "name=^/${CONTAINER_NAME}$"
  npu-smi info || true
}

cmd_test() {
  require curl
  require python3
  curl --fail --silent --show-error "http://127.0.0.1:$PORT/v1/models"
  echo
  curl --fail --silent --show-error \
    "http://127.0.0.1:$PORT/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -d '{"model":"deepseek-v4-flash-0731","messages":[{"role":"user","content":"用一句话说明你是谁。"}],"max_tokens":128,"temperature":0}'
  echo

  local tool_response
  tool_response=$(mktemp)
  curl --fail --silent --show-error \
    "http://127.0.0.1:$PORT/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    --data-binary @- >"$tool_response" <<'JSON'
{"model":"deepseek-v4-flash-0731","messages":[{"role":"user","content":"北京现在天气怎么样？请调用工具查询。"}],"tools":[{"type":"function","function":{"name":"get_weather","description":"查询指定城市的实时天气","parameters":{"type":"object","properties":{"city":{"type":"string","description":"城市名称"}},"required":["city"]}}}],"tool_choice":"auto","max_tokens":256,"temperature":0}
JSON
  python3 - "$tool_response" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as response_file:
    response = json.load(response_file)
tool_calls = response["choices"][0]["message"].get("tool_calls") or []
if not tool_calls:
    raise SystemExit("tool calling test failed: response contains no tool_calls")
if tool_calls[0].get("function", {}).get("name") != "get_weather":
    raise SystemExit("tool calling test failed: unexpected function name")
print("OK: tool calling returned get_weather")
PY
  rm -f "$tool_response"
}

cmd_stop() {
  require docker
  docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
  docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
}

usage() {
  cat <<'EOF'
Usage: ./start.sh <command>

Commands:
  load       Load and verify the bundled ${ARCH} image archive without network
  pull       Pull the pinned multi-arch image (linux/${ARCH}) from the domestic mirror (fallback)
  download   Resume the pinned ModelScope model download and verify each file
  verify     Re-hash the complete model snapshot
  preflight  Check Docker, 8 NPUs, free devices, and model structure
  diagnose   Verify torch/torch_npu/vLLM and all 8 NPUs inside the container
  start      Start the OpenAI-compatible service
  logs       Follow service logs
  status     Show container and NPU status
  test       Run API smoke tests
  stop       Stop and remove only this deployment's container
EOF
}

case "${1:-}" in
  load) cmd_load ;;
  pull) cmd_pull ;;
  download) cmd_download ;;
  verify) cmd_verify ;;
  preflight) cmd_preflight ;;
  diagnose) cmd_diagnose ;;
  start) cmd_start ;;
  logs) cmd_logs ;;
  status) cmd_status ;;
  test) cmd_test ;;
  stop) cmd_stop ;;
  *) usage; exit 2 ;;
esac

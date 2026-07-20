#!/usr/bin/env bash
# XT CUDA 12.4 兼容性验收。联网构建机可不带 GPU 使用 --image-only;
# 两台离线服务器安装后必须执行完整检查。
set -euo pipefail

IMAGE="${IMAGE:-xt-vllm:0.24.0-cu124}"
MIN_DRIVER="${MIN_DRIVER:-550.54.15}"
EXPECTED_CUDA="${EXPECTED_CUDA:-12.4}"
MODE="${1:-full}"

version_ge() {
  [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

echo "== CUDA 12.4 镜像检查: ${IMAGE} =="
docker image inspect "${IMAGE}" >/dev/null 2>&1 || {
  echo "!! 未找到镜像 ${IMAGE};先运行 install-offline.sh 或设置 IMAGE="
  exit 1
}

LABEL_PROFILE="$(docker image inspect -f '{{ index .Config.Labels "org.blade-agent.cuda-profile" }}' "${IMAGE}")"
[ "${LABEL_PROFILE}" = "cu124" ] || {
  echo "!! 镜像标签不是 cu124(profile=${LABEL_PROFILE:-missing}),拒绝继续"
  exit 1
}

docker run --rm -e EXPECTED_CUDA="${EXPECTED_CUDA}" --entrypoint python3 "${IMAGE}" -c '
import os, torch, vllm, ray
expected = os.environ["EXPECTED_CUDA"]
actual = torch.version.cuda or ""
assert actual == expected or actual.startswith(expected + "."), (expected, actual)
print("torch_cuda=", actual)
print("torch=", torch.__version__)
print("vllm=", vllm.__version__)
print("ray=", ray.__version__)
'

[ "${MODE}" = "--image-only" ] && {
  echo "PASS:镜像内运行时为 CUDA ${EXPECTED_CUDA};GPU/驱动留到离线服务器检查"
  exit 0
}

command -v nvidia-smi >/dev/null 2>&1 || { echo "!! 无 nvidia-smi"; exit 1; }
DRIVER="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n1 | tr -d '[:space:]')"
version_ge "${DRIVER}" "${MIN_DRIVER}" || {
  echo "!! 驱动 ${DRIVER} 低于 CUDA 12.4 基线 ${MIN_DRIVER}"
  exit 1
}
echo "host_driver=${DRIVER} (>=${MIN_DRIVER})"

docker info 2>/dev/null | grep -qi nvidia || { echo "!! Docker 未配置 nvidia runtime"; exit 1; }
docker run --rm --gpus all --entrypoint python3 "${IMAGE}" -c '
import torch
assert torch.cuda.is_available(), "CUDA unavailable in container"
count = torch.cuda.device_count()
assert count > 0, "no GPU"
for i in range(count):
    cap = torch.cuda.get_device_capability(i)
    print(f"gpu[{i}]={torch.cuda.get_device_name(i)} capability={cap[0]}.{cap[1]}")
    assert cap == (8, 6), f"GPU {i} is not A40/sm_86: {cap}"
'

echo "PASS:宿主驱动、nvidia runtime、CUDA ${EXPECTED_CUDA} 容器和 A40(sm_86) 全部通过"

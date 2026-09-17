#!/usr/bin/env bash
# XT CUDA 12.9 Forward Compatibility验收。
# 联网构建机可不带GPU使用--image-only;两台A40离线服务器必须执行完整检查。
set -euo pipefail

IMAGE="${IMAGE:-xt-vllm:0.24.0-cu129-compat545}"
MIN_DRIVER="${MIN_DRIVER:-545.0}"
NATIVE_DRIVER="${NATIVE_DRIVER:-575.51.03}"
EXPECTED_CUDA="${EXPECTED_CUDA:-12.9}"
EXPECTED_RAY="${EXPECTED_RAY:-2.56.1}"
MODE="${1:-full}"

version_ge() {
  [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

echo "== CUDA 12.9 Forward Compatibility镜像检查:${IMAGE} =="
docker image inspect "${IMAGE}" >/dev/null 2>&1 || {
  echo "!! 未找到镜像${IMAGE};先运行install-offline.sh或设置IMAGE="
  exit 1
}

LABEL_PROFILE="$(docker image inspect -f '{{ index .Config.Labels "org.blade-agent.cuda-profile" }}' "${IMAGE}")"
[ "${LABEL_PROFILE}" = "cu129-compat545" ] || {
  echo "!! 镜像标签不是cu129-compat545(profile=${LABEL_PROFILE:-missing}),拒绝继续"
  exit 1
}
LABEL_545_POLICY="$(docker image inspect -f '{{ index .Config.Labels "org.blade-agent.driver-545-policy" }}' "${IMAGE}")"
[ "${LABEL_545_POLICY}" = "conditional-real-a40-validation-required" ] || {
  echo "!! 缺少R545条件兼容策略标签,拒绝继续"
  exit 1
}

docker run --rm -e EXPECTED_CUDA="${EXPECTED_CUDA}" -e EXPECTED_RAY="${EXPECTED_RAY}" \
  --entrypoint python3 "${IMAGE}" -c '
import os, pathlib, torch, vllm, ray
actual = torch.version.cuda or ""
expected = os.environ["EXPECTED_CUDA"]
assert actual == expected or actual.startswith(expected + "."), (expected, actual)
assert ray.__version__ == os.environ["EXPECTED_RAY"], (ray.__version__, os.environ["EXPECTED_RAY"])
assert pathlib.Path("/usr/local/cuda-12.9/compat/libcuda.so.1").exists()
print("torch_cuda=", actual)
print("torch=", torch.__version__)
print("vllm=", vllm.__version__)
print("ray=", ray.__version__)
print("cuda_compat=cuda-compat-12-9")
'
docker run --rm --entrypoint nginx "${IMAGE}" -v 2>&1 | grep -q '^nginx version:' || {
  echo "!! 镜像内nginx网关不可用"
  exit 1
}

[ "${MODE}" = "--image-only" ] && {
  echo "PASS:镜像内CUDA ${EXPECTED_CUDA}、Ray ${EXPECTED_RAY}、cuda-compat-12-9和nginx通过;GPU/PTX JIT留到A40服务器检查"
  exit 0
}

command -v nvidia-smi >/dev/null 2>&1 || { echo "!! 无nvidia-smi"; exit 1; }
DRIVER="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n1 | tr -d '[:space:]')"
version_ge "${DRIVER}" "${MIN_DRIVER}" || {
  echo "!! 驱动${DRIVER}低于Forward Compatibility策略下限${MIN_DRIVER}"
  exit 1
}
if version_ge "${DRIVER}" "${NATIVE_DRIVER}"; then
  echo "host_driver=${DRIVER}(达到CUDA 12.9原生驱动基线${NATIVE_DRIVER})"
else
  echo "host_driver=${DRIVER}(<${NATIVE_DRIVER},必须使用镜像内cuda-compat-12-9)"
  echo "WARN:R545不在官方cu129镜像预置分支白名单;只有下方compat libcuda与Triton JIT全部通过才可继续"
fi

docker info 2>/dev/null | grep -qi nvidia || { echo "!! Docker未配置nvidia runtime"; exit 1; }
docker run --rm --gpus all --entrypoint python3 "${IMAGE}" -c '
import ctypes, pathlib, torch
ctypes.CDLL("libcuda.so.1")
maps = pathlib.Path("/proc/self/maps").read_text()
loaded = sorted({line.split()[-1] for line in maps.splitlines() if "libcuda.so" in line and "/" in line})
print("libcuda=", loaded)
assert any("/usr/local/cuda-12.9/compat/" in path for path in loaded), loaded
assert torch.cuda.is_available(), "CUDA unavailable in container"
count = torch.cuda.device_count()
assert count > 0, "no GPU"
for i in range(count):
    cap = torch.cuda.get_device_capability(i)
    print(f"gpu[{i}]={torch.cuda.get_device_name(i)} capability={cap[0]}.{cap[1]}")
    assert cap == (8, 6), f"GPU {i} is not A40/sm_86:{cap}"
'

docker run --rm --gpus all --entrypoint python3 "${IMAGE}" -c '
import torch, triton, triton.language as tl

@triton.jit
def add_kernel(x, y, out, n, BLOCK: tl.constexpr):
    offsets = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)
    mask = offsets < n
    tl.store(out + offsets, tl.load(x + offsets, mask=mask) + tl.load(y + offsets, mask=mask), mask=mask)

n = 4096
x = torch.randn(n, device="cuda")
y = torch.randn(n, device="cuda")
out = torch.empty_like(x)
add_kernel[(triton.cdiv(n, 256),)](x, y, out, n, BLOCK=256)
torch.cuda.synchronize()
torch.testing.assert_close(out, x + y)
print("triton_ptx_jit=PASS")
'

echo "PASS:驱动、nvidia runtime、compat libcuda、CUDA ${EXPECTED_CUDA}、A40(sm_86)与Triton PTX JIT全部通过"

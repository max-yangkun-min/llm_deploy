#!/usr/bin/env bash
set -euo pipefail

python3 -m pip check
python3 /opt/verify_stack.py

test "$(cat /opt/vllm_base_commit.txt)" = "ee0da84ab9e04ac7610e28580af62c365e898389"
test "$(cat /opt/vllm_pr38476_commit.txt)" = "3740c02bb1223d37823593664ae3eafa397b9937"

mapfile -t cubin_libraries < <(python3 -c '
import pathlib, vllm
root = pathlib.Path(vllm.__file__).resolve().parent
patterns = (
    "_C_stable_libtorch*.so",
    "_moe_C_stable_libtorch*.so",
    "vllm_flash_attn/_vllm_fa2_C*.so",
)
for pattern in patterns:
    matches = list(root.glob(pattern))
    if len(matches) != 1:
        raise SystemExit(f"expected one {pattern}, found {matches}")
    print(matches[0])
')

for library in "${cubin_libraries[@]}"; do
  listing=$(cuobjdump --list-elf "$library")
  printf '%s\n' "$library" "$listing"
  grep -q 'sm_80' <<<"$listing"
  if grep -Eq 'sm_(7[0-9]|8[679]|9[0-9]|10[0-9]|12[0-9])' <<<"$listing"; then
    echo "unexpected non-sm_80 cubin in $library" >&2
    exit 1
  fi
done

python3 - <<'PY'
from pathlib import Path

freeze = Path("/opt/glm52-vllm-pip-freeze.txt").read_text(encoding="utf-8")
required = (
    "torch==2.11.0+cu128",
    "torchvision==0.26.0+cu128",
    "torchaudio==2.11.0+cu128",
    "numpy==2.2.6",
    "cuda-bindings==12.9.7",
    "cuda-pathfinder==1.5.5",
    "cuda-python==12.9.7",
    "triton==3.6.0",
)
missing = [line for line in required if line not in freeze.splitlines()]
if missing:
    raise SystemExit(f"pip freeze is missing: {missing}")
print("independent pip-freeze verification passed")
PY

echo "INDEPENDENT_VALIDATION_PASSED"

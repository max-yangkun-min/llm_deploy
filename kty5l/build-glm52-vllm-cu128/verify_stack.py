from __future__ import annotations

import ctypes
import importlib.metadata as metadata
import pathlib
import subprocess

import numpy
import torch
import vllm


expected = {
    "torch": "2.11.0+cu128",
    "torchvision": "0.26.0+cu128",
    "torchaudio": "2.11.0+cu128",
    "numpy": "2.2.6",
    "cuda-bindings": "12.9.7",
    "cuda-pathfinder": "1.5.5",
    "cuda-python": "12.9.7",
    "triton": "3.6.0",
}
for package, version in expected.items():
    actual = metadata.version(package)
    if actual != version:
        raise RuntimeError(f"{package}: expected {version}, got {actual}")

if torch.version.cuda != "12.8":
    raise RuntimeError(f"torch CUDA must be 12.8, got {torch.version.cuda}")
if not vllm.__version__.startswith("0.24.0+pr38476.cu128.clean2"):
    raise RuntimeError(f"unexpected vLLM version: {vllm.__version__}")

root = pathlib.Path(vllm.__file__).resolve().parent
required_patterns = (
    "_C_stable_libtorch*.so",
    "_moe_C_stable_libtorch*.so",
    "cumem_allocator*.so",
    "vllm_flash_attn/_vllm_fa2_C*.so",
)
required: list[pathlib.Path] = []
for pattern in required_patterns:
    matches = list(root.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"expected one {pattern}, found {matches}")
    required.extend(matches)

forbidden_patterns = (
    "_qutlass_C*.so",
    "_flashmla*.so",
    "_deep_gemm_C*.so",
    "vllm_flash_attn/_vllm_fa3_C*.so",
)
for pattern in forbidden_patterns:
    matches = list(root.glob(pattern))
    if matches:
        raise RuntimeError(f"forbidden A100-incompatible extension: {matches}")

# Load every packaged native library now. This catches unresolved symbols and
# stale ABI artifacts during the build rather than at the target's model load.
for library in required:
    ctypes.CDLL(str(library))
    ldd = subprocess.run(
        ["ldd", str(library)],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    if "not found" in ldd:
        raise RuntimeError(f"unresolved dependency in {library}:\n{ldd}")
    if "cuda-12.9" in ldd or "cu129" in ldd:
        raise RuntimeError(f"cu129 dependency leaked into {library}:\n{ldd}")

from vllm import _custom_ops  # noqa: F401,E402
from vllm.model_executor.layers.quantization.awq import AWQConfig  # noqa: F401,E402
from vllm.model_executor.models.registry import ModelRegistry  # noqa: E402

model_cls, _ = ModelRegistry.resolve_model_cls("Glm4MoeForCausalLM")
if model_cls is None:
    raise RuntimeError("GLM MoE model class was not registered")

registry = (root / "v1/attention/backends/registry.py").read_text(encoding="utf-8")
backend = (root / "v1/attention/backends/triton_mla_sparse.py")
if "TRITON_MLA_SPARSE" not in registry or not backend.is_file():
    raise RuntimeError("PR #38476 TRITON_MLA_SPARSE backend is missing")

print(f"torch={torch.__version__} CUDA={torch.version.cuda}")
print(f"vllm={vllm.__version__} root={root}")
print(f"numpy={numpy.__version__}")
print("native sm_80 stack verification passed")

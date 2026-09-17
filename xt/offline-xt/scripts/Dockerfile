# syntax=docker/dockerfile:1.7
# ============================================================================
# xt · 14×A40 48GB(sm_86) · 宿主驱动>=545的CUDA 12.9 Forward Compatibility镜像
# 官方vLLM 0.24.0没有cu124变体;显式使用cu129,在容器内加入cuda-compat-12-9
# 解决旧宿主驱动上的PTX JIT限制。宿主CUDA Toolkit不参与容器运行。
# 官方vLLM 0.24.0镜像不含Ray,本镜像显式锁定并安装Ray 2.56.1。
# ============================================================================
ARG VLLM_TAG=v0.24.0
ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.24.0-cu129
FROM ${VLLM_BASE_IMAGE}

ARG VLLM_TAG
ARG VLLM_BASE_IMAGE
ARG CUDA_COMPAT=12.9
ARG RAY_VERSION=2.56.1

USER root

# 官方cu129基础镜像已经内置cuda-compat-12-9;只做断言,避免重复安装和新增大层。
# 官方NVIDIA_REQUIRE_CUDA白名单没有列R545。为允许“驱动恰为545”的实机验证,
# 关闭容器启动前门禁;这不代表官方认证,最终必须由A40上的compat libcuda和Triton JIT验收。
RUN dpkg-query -W cuda-compat-12-9 \
 && test -e /usr/local/cuda-12.9/compat/libcuda.so.1 \
 && apt-get update \
 && apt-get install -y --no-install-recommends nginx \
 && rm -rf /var/lib/apt/lists/*

RUN CUDA_COMPAT="${CUDA_COMPAT}" python3 -c 'import os, torch; expected=os.environ["CUDA_COMPAT"]; actual=torch.version.cuda or ""; assert actual == expected or actual.startswith(expected + "."), f"expected CUDA {expected}, got torch CUDA {actual}"; print(f"verified torch CUDA {actual}")'

RUN python3 -m pip install --no-cache-dir \
      "ray[default]==${RAY_VERSION}" "huggingface_hub[hf_transfer]" \
 && RAY_VERSION="${RAY_VERSION}" python3 -c 'import os, ray, vllm; assert ray.__version__ == os.environ["RAY_VERSION"], (ray.__version__, os.environ["RAY_VERSION"]); print(f"vllm={vllm.__version__} ray={ray.__version__}")'

ENV HF_HUB_ENABLE_HF_TRANSFER=1 \
    NVIDIA_DISABLE_REQUIRE=1 \
    LD_LIBRARY_PATH=/usr/local/cuda-12.9/compat:${LD_LIBRARY_PATH}

LABEL org.blade-agent.cuda-profile="cu129-compat545" \
      org.blade-agent.cuda-runtime="${CUDA_COMPAT}" \
      org.blade-agent.cuda-compat-package="cuda-compat-12-9" \
      org.blade-agent.min-host-driver="545.0" \
      org.blade-agent.native-host-driver="575.51.03" \
      org.blade-agent.driver-545-policy="conditional-real-a40-validation-required" \
      org.blade-agent.vllm-tag="${VLLM_TAG}" \
      org.blade-agent.ray-version="${RAY_VERSION}" \
      org.blade-agent.gateway="nginx-in-vllm-image" \
      org.blade-agent.base-image="${VLLM_BASE_IMAGE}"

# 覆盖官方ENTRYPOINT,让run.sh能传vllm serve / ray start等任意命令。
ENTRYPOINT []
CMD ["bash"]

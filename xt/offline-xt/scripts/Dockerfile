# syntax=docker/dockerfile:1.7
# ============================================================================
# xt · 14×A40 48GB(sm_86)· CUDA 12.4 兼容镜像
# 与 kty5l 不同:这些模型 stock vLLM 就支持,【无需 PR / patch】。
# 官方 vllm-openai 镜像已含 vLLM + Ray(分布式依赖)+ 各模型 parser。
# 构建:  docker build --build-arg VLLM_TAG=v0.24.0 -t xt-vllm:0.24.0-cu124 .
# 这里的 cu124 是硬约束:基础镜像内 torch.version.cuda 必须恰为 12.4。
# 宿主机安装的 CUDA Toolkit 不会挂进容器;现场只要求驱动 >=550.54.15。
# ============================================================================
# ⚠️ 基础镜像必须同时支持三模型/parser、sm_86,且torch CUDA必须是12.4。
# 可指向内部仓库中已验证的cu124 vLLM镜像。
ARG VLLM_TAG=v0.24.0
ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.24.0
FROM ${VLLM_BASE_IMAGE}

ARG VLLM_TAG
ARG VLLM_BASE_IMAGE
ARG CUDA_COMPAT=12.4

# 不允许把 CUDA 12.8/13 的官方镜像误打成 cu124。若断言失败,应更换为
# 同时满足三模型支持和 cu124 的 VLLM_TAG,而不是删除检查。
RUN CUDA_COMPAT="${CUDA_COMPAT}" python3 -c 'import os, torch; expected=os.environ["CUDA_COMPAT"]; actual=torch.version.cuda or ""; assert actual == expected or actual.startswith(expected + "."), f"expected CUDA {expected}, got torch CUDA {actual}"; print(f"verified torch CUDA {actual}")'

# 官方镜像已带 vLLM + Ray;补 hf_transfer 便于拉权重
RUN pip install --no-cache-dir "huggingface_hub[hf_transfer]" || true

ENV HF_HUB_ENABLE_HF_TRANSFER=1

LABEL org.blade-agent.cuda-profile="cu124" \
      org.blade-agent.cuda-runtime="${CUDA_COMPAT}" \
      org.blade-agent.vllm-tag="${VLLM_TAG}" \
      org.blade-agent.base-image="${VLLM_BASE_IMAGE}"

# 覆盖官方 ENTRYPOINT(默认是 vllm serve),让 run.sh 能传 vllm serve / ray start 任意命令
ENTRYPOINT []
CMD ["bash"]

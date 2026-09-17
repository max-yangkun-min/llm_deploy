# syntax=docker/dockerfile:1.7
# zc5s · RTX 4090(sm_89) · MiniMax M2.7 AWQ · 银河麒麟 V10
#
# vLLM 0.24.0 官方可用镜像只有 CUDA 12.9 变体。GeForce RTX 4090 不应依赖
# cuda-compat 做旧驱动上的 forward compatibility，因此保留官方 CUDA 驱动门禁：
# Linux 宿主驱动必须 >= 575.51.03。容器用户态与宿主发行版解耦，可用于 x86_64 麒麟。
ARG VLLM_TAG=v0.24.0
ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.24.0-cu129
FROM ${VLLM_BASE_IMAGE}

ARG VLLM_TAG
ARG VLLM_BASE_IMAGE
USER root

# LB 也复用本镜像，现场只需导入一个 tar。
RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -c 'import torch, vllm; assert torch.version.cuda and torch.version.cuda.startswith("12.9"), torch.version.cuda; assert vllm.__version__ == "0.24.0", vllm.__version__; print("vllm", vllm.__version__, "torch-cuda", torch.version.cuda)'

ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

LABEL org.blade-agent.environment="zc5s" \
      org.blade-agent.model="MiniMax-M2.7-AWQ" \
      org.blade-agent.cuda-runtime="12.9" \
      org.blade-agent.min-host-driver="575.51.03" \
      org.blade-agent.geforce-forward-compat="disabled" \
      org.blade-agent.vllm-tag="${VLLM_TAG}" \
      org.blade-agent.base-image="${VLLM_BASE_IMAGE}"

ENTRYPOINT []
CMD ["bash"]

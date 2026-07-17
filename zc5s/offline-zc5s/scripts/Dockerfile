# syntax=docker/dockerfile:1.7
# ============================================================================
# zc5s · 单机 8×RTX4090 48GB(Ada sm_89,有 FP8)· 银河麒麟 V10
# 一个镜像跑 M2.7(INT4 或 FP8)/ Qwen3.5-397B。stock vLLM,【无需 PR/patch】。
# 注意:镜像是 Linux 容器,与宿主 OS(麒麟)无关;能否在麒麟上跑容器取决于
#   宿主装没装 docker + nvidia-container-toolkit(见 recon;装不上走裸机 pip 备案)。
# 构建:  docker build --build-arg VLLM_TAG=v0.24.0 -t zc5s-vllm:0.24.0 .
# ============================================================================
ARG REGISTRY=
# ⚠️ 锁一个支持 M2.7 / Qwen3.5-397B parser 且跑 sm_89 的版本
ARG VLLM_TAG=v0.24.0
FROM ${REGISTRY}vllm/vllm-openai:${VLLM_TAG}

RUN pip install --no-cache-dir "huggingface_hub[hf_transfer]" || true
ENV HF_HUB_ENABLE_HF_TRANSFER=1
ENTRYPOINT []
CMD ["bash"]

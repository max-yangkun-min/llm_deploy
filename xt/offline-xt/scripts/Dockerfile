# syntax=docker/dockerfile:1.7
# ============================================================================
# xt · 2×7×A40 48GB(sm_86)· 一个镜像跑三方案(M2.7 / Qwen3.5-397B / Kimi K2.6)
# 与 kty5l 不同:这些模型 stock vLLM 就支持,【无需 PR / patch】。
# 官方 vllm-openai 镜像已含 vLLM + Ray(分布式依赖)+ 各模型 parser。
# 构建:  docker build --build-arg VLLM_TAG=v0.24.0 -t xt-vllm:0.24.0 .
# ============================================================================
ARG REGISTRY=
# ⚠️ 锁定一个【同时支持 M2.7 / Qwen3.5-397B / Kimi K2.6 三者 parser 且跑 sm_86】的版本
ARG VLLM_TAG=v0.24.0
FROM ${REGISTRY}vllm/vllm-openai:${VLLM_TAG}

# 官方镜像已带 vLLM + Ray;补 hf_transfer 便于拉权重
RUN pip install --no-cache-dir "huggingface_hub[hf_transfer]" || true

ENV HF_HUB_ENABLE_HF_TRANSFER=1

# 覆盖官方 ENTRYPOINT(默认是 vllm serve),让 run.sh 能传 vllm serve / ray start 任意命令
ENTRYPOINT []
CMD ["bash"]

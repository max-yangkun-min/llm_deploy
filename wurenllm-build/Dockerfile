# syntax=docker/dockerfile:1.7
ARG BASE_IMAGE=xt-vllm:0.24.0-cu129-compat545
FROM ${BASE_IMAGE}

ARG MODEL_PROFILE
ARG MODEL_REPOSITORY
ARG MODEL_REVISION

USER root

# The upstream cu129 image already contains cuda-compat-12-9 and explicitly
# supports the R535/R550/R560/R565/R570 data-center driver branches. Undo the
# legacy package's unconditional NVIDIA requirement bypass.
ENV NVIDIA_DISABLE_REQUIRE="" \
    HF_HUB_ENABLE_HF_TRANSFER="" \
    HF_XET_HIGH_PERFORMANCE=1 \
    VLLM_ENABLE_CUDA_COMPATIBILITY=1

RUN test -n "${MODEL_PROFILE}" \
 && test -n "${MODEL_REPOSITORY}" \
 && dpkg-query -W cuda-compat-12-9 \
 && test -e /usr/local/cuda-12.9/compat/libcuda.so.1 \
 && python3 -c "import ray, torch, vllm; assert vllm.__version__ == '0.24.0'; assert ray.__version__ == '2.56.1'; assert (torch.version.cuda or '').startswith('12.9')" \
 && case "${MODEL_PROFILE}" in \
      minimax-m2.7) \
        grep -q 'MiniMaxM2ForCausalLM' /usr/local/lib/python3.12/dist-packages/vllm/model_executor/models/registry.py \
        && grep -q '"minimax_m2"' /usr/local/lib/python3.12/dist-packages/vllm/tool_parsers/__init__.py ;; \
      qwen3.5-397b-a17b) \
        grep -q 'Qwen3_5MoeForConditionalGeneration' /usr/local/lib/python3.12/dist-packages/vllm/model_executor/models/registry.py \
        && grep -q '"qwen3"' /usr/local/lib/python3.12/dist-packages/vllm/reasoning/__init__.py ;; \
      kimi-k2.6) \
        grep -q 'KimiK25ForConditionalGeneration' /usr/local/lib/python3.12/dist-packages/vllm/model_executor/models/registry.py \
        && grep -q '"kimi_k2"' /usr/local/lib/python3.12/dist-packages/vllm/tool_parsers/__init__.py ;; \
      *) echo "unsupported MODEL_PROFILE=${MODEL_PROFILE}" >&2; exit 2 ;; \
    esac

LABEL io.wurenllm.profile="${MODEL_PROFILE}" \
      io.wurenllm.model.repository="${MODEL_REPOSITORY}" \
      io.wurenllm.model.revision="${MODEL_REVISION}" \
      io.wurenllm.vllm.version="0.24.0" \
      io.wurenllm.cuda.version="12.9" \
      io.wurenllm.cuda.arch="sm_86" \
      io.wurenllm.minimum-supported-driver-branch="R535" \
      io.wurenllm.base.domestic-mirror="docker.m.daocloud.io/vllm/vllm-openai:v0.24.0-cu129" \
      io.wurenllm.base.digest="sha256:6b005c78cd17a1f0215f31e95d183833f4dfd6167c4473241b80d1c8843b91e8" \
      org.blade-agent.base-image="docker.m.daocloud.io/vllm/vllm-openai:v0.24.0-cu129" \
      org.blade-agent.cuda-profile="cu129-compat-r535" \
      org.blade-agent.min-host-driver="535" \
      org.blade-agent.driver-545-policy="not-allowlisted-do-not-use"

ENTRYPOINT []
CMD ["bash"]

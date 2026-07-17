# syntax=docker/dockerfile:1.7
# ============================================================================
# GLM-5.2 · 8×A100 80GB PCIe · vLLM + PR #38476 (sm80 的 TRITON_MLA_SPARSE 兜底)
# ----------------------------------------------------------------------------
# 设计目标:主/备两台随时可切、且抹平主机 CUDA 12.8 / 12.2 差异。
#   - 镜像自带 CUDA 运行时,宿主机只需 NVIDIA 驱动 >= 550(12.8 那台通常 >=570)。
#   - vLLM 锁定 commit + 打 PR #38476,固化进镜像,两台永远同一个已验证版本。
#   - 纯 Python 改动,VLLM_USE_PRECOMPILED=1,不重编 CUDA。
# 构建:  docker build --build-arg VLLM_REF=v0.24.0 -t glm52-vllm:0.24.0-pr38476 .
# ============================================================================
FROM nvidia/cuda:12.8.1-devel-ubuntu22.04

# ── 必须显式锁定,别用浮动 main;先 git ls-remote --tags 确认该 tag 存在 ──
ARG VLLM_REF=v0.24.0
ARG PR_NUM=38476

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      git python3.11 python3.11-venv python3.11-dev python3-pip \
      build-essential ca-certificates curl \
 && rm -rf /var/lib/apt/lists/* \
 && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
 && python3 -m pip install --upgrade pip

WORKDIR /opt
RUN git clone https://github.com/vllm-project/vllm.git
WORKDIR /opt/vllm

# 锁定 commit,并把它写进镜像备查(部署文档要记这个)
RUN git checkout ${VLLM_REF} \
 && git rev-parse HEAD > /opt/vllm_commit.txt \
 && git log --oneline -1 \
 && git config user.email build@local \
 && git config user.name  build \
 && git fetch origin pull/${PR_NUM}/head:pr-${PR_NUM}

# PR #38476 在 sparse_attn_indexer.py 上多半会冲突:
#   把硬抛的 RuntimeError 换成 "DeepGEMM 不可用 -> 走 Triton 兜底" 分支。
# 该冲突需人工解一次,固化成 patch 后放 patches/,后续构建全自动。
COPY patches/ /opt/patches/
RUN set -eux; \
    if git cherry-pick pr-${PR_NUM}; then \
        echo ">> cherry-pick 无冲突,直接应用"; \
    elif [ -f /opt/patches/38476-with-triton-fallback.patch ]; then \
        echo ">> cherry-pick 冲突,改用已解好的 patch"; \
        git cherry-pick --abort; \
        git apply --3way /opt/patches/38476-with-triton-fallback.patch; \
    else \
        echo "!! PR ${PR_NUM} 在 ${VLLM_REF} 上冲突,且 patches/ 里没有已解 patch。"; \
        echo "!! 按 patches/README.md 生成 38476-with-triton-fallback.patch 再重建。"; \
        exit 1; \
    fi

# 纯 Python 改动,不重编 CUDA;顺带装 hf_transfer 加速拉权重
RUN VLLM_USE_PRECOMPILED=1 pip install -e . \
 && pip install "huggingface_hub[hf_transfer]"

# ── A100 兜底三件套 + hf_transfer,固化进镜像,启动时不用再 export ──
ENV VLLM_ATTENTION_BACKEND=TRITON_MLA_SPARSE \
    VLLM_USE_DEEP_GEMM=0 \
    VLLM_USE_FLASHINFER_SAMPLER=0 \
    HF_HUB_ENABLE_HF_TRANSFER=1

EXPOSE 8000
WORKDIR /opt/vllm

# 刻意不把 vllm serve 设成 ENTRYPOINT:
# 分阶段调参(阶段3->阶段4)时靠 docker run 末尾传完整 serve 命令,免重建镜像。
CMD ["bash"]

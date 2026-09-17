ARG CUDA_DEVEL_IMAGE=docker.1panel.live/nvidia/cuda:12.8.1-devel-ubuntu22.04@sha256:6617a625f4090c76c545a0e7d63f2e441718ef9af7f4efe7dd1242a29e289fd7
ARG VLLM_BASE_IMAGE=docker.m.daocloud.io/vllm/vllm-openai:v0.24.0-cu129@sha256:4fab2d06cb3898f00d46def116d5aff27b2388126993efc871fe2601c7df9742

FROM ${CUDA_DEVEL_IMAGE} AS cuda128

FROM ${VLLM_BASE_IMAGE}

ARG VLLM_COMMIT=ee0da84ab9e04ac7610e28580af62c365e898389
ARG PR38476_COMMIT=3740c02bb1223d37823593664ae3eafa397b9937
ARG PYPI_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
ARG TORCH_INDEX=https://mirrors.nju.edu.cn/pytorch/whl/cu128
ARG MAX_JOBS=8
ARG NVCC_THREADS=2

LABEL org.opencontainers.image.title="GLM-5.2 vLLM for 8x A100 sm_80" \
      org.opencontainers.image.version="0.24.0-pr38476-cu128-clean-v2" \
      org.opencontainers.image.revision="ee0da84ab9e04ac7610e28580af62c365e898389" \
      io.blade.vllm.pr38476.revision="3740c02bb1223d37823593664ae3eafa397b9937" \
      io.blade.cuda.base.amd64.digest="sha256:6617a625f4090c76c545a0e7d63f2e441718ef9af7f4efe7dd1242a29e289fd7" \
      io.blade.vllm.base.amd64.digest="sha256:4fab2d06cb3898f00d46def116d5aff27b2388126993efc871fe2601c7df9742" \
      io.blade.mirror.cuda="docker.1panel.live/nvidia/cuda" \
      io.blade.mirror.vllm="docker.m.daocloud.io/vllm/vllm-openai" \
      io.blade.mirror.torch="https://mirrors.nju.edu.cn/pytorch/whl/cu128" \
      io.blade.mirror.pypi="https://pypi.tuna.tsinghua.edu.cn/simple" \
      io.blade.mirror.vllm_source="https://gitee.com/mirrors/vllm.git" \
      io.blade.vllm.source.archive.sha256="6bf9c64c848c06e2fd985f3051ccb65adc878cc7d0bb1f38f73090b8d952c5e1" \
      io.blade.vllm.pr38476.patch.sha256="f8e22e9df9b05b15bf0cbb5cb59e9ab61b7dd74b08c6484342b3da5d7603f31a"

USER root

# Compile against the verified CUDA 12.8.1 toolkit. The official vLLM base
# supplies a complete, internally consistent Python dependency set; only the
# CUDA/PyTorch ABI stack is replaced below.
COPY --from=cuda128 /usr/local/cuda-12.8 /usr/local/cuda-12.8
RUN ln -sfn /usr/local/cuda-12.8 /usr/local/cuda

ENV CUDA_HOME=/usr/local/cuda-12.8 \
    PATH=/usr/local/cuda-12.8/bin:${PATH} \
    LD_LIBRARY_PATH=/usr/local/lib/python3.12/dist-packages/torch/lib:/usr/local/cuda-12.8/lib64 \
    TORCH_CUDA_ARCH_LIST=8.0 \
    VLLM_FA_CMAKE_GPU_ARCHES=80-real \
    VLLM_MAIN_CUDA_VERSION=12.8 \
    VLLM_TARGET_DEVICE=cuda \
    VLLM_ATTENTION_BACKEND=TRITON_MLA_SPARSE \
    VLLM_USE_DEEP_GEMM=0 \
    VLLM_USE_FLASHINFER_SAMPLER=0 \
    PYTHONFAULTHANDLER=1 \
    TORCH_SHOW_CPP_STACKTRACES=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

# The CUDA image's NVIDIA apt feed is not needed. Removing it ensures apt uses
# only the selected domestic Ubuntu mirror during this build.
RUN rm -f /etc/apt/sources.list.d/cuda*.list \
 && sed -i \
      -e 's|http://archive.ubuntu.com/ubuntu/|https://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' \
      -e 's|http://security.ubuntu.com/ubuntu/|https://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' \
      /etc/apt/sources.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl git libnuma-dev ninja-build \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m pip config set global.index-url "${PYPI_INDEX}"

# Keep the official image's known-good non-CUDA packages (notably numpy 2.2.6,
# cuda-python/bindings/pathfinder 12.9.7/12.9.7/1.5.5). Replace only the exact
# torch and CUDA runtime distributions. --no-deps is intentional: the prior
# image's unrestricted --force-reinstall upgraded unrelated packages into a
# resolver-conflicted combination.
RUN python3 -m pip install --force-reinstall --no-deps \
      --index-url "${TORCH_INDEX}" \
      torch==2.11.0+cu128 \
      torchvision==0.26.0+cu128 \
      torchaudio==2.11.0+cu128 \
 && python3 -m pip install --force-reinstall --no-deps \
      --index-url "${TORCH_INDEX}" \
      cuda-toolkit==12.8.1 \
      nvidia-cublas-cu12==12.8.4.1 \
      nvidia-cuda-cupti-cu12==12.8.90 \
      nvidia-cuda-nvrtc-cu12==12.8.93 \
      nvidia-cuda-runtime-cu12==12.8.90 \
      nvidia-cudnn-cu12==9.19.0.56 \
      nvidia-cufft-cu12==11.3.3.83 \
      nvidia-cufile-cu12==1.13.1.3 \
      nvidia-curand-cu12==10.3.9.90 \
      nvidia-cusolver-cu12==11.7.3.90 \
      nvidia-cusparse-cu12==12.5.8.93 \
      nvidia-cusparselt-cu12==0.7.1 \
      nvidia-nccl-cu12==2.28.9 \
      nvidia-nvjitlink-cu12==12.8.93 \
      nvidia-nvshmem-cu12==3.4.5 \
      nvidia-nvtx-cu12==12.8.90 \
      triton==3.6.0 \
 && python3 -m pip install --upgrade --no-cache-dir \
      'cmake>=3.26.1,<4.5' \
      'packaging>=24.2' \
      'setuptools>=77.0.3,<81.0.0' \
      'setuptools-scm>=8' \
      'setuptools-rust>=1.9.0' \
      wheel

WORKDIR /opt
COPY vllm-v0.24.0-ee0da84.tar.gz /tmp/vllm-v0.24.0-ee0da84.tar.gz
COPY vendor-patches/38476-v0.24.0-compatible.patch /tmp/38476-v0.24.0-compatible.patch
RUN echo "6bf9c64c848c06e2fd985f3051ccb65adc878cc7d0bb1f38f73090b8d952c5e1  /tmp/vllm-v0.24.0-ee0da84.tar.gz" | sha256sum -c - \
 && echo "f8e22e9df9b05b15bf0cbb5cb59e9ab61b7dd74b08c6484342b3da5d7603f31a  /tmp/38476-v0.24.0-compatible.patch" | sha256sum -c - \
 && tar -xzf /tmp/vllm-v0.24.0-ee0da84.tar.gz -C /opt \
 && cd /opt/vllm \
 && git init \
 && git config core.autocrlf input \
 && git config user.name "offline-builder" \
 && git config user.email "offline-builder@localhost" \
 && git add -A \
 && git commit -m "vLLM v0.24.0 ${VLLM_COMMIT}" \
 && git checkout-index --force --all \
 && git apply --check /tmp/38476-v0.24.0-compatible.patch \
 && git apply /tmp/38476-v0.24.0-compatible.patch \
 && git add -A \
 && git commit -m "Apply PR #38476 ${PR38476_COMMIT} compatible patch" \
 && printf '%s\n' "${VLLM_COMMIT}" > /opt/vllm_base_commit.txt \
 && printf '%s\n' "${PR38476_COMMIT}" > /opt/vllm_pr38476_commit.txt \
 && rm -f /tmp/vllm-v0.24.0-ee0da84.tar.gz /tmp/38476-v0.24.0-compatible.patch

COPY vendor-sources/cutlass-v4.4.2-da5e086.tar.gz /tmp/cutlass-v4.4.2-da5e086.tar.gz
RUN echo "fc0d4b8aa08cb2d973f06cbc294099899da881f86a4cb93e39e8e6d8fe7d85bd  /tmp/cutlass-v4.4.2-da5e086.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/cutlass-v4.4.2-da5e086.tar.gz -C /opt \
 && test -f /opt/cutlass-v4.4.2/include/cutlass/cutlass.h \
 && rm -f /tmp/cutlass-v4.4.2-da5e086.tar.gz

ENV VLLM_CUTLASS_SRC_DIR=/opt/cutlass-v4.4.2

WORKDIR /opt/vllm
COPY patch_setup_sm80.py /opt/patch_setup_sm80.py
RUN python3 /opt/patch_setup_sm80.py

# Build a normal wheel, uninstall the cu129 base package completely, and then
# install the new wheel. This prevents stale native .so files surviving from
# the base image, which an editable overlay can otherwise mask.
RUN MAX_JOBS="${MAX_JOBS}" NVCC_THREADS="${NVCC_THREADS}" \
      VLLM_VERSION_OVERRIDE=0.24.0+pr38476.cu128.clean2 \
      python3 -m pip wheel --no-cache-dir --no-deps --no-build-isolation \
        --wheel-dir /tmp/vllm-wheel . \
 && python3 -m pip uninstall -y vllm \
 && python3 -m pip install --no-cache-dir --no-deps /tmp/vllm-wheel/*.whl \
 && rm -rf /tmp/vllm-wheel /root/.cache/pip

# Repair two dependency defects inherited from the runtime base after the
# expensive native wheel layer so the verified sm_80 compilation stays cached.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libcairo2-dev pkg-config \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m pip install --no-cache-dir 'pycairo==1.28.0' \
 && python3 -m pip install --force-reinstall --no-deps --no-cache-dir \
      'nixl-cu12==1.2.0'

COPY verify_stack.py /opt/verify_stack.py
RUN python3 -m pip check \
 && python3 /opt/verify_stack.py \
 && python3 -m pip freeze --all | sort > /opt/glm52-vllm-pip-freeze.txt

EXPOSE 8000
WORKDIR /opt/vllm
ENTRYPOINT []
CMD ["bash"]

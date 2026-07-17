#!/usr/bin/env bash
# ============================================================================
# zc5s · 备案 C:裸机 pip 装 vLLM(不走 Docker)—— 麒麟 V10 上容器栈装不上时用。
# 前提:麒麟已装 NVIDIA 驱动 + CUDA(驱动/CUDA 通不通是"第一道关",recon 先验)。
# 用法:  cd /offline-zc5s && ./scripts/install-baremetal.sh
# 依赖 system/wheels/ 里预先在联网机下好的 vllm 及其依赖 wheel(见 下载清单 · C2)。
# ============================================================================
set -euo pipefail
PKG="${PKG:-/offline-zc5s}"
WHEELS="${PKG}/system/wheels"

echo "== 0. 环境自检 =="
nvidia-smi -L || { echo "!! 无 GPU/驱动 —— 先解决驱动+CUDA(麒麟第一道关)"; exit 1; }
python3 --version || { echo "!! 无 python3"; exit 1; }
[ -d "${WHEELS}" ] && ls "${WHEELS}"/*.whl >/dev/null 2>&1 || { echo "!! ${WHEELS} 里没有 wheel,先在联网机备(下载清单 C2)"; exit 1; }

echo "== 1. 建虚拟环境 =="
python3 -m venv /opt/vllm-venv
source /opt/vllm-venv/bin/activate
pip install --no-index --find-links "${WHEELS}" --upgrade pip 2>/dev/null || true

echo "== 2. 离线装 vLLM(全部依赖来自 wheels/,不联网)=="
pip install --no-index --find-links "${WHEELS}" vllm "huggingface_hub[hf_transfer]"

echo "== 3. 冒烟 =="
python3 -c "import vllm; print('vLLM', vllm.__version__, 'OK')"
echo
echo "== 完成。裸机起服(以 M2.7 INT4 单副本为例,参数同 run.sh): =="
echo "  source /opt/vllm-venv/bin/activate"
echo "  CUDA_VISIBLE_DEVICES=0,1,2,3 vllm serve ${PKG}/models/MiniMax-M2.7-AWQ \\"
echo "    --served-model-name minimax-m2.7 --tensor-parallel-size 4 --enable-expert-parallel \\"
echo "    --quantization awq_marlin --tool-call-parser minimax_m2 \\"
echo "    --reasoning-parser minimax_m2_append_think --trust-remote-code --port 8001"
echo "  (双副本/FP8/397B 的参数照抄 run.sh 对应分支,去掉 docker run 外壳即可)"

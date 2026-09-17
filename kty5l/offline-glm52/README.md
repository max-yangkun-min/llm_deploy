# GLM-5.2 离线部署（8×A100 80GB）

本目录是一套独立部署包，只服务 `GLM-5.2-AWQ-INT4`。目录中只保留运行所需的镜像、模型目录、启动脚本和本文档。

## 固定版本

- 镜像：`glm52-vllm:0.24.0-pr38476-cu128-native-r570-a100`
- vLLM：`0.24.1.dev0`（v0.24.0 + PR #38476）
- PyTorch：`2.11.0+cu128`
- CUDA：容器内 12.8，原生 A100 `sm_80` 扩展
- 模型：`cyankiwi/GLM-5.2-AWQ-INT4`
- 镜像 SHA-256：`b0afdbfb6c04807dd33238fd19b32f2158353fbec62787015afd0a0c564d5d11`

目标机需要 8 张 A100 80GB、NVIDIA 驱动 `570.124.06` 或已验证兼容版本、Docker 和 NVIDIA Container Toolkit。宿主机不需要安装 CUDA Toolkit。

## 目录

```text
offline-glm52/
├── README.md
├── start.sh
├── images/
│   ├── glm52-vllm-0.24.0-pr38476-cu128-native-r570-a100.tar
│   └── glm52-vllm-0.24.0-pr38476-cu128-native-r570-a100.tar.sha256
└── models/
    └── GLM-5.2-AWQ-INT4/
```

将完整模型文件放入 `models/GLM-5.2-AWQ-INT4/`。至少应有 `config.json`、权重分片和索引文件，不能残留 `.incomplete`、`.lock` 或 `.part` 文件。

## 使用

```bash
cd offline-glm52
chmod +x start.sh
./start.sh load
./start.sh start
./start.sh logs
./start.sh test
```

停止服务：

```bash
./start.sh stop
```

默认端口 `8000`、8 张卡、32K 上下文。需要调整时直接传环境变量：

```bash
GPU_DEVICES=0,1,2,3,4,5,6,7 PORT=8000 MAX_MODEL_LEN=65536 MAX_NUM_SEQS=16 ./start.sh start
```

如果 `nvidia-smi topo -m` 显示跨 NUMA 的 `SYS` 通路，或遇到 P2P/NCCL 问题，可先用以下兼容模式验证，性能会下降：

```bash
NCCL_P2P_DISABLE=1 ./start.sh start
```

## 验收

启动日志必须确认：

```text
[cuda.py] Using TRITON_MLA_SPARSE attention backend
[sparse_attn_indexer.py] DeepGEMM not supported on this platform; using Triton fallback
```

首次冷启动约需 7 分钟，首个请求还会触发 Triton JIT。不要给容器设置短于 15 分钟的启动超时，也不要在模型加载阶段自动重启。

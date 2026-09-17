# Qwen3.5-397B-A17B AWQ：单机 8 卡或双机 4+4 卡

本目录支持两种互不混用的启动方式：单机 8 卡直接启动，或双机 4+4 卡 Ray 启动。

## 单机 8 卡启动（不使用集群）

```bash
chmod +x start.sh
./start.sh load
GPU_DEVICES=0,1,2,3,4,5,6,7 PORT=8000 ./start.sh local
./start.sh local-logs
```

API 地址为 `http://本机IP:8000/v1`。停止执行 `./start.sh stop`。

单机模式使用 `TP=4 + PP=2`，由 vLLM 的本机 `mp` 后端管理全部 8 张卡，
不需要 Ray、万兆网卡参数或第二台机器。

## 双机 4+4 卡启动

两台机器都复制此完整目录。主节点负责 API，工作节点提供另外 4 张 GPU。

两台机器先加载镜像：

```bash
chmod +x start.sh
./start.sh load
```

主节点：

```bash
NIC=ens6f0 NODE_IP=10.0.0.1 GPU_DEVICES=0,1,2,3 ./start.sh head
```

工作节点：

```bash
NIC=ens6f0 NODE_IP=10.0.0.2 HEAD_IP=10.0.0.1 GPU_DEVICES=0,1,2,3 ./start.sh worker
```

回到主节点：

```bash
./start.sh serve
./start.sh logs
```

停止：两台机器分别执行 `./start.sh stop`。

## 可设置变量

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `NIC` | 无 | 两台机器互通的万兆网卡名，Ray、NCCL、Gloo 都固定使用它。 |
| `NODE_IP` | 无 | 当前机器该万兆网卡的 IP。 |
| `HEAD_IP` | 无 | 仅工作节点需要，填写主节点万兆 IP。 |
| `GPU_DEVICES` | 单机 `0..7`；双机每节点 `0..3` | 当前实例使用的 GPU 编号；单机必须 8 张，双机每节点必须 4 张。 |
| `PORT` | `8000` | 主节点 API 监听端口；使用 host 网络，直接对外开放。 |
| `MAX_MODEL_LEN` | `65536` | 最大上下文长度；显存不足时先降低。 |

脚本会将 `NODE_IP` 同时传给 Ray 的 `--node-ip-address` 和容器内的
`VLLM_HOST_IP`，确保 Ray 与 vLLM 在多网卡服务器上使用同一条跨机链路。

## vLLM 启动参数

| 参数 | 作用 | 保留原因 |
|---|---|---|
| `/model` | 容器内模型路径。 | 必须指定模型。 |
| `--served-model-name qwen3.5-397b` | 固定 API 模型名。 | 供客户端稳定调用。 |
| `--tensor-parallel-size 4` | 每个流水段使用 4 张 GPU。 | 两个流水段合计使用 8 张卡。 |
| `--pipeline-parallel-size 2` | 将模型切成两个流水段。 | 单机时两个段都在本机；双机时每台一个段。 |
| `--distributed-executor-backend mp` | 使用本机多进程管理 GPU。 | 单机 8 卡模式使用，不需要 Ray。 |
| `--distributed-executor-backend ray` | 使用 Ray 调度跨机 GPU。 | 仅双机模式使用。 |
| `--enable-expert-parallel` | 启用 MoE 专家并行。 | 匹配 Qwen MoE 架构。 |
| `--quantization awq_marlin` | 使用 AWQ Marlin 内核。 | 匹配 AWQ 权重和 A40。 |
| `--max-model-len` | 限制上下文/KV Cache。 | 控制显存。 |
| `--trust-remote-code` | 允许模型仓库代码。 | 兼容固定 revision。 |
| `--port` | API 监听端口。 | host 网络下必须与期望端口一致。 |

单机模式使用 `mp`，双机模式使用 `ray`；其余模型加载参数保持一致。

镜像：`wurenllm/qwen3.5-397b-a17b:vllm0.24.0-cu129`  
镜像归档：`images/wurenllm-qwen3.5-397b-a17b-vllm0.24.0-cu129.tar`，12,222,927,872 bytes  
SHA-256：`8C55174A6C39D15817BFDE32DA4F3B06F10EBC2B0F01994952263BAD0801E372`  
模型：`QuantTrio/Qwen3.5-397B-A17B-AWQ@536f95520cb5202283f828e76fdc86afda581e43`

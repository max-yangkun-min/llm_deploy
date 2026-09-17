# Kimi K2.6：双机 6+6 卡方案

两台机器都复制此完整目录。该模型使用官方 4-bit `compressed-tensors` 权重，不是 AWQ。

## 启动

两台机器先执行：

```bash
chmod +x start.sh
./start.sh load
```

主节点：

```bash
NIC=ens6f0 NODE_IP=10.0.0.1 GPU_DEVICES=0,1,2,3,4,5 ./start.sh head
```

工作节点：

```bash
NIC=ens6f0 NODE_IP=10.0.0.2 HEAD_IP=10.0.0.1 GPU_DEVICES=0,1,2,3,4,5 ./start.sh worker
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
| `NIC` | 无 | 两台机器互通的万兆网卡名。 |
| `NODE_IP` | 无 | 当前机器的万兆 IP。 |
| `HEAD_IP` | 无 | 仅工作节点需要，填写主节点万兆 IP。 |
| `GPU_DEVICES` | `0,1,2,3,4,5` | 当前节点参与部署的 6 张 GPU。 |
| `PORT` | `8000` | 主节点 API 监听端口。 |
| `MAX_MODEL_LEN` | `65536` | 最大上下文长度；显存不足时先降低。 |

脚本会将 `NODE_IP` 同时传给 Ray 的 `--node-ip-address` 和容器内的
`VLLM_HOST_IP`，确保 Ray 与 vLLM 在多网卡服务器上使用同一条跨机链路。

## vLLM 启动参数

| 参数 | 作用 | 保留原因 |
|---|---|---|
| `/model` | 容器内模型路径。 | 必须指定模型。 |
| `--served-model-name kimi-k2.6` | 固定 API 模型名。 | 供客户端稳定调用。 |
| `--tensor-parallel-size 2` | 每个流水段使用 2 张 GPU。 | 配合 6 个流水段，共使用 12 张卡。 |
| `--pipeline-parallel-size 6` | 建立 6 个流水段。 | 将大模型分布到双机 12 卡。 |
| `--distributed-executor-backend ray` | 使用 Ray 跨机调度。 | 跨机执行所必需。 |
| `--enable-expert-parallel` | 启用 MoE 专家并行。 | 匹配 Kimi MoE 架构。 |
| `--quantization compressed-tensors` | 使用权重声明的压缩格式。 | 该官方 revision 不是 AWQ。 |
| `--max-model-len` | 限制上下文/KV Cache。 | 控制显存。 |
| `--trust-remote-code` | 允许模型仓库代码。 | 兼容固定 revision。 |
| `--port` | API 监听端口。 | host 网络下指定服务端口。 |

镜像：`wurenllm/kimi-k2.6:vllm0.24.0-cu129`  
镜像归档：`images/wurenllm-kimi-k2.6-vllm0.24.0-cu129.tar`，12,222,927,360 bytes  
SHA-256：`19942DF37FD8BCF20EFEF29E2AD84868FC7D1F83CF59538AE5F5CB6140BD7079`  
模型：`moonshotai/Kimi-K2.6@7eb5002f6aadc958aed6a9177b7ed26bb94011bb`

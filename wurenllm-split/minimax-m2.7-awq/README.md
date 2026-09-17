# MiniMax M2.7 AWQ：单机 4 卡方案

此目录完全独立，只需要本目录中的镜像、模型和 `start.sh`。

## 启动

```bash
chmod +x start.sh
./start.sh load
GPU_DEVICES=0,1,2,3 PORT=8000 ./start.sh start
./start.sh logs
```

停止：`./start.sh stop`。

## 可设置变量

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `GPU_DEVICES` | `0,1,2,3` | 本实例使用的 4 张 GPU 编号；必须正好 4 张。 |
| `PORT` | `8000` | 宿主机对外提供 OpenAI API 的端口。 |
| `MAX_MODEL_LEN` | `65536` | 最大上下文长度；显存不足时先降低此值。 |

## vLLM 启动参数

| 参数 | 作用 | 保留原因 |
|---|---|---|
| `/model` | 容器内模型路径。 | 必须指定要加载的模型。 |
| `--served-model-name minimax-m2.7` | 固定 API 请求中的模型名。 | 避免客户端使用容器路径作为模型名。 |
| `--tensor-parallel-size 4` | 将张量切分到 4 张 GPU。 | 模型无法在单张 A40 上加载。 |
| `--enable-expert-parallel` | MoE 专家并行。 | 匹配 MiniMax MoE 架构和 4 卡部署。 |
| `--quantization awq_marlin` | 使用 A40 适用的 AWQ Marlin 内核。 | 匹配本目录的 AWQ 权重。 |
| `--max-model-len` | 限制上下文和 KV Cache 上限。 | 防止默认长上下文占用过多显存。 |
| `--trust-remote-code` | 允许加载仓库随附的模型代码。 | 兼容该固定模型 revision。 |

镜像：`wurenllm/minimax-m2.7:vllm0.24.0-cu129`  
镜像归档：`images/wurenllm-minimax-m2.7-vllm0.24.0-cu129.tar`，12,222,927,872 bytes  
SHA-256：`6B0D9980E912A3BA404F79C20F0BF4DB3835E4FC0F258EEEC106BFF25DF38497`  
模型：`QuantTrio/MiniMax-M2.7-AWQ@c9f2192c7b81f26f9a257ce73d92122fff0aea3d`

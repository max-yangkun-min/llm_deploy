# wurenllm 离线部署包

本包只包含三个共享基础层的模型镜像、三个模型目录、`start.sh` 和本文。不要把旧的系统安装、下载或硬件检测脚本混入本目录。

## 固定版本

| 项目 | 固定值 |
|---|---|
| 国内基础镜像 | `docker.m.daocloud.io/vllm/vllm-openai:v0.24.0-cu129` |
| 基础镜像摘要 | `sha256:6b005c78cd17a1f0215f31e95d183833f4dfd6167c4473241b80d1c8843b91e8` |
| vLLM / Ray / Torch CUDA | `0.24.0` / `2.56.1` / `12.9` |
| 三镜像归档 | `images/wurenllm-images-vllm0.24.0-cu129.tar`，12,223,049,216 bytes |
| 归档 SHA-256 | `0E31B7F8BAEE16C7B73D1A85D90627DB6AE7FE245411485DFCBAE5EEA8106150` |
| MiniMax | `QuantTrio/MiniMax-M2.7-AWQ@c9f2192c7b81f26f9a257ce73d92122fff0aea3d` |
| Qwen | `QuantTrio/Qwen3.5-397B-A17B-AWQ@536f95520cb5202283f828e76fdc86afda581e43` |
| Kimi | `moonshotai/Kimi-K2.6@7eb5002f6aadc958aed6a9177b7ed26bb94011bb` |

Kimi 官方权重是 4-bit `compressed-tensors`，不是 AWQ。三个镜像基于同一 CUDA/vLLM 层，合并 tar 只保存一份共享层。

CUDA 12.9 是 vLLM 0.24.0 国内镜像中能验证到的最低 CUDA 变体；无后缀镜像实际是 CUDA 13.0，不使用。cu129 镜像内含 `cuda-compat-12-9`，官方约束允许 A40 使用最低 R535 数据中心驱动分支，也允许 R550/R560/R565/R570 兼容分支和原生支持 CUDA 12.9 的新驱动。建议现场使用已准备的 R570.172.08 或 R575+；不要用未列入该镜像白名单的 R545 分支。

目录应为：

```text
wurenllm/
├── README.md
├── start.sh
├── images/wurenllm-images-vllm0.24.0-cu129.tar
└── models/
    ├── MiniMax-M2.7-AWQ/
    ├── Qwen3.5-397B-A17B-AWQ/
    └── Kimi-K2.6/
```

## 一、部署前检测

两台服务器各运行以下几行：

```bash
nvidia-smi --query-gpu=index,name,driver_version,memory.total --format=csv
nvidia-smi topo -m
docker info | grep -E 'Server Version|Runtimes|Docker Root Dir'
df -h /var/lib/docker "$(pwd)"; ip -br addr
```

应看到 A40 48GB、Docker 含 `nvidia` runtime、模型盘与 Docker 盘空间充足。跨机方案还要确认两台的万兆接口名和 IP；TP 组尽量选择同 PCIe root/NVLink、避免跨 `SYS` 的卡。

加载镜像并做真实 GPU/CUDA 检查：

```bash
chmod +x start.sh
./start.sh load
./start.sh check-gpu
```

`check-gpu` 必须输出 CUDA 12.9、Tesla A40、计算能力 8.6。

## 二、检测异常怎么处理

| 现象 | 处理 |
|---|---|
| Docker 不存在或没有 `nvidia` runtime | 先按服务器操作系统安装 Docker 和 NVIDIA Container Toolkit，重启 Docker；本精简包不携带系统安装包。 |
| 驱动太旧或容器提示 `unsatisfied condition` | 换 R535/R550/R560/R565/R570 的数据中心生产分支，推荐 R570.172.08；也可使用原生支持 CUDA 12.9 的 R575+，安装后重启。不要强行设置 `NVIDIA_DISABLE_REQUIRE=1`。 |
| `check-gpu` 找不到 `libcuda`、Triton/JIT 报错 | 检查宿主驱动与 NVIDIA Container Toolkit；确认没有把宿主 CUDA 目录覆盖挂入容器。仍失败就停止部署。 |
| GPU 数量不对 | 检查 `nvidia-smi -L`、BIOS Above 4G Decoding、供电与槽位；用 `GPU_DEVICES=` 显式指定参与模型的卡。 |
| TP 通信慢或 NCCL 超时 | 重新按 `nvidia-smi topo -m` 选卡；跨机时把 `NIC=` 固定到万兆口，确认两台 MTU、路由和防火墙一致。 |
| `docker load` 空间不足 | 用 `docker system df` 检查；清理无关旧镜像或把 Docker Root Dir 迁到大盘后再加载。 |
| 模型检查提示缺文件/未完成 | 不要启动；重新复制或续传固定 revision，删除下载缓存和 `.incomplete/.lock` 后再执行 `./start.sh check-models`。 |
| CUDA OOM | 先降低 `MAX_MODEL_LEN` 和 `GPU_MEMORY_UTILIZATION`，再降低脚本中的 `--max-num-seqs`。 |
| parser 参数报错 | 确认加载的是本包镜像而非旧 `xt-vllm`；三个镜像已分别检查对应 parser 注册。 |

## 三、最终部署

先检查模型文件：

```bash
./start.sh check-models
```

### 方案 A：7+7，MiniMax M2.7 双副本

两台各执行：

```bash
GPU_DEVICES=0,1,2,3 PORT=8000 ./start.sh m2.7
./start.sh logs wurenllm-m2.7
```

任一台再启动负载均衡：

```bash
NODE_A=10.0.0.1:8000 NODE_B=10.0.0.2:8000 LB_PORT=9000 ./start.sh lb-m2
```

统一入口为 `http://负载均衡主机:9000/v1`。MTP 默认关闭以优先保证启动；基础服务验收后可用 `ENABLE_MTP=1 ./start.sh m2.7` 对照测试。

### 方案 B：8+6，8 卡机 Qwen、6 卡机 MiniMax

8 卡机：

```bash
GPU_DEVICES=0,1,2,3,4,5,6,7 ./start.sh qwen-local
./start.sh logs wurenllm-qwen
```

6 卡机选择拓扑最好的四张卡：

```bash
GPU_DEVICES=0,1,2,3 ./start.sh m2.7
```

### 方案 C：7+7，Qwen 跨机

机器 A：

```bash
NIC=ens6f0 GPU_DEVICES=0,1,2,3 ./start.sh ray-head qwen
```

机器 B：

```bash
NIC=ens6f0 HEAD_IP=10.0.0.1 GPU_DEVICES=0,1,2,3 ./start.sh ray-worker qwen
```

机器 A：

```bash
docker exec wurenllm-ray-head ray status
./start.sh serve-qwen
./start.sh pp-logs
```

### 方案 D：7+7，Kimi K2.6 跨机

两台各用六张卡，步骤与 Qwen 相同，但 profile 换成 `kimi`：

```bash
# 机器 A
NIC=ens6f0 GPU_DEVICES=0,1,2,3,4,5 ./start.sh ray-head kimi
# 机器 B
NIC=ens6f0 HEAD_IP=10.0.0.1 GPU_DEVICES=0,1,2,3,4,5 ./start.sh ray-worker kimi
# 回机器 A
docker exec wurenllm-ray-head ray status
./start.sh serve-kimi
./start.sh pp-logs
```

Kimi 使用 `TP=2 × PP=6` 和 `compressed-tensors`；这是三套方案中最重、最依赖真实 A40 吞吐压测的一套。

## 四、测试

先看状态与模型列表：

```bash
./start.sh status
curl http://127.0.0.1:8000/v1/models
```

最小生成测试：

```bash
./start.sh test minimax-m2.7
./start.sh test qwen3.5-397b
./start.sh test kimi-k2.6
```

测试负载均衡入口时：

```bash
BASE_URL=http://127.0.0.1:9000/v1 ./start.sh test minimax-m2.7
```

正式验收还应执行 blade_agent 的真实工具调用、流式输出、长上下文和并发测试，并记录首 token 延迟、输出 tokens/s、峰值显存和节点故障行为。停止本包容器：

```bash
./start.sh stop
```

本准备机没有 A40，镜像构建时只能验证版本、CUDA compat 文件、模型架构和 parser 注册；`check-gpu` 以及真实权重加载必须在目标 A40 服务器完成。

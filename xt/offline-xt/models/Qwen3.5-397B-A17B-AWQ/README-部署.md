# Qwen3.5-397B-A17B AWQ 离线部署步骤

Qwen3.5-397B在XT环境有两种部署方式:

| GPU布局 | 部署方式 | 是否需要Ray | 推荐用途 |
| ---- | ---- | ---- | ---- |
| `7+7` | 两台各4卡,跨机 `TP=4 × PP=2` | 需要 | 不改硬件时的强模型方案 |
| `8+6` | 8卡机单机 `TP=4 × PP=2` | 不需要,使用本机mp | 消除10GbE模型数据面,优先推荐 |

默认不使用TP=8。A40只有两卡NVLink桥,TP=8会在每层产生跨PCIe/NUMA的all-reduce;单机两段PP通常更稳。现场可以把TP=8作为对照压测,但不能未经测试直接替换默认参数。

## 1. 公共准备

目标服务器先执行:

```bash
cd /offline-xt/scripts
bash recon.sh
```

确认:

- A40数量符合7+7或8+6布局,驱动不低于550.54.15。
- `nvidia-smi topo -m` 能选出拓扑合适的4卡TP组。
- 权重目标盘为SSD,空间足够容纳约200GB权重、缓存和日志。
- Docker和NVIDIA Container Runtime可用。

安装镜像:

```bash
cd /offline-xt
./scripts/install-offline.sh
```

验证镜像:

```bash
docker run --rm --entrypoint bash xt-vllm:0.24.0-cu124 -lc '
python -c "import vllm,ray; print(\"vllm\",vllm.__version__); print(\"ray\",ray.__version__)"
'
```

## 2. 权重落盘

创建目录:

```bash
sudo mkdir -p /data/models /data/hf-cache
```

复制权重:

```bash
sudo rsync -aH --info=progress2 \
  /offline-xt/models/Qwen3.5-397B-A17B-AWQ/ \
  /data/models/Qwen3.5-397B-A17B-AWQ/
```

无 `rsync` 时使用:

```bash
sudo cp -a /offline-xt/models/Qwen3.5-397B-A17B-AWQ /data/models/
```

校验:

```bash
test -f /data/models/Qwen3.5-397B-A17B-AWQ/config.json
du -sh /data/models/Qwen3.5-397B-A17B-AWQ
```

- 7+7跨机PP:两台都复制完整权重目录。
- 8+6单机:只要求8卡机复制397B;6卡机不需要该权重。

## 3. 配置运行脚本

编辑 `/offline-xt/scripts/run.sh`:

```bash
IMAGE="xt-vllm:0.24.0-cu124"
MODELS_DIR="/data/models"
HF_CACHE="/data/hf-cache"
NIC="ens6f0"          # 7+7跨机方案填写各自10GbE接口名
HEAD_IP="10.0.0.1"    # 机器A的10GbE地址
PORT="8000"
```

## 4A. 7+7跨机部署

布局:

```text
机器A:4卡TP组,PP stage 0,Ray head
机器B:4卡TP组,PP stage 1,Ray worker
两台各剩3卡
```

机器A启动Ray,把卡号换成topo选出的4张:

```bash
cd /offline-xt/scripts
RAY_GPU_DEVICES=0,1,2,3 ./run.sh ray-head
docker logs -f ray-head
```

机器B加入:

```bash
cd /offline-xt/scripts
RAY_GPU_DEVICES=0,1,2,3 ./run.sh ray-worker
docker logs -f ray-worker
```

机器A检查资源:

```bash
docker exec ray-head ray status
```

必须显示2节点、合计8张GPU。然后只在机器A启动397B:

```bash
cd /offline-xt/scripts
./run.sh 397b
./run.sh pp-logs
```

## 4B. 8+6单机部署

布局:

```text
8卡机:卡0-3为PP stage 0,卡4-7为PP stage 1
      单机TP=4 × PP=2,使用mp后端
6卡机:不参与397B,可运行M2.7
```

8卡机执行:

```bash
cd /offline-xt/scripts
./run.sh 397b-8gpu
docker logs -f xt-397b-8gpu
```

该方式不启动Ray head/worker,也不依赖跨服务器10GbE。启动日志应确认 `tensor_parallel_size=4`、`pipeline_parallel_size=2`、`distributed_executor_backend=mp`。

## 5. API验证

服务所在机器执行:

```bash
curl http://127.0.0.1:8000/v1/models
```

生成测试:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"qwen3.5-397b",
    "messages":[{"role":"user","content":"检查下面Python函数并给出一个最小修复方案: def add(a,b): return a-b"}],
    "max_tokens":256,
    "temperature":0
  }'
```

验收时还需覆盖:

- tool-call结构能被blade_agent正确解析。
- reasoning parser不污染最终答案字段。
- 流式SSE输出不中断。
- 真实skill开发和多轮代码审查任务能够完成。

## 6. blade_agent接入

OpenAI兼容参数:

```text
base_url = http://<397B服务IP>:8000/v1
model    = qwen3.5-397b
api_key  = EMPTY
```

8+6布局下建议把397B作为复杂推理、架构设计、长程规划和疑难审查模型;常规编码与高频工具循环路由到6卡机上的M2.7。

## 7. 日志与停止

7+7:

```bash
docker logs -f ray-head
./run.sh pp-logs
docker exec ray-head ray status
# 机器A
docker rm -f ray-head
# 机器B
docker rm -f ray-worker
```

8+6:

```bash
docker logs -f xt-397b-8gpu
docker rm -f xt-397b-8gpu
```

## 8. 常见问题

| 现象 | 检查与处理 |
| ---- | ---- |
| 7+7 Ray显示超过8张GPU | 两台重新设置 `RAY_GPU_DEVICES`,各暴露4张 |
| 7+7跨机延迟高 | 检查 `NIC`、10GbE路由、bond和接口错误包;确认没有走管理口 |
| 8+6启动慢或通信慢 | 按topo重新划分两个4卡TP组;检查是否跨 `SYS`;再对照压测TP=8 |
| CUDA OOM | 先降 `--max-num-seqs`,再降 `--max-model-len` |
| parser参数报错 | 镜像版本不支持当前parser;在联网准备机验证新镜像后整体替换 |
| API能生成但工具调用失败 | 使用真实tool-call请求检查Hermes parser输出,不要只做普通对话测试 |

## 9. 验收清单

- [ ] 7+7时Ray显示2节点8GPU;8+6时不启动跨机Ray。
- [ ] 权重位于参与部署服务器的本地SSD。
- [ ] `/v1/models` 和chat completions正常。
- [ ] tool-call与reasoning字段符合blade_agent协议。
- [ ] 记录首token延迟、输出tok/s、并发吞吐和64K上下文余量。
- [ ] 8+6时验证6卡机M2.7可同时运行,两模型互不占用GPU。

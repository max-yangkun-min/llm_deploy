# Kimi K2.6 AWQ 离线部署步骤

本文只描述 XT 环境中 Kimi K2.6 的实际部署。适用于两种物理布局:

- `7+7`:两台各使用6张A40,各剩1张。
- `8+6`:两台仍各使用6张A40;8卡机剩2张,6卡机无剩余。

K2.6 INT4约500GB,单台8×48GB仍装不下,两种布局都必须采用跨机 `TP=2 × PP=6 = 12卡`。改成8+6不会改变K2.6的模型参数、显存总量或10GbE跨机PP路径。

## 1. 最终布局

```text
机器A(Ray head):3个PP stage × 每stage TP=2 = 6卡
                         │ 10GbE,只跨一个PP边界
机器B(Ray worker):3个PP stage × 每stage TP=2 = 6卡
```

要求:

- 两台都是x86_64,驱动不低于545.0,A40均可被Docker识别。
- 两台加载完全相同的`xt-vllm:0.24.0-cu129-compat545`镜像。
- 两台本地SSD都保存完整的 `Kimi-K2.6-AWQ` 权重目录。
- 两台之间的10GbE地址直连,主机防火墙允许这两个地址互相通信。
- K2.6社区AWQ仓库、vLLM版本、`kimi_k2` parser必须在联网准备机上先验证。

## 2. 两台机器先做现场核对

分别执行:

```bash
cd /offline-xt/scripts
bash recon.sh
```

重点检查:

```bash
nvidia-smi -L
nvidia-smi topo -m
ip -br addr
df -h
```

根据 `topo -m` 为每台选出3组TP=2卡对。优先使用NVLink/同PCIe root的组合,避免把跨 `SYS` 的两张卡组成一个TP组。记录两台万兆接口名和机器A的万兆IP。

## 3. 安装离线镜像

两台都执行:

```bash
cd /offline-xt
bash scripts/install-offline.sh
```

`install-offline.sh`会先执行`verify-cu129-compat.sh`;只有驱动、compat libcuda、torch CUDA 12.9、Triton JIT和A40(sm_86)全部通过才继续。再确认镜像和Ray均可用:

```bash
docker run --rm --entrypoint bash xt-vllm:0.24.0-cu129-compat545 -lc '
python -c "import ray,vllm; print(\"ray\",ray.__version__); print(\"vllm\",vllm.__version__)"
ray --version
'
```

任何一台无法导入Ray时不要进场临时联网安装,应回到联网准备机重建镜像并重新 `docker save`。

## 4. 权重落到两台本地SSD

两台都执行,目标路径需与 `run.sh` 的 `MODELS_DIR` 一致:

```bash
sudo mkdir -p /data/models /data/hf-cache
sudo rsync -aH --info=progress2 \
  /offline-xt/models/Kimi-K2.6-AWQ/ \
  /data/models/Kimi-K2.6-AWQ/
```

若没有 `rsync`,使用:

```bash
sudo cp -a /offline-xt/models/Kimi-K2.6-AWQ /data/models/
```

校验:

```bash
test -f /data/models/Kimi-K2.6-AWQ/config.json
du -sh /data/models/Kimi-K2.6-AWQ
```

## 5. 配置跨机参数

两台都编辑 `/offline-xt/scripts/run.sh` 顶部:

```bash
IMAGE="xt-vllm:0.24.0-cu129-compat545"
MODELS_DIR="/data/models"
HF_CACHE="/data/hf-cache"
NIC="ens6f0"          # 换成各自10GbE接口名
HEAD_IP="10.0.0.1"    # 必须是机器A的10GbE地址
PORT="8000"
```

先验证10GbE路径:

```bash
ping -c 3 10.0.0.1
```

如果有 `iperf3`,建议压测确认链路接近10GbE。不要把 `HEAD_IP` 填成千兆管理口。

## 6. 启动Ray集群

以下GPU编号只是示例,必须换成 `topo -m` 选出的6张卡。两台选择的卡数必须都是6。

机器A:

```bash
cd /offline-xt/scripts
RAY_GPU_DEVICES=0,1,2,3,4,5 ./run.sh ray-head
docker logs -f ray-head
```

看到Ray head正常启动后按 `Ctrl+C` 退出日志查看,不要停止容器。

机器B:

```bash
cd /offline-xt/scripts
RAY_GPU_DEVICES=0,1,2,3,4,5 ./run.sh ray-worker
docker logs -f ray-worker
```

回到机器A确认资源:

```bash
docker exec ray-head ray status
```

必须看到两节点、合计12张GPU。若显示14张,说明没有正确设置 `RAY_GPU_DEVICES`;停止Ray后重新启动。

## 7. 启动K2.6

只在机器A执行:

```bash
cd /offline-xt/scripts
./run.sh k2.6
./run.sh pp-logs
```

首次加载约500GB权重会很久。启动日志必须确认:

- 模型名为 `kimi-k2.6`。
- `tensor_parallel_size=2`、`pipeline_parallel_size=6`。
- Ray资源为两节点12卡。
- 没有CUDA OOM、NCCL超时或parser不存在错误。
- 服务最终监听机器A的 `:8000`。

## 8. API验证

在机器A执行:

```bash
curl http://127.0.0.1:8000/v1/models
```

再执行最小生成测试:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"kimi-k2.6",
    "messages":[{"role":"user","content":"用一句话说明服务已正常运行"}],
    "max_tokens":64,
    "temperature":0
  }'
```

还要使用真实的skill编写、工具调用和代码修改任务测试tool-call parser。仅能输出普通文本不代表agentic能力已经验收。

## 9. 日常运维

查看日志:

```bash
docker logs -f ray-head
docker logs -f ray-worker
./run.sh pp-logs
docker exec ray-head ray status
```

停止顺序:

```bash
# 机器A
docker rm -f ray-head
# 机器B
docker rm -f ray-worker
```

## 10. 常见问题

| 现象 | 检查与处理 |
| ---- | ---- |
| Ray只有一台节点 | 检查机器B的 `HEAD_IP`、10GbE路由和主机防火墙 |
| Ray显示14张GPU | 两台重新用 `RAY_GPU_DEVICES` 各限制6张卡 |
| NCCL卡死 | 确认 `NIC` 是万兆口;检查两机接口MTU和路由;临时增加NCCL调试日志 |
| CUDA OOM | 先降低 `--max-num-seqs`,再降低 `--max-model-len` 或 `--gpu-memory-utilization` |
| 单请求延迟高 | K2.6为32B激活且PP=6,属于预期;用并发填充流水线后再评估吞吐 |
| parser不存在 | 当前vLLM版本不支持该parser;在联网准备机更换并验证镜像,不要现场浮动安装 |
| 8+6后无法启动 | 重新检查6卡机移卡后的TP=2配对;K2.6仍必须保持两台各6卡 |

## 11. 验收清单

- [ ] 两台镜像ID和Ray/vLLM版本一致。
- [ ] 两台K2.6权重目录完整且位于SSD。
- [ ] Ray显示2节点、12GPU,两台各6GPU。
- [ ] 模型API和流式输出正常。
- [ ] tool-call能够被blade_agent正确解析和执行。
- [ ] 记录首token延迟、输出tok/s、并发吞吐和64K上下文显存余量。
- [ ] 任一节点停止时确认整个K2.6服务按预期不可用,监控能够报警。

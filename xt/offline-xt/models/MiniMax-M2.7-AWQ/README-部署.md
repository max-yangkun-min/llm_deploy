# MiniMax M2.7 AWQ 离线部署步骤

M2.7采用单机 `TP=4`,不需要Ray。XT环境支持两种布局:

| GPU布局 | 部署方式 | 冗余 |
| ---- | ---- | ---- |
| `7+7` | 两台各运行一个M2.7 TP=4副本,通过nginx聚合 | 有双副本故障转移 |
| `8+6` | 6卡机运行一个M2.7 TP=4;8卡机运行397B | M2.7无同模型冗余,但强/快模型可互相降级 |

## 1. 现场核对

需要运行M2.7的服务器执行:

```bash
cd /offline-xt/scripts
bash recon.sh
nvidia-smi topo -m
```

选择拓扑最好的4张卡组成TP组。优先同一PCIe root/NVLink配对,避免跨 `SYS`。确认本地SSD至少有约115GB权重空间以及缓存、日志余量。

## 2. 安装离线镜像

```bash
cd /offline-xt
./scripts/install-offline.sh
```

安装脚本会先校验驱动>=550.54.15、镜像内torch CUDA=12.4.x及A40(sm_86)。确认镜像能看到GPU:

```bash
docker run --rm --gpus all xt-vllm:0.24.0-cu124 \
  python -c 'import torch; print(torch.cuda.device_count())'
```

7+7布局两台都执行;8+6布局至少在6卡机执行。

## 3. 权重落盘

```bash
sudo mkdir -p /data/models /data/hf-cache
sudo rsync -aH --info=progress2 \
  /offline-xt/models/MiniMax-M2.7-AWQ/ \
  /data/models/MiniMax-M2.7-AWQ/
```

无 `rsync` 时:

```bash
sudo cp -a /offline-xt/models/MiniMax-M2.7-AWQ /data/models/
```

校验:

```bash
test -f /data/models/MiniMax-M2.7-AWQ/config.json
du -sh /data/models/MiniMax-M2.7-AWQ
```

- 7+7双副本:两台都复制权重。
- 8+6:复制到6卡机;可选在8卡机保留一份,用于397B停机后的应急切换。

## 4. 配置运行脚本

编辑 `/offline-xt/scripts/run.sh`:

```bash
IMAGE="xt-vllm:0.24.0-cu124"
MODELS_DIR="/data/models"
HF_CACHE="/data/hf-cache"
PORT="8000"
```

当前脚本使用逻辑卡0-3。如果topo结果要求使用其他4张卡,应同步修改 `m2.7)` 分支中的 `CUDA_VISIBLE_DEVICES`。

## 5A. 7+7双副本部署

机器A和机器B分别执行:

```bash
cd /offline-xt/scripts
./run.sh m2.7
docker logs -f xt-m2.7
```

两台服务地址示例:

```text
机器A http://10.0.0.1:8000/v1
机器B http://10.0.0.2:8000/v1
```

编辑网关机 `/offline-xt/scripts/lb/nginx.conf`,把upstream改成两台实际IP。然后启动负载均衡:

完整离线包已包含 `nginx-stable.tar`;执行 `install-offline.sh` 时会与vLLM镜像一起加载,现场不需要联网拉取nginx。

```bash
cd /offline-xt/scripts
./run.sh lb-nginx
docker logs -f xt-lb
```

统一入口为运行LB的机器 `:9000`。nginx容器内部监听8000,`run.sh`映射为宿主机9000,因此可以直接与本机M2.7的8000端口共存。nginx必须关闭 `proxy_buffering`,否则流式SSE会被缓存。

## 5B. 8+6单副本部署

只在6卡机执行:

```bash
cd /offline-xt/scripts
./run.sh m2.7
docker logs -f xt-m2.7
```

其中4张卡运行M2.7,剩余2张可用于embedding、reranker或小模型。8卡机可同时运行:

```bash
./run.sh 397b-8gpu
```

该布局不把M2.7和397B配置成同名随机负载均衡。blade_agent应显式选择 `minimax-m2.7` 或 `qwen3.5-397b`。

## 6. 启动日志检查

必须确认:

- 模型名为 `minimax-m2.7`。
- `tensor_parallel_size=4`。
- `quantization=awq_marlin`。
- KV类型为auto,没有误开FP8 KV。
- MTP投机解码成功启用。
- 服务监听 `:8000`。

若 `--speculative-config` 因当前模型或vLLM版本报错,先删除该参数完成基础部署,记录无MTP性能;不要为了启用MTP在离线机临时升级依赖。

## 7. API验证

单副本测试:

```bash
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"minimax-m2.7",
    "messages":[{"role":"user","content":"写一个带参数校验的Python文件读取函数"}],
    "max_tokens":256,
    "temperature":0
  }'
```

7+7布局还要测试网关统一入口,并逐台停止副本验证故障转移:

```bash
# 先停止机器A副本,请求应继续由机器B完成
docker rm -f xt-m2.7
```

测试结束后重新启动机器A副本,再对机器B执行同样测试。

## 8. blade_agent接入

7+7统一入口:

```text
base_url = http://<运行LB的机器IP>:9000/v1
model    = minimax-m2.7
api_key  = EMPTY
```

8+6直接入口:

```text
base_url = http://<6卡机IP>:8000/v1
model    = minimax-m2.7
api_key  = EMPTY
```

M2.7优先承接高频工具循环、skill编写/修改、常规代码生成和低延迟任务。简单任务关闭thinking,避免推理过程拖慢Agent循环。

## 9. 日志与停止

```bash
docker logs -f xt-m2.7
docker stats xt-m2.7
docker rm -f xt-m2.7
```

网关:

```bash
docker logs -f xt-lb
docker rm -f xt-lb
```

## 10. 常见问题

| 现象 | 检查与处理 |
| ---- | ---- |
| CUDA OOM | 先降低 `--max-num-seqs`,再降低 `--max-model-len` |
| MTP参数报错 | 临时移除 `--speculative-config`,先验基础服务,再回联网机验证兼容版本 |
| 单路速度异常 | 检查4卡是否跨 `SYS`;确认AWQ Marlin和MTP实际生效 |
| 双副本只有一台收到请求 | 检查nginx upstream、健康状态和两台模型名是否一致 |
| 流式输出一次性返回 | nginx必须设置 `proxy_buffering off` |
| 8+6请求发错模型 | 网关中两个模型必须使用不同 `model_name`,由blade_agent显式路由 |

## 11. 验收清单

- [ ] M2.7权重位于参与部署服务器的本地SSD。
- [ ] 每个副本只看到选定的4张GPU。
- [ ] API、流式输出和tool-call正常。
- [ ] MTP启用状态和无MTP基线均有记录。
- [ ] 7+7布局完成逐台故障转移测试。
- [ ] 8+6布局确认M2.7和397B可同时运行且模型名不会混淆。
- [ ] 记录首token延迟、输出tok/s、并发吞吐和64K上下文余量。

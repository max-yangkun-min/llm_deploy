# zc5s 离线安装 · MiniMax M2.7 AWQ

## 1. 现场核查

```bash
cd /offline-zc5s/scripts
bash recon.sh
```

确认：8张 RTX 4090、驱动不低于 575.51.03、Docker 和 NVIDIA Container Toolkit 可用，并根据 `nvidia-smi topo -m` 确认两组4卡的 PCIe/NUMA 拓扑。

## 2. 校验并导入

```bash
cd /offline-zc5s
bash scripts/install-offline.sh
```

安装脚本会校验全包 SHA256、44个权重分片、宿主驱动版本和镜像标签。

## 3. 复用同盘权重

```bash
test -f /offline-xt/models/MiniMax-M2.7-AWQ/config.json
test "$(find /offline-xt/models/MiniMax-M2.7-AWQ -maxdepth 1 \
  -name 'model-*.safetensors' -type f | wc -l)" -eq 44
```

zc5s 包不重复存放这约121GiB权重。默认启动路径为 `/offline-xt/models`；若整块 E 盘挂载在其他位置，设置：

```bash
export MODEL_SOURCE=/实际挂载点/offline-xt/models/MiniMax-M2.7-AWQ
export MODELS_DIR=/实际挂载点/offline-xt/models
```

## 4. 验证镜像与GPU

```bash
cd /offline-zc5s/scripts
export MODELS_DIR=/offline-xt/models   # 按实际挂载位置调整
./run.sh verify
```

输出应包含 `vllm 0.24.0`、`cuda 12.9`、`gpus 8`。

## 5. 启动双副本和负载均衡

```bash
./run.sh m2.7
./run.sh lb-nginx
./run.sh test 8000
```

- GPU 0-3：副本A，宿主端口8001。
- GPU 4-7：副本B，宿主端口8002。
- nginx：统一入口8000，复用同一个 zc5s-vllm 镜像，无第二张镜像依赖。

若拓扑显示默认分组跨 NUMA，可在启动前覆盖：

```bash
export GPU_A=0,2,4,6
export GPU_B=1,3,5,7
./run.sh m2.7
```

具体卡号以现场 `nvidia-smi topo -m` 为准。

## 6. 验收重点

- 两个副本均加载 `MiniMax-M2.7-AWQ`，且 `TP=4`、AWQ Marlin 生效。
- API、流式输出、tool call 和 reasoning parser 正常。
- 若 MTP 投机参数报错，先移除 `--speculative-config` 跑通基础服务并记录。
- 逐个停止副本，确认 nginx 故障切换正常。
- 记录首 token 延迟、输出 tok/s、并发吞吐、显存占用和64K上下文余量。

# zc5s 离线包 · 下载清单(把大件填进本骨架)

> 骨架已搭好(脚本 + 启动 + LB + 裸机备案 + 选型文档就位)。**大件按下表下载填充。**
> 硬件:**单机** 8×RTX4090 48GB(Ada sm_89,**有 FP8**,无 NVLink 只 PCIe),OS **银河麒麟 V10**。
> 单机 = 无跨机/无 Ray,最简单;但**麒麟可能装不上容器栈** → 备了裸机 pip 备案(备案C)。

---

## 目录结构(✅=已就位 / ⬇️=待下载)

```
offline-zc5s/
├── images/   ⬇️ zc5s-vllm-0.24.0.tar             # A · 镜像 ~5-8G(容器路径;裸机路径可不用)
├── models/                                       # B · 按选型下,可只下一个
│   ├── MiniMax-M2.7-AWQ/         ⬇️ ~115G        #   🥇 INT4 稳健默认(TP=4×2副本)
│   ├── MiniMax-M2.7-FP8/         ⬇️ ~230G        #   🥇 FP8 质量版(TP=8;4090红利;仓库待确认)
│   └── Qwen3.5-397B-A17B-AWQ/    ⬇️ ~200G        #   🥈 更强推理(TP=8)
├── system/
│   ├── container-toolkit/ ⬇️  docker/ ⬇️  driver/ ⬇️(按需,★按 recon 判 deb/rpm)
│   └── wheels/            ⬇️(备案C)             #   裸机 pip 轮子(容器装不上时)
├── scripts/  ✅ Dockerfile(.cn) run.sh recon.sh install-offline.sh install-baremetal.sh prepare-offline.sh lb/
├── 大模型选型方案-8x4090-48G.md  ✅
├── 下载清单-FILL-ME.md          ✅
└── ⬇️ MANIFEST.sha256                            # D
```

---

## A · 镜像 → `images/`(容器路径用)

```bash
cd scripts
docker build -t zc5s-vllm:0.24.0 .      # 国内:-f Dockerfile.cn --build-arg REGISTRY=docker.m.daocloud.io/
docker save zc5s-vllm:0.24.0 -o ../images/zc5s-vllm-0.24.0.tar
```
> `FROM vllm/vllm-openai:<VLLM_TAG>`,先确认该 tag 支持 M2.7/Qwen3.5-397B parser 且跑 sm_89。**麒麟若装不上 docker,这一步可跳过,走裸机(C2)。**

## B · 权重 → `models/`(按选型下)

| | 模型 | 命令(+`HF_ENDPOINT=https://hf-mirror.com`) | 大小 |
|---|---|---|---|
| 🥇稳 | M2.7 INT4 | `huggingface-cli download QuantTrio/MiniMax-M2.7-AWQ --local-dir models/MiniMax-M2.7-AWQ` | ~115G |
| 🥇质量 | M2.7 FP8 | `huggingface-cli download <org>/MiniMax-M2.7-FP8 --local-dir models/MiniMax-M2.7-FP8`(仓库待确认) | ~230G |
| 🥈 | 397B | `huggingface-cli download QuantTrio/Qwen3.5-397B-A17B-AWQ --local-dir models/Qwen3.5-397B-A17B-AWQ` | ~200G |

> 先跑起来选 **M2.7 INT4**;要质量再加 FP8;要更强推理加 397B。备选 Qwen3.5-122B(~68G)如需可自行加目录。

## C · 系统依赖 → `system/`(★麒麟关键)

**C1 容器栈**(先 recon 判 deb/rpm):
- toolkit:`nvidia.github.io/libnvidia-container/stable/{deb,rpm}/amd64/` 取对应包 → `system/container-toolkit/`
- docker:麒麟多为 rpm 系,优先试官方源 `dnf install docker`;需离线包则备 rpm → `system/docker/`
- 驱动:recon 显示 <550 才备 `.run`+kernel-devel → `system/driver/`

**C2 裸机 pip 备案**(麒麟容器装不上时,推荐一并备):
```bash
# x86_64 联网机(manylinux 轮子麒麟通用):
pip download vllm "huggingface_hub[hf_transfer]" -d system/wheels/
```
离线机:`./scripts/install-baremetal.sh`(venv + `--no-index` 离线装 vLLM)。

## D · 填完 · 校验和
```bash
cd offline-zc5s
find . -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256
```

---

## 一键版(有带宽的联网 Linux)
```bash
cd scripts
export OUT=<硬盘挂载点上级> VLLM_TAG=v0.24.0 HF_ENDPOINT=https://hf-mirror.com
./prepare-offline.sh base            # 镜像 + 裸机wheels + 脚本 + 校验和
./prepare-offline.sh m2.7            # 按选型:m2.7 / m2.7-fp8 / 397b
```

---

## 部署提醒(填完拷到麒麟机)
1. **先 `bash scripts/recon.sh`** → 看 **A2 包管理器 / B1 驱动 / C1 容器能否用**,决定走哪条路:
   - docker + nvidia runtime 都在 → `./install-offline.sh`(容器)
   - 装不上 → `./install-baremetal.sh`(裸机 pip,需 system/wheels/)
2. 改 `run.sh` 顶部 `MODELS_DIR`,按选型起:
   - `./run.sh m2.7` + `./run.sh lb-nginx`(INT4 双副本,有冗余,PCIe友好)
   - `./run.sh m2.7-fp8`(FP8 质量,8卡单副本)
   - `./run.sh 397b`(更强推理,TP=8 压测单路)
3. 进场重点:🔴 **麒麟驱动/CUDA/vLLM 能否装通(第一道关)**;🔴 8×4090 满载≈3.6-4kW 供电;PCIe 拓扑(`topo -m`)定 TP 组、别跨 NUMA。

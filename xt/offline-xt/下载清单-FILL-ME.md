# xt 离线包 · 下载清单(把大件填进本骨架)

> 骨架已搭好(脚本 + 三方案启动 + LB 配置 + 对比文档就位)。**大件按下表下载填充。**
> 硬件:2 台 × 7×A40 48GB,跨机仅 10GbE。3 方案共用**一个镜像**,权重按方案分别下。
> **两台机器都要**:load 同一个镜像;PP 方案(一/二)两台都要放对应权重。

---

## 目录结构(✅=已就位 / ⬇️=待下载)

```
offline-xt/
├── images/        ⬇️ xt-vllm-0.24.0.tar        # A · 镜像(build+save,~5-8GB),两台都 load
├── models/                                     # B · 按你要部署的方案下,可只下一个
│   ├── MiniMax-M2.7-AWQ/          ⬇️ ~115GB    #    方案三
│   ├── Qwen3.5-397B-A17B-AWQ/     ⬇️ ~200GB    #    方案二(★推荐)
│   └── Kimi-K2.6-AWQ/            ⬇️ ~500GB    #    方案一
├── system/  nvidia-container-toolkit/ ⬇️  docker/ ⬇️(按需)  driver/ ⬇️(按需)   # C
├── scripts/  ✅ Dockerfile(.cn) run.sh recon.sh install-offline.sh prepare-offline.sh lb/
├── 大模型部署方案对比-2x7xA40.md  ✅
├── 下载清单-FILL-ME.md          ✅ (本文)
└── ⬇️ MANIFEST.sha256                          # D · 填完生成
```

> **三方案共用一个镜像**(stock vLLM + Ray,无需 PR/patch)。区别只在启动命令(见 `run.sh`)。

---

## A · 镜像 → `images/`(~5-8GB,build+save,两台都 load)

在 **x86_64 Linux + Docker** 上:
```bash
cd scripts
docker build -t xt-vllm:0.24.0 .                        # 海外/带宽好
# 国内:docker build -f Dockerfile.cn --build-arg REGISTRY=docker.m.daocloud.io/ -t xt-vllm:0.24.0 .
docker save xt-vllm:0.24.0 -o ../images/xt-vllm-0.24.0.tar
```
> ⚠️ 镜像 `FROM vllm/vllm-openai:<VLLM_TAG>`。**先确认该 tag 同时支持 M2.7 / Qwen3.5-397B / Kimi K2.6 三者的 parser 且跑 sm_86**;不确定就锁一个已验证版本改 `--build-arg VLLM_TAG=`。国内拉不动就换 `REGISTRY` 镜像,或别处 pull 好再 `docker tag`。

## B · 权重 → `models/`(按方案下,可只下要部署的)

| 方案 | 模型 | 命令(加 `HF_ENDPOINT=https://hf-mirror.com` 国内加速) | 大小 | 放两台? |
|---|---|---|---|---|
| 三 | M2.7 | `huggingface-cli download QuantTrio/MiniMax-M2.7-AWQ --local-dir models/MiniMax-M2.7-AWQ` | ~115G | ✅ 两台各一份 |
| 二★ | 397B | `huggingface-cli download QuantTrio/Qwen3.5-397B-A17B-AWQ --local-dir models/Qwen3.5-397B-A17B-AWQ` | ~200G | ✅ 两台(PP各半层) |
| 一 | K2.6 | `huggingface-cli download <org>/Kimi-K2.6-AWQ --local-dir models/Kimi-K2.6-AWQ` | ~500G | ✅ 两台 |

> K2.6 的 AWQ 社区仓库名**现场确认可用的**(占位 `<org>`)。要三个都实测就三个都下(单台约 815G,备 1-2TB/台)。

## C · 系统依赖 → `system/`(按 recon 结果,两台同款)

- **toolkit**(codename 无关):`https://nvidia.github.io/libnvidia-container/stable/deb/amd64/` 取 4 个 deb。
- **docker-ce**(仅没装 docker 时;codename 相关):先 `lsb_release -cs`,再从 `download.docker.com/linux/ubuntu/dists/<codename>/pool/stable/amd64/` 取。
- **驱动**:仅 recon 显示驱动<535 时,手动 .run + 内核头。

## D · 填完 · 校验和

```bash
cd offline-xt
find . -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256
```

---

## 一键版(有带宽的联网 Ubuntu)

```bash
cd scripts
export OUT=<硬盘挂载点上级> VLLM_TAG=v0.24.0 SYS_DISTRO=ubuntu HF_ENDPOINT=https://hf-mirror.com
./prepare-offline.sh base       # 镜像 + system deps + 脚本 + 校验和(不含权重)
./prepare-offline.sh 397b       # 按方案挑:m2.7 / 397b / k2.6(可多次)
```

---

## 部署提醒(填完拷到两台后)

1. **两台都** `./install-offline.sh`(load 镜像),改 `run.sh` 顶部 `MODELS_DIR / NIC / HEAD_IP`。
   - **`NIC` = 万兆光口接口名**(recon C1 查),PP 方案跨机通信全靠它,填错直接慢死。
2. 按方案起(详见 `run.sh` 头部 + 对比文档):
   - **方案三**:两台各 `./run.sh m2.7` → 网关 `./run.sh lb-nginx`(改 `lb/nginx.conf` 里两台 IP)。
   - **方案二/一**:机器A `./run.sh ray-head` → 机器B `./run.sh ray-worker` → 机器A `./run.sh 397b`(或 `k2.6`)。
3. 进场先两台各跑 `recon.sh`:重点 **topo(A40 挑同根桥的卡)+ 万兆网卡名 + 配电(满载 2.5-3kW/台)**。

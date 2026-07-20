# xt 离线包 · 下载清单(把大件填进本骨架)

> 骨架已搭好(脚本 + 3个7+7主方案 + 1个8+6备用方案 + LB 配置 + 对比文档)。**大件按下表下载填充。**
> 硬件:合计 14×A40 48GB,默认 7+7,可选 8+6;跨机仅 10GbE。所有方案共用**一个 CUDA 12.4 验收镜像**。
> **正式离线包固定备齐 3 个模型**:Kimi K2.6、Qwen3.5-397B、MiniMax M2.7。卡布局现场才决定,7+7 和 8+6 复用同一离线包,无需重新下载、构建镜像或制作另一套包。

---

## 目录结构(✅=已就位 / ⬇️=待下载)

```
offline-xt/
├── images/        ⬇️ xt-vllm-0.24.0-cu124.tar  # A · CUDA 12.4模型镜像(build+save),两台都load
│                  ⬇️ nginx-stable.tar           #     M2.7双副本网关镜像
├── models/                                     # B · 正式包三个模型全部备齐
│   ├── MiniMax-M2.7-AWQ/          ⬇️ ~115GB    #    含 README-部署.md
│   ├── Qwen3.5-397B-A17B-AWQ/     ⬇️ ~200GB    #    含 README-部署.md
│   └── Kimi-K2.6-AWQ/            ⬇️ ~500GB    #    含 README-部署.md
├── system/  nvidia-container-toolkit/ ⬇️  docker/ ⬇️(按需)  driver/ ⬇️(按需)   # C
├── scripts/  ✅ Dockerfile(.cn) run/recon/verify-cuda124/install/prepare + lb/
├── 大模型部署方案对比-2x7xA40.md  ✅
├── 下载清单-FILL-ME.md          ✅ (本文)
└── ⬇️ MANIFEST.sha256                          # D · 填完生成
```

> **所有模型服务共用一个vLLM镜像和同一套三模型权重**(stock vLLM + Ray,无需 PR/patch);另备一个很小的nginx网关镜像供M2.7双副本使用。8+6只是换部署布局,无需增加第四个模型或制作第二套离线包。

---

## A · CUDA 12.4 镜像 → `images/`(build+save,两台都 load)

这里的“兼容 CUDA 12.4”定义为:

- 镜像内 `torch.version.cuda` 必须为 `12.4.x`;Dockerfile 会在构建阶段硬校验,不能用 CUDA 12.8/13 镜像冒充。
- 离线机只使用宿主 NVIDIA 驱动,不依赖宿主 `/usr/local/cuda`;驱动必须 `>=550.54.15`。
- 两台服务器必须加载同一个 tar,镜像 ID 和 vLLM/Ray 版本保持一致。

在 **x86_64 Linux + Docker** 上:
```bash
cd scripts
docker build --build-arg VLLM_TAG=v0.24.0 --build-arg CUDA_COMPAT=12.4 \
  --build-arg VLLM_BASE_IMAGE=vllm/vllm-openai:v0.24.0 \
  -t xt-vllm:0.24.0-cu124 .
# 国内改用:-f Dockerfile.cn --build-arg VLLM_BASE_IMAGE=<镜像站>/vllm/vllm-openai:v0.24.0
IMAGE=xt-vllm:0.24.0-cu124 bash ./verify-cuda124.sh --image-only
docker save xt-vllm:0.24.0-cu124 -o ../images/xt-vllm-0.24.0-cu124.tar
docker pull nginx:stable
docker save nginx:stable -o ../images/nginx-stable.tar
```
> ⚠️ `VLLM_BASE_IMAGE` 必须同时满足两项:①镜像内 PyTorch CUDA=12.4;②支持 M2.7 / Qwen3.5-397B / Kimi K2.6 的模型架构和 parser。默认 `v0.24.0` 仍是待验证占位;若其官方镜像不是cu124,构建会主动失败,应更换经过验证的tag或指向内部cu124镜像,不能删除断言。

## B · 权重 → `models/`(正式包三个都下)

| 模型 | 命令(加 `HF_ENDPOINT=https://hf-mirror.com` 国内加速) | 大小 | 7+7部署时 | 8+6部署时 |
|---|---|---|---|---|
| M2.7 | `huggingface-cli download QuantTrio/MiniMax-M2.7-AWQ --local-dir models/MiniMax-M2.7-AWQ` | ~115G | 方案三两台使用 | 6卡机使用 |
| 397B | `huggingface-cli download QuantTrio/Qwen3.5-397B-A17B-AWQ --local-dir models/Qwen3.5-397B-A17B-AWQ` | ~200G | 方案二两台使用 | 8卡机使用 |
| K2.6 | `huggingface-cli download <org>/Kimi-K2.6-AWQ --local-dir models/Kimi-K2.6-AWQ` | ~500G | 方案一两台使用 | 包内保留,改回7+7时直接可用 |

> K2.6 的 AWQ 社区仓库名**现场确认可用的**(占位 `<org>`)。三套权重合计约 **815GB**,离线介质建议至少 1TB,稳妥用 2TB。
>
> **离线介质与服务器模型盘要区分**:完整三模型包保存在移动硬盘/NAS;进场后按最终布局把当前要运行的权重复制到各服务器 SSD。无需强行让两台服务器 SSD 都长期保存全部 815GB。

## C · 系统依赖 → `system/`(按 recon 结果,两台同款)

- **toolkit**(codename 无关):`https://nvidia.github.io/libnvidia-container/stable/deb/amd64/` 取 4 个 deb。
- **docker-ce**(仅没装 docker 时;codename 相关):先 `lsb_release -cs`,再从 `download.docker.com/linux/ubuntu/dists/<codename>/pool/stable/amd64/` 取。
- **驱动**:CUDA 12.4档位要求 `>=550.54.15`;更低时准备 NVIDIA `.run` 安装包及与离线机内核匹配的 headers。建议锁定现场已验证的同一生产分支,不要在线浮动升级。

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
./prepare-offline.sh all        # 正式交付:镜像 + system deps + 三个模型 + 校验和
```

---

## 部署提醒(填完拷到两台后)

1. **两台都** `./install-offline.sh`(load 后会强制运行 CUDA 12.4/A40 验收),改 `run.sh` 顶部 `MODELS_DIR / NIC / HEAD_IP`。
   - **`NIC` = 万兆光口接口名**(recon C1 查),PP 方案跨机通信全靠它,填错直接慢死。
   - 完整离线包保持不变;根据最终是7+7还是8+6,只把需要运行的模型权重复制到对应服务器 SSD。
2. 按方案起(详见 `run.sh` 头部 + 对比文档):
   - **方案三**:两台各 `./run.sh m2.7` → 网关 `./run.sh lb-nginx`(改 `lb/nginx.conf` 里两台 IP)。
   - **方案二/一**:机器A `./run.sh ray-head` → 机器B `./run.sh ray-worker` → 机器A `./run.sh 397b`(或 `k2.6`)。
   - **备用四 8+6**:8卡机 `./run.sh 397b-8gpu`;6卡机 `./run.sh m2.7`;可选用 `lb/8plus6-litellm.yaml` 暴露统一入口的两个模型名。
3. 进场先两台各跑 `recon.sh`:重点 **topo(A40 挑同根桥的卡)+ 万兆网卡名 + 配电**。改成8+6前还必须确认第8张卡的槽位、8-pin线束、PSU、风道和 BIOS 8卡枚举。

三个模型的逐步操作分别见:

- `models/Kimi-K2.6-AWQ/README-部署.md`
- `models/Qwen3.5-397B-A17B-AWQ/README-部署.md`
- `models/MiniMax-M2.7-AWQ/README-部署.md`

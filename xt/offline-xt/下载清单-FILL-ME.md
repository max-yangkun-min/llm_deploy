# xt 离线包 · 下载清单(把大件填进本骨架)

> 骨架已搭好(脚本 + 3个7+7主方案 + 1个8+6备用方案 + LB 配置 + 对比文档)。**大件按下表下载填充。**
> 硬件:合计 14×A40 48GB,默认 7+7,可选 8+6;跨机仅 10GbE。所有方案共用**一个cu129 Forward Compatibility验收镜像**。
> **正式离线包固定备齐 3 个模型**:Kimi K2.6、Qwen3.5-397B、MiniMax M2.7。卡布局现场才决定,7+7 和 8+6 复用同一离线包,无需重新下载、构建镜像或制作另一套包。

---

## 目录结构(✅=已就位 / ⬇️=待下载)

```
offline-xt/
├── images/        ⬇️ xt-vllm-0.24.0-cu129-compat545.tar # A · 模型+内置nginx网关,两台都load
├── models/                                     # B · 正式包三个模型全部备齐
│   ├── MiniMax-M2.7-AWQ/          ⬇️ ~115GB    #    含 README-部署.md
│   ├── Qwen3.5-397B-A17B-AWQ/     ⬇️ ~200GB    #    含 README-部署.md
│   └── Kimi-K2.6-AWQ/            ⬇️ ~500GB    #    含 README-部署.md
├── system/  nvidia-container-toolkit/ ⬇️  docker/{focal,jammy,noble}/ ⬇️  driver/ ⬇️ # C
├── scripts/  ✅ Dockerfile(.cn) run/recon/verify-cu129-compat/install/prepare + lb/
├── 大模型部署方案对比-2x7xA40.md  ✅
├── README-安装.md                ✅ (现场从这里开始)
├── 下载清单-FILL-ME.md          ✅ (本文)
└── ⬇️ MANIFEST.sha256                          # D · 填完生成
```

> **所有模型服务和M2.7双副本网关共用一个vLLM镜像和同一套三模型权重**。镜像以官方vLLM 0.24.0-cu129为基础,额外固化`cuda-compat-12-9`、Ray 2.56.1与nginx;不再单独下载nginx镜像。8+6只是换部署布局,无需增加第四个模型或制作第二套离线包。

---

## A · CUDA 12.9 Forward Compatibility镜像 → `images/`(build+save,两台都load)

这里的“宿主驱动545兼容”定义为:

- 官方vLLM 0.24.0没有cu124变体;显式使用`v0.24.0-cu129`,镜像内`torch.version.cuda`必须为`12.9.x`。
- 官方cu129基础镜像必须已经包含`cuda-compat-12-9`,派生镜像将其libcuda目录置于`LD_LIBRARY_PATH`首位,补足旧驱动上的PTX JIT能力。
- 离线机不依赖宿主`/usr/local/cuda`;策略下限为驱动`>=545.0`。驱动`>=575.51.03`可原生承载CUDA 12.9。R545不在官方镜像预置驱动分支白名单内,派生镜像通过`NVIDIA_DISABLE_REQUIRE=1`只允许进入真实A40验收,不代表官方无条件支持。
- 官方vLLM镜像不含Ray;本包锁定Ray 2.56.1,构建和安装阶段都会校验。
- 两台服务器必须加载同一个 tar,镜像 ID 和 vLLM/Ray 版本保持一致。

在 **x86_64 Linux + Docker** 上:
```bash
cd scripts
docker build --build-arg VLLM_TAG=v0.24.0 --build-arg CUDA_COMPAT=12.9 \
  --build-arg RAY_VERSION=2.56.1 \
  --build-arg VLLM_BASE_IMAGE=vllm/vllm-openai:v0.24.0-cu129 \
  -t xt-vllm:0.24.0-cu129-compat545 .
# 国内改用:-f Dockerfile.cn --build-arg VLLM_BASE_IMAGE=docker.m.daocloud.io/vllm/vllm-openai:v0.24.0-cu129
IMAGE=xt-vllm:0.24.0-cu129-compat545 bash ./verify-cu129-compat.sh --image-only
docker save xt-vllm:0.24.0-cu129-compat545 -o ../images/xt-vllm-0.24.0-cu129-compat545.tar
```
> ⚠️ `VLLM_BASE_IMAGE`已锁为官方`v0.24.0-cu129`档位,但三个2026模型的具体AWQ仓库和parser仍须用实际权重验收。`--image-only`只能证明CUDA/Ray/compat库完整,不能替代A40上的Triton、AWQ Marlin和模型加载测试。

## B · 权重 → `models/`(正式包三个都下)

| 模型 | 命令(加 `HF_ENDPOINT=https://hf-mirror.com` 国内加速) | 大小 | 7+7部署时 | 8+6部署时 |
|---|---|---|---|---|
| M2.7 | `huggingface-cli download QuantTrio/MiniMax-M2.7-AWQ --local-dir models/MiniMax-M2.7-AWQ` | ~115G | 方案三两台使用 | 6卡机使用 |
| 397B | `huggingface-cli download QuantTrio/Qwen3.5-397B-A17B-AWQ --local-dir models/Qwen3.5-397B-A17B-AWQ` | ~200G | 方案二两台使用 | 8卡机使用 |
| K2.6 | `huggingface-cli download <org>/Kimi-K2.6-AWQ --local-dir models/Kimi-K2.6-AWQ` | ~500G | 方案一两台使用 | 包内保留,改回7+7时直接可用 |

> K2.6 的 AWQ 社区仓库名**现场确认可用的**(占位 `<org>`)。三套权重合计约 **815GB**,离线介质建议至少 1TB,稳妥用 2TB。
>
> **离线介质与服务器模型盘要区分**:完整三模型包保存在移动硬盘/NAS;进场后按最终布局把当前要运行的权重复制到各服务器 SSD。无需强行让两台服务器 SSD 都长期保存全部 815GB。

## C · 系统依赖应急包 → `system/`

- **默认不改现有环境**:Docker与NVIDIA runtime已可用时`install-system-deps.sh`直接跳过。
- **Docker CE**:固定准备Ubuntu 20.04/focal、22.04/jammy、24.04/noble三套amd64包;每套含`containerd.io`、`docker-ce-cli`、`docker-ce`、buildx与compose插件。
- **NVIDIA Toolkit**:固定准备`nvidia-container-toolkit`、`-base`、`libnvidia-container1`、`libnvidia-container-tools`四个amd64 deb。
- **驱动**:准备R570 `.run`仅作人工兜底,绝不自动安装。驱动不满足时仍需现场内核精确匹配的headers、gcc/make、Secure Boot审查和重启窗口。
- **联网Windows一键下载**:`powershell -ExecutionPolicy Bypass -File scripts/prepare-system-windows.ps1 -OutRoot E:\offline-xt\system`;脚本读取官方Packages索引并验证SHA256,不经过Docker VHDX。
- **现场缺依赖时**:`sudo bash scripts/install-system-deps.sh`;非focal/jammy/noble会安全拒绝。

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

1. **两台都**在`/offline-xt`执行`bash scripts/install-offline.sh`(兼容exFAT无执行位;load后强制运行驱动/compat libcuda/CUDA 12.9/A40/Triton JIT验收),改`scripts/run.sh`顶部`MODELS_DIR / NIC / HEAD_IP`。
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

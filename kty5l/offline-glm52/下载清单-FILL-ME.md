# GLM-5.2 离线包 · 下载清单(把大件填进本骨架)

> 骨架已搭好(脚本 + 文档 + PR patch 已就位)。**剩下大件按下表下载,放到对应目录即可。**
> 离线机 = **Ubuntu**(已确认),x86_64。填完把整个 `offline-glm52/` 拷到硬盘,按 `GLM-5.2-部署步骤-8xA100.md` 部署。

---

## 目录结构(✅=已就位 / ⬇️=待你下载填充)

```
offline-glm52/
├── images/
│   └── ⬇️ glm52-vllm-0.24.0-pr38476.tar        # A · 镜像(build+save 产出,~25GB)
├── models/
│   ├── GLM-5.2-AWQ-INT4/  ⬇️                    # B · 唯一权重 ~410GB
│   └── Qwen3-8B/          ⬇️                    # C · 诊断小模型 ~16GB
├── system/
│   ├── nvidia-container-toolkit/ ⬇️             # D · toolkit deb(codename 无关)
│   ├── docker/                   ⬇️(按需)      # E · docker-ce deb(离线机没装 docker 才要)
│   └── driver/                   ⬇️(按需)      # F · 驱动.run(驱动<550 才要)
├── scripts/  ✅ (Dockerfile run.sh recon.sh install-offline.sh prepare-offline.sh patches/)
├── GLM-5.2-部署步骤-8xA100.md  ✅
├── 下载清单-FILL-ME.md         ✅ (本文)
└── ⬇️ MANIFEST.sha256                           # G · 填完最后生成
```

---

## A · 镜像 tar → `images/`(~25GB)

**不是直接下载,要 build 后 save**(patch 已在 `scripts/patches/`,build 自动套用)。在 **x86_64 Linux + Docker** 上二选一:

**海外/带宽好 → 原版 Dockerfile:**
```bash
cd scripts
docker build --build-arg VLLM_REF=v0.24.0 -t glm52-vllm:0.24.0-pr38476 .
docker save glm52-vllm:0.24.0-pr38476 -o ../images/glm52-vllm-0.24.0-pr38476.tar
```

**国内网 → 国内源版 `Dockerfile.cn`**(apt/pip/git 全走国内,patch 直接套不 fetch PR):
```bash
cd scripts
docker build -f Dockerfile.cn \
  --build-arg CUDA_REGISTRY=docker.m.daocloud.io/ \    # ← 换成你当前可用的 Docker Hub 镜像;留空=直连
  --build-arg GH_PROXY=https://ghfast.top/ \           # ← 换成你当前可用的 GitHub 代理
  --build-arg VLLM_REF=v0.24.0 -t glm52-vllm:0.24.0-pr38476 .
docker save glm52-vllm:0.24.0-pr38476 -o ../images/glm52-vllm-0.24.0-pr38476.tar
```
> `Dockerfile.cn` 里镜像地址会变(daocloud/ghfast 时好时坏),**用前先确认当下可用的**;CUDA base 实在拉不动就先在别处 `docker pull` 好再 `docker tag` 成 `nvidia/cuda:12.8.1-devel-ubuntu22.04` 命中本地。

**避开 vLLM precompiled wheel 慢下载(推荐)**:那步走 vLLM 自有存储、清华源盖不住。先在联网机走清华源把 wheel 下到 `scripts/wheels/`(快),再用 `PRECOMPILED_WHEEL` 指过去:
```bash
cd scripts
pip download vllm==0.24.0 --no-deps -d wheels/ -i https://pypi.tuna.tsinghua.edu.cn/simple
docker build -f Dockerfile.cn \
  --build-arg CUDA_REGISTRY=docker.m.daocloud.io/ --build-arg GH_PROXY=https://ghfast.top/ \
  --build-arg VLLM_REF=v0.24.0 \
  --build-arg PRECOMPILED_WHEEL=vllm-0.24.0-cp38-abi3-manylinux1_x86_64.whl \  # ← 上一步下到的实际文件名
  -t glm52-vllm:0.24.0-pr38476 .
```
不填 `PRECOMPILED_WHEEL` 也能 build,只是那步会慢。

---

## B · GLM-5.2 权重 → `models/GLM-5.2-AWQ-INT4/`(~410GB,唯一权重)

```bash
export HF_HUB_ENABLE_HF_TRANSFER=1
export HF_ENDPOINT=https://hf-mirror.com          # 国内加速(可选)
huggingface-cli download cyankiwi/GLM-5.2-AWQ-INT4 \
  --local-dir models/GLM-5.2-AWQ-INT4
du -sh models/GLM-5.2-AWQ-INT4                     # 应约 410GB
```

---

## C · 诊断小模型 → `models/Qwen3-8B/`(~16GB)

```bash
huggingface-cli download Qwen/Qwen3-8B --local-dir models/Qwen3-8B
```
> 仅用于进场阶段1 验 TP=8/NCCL 通路,不对外服务。

---

## D · nvidia-container-toolkit deb → `system/nvidia-container-toolkit/`(Ubuntu,codename 无关)

从官方 apt 仓库取这 4 个 deb(版本号取当前 stable,4 个要同版本):

```
https://nvidia.github.io/libnvidia-container/stable/deb/amd64/
  nvidia-container-toolkit_<ver>_amd64.deb
  nvidia-container-toolkit-base_<ver>_amd64.deb
  libnvidia-container1_<ver>_amd64.deb
  libnvidia-container-tools_<ver>_amd64.deb
```
或在一台联网 Ubuntu 上配好 nvidia 源后:
```bash
cd system/nvidia-container-toolkit
apt-get download nvidia-container-toolkit nvidia-container-toolkit-base \
                 libnvidia-container1 libnvidia-container-tools
```

---

## E · docker-ce deb → `system/docker/`(**仅当离线机没装 docker**)

**先确认**离线机 Ubuntu 版本(codename):`lsb_release -cs`(jammy=22.04 / focal=20.04 / noble=24.04)。
从 download.docker.com 取对应 codename 的 deb:

```
https://download.docker.com/linux/ubuntu/dists/<codename>/pool/stable/amd64/
  docker-ce_<ver>_amd64.deb
  docker-ce-cli_<ver>_amd64.deb
  containerd.io_<ver>_amd64.deb
  docker-buildx-plugin_<ver>_amd64.deb   (可选)
```
> 若 recon 显示离线机**已装 docker + nvidia runtime**,本项整目录留空即可。

---

## F · 驱动 → `system/driver/`(**仅当 recon 显示驱动 <550 或没装**)

手动下(nvidia.com),放进来:
```
NVIDIA-Linux-x86_64-<版本>.run          # 版本 >=550
linux-headers-$(uname -r) 对应 deb        # 编译驱动要用(与离线机内核匹配)
```
> 8×A100 且能看到 CUDA 12.8 的机器,驱动通常已就绪 → 本项多半留空。**以 recon 结果为准。**

---

## G · 填完最后一步 · 生成校验和

```bash
cd offline-glm52
find . -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256
```
拷到离线机后先 `sha256sum -c MANIFEST.sha256` 再部署。

---

## 一键版(在有带宽的联网 Ubuntu 上,自动填 A/C/D + 大权重 B)

骨架里的 `scripts/prepare-offline.sh` 就是干这个的:

```bash
cd scripts
export OUT=<硬盘挂载点的上级>       # 使 $OUT/offline-glm52 指向本骨架;或直接在骨架里手动填
export VLLM_REF=v0.24.0 SYS_DISTRO=ubuntu HF_ENDPOINT=https://hf-mirror.com
./prepare-offline.sh base           # 镜像 + 诊断小模型 + system 依赖 + 校验和(不含大权重)
./prepare-offline.sh weights        # GLM-5.2 唯一权重(~410GB)
```
> 手动逐项填(A–F)与跑脚本二选一,结果一致。

# GLM-5.2 离线包 · 本机备料步骤(联网机 = 这台 Windows)

> 本文只管**在这台 Windows 上把 `offline-glm52/` 填满**;填完拷到离线机后的部署走 `GLM-5.2-部署步骤-8xA100.md`。
> 逐项要下什么、多大、从哪来 → 见 `下载清单-FILL-ME.md`(A–G)。本文是这台机器的执行顺序与坑。

## 本机现状(2026-07-17 实测)

| 项 | 情况 | 影响 |
|---|---|---|
| E: (Lenovo) | exFAT,931GB 全空 | 唯一放得下整包(~451GB)的盘 → 整包目标盘 |
| C: | 剩 82GB;docker 内 77.5GB 镜像,98% 可回收 | build 前必须清,否则 25GB 镜像撑爆 C |
| D: | 剩 51.5GB | 放不下大件 |
| Docker | Desktop 28.4.0,WSL2;WSL Ubuntu 内 `docker` 已通 | 镜像可本机 build |
| WSL Ubuntu | codename = `resolute`(25.10) | ≠ 离线机 Ubuntu 版本 → 见步骤 4 |
| Python | Windows 3.8 + huggingface_hub 0.36.2;`hf_transfer` 未装 | 下权重前先装 |
| 网络 | huggingface.co / hf-mirror.com 均通 | 直连或走镜像皆可 |

整包 ≈ 451GB:权重 410GB + 镜像 25GB + 诊断小模型 16GB。

---

## 0 · 骨架拷到 E 盘

脚本里 `OUT=/mnt/e` 对应 `E:\offline-glm52`,两边必须一致。

```powershell
robocopy D:\workspaces\blade_agent\llm\kty5l\offline-glm52 E:\offline-glm52 /E
```

## 1 · 先起权重下载(最慢,几小时~几天,先开着跑)

Windows 原生下比在 WSL 里穿 `/mnt/e` 快。`--local-dir` 是实拷贝不建符号链接 → exFAT 没问题;中断后重跑同一条命令续传。

```powershell
python -m pip install hf_transfer
$env:HF_HUB_ENABLE_HF_TRANSFER = "1"
$env:HF_ENDPOINT = "https://hf-mirror.com"     # 直连慢时再加
huggingface-cli download cyankiwi/GLM-5.2-AWQ-INT4 --local-dir E:\offline-glm52\models\GLM-5.2-AWQ-INT4
huggingface-cli download Qwen/Qwen3-8B          --local-dir E:\offline-glm52\models\Qwen3-8B
```

下完核对大小:`GLM-5.2-AWQ-INT4` 应约 410GB,`Qwen3-8B` 约 16GB。

## 2 · 清 C 盘 docker 空间(权重在下时顺手做)

`prune` 只把空间标记为空闲,**vhdx 不会自己缩;必须 fstrim 后再 compact,顺序反了无效**。

```powershell
docker system prune -a --volumes
wsl -d docker-desktop sh -c "fstrim -v /mnt/docker-desktop-disk"
```
然后**管理员 PowerShell**:
```powershell
wsl --shutdown
Stop-Service WSLService
diskpart          # select vdisk file="...\docker_data.vhdx" → attach vdisk readonly → compact vdisk → detach vdisk
```
做完 C 盘应回到 150GB+ 可用,build 才安全。

## 3 · build + save 镜像(WSL Ubuntu 内,直接 save 到 E)

```bash
cd /mnt/e/offline-glm52/scripts
export OUT=/mnt/e VLLM_REF=v0.24.0 DOCKERFILE=Dockerfile.cn
export CUDA_REGISTRY=docker.m.daocloud.io/ GH_PROXY=https://ghfast.top/   # 用前先确认当下可用
bash prepare-offline.sh build
bash prepare-offline.sh save
```

- `Dockerfile.cn` 里的 daocloud / ghfast 时好时坏,build 前先 curl 验;CUDA base 拉不动就在别处 pull 好再 `docker tag` 成 `nvidia/cuda:12.8.1-devel-ubuntu22.04` 命中本地。
- 想省掉 vLLM precompiled wheel 那步的慢下载:先 `pip download vllm==0.24.0 --no-deps -d wheels/ -i https://pypi.tuna.tsinghua.edu.cn/simple`,再加 `--build-arg PRECOMPILED_WHEEL=<实际文件名>`(见清单 A)。
- PR#38476 patch 已在 `scripts/patches/`,build 自动套用。

## 4 · 系统依赖(坑在这)

本机 WSL 是 **Ubuntu 25.10 (resolute)**,和离线机不是一个版本:

- **docker-ce 系列**:别用 `apt-get download`(会下成 resolute 的包,离线机装不上)。等 `recon.sh` 在离线机上跑出 `lsb_release -cs`,再去
  `https://download.docker.com/linux/ubuntu/dists/<codename>/pool/stable/amd64/` 按 URL 下 → `system/docker/`。
  **离线机已装 docker + nvidia runtime → 整项跳过。**
- **nvidia-container-toolkit**:4 个 deb 与 codename 无关,`https://nvidia.github.io/libnvidia-container/stable/deb/amd64/` 直接抓(4 个同版本)→ `system/nvidia-container-toolkit/`。
- **驱动**:仅当 recon 显示驱动 <550 才要;8×A100 能看到 CUDA 12.8 的机器多半留空。**以 recon 结果为准。**

## 5 · 生成校验和

```bash
cd /mnt/e/offline-glm52/scripts && bash prepare-offline.sh manifest
```

## 拷到离线机后

- 先 `sha256sum -c MANIFEST.sha256` 再部署。
- **exFAT 不保存执行位** → 所有脚本用 `bash install-offline.sh` 这样调,`./xxx.sh` 会 Permission denied。

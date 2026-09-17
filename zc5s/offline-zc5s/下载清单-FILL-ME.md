# zc5s 离线包清单 · MiniMax M2.7 AWQ

更新时间：2026-07-21

本包固定为一个镜像，并共享 E 盘 `offline-xt` 中唯一需要的 M2.7 AWQ；不重复复制模型，也不下载或携带 M2.7 FP8、Qwen3.5-397B 等其他权重。

## 固定内容

| 内容 | 来源 | 目标 | 状态 |
| --- | --- | --- | --- |
| M2.7 AWQ 权重 | `E:\offline-xt\models\MiniMax-M2.7-AWQ` | 共享原目录 | 44片权重，不复制、不联网下载 |
| vLLM 镜像 | `vllm/vllm-openai:v0.24.0-cu129` | `images/zc5s-vllm-0.24.0-cu129.tar` | 本机构建并导出 |
| 部署脚本 | 本仓库 `scripts/` | `scripts/` | 随包携带 |
| 完整性清单 | 本包全部交付文件 | `MANIFEST.sha256` | 最后生成 |

## 兼容性边界

- GPU：8×RTX 4090 48GB，计算能力 `sm_89`。
- 容器：vLLM 0.24.0、PyTorch CUDA 12.9。
- 宿主 NVIDIA Linux 驱动：必须 `>=575.51.03`。
- RTX 4090 是 GeForce 卡，不使用 A40 数据中心卡方案中的 `cuda-compat` 绕过旧驱动；这样可避免镜像导入成功、CUDA 启动失败的假兼容。
- 宿主不需要安装 CUDA Toolkit；只需要合格的 NVIDIA 驱动、Docker 和 NVIDIA Container Toolkit。
- 容器用户态与银河麒麟发行版解耦，但 Docker/NVIDIA Container Toolkit 是否能在具体麒麟版本安装，仍需现场执行 `scripts/recon.sh` 确认。

## 包结构

```text
offline-zc5s/
├── images/zc5s-vllm-0.24.0-cu129.tar
├── models/MODEL-SOURCE.txt  # 指向同盘 ../offline-xt/models/MiniMax-M2.7-AWQ
├── scripts/
├── system/                  # 按现场麒麟包格式补Docker/toolkit/驱动
├── README-安装.md
└── MANIFEST.sha256
```

## 制作命令

在联网 Linux/WSL 环境中：

```bash
cd offline-zc5s/scripts
export OUT=/mnt/e
./prepare-offline.sh all
```

模型不进入 zc5s 包的 SHA256 清单；它继续使用 `offline-xt` 已有的完整权重及其校验记录。现场若挂载路径不是 `/offline-xt/models`，通过 `MODEL_SOURCE` 和 `MODELS_DIR` 指定实际路径。

# DeepSeek-V4-Flash-0731 / 8 卡 Ascend 910B4 离线部署包

本包用于在单台 8×Ascend 910B4-1（每卡 64 GiB）的服务器上验证
`DeepSeek-V4-Flash-0731` W8A8 模型。默认配置为 TP8+EP、64K 上下文、
4 路并发和 DSpark 7 个推测 token；这套 0731 权重只记录了 Atlas A3
验证，910B4/A2 必须先完成真实启动、首 token 和稳定性验收。

## 交付范围

本离线包包含：

- 固定摘要的 vLLM Ascend `linux/arm64` 镜像 tar；
- 镜像、脚本和文档的 SHA-256 校验清单；
- 模型下载、校验、环境诊断、启动和测试脚本。

本包不包含约 293 GiB 的模型权重。已下载的权重目录需要单独复制到：

```text
models/DeepSeek-V4-Flash-0731-w8a8/
```

## 离线镜像

目标服务器为 ARM64 架构。离线镜像 tar 需在目标机上通过以下脚本生成（见下文）：

```text
images/vllm-ascend-nightly-main-20260804-arm64.tar
```

- OCI index digest（multi-arch）：`sha256:ade04e75aa4a888df5dfb7917f21e7d9178014d5f5e52b358f2cd1d8897f46ce`
- ARM64 manifest digest：`sha256:8dd01aa0e0e5c4b04d3d715f483351af24c626c30373215e74238cf389fc2a93`
- 平台：`linux/arm64`
- 运行时：vLLM 0.26.0、CANN 9.0.1、DeepSeek V4 DSpark 支持
- 离线加载后的本地标签：`deepseek-v4-flash/vllm-ascend:20260804-arm64`
- 文件大小：`6364067840` bytes
- 文件 SHA-256：`57bbe948bec21654eebdcdfe9bbbc939c6054ba40592d75f8b6ee73403c557a1`

> **注意**：包内现有的 `vllm-ascend-nightly-main-20260804-amd64.tar` 是
> `linux/amd64` 镜像，**不能**在 ARM64 目标机上使用。请在目标机上运行
> `scripts/pull-arm64-image.sh` 生成 ARM64 tar，或直接使用 `./start.sh pull`
> 在线拉取。

## 使用方法

先在目标 Linux 服务器上校验交付文件：

```bash
cd offline-dsv4-0731
sha256sum -c PACKAGE-SHA256SUMS
chmod +x start.sh scripts/*.sh
```

复制模型权重后，直接离线加载已生成的 ARM64 镜像：

```bash
./start.sh load
```

然后执行离线验证：

```bash
./start.sh load
./start.sh verify
./start.sh preflight
./start.sh diagnose
./start.sh start
./start.sh logs
./start.sh test
```

`docker load` 会先恢复固定镜像 ID，脚本核对 ID 和 `arm64` 架构后再创建上述
本地标签；启动过程不依赖远程仓库引用。

如果目标机无法联网生成 tar，也可在目标机上直接执行 `./start.sh pull`
在线拉取固定 ARM64 manifest（`--platform linux/arm64`）。

服务启动参数固定启用 `--enable-auto-tool-choice`、
`--tool-call-parser deepseek_v4` 和 `--reasoning-parser deepseek_v4`。
`./start.sh test` 会发送真实的 `tools + tool_choice: "auto"` 请求，并要求
响应中返回 `get_weather` 工具调用；没有 `tool_calls` 时测试直接失败。

管理命令：

```bash
./start.sh status
./start.sh stop
```

只有目标机能联网且包内镜像缺失时，才使用 `./start.sh pull` 从已验证的
DaoCloud 国内代理拉取固定 digest。`./start.sh download` 可从 ModelScope
固定 revision 断点续传模型，但不属于完全离线流程。

## 默认参数

| 环境变量 | 默认值 | 说明 |
|---|---:|---|
| `PORT` | `8000` | OpenAI API 端口 |
| `MAX_MODEL_LEN` | `65536` | 最大上下文 |
| `MAX_NUM_SEQS` | `4` | 最大并发序列数 |
| `MAX_BATCHED_TOKENS` | `4096` | 单轮批处理 token 上限 |
| `GPU_MEMORY_UTILIZATION` | `0.90` | NPU HBM 使用比例 |
| `SPECULATIVE_METHOD` | `dspark` | 排障时可改为 `mtp` |
| `NUM_SPECULATIVE_TOKENS` | `7` | MTP 模式应改为 `1` |
| `ALLOW_BUSY_NPU` | `0` | 检测到其他 NPU 进程时拒绝启动 |
| `ARCH` | `arm64` | 镜像架构（目标机为 ARM64；排障时可设 `amd64`） |

不要一开始直接启用 1M 上下文或高并发。当前 NPU 上如有其他服务，必须先
停掉相关业务进程；本包不会自动停止或删除其他容器和进程。

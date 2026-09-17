# wurenllm 三套独立离线方案

三个目录互不引用；选择哪套，就只复制该目录到目标服务器：

| 目录 | 拓扑 | GPU |
|---|---|---|
| `minimax-m2.7-awq/` | 单机 | 4 × A40 |
| `qwen3.5-397b-a17b-awq/` | 单机 mp 或双机 Ray | 8 × A40 或 4 + 4 × A40 |
| `kimi-k2.6/` | 双机 Ray | 6 + 6 × A40 |

| 方案 | 独立镜像归档 SHA-256 |
|---|---|
| MiniMax | `6B0D9980E912A3BA404F79C20F0BF4DB3835E4FC0F258EEEC106BFF25DF38497` |
| Qwen | `8C55174A6C39D15817BFDE32DA4F3B06F10EBC2B0F01994952263BAD0801E372` |
| Kimi | `19942DF37FD8BCF20EFEF29E2AD84868FC7D1F83CF59538AE5F5CB6140BD7079` |

每套目录都固定包含：

```text
README.md
start.sh
images/<本模型唯一镜像归档>.tar
models/<本模型唯一模型目录>/
```

镜像统一基于经国内镜像验证的
`docker.m.daocloud.io/vllm/vllm-openai:v0.24.0-cu129`，固定摘要
`sha256:6b005c78cd17a1f0215f31e95d183833f4dfd6167c4473241b80d1c8843b91e8`。

脚本只保留模型加载、GPU/跨机并行和显存边界所需参数。工具调用 parser、
reasoning parser、prefix cache、chunked prefill、MTP、并发调优和日志轮转均未混入
基础启动命令；应在目标 A40 完成基础加载后再按业务压测结果添加。

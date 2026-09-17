# DeepSeek-V4-Flash-0731 Q4_K_XL 部署指南

> 本流程已在 2×A100 80GB 上完整实测验证（参数调优 2026-08-02~04，官方镜像部署路径验证 2026-08-08）。
> 目标机器为 **8×RTX 4090 24G** 时，按 §5 调整即可，其余照搬。

---

## 0. 结论速览

- **不需要自编译推理框架**：llama.cpp 官方 Docker 镜像直接 `docker run` 即可，`ngram-map-k4v` 投机解码内置。
- **工具调用（function calling）可用**：OpenAI 格式 `tools`，流式/非流式/`tool_choice=required`/多轮结果回传均实测通过。
- **精度就是天花板**：这个 "Q4_K_XL" 名字里带 Q4，但占 95% 参数的专家层是**原生 MXFP4**（与官方发布比特一致、零损失），注意力 Q8_0。不用再找"更高精度"的量化版。
- **8×4090 可行**：聚合 192 GB 比我们的 2×A100（162 GB 可用）更宽裕，关键在单卡均衡和 PCIe 拓扑，不在总量。

---

## 1. 模型下载

| 项 | 值 |
|---|---|
| Repo | `unsloth/DeepSeek-V4-Flash-0731-GGUF` |
| 文件 | `UD-Q4_K_XL/DeepSeek-V4-Flash-0731-UD-Q4_K_XL-0000X-of-00005.gguf`（5 分片，合计 **144.44 GiB**） |
| 架构 | deepseek4，43 层，284B 总参 / 13B 激活，256 专家（激活 6） |

**注意文件在 `UD-Q4_K_XL/` 子目录下**，直接拼文件名会 404：

```
https://hf-mirror.com/unsloth/DeepSeek-V4-Flash-0731-GGUF/resolve/main/UD-Q4_K_XL/<文件名>
```

- 国内直连 `huggingface.co` 不通，走 hf-mirror.com。
- 单连接可能被限速（我们实测 ~2 MB/s），用 aria2c 等**多连接分片工具**（实测聚合 ~10 MB/s，155 GB 约 4 小时）。
- sha256 从 `https://hf-mirror.com/api/models/unsloth/DeepSeek-V4-Flash-0731-GGUF/tree/main?recursive=1` 的 `lfs.oid` 字段获取，下载完务必校验。

> **命名陷阱说明**：我们逐张量核验过此文件的量化类型——里面没有任何 Q4_K 张量。专家层 MXFP4（官方出厂格式）、注意力 Q8_0、其余 F32/BF16。别被 "Q4" 误导成粗量化，也别为"更高精度"去下更大的版本，没有。

---

## 2. 推理框架：官方 Docker 镜像

```bash
# 官方地址（国内可换 ghcr.nju.edu.cn 前缀）
docker pull ghcr.io/ggml-org/llama.cpp:server-cuda-b10326
```

- 我们实测版本 **b10326**（digest `sha256:2b24f0962a5cfa75f58f3fb1809bf88559ab46b23a8565f66ebaef05977943ac`，4.34 GB）。更新的 build 一般也可；镜像 CI 偶有断档，拉最新失败就退回 b10326。
- `server-cuda`（CUDA12 线）/ `server-cuda12` / `server-cuda13` 三条线均可，默认 `server-cuda` 最稳。
- 官方镜像是多架构编译，**已包含 4090 的 sm_89**，无需为 4090 重新编译。
- 前提：宿主机装好 NVIDIA 驱动 + `nvidia-container-toolkit`。自检：
  `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`
- **引擎版本下限 b10223**：更早版本的 K-cache 量化有乱码 bug，别用旧镜像/旧二进制。

---

## 3. 启动命令（实测配置）

```bash
docker run -d --name dsv4-q4kxl --gpus all --restart unless-stopped \
  -p 127.0.0.1:1234:1234 \
  -v /path/to/models:/models:ro \
  ghcr.io/ggml-org/llama.cpp:server-cuda-b10326 \
  -m /models/UD-Q4_K_XL/DeepSeek-V4-Flash-0731-UD-Q4_K_XL-00001-of-00005.gguf \
  --alias deepseek-v4-flash-0731 \
  --host 0.0.0.0 --port 1234 \
  -ngl 999 -c 327680 --flash-attn on \
  --cache-type-k q8_0 --cache-type-v q8_0 --kv-unified \
  --batch-size 2048 --ubatch-size 512 --parallel 4 --jinja \
  --fit off \
  --spec-type ngram-map-k4v --spec-ngram-map-k4v-size-n 16
```

（`-m` 指向第一个分片即可，其余分片自动加载；对外暴露方式按自己环境改 `-p`。）

| 参数 | 作用 / 为什么 |
|---|---|
| `-ngl 999` | 全部层放 GPU |
| `-c 327680` | 320K 上下文（8×4090 显存更多，可再加，见 §5） |
| `--flash-attn on` | q8_0 KV **必须**配 flash-attn |
| `--cache-type-k/v q8_0` | KV 量化省显存，b10223+ 无精度问题 |
| `--fit off` | 关掉自动装配，显存布局手工可控 |
| `--spec-type ngram-map-k4v --spec-ngram-map-k4v-size-n 16` | 零显存投机解码，见 §4 |

---

## 4. 实测参考数据（2×A100 80GB，供对照验收）

- **显存**：320K 上下文静态占用 156,740 MiB；GPU0 最挤（额外扛 embedding + lm_head）。
- **速度**：decode 短上下文 ~40 tok/s、49K 上下文深度 35.9 tok/s；prefill 530 tok/s @49K、全程均值 261 tok/s @313K 满窗。
- **长上下文**：49K token 文档中段插针检索、313K 满窗检索均实测通过。
- **工具调用**：`tool_calls` 结构与参数 JSON 正确，流式增量 delta 标准，`tool_choice=required` 生效，工具结果回传后模型正确引用（2026-08-08 @ b10326 实测）。
- **ngram-map-k4v 投机解码**（三负载中位数）：散文 41.6 / 代码复用 68.6（**+68%**）/ 代码重构 41.4 tok/s。零显存开销、无任何负载变慢，建议常开。收益集中在"输出大量复用输入"的场景（整文件改写等）；**单负载测速会严重高估投机解码，验收要多负载**。
- `--ubatch-size` 1024 可让 prefill +31%，我们因显存不够放弃；8×4090 余量更大，可以试。
- `-sm row`（张量并行）与 KV 量化不兼容，不可用——4090 无 NVLink 本来也不该用（见 §5）。
- **prefill 慢是固有特性**：llama.cpp 尚未实现 V4 的压缩 KV 布局（KV 实占约为官方参考值 3.7 倍），冷灌几十万 token 全新内容要几十分钟；但对话场景每轮只 prefill 增量（前缀缓存命中），日常无感。

---

## 5. 8×4090 24G 调整要点

> 此部分未在 4090 上实测，基于架构与 2×A100 实测显存数据推算。

**能装下**：权重 147,907 MiB ÷ 8 ≈ 每卡 18.5 GB；GPU0 额外 1–2 GB（embedding + lm_head），峰值约 21–22 GB / 24 GB，是最挤的一张。

| 项 | 调整 | 原因 |
|---|---|---|
| 拆分模式 | **保持默认 layer split，绝不用 `-sm row`** | 4090 无 NVLink，张量并行逐层 all-reduce 走 PCIe 会拖死 |
| `-ts` | 给 GPU0 调低配比（如 `-ts 7,8,8,8,8,8,8,8`，按实际显存微调） | 抵消 embedding + lm_head，否则 GPU0 先 OOM |
| split 上限 | 若启动崩在 `GGML_ASSERT(n_graph_inputs < 30)`，需自编译加 `-DGGML_SCHED_MAX_SPLIT_INPUTS=128 -DCMAKE_CUDA_ARCHITECTURES=89` | 8 路切分图输入可能超默认上限（2 卡时未触发，8 卡待实测） |
| PCIe | 每卡至少 PCIe 4.0 ×8，避免 ×4 转接线 | 直接影响 prefill |
| 供电/散热 | 8×450W ≈ 3.6 kW（仅 GPU） | 需相应 PDU；消费卡无 ECC，密集散热要设计 |

其余参数（`-ngl 999` / KV q8_0 / ngram-k4v-16 / `--fit off`）照搬。

**性能预期**：decode 可能比 2×A100 略慢（单 token 顺序穿 8 级流水线，8 次 PCIe 跳）；prefill 可能更快（聚合算力大）。MXFP4 在 4090 上没问题——sm_89 和 A100 一样走 llama.cpp 软件 kernel，不需要 Blackwell 硬件支持。

**显存富余的升级空间**（聚合 192 GB 比我们多 30 GB）：
- 上下文可尝试推到 **512K+**（KV 按层分散到 8 卡）。
- 可以加载 **DSpark 投机解码 drafter**（官方 sidecar `dspark-DeepSeek-V4-Flash-0731-BF16.gguf`，~11 GB）：`--model-draft <sidecar> -ngld 999 --spec-type draft-dspark`，我们在 A100 上实测长上下文 decode **+59%**，只因显存不够未上生产。这是 8×4090 相对我们配置最有价值的增强点。

---

## 6. 已知限制

- prefill 慢是引擎固有（见 §4），不是配置问题，调参无解。
- KV q8_0 必须配 `--flash-attn on`，二者绑定。
- 工具调用依赖 `--jinja` 与 llama.cpp 自带的模板解析。**换 LM Studio 等其他链路时 deepseek4 的 tool parser 未必存在**（我们在 LM Studio 上实测过不可用），照本文用官方镜像则没有此问题。

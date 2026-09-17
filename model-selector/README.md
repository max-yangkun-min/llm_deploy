# 开源模型本地部署选型表与硬件推荐器

这套目录解决两个问题：

1. 用一张可排序、可维护的表记录模型量化档、硬件门槛和部署栈。
2. 每次拿到 `nvidia-smi` 等硬件信息后，自动排除不兼容项并给出最合适的模型档。

目录采用两层结构：

- [model-families.csv](model-families.csv)：广覆盖模型家族库，当前收录 **83 个模型/尺寸、21 个组织**，包括文本、多模态、代码、embedding 和 reranker。这里记录许可证、开放性和vLLM支持状态，但不伪造未经验证的部署版本。
- [models.csv](models.csv)：精确部署档。只有具备明确量化、显存门槛、驱动/CUDA/vLLM组合的条目才进入此表。

“开源模型”在业界经常同时指真正宽松开源和仅开放权重模型。本目录通过 `openness` 与 `license` 分开标记；Llama、Gemma、部分Mistral、Command-R等不能自动视为Apache/MIT式开源。

## 快速使用

Windows：

```powershell
cd model-selector
.\collect-hardware.ps1 -Output hardware.json
# 编辑 hardware.json，补齐互联、用途、上下文等信息
python .\recommend.py .\hardware.json --preference balanced
```

Linux：

```bash
cd model-selector
bash collect-hardware.sh hardware.json
# 编辑 hardware.json，补齐互联、用途、上下文等信息
python3 recommend.py hardware.json --preference balanced
```

偏好可选 `quality`（能力优先）、`throughput`（吞吐优先）和 `balanced`（默认）。`models.csv` 可直接用 Excel/WPS 打开，默认已按硬件要求大致从高到低排列。推荐报告末尾还会列出家族库中“容量可能匹配、但尚无精确部署档”的发现项；使用 `--no-estimates` 可隐藏。

若业务只允许Apache/MIT等宽松许可，将硬件JSON中的 `require_permissive_license` 改为 `true`。注意：许可证最终仍应交由法务按具体模型revision复核。

## 核心模型部署档（高到低摘要）

权重一列全部是 **artifact 实测值**(2026-09-16 逐个仓库统计 `.safetensors` 字节数),不是估算。
上下文取自官方模型卡或仓库 `config.json`；标 * 的是模型卡标称的扩展上限,部署时需在配置里打开 YaRN 等扩展。

| 模型部署档 | 量化 | 最低/推荐硬件 | 实测权重 | 上下文 | 驱动与容器CUDA | vLLM镜像 | 状态 |
|---|---|---|---:|---:|---|---|---|
| DeepSeek-R1 | BF16 | 8×H200 192GB，NVSwitch | 1275GiB | 160K | ≥575.51.03 / 12.9 | `vllm/vllm-openai:v0.24.0-cu129` | 候选 |
| Llama-3.1-405B-Instruct | BF16 | 8×141GB，推荐8×H200 | 756GiB | 128K | ≥575.51.03 / 12.9 | 同上 | 候选 |
| GLM-5.2 | INT4 | 8×A100 80GB | 442GiB | 1024K | ≥570.124.06 / 12.8 | `glm52-vllm:0.24.0-pr38476-cu128-native-r570-a100` | 本地镜像已验证，现场GPU待验收 |
| Kimi-K2.6 | AWQ | 12×A40 48GB，可跨机PP | 554GiB | 256K | ≥545条件兼容 / 12.9 | `xt-vllm:0.24.0-cu129-compat545` | 临时候选 |
| DeepSeek-V3.1 | INT4 | 8×48GB，容量很紧 | 371GiB | 160K | ≥575.51.03 / 12.9 | 官方vLLM镜像 | 候选 |
| Qwen3.5-397B-A17B | AWQ | 8×48GB | 228GiB | 256K | ≥575.51.03 / 12.9 | 官方vLLM镜像 | 工作区规划候选 |
| MiniMax-M2.7 | FP8 | 8×48GB Ada/Hopper | 214GiB | 200K | ≥575.51.03 / 12.9 | 官方vLLM镜像 | 候选 |
| Qwen3-235B-A22B | AWQ | 4×48GB | 116GiB | 256K | ≥575.51.03 / 12.9 | 官方vLLM镜像 | 候选 |
| MiniMax-M2.7 | AWQ | 4×48GB/实例；8卡推荐双副本 | 121GiB | 192K | A40可用R545条件兼容；4090需R575+ | XT或官方镜像 | 工作区用户态已验证 |
| Qwen3.5-122B-A10B | FP8 / AWQ | FP8 4×48GB；AWQ 2×48GB | 118/77GiB | 256K | ≥575.51.03 / 12.9 | 官方vLLM镜像 | 候选 |
| Qwen3-Coder-30B-A3B | AWQ | 1×24GB | 16GiB | 256K | ≥570 / 12.8+ | 官方vLLM镜像 | 候选 |
| Qwen3-32B | AWQ | 1×24GB | 18GiB | 128K\* | ≥570 / 12.8+ | 官方vLLM镜像 | 候选 |
| Qwen3-14B | AWQ | 1×16GB | 9.3GiB | 128K\* | ≥570 / 12.8+ | 官方vLLM镜像 | 候选 |
| Qwen3-8B | BF16 / AWQ | BF16 1×24GB；AWQ 1×12GB | 15.3/5.7GiB | 128K\* | ≥570 / 12.8+ | 官方vLLM镜像 | 候选/诊断 |
| Qwen3-4B | BF16 | 1×12GB | 7.5GiB | 128K\* | ≥570 / 12.8+ | 官方vLLM镜像 | 候选 |

摘要只便于阅读；机器筛选以 [models.csv](models.csv) 的完整字段为准。
每一行的 `verified_repo` / `verified_revision` / `verified_at` 记录了该数值取自哪个仓库的哪个 revision,
`artifact_params_b` 是 artifact 实测参数量(与官方标称不一致时两列并存,不合并)。

## 家族库覆盖

当前包含：

- DeepSeek R1/V3及R1蒸馏系列
- Qwen2.5、Qwen3、Qwen3-Coder、Qwen-VL和Qwen3 embedding/reranker
- Llama 3.1/3.2/3.3/4
- Mistral、Mixtral、Codestral
- Gemma 3、Phi-4
- GLM-4.5/5.2、Kimi K2、MiniMax M2
- gpt-oss、Command-R、DBRX、Falcon
- Yi、InternLM/InternVL、OLMo、Granite、SmolLM、Baichuan
- BGE embedding/reranker

这不是声称覆盖互联网上每一个微调仓库。目录以“基础模型和重要官方变体”为粒度；海量LoRA、角色微调、同模型数百个社区量化仓库不逐个列为独立模型，而是在选择基础模型后验证并锁定具体artifact。

## 为什么还要考虑这些字段

| 维度 | 作用 |
|---|---|
| 单卡显存、总显存、权重大小 | 决定能否加载；总显存不能只等于权重，还要留运行时和KV Cache |
| 上下文、并发、KV Cache精度 | 同一模型“能启动”不代表能承担目标上下文和并发 |
| GPU计算能力与特殊内核 | FP8、稀疏注意力、FlashAttention等可能只支持特定架构；显存够也可能跑不了 |
| TP/PP/副本数 | 决定卡间通信、单请求速度、吞吐和故障域 |
| NVLink/NVSwitch/PCIe/跨机网络 | 大TP依赖高速互联；跨机TP通常不应放在普通10GbE上 |
| 驱动、容器CUDA、PyTorch、vLLM | 它们是一个锁定组合；`nvidia-smi` 显示的CUDA不是宿主Toolkit版本 |
| 模型revision、量化实现、parser | 同名模型的不同权重可能需要不同内核，工具调用与思考parser也会变化 |
| 主存、SSD容量与读速 | 加载大权重、离线包暂存、模型转换都可能需要权重大小数倍的空间 |
| 许可证与数据合规 | 决定能否商用、再分发及是否能进入内网环境 |
| 业务质量与吞吐实测 | 参数量不是最终答案；应使用自己的Agent、编码、中文和长上下文任务评测 |
| 供电、散热、NUMA和稳定性 | 多卡机器常被这些物理条件限制，尤其无NVLink的消费卡集群 |
| 验证状态和来源 | 区分已验证镜像、工作区规划和仅按容量估算的候选，防止把估算当承诺 |
| `verified_repo` / `verified_revision` | 每行数值取自哪个仓库的哪个 revision，可回溯、可复核 |
| `license_id` / `context_source` | 许可的机器可读标识（宽松与否按它判断）与上下文的取值口径（模型卡标称 vs 仓库 config） |

## 推荐流程

1. 确认硬件:站点侧从**已核实的 GPU 目录**(`deploy-portal/data/gpu-catalog.json`,
   15 张卡 = 12 NVIDIA + 3 华为昇腾)里选卡与卡数,型号/单卡显存/算力不再手填;
   命令行侧仍读本目录的 `hardware*.json`,其中 `vram_per_gpu_gib` 必须与厂商页一致,
   `compute_capability` 必须与 NVIDIA 官方算力表一致——**但这一条只对 CUDA 生态成立**:
   昇腾没有 `sm_xx`,该字段留空并另写 `ecosystem=cann`(见下)。
2. 填写用途、多模态需求、最低上下文；选择质量或吞吐偏好。
3. 运行推荐器,先看硬约束通过项,再看「算出来的显存占用」(实测权重 + KV + 余量 → 单卡需求 → 占用率),
   最后看风险提示和“接近但不满足”项。占用率过低意味着这个档配这些卡偏小。
4. 对首选和次选下载前验证国内镜像是否含精确 revision/artifact；失败才告知并转官方海外源。
5. 锁定模型 revision、量化仓库、镜像 tag+digest/SHA256、驱动下限和启动参数。
6. 真实 GPU 上验证 CUDA 初始化、内核、parser、输出质量、KV Cache、首Token、tok/s、并发和72小时稳定性。
7. 将实测值回填 `models.csv`(`python deploy-portal/tools/apply_truth.py` 会把权重/上下文/许可
   按仓库实测值订正,并写上 `verified_repo` 与 revision),把状态从 `candidate` 提升为本地验证。

## 显存怎么核算

`assess()` 是唯一的判定入口(命令行与站点共用),它不把登记表里的显存门槛当权威,
而是按实测值重算:

```
权重 GiB = artifact 里 .safetensors 的实际字节数(实测)
KV GiB   = 元素数/token/层 × 层数 × 上下文 token × 2 字节 / 1024³
合计 GiB = (权重 + KV) × 1.10          # 运行时余量
单卡 GiB = 合计 ÷ TP
判定     = 单卡 GiB ≤ 单卡显存 × 0.92   # 单卡可用比例
```

KV 按模型真实的 attention 结构分三种口径算(MLA / 混合线性注意力 / GQA),
见 `deploy-portal/DEVELOPMENT.md` 5.8。`2 字节` / `1.10` / `0.92` 是工程假设,
不是实测值,界面上逐条标注。结构拿不到的档会留空并注明「只按权重下界核算」,不套公式顶数。

## 非 CUDA 生态(华为昇腾)

硬件 JSON 里可以写 `"ecosystem": "cann"` 表示昇腾。此时:

- **不要填 `compute_capability`。** `sm_xx` 是 NVIDIA 专有标度,昇腾没有这个等级。
  填一个数会让 `fp8_capability()` 拿它去推 FP8 能力,得出假结论。
- **`fp8_supported` 是必填的**,取值必须来自厂商产品页标称值(例如 Atlas 350 官方页
  写明支持 HiF8/mxFP8/mxFP4 → `true`)。没有这个字段时,非 CUDA 生态返回「无法判定」,
  FP8 档会报「需先核实再上」,而不是悄悄当成不支持。
- **算力门槛与 NVIDIA 驱动下限会被跳过。** 登记表里的 `min_compute_capability` 与
  `min_driver` 都是 CUDA 口径,对昇腾不适用。
- **KV cache 只按权重下界核算。** `--quantization ascend` 的 KV 量化是华为专有实现,
  没有可核实的公开公式,因此不套 CUDA 的 2 字节口径,结果里 `kv_gib` 为 `null`
  并带说明。这条是刻意的:套一个错的公式比留空更危险。
- **部署档目录里没有昇腾的档。** `models.csv` 没有 `ecosystem` 列,现有条目都是 CUDA 栈
  (vLLM + CUDA 镜像 + NVIDIA 驱动下限)。推荐结果里会明说这一点,同名模型的 CUDA 方案
  会单独标为「不能直接搬过来」。

现场登记(不选 `gpu_id`)时,不填 `compute_capability` 就**必须**写明 `ecosystem`;
自称非 CUDA 却给了 sm 号会被拒绝。这是为了避免昇腾机器被静默按 CUDA 口径核对。

`collect-hardware.sh` / `.ps1` 只采集 NVIDIA 卡(依赖 `nvidia-smi`)。昇腾机器上它们会
给出提示并以退出码 2 结束,不会去猜 `npu-smi` 的输出格式。

排序不再按 `validation_status` 加分——那会让本工作区试过的方案天然占优。
现在只保留「有可执行部署方法」(+3)并新增显存利用率项(低于 45% 或高于 90% 都扣分)。

## 重要边界

- 表内容量是部署预筛选值，不是性能承诺。`weight_gib` 是 artifact 实测值(统计仓库里 `.safetensors` 的实际字节数),
  但同一模型换一个量化仓库体积就会变,部署前请按 `verified_repo` 指到的那个仓库复核。
- `context_k` 来自官方模型卡或仓库 `config.json`;凡模型卡标称需打开 YaRN 等扩展才能达到的值,`context_source` 记为 `card`。
- 参数量分两列:`total_params_b` 是官方标称值,`artifact_params_b` 是从仓库 safetensors 索引汇总的实测值
  (DeepSeek 系因含 MTP 层会比标称多约 2%)。两者不一致时都保留,不做合并。
- `candidate`/`provisional-local` 行必须在联网准备机和目标GPU上验证后才能用于生产。
- vLLM tag 只是可复现栈的一部分；最终还应记录镜像 digest、离线tar SHA256、PyTorch/CUDA版本和模型revision。
- 不建议为了追求新CUDA单独在宿主安装CUDA Toolkit。容器部署通常只要求合格的NVIDIA驱动与NVIDIA Container Toolkit。

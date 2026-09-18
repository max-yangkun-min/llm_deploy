# 大模型部署管理台

> 开发者请另见 `DEVELOPMENT.md`:技术栈选型与理由、系统边界、实际开发进度、
> 未经修复的已知缺陷与 backlog。本文件面向使用者。

一个纯本地的 Web 管理台,解决两件事:

1. **按硬件推荐模型**:输入 GPU 型号/数量/显存、计算能力、驱动、主存、磁盘和拓扑,
   自动排除不兼容项并按得分排序,给出可落地的部署档。
2. **给出经过社区验证的部署方法**:每条推荐都能直接跳转到本工作区已记录的部署方案
   (含锁定镜像、完整启动命令、分阶段执行步骤、验收清单和已知坑),并附上该模型的
   vLLM 官方配方、引擎官方文档与官方模型卡链接——这些链接由工具实际请求验证过。

## 为什么和 `model-selector` 的结论总是一致

推荐规则只有一份实现。`engine.py` 不重写打分逻辑,而是把
[`../model-selector/recommend.py`](../model-selector/recommend.py) 当作库导入,
整理成 Web API 需要的 JSON。因此命令行工具和网站必然给出同一个答案。

```python
# deploy-portal/engine.py 的核心做法
sys.path.insert(0, str(WORKSPACE / "model-selector"))
import recommend as core
```

想调整推荐规则时,只改 `model-selector/`,网站立即跟着变。

## 模型数据与权威出处从哪来

目录里的数字不采信任何「凭印象填的估算」。每一条权重、参数量、上下文与许可都能追溯到
具体仓库的 revision:

- **权重**取自 artifact 实测 —— 统计该仓库 `.safetensors` 的实际字节数;
- **上下文**取自仓库 `config.json`;凡官方模型卡标称、需打开 YaRN 等扩展才能达到的值,
  单独记 `context_source=card` 并在界面上用 `*` 标出,不和 config 默认值混为一谈;
- **参数量**分两列:`total_params_b`(官方标称)与 `artifact_params_b`(实测),
  DeepSeek 系因含 MTP 层会比标称多约 2%,两列并存、不合并;
- **许可**取 HF 的 `license` 标签与 `license_name`,归一成机器可读的 `license_id`
  (「仅宽松许可」按它判定,而不是按会变措辞的展示名);
- 每行都写 `verified_repo` / `verified_revision` / `verified_endpoint` / `verified_at`,
  界面上直接显示,可点回仓库核对。

硬件(能不能跑得动)同样不采信印象值,而且**不需要你手填型号**:

- **GPU 只从已核实的目录里选**(12 张卡)。每张卡的显存容量/类型/互联都逐字命中厂商
  产品页正文,算力命中 NVIDIA 官方 CUDA-Enabled GPUs 算力表;两条都对不上就不收录,
  页面上直接给出厂商页链接、官方算力表链接、核实日期与正文 sha256。
  A800 / H800 / L20 / A10 / A30 / V100 等已从厂商产品页下线的卡不在目录内。
- **KV cache 按模型真实的 attention 结构算**,分三种口径:MLA(DeepSeek 系 / GLM-5.2 /
  Kimi-K2.6,`kv_lora_rank + qk_rope_head_dim`,各头共享不乘 2)、混合线性注意力
  (Qwen3.5 系,只算 `full_attention` 的层)、GQA(其余)。用一个公式套所有模型会把
  Qwen3.5 的 KV 高估约 4 倍、把 DeepSeek 系高估一倍。
- **显存核算** = 实测权重 + 算出的 KV,再乘 1.10 运行时余量,除以 TP 后与单卡显存的 92%
  比较。`2 字节 / 1.10 / 0.92` 这三个系数是工程预留、**不是实测值**,界面上逐条标注。
- **唯一的例外会如实说出来**:`Meta-Llama-3.1-405B-Instruct` 官方与社区镜像全部 gated,
  KV 结构拿不到,该档就留空并注明「只按权重下界核算」,不会套公式顶一个数。

网站同时把登记值与上游**当前**值逐项对照,即**漂移检查**:上游改了权重或 config 就会露出来。

| 工具 | 作用 | 输出 |
| --- | --- | --- |
| `tools/sync_hf.py` | 抓取 41 个官方/量化组织的模型索引 + 28 个重点仓库的完整元数据 | `data/hf-catalog.json` |
| `tools/apply_truth.py` | 按实测值订正 `models.csv` / `model-families.csv`(`--check` 只报差异,`--refresh` 重新抓取) | 两个 CSV + `data/catalog-verified.json` |
| `tools/sync_docs.py` | 逐个真实请求验证 38 个权威来源与 28 个官方模型卡 | `data/doc-sources.json` |
| `tools/sync_gpus.py` | 逐张核实 GPU 的显存/类型/互联(命中厂商产品页正文)与算力(命中 NVIDIA 官方算力表) | `data/gpu-catalog.json` |

选型口径里的**上下文上限**是反算出来的:见 `model-selector/recommend.py` 的
`max_context_for()`——把 KV 的线性公式倒过来求「这些卡最多能开到多少 K」。
它与正向核算共用同一批系数;算不出时返回 `null` 并说明原因,不给一个看着精确的数。

```powershell
python deploy-portal/tools/sync_hf.py            # 全量,约 15 分钟
python deploy-portal/tools/sync_hf.py --repair   # 只补抓失败的组织与记录不完整的仓库
python deploy-portal/tools/sync_docs.py
python deploy-portal/tools/sync_gpus.py   # 联网核实 12 张 GPU;--check 只比差异
```

下载来源策略:优先国内镜像 `hf-mirror.com`,只有它整体不可用时才回退官方
`huggingface.co`,并在快照的 `endpoint_used` / `endpoint_kind` 中标明实际使用的端点。
抓取失败不会被静默丢弃,会写进快照的 `errors` 字段,页面上原样展示。

踩过的三个坑(已固化在工具里,改动同步脚本时不要绕过):

- 镜像对不带 `User-Agent` 的请求返回 403,必须显式带上。
- 分页 `Link` 头会指回 `huggingface.co`(本机直连超时),必须把主机名重写回镜像。
- 大响应会在约 360KB 处被截断,且表现为 JSON 解析失败而非 HTTP 错误。此时重试偶尔有效,
  重试预算用尽就必须把 `limit` 对半减小重新分页,否则整块数据会静默缺失。

## 启动

只依赖 Python 标准库,不需要安装任何包,不需要联网。

```powershell
python deploy-portal/server.py --port 8787 --open
```

```bash
python3 deploy-portal/server.py --port 8787 --open
```

打开 <http://127.0.0.1:8787/>。加 `--quiet` 可关闭每条请求的日志。

## 页面

| 页面 | 作用 |
| --- | --- |
| **硬件选型** | 从已核实的 GPU 目录选卡(不手填型号)+ 卡数/节点/驱动/上下文/用途;输出 3-5 条真正放得下、且不浪费显存的方案,每条列出实测权重、KV(含口径徽章)、运行余量、单卡需求、显存占用率与空闲显存;可复制 Markdown 报告或导出 JSON |
| **模型目录** | 上层是 19 条可落地部署档(含实测权重、上下文、许可与「登记值来源」),下层是 83 条模型家族库;可按关键词、组织、vLLM 支持、多模态、宽松许可过滤 |
| **真实模型库** | 直接检索从 HF 实抓的模型索引(万个量级),可看 revision/参数量/许可证/最后更新时间;重点仓库还有权重体积、上下文、专家数与量化配置详情 |
| **部署方案** | 7 条已记录方案,按环境分组;详情页给出锁定栈、启动命令、执行步骤、验收清单与常见问题 |
| **部署台账** | kty5l / xt / zc5s 三个环境的硬件、选定档、离线包与硬件红线;可一键按该环境硬件做达标检查 |
| **数据来源** | 说明数据取自哪些文件、国内镜像策略(含已核实的固定摘要)与字段含义 |

## 数据文件

| 文件 | 角色 | 来源 |
| --- | --- | --- |
| `../model-selector/models.csv` | 19 条精确部署档(39 字段,含实测与溯源列) | 工作区既有资产,不复制;数值由 `apply_truth.py` 按实测订正 |
| `../model-selector/model-families.csv` | 83 条模型家族(21 个组织) | 同上 |
| `data/recipes.json` | 7 条部署方案 + 11 条国内镜像登记 | 从工作区文档与脚本提炼 |
| `data/deployments.json` | 3 个环境台账 | 从工作区文档与记忆文件提炼 |
| `data/sources.json` | 抓取来源登记:2 个端点、41 个组织、28 个重点仓库、37 个权威文档 | 人工登记,URL 由 `sync_docs.py` 逐条验证 |
| `data/catalog-verified.json` | 核实缓存:95 个仓库的实测值 + revision + 端点,供 `apply_truth.py` 离线复现 | `tools/apply_truth.py` 生成 |
| `data/hf-catalog.json` | HF 实抓快照(索引 + 重点仓库详情 + 错误明细) | `tools/sync_hf.py` 生成 |
| `data/doc-sources.json` | 权威来源可达性与内容指纹 | `tools/sync_docs.py` 生成 |
| `data/gpu-catalog.json` | 12 张 GPU 的显存/类型/互联/算力 + 厂商页 URL、sha256、核实时间 | `tools/sync_gpus.py` 生成 |
| `../model-selector/hardware*.json` | 参考用的硬件示例(命令行 `recommend.py` 读取,网站不再使用) | 工作区既有资产,不复制 |

设计上刻意不复制 `models.csv` / `model-families.csv` / `hardware*.json`。
这些文件是工作区里正在使用的资产,复制会产生第二份副本并很快失去同步。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 存活检查 |
| GET | `/api/meta` | 数据源路径与条目数 |
| GET | `/api/gpus` | 已核实的 GPU 目录(12 张卡)+ 算力表来源与发布时间 |
| GET | `/api/catalog` | 部署档与家族库,支持 `q`/`organization`/`vllm_only`/`multimodal`/`permissive` |
| GET | `/api/recipes` | 部署方案与镜像策略,支持 `profile`/`q` |
| GET | `/api/deployments` | 环境台账 |
| GET | `/api/hf-catalog` | 实抓模型索引,支持 `q`/`organization`/`task`/`license`/`sort`/`limit`/`offset` |
| GET | `/api/hf-detail` | 单个重点仓库的完整元数据 + 与该部署档的核对结果 |
| GET | `/api/docs` | 权威来源清单,支持 `profile` 过滤 |
| POST | `/api/recommend` | 硬件 JSON(必须含 `gpu_id`)→ 3-5 条方案 + 未通过项与缺口原因 |
| POST | `/api/check` | 硬件 JSON + `profile_id` → 单档达标检查 |

示例:

`gpu_id` 取自 `/api/gpus`。单卡显存与算力由服务端按核实目录填,**不接受调用方自带
`vram_per_gpu_gib`**——否则等于让用户手填数值绕过判定。

```bash
curl -sS -X POST http://127.0.0.1:8787/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"hardware":{"gpu_id":"a100-pcie-80","gpu_count":8,"nodes":1,
       "driver_version":"570.124.06","host_ram_gib":512,"disk_free_gib":1000,
       "context_k":32,"workload":"agent,coding"},"preference":"balanced","top":5}'
```

## 自检

```bash
python deploy-portal/tools/smoke_test.py
```

在进程内起服务并逐个断言全部接口,覆盖推荐、目录过滤、达标检查、快照分页与分面、
权威文档可达性、参数校验、404 处理与目录穿越防护,以及**防「假数据」「假硬件」「死控件」
与「整页静默失效」回归**的断言,共 120 项。

## 维护方式

- **推荐规则**:改 `model-selector/models.csv` 或 `recommend.py`,网站自动生效。
- **订正目录数值**:跑 `python deploy-portal/tools/apply_truth.py`
  (`--check` 只报差异,`--refresh` 重新联网抓取)。它会按实测值改写权重/上下文/许可,
  并补上 `verified_repo` 与 revision。不要手工填数字:手工填的值没有出处,自检会失败。
- **新增部署方案**:在 `data/recipes.json` 增加一条,`profile_id` 指回 `models.csv` 的 `model_id`,
  推荐结果就会自动出现“查看部署方案”入口。新方案必须能追溯到工作区里的真实文档或脚本。
- **新增环境**:在 `data/deployments.json` 增加一条,`hardware` 里填 `gpu_id`(取自
  `/api/gpus`);现场改装过、厂商页查不到的卡可以填 `gpu_id_unverified` + `verification_note`,
  页面会明确标出「未经厂商页核实」,不会冒充已核实。
- **新增 GPU**:在 `tools/sync_gpus.py` 的卡表里加一张,跑一次 `sync_gpus.py`;
  显存/算力命不中厂商页或官方算力表就会标 `failed`,此时**要么换卡、要么修标记,
  不要改成凭记忆的数值**。
- **扩大模型覆盖面**:在 `data/sources.json` 的 `organizations` 增加组织 id
  (先探测该组织在镜像上是否真有模型,空组织会拉低分面质量),再跑 `sync_hf.py`。
- **新增权威来源**:在 `data/sources.json` 的 `doc_sources` 增加一条。填 `profiles` 表示
  只在该部署档的页面出现;没有部署档的方案(如 GGUF 路径)用 `recipe_ids` 点名,
  例如 `"recipe_ids": ["deepseek-v4-flash-gguf-llamacpp"]`。**不填这两个键的条目不会
  出现在任何方案页上**——没有显式挂接的文档不等于所有方案的依据。
  加完必须跑 `sync_docs.py`,只有确认返回 200 的链接才会进入已验证清单。
- **新增方案用到的权重仓**:在 `tracked_repos` 里给该仓库加 `recipe_ids`,
  `sync_docs.py` 会把它抄到自动生成的模型卡条目上(GGUF 方案就是这样挂上
  `unsloth/DeepSeek-V4-Flash-0731-GGUF` 的)。

### 状态词汇(沿用 `models.csv`)

| 状态 | 含义 |
| --- | --- |
| `verified-local` | 本地已构建并通过验收 |
| `validated-user-workspace` | 用户态已在实际配置上验证 |
| `provisional-local` | 已规划脚本与文档,但明确条件兼容或权重未就绪 |
| `candidate` | 仅按容量与版本组合筛出的候选 |

容量估算项永远不会覆盖精确部署档,也不会被标成生产可用。

## 边界

- 推荐结果是**部署预筛选**,不替代实机验收。上线前必须锁定模型 revision、
  量化仓库、镜像 tag + digest、驱动下限与 parser,并在目标 GPU 上验证内核、输出质量与压测。
- 支持工具调用的部署,验收必须发送带 `tools` 与 `tool_choice: "auto"` 的真实请求;
  纯文本生成不算通过。
- 许可证最终应由法务按具体模型 revision 复核。
- 本服务只监听 `127.0.0.1`,面向单机使用,未做认证与多用户隔离。

## 关于 `tools/apply_patch.py`

本机 `apply_patch` 是 `.bat` 包装器,从 PowerShell 直接调用时会把 patch 里
反斜杠加双引号的序列破坏掉,导致 patch 校验失败或文件被静默写坏。
`tools/apply_patch.py` 改由 Python 的 `subprocess` 构造 argv,绕开该问题,
并强制校验 patch 最后一行必须精确是 `*** End Patch`。

```powershell
python deploy-portal/tools/apply_patch.py <patch-file>
```

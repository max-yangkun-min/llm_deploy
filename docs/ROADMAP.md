# 接下来要做的工作(单一真源)

这份文档是「接下来做什么」的**唯一**清单。2026-09-18 整理之前,同一批待办同时躺在
三处(`ACTIVE_TASK.md` 的口头待办、`DEVELOPMENT.md` 的 5.10/5.11、`MEMORY.md` 的
Next actions),互相之间已经漂移——其中两处当时就过期了。现在其他文档只留指针,
条目只在这里维护。

## 怎么用

- 每项都带**依据**(实测数字或代码位置)与**验收标准**(能变成断言或可执行检查)。
- 没有依据的条目不进这张表:「核不到就留空并写明原因」这条原则同样适用于待办。
- 做完一项:补断言 → `python tools/ci.py` → 把状态改成完成,并留下证据(命令 + 输出)。
- `P0` 现在就做(不需要外部输入);`P1` 价值最高但有前置条件;`P2` 是数据真实性债务;
  `P3` 是工程债;`P4` 只在明确要求时做。

## 状态总览

| 编号 | 优先级 | 事项 | 前置条件 | 状态 |
|---|---|---|---|---|
| R1 | P0 | 交接/文档一致性收尾(4 处,其中 2 处是「报了假数」) | 无 | 已完成 2026-09-18 |
| R2 | P1 | 昇腾方案改从**公开权威来源**建立(通用平台,不用本机资产) | 无(已按现有三张卡做完) | 已完成 2026-09-18 |
| R17 | P1 | 现有 7 条方案的来源只有本工作区路径(与 R2 同一个通用性缺口) | 无 | 可开工 |
| R3 | P1 | KV 上限反向提示(这张卡最多能开多长) | 无 | 可开工 |
| R4 | P1 | `--kv-cache-dtype fp8` 作为输入项 | 无 | 可开工 |
| R5 | P2 | `quality_score` / `throughput_score` 仍是人工评分 | 需在目标卡跑基准 | 可开工(慢) |
| R6 | P2 | `databricks/dbrx-instruct` 许可未核实 | 需人工确认条款 | 等外部 |
| R7 | P2 | 是否用 `DeepSeek-V4.1-Flash` 替换 0731 | 需决策 | 等决策 |
| R8 | P2 | `Meta-Llama-3.1-405B` 的 KV 结构无法核实 | 官方 config 全 401 | 卡在上游 |
| R9 | P2 | A800 / H800 等下架卡的官方归档页依据 | 需找到可引用的归档页 | 可开工 |
| R10 | P3 | `hf-catalog.json` 19.17 MiB 全量首屏 | 无 | 可开工 |
| R11 | P3 | 索引过滤是线性全量扫描 | 无 | 可开工 |
| R12 | P3 | 同步工具无并发写保护 | 无 | 可开工 |
| R13 | P3 | 定时任务只在用户登录后触发 | 需要管理员权限 | 可开工 |
| R14 | P4 | 硬件对比视图 / 组织类型过滤 / 台账导出 | 明确要求 | 不做 |
| R15 | 独立任务 | 910B4 真机验收(任务 `deepseekv4-flash-910b4`) | 需要真机 | 等机器 |
| R16 | 独立任务 | 现场硬件 JSON 进来后的流程 | 需要输入 | 等输入 |

---

## R1 交接/文档一致性收尾(已完成)

四项都是「文档或断言与代码不一致」,其中两项是**检查自己报了假数**——比缺检查更糟,
因为人会信它。

1. `.agents/ACTIVE_TASK.md` 的「Task ID / Memory / Inputs / Last updated」连同
   「## Previously active task」被整段复制成了两份(第 40-54 行重复第 25-39 行),
   末次更新时间还停在上一阶段。这是**每次交互第一个被读的文件**,坏掉等于交接断线,
   而当时 CI 全绿——没有任何检查看得见这种坏法。
   修法:去重 + 更新为阶段八;新增 CI 断言「任务记忆文件」
   (`tools/ci.py::check_memory_files`),同时钉住:Task ID 不许重复、
   『## Previously active task』最多一个、必须有 `Last updated:`、`Memory:`/`Inputs:`
   指向的文件必须真的存在。反例已实测:重复 Task ID → FAIL;引用不存在 → FAIL;
   缺 `Last updated` → FAIL。
2. `tools/ci.py::check_project_files` 用 `*/spec.md` 通配统计规范数,把
   `.codex-specs/_TEMPLATE/spec.md` 也算成一份——2 份真规范被报成 3 份。
   修法:下划线开头的目录不计入活规范。
3. `deploy-portal/DEVELOPMENT.md` 5.10 的编号跑到 `1..8` 之后又从 `7.`、`8.` 重来。
4. 同文件 5.11 技术债里 `| 无 CI |` 已经过期——CI 在 2026-09-17 就有了,而且云端
   workflow 已实测转绿。修法:改成「已解决」并写清剩下的债(在线核实不在云端跑)。

验收标准:`python tools/ci.py` 输出「工作流骨架文件 … 规范 2 份」「任务记忆文件 …
ACTIVE_TASK.md 自洽」;`docs/CI.md` 的检查表含这两项。

---

## R2 昇腾部署方案改从公开权威来源建立(通用平台方向)— 已完成 2026-09-18

> 验收标准的第一条原本要求「至少一条 `ecosystem: cann` 的方案,`sources` 全是公开 URL」。
> 实施时改成更直接的形态:昇腾卡的推荐结果直接带**官方支持矩阵**与官方逐模型教程的
> 部署命令(逐字、带 sha256 留痕),而不是在 `recipes.json` 里再抄一份方案——
> 抄一份就等于多一个会过期的真源。下面「验收标准」保留原文,末尾记实际交付。

**方向(用户 2026-09-18 明确)**:这条不是「把某台机器的现场做法搬进网站」。
平台是**通用**的:**不参考本机现场资产**,昇腾的部署方法必须来自**可公开核实的权威来源**。

**现状(实测)**

- `gpu-catalog.json` 15 张卡(12 NVIDIA + 3 昇腾:`ascend-950pr-atlas350`、
  `ascend-300i-duo-96`、`ascend-300i-duo-48`)。
- `recipes.json` 的 7 条方案里**没有 `ecosystem` 字段**,`engine.py::recipe_ecosystem()`
  因此一律按 `cuda` 处理 → 昇腾卡的方案列表是空的。
- `doc-sources.json` 65 条来源里,**昇腾相关 0 条**。
- 现有 7 条方案的 `sources` **全是工作区本地路径**(如 `kty5l/...`),第三方无法核实;
  详情页把它们渲染成「本工作区来源文档」——这正是通用平台要补的另一半。

**可用的公开权威来源(2026-09-18 实测可达)**

| 来源 | URL | 实测 |
|---|---|---|
| vLLM Ascend 官方文档 | `https://docs.vllm.ai/projects/ascend/en/latest/` | 200,90,501 B |
| 同上·可固定版本 | `.../en/v0.23.0/user_guide/support_matrix/supported_models.html` | 200(可引带版本 URL,满足「离线构建可复现」) |
| `vllm-ascend.readthedocs.io/en/latest/` | 重定向到上面的 `docs.vllm.ai` 域名 | 200 |
| 官方仓库 | `https://github.com/vllm-project/vllm-ascend` | 200 |
| 华为官方文档 | `https://www.hiascend.com/document` | 200 |
| 华为加速卡页(已在用) | `https://www.hiascend.com/hardware/accelerator-card` | 200 |
| ~~`gitee.com/ascend/vllm-ascend`~~ | | **404,不引用** |
| ~~`.../en/stable/`~~、~~`.../en/v0.25.0/`~~ | | **404,不引用** |

**关键发现:官方支持矩阵就是一张机器可读的能力表。**
`user_guide/support_matrix/supported_models.html` 按硬件分表:
`Ascend 950 Products`(4 个模型)、`Ascend 950DT`(3)、`A2/A3`(20 + 12)、
`Atlas 300I DUO`(2 + 9)、Pooling 模型(8 + 7)。列名:
`Model / Support / Note / BF16 / Supported Hardware / W8A8 / Chunked Prefill /
Automatic Prefix Cache / LoRA / Speculative Decoding / Async Scheduling /
Tensor Parallel / Pipeline Parallel / Expert Parallel / Data Parallel /
Prefill-decode Disaggregation / Piecewise AclGraph / Fullgraph AclGraph /
max-model-len / MLP Weight Prefetch / Doc`。

- **`Atlas 300I DUO` 与 `Ascend 950` 正是目录里已有的卡** → 这两张卡与模型的匹配
  可以直接用官方口径,不需要任何本机证据。
- `A2/A3` 是官方在列的硬件族,但目录里没有对应卡(见下面的待定项)。
- `Doc` 列链到官方逐模型教程(如 `tutorials/models/DeepSeek-V4-Flash.html`),
  里面是真实的启动命令(`--quantization ascend`、TP/EP、`--speculative-config` 等)。

**做法**:像 `apply_truth.py` 对待 `models.csv` 那样处理昇腾能力事实——
从官方矩阵抓取并留痕(**URL + 版本 + 抓取时间 + sha256**),不在代码或 JSON 里手写;
方案正文引用官方逐模型教程作为部署方法;方案归 `ecosystem: cann`。

**边界(不可削弱)**

- **不把本机现场资产当通用方案。** `deepseekv4-flash/offline-dsv4-0731/` 那类包是
  某台机器的交付记录:只能以 `*-local` 状态存在,并写明「本工作区现场记录,不是通用方法」;
  **不得据它生成通用的昇腾方案。**
- 不把某台机器的具体配置(如「8×910B4」)写成平台对所有昇腾卡的推荐;
  卡与模型的匹配只能来自官方支持矩阵的硬件列。
- 昇腾方案不含 NVIDIA 专有字段(`min_driver` / `sm_*`)。
- 来源只取官方/厂商域;上表标 404 的地址不引用。

**验收标准**

- 至少一条 `ecosystem: cann` 的方案,`sources` **全是公开 URL**,且
  `python tools/ci.py --online` 的「权威文档可达性」覆盖到它们(离线跑时该项报 SKIP,
  不冒充通过);
- 能力事实(W8A8 / TP / EP / max-model-len 等)**逐字来自官方支持矩阵**,并有断言
  钉住「不是手写值」;
- 昇腾卡请求 `/api/recommend` 不再返回空方案;若某张卡在官方矩阵里确实没有对应模型,
  必须明确说明并给出矩阵链接(而不是留一个没有解释的空列表);
- 新增断言挂进 `smoke_test.py`,与现有 20 项昇腾反回归放在一起。

**需要你定的一件事(已收窄)**:目录要不要按官方 `A2/A3` 产品名单扩卡。
官方矩阵覆盖 A2/A3 族,而目录里没有对应条目;不扩也能先做现有三张卡
(950PR 与 Atlas 300I Duo 都在官方矩阵内)。**扩卡也只能按官方文档里出现过的产品名加**,
不能为了让某条方案挂上去而把 910B 之类硬塞进目录。

**实际交付(2026-09-18,已实测)**

- `deploy-portal/tools/sync_ascend.py` 抓 vllm-ascend 官方**稳定版 v0.23.0**:
  支持矩阵(10 张表 / 96 行能力 / 7 个硬件族)+ 矩阵 `Doc` 列引用的 31 份逐模型教程,
  每条来源留痕 URL + 文档版本 + 抓取时间 + sha256 + 字节数,写入
  `data/ascend-support-matrix.json`(只由工具写入)。
- `engine.official_family_match`:官方族名必须逐字出现在厂商核实过的卡名里
  (归一化后子串相等;不足 4 字符的族名不参与匹配)。实测
  `ascend-300i-duo-96` / `-48` → `Atlas 300I DUO`(15 个模型行);
  `ascend-950pr-atlas350` → **不匹配**,页面写明原因并给矩阵链接。
- 推荐页新增「官方支持矩阵(公开来源)」区块:官方能力表逐字照搬 + 官方教程里对应
  硬件族 tab 的部署命令(折叠展示,标明抽取了几个代码块,带原文链接)。
- 门禁:离线新增「昇腾官方矩阵」,联网新增「在线:昇腾官方文档」(sha256 漂移即报);
  `smoke_test.py` 99 → 109 项。
- 浏览器复核:六视图 0 报错;证据 `output/playwright/21-ascend-official-matrix.png`、
  `22-ascend-official-commands.png`。
- **未做**:按官方 A2/A3 名单扩卡(需要先有厂商页可核实的对应产品名,不能硬塞);
  现场资产仍只以 `*-local` 存在。

## R17 现有 7 条方案的来源只有本工作区路径(P1)

> 放在 R2 后面:它和 R2 是**同一个缺口**的两半——R2 是「昇腾还没有通用方案」,
> R17 是「已有方案的依据也不通用」。

**依据(实测)**:`recipes.json` 的 7 条方案,`sources` **全部**是工作区本地路径
(如 `kty5l/GLM-5.2-部署步骤-8xA100.md`、`kty5l/offline-glm52/start.sh`),
详情页把它们渲染成「本工作区来源文档」。第三方打不开、也核实不了。
`doc-sources.json` 里那 65 条权威来源是按 profile 挂在 NVIDIA 侧的引擎文档与模型卡上,
**与这些方案并没有连起来**。

**问题**:这等于平台当前给出的部署方法,依据只有本机证据。通用平台要能回答
「你凭什么这么说」,而且答案得是任何人都能自己打开的东西。

**验收标准**

- 每条方案在本地出处之外,能引到**可公开核实**的权威来源(引擎官方文档 / 官方模型卡 /
  官方教程),并且 `python tools/ci.py --online` 的「权威文档可达性」覆盖到它们;
- 确实拿不到权威来源的条目:要么降级为「现场记录」并在页面上明说,
  要么从通用方案里移出;
- 前端把两类来源**分开显示**(可公开核实的通用依据 / 本工作区的现场记录),
  不再混在一个「来源」列表里。

**不做什么**:不是把本地路径删掉——它们是有价值的落地记录(哪台机器、什么参数、
踩过什么坑)。要改的是**标注与归属**,不是抹掉证据。

## R3 KV 上限反向提示(P1)

**依据**:当前 KV 只按用户填的上下文算(`--max-model-len` 是输入),不会反算
「这张卡在该模型上最多能开多长」,也不会在接近显存上限时告警。`DEVELOPMENT.md` 5.11
把它列为债务。

**验收标准**:

- `/api/recommend` 的每个 plan 增加 `memory.max_context_k`;算不出来时必须是 `null`
  加 `max_context_note`(写明为什么算不出),**不许编一个数**;
- 用户填的上下文超过该值时,判定从「放得下」变成「放不下」并在说明里指明是 KV 超了;
- 昇腾卡:KV 精度是专有量化、无公开公式,所以 `max_context_k` 必须为 `null` +
  下界说明(与现有 `kv_gib = null` 的口径一致);
- `smoke_test.py` 补断言(含昇腾的 null 分支)。

## R4 `--kv-cache-dtype fp8` 作为输入项(P1)

**依据**:KV 恒按 2 字节(fp16/bf16)核算,`--kv-cache-dtype fp8` 可减半,当前不是输入项。
偏保守不会选错卡,但会低估可承载并发。

**验收标准**:请求可带 `kv_cache_dtype`(默认 `fp16`);`fp8` 时 KV 减半并在口径说明里
写明依据;昇腾生态下该参数不生效时必须在响应里说明,而不是静默忽略。

---

## R5 `quality_score` / `throughput_score` 换成实测(P2)

**依据**:这两个分是排序权重,不是实测数据(页面标为评分)。`DEVELOPMENT.md` 5.11 同行。

**验收标准**:要么在目标卡上跑基准并回填(附命令与原始输出),要么从排序里移除;
不允许继续以「分数」的形式暗示它是事实。

## R6 `databricks/dbrx-instruct` 许可(P2)

**依据**:官方仓库 gated,当前无法核实许可条款。**验收标准**:拿到官方许可页并记进
`MODEL-SOURCE` 类文档;在核实之前该模型不得出现在任何部署档里。

## R7 `DeepSeek-V4.1-Flash` 是否替换 0731(P2)

**依据**:0731 已在 `tracked_repos` 里(`deepseek-ai/DeepSeek-V4-Flash-0731`,
`quant=mxfp4`),V4.1-Flash 未被追踪。**验收标准**:决策后更新
`model-selector/models.csv`(经 `apply_truth.py`,不手改)+ `tracked_repos` + 复跑
`--online` 核实。

## R8 `Meta-Llama-3.1-405B` 的 KV 结构(P2,卡上游)

**依据**:官方仓库与多个镜像全部 401。这**就是** `hf-catalog.json` 里唯一的那条
`errors`(scope `repo:meta-llama/Meta-Llama-3.1-405B-Instruct`,stage `config`)。
当前处理:上下文用官方模型卡标称 128K 并记 `context_source=card`,KV 留空 + 只按权重
下界核算。**验收标准**:拿到官方 config 后回填真实 KV 结构并撤掉下界说明。

## R9 A800 / H800 等下架卡的归档页依据(P2)

**依据**:A800 / H800 / L20 / A10 / A30 / V100 已从厂商产品页下线,因此不进目录;
工作区里真实存在的这类机器只能走台账「现场登记(未核实)」。
**验收标准**:找到官方归档页(不是第三方转载)才收录;收录时快照里保留归档 URL 与抓取时间。

---

## R10 `hf-catalog.json` 首屏体积(P3)

**依据(实测)**:20,096,844 B(19.17 MiB);`index` 24,412 条、`details` 28 个追踪仓库、
`organizations` 41、`errors` 1;`fetched_at` 2026-09-17T07:14:47Z,
`endpoint_kind` = `domestic-mirror`。前端一次性加载后分页。

**验收标准**:首屏不再依赖整份 JSON(分片 / 预聚合 / 按需三种任选),并记录改前改后
`/api/catalog` 响应体字节数的实测对比。

## R11 索引过滤是线性扫描(P3)

**依据**:`hf_query()` 在 Python 内对 24,412 条线性过滤,当前无感。
**验收标准**:先记录实测查询耗时作为基线;超过 10 万条时建反向索引,并给出前后对比。

## R12 同步工具无并发写保护(P3)

**依据**:同步工具直接覆盖 `data/*.json`。**验收标准**:写入改为临时文件 + 原子替换,
或加锁;并补一条断言(写入过程中读到的是旧快照或新快照,不会读到半个文件)。

## R13 定时任务只在登录后触发(P3)

**依据**:`llm-ci-daily`(每天 09:30)/`llm-ci-weekly`(周日 10:00)注册在当前用户下,
未登录不会触发;要「未登录也跑」需 `-RunWhetherLoggedOn` + 管理员权限。
**验收标准**:用 `-RunWhetherLoggedOn` 注册后,锁屏状态下触发一次并确认
`LastTaskResult = 0`。

## R14 可选增强(P4)

硬件方案对比视图、`organization_kind` 过滤、台账导出 Markdown。只在明确要求时做。

---

## R15 910B4 真机验收(独立任务线)

任务记忆:`.agents/tasks/deepseekv4-flash-910b4/MEMORY.md`(自 2026-08-06 起挂着)。
包已经就绪(`deepseekv4-flash/offline-dsv4-0731/`),缺的是机器上的启动、首 token 与
并发 4 下的稳定性验收。

注意:它**不再**是 R2 的解锁条件——R2 已改为从公开权威来源建立通用方案,
不依赖这台机器。这条任务线现在的价值是「现场交付验收」本身,与目录里的
通用昇腾方案互不阻塞。

## R16 现场硬件 JSON 进来后的流程(独立任务线)

1. 走硬件页(选卡,不手填规格)拿到推荐;
2. 对推荐出来的候选,核实其国内镜像里的**确切产物**(tag / digest / 校验和);
3. 只有核实通过才升级该方案的状态;核实失败就标注失败原因,不升级。

---

## 为什么这次不会又漂移

- 「接下来做什么」只有这份文档;`DEVELOPMENT.md` 5.10、`MEMORY.md` 的 Next actions
  已改成指针。
- 交接文件的完整性现在有断言(`check_memory_files`),而不是靠人记得。
- 检查项数不许写死:文档里说几项,就要和 `tools/ci.py` 实际跑的一致
  (这次修的两处正是「报的数和实际不符」)。

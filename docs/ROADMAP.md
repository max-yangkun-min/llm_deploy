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
| R2 | P1 | 昇腾的第一条部署方案 | 见 R2(需决策,可能需真机) | 等决策 |
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

## R2 昇腾的第一条部署方案(P1,价值最高)

**现状(实测)**:`gpu-catalog.json` 有 15 张卡(12 NVIDIA + 3 昇腾),而
`recipes.json` 的 7 条方案里 `ecosystem` 字段**根本不存在**,
`engine.py::recipe_ecosystem()` 因此一律按 `cuda` 处理 —— 所以昇腾卡的方案列表是空的
(比挂一条 CUDA 方案上去更诚实,但确实是缺口)。

**已有的真实资产**(在工作区里,不是设想):`deepseekv4-flash/offline-dsv4-0731/`

| 项 | 实测值 | 出处 |
|---|---|---|
| 目标机 | 8×Ascend 910B4-1(每卡 64 GiB),ARM64 | `README.md` |
| 模型 | DeepSeek-V4-Flash-0731 W8A8,权重约 293 GiB(不在包内) | `README.md` |
| 并行/量化 | `--tensor-parallel-size 8`、`--enable-expert-parallel`、`--quantization ascend` | `scripts/run-server.sh` |
| 上下文/并发 | `--max-model-len 65536`、`--max-num-seqs 4`、`--max-num-batched-tokens 4096`、`--gpu-memory-utilization 0.90` | 同上 |
| 投机解码 | `--speculative-config {method: dspark, num_speculative_tokens: 7}` | 同上 |
| 镜像 | `quay.io/ascend/vllm-ascend` 经 `m.daocloud.io` 代理;OCI index `sha256:ade04e75aa4a…`、arm64 manifest `sha256:8dd01aa0e0e5…` | `README.md` |
| 运行时 | vLLM 0.26.0 + CANN 9.0.1(DSpark) | `README.md` |
| 本地镜像 tar | 6,364,067,840 B,sha256 `57bbe948bec21654…`(另有 amd64 6.57 GB,ARM64 机上不可用) | `README.md` |
| 上游验证范围 | **只记录了 Atlas A3 验证**;910B4/A2 必须先做真实启动、首 token、稳定性验收 | `README.md` |

**两个必须先定的问题**(这就是它为什么不是「直接做」):

1. **卡本身不在目录里。** 目录里的昇腾卡是 950PR / 300I Duo;910B 经尽力核实无厂商页
   逐字证据(官网已换代),所以要么先找到可引用的官方归档页,要么让这条方案走台账的
   「现场登记(未核实)」路径。**不能**为了让方案挂上去而把 910B 塞进目录。
2. **方案状态取哪一种。** 两种都合规,但含义不同:
   - 按 `provisional-local` 登记(与现有 3 条同规格),并在方案里**显式写明**
     「上游只记录 Atlas A3 验证;910B4 未真机验收」。好处:昇腾卡不再是空的;
     代价:必须把未验收写在同一屏里,不能靠状态字段暗示。
   - 等 910B4 真机验收(见 R15)后按 `validated` 登记。更慢,但结论最硬。

**验收标准**(无论走哪条):

- 昇腾卡请求 `/api/recommend` 时 `recipes` 非空(或明确为空并给出原因文案),
  且每条昇腾方案的 `hardware` 块**不含** NVIDIA 专有字段(`min_driver` / `sm_*`);
- 方案的「验收事实」与 `README.md` 里那句「只记录 Atlas A3」一致,不许写成已验证;
- `smoke_test.py` 增加对应反回归断言(现在有 20 项昇腾断言,新增这条要挂在同一处)。

---

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
并发 4 下的稳定性验收。**它同时是 R2 的解锁条件。**

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

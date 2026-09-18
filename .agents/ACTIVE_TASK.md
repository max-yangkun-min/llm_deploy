# Active task pointer

Status: 大模型部署管理台已完成十阶段,下一步工作已收敛到 `docs/ROADMAP.md`(单一真源)。
阶段十(2026-09-18,对应 R17)=方案的**公开依据按归属显式挂接**。原先只有有部署档的方案才
能引到公开来源,而唯一没有部署档的 GGUF 方案走 `engine.global_docs()` 兜底——那等于把
sglang / TensorRT-LLM / Triton / Ollama 的引擎总览全算成一条 llama.cpp 方案的依据,
**假归属比留空更坏**,所以兜底直接删除:新增 `engine.docs_for_recipe()`(只认 `profiles`
命中或 `recipe_ids` 明文点名),`sources.json` 的 `doc_sources`/`tracked_repos` 新增
`recipe_ids`,`sync_docs.py` 把它抄到自动生成的模型卡条目上,GGUF 方案据此拿到 llama.cpp
官方仓库、新增的 `llamacpp-server` 官方文档与它真正用的权重模型卡(65→66,实测 66/66 可达)。
前端详情页与列表页把「可公开核实的通用依据」(带归属列)与「本工作区的现场记录(第三方打不开)」
分开,挂不上时如实降级成「公开依据:暂无」;**19 个本地来源路径全部保留**,不删证据。
门禁:自检 109→112 项(新增不跨引擎、`recipe_ids` 都指向真实方案、无档方案都被点名,
并强化「每条方案都有依据」——原来只要 ≥5 条就能全绿),两条坏法都**实测反向验证过**;
另修掉门禁自身「失败却没有任何细节」的缺陷(`tools/ci.py::failure_detail`)。
实测:`tools/ci.py --online` = 通过 16 · 失败 0 · 跳过 0;沙箱离线 = 通过 11 · 失败 0 · 跳过 1。
已推送 `a8d392e`,云端 Actions 运行 #8 = success。
阶段九(2026-09-18,对应 R2)=按用户「不要参考本地的真实资产,是要做一个通用的平台」的要求,
把昇腾的部署方法改成**只来自公开权威来源**:新增 `deploy-portal/tools/sync_ascend.py`,
从 vllm-ascend 官方**稳定版 v0.23.0** 抓支持矩阵(10 张表 / 96 行能力)与矩阵 `Doc` 列引用的
31 份逐模型教程,每条来源留痕 URL + 文档版本 + 抓取时间 + sha256,落成
`deploy-portal/data/ascend-support-matrix.json`;卡与官方硬件族的匹配只在「族名逐字出现在
厂商核实过的卡名里」时成立,实测 `Atlas 300I DUO` 命中而 `Ascend 950PR` **不匹配**
(官方文档没有对应表述,页面如实报不匹配并给矩阵链接,不硬说那张卡支持该族模型)。
门禁:离线 11→12 项、联网 2→3 项(新增「昇腾官方矩阵」与「在线:昇腾官方文档」漂移检测),
自检 99→109 项;六视图浏览器复核 0 报错。
实测:`tools/ci.py --online` = 通过 15 · 失败 0 · 跳过 0;沙箱离线 = 通过 11 · 失败 0 · 跳过 1。
同一轮还修掉一处「文档说已 gitignore、实际没忽略」:`output/ci/*.json` 一直被跟踪,
现加入 `.gitignore` 并移出索引(本地文件保留)。
阶段八(2026-09-17/18)=把仓库发布到 github.com/max-yangkun-min/llm_deploy(旧 remote 指向的
.../llm 已 404),修掉首次云端 CI 变红的原因,并让 workflow 第一次在真实 runner 上变绿。
推送前拦住两个真危险:①`git add -A` 本来会吞进 12.4 GiB 本地产物(6225.67 MB 的 no-weights
tar.gz、两卷 `*.tar.part01/02`、两个 vendor 源码包),`.gitignore` 只挡了 `**/images/*.tar`、
匹配不到分卷;②索引里有两个指向本地不存在提交的 gitlink(`kty5l/.vendor-fetch-cutlass-v4.4.2`、
`kty5l/source-cache/vllm`),已用 `git rm --cached -f -r` 退出索引并加忽略(本地文件保留)。
入库 229 个文件 / 57.3 MB,无单文件超 50 MB,未发现凭据。云端第一次运行(17331d0)失败,
日志与产物要鉴权(401/403),于是用 WSL Ubuntu 做忠实检出复现(`git archive` 必须显式关掉
`core.autocrlf=true`,否则导出物变 CRLF、凭空多出三个 bash 语法错):真凶只有一个——
`deploy-portal/tools/apply_patch.py` 写死了 Windows 的 codex.exe 路径,Linux 上必然失败,
于是「改文件工具」门禁常年是红的。修法见 `.codex-specs/ci-portability/`:补丁后端改为 codex
(要求真的跑得起来,先 `codex --version` 探测——文件存在不等于可用,WSL 里 PATH 上的 Windows
codex 会 `exec: node: not found`)+ 内置严格引擎(逐字匹配、不认识的指令报错、绝不猜插入位置、
全部算完才落盘);`tools/apply_patch.py` 原是字节相同的第二份副本,现在只做转发;门禁同时测
默认后端与内置引擎(三条真实往返),并新增「Shell 脚本行尾」检查(入库 `.sh` 不得带 CRLF,
查索引不查工作区)。验证:本机(进程能访问 WSL 时)`python tools/ci.py` 为「通过 10 · 失败 0 ·
跳过 0」;沙箱里 WSL 被拒(`E_ACCESSDENIED`)时同一项如实报 SKIP(9 · 0 · 1);WSL 内
`python3 tools/ci.py` 为「通过 9 · 失败 0 · 跳过 1」(EXIT=0),那里跳过的是 `C:` 盘余量。
修复后推送的 8b03239 云端运行 #2 与 5cd30d6 运行 #3 均为 success。

Task ID: deploy-portal
Memory: `.agents/tasks/deploy-portal/MEMORY.md`
Inputs: `.agents/tasks/deploy-portal/INPUTS.md`
Last updated: 2026-09-18 (Asia/Shanghai) — 阶段十(R17 方案的公开依据按归属显式挂接)已完成并验证

## Previously active task

Status: DeepSeek 0731 ARM64 image archived and split; target 910B4 validation pending
Task ID: deepseekv4-flash-910b4
Memory: `.agents/tasks/deepseekv4-flash-910b4/MEMORY.md`
Inputs: `.agents/tasks/deepseekv4-flash-910b4/INPUTS.md`
Last updated: 2026-08-06 (Asia/Shanghai)

Read the referenced files before continuing a task. Update this pointer only
when the user starts, switches, completes, or explicitly clears a task.

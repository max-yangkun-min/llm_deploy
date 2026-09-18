# Active task pointer

Status: 大模型部署管理台已完成十一阶段,下一步工作已收敛到 `docs/ROADMAP.md`(单一真源)。
阶段十一(2026-09-18,对应 R3)=**上下文上限反算**。上下文此前只是输入:填 `context_k`
正算 KV,于是「放不下」与「权重本身就装不下」共用同一句,回答不出「这些卡最多能开多长」。
新增 `recommend.max_context_for(row, hw)`(唯一实现,`assess()` 直接调用),把同一条 KV
线性公式倒过来:`vram × PER_CARD_BUDGET × TP` 扣掉运行时余量与实测权重后全给 KV,再换成
多少 K;**复用正向核算的同一批系数**,否则正反算会用两套假设。`/api/recommend` 与
`/api/check` 的 `memory` 增 `max_context_k`/`max_context_note`/`max_context_memory_k`/
`max_context_model_k`/`max_context_limit`:显存反算值与「该档自身标称上下文」取小并写明
是哪边在限制。实测四个分支:1×RTX4090-24 的 qwen3-coder-30b-awq → 46K(显存限制);
8×A100-80 的 glm52-int4-a100 → 显存侧 1091.9K、标称 1024K → 取 1024K(标称限制);
deepseek-r1-bf16 → null(权重 1275GiB 已占满);llama31-405b-bf16 → null(结构缺失);
昇腾 → 全部 null(专有 KV 量化无公开公式)。超限时新增独立失败信息点明「这是 KV 超了,
不是权重放不下」——判据用**显存反算值**而非 `max_context_k`,后者可能被标称上下文压住,
会把「模型开不了那么长」误报成 KV 超。界面:推荐计划卡、Markdown 导出、台账达标检查表
各加「最长上下文」。门禁:自检 112→120 项,核心是自洽性断言(上限回填必须零失败、
+1K 必须判超),**这条断言第一版写弱了**(只查 KV 那一条失败,于是把反算公式乘 2 后
120 项全绿),改强后同一改动立刻报红,两个方向都反向验证过。
实测:`tools/ci.py` 沙箱离线 = 通过 11 · 失败 0 · 跳过 1;`--online` = 通过 16 · 失败 0 ·
跳过 0(厂商页 15/15、权威文档 66/66、昇腾矩阵与 31 份教程 sha256 未漂移);云端 Actions 运行 #10(`eb75fb6`)成功。
文档里此前把自检写成 119 项(首条断言打印在标题之前,肉眼数字会漏),反复出现的「20 项昇腾反回归断言」也从未成立——已按实测改为 120 与所属时点的真实值(见 `deploy-portal/DEVELOPMENT.md` 1.8.1)。
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
Last updated: 2026-09-18 (Asia/Shanghai) — 阶段十一(R3 上下文上限反算)已完成并验证

## Previously active task

Status: DeepSeek 0731 ARM64 image archived and split; target 910B4 validation pending
Task ID: deepseekv4-flash-910b4
Memory: `.agents/tasks/deepseekv4-flash-910b4/MEMORY.md`
Inputs: `.agents/tasks/deepseekv4-flash-910b4/INPUTS.md`
Last updated: 2026-08-06 (Asia/Shanghai)

Read the referenced files before continuing a task. Update this pointer only
when the user starts, switches, completes, or explicitly clears a task.

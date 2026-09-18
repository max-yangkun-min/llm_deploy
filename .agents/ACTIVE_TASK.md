# Active task pointer

Status: 大模型部署管理台已完成八阶段,下一步工作已收敛到 `docs/ROADMAP.md`(单一真源)。
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
Last updated: 2026-09-18 (Asia/Shanghai) — 阶段八(仓库发布 + 云端 CI 转绿)已完成并验证

## Previously active task

Status: DeepSeek 0731 ARM64 image archived and split; target 910B4 validation pending
Task ID: deepseekv4-flash-910b4
Memory: `.agents/tasks/deepseekv4-flash-910b4/MEMORY.md`
Inputs: `.agents/tasks/deepseekv4-flash-910b4/INPUTS.md`
Last updated: 2026-08-06 (Asia/Shanghai)

Read the referenced files before continuing a task. Update this pointer only
when the user starts, switches, completes, or explicitly clears a task.

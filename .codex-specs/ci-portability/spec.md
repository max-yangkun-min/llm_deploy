# CI 可移植性:补丁后端不应依赖 Windows 的 codex.exe

- 功能 ID:`ci-portability`
- 状态:`已完成`
- 创建:`2026-09-17`
- 最后更新:`2026-09-17`
- 对应任务记忆:`.agents/tasks/deploy-portal/MEMORY.md`

## 意图

为「把仓库推上 GitHub、让云端 CI 真的能当门禁用」解决一件事:**本机专用工具链
不能散落在门禁里**。首次推送后 CI 立刻变红,原因不是代码写错,而是门禁里有一项
依赖只有本机才装着的 `codex.exe`。

## 现状

真实证据:

- 首次推送 `17331d0` 后 Actions 运行结论为 `failure`,job `offline-gate` 停在
  第 4 步「项目 CI(离线门禁)」(2026-09-17 09:24 UTC,run 35204924376)。
- 失败日志需要鉴权才能取,所以在本地用 WSL Ubuntu 做**忠实检出**复现:
  `git -c core.autocrlf=false archive HEAD | tar -x`(必须显式关掉 autocrlf;
  本机 `core.autocrlf=true` 会把导出物变成 CRLF,反而制造出「bash 语法错」的
  假象——这是第一次复现时踩过的坑)。
- 复现结果:`改文件工具` FAIL(详情「整文件替换工具:替换失败:找不到 codex.exe」),
  其余各项全过。与云端失败项数量(1 项)一致。
- 根因:`deploy-portal/tools/apply_patch.py` 只有一条 `CODEX_EXE_CANDIDATES`,
  指向 `~/AppData/Roaming/npm/.../codex.exe`;找不到就 `SystemExit`。
- 顺带发现:`tools/apply_patch.py` 与 `deploy-portal/tools/apply_patch.py` 是两份
  **字节完全相同**的副本(sha256 前 16 位 `4ee22af60cca05f2`),改一处必须记得
  改另一处——这正是「规则只有一份实现」原则被破坏的地方。

## 验收标准

- [x] 没有 codex 的环境里,`python tools/ci.py` 的「改文件工具」为 `pass`(走内置引擎)。
- [x] 有可用 codex 的环境里,默认后端仍是 codex(改动继续进 Codex 补丁记录)。
- [x] `LLM_DEPLOY_PATCH_BACKEND=builtin` 能强制走内置引擎,且「整文件替换」
      「新增文件」两条链路都逐字节一致。
- [x] 内置引擎遇到上下文对不上时**必须失败且不改动文件**,不做模糊匹配。
- [x] 存在但跑不起来的 codex(例如 WSL 里 PATH 上那个需要 node 的 Windows 包装
      脚本)不能被选中。
- [x] 补丁实现只有一份;另一个路径是转发入口,两个入口行为一致。
- [x] 入库的 `.sh` 内容带 CRLF 时 CI 必须报错(CRLF 脚本在 Linux 上会成片报
      `$'\r': command not found`)。

## 边界:明确不做什么

- **不把 codex 装进 CI 环境。** 为了跑一个语法往返替换去装 Node + Codex,代价
  远超收益,而且会把「门禁依赖外部工具」这个毛病原样保留下来。
- **不做「codex 失败就悄悄回落内置引擎」。** 那会把 codex 的真实不兼容掩盖掉。
  显式 `--backend codex` 用不了时直接报错。
- **不支持本仓库工具不产生的补丁语法**(`*** Move to:`、模糊上下文匹配等)。
  不认识的指令直接报错,不猜。
- **不改 `.gitattributes` / `core.autocrlf` 来顺带统一行尾。** 与本功能无关,而且
  会改变用户已有的检出行为;此项只做检查,不做改写。

## 依赖与前提

- 复现需要 Linux 环境:本机用 WSL Ubuntu(`python3` 已在其中)。
- 「入库内容」用 `git cat-file --batch` 读索引判定,不读工作区。
- 联网只用于推送后看云端结果;修复本身不需要联网。

## 风险

- 最坏的错误结论:内置引擎把补丁应用到错误位置却报成功,静默写坏文件。防线有两层
  ——内置引擎逐字匹配上下文,对不上立即失败;调用方
  `deploy-portal/tools/whole_file_replace.py` / `tools/add_file.py` 结束时逐字节
  校验,不一致就回滚/删除并退出非零。
- 次要代价:选择 codex 前会跑一次 `codex --version` 探测(约 0.3 秒),分块替换会被
  多次调用。接受:因为「文件存在但跑不起来」正是本功能要修的那个失败。

## 变更记录

| 日期 | 变更 |
|---|---|
| 2026-09-17 | 创建并完成:定位首次推送 CI 失败原因,补丁后端改为 codex/内置引擎双后端 |

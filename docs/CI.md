# 持续集成与定时检查

这套仓库的检查只有一份实现:`tools/ci.py`。命令行、Windows 定时任务、以及
`.github/workflows/ci.yml` 跑的都是它,所以不会出现「本地过了、CI 挂了」这种
两套规则的问题。

## 一条命令看仓库是否健康

```powershell
pwsh -File scripts\ci\run-ci.ps1            # 离线,秒级
pwsh -File scripts\ci\run-ci.ps1 -Online    # 额外联网核实,分钟级
```

或者直接调 Python(不带日志留痕):

```bash
python tools/ci.py
python tools/ci.py --online --json output/ci/report.json
```

退出码 = **失败项数**,0 表示全通过。`SKIP` 不计入失败,但会单独列出来。

> 为什么把 `SKIP` 单独列出:一个没跑过的检查不能看起来像跑过了。本机 Windows 侧
> 调用的 `bash` 其实就是 WSL 的,它读不到 `D:/...` 这种路径:进程能访问 WSL 时这一项
> 会**真跑**(实测 21 个脚本全过,路径风格 posix);被沙箱挡住 WSL 时报 `SKIP`
> (`E_ACCESSDENIED`)而不是 `PASS`——**跳过和通过是两回事**,它不会把没跑过的说成
> 跑过了。要在真 Linux 下跑这一项:
>
> ```bash
> wsl -d Ubuntu bash -lc "cd /mnt/d/workspaces/blade_agent/llm && python3 tools/ci.py"
> ```

## 检查项

| 检查 | 模式 | 拦什么 |
|---|---|---|
| `C: 盘可用空间` | 离线 | 低于 20 GiB 直接失败。这是 `AGENTS.md` 的硬约束:离线包、镜像 tar、权重动辄十几 GB,先看清磁盘再动手 |
| `Python 语法检查` | 离线 | `tools/` `deploy-portal/` `model-selector/` 全部 `.py`。语法错误会让后面每项都失败,先隔离出来最省时间 |
| `冒烟测试` | 离线 | `deploy-portal/tools/smoke_test.py` 的 112 项断言:接口、数据自洽、前端模块括号平衡、死控件、目录穿越、昇腾官方口径、方案的公开依据是否按归属显式挂接 |
| `实测值核对` | 离线 | `models.csv` / `model-families.csv` 有没有被手改。每个值都要带 40 位 `verified_revision`,所以必须来自 `apply_truth.py` |
| `Shell 脚本语法` | 离线 | 仓库自有的 21 个 `.sh` 做 `bash -n`(只解析不执行)。第三方源码目录(如 `.vendor-fetch-*`、`source-cache`)不在门禁范围 |
| `Shell 脚本行尾` | 离线 | `.sh` 的**入库内容**不能带 CRLF——带 CRLF 的脚本在 Linux 上会成片报 `$'\r': command not found`。查索引而不是工作区:本机 `core.autocrlf=true` 会把工作区换行还原成 CRLF,查工作区必然误报 |
| `GPU 目录自洽` | 离线 | `gpu-catalog.json` 里没有 `verification.status != ok` 的条目,并统计厂商分布 |
| `昇腾官方矩阵` | 离线 | `ascend-support-matrix.json`(R2 的根基):来源必须全是公开 `https`、每条带 sha256/字节数/抓取时间、行的硬件族与教程引用都在文件内、卡与硬件族的匹配重算一遍与留痕一致。这份数据决定昇腾卡能看到哪些官方模型与命令,所以拦的是「来源不是公开页」和「被人手改过」 |
| `改文件工具` | 离线 | 真跑三条链路:整文件替换(默认后端)、整文件替换(内置引擎)、新增文件(内置引擎),每条都逐字节校验。内置引擎用环境变量强制,所以本机即使有 codex,它也被真的跑过 |
| `根目录残留物` | 离线 | 临时脚本 / 待办文件 / 散落日志,只报 `WARN`,**不删用户的东西** |
| `工作流骨架文件` | 离线 | `AGENTS.md`、`docs/PROJECT-MAP.md`、`docs/CI.md`、`docs/ROADMAP.md`、`tools/ci.py`、`scripts/ci/*`、`.github/workflows/ci.yml` 还在不在,规范目录里有没有活的 `spec.md`(`_TEMPLATE/` 不算) |
| `任务记忆文件` | 离线 | `.agents/ACTIVE_TASK.md` 这份跨会话交接:Task ID 不许重复、『## Previously active task』最多一个、当前任务段只能有**一条** `Status:` 行、必须有 `Last updated:`、`Memory:`/`Inputs:` 指向的文件必须真的存在 |
| `在线:GPU 厂商页核实` | `--online` | 15 张卡的显存/类型/互联是否还能在厂商页逐字命中;NVIDIA 卡另外对官方算力表核 |
| `在线:权威文档可达性` | `--online` | 66 个权威来源链接是否还活着(方案页引用的每一条都在其中,所以方案依据的可达性由这项直接覆盖) |
| `在线:昇腾官方文档` | `--online` | vllm-ascend 官方支持矩阵与 31 份逐模型教程是否还可达、sha256 是否漂移。固定引用 v0.23.0 稳定版,所以漂移是**有意义**的信号:上游改一个字就会报出来 |
| `检查模式不改仓库` | `--online` | 三个 `--check`(GPU 厂商页 / 权威文档 / 昇腾官方文档)跑完后,对应的数据文件指纹必须不变。`sync_docs.py` 曾先写盘再打印「--check:未写入」,于是每次联网门禁都刷新 154 行 `checked_at`、把工作区弄脏而输出还说没写 |

失败的三项联网检查会带上**退出码与输出片段**;子进程被硬杀导致输出为空时,明说
「退出码 X,没有任何输出(像被硬杀或静默退出)」。这是实测踩出来的:2026-09-18 有一轮
「在线:昇腾官方文档」返回非零且细节空白,复跑即通过——**空白细节和 `SKIP` 一样会被
误当成没事**,所以它必须被写出来。

**联网项会因本机网络偶发失败,一次 FAIL 不等于参考失效。** 同一台机器实测:2026-09-18
有一轮 `--online` 报「在线:权威文档可达性 可达 14/16」,细节是
`FAIL llamacpp-repo URLError: <urlopen error [WinError 10054] 远程主机强迫关闭了一个现有的连接。>`,
同时昇腾那项也抓取失败;**立刻重跑这两条**,`sync_docs.py --check` 就是「可达 66 / 66,失败 0」、
昇腾矩阵 sha256 未漂移。所以判定顺序是:先看细节里是「取不到」还是「取到了但内容变了」
(`sha256`/`marker` 漂移才是内容变化),取不到就原样重跑一次再下结论。
github.com 上的来源在这一侧尤其容易出现连接被重置。

## 两条刻意的设计

**离线检查必须不联网、不写仓库。** 默认模式只读仓库、秒级完成,任何一次改动后
都能跑。需要联网的核实放在 `--online`,因为厂商页慢且可能超时;把它设成默认会
让人不敢跑 CI。

**第三方代码不进门禁。** `kty5l/.vendor-fetch-cutlass-v4.4.2/` 是下载来的
CUTLASS 源码,`kty5l/source-cache/` 是 vLLM 的 fetch 缓存。它们的语法问题不是
本项目的缺陷,拿它们当门禁只会让 CI 常年红着,最后所有人都学会忽略结果——
那比没有 CI 更糟。判定规则见 `tools/ci.py::is_third_party`。

## 定时任务

```powershell
# 注册(默认:每天 09:30 离线 + 每周日 10:00 联网)
pwsh -File scripts\ci\register-scheduled-task.ps1

# 自定义时间
pwsh -File scripts\ci\register-scheduled-task.ps1 -DailyAt 08:00 -WeeklyDay Monday -WeeklyAt 09:00

# 立即跑一次 / 看上次结果
Start-ScheduledTask -TaskName llm-ci-daily
Get-ScheduledTaskInfo -TaskName llm-ci-daily | Select-Object LastRunTime,LastTaskResult

# 取消
pwsh -File scripts\ci\register-scheduled-task.ps1 -Unregister
```

任务注册在当前用户下,所以不需要提权;代价是只在用户登录后才触发。需要
「未登录也跑」时加 `-RunWhetherLoggedOn`(那一步需要管理员权限)。

### 留痕

每次运行都会写两份文件,并且固定复制一份「最新」的,免得翻时间戳:

```
output/ci/ci-<时间戳>.log    全量输出
output/ci/ci-<时间戳>.json   结构化结果(含每项耗时)
output/ci/ci-latest.log      最新一次
output/ci/ci-latest.json     最新一次
```

`output/ci/` 已在 `.gitignore` 里,所以这些留痕不会污染提交。

## 云端 CI

`.github/workflows/ci.yml` 在 push 与 PR 上跑离线门禁(ubuntu,只需要 Python
3.11+,没有第三方依赖)。在线核实不在云端跑:厂商页偶发超时会变成假失败,
而这类检查按周在本机跑更有意义。

> 验证记录(2026-09-17):
> - 首次推送 `17331d0` 的第一次运行**失败**——job `offline-gate` 停在「项目 CI
>   (离线门禁)」,因为门禁里有一项依赖只在本机存在的 `codex.exe`。
> - 修复见 `.codex-specs/ci-portability/`。修复后的 `8b03239` 云端运行 #2 为
>   **success**:job `offline-gate` 的第 4 步「项目 CI(离线门禁)」通过。
>   运行页:`https://github.com/max-yangkun-min/llm_deploy/actions/runs/35209938457`
> - 同一份代码在本机(能访问 WSL 时)为「通过 10 · 失败 0 · 跳过 0」,WSL 内为
>   「通过 9 · 失败 0 · 跳过 1」(那里读不到 `C:/`,跳过的是磁盘余量那一项)。
>
> 换仓库、改过 workflow 之后,仍然以 Actions 页面为准,别假定它能跑。
>
> 验证记录(2026-09-18,新增「昇腾官方矩阵」离线项 + 「在线:昇腾官方文档」联网项后):
> `python tools/ci.py --online` = **通过 16 · 失败 0 · 跳过 0**(GPU 15/15、
> 权威文档 65/65、昇腾矩阵与 31 份教程 sha256 未漂移);沙箱内离线跑为
> **通过 11 · 失败 0 · 跳过 1**(读不到 WSL,shell 语法报 SKIP)。

## 加一项检查

1. 在 `tools/ci.py` 里写一个 `check_xxx(report)` 函数,用 `report.add(名字, 结果, 详情)` 汇报。
2. 结果只能是 `pass` / `fail` / `skip` / `warn`。
3. 在 `main()` 里调用它;联网的检查放进 `check_online()`。
4. 如果新检查依赖某个外部命令,先探测**这个用法**是否可用,再决定报 `pass` 还是 `skip`。

第 4 条不是形式主义:第一次实现 shell 检查时只探测了「bash 能不能跑 echo」,
探测通过、紧接着每个脚本都报路径错误,把整项判成失败。探测通过不等于这个用法可用。

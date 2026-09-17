# 项目宪法(AGENTS.md)

本仓库的中央规则文件。每次交互都会被读取,所以这里只写**长期有效的东西**:
目标、边界、硬约束、禁止事项。具体的模块细节看 `docs/PROJECT-MAP.md`。

一句话原则:把「一个靠谱的新同事第一天就该知道的事」都写在这里。

---

## 1. 这个仓库是什么

大模型本地部署的工程工作区。两条主线:

1. **部署管理台**(`deploy-portal/` + `model-selector/`)——从**已核实的 GPU 目录**
   选卡,推荐放得下且不浪费显存的模型,并给出经核实的部署方法。
2. **现场离线包**(`kty5l/` `xt/` `zc5s/` `deepseekv4-flash/` `wurenllm-*`)——
   针对具体机器的可交付离线部署包与文档。

**最重要的原则:不编造。** 核不到就留空并写明原因,绝不填一个「大概是这个」的值。
这条优先于「把功能做完整」「把页面填满」等一切考虑。

---

## 2. 技术栈与边界(不可削弱)

- **只用 Python 标准库。** 不引入第三方前端或服务端依赖。
- **前端是原生 ES Module。** 没有构建步骤、没有 `package.json`、没有 npm。
- **管理台只监听本机**(默认 `127.0.0.1:8787`),不是对外服务,不做鉴权。
- **规则只有一份实现。** `model-selector/recommend.py` 是唯一真源,
  `deploy-portal/engine.py` 通过 `sys.path.insert` 导入它。命令行的输出与网站
  的结论必须一致——不许在任一侧另写一套判定。
- **不手改数据。** `models.csv` / `model-families.csv` 的每个值都要带
  `verified_repo` + 40 位 `verified_revision`,只能由
  `deploy-portal/tools/apply_truth.py` 写入;`gpu-catalog.json` 只能由
  `tools/sync_gpus.py` 生成。`smoke_test.py` 会拦手改。
- **不用一次性脚本做整文件替换。** 见第 4 节。

---

## 3. 长期硬约束

### 存储安全(优先级最高)

1. 任何 Docker / WSL / VM / 镜像构建加载、大文件下载、数据集传输、压缩包解压,
   或预计写入超过 1 GiB 的操作,**先**检查 `C:` 可用空间、**先**确认 Docker/WSL
   数据存在哪里。
2. `C:` 可用空间低于 **20 GiB** 时,停掉一切会写盘的工作,只做只读诊断和经明确
   批准的 C 盘处置。先解决磁盘问题,再回到原任务。
3. **绝不对 Docker Desktop / WSL 的 VHD/VHDX 做扩容、迁移、压缩或任何改动。**
   除非用户在未来某一轮明确撤销这条规则。
4. Docker 数据在 `C:` 上时,不要跑大的 build / pull / load。
5. **绝不**清理或删除用户已有的镜像、容器、卷、构建缓存、WSL 发行版、VHD 文件,
   除非逐项明确批准。只允许清理本任务创建并已确认归属的临时资源。
6. 大件放 `D:` 或 `E:`。即使源和目标都不在 `C:` 上,`C:` 紧张时也要停下。
7. 任何经批准的处置前后都要报 `C:` 可用空间;不要在磁盘告警后静默继续。

### 下载源策略

- 任何依赖、源码仓库、容器镜像、模型、驱动等外部下载,先找**国内镜像**,并
  **核实它确实含有所需的那个版本/产物**。
- 不要只看域名就认定镜像可用——先确认 tag / wheel / 校验和 / 文件确实存在。
- 只有国内镜像都没有、或全部核实失败时,才回退海外官方源,**并且要告知用户**。
- 把选定的镜像和确切版本记进构建脚本或部署文档,让离线构建可复现。

### 时间与资源

- 预计长时间运行、持续占用磁盘/网络/GPU/CPU,或可能明显阻塞用户工作的操作,
  执行前先说明预计耗时、收益、风险,并问用户现在是否合适。
- 优先解决最重要、最能快速闭环的问题。耗时的复制、下载、全盘扫描、完整哈希、
  压力测试放到后面,不要未经确认就开始。
- 实际耗时明显超出预估时,立即报告进度和新 ETA,并问继续/暂停/换轻量方案。
- 可复用的数据优先用共享路径或增量方案,避免不必要的大文件复制。

---

## 4. 本机特有的两个坑(改文件必读)

**坑一:必须用 `tools/apply_patch.py` 改文件。**
本机 `apply_patch` 是 `.bat` 包装器,PowerShell 直接调用会把 patch 里的 `\"`
序列破坏掉,**静默写坏文件**。

```bash
python deploy-portal/tools/apply_patch.py <patch-file>
```

patch 文件 UTF-8(建议无 BOM),**最后一行必须精确是** `*** End Patch`。

**坑二:整文件替换走 `deploy-portal/tools/whole_file_replace.py`。**
它分块应用、结束时**逐字节校验**,对不上就整体回滚。历史上用一次性脚本做过一次
替换,因为脚本末尾 `text.split("\n")[:-1]` 丢了最后一行,导致
`web/js/views/recommend.js` 少了一个 `}`,浏览器只报
`SyntaxError: Unexpected end of input`(无位置),整页停在「加载中」而所有接口都是 200。

新增文件用 `python tools/add_file.py <目标路径> <内容文件>`。

其他环境注意:
- PowerShell 会吃掉 Python 内联代码里的 `${...}` 和引号 → 用 here-string +
  `[System.IO.File]::WriteAllText(...)` 写生成脚本,再 `python 脚本`。
- 中文乱码 → 先设 `$env:PYTHONIOENCODING='utf-8'`;
  `.ps1` 文件含中文时要写 UTF-8 **BOM**(PowerShell 5.1 才认)。
- 联网前清空代理(见 `scripts/ci/run-ci.ps1` 头部的说明)。
- **端口双监听陷阱**:旧服务进程会与新进程同时监听 `127.0.0.1:8787`,请求被旧
  进程接走并按旧代码应答。改完后端要用
  `netstat -ano | Select-String ':8787.*LISTENING'` 看 PID,停掉旧的那个。

---

## 5. 验证:改完必须跑

```bash
python tools/ci.py                # 离线门禁,秒级(改完就跑)
python tools/ci.py --online       # 联网核实,分钟级(收尾跑)
```

CI 会跑语法检查、冒烟测试(99 项)、实测值核对、shell 语法、GPU 目录自洽,
并检查工作流骨架文件还在不在。详见 `docs/CI.md`。

**`SKIP` 不等于 `PASS`。** 一项检查没跑起来时会报 `SKIP`,它不阻塞 CI,但会
单独列出来。不要让「跳过」看起来像「通过」。

界面改动还要在浏览器里复跑六个视图,确认 0 控制台报错、没有 `[object Object]`。

---

## 6. 双生态:昇腾与 NVIDIA 口径不同

目录里同时有 NVIDIA(`ecosystem: cuda`)与华为昇腾(`ecosystem: cann`)。
改任何跟算力 / FP8 / 驱动 / KV 相关的代码前,先读
`docs/PROJECT-MAP.md` 的「双生态」一节和
`.codex-specs/ascend-gpu-catalog/spec.md`。

要点:`sm_xx` 是 NVIDIA 专有标度,**不给昇腾做 sm 映射**;昇腾的 FP8 能力看
厂商页标称值、不由算力推导;NVIDIA 驱动下限对昇腾不适用;昇腾的 KV 精度是
专有量化、**没有可核实的公开公式**,所以只按权重下界核算并如实标注。

`smoke_test.py` 里有 20 项昇腾反回归断言钉住这些差别。

---

## 7. 禁止事项

- 不编造数字、型号、显存容量、KV 结构、许可、revision。核不到就留空并写明原因。
- 不手改 `models.csv` / `model-families.csv` / `gpu-catalog.json`;不手改 GPU 规格。
  一张卡要么对上厂商页(以及 NVIDIA 卡的官方算力表),要么标 `failed` 并剔除。
- **不把硬件做成手填。** 推荐接口不接受调用方自带的 `vram_per_gpu_gib` /
  `ecosystem` / `fp8_supported`;选了 `gpu_id` 就必须用目录里的值。
- **不把三种 KV 口径合成一个公式。** 混合线性按全层算会把 Qwen3.5 高估约 4 倍;
  把 MLA 当 GQA(乘 2)会把 DeepSeek 系高估一倍。核实不到就留空。
- 不把 `validation_status` 重新引入排序。之前给「本机验证过」加分等于把
  「我们试过」当成「更适合你的硬件」,用户明确要求去掉。
- 不把 `provisional-local` / `candidate` 标成已验证——没有真机验收就不能升。
- 不要把本机已有的方案当成昇腾的部署方法;部署方法只在同生态内关联。
- **不渲染没有绑定、没有数据、没有可见效果的控件。** 只有一个选项的下拉、
  永远不改变顺序的排序、一点就抛的按钮,都是死控件——要么修数据,要么删控件。
  `smoke_test.py` 会静态扫描(`dead_controls`)。
- 不把 `models.csv` / `model-families.csv` / `hardware*.json` 复制进
  `deploy-portal/`;从 `model-selector/` 读。
- 不做无授权的破坏性操作(`rm -rf`、`git reset --hard`、删除镜像/卷/VHD、
  清空用户数据)。删除前先确认归属。
- 不在根目录留临时脚本。临时文件放 `.tmp/`。
- 不提交大件(镜像 tar、模型权重、deb/rpm/whl)。`.gitignore` 已挡住;
  提交前用 `git status` 确认。
- 不为了「让检查变绿」而放宽断言。如果断言错了,改断言并说明理由;
  如果是代码错了,改代码。

---

## 8. 项目记忆协议

- 每次对话开始先读 `.agents/ACTIVE_TASK.md`。
- 若里面指向一个活跃任务,做任务前先读它引用 memory 与输入清单,把那两个文件
  当作跨会话交接。
- 从记录的「下一步」继续;不要重复已完成的下载、构建、验证或决策,
  除非交接文件明确要求。
- 有实质进展、决策变化、新阻塞或任务完成时,在结束本轮前更新活跃任务 memory。
- 用户开始或上传一个明显不同的任务时,新建
  `.agents/tasks/<task-id>/{MEMORY.md,INPUTS.md}`,然后更新 `.agents/ACTIVE_TASK.md`。
  保留既有任务记录。
- 持久化的上传输入按「工作区相对路径 + 大小 + SHA-256(可得时) + 用途」记录。
  不要依赖只在聊天里出现过的附件。
- 处理 `kty5l`、GLM-5.2、A100 部署或其 Docker 镜像前,先读 `kty5l/MEMORY.md`,
  把它当作当前交接记录。
- 功能级规范放 `.codex-specs/<feature-id>/`(见该目录的 `README.md`)。
  规范里的「验收标准」要逐条变成 `smoke_test.py` 的断言。

---

## 9. 文档在哪

| 要了解什么 | 看哪里 |
|---|---|
| 规则、边界、禁止事项 | 本文件 |
| 模块、入口、数据文件、双生态差别 | `docs/PROJECT-MAP.md` |
| CI 与定时任务 | `docs/CI.md` |
| 管理台设计(技术栈、阶段进度、已知缺陷、backlog) | `deploy-portal/DEVELOPMENT.md` |
| 选型规则与硬件 JSON 格式 | `model-selector/README.md` |
| 某个功能「要解决什么、不做什么」 | `.codex-specs/<feature-id>/spec.md` |
| 当前任务与跨会话交接 | `.agents/ACTIVE_TASK.md` |

文档与代码不一致时,**以代码和断言为准**,并把文档改过来。

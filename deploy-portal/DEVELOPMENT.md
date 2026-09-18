# 开发文档 · 大模型部署管理台

| 项目 | 内容 |
| --- | --- |
| 文档版本 | 1.6 |
| 最后更新 | 2026-09-18 (Asia/Shanghai) |
| 代码位置 | `deploy-portal/` |
| 配套文档 | `README.md` 面向使用者(怎么启动、有哪些接口);本文件面向开发者(技术栈、边界、进度、坑) |
| 当前状态 | 阶段一至八已完成并通过验证;持续集成已落地(`tools/ci.py`)且云端 workflow 已实测转绿;无阻塞项;待办清单见 `docs/ROADMAP.md` |

---

## 1. 这份文档解决什么问题

`README.md` 回答"怎么用"。这份文档回答三个问题:

1. **技术栈是什么,为什么是这些** —— 以及刻意没有引入什么。
2. **边界在哪里** —— 哪些事这个系统负责,哪些事它明确不负责。
3. **现在做到哪一步** —— 哪些已验证、哪些只是计划、哪些已知有缺陷。

任何与本文档冲突的描述,以本文档为准;任何超出本文档边界的改动,先改文档再改代码。

---

## 2. 技术栈

### 2.1 一览

| 层 | 选型 | 落地位置 | 约束 |
| --- | --- | --- | --- |
| 语言 | Python 3.8+ | 后端与工具链 | 只用标准库 |
| HTTP 服务 | `http.server.ThreadingHTTPServer` | `server.py` | 无线程池调优、无反向代理 |
| 业务适配层 | 自写 `engine.py` | `engine.py` | 不自带业务规则 |
| 推荐规则 | `model-selector/recommend.py` | 工作区既有资产 | 单点实现,禁止复制 |
| 前端 | 原生 ES Modules + 手写 hash 路由 | `web/` | 无框架、无构建、无 npm |
| 样式 | 单文件手写 CSS(含 CSS 变量) | `web/css/app.css` | 无预处理器 |
| 数据 | JSON + CSV 文件 | `data/`、`model-selector/` | 无数据库、无 ORM |
| 传输 | JSON over HTTP | 全部 `/api/*` | 无 protobuf、无 GraphQL |
| 同步工具 | 自写爬取/校验脚本 | `tools/sync_hf.py`、`tools/sync_docs.py` | 只用 `urllib` |
| GPU 目录 | 自写核实脚本 | `tools/sync_gpus.py` -> `data/gpu-catalog.json` | 显存/算力必须命中厂商页与官方算力表 |
| 整文件替换 | 自写分块 patch 工具 | `tools/whole_file_replace.py` | 分块写入并逐字节校验,不一致即回滚 |
| 自检 | 自写接口断言 | `tools/smoke_test.py` | 不引入 pytest |

### 2.2 后端

- `server.py` 是薄壳:解析路径与查询参数 → 调用 `engine.py` → 序列化 JSON。
  它不包含任何推荐、核对、筛选逻辑。
- `engine.py` 是**适配层而非实现层**。核心做法是把工作区既有的推荐引擎当库导入:

  ```python
  sys.path.insert(0, str(WORKSPACE / "model-selector"))
  import recommend as core
  ```

  这样命令行工具(`model-selector/recommend.py`)与网站**永远给出同一结论**。
  调整推荐规则只改 `model-selector/`,网站自动跟随。

- 缓存策略:按文件 `mtime + size` 做失效判断,缓存 `models.csv` / `model-families.csv` /
  `hf-catalog.json` / `doc-sources.json` 的解析结果与派生索引。同步工具写完文件后无需重启服务。
- 错误约定:业务参数错误返回 400 + `{"error": "..."}`;资源不存在返回 404;未知 `/api/*` 一律 404;
  静态文件路径做穿越防护(`/../server.py` 被拒绝)。

### 2.3 前端

- `index.html` 只提供外壳:`<main id="view">` + `<script type="module" src="/js/app.js">`。
- `app.js` 提供共用能力:`api()`、`esc()` HTML 转义、`num()`、`toast()`、
  `statusBadge()`、`verificationBlock()`、`docSourceBlock()`。
- 每个视图一个模块,导出 `render(container, params)`,由 `app.js` 的路由按 hash 分发:

  | hash | 模块 | 作用 |
  | --- | --- | --- |
  | `#/recommend` | `views/recommend.js` | 从已核实的 GPU 目录选卡 → 3-5 条方案、达标检查、Markdown/JSON 导出 |
  | `#/catalog` | `views/catalog.js` | 19 条部署档 + 83 条模型家族 |
  | `#/models` | `views/models.js` | 实抓 HF 索引检索 + 重点仓库详情 |
  | `#/recipes` | `views/recipes.js` | 7 条部署方案与镜像策略 |
  | `#/ledger` | `views/ledger.js` | 3 个环境台账 |
  | `#/about` | `views/about.js` | 数据来源与边界说明 |

- 所有插值一律经过 `esc()`;`verificationBlock()` / `docSourceBlock()` 由推荐页与方案详情页复用,
  保证"核对结果"和"权威来源"在任何页面呈现一致。

### 2.4 数据层

| 文件 | 归属 | 写入者 |
| --- | --- | --- |
| `model-selector/models.csv` | 工作区既有资产 | 人工(本工具只读) |
| `model-selector/model-families.csv` | 工作区既有资产 | 人工(本工具只读) |
| `model-selector/hardware*.json` | 工作区既有资产 | 人工(本工具只读) |
| `data/sources.json` | 本工具 | 人工登记 |
| `data/recipes.json` | 本工具 | 人工提炼 |
| `data/deployments.json` | 本工具 | 人工提炼 |
| `data/hf-catalog.json` | 本工具 | `tools/sync_hf.py` 生成 |
| `data/doc-sources.json` | 本工具 | `tools/sync_docs.py` 生成 |
| `data/gpu-catalog.json` | 本工具 | `tools/sync_gpus.py` 生成 |

**刻意不复制** `models.csv` / `model-families.csv` / `hardware*.json`。它们是工作区里正在使用的资产,
复制会产生第二份副本并很快失去同步,因此运行期就地读取。

### 2.5 刻意不引入的依赖

| 不引入 | 理由 | 代价(已接受) |
| --- | --- | --- |
| Flask / FastAPI | 单机单人工具,标准库足够;避免在内网/离线机器上装包 | 需手写路由与错误处理 |
| React / Vue / Vite | 要求 `node_modules` 与构建步骤,破坏离线可用性 | 手写路由与 DOM 渲染 |
| 数据库(SQLite 及以上) | 数据量小,且需要能被 `git diff` 审阅、被人工直接编辑 | 无事务、无并发写 |
| ORM | 同上 | 手写 JSON 读写 |
| 模板引擎(Jinja2 等) | 前端已用模块化 JS 渲染,后端只出 JSON | 无服务端渲染 |
| pytest / requests | 保持"零依赖即可自检";`urllib` 足够 | 断言需自己写 |

一句话原则:**能在标准库内解决,就不引入依赖。** 这是为了"离线机器上解压即用"。

### 2.6 运行环境要求

- Python ≥ 3.8(本机为 `C:\Users\11984\AppData\Local\Programs\Python\Python38\python.exe`)。
- 浏览器需支持 ES Modules(现代 Chrome/Edge/Firefox 均可)。
- **网站本身不需要联网**:所有页面数据来自本地文件,外链仅为可点击跳转。
- 只有同步工具(`sync_hf.py` / `sync_docs.py`)需要联网,且优先走国内镜像。

---

## 3. 架构与数据流

```
                       ┌───────────────────────────────┐
   浏览器  #/recommend →│  web/js/app.js  (hash 路由)    │
            #/models    │  web/js/views/*.js            │
            #/recipes   └──────────────┬────────────────┘
                                       │ fetch /api/*
                       ┌───────────────▼────────────────┐
                       │  server.py  (路由 + 参数校验)    │
                       └───────────────┬────────────────┘
                                       │ 调用
                       ┌───────────────▼────────────────┐
                       │  engine.py  (适配层,无业务规则)  │
                       └──┬──────────┬────────┬─────────┘
                          │          │        │
        import recommend  │          │        │ 读快照
              ┌───────────▼──┐  ┌────▼─────┐  │
              │ model-selector│  │ data/*.  │◄─┘
              │ recommend.py  │  │ json     │
              │ models.csv    │  └────▲─────┘
              └───────────────┘       │ 写入(离线,需联网)
                                      │
                        ┌─────────────┴──────────────┐
                        │ tools/sync_hf.py           │→ hf-mirror.com
                        │ tools/sync_docs.py         │→ docs.vllm.ai / github.com
                        │ tools/sync_gpus.py         │→ 厂商产品页 / NVIDIA 算力表
                        └────────────────────────────┘
```

两条关键设计:

1. **规则单点**:推荐逻辑只有 `model-selector/recommend.py` 一份实现,`engine.py` 只做形状转换。
2. **声明与实测分离**:`models.csv` 的字段是"声明值",HF 抓取结果是"实测值",
   两者在 UI 上永远分栏呈现,不合并、不覆盖。

---

## 4. 边界

### 4.1 功能边界

**在范围内**

- 硬件从**已核实的 GPU 目录**里选择(型号/卡数/节点/驱动/主存/磁盘/互联),不是手填型号;
  单卡显存与算力以厂商产品页与 NVIDIA 官方算力表为准,**不接受调用方自带数值**。
- 按「实测权重 + 按真实 attention 结构算出的 KV + 明确标注的余量」核算显存,
  输出 3-5 条真正放得下、且不浪费显存的方案,并给出未通过项的缺口原因。
- 展示已记录的部署方案(锁定镜像、启动命令、步骤、验收清单、已知坑)。
- 展示实抓的模型索引与重点仓库元数据,并与目录声明值逐项核对。
- 聚合权威部署来源(vLLM 官方文档与官方逐模型配方、引擎文档、官方模型卡)。
- 输出可复制的 Markdown 报告 / JSON。

**明确不在范围内**

- 不代替用户做最终选型决策,不做成本/采购建议。
- 不下载模型权重、不拉取镜像、不部署容器、不修改远程主机。
- 不训练、不微调、不做评测跑分。
- 不做多用户、权限、审计、配额。
- 不做自动化的"最佳实践"生成——部署方法只来自已记录或权威出处,不自由发挥。

### 4.2 最小功能开发(硬规则)

**界面上出现的每一个可交互元素,必须在当前数据下真实可用。不允许出现点了没反应、
或只是摆设的按钮、下拉框、复选框。**

具体判定标准:

1. **有绑定**:控件必须绑定事件处理函数。静态审计(自检项「没有渲染出来却点不动的控件」)
   扫描所有 `<button|select|input|textarea id="...">`,声明的 id 必须在该模块内被引用过;
   `data-copy` / `data-check` 这类钩子必须有对应的 `bindCopyButtons` 等绑定函数。
2. **有数据**:下拉框的候选项来自真实数据。若某个筛选维度的候选项只剩「全部」一项,
   说明数据源缺字段,此时**要么补数据、要么撤掉控件**,不能留一个空壳。
3. **有反馈**:点击后必须有可见结果——数据变化、页面跳转、toast 提示或文件下载。
   只改变内部状态而用户看不到任何变化,等同于死控件。
4. **作用范围与标签一致**:一个筛选器若只作用于两张表中的一张,标签必须写明
   (例:`组织(家族库)`)。标签没写范围的,就必须对界面上所有相关结果生效。
5. **不做「预告式」功能**:不提前渲染尚未实现的入口,也不放"即将支持"的占位按钮。
   宁可少一个控件,也不放一个假控件。

配套检查:

- 静态层:`smoke_test.py` 的 `dead_controls()` 扫描未绑定的控件。
- 数据层:自检断言各筛选分面至少有 2 个候选项、索引项必须带 `pipeline_tag` 与 `likes`。
- 行为层:筛选项必须让两张表的计数同时下降(见自检「目录过滤对两张表都生效」)。
- 人工层:新增或改动控件后,用 Playwright 真的点一遍,并在浏览器控制台确认 0 报错。

### 4.3 已按本规则修复的死控件

以下问题都是「页面能开、接口全 200,但控件其实没用」的类型,已修复并加了防回归断言:

| 症状 | 根因 | 修复 |
| --- | --- | --- |
| 任务类型下拉只有「全部」一项,任务列恒为「—」 | 镜像列表接口的 `expand` 是白名单,未显式声明 `pipeline_tag` / `tags` / `likes` 就不返回 | 把 4 个字段加入 `EXPAND_FIELDS`;补齐后任务类型有 50 个候选、许可证 47 个 |
| 「点赞数」排序点了没变化 | 同上,`likes` 全为 null,排序无数据可比 | 同上,现 24,412 条 100% 有点赞数 |
| 模型库只能看前 100 条,「显示前 N 个」提示等于骗人 | 接口支持 `offset` 但前端没做翻页 | 新增每页 50 条 + 上一页/下一页,条件变更自动回到第一页 |
| 「查看部署方案」跳转后整页「加载失败」 | `recipes.json` 的验收清单和 `server.py` 的仓库核对结果共用 `verification` 键,前者是数组、后者是对象,前端按数组 `.map` 直接抛异常 | 验收清单改名 `acceptance`(7/7),前端改读该键;`verification` 自此只表示仓库核对 |
| 「仅多模态」「仅宽松许可」只影响部署档表,家族表纹丝不动 | 过滤逻辑只写在 `models` 上,`families` 漏了 | 两个条件同时作用于家族表(家族模态按 `;` 分隔解析);断言要求两张表计数同时下降 |
| 控制台常驻 `favicon.ico` 404 | 只放了 `favicon.svg` | `server.py` 把 `/favicon.ico` 指向 `favicon.svg` |

### 4.4 数据真实性边界

这是本项目最核心的一条边界,**任何改动都不得削弱它**:

- 目录声明值与抓取实测值分栏展示,偏差百分比原样给出,不美化。
- **目录里的数值本身也必须是实测值**(阶段五起):权重来自 artifact 实测字节数,
  上下文来自 `config.json` 或官方模型卡标称,许可来自 HF 的 `license`/`license_name`,
  每一行都带 `verified_repo` + `verified_revision` 以便回溯。**不允许出现凭印象填写的值。**
- 一个数有两种合理口径时(如官方标称参数量 671B vs artifact 实测 684.5B),
  **两列并存**,不合并、不取平均;页面上标明各自口径。
- **只有量化档位一致的仓库才用于权重对比**。用 BF16 基座去比 INT4 档会得出无意义的偏差,
  因此 `QUANT_RULES` 做档位归类,不匹配的仓库只列出、标注"非对照档"、不参与比对。
- **硬件规格与 KV 结构同样必须可核实**(阶段六起):GPU 的显存容量/类型/互联要逐字命中
  厂商产品页正文,算力要命中 NVIDIA 官方算力表;模型 KV 结构要来自真实 `config.json` 的
  `num_attention_heads` / `num_key_value_heads` / `head_dim` / `kv_lora_rank` 等字段。
  **命不中就不收录、不填记忆值**;结构拿不到就留空,并按"只按权重下界核算"如实标注。
- **KV 口径按模型真实结构分三类**(MLA / 混合线性注意力 / GQA),不套用同一个公式。
  系数里只有「2 字节 / 1.10 余量 / 0.92 可用比例」是工程假设,必须在界面上标注为非实测。
- 容量估算项(estimation)在视觉上与精确部署档严格分离,**永远不会被标成生产可用**,
  也不会覆盖精确档。
- 抓取失败**不静默丢弃**:写入快照的 `errors` 字段,并在页面上如实展示。
- 快照记录实际使用的端点(`endpoint_used` / `endpoint_kind`),回退到官方上游时必须可见。
- 不复制第三方正文。`doc-sources.json` 只存 URL、HTTP 状态、内容指纹与标题,
  网页正文版权归原站。

### 4.5 运行与安全边界

- 服务**只监听 `127.0.0.1`**,定位为单机本地工具,**无认证、无多用户隔离**,
  不得暴露到公网或共享网络。
- 静态文件路径做穿越防护;`/../` 类请求返回 403/404。
- 网站对业务数据**只读**。唯一会写文件的是两个同步工具,且只写 `data/` 下的 JSON。
- 不执行用户提交的任何代码;`/api/recommend` 的入参只做数值解析与字段白名单处理。

### 4.6 合规边界

- 许可证字段展示的是 HF 抓取值,**最终应由法务按具体模型 revision 复核**,
  本工具的展示不构成法律意见。
- 模型权重与文档正文的版权归各自权利人;本工具只做索引与链接。
- 部署方案中的镜像与命令来自工作区已记录的验证结果,不构成对第三方的授权。

### 4.7 网络与存储边界(遵循工作区 `AGENTS.md`)

- **国内镜像优先**:下载类操作先验证国内镜像是否含精确 artifact,失败才回退海外源并告知用户。
  当前同步工具固定优先 `hf-mirror.com`,官方 `huggingface.co` 仅作回退。
- 同步工具**只写 JSON 文本,不下载权重/镜像**,单次快照在 15 MiB 量级,
  不触及 ">1 GiB 写入" 与 C 盘容量红线。
- 不修改 Docker/WSL 的 VHD/VHDX,不清理用户既有镜像与容器。

---

## 5. 实际开发进度

### 5.1 总览

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| 阶段一 | 推荐引擎复用 + 网站骨架 + 5 个视图 + 自检 | ✅ 完成并验收 |
| 阶段二 | 接入真实 HF 数据 + 权威来源验证 + 核对逻辑 | ✅ 完成并验收 |
| 阶段三 | 数据源扩充(26→41 组织)+ 抓取缺陷根因修复 | ✅ 完成并验收 |
| 阶段四 | 最小功能开发:死控件审计与修复(见 4.2 / 4.3 / 5.5) | ✅ 完成并验收 |
| 阶段五 | 目录按实测订正,去掉估算与无依据的值(见 5.7) | ✅ 完成并验收 |
| 阶段六 | 硬件改为已核实 GPU 目录选型 + 真实 KV 结构核算显存 + 去掉本地方案偏袒(见 5.8) | ✅ 完成并验收 |
| 阶段七 | 双生态(华为昇腾)与持续集成(见 5.9) | ✅ 完成并验收 |
| 阶段八 | 仓库发布到 GitHub + 云端 CI 首次实测转绿(见 5.9) | ✅ 完成并验收 |
| 阶段九 | 昇腾部署方法改从**公开权威来源**建立(R2,见 5.9.1) | ✅ 完成并验收 |
| 阶段十 | 方案的公开依据按**归属**显式挂接(R17,见 5.9.2) | ✅ 完成并验收 |
| 待办 | 其余人工评分项(quality/throughput)实测化等 | 见 `docs/ROADMAP.md`(单一真源) |

### 5.2 阶段一:网站骨架(已完成)

- `server.py` 纯标准库 HTTP 服务;`engine.py` 导入 `model-selector/recommend.py` 复用规则。
- `data/recipes.json`:7 条部署方案 + 11 条国内镜像登记。
- `data/deployments.json`:kty5l / xt / zc5s 三个环境台账。
- 前端 6 个视图 + `app.css` + `favicon.svg`。
- 引用完整性核对通过:方案无悬空 `profile_id`;台账无悬空方案 id;
  每条方案都有 `sources`;台账 `selected_profile` 都能在 `models.csv` 解析到。

### 5.3 阶段二:真实数据接入(已完成)

- 新增接口 `/api/hf-catalog`、`/api/hf-detail`、`/api/docs`。
- 新增「真实模型库」视图(`web/js/views/models.js`),支持关键词/组织/任务/许可证过滤与分页。
- `engine.py` 新增 `verification_for()`、`compare()`、`quant_class()`、`hf_query()`、
  `hf_summary()`、`doc_sources()`(阶段十另加 `docs_for_recipe()`,见 5.9.2)。
- `app.js` 新增 `verificationBlock()`、`docSourceBlock()`,已接入推荐结果页与方案详情页。
- 核对逻辑按量化档位匹配(见 4.4),并回传 `is_reference` / `target_quant` 标记。

### 5.4 阶段三:数据源扩充与缺陷修复(已完成)

登记来源从 26 个组织 / 13 个文档扩到 **41 个组织 / 37 个文档来源 / 19 个重点仓库**
(阶段五为让核对面板比同一档位的 artifact,重点仓库增至 28 个),并逐个真实请求验证。

修掉四个根因级缺陷(全部是实测暴露,不是推测):

| # | 缺陷 | 根因 | 修复 |
| --- | --- | --- | --- |
| 1 | 某大组织整块数据静默缺失 | 大响应被镜像在约 360KB 处截断,表现为 JSON 解析错误而非 HTTP 错误;原代码按固定 `limit=1000` 一次拉取 | 命中截断先把 `limit` 对半减,最小 25,靠游标翻页补齐 |
| 2 | 首屏超时直接放弃整个组织 | 原代码把"首屏超时"等同于"组织无数据" | 首屏即超时改为先把页大小减半重试 |
| 3 | 缩到最小页仍被截断,组织永久残缺 | 瓶颈是单条记录的 `cardData` 体积,不是分页大小 | 新增精简扩展字段回退(`LEAN_EXPAND_QUERY`,去掉 `cardData`),许可证仍可从 `tags` 的 `license:` 前缀取到;并保留全量模式已取到的许可证不被覆盖成空 |
| 4 | `config.json` 直取偶发超时导致记录永远"不完整" | `get_raw()` 完全没有重试逻辑 | 加入与其他接口一致的重试;若仍失败,用 `/api/models/<repo>` 返回的同一份 `config` 兜底 |

另外新增两个能力:`--repair`(只补抓失败组织与记录不完整的仓库)与 `--org`(定向刷新单个组织),
并修掉一个自身 bug:定向模式曾错误回落到全量列表,导致一次 `--org` 变成十分钟全量重抓。

### 5.5 阶段四:最小功能开发与死控件修复(已完成)

用户新增的硬规则是「界面上每一个功能都必须真的能用,不展示空按钮」。
本轮先把它写成可判定的标准(见 4.2),再按标准把 6 个视图渲染出的控件逐个验一遍。

| 工作 | 内容 |
| --- | --- |
| 立规 | 新增 4.2「最小功能开发(硬规则)」:5 条判定标准 + 4 层配套检查 |
| 静态审计 | 扫描全部视图,逐个确认控件 id 是否被本模块引用、`data-copy` / `data-check` 是否真有绑定函数 |
| 数据补齐 | 镜像列表接口的 `expand` 白名单补上 `pipeline_tag` / `tags` / `likes` 等字段,筛选分面从「只有全部」变成任务类型 50 项、许可证 47 项 |
| 交互补齐 | 模型库新增每页 50 条与上一页 / 下一页,条件变更自动回到第一页 |
| 键名冲突 | 验收清单由 `verification` 改名 `acceptance`,与仓库核对结果解耦,「查看部署方案」不再整页崩 |
| 过滤对齐 | 「仅多模态」「仅宽松许可」同时作用于部署档表与家族表(家族模态按 `;` 分隔解析) |
| 控制台 | `/favicon.ico` 指向 `favicon.svg`,6 个页面控制台 0 报错、0 警告 |

6 个死控件的逐条根因与修复见 4.3。自检规模由 45 项增至 **57 项**(阶段五再增至 63 项),
新增断言全部针对这类「接口全 200、功能是假的」问题,明细见 5.6。

### 5.6 验证证据

| 验证项 | 结果 | 方式 |
| --- | --- | --- |
| 接口自检 | **112 / 112 通过**(阶段十口径;本节其余行是阶段五–六的留痕) | `python deploy-portal/tools/smoke_test.py` |
| 权威来源可达性 | **66 / 66 可达,0 失败**(阶段十口径) | `sync_docs.py` 真实 HTTP 请求 + 内容指纹 |
| 抓取快照 | 24,412 条索引 / 41 个组织 / 28 个重点仓库 / 剩余 1 条已记录错误 | `sync_hf.py` |
| 索引字段覆盖率 | sha 100%、likes 100%、tags 99.6%、license 87.7%、pipeline_tag 52.3%(上游只标了一部分) | 快照统计 |
| 重点仓库完整性 | 28 / 28 均具备 revision + 权重大小 + config 字段 | 自检断言 + 人工核对 |
| 目录登记值有出处 | 19 个部署档 + 83 个家族条目全部带 `verified_repo` 与 40 位 revision | 自检断言「登记了核实来源」 |
| 量化档位名副其实 | 19 / 19 从 safetensors dtype 反推的档位与 `quantization` 一致,0 条不符 | `apply_truth.py` |
| 宽松许可判定口径 | 「仅宽松许可」按 `license_id` 判定,不混入展示名不同的许可 | 自检断言 |
| 组织覆盖一致性 | 登记的 41 个组织全部在索引中有数据 | 新增自检断言"登记的组织都有数据" |
| 死控件静态审计 | 0 处未绑定控件;6 个页面渲染的控件全部有事件处理 | 自检 `dead_controls()` |
| 死控件行为验证 | 逐个真实点击:查询/组织/任务/许可证/排序/上一页/下一页/复制(2 处)/导出 JSON/恢复默认/载入示例/查看部署方案/台账达标检查 | Playwright 实点,`output/playwright/` 截图 01-12 |
| 浏览器控制台 | 6 个页面均 0 报错、0 警告(含此前常驻的 `favicon.ico` 404) | Playwright console |
| 前端语法 | 全部视图模块通过 `node --check` | 静态检查 |
| 阶段五界面复核 | 6 个视图重新打开:0 报错 0 警告;模型目录出现「登记值来源(实测)」列;方案详情的核对面板显示来源仓库+revision 与漂移表;「仅宽松许可」筛选后 19→14 条且无白名单外许可 | Playwright 实点,`output/playwright/13-catalog-measured.png` |
| GPU 目录核实 | **12 / 12 通过**;每张卡带厂商页 URL、HTTP 200、正文 sha256 与核实时间 | `sync_gpus.py` |
| KV 结构核实 | 19 个部署档里 **18 个**拿到真实 attention 结构;唯一例外 `llama31-405b-bf16`(官方与社区镜像均 401)如实标注 | `sync_hf.py --repos-only --repair` |
| 阶段六浏览器复核 | 6 个视图重新打开:0 报错 0 警告;推荐页出现 GPU 下拉(12 张卡,标签含显存与 `sm_xx`)、规格行显示架构/显存类型/算力/FP8 + 厂商页与算力表链接 + 核实日期;5 条方案各带实测权重/KV(含三种口径徽章)/余量/合计/单卡/占用率/空闲显存 | Playwright 实点,`output/playwright/15-recommend-gpu.png` 等 15-20 |
| 前端模块括号配平 | 全部视图模块通过静态配对检查(新增断言;缺右括号会让整页停在「加载中」) | 自检 `module_syntax()` |

自检断言分四批累积,合计 75 项:

- 阶段三 4 项防「静默缺失」:登记的组织都有数据 / 重点仓库详情都完整 /
  无部署档的方案也有权威来源 / 有 vLLM 官方逐模型配方。
- 阶段四 12 项防「死控件」:未绑定控件扫描;组织、任务类型、许可证三个分面各至少 2 个候选项;
  索引项必须带 `pipeline_tag`;索引项必须带 `likes`;翻页两次结果不重叠;
  「仅多模态」「仅宽松许可」必须让部署档表与家族表计数同时下降;
  验收清单必须是数组;核对结果不与验收清单共用键;`favicon.ico` 不返回 404。
- 阶段五 6 项防「假数据回归」:每个部署档/家族条目都要有 `verified_repo` 与 40 位 revision;
  每个部署档都要有 `license_id`;每个部署档都要有实测权重;`context_source` 必须是 `card` 或 `config`;
  「仅宽松许可」的返回结果里不得出现白名单之外的许可 id。
- 阶段六 12 项防「假硬件 / 假核算 / 整页静默失效」:GPU 目录接口只返回核实通过的卡;
  每张卡带来源页与 sha256;推荐条数落在 3-5;结果内模型不重复;每条方案都带
  权重/KV/合计/单卡/占用率;占用率不超 90%;单卡场景可出结果;台账里未核实的改装卡
  走 `require_verified=False` 并能看出未核实;推荐必须选 GPU 型号;未知 GPU 返回 404;
  不接受自填单卡显存;前端模块括号必须配平。

### 5.7 阶段五:目录按实测值订正(已完成)

引入真实数据的第一个价值就是**发现目录里对不上的地方**。上一轮把这些偏差列出来待决策,
本轮按「不留虚假数据」的要求全部订正。

订正后的口径(两条 CSV 一致):

| 字段 | 口径 | 依据 |
| --- | --- | --- |
| `weight_gib` | 该 artifact 实测权重 | 统计仓库里 `.safetensors` 的实际字节数 |
| `total_params_b` | 官方标称参数量 | 官方模型卡 |
| `artifact_params_b` | 实测参数量(新增列) | safetensors 索引汇总;与标称不一致时两列并存 |
| `context_k` | 模型可用上下文 | 仓库 `config.json`;模型卡标称的扩展上限另记 `context_source=card` |
| `license` / `license_id` | 展示名 + 机器可读标识(新增列) | HF `license` 标签与 `license_name`;两者冲突时以官方权重为准 |
| `verified_repo` / `verified_revision` / `verified_endpoint` / `verified_at` | 该行数值的出处(新增列) | 抓取时记录的仓库、revision、端点、日期 |

主要订正(完整明细见每个部署档详情的「登记值 vs 上游当前值」):

| 部署档 | 字段 | 原登记 | 实测 |
| --- | --- | --- | --- |
| GLM-5.2 INT4 | 权重 | 410 GiB | 441.7 GiB |
| Kimi-K2.6 AWQ | 权重 | 500 GiB | 554.3 GiB |
| DeepSeek-V3.1 INT4 | 权重 | 350 GiB | 370.8 GiB |
| Qwen3.5-397B AWQ | 权重 | 200 GiB | 227.6 GiB |
| Qwen3-235B AWQ | 权重 | 135 GiB(原注为「社区估算」) | 115.5 GiB |
| MiniMax-M2.7 AWQ | 权重 | 115 GiB | 121.3 GiB |
| Qwen3.5-122B AWQ | 权重 | 68 GiB | 76.5 GiB |
| Qwen3-Coder-30B AWQ | 权重 | 18 GiB | 15.7 GiB |
| Qwen3-32B AWQ | 权重 | 19 GiB | 18 GiB |
| Qwen3-14B AWQ | 权重 | 9 GiB | 9.3 GiB |
| Qwen3-8B BF16 / AWQ | 权重 | 16 / 5 GiB | 15.3 / 5.7 GiB |
| Qwen3-4B BF16 | 权重 | 8 GiB | 7.5 GiB |
| GLM-5.2 | 上下文 | 128 K | 1024 K(仓库 config) |
| Qwen3 系(8B/14B/32B/4B) | 上下文 | 32 K | 128 K(模型卡:32K 原生 + YaRN) |
| Qwen3.5 全系 / Kimi-K2.6 / Qwen3-235B | 上下文 | 64 / 64 / 128 K | 256 K |
| MiniMax-M2.7 系 | 上下文 | 64 K | 192~200 K |
| DeepSeek 全系 | 上下文 | 128 K | 160 K |
| Yi-1.5 系 | 上下文 | 32 K | 4 K(原值无依据) |
| InternVL3 系 | 上下文 | 128 K | 32 K(原值无依据) |
| 多个 Qwen2.5 档 | 许可 | Apache-2.0 | Qwen License / Qwen Research License(HF 实测) |
| 多个 Kimi/MiniMax 档 | 许可 | 模型仓库许可证为准 | Modified MIT / 厂商自定义(HF 实测) |

**上一轮标记的结构性缺陷已解**:`deepseek-r1-bf16` 档原先指向官方 `deepseek-ai/DeepSeek-R1`,
而官方只发 FP8(641.3 GiB),该档无从核对。现改为指向真实的 BF16 artifact
`unsloth/DeepSeek-R1-BF16`(1275 GiB,与声明一致),同档位对照成立。

**量化档位核对**:从 safetensors 的 dtype 分布反推档位,与 `quantization` 列逐条比对,
19 个部署档 **0 条不符**(AWQ/INT4 仓库的主 dtype 均为 I32 打包权重,FP8 仓库为 F8_E4M3)。

**仍然存在、且如实标注的一项**:`databricks/dbrx-instruct` 官方仓库为 gated(API 401,
config 也取不到),登记值改由社区镜像 `alpindale/dbrx-instruct` 核实(另一镜像
`LnL-AI/dbrx-base-converted-v2` 给出相同的 131.6B / 245.1 GiB,两处互证),许可因无来源而
标注「未能核实」。

时效性发现仍然保留待办:HF 上存在比工作区记录更新的
`deepseek-ai/DeepSeek-V4.1-Flash`(2026-09-10),工作区记录的是 `DeepSeek-V4-Flash-0731`。

订正由 `tools/apply_truth.py` 完成,可复跑:`--check` 只报差异,不带参数则按核实缓存写回,
`--refresh` 重新抓取。核实缓存落在 `data/catalog-verified.json`(95 个仓库,含 revision 与端点),
因此**离线也能复现同一份结果**,不需要每次联网。

### 5.8 阶段六:硬件目录与真实显存核算(已完成)

用户本轮提了三条要求:(1) 硬件选型应该是**给出可选的 GPU**,不是让用户自己输入型号;
(2) 推荐结果要根据**真实硬件配置**给出真正符合要求、且**不浪费显存**的 3-5 个方案;
(3) 去掉对工作区本地方案(kty5l / xt / zc5s)的偏袒,改为按实际匹配结果推荐。

三条分别落在数据层、规则层、界面层:

| 层 | 改动 | 关键点 |
| --- | --- | --- |
| GPU 目录 | 新增 `tools/sync_gpus.py` -> `data/gpu-catalog.json` | 每张卡的显存容量/类型/互联必须**逐字命中厂商产品页正文**,算力必须在 **NVIDIA 官方 CUDA-Enabled GPUs 算力表**对应档位命中该卡名字;任一条不满足即标 `failed` 并写明原因,**绝不填记忆值** |
| KV 结构 | `tools/sync_hf.py` 新增 `attention_shape()` | 从真实 `config.json` 取头数/层数/MLA 维度,并支持 `text_config` / `llm_config` 等嵌套结构 |
| 显存核算 | `model-selector/recommend.py` 新增 `assess()` / `kv_gib()` | 权重取 artifact 实测字节数,KV 按真实 attention 结构算;只有余量系数是工程值且逐条标注 |
| 排序 | `_score()` 重写 | 新增显存利用率项;删除按 `validation_status` 加分的本地方案偏袒 |
| 接口 | `/api/presets` 移除,改为 `/api/gpus` | 推荐接口**必须传 `gpu_id`**,不接受调用方自带 `vram_per_gpu_gib` |
| 前端 | `views/recommend.js` 重写 | GPU 改成下拉,只列核实通过的卡;结果区显示实测权重/KV/单卡需求/占用率/空闲显存 |

**GPU 目录(12 张卡,12 / 12 核实通过)**

| 算力 | 卡 | 单卡显存 |
| --- | --- | --- |
| sm_120 | RTX 5090 | 32 GiB GDDR7 |
| sm_100 | B200 | 180 GiB HBM3e |
| sm_90 | H100 SXM / H100 NVL / H200 SXM | 80 / 94 / 141 GiB HBM3(e) |
| sm_89 | L40S / L4 / RTX 6000 Ada / RTX 4090 | 48 / 24 / 48 / 24 GiB GDDR6(X) |
| sm_86 | A40 | 48 GiB GDDR6 |
| sm_80 | A100 SXM / A100 PCIe | 80 GiB HBM2e |

产品页已下线的旧卡(A800 / H800 / L20 / A10 / A30 / V100)**不收录**——没有可引用的
厂商页就不进目录,而不是凭记忆补一个数。`b200-180` 的显存由 DGX B200 整机 1440 GiB / 8
推得(官方页只给整机值),该口径写在 `vram_basis` 里。

**KV cache 的三种口径**(本轮最关键的修正,不能用一个公式套所有模型)

| 口径 | 元素数 / token / 层 | 适用 | 实测值 |
| --- | --- | --- | --- |
| `mla` | `kv_lora_rank` + `qk_rope_head_dim`,各头共享**不乘 2** | DeepSeek 系、GLM-5.2、Kimi-K2.6 | 512 + 64 = 576 |
| `hybrid-linear` | 只算 `layer_types` 里 `full_attention` 的层,`2 x kv_heads x head_dim` | Qwen3.5 系 | 1024(397B:60 层里 15 层;122B:48 层里 12 层) |
| `gqa` | `2 x kv_heads x head_dim x 层数` | 其余(含 MiniMax-M2.7、Qwen3 系) | 1024 / 2048 |

把混合线性注意力按全层算会把 Qwen3.5 的 KV 高估约 4 倍;把 MLA 当 GQA(乘 2)会把
DeepSeek 系高估一倍。两者都会直接改变「这些卡放得下吗」的结论。

**显存核算公式**(每一步可复算)

```
权重 GiB = artifact 里 .safetensors 的实际字节数(实测)
KV GiB   = 元素数/token/层 x 层数 x 上下文 token x 2 字节 / 1024^3
合计 GiB = (权重 + KV) x 1.10          # 1.10 = 运行时余量(工程预留)
单卡 GiB = 合计 / TP
判定     = 单卡 GiB <= 单卡显存 x 0.92   # 0.92 = 单卡可用比例
占用率   = 合计 / (TP x 单卡显存)
```

三个系数(`2` 字节 / `1.10` / `0.92`)**都是工程假设,不是实测值**,界面上逐条标注
「工程预留,非实测」。

**去掉本地方案偏袒**

`_score()` 原先按 `validation_status` 给 `verified-local` 加分,于是 kty5l / xt / zc5s
用过的方案天然排在前面——这等于把「我们试过」当成了「更适合你的硬件」。现在:

- `validation_status` **完全不参与排序**;
- 唯一保留的是「有没有可执行部署方法」(`has_recipe`,+3 分),该字段由 `apply_truth.py`
  从 `recipes.json` 统一写进 CSV,命令行与网站用同一份判断;
- 新增**显存利用率**项:占用 < 45% 扣分(该换更大的档,或把卡拿去跑更多副本),
  > 90% 扣分(没给长上下文和并发留余量)。阈值与告警共用,避免两处说法不一致。

首批结果里 Qwen3-Coder-30B-AWQ 在 8 x A100 上只占 26% 显存却挤进前三,就是被这一项压下去的;
调整后同一硬件的首选变为 76% 占用的 GLM-5.2 INT4。

**结果数量与去重**:只输出 3-5 条(`plans`),同一模型 + 同一量化档去重,
避免「一个模型的 AWQ / FP8 / BF16 三档霸榜」。

**仍然无法核实、如实标注的项**

- `meta-llama/Meta-Llama-3.1-405B-Instruct` 官方仓库 gated(401),社区镜像同样 401,
  **KV 结构拿不到**。该档 KV 字段留空,页面显示「官方仓库 gated,KV 结构无法核实,
  只按权重下界核算」,**不套公式顶一个数**。19 个部署档里 18 个拿到了真实 KV 结构,
  仅此一档属于这种情况。
- 驱动未填时不再默认满足该档的驱动下限,而是给出「此档要求驱动>=X,当前未填驱动,
  上线前必须先核对」的告警。

**验证**:自检 63 项 -> **75 项**,新增断言覆盖 GPU 目录接口、每张卡核实通过且带来源页与
sha256、推荐条数落在 3-5、结果内模型不重复、每条方案都带完整显存核算、占用率不超 90%、
单卡场景、台账里未核实的改装卡、必须选 GPU 型号、未知 GPU 返回 404、不接受自填显存、
未知部署档返回 404(明细见 5.6)。

**本轮顺带修掉的严重缺陷**:`web/js/views/recommend.js` 在整文件替换时丢掉末尾的 `}`。
症状是**页面永远停在「加载中…」而所有接口都是 200**——浏览器只报
`SyntaxError: Unexpected end of input` 且不带行列号,`node --check` 也发现不了
(它不按 ES module 解析相对导入)。定位办法是在页面里逐个 `import()` 模块。文件已恢复,
并新增静态断言防回归(见 5.6 与 6.8 / 6.9)。

### 5.9 阶段七:双生态支持(华为昇腾)与持续集成(已完成)

**触发**:用户要求「显卡加上华为系的」。管理台原先默认所有 GPU 都是 NVIDIA/CUDA,
这些假设对昇腾全部不成立,照搬会给出看起来合理、实际错误的结论。

**先说结论:没有做 sm 映射。** `sm_xx` 是 NVIDIA 专有标度,给昇腾编一个等级是
伪核实。目录里昇腾条目的 `compute_capability` 是 `null`,并带
`compute_capability_basis` 写明口径;`verification.cc_checked` 只有 NVIDIA 卡为
`true`。

#### 收录结果(逐字核实,15 张卡)

| 卡 | 厂商页 | 逐字命中 | 显存 |
|---|---|---|---|
| Atlas 350 加速卡(Ascend 950PR) | `www.hiascend.com/hardware/accelerator-card` | `112 GB HBM`、`PCIe 5.0 x16`、`灵衢连接器实现多卡互联` | 112 GiB HBM |
| Atlas 300I Duo 推理卡 | `e.huawei.com/.../atlas-300i-duo` | `LPDDR4X 96GB或48GB`、`280 TOPS INT8`、`408GB/s` | 96 / 48 GiB LPDDR4X |

两条 ATP 350 的依据补充:官方页写明 `支持HiF8/mxFP8/mxFP4`,所以 FP8 标为**支持**
(依据是厂商页标称,不是算力推导)。Atlas 300I Duo 官方页没有芯片型号字样,
`architecture` 留空并写 `architecture_basis`;官方页也没有 FP8 字样,记为不支持。
该页把 96GB 与 48GB 写在**同一行**,因此两个容量各列一条,与本仓库既有的
「两种口径并存」原则一致。

#### 为什么不收录 910B / 310P

已尽力核实但拿不到证据:现官网已换代到 950 系列,`/hardware/accelerator-card`、
`/hardware/ai-server`、`/hardware/processor`、`/hardware/cluster` 全部标签页、
`/llms-content/*.md`、`https://e.huawei.com/cn/products/computing/ascend/atlas-800t-a2`
(该页连 `HBM`/`显存`/`910` 都是 0 命中,是 JS 渲染空壳)、support.huawei.com 上
`910B4` **逐字 0 命中**。

唯一提到「64 GiB/卡」的是本工作区自己的 README(`deepseekv4-flash/offline-dsv4-0731/`),
那**不是厂商页证据**,不能进目录。所以这次不收录,只在 about 页写明原因——
宁可少一张卡,也不填一个核不到的数字。

#### 五个必须分流的口径

改任何跟算力 / FP8 / 驱动 / KV 相关的代码前,先看这五条:

1. **算力门槛**(`min_compute_capability` 是 sm 号)只对 CUDA 成立,昇腾跳过。
2. **NVIDIA 驱动下限**只对 CUDA 成立,昇腾跳过;界面把驱动输入框对外生态**停用**。
3. **FP8 能力**读目录里核实过的 `fp8_supported`,不再由 `cc >= 8.9` 推导。
   非 CUDA 生态又拿不到厂商页标称值时返回「无法判定」,不由 0.0 变成「不支持」。
4. **KV cache**:昇腾走 `--quantization ascend` 的专有量化,没有可核实的公开公式,
   因此 `kv_gib = null` + `kv_note` 说明,只按权重下界核算。**不套 CUDA 的 2 字节口径。**
5. **部署方案不跨生态关联**:`models.csv` 没有 `ecosystem` 列,现有 7 条方案都是
   CUDA 栈。昇腾卡只关联同生态方案,并在结果里用 `stack_note` 明说
   「目录登记的都是 CUDA 栈实现」;同名模型的异生态方案单独说明「不能直接搬过来」。

#### 另一个缺陷:现场登记不再逼人编算力

原实现要求现场登记(不选 `gpu_id`)必须填 `compute_capability`。昇腾唯一的真实取值
是「没有」,于是调用方只能编一个数,而那个数还会影响 FP8 判定。现在改为:
不填算力就**必须写明 `ecosystem`**;自称非 CUDA 却给 sm 号会被 400 拒绝;
且 `ecosystem` 未声明时不再静默默认成 CUDA(会造成把昇腾按 CUDA 核)。

#### 顺带修掉的三个工具缺陷

1. `whole_file_replace.py` 首行被改动时,把旧首行当补丁上下文,于是**新首行被丢掉、
   旧首行原地留下**;现在首行不同就发无上下文块的补丁。
2. 同一个工具校验失败要回滚时用了 Python 3.8 不支持的 `write_text(newline=...)`,
   **回滚自己抛 TypeError**,文件留在改了一半的状态——比不回滚更糟。已改。
3. `sync_docs.py` 新增 `--check`(只验证不写文件),供 CI 使用。

这三条都补了断言/检查:`tools/ci.py::check_replace_tool` 用一次真实往返替换覆盖
前两条(首行改动 + 新内容结尾无换行)。

#### 持续集成与定时检查(用户「固化为定时任务」的要求)

- `tools/ci.py` 是**唯一**的门禁实现:离线 12 项 + 联网 4 项,退出码 = 失败项数。
  此前这里一直写「离线 8 项」,与实际不符。检查项数不再靠手写:以 `docs/CI.md` 的检查表为准。
- `scripts/ci/run-ci.ps1` 调用它并把结果留痕到 `output/ci/`。
- `scripts/ci/register-scheduled-task.ps1` 注册 `llm-ci-daily`(每天离线)与
  `llm-ci-weekly`(每周联网)。已验证:`LastTaskResult = 0`。
- `.github/workflows/ci.yml` 云端跑离线门禁。已实测:首次推送 `17331d0` 为 failure
  (门禁依赖本机 `codex.exe`),修复后 `8b03239` 运行 #2 与 `5cd30d6` 运行 #3 均为 success。
- 设计原则:`SKIP` 单独列出,不算通过;第三方源码目录(如 `.vendor-fetch-*`、
  `source-cache`)不进门禁——它们常年红只会让人学会忽略结果。

#### 验证证据

| 项 | 结果 |
|---|---|
| `python tools/ci.py` | 沙箱内:通过 11 · 失败 0 · 跳过 1(读不到 WSL → shell 语法报 SKIP,不算通过);WSL 可达时 12 · 0 · 0 |
| `python tools/ci.py --online` | 通过 16 · 失败 0 · 跳过 0(GPU 15/15、文档 65/65、昇腾矩阵与 31 份教程 sha256 未漂移、三个 `--check` 都没改数据文件)——阶段九当轮;阶段十口径见 5.9.2 |
| `python deploy-portal/tools/smoke_test.py` | **109/109**(阶段九当轮;阶段十增至 112/112,见 5.9.2) |
| `python deploy-portal/tools/sync_gpus.py --check` | 15/15 |
| `python deploy-portal/tools/sync_ascend.py --check` | 官方矩阵与教程 sha256 未漂移 |
| 浏览器六视图 | 0 控制台报错、0 警告;无 `[object Object]`、无 `sm_null` |
| `Get-ScheduledTaskInfo llm-ci-daily` | `LastTaskResult = 0` |

#### 5.9.1 阶段九:昇腾部署方法改从公开权威来源建立(R2)

**用户方向(2026-09-18)**:「R2 不要参考本地的真实资产,是要做一个通用的平台。」
所以昇腾那条线不能拿某台机器的交付记录当通用方法。

之前的状态:昇腾卡能列出「放得下」的候选,但那批候选是按 CUDA 生态的量化档算的,
而且**一条部署方法都没有**(7 条方案的 `sources` 全是 `kty5l/...` 这类工作区路径,
第三方打不开)。这就是「不通用」。

做法:像 `apply_truth.py` 对待 `models.csv` 那样,从**官方**支持矩阵抓取能力事实。

| 项 | 内容 |
| --- | --- |
| 来源 | `docs.vllm.ai/projects/ascend` 的**稳定版 v0.23.0**(页面自述 "You are viewing the stable release (v0.23.0) documentation");固定版本让 sha256 漂移成为有意义的信号 |
| 抓什么 | 支持矩阵(`_sources/.../supported_models.md`,机器可读)+ 矩阵 `Doc` 列引用的 31 份逐模型教程(HTML,渲染后带真实版本号) |
| 留痕 | 每条来源记 URL + 文档版本 + 抓取时间 + sha256 + 字节数;只由 `tools/sync_ascend.py` 写入 |
| 规模 | 10 张表 / 96 行能力(其中官方有 10 行没填 `Supported Hardware`,照实留空)/ 硬件族 7 个 |
| 匹配规则 | 官方族名必须**逐字**出现在厂商核实过的卡名里(`engine.official_family_match`);归一化后不足 4 字符的族名(如 `A2`)不参与匹配,避免误命中 |

实测匹配结果:`ascend-300i-duo-96` / `-48` 命中 `Atlas 300I DUO`(15 个模型行);
`ascend-950pr-atlas350` 卡名是 `Ascend 950PR`,官方文档里**没有**把它与
`Ascend 950 Products` 对应的可引用表述 → 页面如实报「对不上」并给出矩阵链接,
**不把该族的模型说成这张卡支持的型号**。

页面上新增「官方支持矩阵(公开来源)」区块:官方能力表(逐字)+ 官方逐模型教程里
对应硬件族 tab 的部署命令(`<details>` 折叠,标明「教程共 N 个代码块,取部署相关小节 M 个」,
并给原文链接)。抽哪些小节由 `engine.OFFICIAL_DEPLOY_SECTIONS` 决定,命令本身不改写。

反回归:`smoke_test.py` 新增 10 项(109/109),钉住来源必须是 `https://docs.vllm.ai/`、
能力值逐字等于矩阵、命令里出现 `--quantization ascend` 与 `-310p`、结果里不得出现
`sm_` / `min_driver`、以及「对不上硬件族时必须有解释」。
`tools/ci.py` 新增离线检查「昇腾官方矩阵」(来源公开、留痕完整、卡与族匹配重算一致)
与联网检查「在线:昇腾官方文档」(可达 + sha256 未漂移)。规范见
`.codex-specs/ascend-official-recipes/spec.md`。

顺带修掉一个从阶段七就存在、每次联网门禁都会踩的缺陷:`sync_docs.py` 在 `--check`
模式下**先写盘再打印「--check:未写入」**,于是每跑一次 `tools/ci.py --online`,
`doc-sources.json` 就有 154 行 `checked_at` 被刷新、工作区被弄脏,而输出还说没写。
现在写盘移到检查分支之后,并新增联网门禁项「检查模式不改仓库」:三个 `--check`
跑完后数据文件指纹必须不变。反向验证过——把旧写法放回去,该项立刻报
`--check 改动了数据文件:deploy-portal/data/doc-sources.json`。
实测修复后 `--check` 前后文件哈希一致,65/65 仍可达。

> 未做:磁盘上的现场资产(`deepseekv4-flash/offline-dsv4-0731/`)仍只以 `*-local`
> 状态存在,不参与通用方案生成。R17(现有 7 条方案的来源仍是工作区路径)已在
> 阶段十处理,见 5.9.2。

#### 5.9.2 阶段十:方案的公开依据按归属显式挂接(R17)

**用户方向(2026-09-18)**:R17「现有 7 条方案的来源只有本工作区路径」。它与 R2 是同一个
通用性缺口的两半:R2 是「昇腾还没有通用方案」,R17 是「已有方案的依据也不通用」——
平台的部署方法只拿本机证据说话,第三方打不开、也核实不了。

先量现状,结论是验收标准一、二**已经满足一半**,真正缺的是「归属」:

| 实测(改前) | 结果 |
|---|---|
| 6 条有部署档的方案 | 来源台账里本来就有 **7–10 条**按 `profiles` 挂好的公开来源(vLLM 官方并行 / 量化 / 工具调用 / 环境变量文档、`vllm-project/recipes` 官方配方、官方模型卡),只是页面没把它当成「依据」展示 |
| 唯一没有部署档的方案 `deepseek-v4-flash-gguf-llamacpp` | 走 `engine.global_docs()` 兜底 = 17 条「profiles 为空」的全局条目,于是 **sglang / TensorRT-LLM / Triton / Ollama 的引擎总览全被算成一条 llama.cpp 方案的依据**,还夹着两条不属于本方案的模型卡 |
| 19 个本地 `sources` 路径 | 逐条 `os.path.isfile` 验过,**missing=0**——证据都在,只是需要分开标注 |

改的是归属,不是证据:

| 项 | 内容 |
|---|---|
| 只认显式挂接 | 新增 `engine.docs_for_recipe(recipe)`:`profile_id` 命中条目的 `profiles`,或条目的 `recipe_ids` 明文点名本方案,才算这条方案的依据;`binding` 字段写明是哪种挂接。`global_docs()` 这个「谁都能用」的兜底**删除**——它唯一的作用就是制造假归属 |
| 无部署档靠 `recipe_ids` | `data/sources.json` 的 `doc_sources` / `tracked_repos` 支持 `recipe_ids`;`sync_docs.py` 把 `tracked_repos` 的 `recipe_ids` 抄到自动生成的模型卡条目上。GGUF 那条现在拿到 3 条:llama.cpp 官方仓库、**新增的** `llamacpp-server`(`https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md`,实测 200)、以及它真正用的权重仓 `model-card:unsloth/DeepSeek-V4-Flash-0731-GGUF` |
| 前端分开归属 | 详情页分成「可公开核实的通用依据」(带 `归属` 列:`部署档 xxx` / `本方案显式声明`)与「本工作区的现场记录(第三方打不开)」;列表页每条标 `公开依据 N 条` / `暂无,只有现场记录`;一条都挂不上时**如实降级**成「公开依据:暂无」,不拿别的引擎的文档凑数 |

反回归:`smoke_test.py` 新增 3 项 + 强化 1 项(109→112),钉住「每条方案都有可公开核实的
依据」(原来只要求 ≥5)、「方案的公开依据不跨引擎」、「`recipe_ids` 都指向真实方案」、
「没有部署档的方案都被 `recipe_ids` 点名」。**反向验证过两条**:给 `ollama-docs` 挂上 GGUF
方案 → `FAIL 方案的公开依据不跨引擎 {'deepseek-v4-flash-gguf-llamacpp': ['ollama-docs']}`;
把 `recipe_ids` 打错一个字 → `FAIL recipe_ids 都指向真实方案`。
规范见 `.codex-specs/recipe-public-sources/`。

**验证证据(阶段十当轮)**

| 项 | 结果 |
|---|---|
| 方案依据逐条打印 | 6 条 vLLM 方案各 7–10 条同引擎来源;GGUF 方案 3 条 llama.cpp 来源,无跨引擎条目 |
| `python deploy-portal/tools/sync_docs.py` | **66 / 66 可达,0 失败** |
| `python deploy-portal/tools/smoke_test.py` | **112/112** |
| `python tools/ci.py` | 沙箱内:通过 11 · 失败 0 · 跳过 1(读不到 WSL → shell 语法 SKIP,不算通过) |
| `python tools/ci.py --online` | 通过 16 · 失败 0 · 跳过 0(文档 66/66;三个 `--check` 都没改数据文件) |

### 5.10 未完成事项(Backlog)

> 本节原先是一份手写清单。问题是同一批待办同时出现在三处(`ACTIVE_TASK.md`、
> `DEVELOPMENT.md`、`.agents/tasks/*/MEMORY.md` 的 Next actions),三份会各自过期——
> 2026-09-18 整理时确认其中两处已经过期。
>
> 现在待办清单**只有一份**:`docs/ROADMAP.md`。本节不再维护条目,以免又出现两个真源。
> 那份文档保留了每项的依据(实测数字或代码位置)、验收标准和前置条件,并按优先级排序。

### 5.11 已知技术债

| 项 | 说明 | 影响 |
| --- | --- | --- |
| `hf-catalog.json` 已达 19.2 MiB(20,085,495 B)/ 74 万行 | 全量 JSON 单文件,前端一次性加载后分页 | 首屏请求体偏大;若索引继续翻倍需改为分片或预聚合 |
| 索引过滤在前端做全量扫描 | `hf_query()` 在 Python 内对 24,412 条做线性过滤 | 当前耗时无感;超过 10 万条需建反向索引 |
| 无并发写保护 | 同步工具直接覆盖 `data/*.json` | 单用户场景可接受;多人同时同步会互相覆盖 |
| 权威来源需手动重跑校验 | `doc-sources.json` 是快照,URL 失效不会被自动发现 | 自检的"文档全部可达"断言可兜底,但需人工触发 |
| ~~无 CI~~ **已解决 2026-09-17** | `tools/ci.py` 是唯一实现,本机定时任务与云端 workflow 都跑它 | 剩下的债:在线核实(厂商页 / 文档可达性)不在云端跑,仍需按周触发 |
| 订正依赖核实缓存 | `apply_truth.py` 从 `data/catalog-verified.json` 取值,缓存过期需 `--refresh` 重抓 | 数值不会凭空变化,但上游改版后需手动刷新 |
| `quality_score` / `throughput_score` 是人工评分 | 属于排序权重,不是实测 | 与「不展示假数据」不冲突(页面标为评分),但终究应换成实测基准 |
| KV 按 2 字节(fp16/bf16)固定核算 | `--kv-cache-dtype fp8` 可减半,当前未作为输入项 | 长上下文场景会偏保守;偏保守不会导致选错卡,但可能低估可承载的并发 |
| 余量系数与利用率阈值是工程判断 | `1.10` / `0.92` / 45% / 90% 均未在目标卡上实测标定 | 影响排序名次,不影响「放得下 / 放不下」的硬判定 |

---

## 6. 环境约束与踩坑记录

这些是本机/本工作区实测得出,**改代码时不要绕过**:

1. **`apply_patch` 是 `.bat` 包装器**。从 PowerShell 直接调用会破坏 patch 文本中
   "反斜杠紧跟双引号"的序列,导致校验失败或**文件被静默写坏**。
   必须用 `python deploy-portal/tools/apply_patch.py <patch-file>`,
   且 patch 最后一行必须**精确**是 `*** End Patch`(写成 `+*** End Patch` 会失败)。
   一个 patch 文件里只能有一个 `*** Begin Patch` ... `*** End Patch` 块。

2. **PowerShell 控制台中文乱码**。跑 Python 前设 `$env:PYTHONIOENCODING='utf-8'`,
   读文件用 `Get-Content -Encoding UTF8`。

3. **沙箱用哨兵代理阻断网络**。联网命令需提权,并在命令开头清空代理:
   `$env:HTTP_PROXY=''; $env:HTTPS_PROXY=''; $env:ALL_PROXY=''; $env:http_proxy=''; $env:https_proxy=''; $env:all_proxy=''`。

4. **`.agents/` 是只读挂载**,写任务记忆需要提权。

5. **端口双监听陷阱(实测踩到)**。旧会话遗留的服务进程会与新进程**同时**监听
   `127.0.0.1:8787`,请求可能被旧进程接走并按**旧代码**应答,
   表现为"接口 404 / 页面加载失败"这类误导性现象。
   排查步骤:`netstat -ano | Select-String ':8787.*LISTENING'` 看有几个 PID,
   再 `Get-Process -Id <pid>` 比对 `StartTime`,停掉早于代码变更的那个。

6. **HF 镜像的三个坑**(已固化在 `sync_hf.py`):
   - 不带 `User-Agent` 会被 403(默认 Python-urllib UA 被拒)。
   - 分页 `Link` 头会指回 `huggingface.co`(本机直连超时),必须把主机名重写回镜像。
   - 大响应在约 360KB 处被截断,且表现为 JSON 解析失败而非 HTTP 错误;
     重试偶尔有效,预算用尽必须改小 `limit` 重新分页。

7. **仓库文件统一使用 LF 换行**(实测 `deploy-portal/` 下全部为 LF)。
   用 PowerShell 写文件时记得 `-replace "`r`n","`n"`。

8. **整文件替换必须逐字节校验,失败要回滚**(阶段六实测踩到)。临时工具的
   `text.split("\n")[:-1]` 会在新内容结尾没有换行时**静默丢掉最后一行**,
   于是 `recommend.js` 少了一个 `}`。现已固化为 `tools/whole_file_replace.py`:
   结尾有没有换行都不丢内容,写入后与源文件逐字节比对,不一致就把原文件写回去。
   **不要再用一次性脚本做整文件替换。**

9. **`node --check` 通过不等于浏览器能加载**。`node --check` 把文件按 CommonJS/脚本
   解析,不解析相对导入;ES module 缺括号时它可能照样返回 0,而浏览器抛
   `SyntaxError: Unexpected end of input`(无行列号,只在 console 里一行)。
   诊断这类"接口全 200 但页面不渲染"的问题,在页面里逐个 `import()` 模块最快。

---

## 7. 变更记录

| 日期 | 版本 | 变更 |
| --- | --- | --- |
| 2026-09-18 | 1.7 | 阶段十(R17):方案的公开依据改成**只认显式挂接**。新增 `engine.docs_for_recipe()`(`profile_id` 命中条目的 `profiles`,或条目的 `recipe_ids` 明文点名本方案),**删除** `engine.global_docs()` 这个导致假归属的全局兜底——它曾把 sglang / TensorRT-LLM / Triton / Ollama 的引擎总览算成一条 llama.cpp 方案的依据。`data/sources.json` 的 `doc_sources`/`tracked_repos` 新增 `recipe_ids`,`sync_docs.py` 把它抄到自动生成的模型卡条目上;GGUF 方案据此拿到 llama.cpp 官方仓库、新增的 `llamacpp-server` 官方文档与它真正用的权重模型卡(来源 65→66,实测 66/66 可达)。前端详情页与列表页把「可公开核实的通用依据」(带归属列)与「本工作区的现场记录(第三方打不开)」分开,一条都挂不上时如实降级。自检 109→112 项(新增「不跨引擎」「`recipe_ids` 都指向真实方案」「没有部署档的方案都被点名」并强化「每条方案都有依据」),反向验证过两条;另修掉门禁自身的空白失败细节(`tools/ci.py::failure_detail`)。规范 `.codex-specs/recipe-public-sources/` |
| 2026-09-18 | 1.6 | 阶段九(R2):昇腾的部署方法改为**只来自公开权威来源**,不参考本机现场资产(用户明确「要做一个通用的平台」)。新增 `tools/sync_ascend.py`,从 vllm-ascend 官方文档**稳定版 v0.23.0** 抓取支持矩阵(10 张表 / 96 行能力)与矩阵 `Doc` 列引用的 31 份逐模型教程,每条来源留痕 URL + 文档版本 + 抓取时间 + sha256 + 字节数,落成 `data/ascend-support-matrix.json`(只由工具写入)。新增 `engine.official_family_match`(卡名必须逐字含官方硬件族名;归一化后不足 4 字符的族不参与匹配)与 `engine.ascend_official`,推荐结果对昇腾卡返回 `official_matrix`:命中族给官方能力表与官方教程里对应 tab 的部署命令(逐字、折叠展示、带原文链接),未命中族**如实报不匹配并给矩阵链接**(实测 `Atlas 300I DUO` 命中,`Ascend 950PR` 不匹配,官方文档无对应表述)。改掉一处「文档说已忽略、实际没忽略」:`output/ci/*.json` 一直被 git 跟踪而 `docs/CI.md` 写着已 gitignore,现加入 `.gitignore` 并移出索引。门禁新增离线「昇腾官方矩阵」与联网「在线:昇腾官方文档」(sha256 漂移即报)、以及「检查模式不改仓库」(修掉 `sync_docs.py --check` 先写盘再打印「未写入」的缺陷,见 5.9.1),离线 11→12 项、联网 2→4 项;自检 99→109 项;浏览器六视图复核 0 报错,证据 `output/playwright/21-ascend-official-matrix.png`、`22-ascend-official-commands.png`;规范 `.codex-specs/ascend-official-recipes/` |
| 2026-09-18 | 1.5 | 阶段八:仓库发布到 github.com/max-yangkun-min/llm_deploy,并让云端 workflow 首次实测转绿。修掉首次云端 CI 变红的原因——`apply_patch.py` 只认 Windows 的 `codex.exe`,Linux 上「改文件工具」门禁必然红;现改为双后端(优先用真能跑起来的 codex,否则用内置严格补丁引擎,见 `.codex-specs/ci-portability/`),`tools/apply_patch.py` 由字节相同的第二份副本改为转发入口。门禁新增「Shell 脚本行尾」「任务记忆文件」两项,并修正两处「检查自己报假数」:规范计数把 `_TEMPLATE/spec.md` 算成一份、离线项数历来写错。待办清单收敛到 `docs/ROADMAP.md`(单一真源) |
| 2026-09-17 | 1.4 | 阶段七完成:GPU 目录新增**华为昇腾**(Atlas 350 / Atlas 300I Duo 96GB·48GB,逐字命中华为官方产品页),目录 12→15 张卡;昇腾**不做 sm 映射**(`compute_capability=null` + `compute_capability_basis`),FP8 改读厂商页标称值,算力门槛与 NVIDIA 驱动下限加 `cuda` 守卫,KV cache 因专有量化只按权重下界核算;`hardware_from_gpu()` 支持 `compute_capability=None`;方案按生态分组(`recipes_grouped`)并返回 `recipes_other_ecosystem`,不把 CUDA 栈方案挂到昇腾卡上;现场登记改为「不填算力就必须写明 ecosystem」;前端下拉按厂商分组、`smLabel(null)` 返回 `—`、新增共享 `computeLabel`/`stackLabel`、计划卡片不再对昇腾显示 CUDA 栈与 NVIDIA 驱动下限;台账对 KV 未计入的档显示「下界通过」;自检 75→99 项(昇腾反回归 20 项)。同版新增**持续集成**:`tools/ci.py`(离线 8 项 + 联网 2 项)、`scripts/ci/run-ci.ps1`、`scripts/ci/register-scheduled-task.ps1`(已注册 llm-ci-daily/llm-ci-weekly 并验证 `LastTaskResult=0`)、`.github/workflows/ci.yml`、`docs/CI.md`、`docs/PROJECT-MAP.md`、`.codex-specs/` 规范层;修掉 `whole_file_replace.py` 两个缺陷(首行被改动时丢新首行、回滚用 Python 3.8 不支持的 `write_text(newline=)`) |
| 2026-09-17 | 1.3 | 阶段六完成:新增 `tools/sync_gpus.py` 与 `data/gpu-catalog.json`(12 张卡,显存/算力逐字命中厂商页与 NVIDIA 官方算力表);`sync_hf.py` 新增真实 attention 结构抓取(KV 分 MLA / 混合线性 / GQA 三种口径);`recommend.py` 新增 `assess()` / `kv_gib()`,权重与 KV 按实测核算,`/api/presets` 改为 `/api/gpus` 且推荐必须传 `gpu_id`;删除按 `validation_status` 的本地方案偏袒,新增显存利用率评分项;新增 `tools/whole_file_replace.py`;修复 `recommend.js` 缺右括号导致整页停在「加载中」的缺陷;自检 63→75 项 |
| 2026-09-16 | 1.2 | 阶段五完成:`models.csv` / `model-families.csv` 按 artifact 实测值订正(权重、参数量、上下文、许可),新增 `verified_*` / `artifact_params_b` / `license_id` / `context_source` 溯源列;新增 `tools/apply_truth.py` 与 `data/catalog-verified.json`;修复 `deepseek-r1-bf16` 的档位对照缺陷;宽松许可改按机器可读 id 判定;核对面板改为漂移检查;自检 57→63 项 |
| 2026-09-15 | 1.1 | 新增 4.2「最小功能开发」硬规则并补充 5.5 阶段四进度;修复 6 个死控件(筛选字段缺失、无翻页、键名冲突、过滤范围不符、`favicon.ico` 404);自检 45→57 项;5.x 小节编号顺延 |
| 2026-09-15 | 1.0 | 首版。沉淀阶段一至三的技术栈、边界、进度与踩坑;记录 5.7 的目录缺陷与 5.8 的 backlog |

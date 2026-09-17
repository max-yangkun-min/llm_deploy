# 项目地图

给下一个进入这个仓库的人(或下一个会话)用的定位文件:哪里是入口、哪个文件管什么、
哪些是别人的代码。目标是**不用把整个仓库翻一遍**就能开始干活。

- 仓库根:`D:\workspaces\blade_agent\llm`
- 分支:`main`,远端 `https://github.com/max-yangkun-min/llm.git`
- 语言/依赖:Python 3.8+(**只用标准库**)、原生 ES Module(**不用构建工具、不用 npm**)

## 顶层布局

| 目录 | 是什么 | 说明 |
|---|---|---|
| `deploy-portal/` | **部署管理台本体**(Web 界面 + API + 数据) | 唯一还在演进的子系统;最常改的就是这里 |
| `model-selector/` | 选型规则与模型目录(CSV + CLI) | 规则只有一份实现,`deploy-portal/engine.py` 直接 import 它 |
| `tools/` | 仓库级工具 | `ci.py`(门禁)、`add_file.py`、`apply_patch.py` |
| `scripts/ci/` | CI 包装脚本与定时任务注册 | 见 `docs/CI.md` |
| `docs/` | 项目级文档 | `PROJECT-MAP.md`(本文件)、`CI.md` |
| `.codex-specs/` | 规范驱动开发(SDD)工作区 | 每个功能一份 `spec.md`;见其 `README.md` |
| `.agents/` | 跨会话任务记忆 | 入口 `.agents/ACTIVE_TASK.md`;规则见 `AGENTS.md` |
| `output/ci/` | CI 留痕(已 gitignore) | `ci-latest.log` / `ci-latest.json` |
| `output/playwright/` | 浏览器验证截图(已 gitignore) | |
| `kty5l/` | 现场一:**8×A100 80GB · GLM-5.2 INT4** | 文档+离线包骨架;大件(15.2 GiB 镜像 tar)在本地 |
| `xt/` | 现场二:**合计 14×A40 48GB** 三方案 | 文档+离线包骨架 |
| `zc5s/` | 现场三:**8×RTX 4090 48GB · 银河麒麟 V10** | 文档+离线包骨架 |
| `deepseekv4-flash/` | DeepSeek-V4-Flash-0731 ↔ **昇腾 910B4** 包 | ARM64;真机验收未完成 |
| `wurenllm-build/` `wurenllm-split/` | 三模型离线包(合并版 / 拆分版) | |
| `scratch` 区(见下) | 临时与大件 | 不进提交 |

### 不进提交的内容

`.gitignore` 已经挡住:镜像 `*.tar`、权重(`.safetensors`/`.gguf`/…)、`.deb`/`.rpm`/`.whl`、
`__pycache__/`、`*.log`、`output/playwright/`、`.tmp/`。

根目录保持干净的约定:临时脚本放 `.tmp/`,不要在根目录留 `.tmp_*.py`。
CI 会检查这一点(只报 `WARN`,不动用户的文件)。

## 部署管理台(`deploy-portal/`)

本地网页工具:从**已核实的 GPU 目录**选卡,推荐放得下且不浪费显存的模型,
并给出经过核实的部署方法。

```
deploy-portal/
├── server.py            本地 Web 服务(仅标准库)。/api/* + web/ 静态资源
├── engine.py            适配层:把 model-selector 的规则接到界面上;硬件/方案/目录的组装
├── web/
│   ├── index.html       外壳:顶栏路由 + <main id="view">
│   ├── css/app.css
│   └── js/
│       ├── app.js       路由表、fetch 封装、共享渲染工具(state / esc / smLabel / computeLabel / …)
│       └── views/       六个视图,每个导出 render(container)
├── data/                见下表;除 gpu-catalog.json 外都是快照,由 tools/ 生成
├── tools/               核实与生成脚本(联网)+ 冒烟测试
└── DEVELOPMENT.md       设计文档(v1.4):技术栈、边界、阶段进度、已知缺陷、backlog
```

### 路由 → 视图

| 路由 | 视图模块 | 作用 |
|---|---|---|
| `#/recommend` | `views/recommend.js` | **硬件选型**:选卡+卡数 → 3-5 条可行方案 |
| `#/catalog` | `views/catalog.js` | 模型目录(部署档表) |
| `#/models` | `views/models.js` | 真实模型库(HF 快照,可搜索/筛选/翻页) |
| `#/recipes` | `views/recipes.js` | 部署方案(7 条已记录方案) |
| `#/ledger` | `views/ledger.js` | 部署台账(3 个现场环境 + 达标检查) |
| `#/about` | `views/about.js` | 数据来源、口径、维护规则 |

后端接口见 `server.py::dispatch()`:`GET /api/{health,meta,gpus,catalog,recipes,deployments,hf-catalog,hf-detail,docs}`、
`POST /api/{recommend,check}`。

### 数据文件(`deploy-portal/data/`)

| 文件 | 内容 | 谁生成 |
|---|---|---|
| `gpu-catalog.json` | **15 张已核实 GPU**(12 NVIDIA + 3 华为昇腾) | `tools/sync_gpus.py`(联网核实厂商页) |
| `catalog-verified.json` | 95 个模型仓库的核实缓存(权重字节数、revision) | `tools/apply_truth.py`(联网) |
| `recipes.json` | 7 条部署方案 + 国内镜像策略 | 手工维护(有凭据要求) |
| `deployments.json` | 3 个现场环境的台账 | 手工维护 |
| `sources.json` | 抓取输入:2 端点 / 41 组织 / 28 关注仓库 / 37 文档源 | 手工维护 |
| `doc-sources.json` | 65 个权威来源的可达性 + 内容指纹 | `tools/sync_docs.py`(联网) |
| `hf-catalog.json` | HF 元数据快照(**19 MiB**,24412 条) | `tools/sync_hf.py`(联网,走 hf-mirror.com) |

> `hf-catalog.json` 有 19 MiB,是首屏体积的主要来源。要减就先做这里,别动别的。

## 选型规则(`model-selector/`)

```
model-selector/
├── models.csv             精确部署档(20 行 × 42 列):权重、显存门槛、量化、KV 结构口径
├── model-families.csv     模型家族库(84 行):容量估算用
├── recommend.py           规则本体(纯标准库 CLI)
├── collect-hardware.*    现场采集机器规格(需要 nvidia-smi)
└── hardware*.example.json 三种硬件样例
```

**规则只有一份实现。** 命令行与网站都调 `recommend.py`,所以两边排序、硬约束、
风险提示必然一致——不会出现「网站说能跑、脚本说不能跑」。

显存核算(核心):

```
权重 GiB = artifact 里 .safetensors 的实际字节数(实测,不是估算)
KV GiB   = 元素数/token/层 × 层数 × 上下文 token × 2 字节 / 1024³
合计     = (权重 + KV) × 1.10      # 运行时余量,工程预留
单卡     = 合计 ÷ TP
判定     = 单卡 ≤ 单卡显存 × 0.92  # 单卡可用比例
```

KV 结构分三种口径(`mla` / `hybrid-linear` / `gqa`),**不能合并成一个公式**:
混用会把 Qwen3.5 的 KV 高估约 4 倍、把 DeepSeek 系高估一倍。
结构核实不到的档(KV 为 `null`)只按权重下界核算,并在结果里写明。

## 双生态:必须知道的差别

目录里同时有 NVIDIA(CUDA)与华为昇腾(CANN)两种卡。它们的口径**不一样**:

| 维度 | NVIDIA | 华为昇腾 |
|---|---|---|
| `ecosystem` | `cuda` | `cann` |
| `compute_capability` | sm 号(如 8.0 / 9.0) | **`null`**,不做 sm 映射 |
| 算力核实依据 | NVIDIA 官方算力表 | 官方产品页(没有 sm 等级可核) |
| FP8 能力来源 | 由算力推导(已标注) | **厂商页标称值** |
| 驱动下限 | 有 | 不适用(CANN 版本才是) |
| KV cache | 按 attention 结构算 | **`null`**,`--quantization ascend` 是专有量化 |
| 部署方案 | 7 条已记录方案 | 暂无;同生态方案才会被关联 |

改任何跟算力/FP8/驱动/KV 相关的代码前,先看 `deploy-portal/web/js/views/about.js`
里的「华为昇腾:同一套页面上,口径不同」一节,以及 `DEVELOPMENT.md` 的对应章节。
`tools/smoke_test.py` 里有 20 项昇腾反回归断言钉住这些差别。

## 核实工具的用法

```bash
python deploy-portal/tools/sync_gpus.py           # 联网核实 15 张卡 → gpu-catalog.json
python deploy-portal/tools/sync_gpus.py --check    # 只核实不写
python deploy-portal/tools/sync_gpus.py --offline  # 沿用上次结果重建结构
python deploy-portal/tools/apply_truth.py --check  # 核对登记值 vs 实测值
python deploy-portal/tools/sync_docs.py --check    # 只验证文档链接可达性
python deploy-portal/tools/sync_hf.py --repos-only # 刷新 28 个关注仓库
python deploy-portal/tools/smoke_test.py           # 冒烟测试(99 项)
python tools/ci.py                                 # 全部门禁
```

> 联网前清空代理并确认 C: 余量。`sync_gpus.py` 遇到 `www.hiascend.com` 的
> 证书问题时,会**回落**到该站官方的 http 入口,并把回落事实写进快照的
> `transport` 字段(`--offline` 模式下可见)——它不是关掉证书校验。

## 改文件的两个坑(本机特有)

1. **必须用 `tools/apply_patch.py` 或 `deploy-portal/tools/whole_file_replace.py` 改文件。**
   本机 `apply_patch` 是 `.bat` 包装器,PowerShell 直接调用会把 patch 里的
   `\"` 序列破坏掉,静默写坏文件。
2. **整文件替换走 `whole_file_replace.py`。** 它分块应用、结束时逐字节校验,
   对不上就整体回滚。历史上用一次性脚本做过一次替换,因为脚本末尾
   `text.split("\n")[:-1]` 丢了最后一行,导致 `recommend.js` 少一个 `}`,
   整页停在「加载中」而所有接口都是 200。

## 新增文件

```bash
python tools/add_file.py <目标路径> <内容文件>
```

已存在的文件用 `whole_file_replace.py`。两个工具结尾都会逐字节校验,内容对不上
就直接失败并回滚,不留「改了一半」的文件。

## 相关文档

- `AGENTS.md` — 项目宪法:硬边界、下载源策略、任务记忆协议、禁止事项
- `docs/CI.md` — 持续集成与定时任务
- `deploy-portal/DEVELOPMENT.md` — 管理台设计文档(技术栈、边界、阶段进度、已知缺陷)
- `model-selector/README.md` — 选型规则与硬件 JSON 格式
- `.agents/ACTIVE_TASK.md` — 当前任务与跨会话交接入口
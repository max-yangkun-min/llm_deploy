# blade_agent · 本地 GPU 大模型部署

blade_agent 智能体系统的**本地/内网 GPU 集群部署方案与离线安装包**。核心场景是 **agentic coding**(编写 skill / 调用 skill / 代码生成)。一个环境一个文件夹,每个含:硬件配置 + 中文部署文档 + 可直接落地的**离线安装包骨架**。

> ⚠️ 仓库只保留**脚本、文档、目录骨架与占位说明**;镜像 tar、模型权重、系统 deb/rpm 等大件**不入库**(见 [`.gitignore`](.gitignore)),由部署方在有带宽的机器上按各环境的 `下载清单-FILL-ME.md` 下载填充。

---

## 环境总览

| 环境 | 硬件 | 选定模型 | 部署文档 | 离线包骨架 |
| --- | --- | --- | --- | --- |
| **kty5l** | 8×A100 80GB PCIe(sm_80) | **GLM-5.2 744B** INT4(+ vLLM PR#38476 Triton 兜底) | [`kty5l/GLM-5.2-部署步骤-8xA100.md`](kty5l/GLM-5.2-部署步骤-8xA100.md) | [`kty5l/offline-glm52/`](kty5l/offline-glm52/) |
| **xt** | 合计 14×A40 48GB(sm_86)· 驱动≥545 + 容器cu129 Forward Compatibility · 7+7或8+6 · 跨机10GbE | **3主+1备用**:K2.6 PP / 397B PP / M2.7双副本 / 8+6双层模型 | [`xt/大模型部署方案对比-2x7xA40.md`](xt/大模型部署方案对比-2x7xA40.md) | [`xt/offline-xt/`](xt/offline-xt/) |
| **zc5s** | 单机 8×RTX4090 48GB(Ada sm_89 · 有 FP8)· 银河麒麟 V10 | **M2.7**(INT4 双副本 / FP8)· 次选 Qwen3.5-397B | [`zc5s/大模型选型方案-8x4090-48G.md`](zc5s/大模型选型方案-8x4090-48G.md) | [`zc5s/offline-zc5s/`](zc5s/offline-zc5s/) |

---

## 仓库结构

```
llm/
├── deploy-portal/               # 部署管理台(本地网页工具:选卡 → 推荐 → 部署方法)
├── model-selector/              # 选型规则与模型目录(规则只有这一份实现)
├── tools/                       # 仓库级工具:ci.py(门禁)/ add_file.py / apply_patch.py
├── scripts/ci/                  # CI 包装脚本 + 定时任务注册
├── docs/                        # PROJECT-MAP.md(项目地图)· CI.md(持续集成)
├── .codex-specs/                # 功能规范(先写规范再改代码)
├── .agents/                     # 跨会话任务记忆
├── kty5l/                       # 8×A100 · GLM-5.2
│   ├── GLM-5.2-部署步骤-8xA100.md
│   └── offline-glm52/           # 离线包骨架(scripts/ 含 Dockerfile(.cn)/run/recon/prepare/install + patches PR#38476 已预置)
├── xt/                          # 14×A40 · 7+7三主方案 / 8+6备用
│   ├── 大模型部署方案对比-2x7xA40.md
│   └── offline-xt/
├── zc5s/                        # 单机 8×4090 麒麟 · M2.7/397B
│   ├── 大模型选型方案-8x4090-48G.md
│   └── offline-zc5s/            # 含裸机 pip 备案(麒麟容器装不上时)
└── .gitignore
```

每个 `offline-*/` 骨架结构一致:
```
offline-*/
├── images/     ⬇️ 镜像 tar(build+save)
├── models/     ⬇️ 权重(按方案下)
├── system/     ⬇️ 驱动 / 容器 toolkit / (裸机 wheels)
├── scripts/    ✅ Dockerfile(.cn) run.sh recon.sh install/prepare-offline.sh (lb/)
├── *部署/选型文档.md
└── 下载清单-FILL-ME.md   ← 每件大件的命令、来源、大小、放哪
```

---

## 快速开始(离线部署通用流程)

1. **进 `offline-<env>/`,读 `下载清单-FILL-ME.md`**,在有带宽的机器上把大件填进骨架:
   - 镜像:`scripts/` 下 `docker build` + `docker save`(国内用 `Dockerfile.cn`)
   - 权重:`huggingface-cli download`(国内加 `HF_ENDPOINT=https://hf-mirror.com`)
   - 系统依赖:按离线机发行版备 deb/rpm
   - 或一键:`./scripts/prepare-offline.sh base` + 按方案 `./scripts/prepare-offline.sh <model>`
2. **生成校验和** → 整个 `offline-<env>/` 拷到现场机器。
3. **进场核对**:`bash scripts/recon.sh`(重点:GPU 拓扑、驱动、容器栈能否用、配电)。
4. **安装**:`bash scripts/install-offline.sh`(容器,兼容exFAT介质无执行位)或 `install-baremetal.sh`(zc5s 麒麟裸机备案)。
5. **启动**:`./scripts/run.sh <方案>`(各环境命令见对应文档 / `run.sh` 头部)。

---

## 各环境要点

- **kty5l · GLM-5.2**:A100(sm_80)跑不了原生 GLM-5.2 的 DSA 稀疏注意力,靠 **vLLM PR#38476** 补 `TRITON_MLA_SPARSE` 兜底(patch 已核实预置)。只 INT4(~410GB),启动必验兜底两行日志。**只上 GLM-5.2,不备替代模型/备用权重**。含主/备双机冷切、容器化抹平 CUDA 差异。
- **xt · 3主+1备用**:统一使用 `cu129-compat545` 验收镜像(宿主驱动≥545,镜像内torch CUDA=12.9、`cuda-compat-12-9`和Ray 2.56.1)。R545不在官方cu129镜像预置驱动分支白名单内,属于必须通过真实A40 compat-libcuda/Triton JIT测试的条件兼容。7+7 下跨机 TP 不可行(10GbE),K2.6/397B 走 Ray 跨机 PP,M2.7 走双副本。若整机支持移卡为 **8+6**,则8卡机单机 TP=4×PP=2 跑397B、6卡机 TP=4 跑M2.7。离线包固定备齐 K2.6/397B/M2.7 三个模型,两种卡布局复用同一包;每个模型目录均含独立的 `README-部署.md`。
- **zc5s · 单机 4090**:最简(无跨机)。**有 FP8**(Ada 红利)→ M2.7 可跑 FP8 质量版;**无 NVLink** → 优先小 TP 多副本。**银河麒麟 V10** 容器栈可能装不上 → 备了裸机 pip 路径。

## 硬件红线(跨环境共性)

- **无 Hopper 稀疏注意力内核**:A100/A40/4090 均**跑不了** GLM-5.2(DSA)/ DeepSeek-V4(CSA+HCA)等的原生稀疏内核(A100 靠 PR 兜底除外);能跑的是 **MLA / Gated DeltaNet / Lightning / 标准注意力**。
- **量化**:Ampere(A100/A40)无 FP8 → 用 INT4、KV 不开 fp8;Ada(4090)有 FP8 可用;均无 FP4(NVFP4 需 Blackwell)。
- **带宽受限的卡优先低激活 MoE**;MoE 一律 `--enable-expert-parallel`;简单调用 `enable_thinking:False`。

---

## 部署管理台(选型用)

`deploy-portal/` 是一个本地网页工具:从**已核实的 GPU 目录**(15 张卡)选卡,
推荐放得下且不浪费显存的模型,并给出经核实的部署方法。

```bash
python deploy-portal/server.py            # 打开 http://127.0.0.1:8787
```

硬件不用手填型号,只能从目录里选,单卡显存也由服务端按目录填入——否则「实测匹配」
就变成自己填个数绕过判定。目录里的每个数字都要在厂商产品页正文里逐字命中;
NVIDIA 卡的算力另外要对 NVIDIA 官方算力表核,华为昇腾则**不做 sm 映射**(见下)。

## 双生态:华为昇腾与 NVIDIA 口径不同

目录里同时有 NVIDIA(`ecosystem: cuda`)与华为昇腾(`ecosystem: cann`)。三张昇腾卡是
逐字命中华为官方产品页收录的:

| 卡 | 显存 | FP8 |
|---|---|---|
| Atlas 350 加速卡(Ascend 950PR) | 112 GiB HBM | 支持(官方页写明 HiF8/mxFP8/mxFP4) |
| Atlas 300I Duo 推理卡 | 96 GiB / 48 GiB LPDDR4X(两种出货配置各列一条) | 官方页未标注 → 不支持 |

昇腾与 CUDA 卡的关键差别(**不要照搬 CUDA 的口径**):

- **不做 sm 映射。** `sm_xx` 是 NVIDIA 专有标度,昇腾的算力等级留空并写明口径。
- **FP8 看厂商页标称值**,不由算力推导。
- **NVIDIA 驱动下限不适用**,昇腾要核的是 CANN 版本。
- **KV cache 只按权重下界核算**:`--quantization ascend` 的 KV 量化是专有实现,
  没有可核实的公开公式,所以不套 CUDA 的 2 字节口径,页面会明说「只按权重下界核算」。
- **部署方法不跨生态关联**:现有方案都是 CUDA 栈,昇腾卡不会挂上 CUDA 方案。

未收录 `910B` / `310P`:现官网已换代到 950 系列,这两个型号在官方页正文里逐字 0 命中,
本工作区自述的「64 GiB/卡」不是厂商页证据,因此宁可少一张卡,也不填核不到的数字。

---

## 持续集成与定时检查

改完代码跑一条命令就知道仓库是否健康:

```bash
python tools/ci.py                # 离线门禁,秒级(改完就跑)
python tools/ci.py --online       # 额外联网核实厂商页与权威文档链接,分钟级
```

也可以走带日志留痕的包装脚本,或让定时任务自己跑:

```powershell
pwsh -File scripts\ci\run-ci.ps1                       # 结果留痕到 output/ci/
pwsh -File scripts\ci\register-scheduled-task.ps1      # 注册每日离线 + 每周联网任务
```

门禁覆盖:磁盘余量(C: 低于 20 GiB 直接失败)、Python 语法、冒烟测试(99 项)、
实测值核对、shell 语法、GPU 目录自洽、整文件替换工具往返、根目录残留物、工作流骨架文件,
以及联网的厂商页与文档可达性。退出码 = 失败项数。

`SKIP` 单独列出,**不算通过**——一个没跑过的检查不能看起来像跑过了。

细节见 [`docs/CI.md`](docs/CI.md);模块与入口见 [`docs/PROJECT-MAP.md`](docs/PROJECT-MAP.md)。

---

## 说明

- 国内构建:各环境含 `Dockerfile.cn`(镜像走 `REGISTRY` 镜像前缀、pip 清华;kty5l 另含 git 代理 + PR patch 直接套 + precompiled wheel 预置)。
- 部分权重仓库名 / vLLM 版本对 2026 新模型(K2.6、M2.7 FP8、Qwen3.5-397B)为占位,**下载前现场确认可用的量化仓库与支持的 vLLM 版本**。
- 项目规则与硬边界见 [`AGENTS.md`](AGENTS.md);功能级规范见 [`.codex-specs/`](.codex-specs/README.md)。

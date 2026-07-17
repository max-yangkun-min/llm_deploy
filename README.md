# blade_agent · 本地 GPU 大模型部署

blade_agent 智能体系统的**本地/内网 GPU 集群部署方案与离线安装包**。核心场景是 **agentic coding**(编写 skill / 调用 skill / 代码生成)。一个环境一个文件夹,每个含:硬件配置 + 中文部署文档 + 可直接落地的**离线安装包骨架**。

> ⚠️ 仓库只保留**脚本、文档、目录骨架与占位说明**;镜像 tar、模型权重、系统 deb/rpm 等大件**不入库**(见 [`.gitignore`](.gitignore)),由部署方在有带宽的机器上按各环境的 `下载清单-FILL-ME.md` 下载填充。

---

## 环境总览

| 环境 | 硬件 | 选定模型 | 部署文档 | 离线包骨架 |
| --- | --- | --- | --- | --- |
| **kty5l** | 8×A100 80GB PCIe(sm_80) | **GLM-5.2 744B** INT4(+ vLLM PR#38476 Triton 兜底) | [`kty5l/GLM-5.2-部署步骤-8xA100.md`](kty5l/GLM-5.2-部署步骤-8xA100.md) | [`kty5l/offline-glm52/`](kty5l/offline-glm52/) |
| **xt** | 2 台 × 7×A40 48GB(sm_86)· 跨机 10GbE | **三方案**:Kimi K2.6 · PP / Qwen3.5-397B · PP / M2.7 双副本 | [`xt/大模型部署方案对比-2x7xA40.md`](xt/大模型部署方案对比-2x7xA40.md) | [`xt/offline-xt/`](xt/offline-xt/) |
| **zc5s** | 单机 8×RTX4090 48GB(Ada sm_89 · 有 FP8)· 银河麒麟 V10 | **M2.7**(INT4 双副本 / FP8)· 次选 Qwen3.5-397B | [`zc5s/大模型选型方案-8x4090-48G.md`](zc5s/大模型选型方案-8x4090-48G.md) | [`zc5s/offline-zc5s/`](zc5s/offline-zc5s/) |

---

## 仓库结构

```
llm/
├── kty5l/                       # 8×A100 · GLM-5.2
│   ├── GLM-5.2-部署步骤-8xA100.md
│   ├── docker/                  # Dockerfile(.cn)/run/recon/prepare/install + patches/(PR#38476 已预置)
│   └── offline-glm52/           # 离线包骨架(images/models/system/scripts + 下载清单)
├── xt/                          # 2×7×A40 · 三方案
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
4. **安装**:`./scripts/install-offline.sh`(容器)或 `install-baremetal.sh`(zc5s 麒麟裸机备案)。
5. **启动**:`./scripts/run.sh <方案>`(各环境命令见对应文档 / `run.sh` 头部)。

---

## 各环境要点

- **kty5l · GLM-5.2**:A100(sm_80)跑不了原生 GLM-5.2 的 DSA 稀疏注意力,靠 **vLLM PR#38476** 补 `TRITON_MLA_SPARSE` 兜底(patch 已核实预置)。只 INT4(~410GB),启动必验兜底两行日志。**只上 GLM-5.2,不备替代模型/备用权重**。含主/备双机冷切、容器化抹平 CUDA 差异。
- **xt · 三方案**:跨机 TP 不可行(10GbE),但 **PP 只传层间激活可扛**。K2.6(能力天花板,12 卡)/ 397B(★推荐,8 卡)走 Ray 跨机 PP;M2.7 双副本 + nginx/LiteLLM 负载均衡(唯一有冗余)。一个镜像通吃三方案。
- **zc5s · 单机 4090**:最简(无跨机)。**有 FP8**(Ada 红利)→ M2.7 可跑 FP8 质量版;**无 NVLink** → 优先小 TP 多副本。**银河麒麟 V10** 容器栈可能装不上 → 备了裸机 pip 路径。

## 硬件红线(跨环境共性)

- **无 Hopper 稀疏注意力内核**:A100/A40/4090 均**跑不了** GLM-5.2(DSA)/ DeepSeek-V4(CSA+HCA)等的原生稀疏内核(A100 靠 PR 兜底除外);能跑的是 **MLA / Gated DeltaNet / Lightning / 标准注意力**。
- **量化**:Ampere(A100/A40)无 FP8 → 用 INT4、KV 不开 fp8;Ada(4090)有 FP8 可用;均无 FP4(NVFP4 需 Blackwell)。
- **带宽受限的卡优先低激活 MoE**;MoE 一律 `--enable-expert-parallel`;简单调用 `enable_thinking:False`。

---

## 说明

- 国内构建:各环境含 `Dockerfile.cn`(镜像走 `REGISTRY` 镜像前缀、pip 清华;kty5l 另含 git 代理 + PR patch 直接套 + precompiled wheel 预置)。
- 部分权重仓库名 / vLLM 版本对 2026 新模型(K2.6、M2.7 FP8、Qwen3.5-397B)为占位,**下载前现场确认可用的量化仓库与支持的 vLLM 版本**。

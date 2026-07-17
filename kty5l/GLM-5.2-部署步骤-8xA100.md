# GLM-5.2 部署步骤 · 8×A100 80GB PCIe · 离线

> 单一执行文档:准备 → 打包 → 进场 → 分阶段启动 → 备案 → 接入。只讲怎么做。
> 配套脚本在离线包 `offline-glm52/scripts/`(包内即 `scripts/`)。**明确只上 GLM-5.2,不准备任何替代模型。**

---

## 0. 关键约束速查(照做,不解释)

| 项 | 定值 |
| --- | --- |
| 权重 | **只能 INT4**,唯一一个:`cyankiwi/GLM-5.2-AWQ-INT4`(~410GB)。**不带备用量化** |
| vLLM | 锁定 tag(`VLLM_REF`,如 `v0.24.0`)+ **PR #38476**(A100 稀疏注意力 Triton 兜底) |
| 后端环境变量 | `VLLM_ATTENTION_BACKEND=TRITON_MLA_SPARSE` / `VLLM_USE_DEEP_GEMM=0` / `VLLM_USE_FLASHINFER_SAMPLER=0`(已固化进镜像) |
| KV | `--kv-cache-dtype auto`,**A100 绝不开 fp8 KV**(会崩) |
| 并行 | **TP=8** |
| 部署 | 离线:联网机 build → `docker save` → 离线机 `docker load` |
| 冷启动 | ~7 分钟。健康检查超时 **>15 分钟**,**禁用自动重启** |
| 环境 | 驱动 ≥550;磁盘 ≥500GB SSD;内存 ≥512GB;x86_64 |

**启动后日志必须出现这两行,否则停:**
```
[cuda.py] Using TRITON_MLA_SPARSE attention backend
[sparse_attn_indexer.py] DeepGEMM not supported on this platform; using Triton fallback
```

---

## 1. 离线包内容与硬盘结构

```
/offline-glm52/
├── images/
│   └── glm52-vllm-<tag>-pr38476.tar          # docker save 产物 (~25GB)
├── models/
│   ├── GLM-5.2-AWQ-INT4/                      # 唯一权重 ~410GB(cyankiwi)
│   └── Qwen3-8B/                              # 阶段1 诊断小模型 ~16GB(只验 TP,不服务)
├── system/                                    # 按 recon 结果补,缺才备
│   ├── docker/  nvidia-container-toolkit/     # 容器栈
│   └── driver/                                # 驱动.run + 内核头(若驱动不达标)
├── scripts/  (Dockerfile run.sh recon.sh install-offline.sh prepare-offline.sh patches/)
├── MANIFEST.sha256                            # 全量校验和
└── *.md                                       # 本文档
```

硬盘 **1TB** 足够(镜像 ~25GB + 唯一权重 ~410GB + 诊断小模型 ~16GB + 系统包)。

---

## 2. 联网机:分两段打包

**前提**:x86_64 + Docker + `huggingface_hub[hf_transfer]`,硬盘已挂载。国内下不动 HF 时先 `export HF_ENDPOINT=https://hf-mirror.com`。

```bash
# ① 确认 tag 存在
git ls-remote --tags https://github.com/vllm-project/vllm | grep 0.24

# ② 生成 PR #38476 冲突 patch(只做一次,按 scripts/patches/README.md)
#    产出 scripts/patches/38476-with-triton-fallback.patch

cd scripts
export OUT=/mnt/drive
export VLLM_REF=v0.24.0
export SYS_DISTRO=ubuntu              # 按"离线机"发行版填(recon 的 A1);非 deb 系走备案 C
```

**第一段 · 先备非权重部分(大权重先不下)**:镜像 + 系统依赖 + 诊断小模型 + 脚本。
```bash
./prepare-offline.sh base
```
> 产出:`images/*.tar`(~25GB)、`models/Qwen3-8B`(~16GB)、`system/`(toolkit/docker)、`scripts/` + 文档 + 校验和。
> 系统依赖 deb **必须匹配离线机发行版**;驱动 `.run` 若 recon 显示驱动<550,手动放 `system/driver/`。
> 国产 OS 容器装不上时,`./prepare-offline.sh wheels` 另备裸机 pip 轮子(备案 C)。

**第二段 · 大权重就绪后再下**(~410GB,数小时):
```bash
./prepare-offline.sh weights                          # GLM-5.2 唯一权重 + 补校验和
```

打包完 `umount` 硬盘,插到离线机。

---

## 3. 进场核对(不碰模型)

```bash
bash scripts/recon.sh                 # 生成 recon-report.txt,逐项看
```

必看三项:

| 项 | 达标 | 不达标 → 备案 |
| --- | --- | --- |
| **拓扑** `topo -m` | `NV*` / `PIX` / `PXB` | `SYS`(跨 socket)→ 备案 A |
| **驱动** | ≥550,8×A100 80GB | <550/无 → 备案 B |
| **容器栈** | docker + nvidia runtime | 缺 → 装 `system/`;国产 OS 装不上 → 备案 C |

拓扑判读:`NV*`=理想 / `PIX`/`PXB`=可上打折 / `PHB`/`NODE`=更慢 / `SYS`=会卡死。

---

## 4. 离线机:安装

```bash
cd /offline-glm52
sha256sum -c MANIFEST.sha256          # 必须全 OK(410GB 拷贝易坏字节)
./scripts/install-offline.sh          # 自检 + docker load
# 若缺容器栈:先装 system/,再:
#   sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker
```

改 `scripts/run.sh` 顶部路径:`MODEL_DIR` / `SMOKE_DIR` / `HF_CACHE` 指到 `models/` 下。

---

## 5. 分阶段启动(验证不过不进下一步)

```bash
cd /offline-glm52/scripts

# 阶段1 · 诊断 TP=8/NCCL(2 分钟,验完即弃)
./run.sh smoke
./run.sh test                         # 能对话=通;卡死=拓扑/NCCL(备案 A)
./run.sh stop

# 阶段3 · 已验证基准(32K / util0.90,一个字别改)
./run.sh stage3
./run.sh logs                         # 验兜底两行 + 记 GPU KV cache size
./run.sh test
#   并发 ≈ KV cache size ÷ max-model-len,以此为准

# 阶段4 · 目标档(64K / 16 路 + prefix cache + 工具调用)
./run.sh stop
./run.sh target
./run.sh logs                         # 确认 KV 够:cache size ÷ 65536 ≥ 16
```

**阶段4 顶格**(64K×32 或 128K×16):单一 AWQ 权重下 KV 余量有限,靠 `--gpu-memory-utilization` 微调往上顶;顶不到就按 KV cache size 实测值接受 64K×16(不再有备用量化可换)。

**压测**(真实上下文长度,别照搬短输入预期):
```bash
docker exec glm52 vllm bench serve --backend openai-chat --model glm-5.2 \
  --base-url http://localhost:8000 --dataset-name random \
  --random-input-len 65536 --random-output-len 512 --max-concurrency 16 --num-prompts 64
```
性能参考:单路约 56 tok/s;16 路后接近饱和,**16–24 路是甜点**。

---

## 6. 备案(现场不满足怎么办 · 全部收敛到 GLM-5.2 自身)

| 备案 | 触发 | 做法 |
| --- | --- | --- |
| **A 拓扑 SYS** | `topo -m` 出 `SYS` | A1 物理挪卡到同 socket(治本);A2 `NCCL_P2P_DISABLE=1 ./run.sh stage3`(能跑,慢);同 socket 仅 4 卡则装不下 410GB → 只能挪卡或换冷备机 |
| **B 驱动不达标** | recon B1 | 装 `system/driver/*.run` + 内核头(需 root);装不动 → 换冷备机 |
| **C 容器装不上** | 国产 OS/无 root | 裸机 pip:联网机先 `pip download` 备 `system/wheels/`,离线 `pip install --no-index --find-links` + 手动打 PR patch |
| **D 镜像/PR 异常** | patch 冲突/后端加载错 | 换预先 build 的第二候选 tag 镜像 |
| **E GLM 跑不起来** | stage3 反复不过 | E1 换第二候选 vLLM tag 镜像 → E2 `NCCL_DEBUG=INFO` 排查通信 → E3 降参(len32K/util0.88/seqs8)→ 都无效=硬件问题,换冷备机/升级硬件 |
| **F 磁盘/内存不足** | recon D1/D2 | 磁盘:直接挂硬盘当权重盘;内存:加 swap 撑过加载 |
| **G 顶格 OOM** | 起不来/崩 | 降 util/len(无备用量化可换,只能降参) |
| **HF 不可达** | 联网机下不了 | `HF_ENDPOINT=https://hf-mirror.com` |

> **无替代模型、无备用权重**:安全边际全在"尽早暴露"——recon + smoke + stage3 三关早发现早处置。E1–E3 都无效即判为硬件/环境,换冷备那台或升级硬件。

---

## 7. 智能体接入

标准 OpenAI 兼容接口(`/v1/chat/completions` 支持 `tools`/`tool_choice`):

```python
from openai import OpenAI
client = OpenAI(base_url="http://<ip>:8000/v1", api_key="EMPTY")
resp = client.chat.completions.create(
    model="glm-5.2",
    messages=[{"role":"user","content":"..."}],
    tools=[...], tool_choice="auto",
)
```

要点:
1. **固定 system prompt + 工具定义顺序**——prefix caching 逐字节匹配,顺序抖动会全失效(TTFT 从 1 秒变 20 秒)。
2. **`<think>`/`reasoning_content` 不回填进下一轮 messages**。
3. **简单工具调用调低/关闭思考强度**,只在复杂规划时开——这对 Agent 延迟影响最大。

---

## 8. 主/备双机切换

- 两台候选,**选一台为主、另一台冷备随时可切**(非双活)。用同一个 Docker 镜像,抹平两台 CUDA(12.8/12.2)差异,宿主只需驱动 ≥550。
- **选主**:拓扑优先(`PIX/PXB` >> `SYS`);拓扑相当再选 CUDA 12.8 那台。
- **权重两台都备好**(或共享存储),否则"随时切"是空话。
- 切换非秒切:冷启动 ~7 分钟 + 首请求 JIT + prefix cache 冷,切过去 **7–10 分钟**才对外服务,期间有中断。

---

## 9. 现场排错速查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 日志没兜底两行 | PR 没生效/patch 解错 | 回打包阶段重做 cherry-pick |
| 报 `dsv3_fused_a_gemm`/sm90 | sm80 不兼容 | PR 没打全,检查 patch |
| 报 DeepGEMM RuntimeError | indexer 兜底没生效 | 检查 `VLLM_USE_DEEP_GEMM=0` + patch |
| 加载到一半被杀 | 健康检查超时 | 放宽 >15 分钟,禁自动重启 |
| `NotImplementedError`+FP8 KV | 误开 fp8 KV | 保持 `--kv-cache-dtype auto` |
| 启动 OOM | util/len 太大 | 回退 0.90 / 32768 |
| 多卡卡死无日志 | NCCL/拓扑 | 阶段1 应拦住;`NCCL_DEBUG=INFO`,试 `NCCL_P2P_DISABLE=1` |
| 首请求特别慢 | Triton JIT | 正常,后续会好 |
| Agent 每轮 40 秒 | `<think>` 思考模式 | 调低思考强度 |

---

## 参考

- [zai-org/GLM-5.2 · HF](https://huggingface.co/zai-org/GLM-5.2) · [vLLM Recipes · GLM-5.2](https://recipes.vllm.ai/zai-org/GLM-5.2)
- [cyankiwi/GLM-5.2-AWQ-INT4(唯一权重)](https://huggingface.co/cyankiwi/GLM-5.2-AWQ-INT4)
- [vLLM PR #38476](https://github.com/vllm-project/vllm/pull/38476) · [Issue #35021(sm80 不兼容)](https://github.com/vllm-project/vllm/issues/35021)
- [8×A100 实测 · TRITON_MLA_SPARSE + PR #38476](https://gist.github.com/timinar/c8d2eca4e2ea7d11db57a1e6e62d06a2)

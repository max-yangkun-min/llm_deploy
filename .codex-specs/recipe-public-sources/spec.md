# 方案的公开依据按归属显式挂接(通用平台方向)

- 功能 ID:`recipe-public-sources`
- 状态:`已完成`
- 创建:`2026-09-18`
- 最后更新:`2026-09-18`
- 对应任务记忆:`.agents/tasks/deploy-portal/MEMORY.md`

## 意图

给**任何外部读者**回答「你凭什么这么说」。平台的 7 条部署方案此前只有一类来源:
本工作区里的落地文档与脚本(如 `kty5l/GLM-5.2-部署步骤-8xA100.md`)。第三方打不开
这些路径,也就无从核实方案里的启动参数、并行布局和显存结论。

本功能让每条方案都给出**可公开核实**的依据(引擎官方文档 / 官方配方 / 官方模型卡),
并把两类来源在页面上**分开归属**:哪一条是通用依据,哪一条只是本机的现场记录。

## 现状

2026-09-18 实测(改之前):

| 事实 | 证据 |
|---|---|
| 7 条方案的 `sources` 全是工作区相对路径 | `data/recipes.json`;19 个路径逐条 `os.path.isfile` 验过,missing=0 |
| 6 条有部署档的方案在来源台账里**已有** 7–10 条按 `profiles` 挂好的公开来源 | `data/doc-sources.json`(vLLM 并行/量化/工具调用/环境变量文档、`vllm-project/recipes` 官方配方、官方模型卡) |
| 唯一没有部署档的 GGUF 方案走 `engine.global_docs()` 兜底 | `server.py::recipes_payload()` 的 `if profile_id ... else engine.global_docs()`;兜底返回 17 条「profiles 为空」的条目 |
| 于是 sglang / TensorRT-LLM / Triton / Ollama 的引擎总览被算成一条 llama.cpp 方案的依据 | 同上;兜底里还夹着两条不属于本方案的模型卡 |

即:问题不只是「本地路径」,更是**归属**:没挂接的文档被当成依据,这比留空更坏。

## 验收标准

- [x] `GET /api/recipes` 的**每条**方案都有非空 `authoritative_docs`(原来只要求 ≥5 条)。
- [x] 方案的公开依据只来自**显式挂接**:`profile_id` 命中条目的 `profiles`,或条目的
      `recipe_ids` 明文点名该方案。跨引擎的条目(ollama / sglang / lmdeploy /
      tensorrt-llm / triton,以及 vLLM 方案引 `llamacpp-*`、llama.cpp 方案引 `vllm*`)
      一律不得出现。
- [x] `data/sources.json` 里出现的每个 `recipe_id` 都指向真实方案;没有部署档的方案
      必须被至少一个 `recipe_ids` 点名(打错一个字两条断言都红)。
- [x] 引用的条目都在 `data/doc-sources.json` 里且 `status == 200`,因此
      `python tools/ci.py --online` 的「在线:权威文档可达性」覆盖到每一条。
- [x] 本地 `sources` **保留**(不删证据),页面把两类来源分成两块并写清归属与
      「能证明什么 / 不能证明什么」。
- [x] 一条都挂不上的方案,页面如实降级为「公开依据:暂无」,不拿别的引擎的文档凑数。

## 边界:明确不做什么

- **不删本地路径。** 它们是有价值的落地记录(哪台机器、什么参数、踩过什么坑)。
  改的是标注与归属。
- **不做「profiles 为空即全局生效」的兜底。** 那正是假归属的来源。
- **不新增一套重复的 URL 数据。** 权威来源的唯一真源仍是
  `data/doc-sources.json`(由 `tools/sync_docs.py` 真实抓取);方案只引用条目标识。
- **不用「有没有本地记录」参与排序或加分。** 与 R2 同一条理由:试过 ≠ 更适合你。
- **不为凑数把不相关的官方文档挂上去。** 挂不上就留空。

## 依赖与前提

- `data/doc-sources.json` 必须已由 `sync_docs.py` 生成(联网,分钟级)。
- 新增条目要走真实 HTTP 校验:只有返回 200 的链接才进已验证清单。
- `tracked_repos[].recipe_ids` 由 `sync_docs.py` 抄到自动生成的模型卡条目上。

## 风险

- **最大的风险是「归属错」而不是「来源少」**:一条 llama.cpp 方案引着 Ollama 文档,
  读者会以为两者有关。断言「方案的公开依据不跨引擎」先报。
- **`recipe_ids` 打错字会导致该方案静默变成「暂无公开依据」**:断言「recipe_ids 都指向
  真实方案」与「没有部署档的方案都被 recipe_ids 点名」先报。
- **`sync_docs.py` 重跑会刷新 `checked_at` 与内容指纹**(这是实测留痕,不是缺陷);
  `--check` 模式不写盘,CI 用 `--check`。

## 变更记录

| 日期 | 变更 |
|---|---|
| 2026-09-18 | 创建并实现:删除 `engine.global_docs()` 兜底,新增 `engine.docs_for_recipe()`;`sources.json` 支持 `recipe_ids`;GGUF 方案挂上 llama.cpp 官方仓库、server 文档与权重模型卡;前端分开两类来源;自检 109 → 112 项 |

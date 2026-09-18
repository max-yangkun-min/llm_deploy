# GPU 目录支持华为昇腾(非 CUDA 生态)

- 功能 ID:`ascend-gpu-catalog`
- 状态:`已完成`
- 创建:`2026-09-17`
- 最后更新:`2026-09-17`
- 对应任务记忆:`.agents/tasks/deploy-portal/MEMORY.md`

## 意图

用户要求「显卡加上华为系的」。管理台原先默认所有 GPU 都是 NVIDIA/CUDA:
硬件选型下拉里只有 NVIDIA 卡,算力按 `sm_xx` 显示,FP8 能力由算力推导,
KV cache 一律按 CUDA 栈的 2 字节口径算。这些假设对昇腾**全部不成立**,
照搬会给出看起来合理、实际错误的结论。

目标:让昇腾卡能被正确选到、正确核算、并如实说明它与 CUDA 卡的差别。

## 现状

- `gpu-catalog.json` 只有 12 张 NVIDIA 卡。
- `hardware_from_gpu()` 里 `fp8_supported = gpu["compute_capability"] >= 8.9` ——
  对 `compute_capability` 为 `None` 的昇腾卡会抛 `TypeError`。
- `assess()` 用 `cc >= 8.9` 判 FP8、用 `cc < min_compute_capability` 卡算力门槛,
  两者都是 CUDA 专属口径。
- KV cache 一律套 `kv_elems × layers × tokens × 2 字节`。
- 前端 `smLabel(null)` 会渲染出 `sm_null`。

## 验收标准

全部已实现并有断言(见 `deploy-portal/tools/smoke_test.py`,23 条昇腾/双生态断言)。

- [x] `gpu-catalog.json` 含 `vendor=huawei` / `ecosystem=cann` 的条目。
- [x] 昇腾条目 `compute_capability` 为 `null`,且带 `compute_capability_basis` 说明口径。
- [x] 昇腾的 `fp8_supported` 来自厂商页标称值,`fp8_basis` 里不出现「算力推导」。
- [x] `verification.cc_checked` 只有 NVIDIA 卡为 `true`。
- [x] 推荐接口对昇腾卡不套 `sm_` 门槛、不套 NVIDIA 驱动下限
      (断言:结果里所有 failures/warnings 文本都不含 `sm_` 与 `驱动需`)。
- [x] 昇腾卡的每个 plan 的 `memory.kv_gib` 为 `null` 且 `kv_note` 非空。
- [x] 昇腾卡不关联任何 CUDA 栈的部署方案(`plan.recipes` 为空)。
- [x] 结果里说明部署档目录只有 CUDA 栈实现(`stack_note` 含「CUDA 栈」)。
- [x] CUDA 卡的 `stack_note` 为空(不出现跨生态提示)。
- [x] 调用方自填的 `vram_per_gpu_gib` / `ecosystem` / `fp8_supported`
      在选中 `gpu_id` 时被忽略。
- [x] 现场登记路径:不填 `compute_capability` 就必须写明 `ecosystem`;
      自称非 CUDA 却给 sm 号会被 400 拒绝。
- [x] Atlas 350 显存 112 GiB、FP8 支持;Atlas 300I Duo 96/48 各列一条。

## 边界:明确不做什么

- **不做 sm 映射。** `sm_xx` 是 NVIDIA 专有标度,给昇腾编一个等级是伪核实。
  `compute_capability` 留 `null`,并在 `compute_capability_basis` 里写明原因。
- **不用 NVIDIA 算力表核昇腾。** 该表里没有昇腾;拿它去核是自欺欺人。
  `verify()` 按厂商分支:NVIDIA 走算力表,昇腾只核厂商产品页。
- **不合并两种容量。** Atlas 300I Duo 官方页把 96GB / 48GB 写在同一行,
  两个容量各列一条,与仓库既有的「两种口径并存」原则一致。
- **不套 CUDA 的 KV 公式。** `--quantization ascend` 的 KV 精度是专有量化,
  没有可核实的公开公式,所以 `kv_gib = null`,只按权重下界核算。
- **不收录核不到的型号。** `910B` / `310P` 在现官网各页逐字 0 命中
  (官网已换代到 950 系列),工作区自述的「64 GiB/卡」不是厂商页证据,
  因此这次不收录,只在 `about` 页写明原因。宁可少一张卡,不填核不到的数字。
- **不伪造 CUDA 镜像。** 昇腾不硬套 `vllm/vllm-openai:*` 镜像;
  部署方法不跨生态关联,同名模型的异生态方案单独说明「不能直接搬过来」。

## 依赖与前提

- 厂商页可达性(联网)。`www.hiascend.com` 在本机 SSL 证书链验不过时,
  `fetch()` 会回落到该站官方 http 入口,并把回落事实写进快照的 `transport`
  字段——**不是关掉证书校验**,非证书类错误(404/超时)不回落。
- `e.huawei.com` 用系统信任库,默认 https 正常通过。
- 已逐字核实的三个条目:Atlas 350 加速卡(Ascend 950PR,112 GB HBM)、
  Atlas 300I Duo(96GB / 48GB,LPDDR4X)。

## 风险

- **最坏情况**:把昇腾当 CUDA 处理,给出「不支持 FP8」或「算力不达标」的假结论。
  Atlas 350 官方页写明支持 HiF8/mxFP8,误判会直接误导选型。
  由 `fp8_capability()` 的显式读取 + 「昇腾不会被 NVIDIA 门槛卡住」断言发现。
- **次坏情况**:拿 CUDA 栈的部署方案冒充昇腾的部署方法。
  由「昇腾卡不关联 CUDA 栈方案」断言 + `stack_note` 发现。
- **静默退化**:KV 显示成 0 或某个算出来的数,让人以为已计入。
  由 `kv_gib is None and kv_note` 断言发现。

## 变更记录

| 日期 | 变更 |
|---|---|
| 2026-09-17 | 创建;目录条目、规则分支、前端口径、文档与 23 条昇腾/双生态断言一并完成 |
| 2026-09-17 | 复审补漏:plan 卡片不再对昇腾显示 CUDA 栈/驱动下限;现场登记不再强制填算力 |

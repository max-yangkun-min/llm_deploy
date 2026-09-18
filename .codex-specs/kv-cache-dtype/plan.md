# 实现计划:KV 精度作为输入项

- 功能 ID:`kv-cache-dtype`
- 状态:`实现中`
- 对应规范:`.codex-specs/kv-cache-dtype/spec.md`

## 改动清单(按执行顺序)

| # | 文件 | 改什么 | 验证 |
|---|---|---|---|
| 1 | `model-selector/recommend.py` | 新增 `KV_CACHE_DTYPES`(取值 → 每元素字节数 + 标签)、`KV_CACHE_DEFAULT`、`KV_CACHE_FP8_MIN_COMPUTE`;新增 `kv_cache_dtype_name(hw)` / `kv_cache_dtype_check(hw)`,后者返回 `(字节数, 是否生效, 说明)` | `python -c` 直接调,枚举五个分支 |
| 2 | `model-selector/recommend.py` | `assess()`:按输入取 `dtype_bytes`,传给 `kv_gib()` 与 `max_context_for()`;`fp8*` 且算力已核实 < 8.9 → 失败;算力未登记 → 警告;非 CUDA → 不生效 + 说明 | 同上 |
| 3 | `model-selector/recommend.py` | `max_context_for()` 的说明里写明 KV 精度口径(非默认精度时) | 反算值随精度变化 |
| 4 | `model-selector/recommend.py` | `assess()` 的 `memory` 增加 `kv_cache_dtype` / `kv_cache_dtype_bytes` / `kv_cache_dtype_effective` / `kv_cache_dtype_note` | 接口返回 |
| 5 | `deploy-portal/server.py` | `build_hardware()` 校验 `kv_cache_dtype` 取值,未知一律 400;字段本身允许作为输入(不是厂商页字段) | `curl` 打非法值 |
| 6 | `deploy-portal/web/js/views/recommend.js` | 表单加 KV 精度下拉;`readForm()` 带上;计划卡显示 KV 精度与是否生效;Markdown 导出一列;非 CUDA 卡给出「不生效」提示 | 浏览器六个视图 |
| 7 | `deploy-portal/web/js/views/ledger.js` | 达标检查表加 KV 精度一列(与 R3 的「最长上下文」同处) | 浏览器 |
| 8 | `deploy-portal/tools/smoke_test.py` | 按验收标准逐条加断言(默认 auto 2 字节 / fp8 减半 / A100 判失败 / 昇腾说明不生效 / 未知值 400 / 反算同口径) | `python tools/ci.py` |
| 9 | 文档 | `docs/ROADMAP.md` 的 R4 标完成 + 实测;`deploy-portal/DEVELOPMENT.md` 阶段十二 + 变更记录 + 技术债那行;`AGENTS.md` / `docs/CI.md` / `docs/PROJECT-MAP.md` / `deploy-portal/README.md` 的项数;`.agents/` 两份记忆 | 人工 + CI |

## 关键决策

1. **默认 `auto`,不改默认行为。** 现有全部推荐结果的数字必须一字不变——这是回归的基线。
2. **算力不足判失败,不是警告。** 现场记录是「会报 `NotImplementedError`」,也就是
   **起不来**;给个警告然后照样按 1 字节算出「放得下」,等于给一个跑不起来的方案。
3. **昇腾不判失败。** 那里 KV 精度由 `--quantization ascend` 决定,`--kv-cache-dtype`
   根本不是那个栈的参数;判失败会把「你选错生态了」混进「你的参数开不了」。
4. **算力未登记只给警告。** 目录里每张卡都有核实过的算力(15 张全通过),但现场登记
   路径允许不填;那时不能假装知道,也不能替它判死刑。
5. **`fp8_e5m2` 仍然提供。** 官方文档列了它,虽然 FA 后端列表里没有;说明里点出这一
   差异,让人自己去确认后端,而不是替他删掉一个官方支持的取值。

## 验证记录

| 验证项 | 结果 |
|---|---|
| 默认口径对拍 | 8 用例(含昇腾、`llama31-405b-bf16` 的 gated config)对上 `git show HEAD` 版 `recommend.py`,`memory` / `failures` / `warnings` **0 差异** |
| 减半 | RTX 4090(sm_89)+ `qwen3-coder-30b-awq`:KV 3.0 → 1.5 GiB,最长上下文 46K → 93K;A100 的数字不变 |
| 低算力拦截 | 8×A100 要 `fp8_e4m3` → `plans_total=0`,19 个 rejected,失败信息含 `sm_89` 与 `NotImplementedError` 且给出处置 |
| 昇腾 | 8×Atlas 300I Duo 要 `fp8_e4m3` → `effective=false` + 说明,`plans_total>0`,无方案因此被判失败 |
| 非法取值 | `kv_cache_dtype=fp4` → 400,错误信息里点名该字段 |
| 台账路径 | `/api/check` 也返回同一份口径;`fp8_e5m2` 的说明点出 FlashAttention 后端列表里没有它 |
| 反算同口径 | fp8 下的上限回填零失败、+1K 判 KV 超 |
| 自检 | 120 → **135** 项,全过 |
| 反向验证 | fp8 字节数改回 2 → 「真的减半」「上限变长」「低算力判失败」3 条 FAIL;不生效分支仍返回 1 字节 → 「不生效时数字必须是 2 字节口径」FAIL |
| 浏览器 | 六视图 0 控制台报错;4090 显示「按 fp8_e4m3 生效 · 1 字节/元素」,A100 显示「未按 fp8_e4m3 生效(仍按 2 字节/元素)」+ 原因,昇腾在下拉旁提示不生效 |
| `tools/ci.py` | 离线 通过 11 · 失败 0 · 跳过 1(沙箱读不到 WSL,shell 语法 SKIP) |

截图:`output/playwright/27-kv-dtype-fp8-blocked-a100.png`、
`28-kv-dtype-fp8-effective-4090.png`。
## 回滚

改动集中在三处(`recommend.py` 的 KV 字节数来源、`server.py` 的取值校验、前端控件)。
出问题时把 `assess()` 的 `dtype_bytes` 还原成 `KV_DTYPE_BYTES` 常量即可回到 R3 行为;
数据文件(`models.csv` / `gpu-catalog.json`)不在本次改动范围内,无需回滚数据。

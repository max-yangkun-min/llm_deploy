# `--kv-cache-dtype fp8` 作为输入项

- 功能 ID:`kv-cache-dtype`
- 状态:`已完成`
- 创建:`2026-09-18`
- 最后更新:`2026-09-18`
- 对应任务记忆:`.agents/tasks/deploy-portal/MEMORY.md`

## 意图

KV cache 一直按 **2 字节/元素**(fp16/bf16)固定核算。开了 `--kv-cache-dtype fp8` 之后
KV 只占 1 字节,同一个档能放下的上下文更长、并发更高。对长上下文场景来说,这不是个
小数点后的差别——是「这条方案在不在你的候选集里」的差别。

所以要让选型的人能把 KV 精度**当成一个输入**来试,并且试出来的数字必须与真实
vLLM 行为一致:能开的说能开(并给出减半后的核算),**不能开的必须说不能开**
——不是静默按 2 字节算完事。

## 现状(2026-09-18 实测)

| 事实 | 证据 |
|---|---|
| KV 精度写死在代码里 | `model-selector/recommend.py` 的 `KV_DTYPE_BYTES = 2.0`,`kv_gib()` / `max_context_for()` 都拿它当默认参数,`assess()` 从不改它 |
| 请求里没有这个字段 | `deploy-portal/server.py` 的 `NUMERIC_HARDWARE_KEYS` / `VERIFIED_ONLY_KEYS` 都没有 `kv_cache_dtype`;前端 `recommend.js` 的 `DEFAULTS` / `readForm()` 也没有 |
| 减半确实成立 | `kv_gib()` 是 `elems × layers × tokens × 字节数 / 1024³`,字节数从 2 变 1 就是减半;官方文档把 `fp8_e4m3` / `fp8_e5m2` 列为 FP8 KV cache 的取值 |
| **但不是所有卡都能开** | 本工作区现场记录:A100 开 fp8 KV 报 `NotImplementedError`,处置是「保持 `--kv-cache-dtype auto`」(`kty5l/GLM-5.2-部署步骤-8xA100.md` 第 9 节);A40 同理(`xt/大模型部署方案对比-2x7xA40.md` 的公共硬规则②) |
| 官方口径门槛 | vLLM 源码 `vllm/platforms/cuda.py`:`supports_fp8()` = `has_device_capability(89)` |
| 后端支持的取值不全一样 | `vllm/v1/attention/backends/flash_attn.py` 的 `supported_kv_cache_dtypes` = `auto / float16 / bfloat16 / fp8 / fp8_e4m3`,**没有 `fp8_e5m2`** |
| 昇腾根本不是这个参数 | 昇腾走 `--quantization ascend` 的专有 KV 量化,`--kv-cache-dtype` 不是 CANN 栈的参数(现有 `kv_gib = null` 的理由同此) |

## 验收标准

- [x] 请求可带 `kv_cache_dtype`(默认 `auto`);未知取值一律 400,不静默回落。
- [x] 取值 `auto` / `float16` / `bfloat16` 按 2 字节核算;`fp8` / `fp8_e4m3` / `fp8_e5m2`
      按 1 字节核算,并在响应里带上**依据**(官方文档链接 + 算力门槛)。
- [x] `fp8*` 在 CUDA 卡上只有在算力已核实且 ≥ 8.9 时才生效;算力已核实但 < 8.9 时
      **判为失败**(vLLM 会直接报错起不来),失败信息里给出实测依据与处置(保持 `auto`)。
- [x] `fp8*` 在非 CUDA 生态(昇腾)下**不生效但不判失败**,并且响应里必须写明
      「该参数在该生态不适用」,不许静默忽略。
- [x] `fp8*` 在算力等级未登记时按 2 字节保守核算,并给出警告要求上线前核对。
- [x] R3 的反算上限与正算**同口径**:请求 `fp8_e4m3` 时 `max_context_k` 相应变长
      (不受标称上下文压住时约翻倍),且反算回填必须仍然零失败。
- [x] 前端:推荐页有 KV 精度选择控件,改动后结果必须真的变(KV 显存、最长上下文、
      占用率);选中非 CUDA 卡时给出「该参数在此生态不生效」的提示,不让它变成死控件。
- [x] `smoke_test.py` 补断言覆盖上面各条。(120 → 135 项)

> 第五条(算力未登记)的实现口径:这条**只给警告并保守按 2 字节**,既不假装知道,
> 也不替它判死刑。第一条的默认值是 `auto` 而不是「新特性的推荐值」,因为改默认会把
> 现有全部推荐结果静默改掉——因此还加了一条对拍断言:默认 `auto` 时 8 个用例的
> `memory` / `failures` / `warnings` 必须与改动前逐字一致。
## 边界:明确不做什么

- **不把 fp8 KV 当默认。** 默认仍是 `auto`(= 模型默认精度,本目录的档都是 bf16 →
  2 字节)。改默认会把现有全部推荐结果静默改掉。
- **不为昇腾编一个 KV 字节数。** 昇腾的 KV 精度是专有量化,没有可核实的公开公式;
  这条与 R3 的处理一致——留空 + 说明,不减半也不猜。
- **不声称 `fp8` 与 `fp8_e4m3` 等价。** vLLM 的 `CacheDType` 把两者分别列出,我没找到
  可核实的等价映射,所以按两个独立取值处理,字节数相同而已。
- **不把「开了 fp8 就能塞下」当成实测结论。** 减半是按字节数算的算术结果;
  真实能不能起来还要看后端与驱动,所以算力不足时判失败、算力不明时给警告。
- **不引入新的工程系数。** 复用 `KV_DTYPE_BYTES` 的语义(每元素字节数),只让它的
  取值由输入决定。

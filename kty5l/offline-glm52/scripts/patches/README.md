# PR #38476 patch(已预置)

**`38476-with-triton-fallback.patch` 已经放好了**,构建时 Dockerfile 自动用,无需再手动生成。

## 这是什么(已核实 2026-07-17)

- 来源:vLLM **PR #38476** 的完整累积 diff(`https://github.com/vllm-project/vllm/pull/38476.diff`)
- 标题:**[Feature] TRITON_MLA_SPARSE backend for SM8x/11x/12x DSA Sparse MLA Support**(SM8x = A100)
- **单 commit**(head=`3740c02bb1223d37823593664ae3eafa397b9937`),base=`main`,状态 **open 未合并**
- 文件:66221 字节,`sha256 = 9b6126e460a818806643b712f6f2f00764aabf3f0b82dbd75a184f10aa976a2b`
- 改动:11 文件 —— 新增 `triton_mla_sparse.py` + Triton 内核 `mqa_logits_triton.py`/`triton_mla_sparse_kernel.py`,并注册 `TRITON_MLA_SPARSE` 后端(`cuda.py`/`registry.py`)。

**关键**:PR **本身**就把 `sparse_attn_indexer.py` 里那句硬抛的
`RuntimeError("... requires DeepGEMM ...")` 改成了
`logger.warning_once("DeepGEMM not supported on this platform; using Triton fallback ...")`,
并加了 `is_deep_gemm_supported()` 判定 + Triton else 分支。**所以部署方案要验证的那行日志,就是这个 PR 自带的,不需要再手动改逻辑。**

## 构建时怎么用(Dockerfile 已实现)

PR 是单 commit,Dockerfile 流程:
1. `git cherry-pick pr-38476` —— 单 commit,能拿全。若在锁定 tag(`VLLM_REF`)上**无冲突**,直接成功,用不到本 patch。
2. 若 cherry-pick **冲突**(tag 与 PR 的 base=main 上下文漂移)→ 自动 `git apply --3way 38476-with-triton-fallback.patch`。`--3way` 靠 diff 里的 blob index 做三方合并,能自动吸收多数上下文漂移(前提:已 `git fetch` 到 PR 对象,Dockerfile 已做)。

## 万一 `git apply --3way` 也失败(tag 漂移过大)

只在此时才需要人工——按 PR 的明确意图解:
- `has_deep_gemm` → `is_deep_gemm_supported`(import 与调用处)
- `__init__` 里硬抛的 `RuntimeError` → `logger.warning_once("DeepGEMM not supported ...; using Triton fallback ...")`
- prefill/decode 两处 `fp8_fp4_mqa_logits`/`fp8_fp4_paged_mqa_logits` 各加 `if use_deep_gemm: ... else: fp8_mqa_logits_triton/fp8_paged_mqa_logits_triton(...)`
参考:https://github.com/vllm-project/vllm/pull/38476/files

或换个更接近 PR base 的 `VLLM_REF`(如 v0.25.x)重试,冲突通常更少。

## 验证 patch 生效

镜像跑起来后,启动日志必须出现:
```
[cuda.py] Using TRITON_MLA_SPARSE attention backend
[sparse_attn_indexer.py] DeepGEMM not supported on this platform; using Triton fallback
```

> ⚠️ 本 patch 只保证"能套用+能编译进镜像",**是否推理正确必须在真机(8×A100)build+run 后靠上面两行日志 + 实际对话验证**——这台准备机无 GPU/Docker,验不了。

# 方案的公开依据按归属显式挂接 · 实现计划

- 功能 ID:`recipe-public-sources`
- 对应规范:`spec.md`
- 状态:`已完成`

## 改动清单

从数据/规则层往界面层改,每一步都能单独验证。

| 顺序 | 文件 | 改什么 | 怎么验证 |
|---|---|---|---|
| 1 | `deploy-portal/data/sources.json` | `doc_sources`/`tracked_repos` 支持 `recipe_ids`;新增 `llamacpp-server`(`https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md`);给 `llamacpp-repo` 与 GGUF 权重仓挂 `recipe_ids` | `python -c "import json;json.load(open(...))"` + 人工核对 ids |
| 2 | `deploy-portal/tools/sync_docs.py` | `model_card_entries(tracked)` 把 `tracked_repos[].recipe_ids` 抄到模型卡条目;`main()` 传入 `tracked_repos` | `sync_docs.py` 重跑,66/66 可达 |
| 3 | `deploy-portal/engine.py` | 新增 `docs_for_recipe(recipe)`(只认显式挂接,附 `binding`);**删除** `global_docs()`;修 `docs_by_profile()` 的错注释 | `python -c "import engine; ..."` 逐条打印 7 条方案的依据 |
| 4 | `deploy-portal/server.py` | `recipes_payload()` 改用 `docs_for_recipe(item)`,不再兜底全局文档 | `python deploy-portal/tools/smoke_test.py` |
| 5 | `deploy-portal/tools/smoke_test.py` | 新增 3 条断言 + 强化 1 条(见规范「验收标准」) | 反向验证两条(见下) |
| 6 | `deploy-portal/web/js/app.js` `web/js/views/recipes.js` | `docSourceBlock` 支持说明文案与「归属」列;详情页/列表页分开两类来源并写清归属 | 浏览器复跑六视图,0 报错 |
| 7 | 文档 | `docs/ROADMAP.md`(R17 完成 + 证据)、`DEVELOPMENT.md`(阶段十 + 计数 + 删掉 `global_docs` 提法)、`README.md`(来源台账计数 + `recipe_ids` 用法)、`PROJECT-MAP.md`/`CI.md`/`AGENTS.md` 计数 | 人工核对 |

## 验证

- 每步之后:`python tools/ci.py`(离线,秒级)
- 收尾:`python tools/ci.py --online`(联网,分钟级)
- 反向验证(必须真跑,不能只是「应该会红」):
  1. 给 `doc-sources.json` 的 `ollama-docs` 挂上 `recipe_ids: [deepseek-v4-flash-gguf-llamacpp]`
     → 期望 `FAIL 方案的公开依据不跨引擎`;还原后逐字节哈希比对。
  2. 把 `sources.json` 的 `recipe_ids` 改成 `...-llamacp`
     → 期望 `FAIL recipe_ids 都指向真实方案`。
- 界面:六个视图(`#/recommend` `#/catalog` `#/models` `#/recipes` `#/ledger` `#/about`)
  0 控制台报错、无 `[object Object]`、无死控件。

## 回滚

- 代码层:改动都在 5 个文件内,`git revert` 单个提交即可。
- 数据层:`doc-sources.json` 是**可重生成**的快照(重跑 `sync_docs.py`);`sources.json` 是
  手维护配置,回滚靠版本控制,没有不可逆的数据变更。
- 没有删除任何本地来源路径,所以不存在「证据丢失」这种回滚风险。

## 遗留

- 未收录引擎全局总览(如 `vllm-serve-cli`、`vllm-optimization`)— 它们与方案相关,
  但要挂上去必须先有一条「这条方案确实以它为据」的判断;当前宁可留空,不靠猜测挂接。
- 昇腾方案没有 `profile_id` 也没有模型卡 — 它走的是 R2 的官方矩阵通道
  (`engine.ascend_official`),本次不改。

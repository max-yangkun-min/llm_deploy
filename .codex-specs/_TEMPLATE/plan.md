# <功能名> · 实现计划

- 功能 ID:`<feature-id>`
- 对应规范:`spec.md`
- 状态:`草稿 | 执行中 | 已完成`

## 改动清单

按文件列出要改什么。**顺序很重要**:从规则层往界面层改,这样每一步都能单独验证。

| 顺序 | 文件 | 改什么 | 怎么验证 |
|---|---|---|---|
| 1 | `model-selector/recommend.py` | 例:判定加生态分支 | `python model-selector/recommend.py <hw.json>` |
| 2 | `deploy-portal/engine.py` | 例:目录值透传,不再推导 | `python tools/ci.py` |
| 3 | `deploy-portal/tools/smoke_test.py` | 例:补 N 条断言 | `python deploy-portal/tools/smoke_test.py` |
| 4 | 前端视图 | 例:按厂商分组、口径文案 | 浏览器复跑,0 报错 |
| 5 | 文档 | 例:更新口径说明 | 人工核对 |

## 验证

- 每步之后:`python tools/ci.py`(离线,秒级)
- 收尾:`python tools/ci.py --online`(联网,分钟级)
- 涉及界面时:浏览器复跑六个视图,确认 0 控制台报错、无 `[object Object]`

## 回滚

- 怎么退回去?
- 有没有不可逆的步骤(改数据文件、重新生成快照)?

## 遗留

这次不做但记下来的事。格式:`<事项> — <为什么现在不做>`。
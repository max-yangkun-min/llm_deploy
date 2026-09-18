# 昇腾部署方案改从公开权威来源建立(通用平台方向)

- 功能 ID:`ascend-official-recipes`
- 提出:用户 2026-09-18「R2 不要参考本地的真实资产,是要做一个通用的平台」
- 对应待办:`docs/ROADMAP.md` 的 R2 / R17

## 要解决什么

昇腾卡在推荐页能算出「这些模型放得下」,但那批候选是按 CUDA 生态的量化档
(AWQ/INT4)算出来的,而且**一条部署方法都没有**——平台对昇腾只给了算术结论,
没给可执行的、第三方能自己核实的方法。这正是「不通用」的地方:现有 7 条方案
的依据全是本工作区路径(如 `kty5l/...`),外部读者打不开。

本功能把昇腾的能力事实与部署方法改成**只来自公开权威来源**:
vLLM Ascend 官方文档的「支持矩阵」与「逐模型教程」。抓取过程留痕
(URL + 文档版本 + 抓取时间 + sha256),数据只由工具写入,不手写。

## 不做什么

- **不参考本工作区现场资产。** `deepseekv4-flash/offline-dsv4-0731/` 那类交付记录
  只能以 `*-local` 状态存在,不得据它生成通用昇腾方案。
- **不为让某张卡「有方案」而强行匹配。** 官方矩阵的硬件族名与目录里的卡名对不上时,
  就如实报「对不上」并给矩阵链接,不猜。
- **不把 CUDA 口径搬到昇腾。** 不生成 `min_driver` / `sm_*` 字段。
- **不手写能力值。** W8A8 / TP / EP / max-model-len 等一律逐字来自官方矩阵。

## 数据来源(2026-09-18 实测,固定版本)

| 角色 | URL | 实测 |
|---|---|---|
| 支持矩阵(markdown 源,机器可读) | `https://docs.vllm.ai/projects/ascend/en/v0.23.0/_sources/user_guide/support_matrix/supported_models.md` | 200,22,020 B |
| 支持矩阵(人可读页) | `.../en/v0.23.0/user_guide/support_matrix/supported_models.html` | 200,81,996 B |
| 逐模型教程(HTML,渲染后带真实版本号) | `.../en/v0.23.0/tutorials/models/<Model>.html` | 200 |
| 项目仓库 | `https://github.com/vllm-project/vllm-ascend` | 200 |

v0.23.0 是官方**稳定版**(页面自述 "You are viewing the stable release (v0.23.0)
documentation"),因此固定引用它而不是 `latest`(开发预览)。
`gitee.com/ascend/vllm-ascend`、`.../en/stable/`、`.../en/v0.25.0/` 实测 404,不引用。

## 卡 ↔ 硬件族的匹配规则(不许放宽)

官方矩阵的硬件族是 `Supported Hardware` 列的值:`Ascend 950 Products`、
`Ascend 950DT`、`A2/A3`、`A2`、`Atlas 300I DUO`。
目录里的卡只允许在**厂商核实过的卡名里逐字出现该族名**时才匹配
(归一化后子串相等;族名归一化后短于 4 个字符的不参与匹配,避免 `A2` 这种
两字符串在卡名里误命中)。匹配不上就是匹配不上,写明原因并给出矩阵链接。

2026-09-18 实测结果:`ascend-300i-duo-96` / `ascend-300i-duo-48` 命中
`Atlas 300I DUO`;`ascend-950pr-atlas350` 的卡名是 `Ascend 950PR`,
官方文档里没有把它与 `Ascend 950 Products` 对应的可引用表述 → **不匹配**。

## 验收标准

1. `deploy-portal/tools/sync_ascend.py --check` 能联网核实矩阵页 sha256 是否漂移;
   `sync_ascend.py` 能把矩阵与教程命令写进 `data/ascend-support-matrix.json`,
   且文件里每个来源都带 URL + 文档版本 + 抓取时间 + sha256 + 字节数。
2. `/api/recommend` 选昇腾卡时返回 `official_matrix`:命中族时给出该族的官方模型行
   (逐字)与官方教程里对应 tab 的真实命令;未命中时给出原因与矩阵链接,不留空。
3. 昇腾卡仍然**不**关联任何 CUDA 栈方案(`recipes` 为空、`recipes_other_ecosystem`
   如实体现在别处),也不出现 `min_driver` / `sm_*`。
4. `smoke_test.py` 增加断言钉住:来源必须是 `https://` 公开地址、命令必须来自
   官方教程正文、未命中时必须有解释;现有 20 项昇腾反回归断言不得放宽。
5. `tools/ci.py` 增加离线检查(数据文件自洽 + 与矩阵的一致性)与联网检查
   (官方页面可达 + sha256 未漂移)。联网项在离线跑时报 SKIP,不冒充通过。

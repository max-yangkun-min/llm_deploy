# 昇腾支持 · 实现计划

- 功能 ID:`ascend-gpu-catalog`
- 对应规范:`spec.md`
- 状态:`已完成`

## 改动清单

| 顺序 | 文件 | 改了什么 | 验证 |
|---|---|---|---|
| 1 | `deploy-portal/tools/sync_gpus.py` | 12 张 NVIDIA 卡补 `vendor`/`ecosystem`;追加 3 条昇腾;`verify()` 按厂商分支;`fetch()` 加证书回落;`verification` 加 `cc_checked` 与 `transport` | `--check` → 15/15 通过 |
| 2 | `deploy-portal/data/gpu-catalog.json` | 重新生成(联网核实) | 15 张全部 `status=ok` |
| 3 | `model-selector/recommend.py` | `is_cuda()` / `fp8_capability()` / `compute_label()` / `driver_label()`;算力门槛与驱动下限加 `cuda` 守卫;昇腾 KV 置 `null` 并写明原因;FP8 未通过时按依据说明 | `--check` 与 CLI 直跑 |
| 4 | `deploy-portal/engine.py` | `hardware_from_gpu()` 读目录的 `fp8_supported`,支持 `compute_capability=None`;方案按生态分组(`recipes_grouped`)并返回 `recipes_other_ecosystem`;新增 `ECOSYSTEM_NOTES` 与 `catalog_ecosystem_note()` | `tools/ci.py` 冒烟 |
| 5 | `deploy-portal/server.py` | 选中 `gpu_id` 时丢弃 `VERIFIED_ONLY_KEYS`;现场登记路径改为「不填算力就必须写明生态」 | 冒烟断言 |
| 6 | `web/js/app.js` | `smLabel(null)` 返回 `—`;新增共享的 `isCudaGpu()` / `computeLabel()` / `stackLabel()` | 浏览器复跑 |
| 7 | `web/js/views/recommend.js` | 下拉按厂商分组(未登记厂商兜底为「其他厂商」);换卡时同步停用无关控件;plan 卡片对非 CUDA 卡不显示 CUDA 栈与 NVIDIA 驱动下限;显示 `stack_note` | 浏览器复跑 |
| 8 | `web/js/views/ledger.js` `about.js` | 统一用 `computeLabel`/`stackLabel`;about 加「昇腾口径不同」整节与厂商列 | 浏览器复跑 |
| 9 | `deploy-portal/tools/smoke_test.py` | 新增 20 项昇腾断言 | 99/99 通过 |
| 10 | `DEVELOPMENT.md` `README.md` `model-selector/README.md` `about.js` | 口径与不收录原因 | 人工核对 |

## 验证

- `python tools/ci.py` → 通过 8 · 失败 0(离线 6 项 + 联网 2 项)
- `python deploy-portal/tools/smoke_test.py` → 99/99
- `python deploy-portal/tools/sync_gpus.py --check` → 15/15
- `python tools/ci.py --online` → 在线 65/65 文档可达

## 回滚

- 代码:`git` 已跟踪的文件可 `git checkout`;`deploy-portal/` 目前仍是未提交状态,
  所以回滚要按文件手工恢复(见下方遗留第 1 条)。
- 数据:`gpu-catalog.json` 可用 `sync_gpus.py --offline` 从现有快照重建,
  或在 `sync_gpus.py` 里删掉三条昇腾条目后重新联网核实。
- 无不可逆步骤:没有删改用户的大件资产。

## 遗留

- `deploy-portal/` 整个目录仍未纳入 git 跟踪,`git checkout` 无法回滚它。
  应该尽快提交一次基线 — 在真正需要回滚之前。
- 昇腾的部署方法尚无一条已记录方案(`recipes.json` 里没有 `ecosystem: cann` 条目)。
  工作区里 `deepseekv4-flash/offline-dsv4-0731/` 有真实的昇腾部署资产
  (TP8+EP、`--quantization ascend`、CANN 9.0.1),但 **910B4 尚未真机验收**,
  且 910B 不在目录内,所以还不能登记为方案。
- `deploy-portal/tools/sync_gpus.py` 的证书回落逻辑只在 `www.hiascend.com` 上被
  实际触发过;其他站点若出现同类问题,回落行为未逐一验证。

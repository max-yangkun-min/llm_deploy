# CI 可移植性 · 实现计划

- 功能 ID:`ci-portability`
- 对应规范:`spec.md`
- 状态:`已完成`

## 改动清单

| 顺序 | 文件 | 改什么 | 怎么验证 |
|---|---|---|---|
| 1 | `deploy-portal/tools/apply_patch.py` | 跨平台发现 codex(不写死平台与路径)+ 真实探测可用性 + 内置严格补丁引擎 + `--backend` / `LLM_DEPLOY_PATCH_BACKEND` | 五种场景直接调用:默认、内置、新增文件、错上下文、无可用的 codex |
| 2 | `tools/apply_patch.py` | 从「字节相同的第二份副本」改成转发入口 | `python tools/apply_patch.py <patch>` |
| 3 | `tools/ci.py` | `run()` 支持注入环境变量;「改文件工具」同时测默认后端与内置引擎,并覆盖新增文件链路 | `python tools/ci.py` |
| 4 | `tools/ci.py` | 新增 `check_shell_eol`:入库 `.sh` 内容不得带 CRLF | `python tools/ci.py` |
| 5 | `docs/CI.md`、`README.md`、`AGENTS.md`、`docs/PROJECT-MAP.md` | 检查表与工具口径对齐实际实现 | 人工逐条核对 |

## 验证

- 本机 Windows:`python tools/ci.py` → 通过 9 · 失败 0 · 跳过 1
  (跳过的是 `Shell 脚本语法`:本机 Windows 侧的 `bash` 读不到 `D:/...` 路径)。
- WSL Ubuntu(真 Linux,同一份工作区):`python3 tools/ci.py` → 通过 9 · 失败 0 ·
  跳过 1,`EXIT=0`。这就是修复前必然失败的那一项。
- 反例验证:把已应用过的补丁再打一次,内置引擎报「原文对不上」并退出 1,文件不变。
- 云端:`.github/workflows/ci.yml` 的 Actions 结论。首次推送 `17331d0` 为 failure,
  修复后 `8b03239` 的运行 #2 为 **success**(job `offline-gate` 第 4 步
  「项目 CI(离线门禁)」通过,run 35209938457)。

## 回滚

- 两个代码文件都在 git 里,`git checkout -- deploy-portal/tools/apply_patch.py tools/ci.py`
  即回到旧行为(旧行为在 Linux 上必红,所以回滚等于重新按下那个故障)。
- 无数据迁移、无不可逆步骤;`tools/apply_patch.py` 转发不影响调用方。

## 遗留

- 内置引擎只实现本仓库工具会产生的补丁子集(Update / Add / Delete File +
  `@@` 分块)。以后若要支持 `*** Move to:` 或模糊上下文,需要先补断言再说。
- `docs/CI.md` 的检查表此前漏了「改文件工具」「工作流骨架文件」两项,本次一并补上。

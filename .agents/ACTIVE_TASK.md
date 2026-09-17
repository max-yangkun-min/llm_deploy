# Active task pointer

Status: 大模型部署管理台已完成七阶段。阶段七(2026-09-17)=①GPU 目录加入**华为昇腾**(Atlas 350 / Atlas 300I Duo 96GB·48GB,逐字命中华为官方产品页),目录 12→15 张卡;昇腾**不做 sm 映射**(compute_capability=null + 口径说明),FP8 改读厂商页标称值,算力门槛与 NVIDIA 驱动下限加 cuda 守卫,KV cache 因 --quantization ascend 是专有量化而只按权重下界核算;方案按生态分组,不把 CUDA 栈方案挂到昇腾卡上;现场登记改为「不填算力就必须写明 ecosystem」。910B/310P 经尽力核实仍无厂商页证据(官网已换代,逐字 0 命中),故不收录,只在页面写明原因。②按用户要求把项目整理成纯终端工作流:重写 AGENTS.md 为项目宪法,新增 .codex-specs/ 规范层、docs/PROJECT-MAP.md、docs/CI.md,并把稳定检查固化为 tools/ci.py + scripts/ci/*;两个 Windows 定时任务(llm-ci-daily / llm-ci-weekly)已注册并验证 LastTaskResult=0。验证:ci.py 离线 8/8、联网 10/10(GPU 15/15、文档 65/65);smoke_test.py 99/99(昇腾反回归 20 项);浏览器六视图 0 报错 0 警告、无 [object Object]/sm_null。同版修掉 whole_file_replace.py 两个缺陷(首行被改动时丢新首行、回滚用 Python 3.8 不支持的 write_text(newline=))并补了往返断言。
Task ID: deploy-portal
Memory: `.agents/tasks/deploy-portal/MEMORY.md`
Inputs: `.agents/tasks/deploy-portal/INPUTS.md`
Last updated: 2026-09-17 (Asia/Shanghai) — 阶段七(昇腾双生态 + 持续集成/定时检查)已完成并验证

## Previously active task

Status: DeepSeek 0731 ARM64 image archived and split; target 910B4 validation pending
Task ID: deepseekv4-flash-910b4
Memory: `.agents/tasks/deepseekv4-flash-910b4/MEMORY.md`
Inputs: `.agents/tasks/deepseekv4-flash-910b4/INPUTS.md`
Last updated: 2026-08-06 (Asia/Shanghai)

Read the referenced files before continuing a task. Update this pointer only
when the user starts, switches, completes, or explicitly clears a task.

# 用户协作偏好

更新时间：2026-07-21（Asia/Shanghai）

## 长时间操作硬约束

- 任何预计会长时间运行、持续占用磁盘/网络/GPU/CPU，或可能明显阻塞用户工作的操作，执行前必须先说明预计耗时、收益和风险，并询问用户当前是否有时间、是否同意立即执行。
- 默认优先解决最重要、最能快速闭环的问题；耗时的复制、下载、全盘扫描、完整哈希、压力测试等工作应拆到后面，不能未经确认直接开始。
- 如果操作开始后发现实际耗时显著超出预估，应立即向用户报告进度和新 ETA，并询问继续、暂停还是改用轻量方案。
- 对可复用的数据优先采用共享路径或增量方案，避免不必要的大文件复制。
# Offline package acceptance

- An offline deployment package is not complete merely because its container
  image exists in Docker Desktop. The image must be exported with `docker save`
  into the deliverable directory, covered by SHA-256 checksums, and validated
  as loadable offline with `docker load`.
- After the exported image archive has been independently validated, the
  task-specific local Docker image may be removed when the user requests it.
  Never extend that permission to unrelated images, containers, caches,
  volumes, or VHD files.
- Model deployment packages that support tool use must enable the appropriate
  automatic tool-choice and parser flags. Acceptance testing must send a real
  request containing `tools` plus `tool_choice: "auto"`; plain text generation
  alone does not validate tool calling.

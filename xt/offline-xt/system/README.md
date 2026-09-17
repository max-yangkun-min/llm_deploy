# XT系统依赖应急包

默认策略是保留服务器已有驱动、Docker和NVIDIA Container Toolkit。只有现场检查缺失时
才使用本目录:

- `docker/focal/`:Ubuntu 20.04 amd64专用。
- `docker/jammy/`:Ubuntu 22.04 amd64专用。
- `docker/noble/`:Ubuntu 24.04 amd64专用。
- `nvidia-container-toolkit/`:4个amd64 deb,三个Ubuntu LTS共用。
- `driver/`:R570 `.run`人工兜底,绝不自动安装。

现场先执行`bash scripts/recon.sh`。如果Docker或NVIDIA runtime缺失:

```bash
cd /offline-xt
sha256sum -c MANIFEST.sha256
sudo bash scripts/install-system-deps.sh
sudo bash scripts/install-offline.sh
```

脚本读取`/etc/os-release`并只选择匹配的codename目录。已有可用Docker/runtime时跳过,
不会覆盖升级；选中的deb会先按`PACKAGES.lock`校验SHA256。现有驱动低于545.0时
立即停止。驱动`.run`不会由脚本执行;它仍要求与`uname -r`完全匹配的
`linux-headers`、gcc/make、Secure Boot审查、维护窗口和重启。未知内核无法提前准备
通用headers,必须在recon后单独补齐。

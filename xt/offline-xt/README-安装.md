# XT 离线包现场安装步骤（不含模型权重）

本包使用单镜像`xt-vllm:0.24.0-cu129-compat545`,内含vLLM、Ray、
`cuda-compat-12-9`和nginx。当前介质不含三套模型权重；系统应急包覆盖Ubuntu
20.04(focal)、22.04(jammy)、24.04(noble)的Docker CE以及通用NVIDIA Toolkit。

## 1. 先复制到服务器本地盘

移动硬盘为exFAT,不可靠保存Linux执行位。建议把包复制到本地SSD:

```bash
sudo mkdir -p /offline-xt
sudo cp -a /media/<移动硬盘挂载点>/offline-xt/. /offline-xt/
cd /offline-xt
sudo chmod +x scripts/*.sh
```

空间不足而必须从移动硬盘直接安装时,使用实际挂载路径覆盖`PKG`,并始终用
`bash`调用脚本:

```bash
cd /media/<移动硬盘挂载点>/offline-xt
sudo env PKG="$PWD" bash scripts/install-offline.sh
```

## 2. 两台服务器分别执行现场侦察

```bash
cd /offline-xt
bash scripts/recon.sh
```

确认:

- GPU全部为A40/sm_86,数量符合7+7或8+6布局。
- 实际驱动版本不低于545.0。
- Docker与NVIDIA Container Toolkit已经可用,`docker run --gpus all`能看到GPU。
- 记录两台的Ubuntu`VERSION_CODENAME`、万兆网卡名、IP和GPU拓扑。

任何安装动作前先校验整包:

```bash
cd /offline-xt
sha256sum -c MANIFEST.sha256
```

如果Docker或NVIDIA Container Toolkit尚未安装,执行:

```bash
cd /offline-xt
sudo bash scripts/install-system-deps.sh
```

脚本会读取`VERSION_CODENAME`,只选择匹配的focal/jammy/noble目录；已有可用环境时
保持原版本并跳过。安装前会再次按`PACKAGES.lock`核对所选deb的SHA256；如果不是
这三个Ubuntu LTS之一,脚本拒绝安装。检测到现有驱动低于545.0时也会直接停止。

`system/driver/`包含R570兜底安装器,但不会被脚本自动执行。驱动升级还需要匹配
`uname -r`的linux-headers、gcc/make、Secure Boot审查、维护窗口与重启；未知内核
无法提前准备通用headers。

## 3. 校验并安装镜像

```bash
cd /offline-xt
sha256sum -c MANIFEST.sha256
sudo bash scripts/install-offline.sh
```

安装脚本会再次校验MANIFEST,再执行`docker load`,最后强制检查:

- 镜像标签、PyTorch CUDA 12.9、vLLM 0.24.0、Ray 2.56.1和nginx。
- 驱动版本、NVIDIA runtime、A40/sm_86。
- 实际加载的是compat目录中的libcuda。
- Triton PTX JIT可以在真实A40上编译并运行。

R545不在官方cu129镜像预置驱动分支白名单内。本包只允许它进入上述实机验收；
任何compat libcuda或Triton检查失败都必须停止,不能删除断言继续部署。

## 4. 放置权重并配置现场参数

按最终方案把权重复制到服务器SSD的`/data/models/`。默认目录名:

```text
/data/models/Kimi-K2.6-AWQ
/data/models/Qwen3.5-397B-A17B-AWQ
/data/models/MiniMax-M2.7-AWQ
```

修改`/offline-xt/scripts/run.sh`顶部的`MODELS_DIR`、`HF_CACHE`、`NIC`和
`HEAD_IP`;修改`/offline-xt/scripts/lb/nginx.conf`中的两台M2.7地址。

## 5. 启动

```bash
# M2.7双副本:两台各执行
bash scripts/run.sh m2.7
# 任一网关节点执行,宿主统一入口为9000
bash scripts/run.sh lb-nginx

# 397B跨机PP:机器A/机器B/机器A
RAY_GPU_DEVICES=0,1,2,3 bash scripts/run.sh ray-head
RAY_GPU_DEVICES=0,1,2,3 bash scripts/run.sh ray-worker
bash scripts/run.sh 397b

# 8+6备用:8卡机/6卡机
bash scripts/run.sh 397b-8gpu
bash scripts/run.sh m2.7
```

K2.6与各模型的完整启动、日志和验收步骤见`models/*/README-部署.md`。

## 6. 最终验收边界

当前联网准备机已验证镜像可以构建、导出、重新`docker load`,并通过无GPU验收和
nginx配置检查。下列项目只能在现场A40和实际权重上完成:

- R545 + cuda-compat-12-9 + Triton PTX JIT。
- AWQ Marlin内核。
- 三个模型架构及tool/reasoning parser。
- Ray跨机PP和10GbE性能。

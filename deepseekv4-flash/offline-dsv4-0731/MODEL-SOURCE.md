# 模型与镜像来源

## 模型

- 国内来源：ModelScope
- 仓库：`Eco-Tech/DeepSeek-V4-Flash-0731-w8a8`
- 固定 revision：`9e8679a9db7eec11efed9925f7efb96549077545`
- 架构：`DeepseekV4ForCausalLM`
- 量化：Ascend ModelSlim W8A8 dynamic
- 权重分片：74
- 索引权重总量：`314621886200` bytes
- 仓库总下载量：`314724356065` bytes

权重结构包含 DSpark 配置和一层 MTP。随附最佳实践只标记了
`vLLM-Ascend + Atlas_A3_Inference`，没有声明 A2/910B4 已验证，因此必须
在目标 8×910B4 机器上完成加载和推理验收。

## 镜像

- 上游：`quay.io/ascend/vllm-ascend:nightly-main`
- 国内代理：`m.daocloud.io/quay.io/ascend/vllm-ascend`
- 固定 OCI index digest：
  `sha256:ade04e75aa4a888df5dfb7917f21e7d9178014d5f5e52b358f2cd1d8897f46ce`
- `linux/amd64` manifest：
  `sha256:05dab76f136f78db6bdf5c1e6d5cb1f6085d451fbcd219e0e6b37768f43f7227`
- `linux/arm64` manifest：
  `sha256:8dd01aa0e0e5c4b04d3d715f483351af24c626c30373215e74238cf389fc2a93`
- 构建时间：2026-08-04
- 关键组件：vLLM 0.26.0、CANN 9.0.1、torch_npu 26.1.0 系列

DaoCloud 国内代理和官方 Quay 在核验时返回相同 OCI index 与平台摘要。
离线交付使用固定 digest，不依赖会变化的 `nightly-main` 标签。

## 离线镜像文件

目标机为 ARM64，ARM64 离线镜像 tar 已生成并完成独立结构校验。

- 路径：`images/vllm-ascend-nightly-main-20260804-arm64.tar`
- 平台：`linux/arm64`
- ARM64 manifest digest：`sha256:8dd01aa0e0e5c4b04d3d715f483351af24c626c30373215e74238cf389fc2a93`
- 文件大小：`6364067840` bytes
- 文件 SHA-256：`57bbe948bec21654eebdcdfe9bbbc939c6054ba40592d75f8b6ee73403c557a1`
- 导出方式：固定 ARM64 manifest 的 OCI blobs 组装为 Docker 离线 tar
- 验收要求：`docker load` 后镜像 ID 必须等于 OCI index digest，架构必须为 `arm64`
- 本地运行标签：`deepseek-v4-flash/vllm-ascend:20260804-arm64`（加载并核验后创建）
- 独立验证：归档包含 18 个 blob，config 明确为 `linux/arm64`

> 包内原有的 `images/vllm-ascend-nightly-main-20260804-amd64.tar`（amd64，
> SHA-256 `02c7077305980f5cb03a7728436b90259ed07bc491f58d16a860ecf1931003b8`）
> 仅供 amd64 环境排障参考，**不能**在 ARM64 目标机上加载。

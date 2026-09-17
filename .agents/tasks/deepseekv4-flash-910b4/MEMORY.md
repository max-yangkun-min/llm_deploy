# DeepSeek V4 Flash on Ascend 910B4 feasibility

## GLM-5.2 Docker 清理（2026-08-06）

- 用户明确要求清除此前构建 GLM-5.2 的镜像和缓存。
- 已删除未被容器使用的镜像：`glm52-vllm:0.24.0-pr38476-cu128-native-r570-a100`、固定 vLLM 基础镜像 `4fab2d06cb38`、CUDA 12.8 构建基础镜像 `a99a1860ba8e`。
- 已删除 Buildx 中所有已识别的 `kty5l/build-glm52-vllm-cu128` 和 `kty5l/offline-glm52/scripts` 构建记录。
- 随后回收未引用 BuildKit 缓存，Docker 报告回收约 `76.88 GB`；剩余 BuildKit 缓存约 `35.76 MB`。
- 两个运行中的业务容器 `deploy-satellite-ew-analysis-1` 和 `deploy-cesium-mcp-1` 保持运行；D 盘离线 tar 未改动。
- C 盘空间清理前后均约 `31.87 GB`，因为 Docker/WSL VHDX 未压缩；未执行任何 VHDX 修改。若需让空间返还 C 盘，必须另行明确授权压缩操作。

## A100 镜像准备取消（2026-08-06）

- 用户后来取消了为 x86/NVIDIA A100 8 卡准备 DeepSeek V4 Flash 0731 镜像的请求。
- 未下载 NVIDIA 权重、未拉取 CUDA 镜像、未构建或修改任何 A100 镜像；现有 ARM64 Ascend 离线包保持不变。
- 公开检索出现 vLLM 上游正在推进 SM80/Ampere 支持的 feature/issue，但在用户取消前未将其验证为可交付的 A100 0731 部署方案。

## ARM64 镜像分卷完成（2026-08-06）

- 用户要求将 ARM64 镜像分成适合 4.7G 盘刻录的两片。
- 原始 tar 保留不变：`6364067840` bytes，SHA-256 `57bbe948bec21654eebdcdfe9bbbc939c6054ba40592d75f8b6ee73403c557a1`。
- 分卷：`.part01` 为 `4600000000` bytes，SHA-256 `d91971ee17073c783463e991e73cc9cd2b189c9162ccecb222fbbd418ff651bf`；`.part02` 为 `1764067840` bytes，SHA-256 `95583f88dd6035f98132eb7e4ef69848df74850ea58bd0b6524bd1ebabef47c1`。
- 分卷按顺序重组后与原 tar 完全一致；说明文件为 `images/vllm-ascend-nightly-main-20260804-arm64.tar.parts.sha256.txt`。

## ARM64 镜像拉取状态（2026-08-06）

- Docker Desktop 已启动，daemon 可用：Docker 28.4.0，`linux/x86_64`，数据根目录为 `/var/lib/docker`（Docker Desktop/WSL，实际位于 C 盘）。
- 已尝试从国内 DaoCloud 镜像源拉取固定 OCI index `sha256:ade04e75aa4a888df5dfb7917f21e7d9178014d5f5e52b358f2cd1d8897f46ce` 的 `linux/arm64` 平台。
- 拉取命令运行超过 30 分钟后超时；当前镜像列表没有完整的 `vllm-ascend` ARM64 镜像，尚未执行 `docker save`，因此 ARM64 tar 尚未生成。
- C 盘余量从 33.84 GB 降至 31.87 GB；没有删除或清理任何现有镜像、容器、卷或缓存。按照全局存储规则，继续大规模拉取前必须先解决 C 盘/Docker 数据位置问题。

## ARM64 镜像归档完成（2026-08-06）

- 用户开启本机代理 `127.0.0.1:7897`。DaoCloud 国内源的 Registry 元数据可访问，但 CDN 传输经代理不稳定（多次 503/401）；通过代理获取签名 URL、直连 CDN 后恢复下载。官方 Quay 同一 manifest 可验证，但当前代理线路过慢，因此未用于正式下载。
- 已将固定 ARM64 manifest `sha256:8dd01aa0e0e5c4b04d3d715f483351af24c626c30373215e74238cf389fc2a93` 的 18 个 blob 下载到 D 盘并逐层 SHA-256 校验。
- 已生成 `deepseekv4-flash/offline-dsv4-0731/images/vllm-ascend-nightly-main-20260804-arm64.tar`，大小 `6364067840` bytes，SHA-256 `57bbe948bec21654eebdcdfe9bbbc939c6054ba40592d75f8b6ee73403c557a1`。
- 独立离线验证通过：归档结构正确，固定 manifest digest 正确，config 为 `linux/arm64`。包内 11 个文件的 `PACKAGE-SHA256SUMS` 全部通过。
- 本机 Docker 数据根目录仍在 C 盘 WSL VHD；为遵守存储规则，未执行本机 `docker load`，也未导入 ARM64 镜像。最终 tar 已保留在 D 盘，可在目标 ARM64 服务器执行 `docker load`。

Status: pinned model download complete and verified; ARM64 offline package scripts updated; deployment deferred by user
Last updated: 2026-08-06 (Asia/Shanghai)

## Objective

Determine whether the photographed server can deploy the newest DeepSeek V4
Flash release, with the user requiring a release after 2026-08-02.

## Hardware confirmed from the supplied screenshot

- 8 x Ascend 910B4-1 (Ascend A2 generation).
- 65,536 MiB HBM per NPU; 512 GiB aggregate nominal HBM.
- `npu-smi 25.5.1`; all eight devices show `Health: OK`.
- Eight existing `VLLMWorker_TP` processes occupy 59,272 MiB each and total HBM
  usage is about 62,647-62,648 / 65,536 MiB per NPU. The current embedding
  service must be stopped before reusing the same eight NPUs.

## Release-date finding

- As of 2026-08-04, no verifiable official DeepSeek V4 Flash model was
  published after 2026-08-02.
- Latest official weight repository found:
  `deepseek-ai/DeepSeek-V4-Flash-0731`.
- Exact Hugging Face commit: `7872f01b1d1fe23eabc4c98b48bffcef5a386062`.
- Repository created 2026-07-31 07:30:24 UTC; last modified
  2026-08-01 03:07:41 UTC (2026-08-01 11:07:41 China time).
- DeepSeek's homepage carrying the official-release API banner has HTTP
  `Last-Modified: 2026-07-31 06:18:47 UTC`; its Responses API guide has
  `Last-Modified: 2026-08-01 09:24:57 UTC`.
- Candidate names `-0802`, `-0803`, `-0804`, `V4.1-Flash`, and `-Latest` do not
  exist under the official `deepseek-ai` namespace on the checked sources.
- Therefore the user's strict post-August-2 condition cannot currently be met;
  third-party pages dated later must not be treated as model artifacts.

## Model and memory findings

- Official 0731 model architecture: `DeepseekV4ForCausalLM`, with DSpark
  speculative decoding, up to 1,048,576 configured positions, FP8 block
  quantization and FP4 expert weights.
- Official 0731 index reports 166,878,536,440 bytes of weights (155.42 GiB), 48
  shards, or 19.43 GiB/card under ideal TP8 sharding. Capacity alone is ample,
  but this NVIDIA-oriented FP4/FP8 checkpoint is not the documented A2 turnkey
  artifact.
- vLLM Ascend's public single-node A2 recipe uses the Ascend-converted
  `Eco-Tech/DeepSeek-V4-Flash-w8a8-mtp` checkpoint: 300,080,868,926 bytes
  (279.47 GiB), about 34.93 GiB/card at TP8. The official tutorial explicitly
  supports one Atlas 800 A2 node (8 x 64 GiB), with 133,120 max model length,
  TP8+EP, 32 sequences, and 0.9 memory utilization.
- That public W8A8 checkpoint was created 2026-04-24 and last updated
  2026-05-07, so it is based on the preview line, not the latest 0731 formal
  release.
- The vLLM Ascend main branch includes DeepSeek V4, DSpark, MTP and A2 code.
  Its A2+DSpark tutorial currently requires `nightly-main` and an
  `UploadWeight/DeepSeek-V4-Flash-DSpark-w4a8-test` checkpoint rather than a
  pinned, publicly reproducible 0731 Ascend release artifact.
- vLLM Ascend v0.23.0rc1 is a prerelease and requires CANN 9.0.1,
  PyTorch 2.10.0 and torch_npu 2.10.0.post2. `npu-smi 25.5.1` alone does not
  prove that this user-space stack is installed.

## Verdict

- Hardware verdict: yes for the DeepSeek V4 Flash family using the published
  Ascend W8A8-MTP recipe; start conservatively at 64K or 128K context after
  freeing all eight NPUs.
- Strict requested-version verdict: not yet a supported, reproducible deployment.
  There is no official post-2026-08-02 model, and the latest 0731 weights lack a
  pinned public A2 conversion/runtime bundle. Do not download or deploy an
  unofficial later-dated artifact.

## Verified domestic sources

- ModelScope official mirror: `deepseek-ai/DeepSeek-V4-Flash-0731`.
- ModelScope Ascend-converted preview checkpoint:
  `Eco-Tech/DeepSeek-V4-Flash-w8a8-mtp`.
- Domestic HF API mirror was used to verify the official 0731 commit and dates.
  Direct Hugging Face was unreachable; no large weights were downloaded.

## If the user proceeds later

Before building or downloading, recheck the official `deepseek-ai` namespace
for a genuinely newer release and verify exact commit, file list, sizes and
checksums on a domestic mirror. For 0731 on A2, require a public pinned Ascend
W8A8/W4A8 conversion and matching vLLM Ascend/CANN image, then validate model
load, one-token generation, accuracy, tool parsing, 64K/128K context and load.

## 0731 deployment package progress (2026-08-04)

The user explicitly requested deployment of the latest 0731 formal release,
then requested that work pause after the current package-preparation step.

### Newly verified model artifact

- ModelScope OpenAPI exposed the post-release Ascend conversion that the older
  model-detail query did not reveal:
  `Eco-Tech/DeepSeek-V4-Flash-0731-w8a8`.
- Pinned ModelScope revision:
  `9e8679a9db7eec11efed9925f7efb96549077545`.
- Created 2026-08-01 09:51:55 +08:00 and updated
  2026-08-02 12:55:08 +08:00.
- Downloader API test at the pinned revision returned 85 hashed blob files,
  74 W8A8 safetensor shards and 314,724,356,065 total bytes.
- The checkpoint index reports 314,621,886,200 weight bytes.
- Architecture and release fields match formal 0731:
  `DeepseekV4ForCausalLM`, one conventional MTP layer, DSpark target layers
  40/41/42, and Markov-head weights in the extra MTP namespace.
- The ModelSlim best-practice file identifies W8A8 dynamic quantization and
  records A3 verification. A2 deployment therefore starts at 64K and low
  concurrency and still requires real acceptance testing.

### Runtime decision

- vLLM Ascend v0.23.0rc1 was rejected for 0731: it has only the old single-MTP
  loader and no `deepseek_v4_dspark.py`; 0731 carries additional MTP/Markov
  weights that create a loader-compatibility risk.
- Selected runtime is the 2026-08-04 `nightly-main` image, pinned by immutable
  OCI index digest rather than a floating tag:
  `sha256:ade04e75aa4a888df5dfb7917f21e7d9178014d5f5e52b358f2cd1d8897f46ce`.
- DaoCloud domestic proxy and official Quay returned the same index digest.
- Platform manifests:
  - amd64: `sha256:05dab76f136f78db6bdf5c1e6d5cb1f6085d451fbcd219e0e6b37768f43f7227`
  - arm64: `sha256:8dd01aa0e0e5c4b04d3d715f483351af24c626c30373215e74238cf389fc2a93`
- Image config shows build time 2026-08-04, vLLM 0.26.0, CANN 9.0.1,
  Python 3.12.13, and torch_npu build series 26.1.0. Its source context was
  copied after main boundary `b481d79c7de49ab285e61cec689172931c124429`;
  the image does not label the exact source commit, so the OCI digest is the
  authoritative identity.
- DSv4 DSpark support was present before that boundary (feature commit
  `8fe122d95fc8cc94f32525f9ed36c2b5e3fbfdcc`).

### Package produced

Directory: `deepseekv4-flash/offline-dsv4-0731/`

- `README.md`: Chinese deployment and tuning instructions.
- `MODEL-SOURCE.md`: domestic mirror, exact revision, image digests and source
  provenance.
- `start.sh`: pull/download/verify/preflight/diagnose/start/logs/status/test/stop.
- `scripts/download_model.py`: ModelScope-only pinned snapshot downloader with
  `.part` resume, 1-8 download jobs, size and per-file SHA-256 verification.
- `scripts/verify_model.py`: quick/full model checks, architecture, MTP/DSpark,
  74 shards and exact index size.
- `scripts/run-server.sh`: TP8+EP, 64K, 4 sequences, Ascend quantization,
  DSpark=7, tool parser and reasoning parser. Runtime values are overrides.
- Model placeholder directory exists but no weights were downloaded.

### Validation completed

- WSL `bash -n` passed for `start.sh` and `scripts/run-server.sh` after the
  pinned-nightly update.
- Python AST parsing passed for both Python scripts.
- The downloader's actual pinned API request passed and confirmed 85 files,
  74 shards, and 314,724,356,065 bytes.
- Stale v0.23.0rc1 image digests were removed from the package.

### Paused state and next action

- No 293 GiB model download was started.
- No image was pulled; local Docker Desktop was not running.
- Local D: has only about 175.95 GiB free and cannot hold the model; E: has
  about 453.19 GiB, but no local staging was started because the target is the
  intended download location.
- Direct SSH to `root@192.168.54.54:22` timed out from this execution
  environment. No target-side change was made and the existing Qwen embedding
  service was not stopped.
- On resume, do not repeat model/image/source verification or package creation.
  First restore network reachability to 192.168.54.54 (or obtain another
  reachable transfer route), copy `offline-dsv4-0731/`, then run `pull`,
  `download`, `verify`, `preflight`, `diagnose`, `start`, `logs`, and `test`.
  Stop the existing NPU service only when the user is ready for the actual
  switchover.

## Resume diagnostics (2026-08-05)

- The user resumed the task. No image pull, model download, package transfer,
  or target-side mutation was performed.
- SSH to `root@192.168.54.54:22` still times out before authentication, and
  ICMP receives no replies.
- The workstation has no route for `192.168.54.0/24`; traffic follows the
  Wi-Fi default gateway (`172.16.0.1`) and then traverses a public China Mobile
  path, so it cannot reach the private target address.
- Both installed OpenVPN adapters are disconnected. The only locally imported
  OpenVPN profile uses `route-nopull` and declares routes only for
  `192.168.107.0/24` and `192.168.110.0/24`, not `192.168.54.0/24`. Connecting
  that profile alone is therefore not a verified fix.
- Required next input: a VPN/profile that routes `192.168.54.0/24`, a reachable
  jump host/transfer route, or a corrected reachable target address. Once
  supplied, first re-test SSH, then copy the existing package and continue the
  recorded `pull` through `test` sequence. Do not recreate or re-verify the
  package before transfer.

## Local no-weights deliverable (2026-08-05)

- The user explicitly deferred deployment and requested only a local offline
  deployment package without model weights.
- Final archive:
  `deepseekv4-flash/offline-dsv4-0731-no-weights-20260805.tar.gz`
- Archive size: 9,990 bytes.
- Archive SHA-256:
  `8dad69bd81f48b3a37500be5bc981cc97deed3eecfa8a0aa04ae987f22ac1b8c`
- Sidecar checksum:
  `deepseekv4-flash/offline-dsv4-0731-no-weights-20260805.tar.gz.sha256`
- The archive has exactly eight files: README, source provenance, internal
  checksum manifest, orchestration script, three helper scripts, and the empty
  model-directory placeholder. It contains no weights, container image,
  `.part`, `__pycache__`, or `.pyc` files.
- Documentation was corrected to match the actual default runtime configuration:
  DSpark with seven speculative tokens; MTP with one token is the troubleshooting
  fallback.
- Validation passed: WSL `bash -n`, Python byte compilation, all seven internal
  SHA-256 entries, explicit archive entry audit, and archive sidecar checksum.
- No external artifact was downloaded and no target-side action was performed.

## Image availability recheck (2026-08-05)

- The local Docker image list still has no DeepSeek or vLLM Ascend image; the
  only vLLM image is the unrelated NVIDIA/amd64 `vllm-openai` image.
- Read-only `docker manifest inspect` against the selected domestic proxy
  succeeded for
  `m.daocloud.io/quay.io/ascend/vllm-ascend@sha256:ade04e75aa4a888df5dfb7917f21e7d9178014d5f5e52b358f2cd1d8897f46ce`.
  It exposes the previously verified amd64 manifest
  `sha256:05dab76f136f78db6bdf5c1e6d5cb1f6085d451fbcd219e0e6b37768f43f7227`
  and arm64 manifest
  `sha256:8dd01aa0e0e5c4b04d3d715f483351af24c626c30373215e74238cf389fc2a93`.
- This confirms online availability and digest stability, not successful
  runtime acceptance on the target 8x Ascend 910B4 host. No image pull was
  started.
- Clarification after the user asked whether 910B startup was already proven:
  it is not. The downloaded checkpoint's own
  `DeepSeek-V4-Flash-DSpark_best_practice.yaml` lists the verified tag only as
  `vLLM-Ascend` plus `Atlas_A3_Inference`; it does not claim A2/910B4
  validation. The image/checkpoint combination must therefore be treated as a
  technically plausible A2 candidate, not a validated 910B4 deployment, until
  target-side `diagnose`, model load, generation, and stability tests pass.

## Image pull blocked by storage policy (2026-08-05)

- The user requested pulling the pinned vLLM Ascend image locally.
- Mandatory preflight measured C: free space at **58.35 GiB**. Docker data is
  still stored at
  `C:\Users\11984\AppData\Local\Docker\wsl\disk\docker_data.vhdx`, whose
  physical size is **109.5 GiB**.
- Docker reports 98.49 GB of images, 1.546 GB of local volumes, and 2.535 GB of
  build cache. Two business containers remain active.
- The global storage rule forbids large Docker pull/load/build operations when
  Docker data is on C:, so the pull was not started. No image, cache, volume,
  container, or VHDX was modified or deleted.

## Pinned image downloaded (2026-08-05 20:22)

- The user explicitly authorized this image download despite Docker data being
  on C:. This was treated as a one-operation exception; no VHDX modification,
  cleanup, container start, or model deployment was authorized or performed.
- Pre-pull C: free space was **58.35 GiB** and the Docker VHDX was **109.5
  GiB**. The amd64 manifest contained about 6.10 GiB of compressed layers. A
  monitored pull used a hard safety stop at 25 GiB C: free space.
- Successfully pulled from the verified domestic DaoCloud proxy:
  `m.daocloud.io/quay.io/ascend/vllm-ascend@sha256:ade04e75aa4a888df5dfb7917f21e7d9178014d5f5e52b358f2cd1d8897f46ce`.
- Local inspection exactly matches that OCI digest, reports `linux/amd64`,
  image size 6,569,083,297 bytes, and build timestamp
  `2026-08-04T05:51:07.219178367Z`.
- Post-pull C: free space is **38.26 GiB** and the Docker VHDX is **129.59
  GiB**. Do not perform another large Docker operation without a fresh storage
  preflight. The image has not been run or exported.

## Offline image deliverable completed (2026-08-05)

- User clarified the permanent acceptance rule: an offline package is not
  complete when the image exists only in Docker Desktop. Every offline package
  must include a `docker save` archive, SHA-256 coverage, and an independent
  offline `docker load` validation. This is also recorded in
  `.agents/USER-PREFERENCES.md`.
- Exported the pinned vLLM Ascend image into the package as
  `deepseekv4-flash/offline-dsv4-0731/images/vllm-ascend-nightly-main-20260804-amd64.tar`.
  Size: 6,569,105,408 bytes. SHA-256:
  `02c7077305980f5cb03a7728436b90259ed07bc491f58d16a860ecf1931003b8`.
- Added `./start.sh load`. It loads the bundled archive, verifies image ID
  `sha256:ade04e75aa4a888df5dfb7917f21e7d9178014d5f5e52b358f2cd1d8897f46ce`
  and `amd64`, then creates local runtime tag
  `deepseek-v4-flash/vllm-ascend:20260804-amd64`. Network `pull` remains only a
  fallback.
- Independently removed the downloaded image, loaded only from the D: archive,
  verified the exact image ID and architecture, and then removed the test image
  again per user request. Final inspect by both tag and image ID returns absent.
  No unrelated image, container, cache, volume, or VHDX was changed.
- Tool use is mandatory. Runtime already pins `--enable-auto-tool-choice`,
  `--tool-call-parser deepseek_v4`, and `--reasoning-parser deepseek_v4`.
  `./start.sh test` now sends a real `tools` plus `tool_choice: "auto"` request
  and fails unless the response contains a `get_weather` tool call. This
  permanent acceptance requirement is also in user preferences.
- Final archive:
  `deepseekv4-flash/offline-dsv4-0731-with-image-no-weights-20260805.tar.gz`.
  Size: 6,528,088,715 bytes (6.08 GiB). SHA-256:
  `f22e31af11d8ade9b69d5ddab2086baf5e6812705a553212c3c72d0d6b168bd4`.
  Matching `.sha256` sidecar exists. Archive audit: 14 entries, exactly one
  image tar, zero safetensors, zero `__pycache__`/`.pyc` files.
- Full internal `PACKAGE-SHA256SUMS`, Bash syntax, OCI archive structure, and
  external archive checksum checks passed. The 293 GiB verified model remains
  separate under `E:\llm_models\DeepSeek-V4-Flash-0731-w8a8`.
- Final measured free space: C: **38.07 GiB**, D: **156.54 GiB**. Docker data
  remains on C:; perform no further large Docker operation without a fresh
  storage preflight.

## Offline image deliverable completed (2026-08-05)

- User clarified the permanent acceptance rule: an offline package is not
  complete when the image exists only in Docker Desktop. Every offline package
  must include a `docker save` archive, SHA-256 coverage, and an independent
  offline `docker load` validation. This is also recorded in
  `.agents/USER-PREFERENCES.md`.
- Exported the pinned vLLM Ascend image into the package as
  `deepseekv4-flash/offline-dsv4-0731/images/vllm-ascend-nightly-main-20260804-amd64.tar`.
  Size: 6,569,105,408 bytes. SHA-256:
  `02c7077305980f5cb03a7728436b90259ed07bc491f58d16a860ecf1931003b8`.
- Added `./start.sh load`. It loads the bundled archive, verifies image ID
  `sha256:ade04e75aa4a888df5dfb7917f21e7d9178014d5f5e52b358f2cd1d8897f46ce`
  and `amd64`, then creates local runtime tag
  `deepseek-v4-flash/vllm-ascend:20260804-amd64`. Network `pull` remains only a
  fallback.
- Independently removed the downloaded image, loaded only from the D: archive,
  verified the exact image ID and architecture, and then removed the test image
  again per user request. Final inspect by both tag and image ID returns absent.
  No unrelated image, container, cache, volume, or VHDX was changed.
- Tool use is mandatory. Runtime already pins `--enable-auto-tool-choice`,
  `--tool-call-parser deepseek_v4`, and `--reasoning-parser deepseek_v4`.
  `./start.sh test` now sends a real `tools` plus `tool_choice: "auto"` request
  and fails unless the response contains a `get_weather` tool call. This
  permanent acceptance requirement is also in user preferences.
- Final archive:
  `deepseekv4-flash/offline-dsv4-0731-with-image-no-weights-20260805.tar.gz`.
  Size: 6,528,088,715 bytes (6.08 GiB). SHA-256:
  `f22e31af11d8ade9b69d5ddab2086baf5e6812705a553212c3c72d0d6b168bd4`.
  Matching `.sha256` sidecar exists. Archive audit: 14 entries, exactly one
  image tar, zero safetensors, zero `__pycache__`/`.pyc` files.
- Full internal `PACKAGE-SHA256SUMS`, Bash syntax, OCI archive structure, and
  external archive checksum checks passed. The 293 GiB verified model remains
  separate under `E:\llm_models\DeepSeek-V4-Flash-0731-w8a8`.
- Final measured free space: C: **38.07 GiB**, D: **156.54 GiB**. Docker data
  remains on C:; perform no further large Docker operation without a fresh
  storage preflight.

## Pinned image downloaded (2026-08-05 20:22)

- The user explicitly authorized this image download despite Docker data being
  on C:. This was treated as a one-operation exception; no VHDX modification,
  cleanup, container start, or model deployment was authorized or performed.
- Pre-pull C: free space was **58.35 GiB** and the Docker VHDX was **109.5
  GiB**. The amd64 manifest contained about 6.10 GiB of compressed layers. A
  monitored pull used a hard safety stop at 25 GiB C: free space.
- Successfully pulled from the verified domestic DaoCloud proxy:
  `m.daocloud.io/quay.io/ascend/vllm-ascend@sha256:ade04e75aa4a888df5dfb7917f21e7d9178014d5f5e52b358f2cd1d8897f46ce`.
- Local inspection exactly matches that OCI digest, reports `linux/amd64`,
  image size 6,569,083,297 bytes, and build timestamp
  `2026-08-04T05:51:07.219178367Z`.
- Post-pull C: free space is **38.26 GiB** and the Docker VHDX is **129.59
  GiB**. Do not perform another large Docker operation without a fresh storage
  preflight. The image has not been run or exported.

## Image pull blocked by storage policy (2026-08-05)

- The user requested pulling the pinned vLLM Ascend image locally.
- Mandatory preflight measured C: free space at **58.35 GiB**. Docker data is
  still stored at
  `C:\Users\11984\AppData\Local\Docker\wsl\disk\docker_data.vhdx`, whose
  physical size is **109.5 GiB**.
- Docker reports 98.49 GB of images, 1.546 GB of local volumes, and 2.535 GB of
  build cache. Two business containers remain active.
- The global storage rule forbids large Docker pull/load/build operations when
  Docker data is on C:, so the pull was not started. No image, cache, volume,
  container, or VHDX was modified or deleted.

## Local model download (started 2026-08-05)

- The user requested the weights under `E:\llm_models` with resumable
  downloading, while continuing to defer deployment.
- Selected domestic source remains ModelScope repository
  `Eco-Tech/DeepSeek-V4-Flash-0731-w8a8`, pinned to immutable revision
  `9e8679a9db7eec11efed9925f7efb96549077545`.
- Download directory:
  `E:\llm_models\DeepSeek-V4-Flash-0731-w8a8`.
- E: reported 444.18 GiB free before download; expected repository payload is
  314,724,356,065 bytes (about 293.11 GiB), so capacity preflight passed.
- Downloader uses two jobs, `.part` files, HTTP Range resume, exact file sizes,
  and ModelScope-provided per-file SHA-256 verification. Four of 74 weight
  shards had completed and shards 5/6 were actively growing at the 10:27
  checkpoint.
- Two downloader fixes were made after live validation on Windows Python 3.8
  and the ModelScope CDN: removed the unsupported `Path.write_text(newline=)`
  argument, and added a finite 16 MiB Range seed for new large files before
  automatic resume. Non-zero `.part` continuation was demonstrated by shards
  3/4 completing without restarting from zero.
- Active download command uses
  `deepseekv4-flash/offline-dsv4-0731/scripts/download_model.py --jobs 2`.
  If interrupted, rerun the same command with the same output directory.
- The no-weights control archive was rebuilt with the corrected downloader.
  New archive size: 10,321 bytes. New archive SHA-256:
  `634a946a54ec465010936cb74a1e2838db53d2d4711975d3d10bb1ac7ed3c572`.
- The verified download was moved to a detached hidden background process so
  it continues after the agent tool cell ends. Background Python PID at launch:
  `32148`; two curl workers were active.
- Progress logs are persistent in the model directory:
  `download.log` for downloader milestones and `download.err.log` for curl
  transfer progress. At the 10:32 checkpoint, shards 1-4 were fully verified;
  shards 5/6 were resuming at about 8-9 MiB/s per worker.

## Download completion (2026-08-05)

- The detached downloader completed all 85 pinned repository files under
  `E:\llm_models\DeepSeek-V4-Flash-0731-w8a8`.
- All 74 weight shards and metadata files passed the ModelScope-provided
  per-file SHA-256 checks. `download.log` ends with
  `All pinned files downloaded and SHA-256 verified.` and the completion marker
  was written.
- Deployment remains deferred; no target-side action was performed.

## ARM64 image clarification (2026-08-06)

- The pinned vLLM Ascend OCI index includes a ready-made linux/arm64 image at
  manifest `sha256:8dd01aa0e0e5c4b04d3d715f483351af24c626c30373215e74238cf389fc2a93`.
- This proves ARM64 image availability, not successful DeepSeek V4 Flash 0731
  operation on Ascend A2/910B4. The checkpoint's own best-practice metadata
  lists only `vLLM-Ascend` plus `Atlas_A3_Inference` as verified.
- Treat the ARM64 image as the preferred target-side candidate. Do not label it
  as 910B4-validated until diagnose, full model load, first-token generation,
  tool calling, and stability tests pass on the target server.
- User confirmed the on-site server is ARM64 and asked whether an already
  validated ARM image exists. Final answer: use the pinned ARM64 manifest as
  the candidate, but no public evidence currently validates the exact 0731
  W8A8 checkpoint plus 8x Ascend 910B4 combination.
- The existing 6,569,105,408-byte package image tar is linux/amd64 and must not
  be sent to or loaded on the ARM64 site. Model weights are architecture-neutral
  and do not need to be downloaded or converted again.

## ARM64 离线包脚本更新 (2026-08-06)

本环境的 Docker daemon 无法启动（WSL `E_ACCESSDENIED`，沙箱限制）且网络
被限制（DaoCloud 域名不可解析），因此无法在此环境直接拉取或保存 ARM64
镜像 tar。改为更新离线包脚本与文档，使目标 ARM64 服务器可自行生成
ARM64 镜像 tar。

### 变更清单

- 新增 `scripts/pull-arm64-image.sh`：在目标 ARM64 服务器上运行，从
  DaoCloud 国内代理拉取固定 ARM64 manifest
  (`sha256:8dd01aa0e0e5c4b04d3d715f483351af24c626c30373215e74238cf389fc2a93`)，
  校验架构为 `linux/arm64`，`docker save` 成 tar 并输出 SHA-256。
- 更新 `start.sh`：架构从硬编码 `amd64` 改为 `ARCH` 环境变量参数化
  （默认 `arm64`）；`IMAGE`、`IMAGE_TAR`、`cmd_load` 架构校验和
  `cmd_pull`（新增 `--platform linux/${ARCH}`）均跟随 `ARCH`。
- 更新 `README.md`：离线镜像章节改为 ARM64；新增 `pull-arm64-image.sh`
  使用步骤；默认参数表新增 `ARCH` 行。
- 更新 `MODEL-SOURCE.md`：离线镜像文件章节改为 ARM64 路径与 manifest
  digest，注明 amd64 tar 仅供排障。
- 更新 `PACKAGE-SHA256SUMS`：新增 ARM64 tar 占位行、pull-arm64-image.sh
  条目；更新 start.sh/README.md/MODEL-SOURCE.md 的 SHA-256；保留 amd64
  tar 记录并标注不能在 ARM64 目标机使用。

### 验证状态

- 三个 bash 脚本的结构检查通过（函数/case/if/fi/大括号匹配）。
- 因 WSL 和 Docker 均不可用，未执行 `bash -n` 或实际 docker 操作。
- `run-server.sh` 已同时覆盖 aarch64 和 x86_64 的 jemalloc 路径，无需
  修改。

### 待目标机执行

1. 将更新后的 `offline-dsv4-0731` 包复制到目标 ARM64 服务器。
2. 运行 `bash scripts/pull-arm64-image.sh` 生成 ARM64 tar。
3. 将脚本输出的 SHA-256 写入 `PACKAGE-SHA256SUMS` 的占位行。
4. 运行 `./start.sh load` → `verify` → `preflight` → `diagnose` →
   `start` → `test` 完成完整验收。
5. 若目标机无法联网，可直接在目标机执行 `./start.sh pull` 在线拉取
   固定 ARM64 manifest（已添加 `--platform linux/arm64`）。
## Next action

在目标 ARM64 服务器上执行 `scripts/pull-arm64-image.sh` 生成 ARM64 镜像
tar，填入 `PACKAGE-SHA256SUMS`，然后完成 `load` → `verify` → `preflight`
→ `diagnose` → `start` → `test` 全流程验收。本环境因 Docker/WSL 不可用，
无法预先生成或验证 ARM64 tar。

## A100 compatibility clarification (2026-08-06)

- User asked whether this DeepSeek package can deploy on NVIDIA A100.
- Current package is Ascend-only: W8A8 Ascend checkpoint, vLLM-Ascend image,
  torch_npu/CANN runtime, TP8+EP NPU launch flags. It cannot run on A100/CUDA
  unchanged, and the ARM64 image is also not an A100 image.
- A100 would require a separate NVIDIA CUDA checkpoint/runtime path. Ampere A100
  lacks native FP8/FP4 support, while the official NVIDIA-oriented 0731 weights
  use FP8/FP4 and DeepSeek V4 sparse kernels are not documented as A100-ready;
  therefore no validated A100 deployment is currently available.

## Current handoff: ARM64 image complete and split (2026-08-06)

### Local model identity

- Model directory: `E:\llm_models\DeepSeek-V4-Flash-0731-w8a8`.
- Source: `Eco-Tech/DeepSeek-V4-Flash-0731-w8a8`.
- Immutable revision: `9e8679a9db7eec11efed9925f7efb96549077545`.
- The revision corresponds to the 2026-07-31 official `DeepSeek-V4-Flash-0731`
  release converted to Ascend W8A8; the ModelScope conversion commit time is
  2026-08-01 11:12:48 +08:00.
- Local verification passed: 85 files, 74 shards, model architecture
  `DeepseekV4ForCausalLM`, model type `deepseek_v4`, one MTP layer and DSpark
  target layers `[40, 41, 42]`.
- This is an Ascend W8A8 conversion, not the original NVIDIA FP4/FP8 checkpoint.

### ARM64 image archive

- Fixed multi-arch OCI index:
  `sha256:ade04e75aa4a888df5dfb7917f21e7d9178014d5f5e52b358f2cd1d8897f46ce`.
- Fixed ARM64 manifest:
  `sha256:8dd01aa0e0e5c4b04d3d715f483351af24c626c30373215e74238cf389fc2a93`.
- Final archive:
  `deepseekv4-flash/offline-dsv4-0731/images/vllm-ascend-nightly-main-20260804-arm64.tar`.
- Archive size: `6364067840` bytes.
- Archive SHA-256:
  `57bbe948bec21654eebdcdfe9bbbc939c6054ba40592d75f8b6ee73403c557a1`.
- Independent offline verification passed: 18 blobs, manifest digest matches,
  config reports `linux/arm64`.
- The temporary OCI download stage was removed after assembly; the original tar
  remains on D:.

### 4.7G-disc split

- `images/vllm-ascend-nightly-main-20260804-arm64.tar.part01`: 4,600,000,000
  bytes; SHA-256 `d91971ee17073c783463e991e73cc9cd2b189c9162ccecb222fbbd418ff651bf`.
- `images/vllm-ascend-nightly-main-20260804-arm64.tar.part02`: 1,764,067,840
  bytes; SHA-256 `95583f88dd6035f98132eb7e4ef69848df74850ea58bd0b6524bd1ebabef47c1`.
- Concatenating `.part01` then `.part02` reconstructs the original tar exactly.
- Split instructions and hashes are in
  `images/vllm-ascend-nightly-main-20260804-arm64.tar.parts.sha256.txt`.

### Pending target-side work

1. Copy both split files to the target ARM64 server.
2. Verify each part SHA-256 and concatenate in numeric order.
3. Verify the reconstructed tar SHA-256 against the original hash above.
4. Run `docker load`, then `./start.sh load`, `verify`, `preflight`, `diagnose`,
   `start`, and `test` on the target server.
5. Do not call the deployment 910B4-validated until full model load, first-token,
   tool-call and stability tests pass.

### Host safety state

- Local Docker data remains in the C: WSL VHD; no local `docker load` was run for
  this large ARM64 tar.
- C: free space was about 31.84 GB during final work; D: retained the archive and
  split files. No VHDX resize, relocation, compaction, or deletion was performed.
- No A100 image or NVIDIA weight download was performed; the A100 request was
  canceled by the user.

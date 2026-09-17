# kty5l / GLM-5.2 deployment memory

Last updated: 2026-08-05 17:25 (Asia/Shanghai)

## Clean-v2 rebuild resumed (2026-08-05)

- The latest retry fixed CRLF-normalized patch application and vendored exact
  CUTLASS `v4.4.2` from the verified GitCode domestic mirror. The A100 native
  wheel built successfully, but strict `pip check` rejected two base-image
  dependency defects. The recipe now pins `pycairo==1.28.0` and
  `nixl-cu12==1.2.0`; it has not been rebuilt with those corrections.
- New user-mandated rules prohibit large Docker operations while Docker data
  remains on C and prohibit any VHDX modification. The build is stopped; C
  free space is 55.40 GiB, Docker VHDX is 104.39 GiB, no output image or
  independent validation marker exists, and both business containers are Up.
- The user later approved an itemized cleanup of old images, cache older than
  seven days, and 12 empty anonymous volumes. Docker now has 6 images and 9
  volumes; both business containers, exact GLM/CUDA bases and recent native
  build cache remain. C free space and VHDX size stayed at 61.66 GiB and
  104.39 GiB respectively; no VHDX operation was performed.
- The user then revoked the build prohibition but required C-drive monitoring.
  A cache-resume build was attempted with a 52 GiB stop line; cache invalidation
  caused Torch layers to rebuild, and the build was stopped after a detached
  buildx process drove C free space to 44.99 GiB. Docker VHDX is now 109.49 GiB.
  The transient aborted-build cache was pruned; the 6.348 GiB native compile
  cache, base images and both business containers remain. No output image or
  validation marker exists. Do not resume until C space is restored.

- Docker Desktop was restored and the retained BuildKit cache was confirmed at
  7.873 GB; it was not pruned.
- The verified `docker.1panel.live/nvidia/cuda:12.8.1-devel-ubuntu22.04`
  domestic-mirror pull is active. The clean-v2 build has not started yet and
  no new image/tar has been produced.
- The mirror's largest 2.989 GB amd64 layer was directly confirmed available
  with the expected digest, but streamed at only about 0.59 MiB/s and ignored
  Range. Keep the active pull; a long quiet period is expected.
- The pull completed successfully, and the clean-v2 build is now running as
  BuildKit ID `q8vphw5bt0nwj3fdx6rx6jst7`. No new image/tar exists until that
  build and the independent validation finish.
- That first build failed before compilation when `ghfast.top` refused the
  fixed source fetch. The recipe was corrected to use a hashed Gitee v0.24.0
  source archive plus the hashed locally preserved PR-compatible patch, with no
  Git network access inside the build. Corrected build ID
  `t195rz5u514evfcq02vbm4ibn` is running; independent validation is queued.
- The corrected build later failed during pip installation with a Docker
  backend EOF; no image was produced. Docker's data VHDX was confirmed to still
  reside on C: and had regrown from about 64.96 GiB to 155.07 GiB, leaving only
  about 11.02 GiB free. Docker Desktop is stopped. Do not restart the build
  until Docker data is relocated or scoped cleanup/compaction is authorized.
- Scoped cleanup removed two stopped containers and the old GLM/MinIO/MySQL
  images, reducing logical image usage by about 34 GB. The VHDX remains about
  155.10 GiB; host C: space will not return until Docker/WSL are stopped and the
  VHDX is compacted. Two unrelated active containers were preserved.
- The user then authorized removing all BladeAI-namespace images. Fourteen tags
  were deleted, reducing logical image usage further to 79.68 GB. Both active
  deploy containers remain up; the VHDX still needs compaction to return host
  C: space.
- The floating cu129 base image `6b005c78cd17` was removed while exact GLM base
  `4fab2d06cb38` was preserved. After ext4 fstrim and offline DiskPart compact,
  Docker VHDX shrank from 155.08 GiB to 83.17 GiB and C: free space rose to
  about 83.15 GiB. Docker and both deploy containers are running again. The
  dynamic VHDX can regrow; no cap or relocation was configured.

## Clean-v2 rebuild paused (2026-07-31)

- Latest on-site evidence confirms a real user-space near-null segfault during
  GLM/AWQ model-load start after all eight GPUs initialized. The container
  exited 1, was not OOM-killed, and the complete normalized artifact manifest
  passed (only non-runtime README/run.sh changed).
- BuildKit history exposed an important defect in the prior native image: its
  unrestricted PyTorch replacement installed resolver-incompatible numpy,
  cuda-bindings, and cuda-pathfinder versions, then exported the image anyway.
- A clean, pinned, sm_80-only rebuild recipe and strict native-library checks
  are saved under `kty5l/build-glm52-vllm-cu128/`.
- Three domestic CUDA mirrors were verified to expose the same exact linux/amd64
  manifest `sha256:6617a625f4090c76c545a0e7d63f2e441718ef9af7f4efe7dd1242a29e289fd7`.
  DaoCloud returned a truncated 2.99GB blob; 1ms did not complete within two
  hours; the 1Panel pull was explicitly stopped by the user.
- Task is paused. Retain the 7.075GB BuildKit cache and consult
  `.agents/tasks/kty5l-glm52-vllm-rebuild/MEMORY.md` before resuming. No new
  image/tar was produced and the existing offline package remains unchanged.

## Simplified final package (2026-07-26)

- `offline-glm52/` now follows the accepted XT deployment-package pattern.
  Its root contains only `README.md`, `start.sh`, `images/`, and `models/`.
- Only the preferred native cu128 A100 image remains. The optional cu129
  compatibility archive and sidecar were removed, reclaiming about 11.29 GiB.
- Build/download/recon/system-install/patch helpers and the Qwen diagnostic
  placeholder were removed from the final deployment package.
- `start.sh` now uses package-relative image/model paths and only exposes
  `load`, `start`, `logs`, `test`, and `stop`.
- The model directory is mounted read-only. Default launch is TP=8, 32K,
  16 sequences, utilization 0.90, `TRITON_MLA_SPARSE`, prefix caching,
  chunked prefill, and GLM tool/reasoning parsers. Context, concurrency, GPU
  selection, port, utilization, and P2P fallback remain environment overrides.
- Structural/reference/UTF-8/LF checks and WSL `bash -n` passed. The selected
  image archive had already been fully hashed and was not redundantly rehashed.
- Tool-calling launch configuration was rechecked after simplification:
  `--enable-auto-tool-choice`, `--tool-call-parser glm47`, and
  `--reasoning-parser glm45` are all present in `start.sh`. This confirms the
  feature is enabled statically; a real request with `tools` and
  `tool_choice: "auto"` is still required after target-side model startup.

## Incident and root cause

- Target server: 8x NVIDIA A100 80GB PCIe, host driver `570.124.06`.
- `nvidia-smi` reports CUDA 12.8 capability on the host.
- The original `glm52-vllm:0.24.0-pr38476` image installed
  `torch 2.11.0+cu130`; therefore PyTorch CUDA initialization returned false.
- A CUDA 12.8 base image alone did not constrain pip: vLLM's precompiled flow
  fell back to cu130.

## Preferred on-site fallback

- Image tag: `glm52-vllm:0.24.0-pr38476-cu128-native-r570-a100`.
- Offline tar:
  `offline-glm52/images/glm52-vllm-0.24.0-pr38476-cu128-native-r570-a100.tar`.
- Tar size: 15.23 GiB.
- SHA-256:
  `b0afdbfb6c04807dd33238fd19b32f2158353fbec62787015afd0a0c564d5d11`.
- Sidecar checksum file is next to the tar with suffix `.tar.sha256`.
- Runtime stack: `torch 2.11.0+cu128`, torch CUDA 12.8,
  `vLLM 0.24.1.dev0 + PR #38476`.
- Native CUDA extensions were source-built only for A100 `sm_80`.
- Included native extensions: stable-libtorch, MoE, FA2, cumem allocator.
- Excluded: cu129/cu130 binaries, cuda-compat, FA3, DeepGEMM/Qutlass,
  FlashMLA.
- `cuobjdump` confirmed the stable-libtorch cubins are `sm_80` only.
- `TRITON_MLA_SPARSE` is registered and is the required GLM attention backend.

## On-site dependency policy

- Do not change the target host unless validation proves it necessary.
- Existing driver `570.124.06` is the intended driver for the native cu128 image.
- Required host components: Docker and NVIDIA Container Toolkit.
- Host CUDA Toolkit is not required and must not be installed just for this image.
- The native cu128 image does not use `cuda-compat`.

## On-site validation

From the copied simplified package:

```bash
cd /offline-glm52
./start.sh load
./start.sh start
./start.sh logs
./start.sh test
```

- Full runtime acceptance still must pass on the Linux 8x A100 server: all
  eight A100 devices, native libcuda loading, Triton PTX JIT, model load, the
  required fallback log lines, and the OpenAI-compatible API test.

## Build source policy

- Prefer verified domestic mirrors for every external download.
- Verified PyTorch cu128 mirror:
  `https://mirrors.nju.edu.cn/pytorch/whl/cu128`.
- Shanghai Jiao Tong mirror also had `torch 2.11.0+cu128` at verification time:
  `https://mirror.sjtu.edu.cn/pytorch-wheels/cu128`.
- The tested Aliyun PyTorch cu128 path did not contain the required wheel.
- GitHub build dependencies were routed through `https://ghfast.top/`.
- Use an official overseas source only after verified domestic sources are absent
  or fail, and tell the user before doing so.

## Removed optional compatibility image

- The former cu129 + `cuda-compat-12-9` alternative tar was removed from the
  final package during simplification:
  `glm52-vllm-0.24.0-pr38476-cu129-compat570.tar`.
- Its historical SHA-256 was
  `d1b10571b10f87d06abebb1468f021441647ab126bb0cdc14ff5ca7f16c2d1b1`.
- Rebuild or restore it only if a future target host cannot use the preferred
  native cu128 image.

## Local Docker cleanup state

- All `glm52-vllm` images were removed from Docker Desktop after exporting tar
  files; the tar files on D: were preserved.
- Unused Docker build cache was pruned to 0B.
- Docker VHDX was trimmed and compacted from about 152.38GB to 64.96GB.
- C: free space increased from 16.38GB to 106.13GB.
- Docker Desktop was restarted and verified operational.

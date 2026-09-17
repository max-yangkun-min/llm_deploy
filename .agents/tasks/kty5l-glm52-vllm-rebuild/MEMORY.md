# kty5l GLM-5.2 vLLM image rebuild

Status: paused; C drive below safe threshold after aborted cache-resume build
Last updated: 2026-08-05 18:05 (Asia/Shanghai)

## Objective

Rebuild the kty5l GLM-5.2 vLLM image using the latest on-site feedback from
the 8x NVIDIA A100 80GB PCIe server (driver 570.124.06), produce a reproducible
offline image archive, and update the simplified deployment package.

## Latest clean-v2 retry (2026-08-05 17:25)

- BuildKit build `60d1edtvzt0kdcmphfqg9mj4d` completed the native A100
  `sm_80` wheel after about 66.8 minutes. Wheel size was 247,114,169 bytes;
  build-reported SHA-256 was
  `2b904eae07e5bb34867656169a582f591593845173f0d853fdfcddfadcecdc56`.
- Fixed deterministic CRLF normalization with Git `core.autocrlf=input`.
  Strict PR #38476 patch checking then passed: 11 files changed, 1,677
  insertions and 9 deletions.
- Verified domestic GitCode CUTLASS mirror tag `v4.4.2` at commit
  `da5e086dab31d63815acafdac9a9c5893b1c69e2`; the build now uses its hashed
  offline archive and no longer contacts GitHub.
- The wheel installed, but strict `pip check` stopped the build because the
  base image lacked `pycairo` for `PyGObject 3.42.1`, and paired `nixl 1.2.0`
  with incompatible `nixl-cu12 1.3.0`.
- The recipe now pins verified domestic-mirror artifacts `pycairo==1.28.0`
  and `nixl-cu12==1.2.0`; this correction has not been Docker-tested.
- No output image or independent validation marker exists.
- New mandatory storage rules prohibit large Docker builds while Docker data
  is on C. Confirmed path:
  `C:\Users\11984\AppData\Local\Docker\wsl\disk\docker_data.vhdx`.
  VHDX size was 104.39 GiB and C free space was 55.40 GiB after build exit.
  Do not resize, relocate, compact or otherwise modify the VHDX.
- Both preserved business containers remain Up. No image, container, volume,
  cache or VHDX was deleted during the stop.
- Next action: do not resume Docker building unless the storage rule is
  explicitly changed or Docker data is independently no longer on C. Then
  rerun the corrected cached build and require strict validation before export.

## Approved scoped cleanup (2026-08-05 17:40)

- The user explicitly approved cleanup groups 1, 2 and 3 from the itemized
  inventory: named old images, BuildKit records older than seven days, and 12
  verified `0B` unmounted anonymous volumes.
- Removed 15 old image tags representing 13 unique images: RL Studio v6/v7 and
  two 2024 images, two model-registry images, Gitea, MySQL 8.0, Nexus 3.91.0,
  nginx 1.21.3, Ubuntu 20.04, Python 3.8-slim and Alpine 3.20.
- `docker builder prune --filter until=168h` released 260.7 MB. It preserved
  the recent GLM native-build records, including the 6.348 GB wheel-build layer.
- Removed exactly 12 approved unmounted anonymous volumes, all reported as 0B.
- Docker inventory fell from 19 to 6 images and from 21 to 9 local volumes.
  Both business containers remain Up. Exact GLM base `4fab2d06cb38` and CUDA
  base `a99a1860ba8e` remain present.
- C free space was 61.66 GiB before and after cleanup. The Docker VHDX remained
  104.39 GiB because deletions do not physically shrink a dynamic VHDX.
  No VHDX compaction, resize, relocation or other modification was performed.

## Cache-resume attempt and stop (2026-08-05 18:05)

- User explicitly revoked the prohibition on large Docker builds with Docker
  data on C, while retaining the requirement to monitor C space and avoid
  filling it. A 52 GiB hard stop was set.
- The Dockerfile was changed so `pycairo==1.28.0` and `nixl-cu12==1.2.0`
  install after the expensive native wheel layer, intending to reuse the
  successful 6.348 GiB A100 native compile cache.
- Static check passed. Cache-resume build started as BuildKit record
  `ar8xlzbuw7ypvkeyo2oeo9qwb`.
- The expected cache did not match because the preceding dependency layer
  changed. The build began downloading/reinstalling Torch again and grew the
  Docker VHDX rapidly. The build client was stopped at C free 50.08 GiB, but
  a detached `docker-buildx.exe` continued briefly and was then stopped.
- Final measured state: C free **44.99 GiB**; Docker VHDX
  `C:\Users\11984\AppData\Local\Docker\wsl\disk\docker_data.vhdx`
  **109.49 GiB**. This is below the 50 GiB preservation target.
- The transient cache created by the aborted attempt was pruned with
  `docker buildx prune --filter until=2m`; the preserved native compile cache
  `qtc6c37h4iqqsasdth3yflhs5` remains **6.348 GiB**. No image was produced and
  no independent validation marker exists.
- Both business containers remain Up. No VHDX resize, relocation, compaction,
  or image deletion was performed in this attempt.
- Do not restart Docker build until C free space is restored above the agreed
  threshold. Next technical action, after space recovery, is to fix cache
  invalidation or use an explicit external cache/export strategy; do not
  assume the 6.348 GiB record will match after Dockerfile edits.

## Prior image

- Tag: `glm52-vllm:0.24.0-pr38476-cu128-native-r570-a100`
- Stack: torch 2.11.0+cu128 and vLLM 0.24.1.dev0 plus PR #38476
- Archive SHA-256: `b0afdbfb6c04807dd33238fd19b32f2158353fbec62787015afd0a0c564d5d11`
- The prior image source-built A100 sm_80 native extensions and used
  `TRITON_MLA_SPARSE`.

## Public validation and image audit (2026-08-05)

- Official vLLM Recipes currently documents Docker tags
  `vllm/vllm-openai:glm52` and `glm52-cu129`, but its GLM-5.2 recipe targets
  the FP8 checkpoint on 8x H200/H20. The hardware UI does not list A100 and
  marks other hardware (for example B200/B300) as end-to-end verified. These
  official tags must not be represented as verified A100/AWQ images.
- The previously referenced community record by `timinar` was successfully
  retrieved through the already-used `ghfast.top` proxy. It gives an
  independent successful **8x A100 80GB** validation of
  `cyankiwi/GLM-5.2-AWQ-INT4` with vLLM main plus PR #38476. Reported proof
  includes coherent output, about 56 decode tok/s single-stream and 625
  aggregate decode tok/s at concurrency 32, using TP8, 32K context, bf16 KV,
  and `TRITON_MLA_SPARSE` plus the Triton indexer fallback.
- That public record describes patching/installing a recent vLLM stack and
  does **not** publish or identify a reproducible prebuilt image digest. It is
  proof that the software path works on A100, not proof of a ready-to-download
  image suitable for driver 570.124.06.
- Therefore no publicly downloadable image has yet been verified for the exact
  target combination: 8x A100 80GB PCIe, driver 570.124.06, and
  GLM-5.2-AWQ-INT4. The prior local cu128-native archive also cannot fill that
  role because it segfaulted during target-side model loading.

## Build attempt after VHDX compaction (2026-08-05 22:00-23:00)

- User requested: build GLM-5.2, validate internally, save the image locally,
  then delete only the task image from Docker.
- Before building, Docker/WSL were stopped and the already-authorized offline
  trim/compact procedure was run. The Docker VHDX shrank from **129.78 GiB**
  to **100.79 GiB**; C: free space rose from **38.06 GiB** to **67.06 GiB**.
  The two `unless-stopped` business containers were restored and are Up. No
  image, cache, volume, VHDX capacity, location, or size limit was modified.
- A controlled cache probe revealed that the prior 6.348 GiB native compile
  layer exists but its parent chain does not reliably match the current
  Dockerfile; the earlier cache-resume therefore restarted Torch downloads.
  The probe itself produced no image and was stopped without a storage event.
- To avoid repeating the native compile, the preserved 15.23 GiB offline
  `glm52-vllm:0.24.0-pr38476-cu128-native-r570-a100` tar was loaded from D:.
  Loading succeeded and restored image ID
  `sha256:19adf8c4f7fc4a9852f2ae74fcdea1705237d6369c2b003f16040f61a8511e13`;
  C: free became **34.85 GiB**.
- A low-cost derived Dockerfile was attempted, adding only `pycairo==1.28.0`
  and `nixl-cu12==1.2.0`, then running strict `pip check` and native verifier.
  The build did not redownload Torch or compile CUDA extensions, but failed
  before producing an image because the loaded base has a mixed CUDA Python
  dependency stack:
  `cuda-core 1.0.1` requires `cuda-pathfinder>=1.4.2` (base has 1.2.2),
  `cuda-python 13.3.1` requires `cuda-bindings~=13.3.1` (base has 12.9.4),
  and `mistral-common` requires `numpy<2.4` (base has 2.4.4).
- No derived image was generated, no tar was exported, and no task image was
  deleted. Both business containers remain Up. C: free after the failed build
  is **34.26 GiB**. Do not start another large operation until a complete,
  resolver-consistent CUDA Python version set is pinned; do not claim the old
  base tar is validated for target runtime.

## Public validation and image audit (2026-08-05)

- Official vLLM Recipes currently documents Docker tags
  `vllm/vllm-openai:glm52` and `glm52-cu129`, but its GLM-5.2 recipe targets
  the FP8 checkpoint on 8x H200/H20. The hardware UI does not list A100 and
  marks other hardware (for example B200/B300) as end-to-end verified. These
  official tags must not be represented as verified A100/AWQ images.
- The previously referenced community record by `timinar` was successfully
  retrieved through the already-used `ghfast.top` proxy. It gives an
  independent successful **8x A100 80GB** validation of
  `cyankiwi/GLM-5.2-AWQ-INT4` with vLLM main plus PR #38476. Reported proof
  includes coherent output, about 56 decode tok/s single-stream and 625
  aggregate decode tok/s at concurrency 32, using TP8, 32K context, bf16 KV,
  and `TRITON_MLA_SPARSE` plus the Triton indexer fallback.
- That public record describes patching/installing a recent vLLM stack and
  does **not** publish or identify a reproducible prebuilt image digest. It is
  proof that the software path works on A100, not proof of a ready-to-download
  image suitable for driver 570.124.06.
- Therefore no publicly downloadable image has yet been verified for the exact
  target combination: 8x A100 80GB PCIe, driver 570.124.06, and
  GLM-5.2-AWQ-INT4. The prior local cu128-native archive also cannot fill that
  role because it segfaulted during target-side model loading.

## Latest on-site feedback

- The container exits with code 1 and `OOMKilled=false`.
- Host kernel reports `uvicorn[8574]: segfault at 28 ... error 4 in python3.11`.
- The model present on site is `GLM-5.2-AWQ-INT4`, containing 83 safetensor
  shards. The screenshot does not include the preceding vLLM log or Python
  stack, so the exact native component that faulted is not yet established.
- Two earlier screenshots show a CRLF-contaminated `MANIFEST.sha256` and two
  expected checksum mismatches after `README.md` and `scripts/run.sh` were
  changed. The current simplified package no longer includes that manifest or
  `scripts/run.sh`; these are packaging issues distinct from the segfault.

## Download policy

Verify exact artifacts on domestic China mirrors first. Existing verified
PyTorch cu128 mirror: `https://mirrors.nju.edu.cn/pytorch/whl/cu128`; verified
secondary mirror: `https://mirror.sjtu.edu.cn/pytorch-wheels/cu128`. GitHub
source dependencies previously used `https://ghfast.top/`.

## Next action

Do nothing until the user resumes this task. On resume, do not repeat the
on-site diagnosis, dependency-conflict audit, source/tag/PR verification, or
Dockerfile creation. First inspect the retained 7.075GB BuildKit cache and then
choose between continuing the verified third domestic CUDA mirror or revising
the recipe to obtain only the CUDA 12.8 compiler components from the verified
NJU Python index. After the base/toolchain is complete, run the existing
`kty5l/build-glm52-vllm-cu128/build.ps1` recipe, validate independently, export
the tar, hash it, and only then update the simplified offline package.

## Rebuild progress (2026-07-31)

- Recovered the prior native build from BuildKit history. Its PyTorch
  replacement step reported incompatible numpy, cuda-bindings, and
  cuda-pathfinder packages but still exported the image; this mixed dependency
  stack is the primary rebuild target.
- Verified domestic artifacts: vLLM base commit/tag, PR #38476 head, DaoCloud
  base manifests, NJU torch/vision/audio cu128 wheels, and ghfast source refs.
- Added reproducible recipe under `kty5l/build-glm52-vllm-cu128/`.
- First build attempt failed before any image mutation or compilation because
  DaoCloud's 2.99GB CUDA layer was truncated (`short read`, `unexpected EOF`).
- Verified `docker.1ms.run` exposes the identical CUDA linux/amd64 manifest
  `sha256:6617a625f4090c76c545a0e7d63f2e441718ef9af7f4efe7dd1242a29e289fd7`
  and selected it as the second domestic mirror, but a standalone pull timed
  out after two hours without completing or reporting a digest/content error.
- Verified third domestic mirror `docker.1panel.live` exposes the same exact
  linux/amd64 manifest digest. Docker retains about 7.075GB of build cache, so
  already completed layers should be reusable across the identical manifests.

## Stop state (2026-07-31 23:08)

- The user explicitly requested: stop and save progress.
- The active `docker pull docker.1panel.live/nvidia/cuda:12.8.1-devel-ubuntu22.04`
  was terminated immediately. No download or Docker build remains running for
  this task.
- No `nvidia/cuda` or `glm52-vllm` image is currently tagged locally.
- Docker accounting after stop: 40 images, 87.56GB; BuildKit cache 117 records,
  7.075GB, all inactive/reclaimable. Do not prune this cache before resuming.
- Recorded failed build ID: `zmhxdkys03djjj2xdesejqcqr`, duration 76m45s;
  failure occurred at CUDA layer copy after DaoCloud returned a truncated blob.
- Reproducible sources are preserved in
  `kty5l/build-glm52-vllm-cu128/`: `Dockerfile`, `build.ps1`,
  `patch_setup_sm80.py`, `verify_stack.py`, and `BUILD-SOURCES.md`.
- The final image, tar archive, SHA-256 sidecar, and offline-package switch have
  not been produced. `kty5l/offline-glm52/start.sh` still points to the prior
  cu128-native image/tar name and must not be changed until a new image passes.

## Resume state (2026-08-05 13:05)

- The user resumed the GLM-5.2 clean-v2 rebuild. The concurrent DeepSeek model
  download on E: remains healthy and was not stopped.
- Docker Desktop was initially stopped, then started successfully. Docker
  Engine 28.4.0 is running with the overlayfs storage driver.
- Retained BuildKit cache is present and larger than the stop checkpoint:
  150 records / 7.873 GB private cache. It was not pruned.
- D: had 188,878,450,688 bytes free (about 175.9 GiB) before resuming the base
  pull.
- Resumed `docker pull` from the already verified third domestic mirror:
  `docker.1panel.live/nvidia/cuda:12.8.1-devel-ubuntu22.04`. The Dockerfile pins
  its linux/amd64 manifest digest to
  `sha256:6617a625f4090c76c545a0e7d63f2e441718ef9af7f4efe7dd1242a29e289fd7`.
- Pull CLI PID at the checkpoint was 37048 and remained active. No CUDA or new
  GLM image tag existed yet; do not start the build until the pull completes
  and the platform digest is confirmed.
- Direct diagnostic of the largest amd64 layer
  `sha256:6b2035e8b73ed2b018995a7b2c8d607d5527daf948d41964f02cc3ce7ed0699a`
  confirmed an exact `Content-Length` of 2,989,040,412 bytes and matching
  `docker-content-digest`. The mirror is serving the blob, but it ignored a
  1 MiB Range request (HTTP 200) and streamed about 0.59 MiB/s; the diagnostic
  intentionally discarded 37,221,900 bytes after a 60-second timeout.
- This throughput implies roughly 80 minutes for the largest layer and explains
  the long quiet pull. PID 37048 was still responsive at 13:25. Preserve this
  pull rather than restarting it; the build remains pending.
- The CUDA base pull later completed successfully. Docker reported multi-arch
  index digest
  `sha256:a99a1860ba8e2916e5c3e73b72ec4c4301653a84586e05bfc9a2aa2d58027e97`;
  local inspection reports `linux/amd64`. The Dockerfile continues to pin the
  exact amd64 platform manifest
  `sha256:6617a625f4090c76c545a0e7d63f2e441718ef9af7f4efe7dd1242a29e289fd7`.
- Added `resume-after-base-pull.ps1` to verify the local index/platform and
  automatically start the existing build recipe. Windows PowerShell 5 native
  stderr handling and Docker Desktop containerd's index-as-image-ID behavior
  were both corrected after conservative test exits; neither test exit started
  a build or changed an image.
- Clean-v2 build started at 13:52:12 with BuildKit ID
  `q8vphw5bt0nwj3fdx6rx6jst7`, output tag
  `glm52-vllm:0.24.0-pr38476-cu128-clean-r570-a100-v2`, `MAX_JOBS=8`, and
  `NVCC_THREADS=2`. Background orchestrator PID at start: 33948.

## First resumed build failure and offline-source correction (2026-08-05)

- Build `q8vphw5bt0nwj3fdx6rx6jst7` failed after 8m42s at Dockerfile step 7/14,
  before compilation, because `ghfast.top:443` refused the fixed vLLM Git
  fetch. No output image was produced, so validation was correctly not run.
- The Gitee domestic mirror `https://gitee.com/mirrors/vllm.git` was verified to
  advertise tag `v0.24.0` at exact commit
  `ee0da84ab9e04ac7610e28580af62c365e898389`. It does not expose the unmerged
  PR head and returned `not our ref` for
  `3740c02bb1223d37823593664ae3eafa397b9937`.
- Loaded the already-hashed prior image tar locally and recovered its preserved
  PR provenance patches. Host-side hashes match the historical records:
  compatible patch
  `f8e22e9df9b05b15bf0cbb5cb59e9ab61b7dd74b08c6484342b3da5d7603f31a`;
  original PR diff
  `9b6126e460a818806643b712f6f2f00764aabf3f0b82dbd75a184f10aa976a2b`.
- Generated a 37,197,449-byte Gitee tag archive
  `vllm-v0.24.0-ee0da84.tar.gz`, SHA-256
  `6bf9c64c848c06e2fd985f3051ccb65adc878cc7d0bb1f38f73090b8d952c5e1`.
- Dockerfile now verifies, extracts and patches these vendored artifacts. It no
  longer performs Git network access. A strict host-side `git apply --check`
  and `docker build --check` both passed.
- Added independent post-build validation scripts. They run `pip check`, the
  full native-library/import/backend verifier, exact source/PR markers,
  `cuobjdump` sm_80-only checks, and pip-freeze checks. Validation does not run
  until the image tag exists.
- Corrected build started as BuildKit ID `t195rz5u514evfcq02vbm4ibn` at 14:27.
  Background build orchestrator PID: 27536.
- Independent validator PID was restarted as 30052 after adding explicit
  build-process failure detection. It waits for the exact output tag, runs the
  checks, writes `INDEPENDENT-VALIDATION-PASSED.txt` only on success, and exits
  with an error if PID 27536 ends without producing the image.

## Corrected build failure and C-drive diagnosis (2026-08-05)

- Corrected build `t195rz5u514evfcq02vbm4ibn` passed the offline source/patch
  stage but failed at BuildKit step 11 during pip wheel installation with
  `error reading from server: EOF`. No clean-v2 image was produced and the
  independent validator did not run.
- Docker Desktop then stopped with a WSL VHDX unmount/exec error and currently
  reports `Status: stopped` / unable to start.
- Root cause of the user's C-drive exhaustion was confirmed: Docker data is
  still at
  `C:\Users\11984\AppData\Local\Docker\wsl\disk\docker_data.vhdx`, not D:.
- `docker_data.vhdx` is now 166,505,480,192 bytes (155.07 GiB), compared with
  about 64.96 GiB immediately after the previous compaction: approximately
  90.11 GiB of physical regrowth. The full Docker Local directory measures
  about 155.22 GiB.
- C: has only 11,832,438,784 bytes free (about 11.02 GiB). Root system files
  also include a 13,425,074,176-byte hibernation file and a 4,969,627,648-byte
  pagefile, but Docker VHDX regrowth is the new dominant cause.
- The regrowth followed loading the prior 15.23 GiB image tar, pulling the CUDA
  devel image, and creating large intermediate PyTorch/CUDA/pip BuildKit layers.
- Do not restart the build until the user authorizes either relocating Docker
  data off C: or a scoped image/cache cleanup and re-compaction. No cleanup or
  relocation has been performed.

## Scoped Docker cleanup (2026-08-05)

- The user authorized cleaning old images and containers. Docker Desktop was
  restarted only to perform the cleanup.
- Preserved the two running containers:
  `deploy-satellite-ew-analysis-1` and `deploy-cesium-mcp-1`.
- Removed the two containers that had been stopped for two weeks: `minio` and
  `mysql8`. Their named volumes were not removed.
- Removed only three clearly scoped image tags:
  `glm52-vllm:0.24.0-pr38476-cu128-native-r570-a100`, `minio:0.1.0`, and
  `mysql:8`. Preserved CUDA/vLLM build bases, all unrelated business/model
  images, all volumes, and BuildKit cache.
- Docker logical image usage fell from 146.3 GB to 112.3 GB (about 34 GB
  released inside the VHDX). Container count fell from four to two, both active.
- Physical `docker_data.vhdx` remains about 155.10 GiB and C: free space remains
  about 10.94 GiB because a dynamic VHDX does not shrink after internal deletes.
  Reclaiming host C: space requires stopping the two active containers/Docker,
  shutting down WSL, and compacting the VHDX; that service-impacting action has
  not been performed and requires user approval.

## BladeAI image cleanup (2026-08-05)

- The user explicitly requested deletion of Blade-related images. Confirmed
  neither active `deploy-*` container referenced the BladeAI namespace.
- Deleted all 14 local tags under
  `registry.cn-beijing.aliyuncs.com/bladeai/*`: three blade-agent versions,
  blade-sandbox, two blade-oauth versions, two blade-hub versions, blade-os,
  two llm-gateway versions, mock-center, nexus_index, and tile-proxy.
- A post-delete wildcard query returned no BladeAI images. Both active deploy
  containers remain up.
- Logical image usage fell again from 112.3 GB to 79.68 GB (about 32.62 GB
  released inside the VHDX). Combined with the prior scoped cleanup, logical
  image use fell from 146.3 GB to 79.68 GB.
- `docker_data.vhdx` remains 155.10 GiB; C: shows about 11.23 GiB free. Physical
  host space still requires Docker/WSL shutdown and VHDX compaction.

## VHDX trim and compaction (2026-08-05)

- The user authorized deleting image `6b005c78cd17`, compacting the Docker VHDX,
  and restoring at least 50 GiB free on C:.
- Removed both tags for `6b005c78cd17`: the 1ms and DaoCloud floating
  `v0.24.0-cu129` references. Preserved exact GLM build base
  `4fab2d06cb38` and the pinned CUDA 12.8.1 image.
- Recorded the two active containers' `unless-stopped` policy, stopped Docker
  Desktop, and shut down WSL. The containers experienced planned downtime.
- A first DiskPart compact made no size change because ext4 free blocks had not
  been discarded. Identified Docker data as `/dev/sde`, UUID
  `23887a14-14e9-4387-a499-eedea954b101`, mounted it without starting Docker,
  replayed the journal, ran `fstrim` (1,003.8 GiB reported trimmed), synced and
  unmounted it cleanly.
- After WSL shutdown, DiskPart compaction reduced `docker_data.vhdx` from
  166,511,771,648 bytes (155.08 GiB) to 89,306,169,344 bytes (83.17 GiB), a
  physical reduction of about 71.91 GiB.
- C: free space is now 89,278,820,352 bytes (about 83.15 GiB), exceeding the
  user's 50 GiB requirement.
- Docker Desktop was restarted. Because `docker desktop stop` left the two
  containers in a normal exited state, they were manually restarted and both
  are confirmed Up.
- Docker VHDX remains dynamic and will grow with future pulls/builds. No fixed
  allocation or maximum-size change was configured. A true long-term guarantee
  for C: requires relocating Docker data to D: or configuring a supported Docker
  Desktop disk-usage cap plus monitoring/periodic trim and compaction.

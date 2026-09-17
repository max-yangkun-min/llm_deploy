# GLM-5.2 vLLM cu128 clean-v2 build sources

All external sources are pinned and routed through verified domestic mirrors.

| Purpose | Selected mirror/artifact | Exact version or digest |
|---|---|---|
| CUDA devel base | `docker.1panel.live/nvidia/cuda` | `12.8.1-devel-ubuntu22.04`, linux/amd64 `sha256:6617a625f4090c76c545a0e7d63f2e441718ef9af7f4efe7dd1242a29e289fd7` |
| vLLM runtime dependency base | `docker.m.daocloud.io/vllm/vllm-openai` | `v0.24.0-cu129`, linux/amd64 `sha256:4fab2d06cb3898f00d46def116d5aff27b2388126993efc871fe2601c7df9742` |
| vLLM source | Gitee domestic mirror `https://gitee.com/mirrors/vllm.git`; vendored as `vllm-v0.24.0-ee0da84.tar.gz` | `v0.24.0` / `ee0da84ab9e04ac7610e28580af62c365e898389`; archive SHA-256 `6bf9c64c848c06e2fd985f3051ccb65adc878cc7d0bb1f38f73090b8d952c5e1` |
| A100 sparse-MLA patch | locally recovered, previously verified PR #38476 v0.24-compatible patch in `vendor-patches/` | upstream head `3740c02bb1223d37823593664ae3eafa397b9937`; patch SHA-256 `f8e22e9df9b05b15bf0cbb5cb59e9ab61b7dd74b08c6484342b3da5d7603f31a` |
| CUTLASS source | GitCode domestic mirror `https://gitcode.com/gh_mirrors/cu/cutlass.git`; vendored as `vendor-sources/cutlass-v4.4.2-da5e086.tar.gz` | tag `v4.4.2` / commit `da5e086dab31d63815acafdac9a9c5893b1c69e2`; archive SHA-256 `fc0d4b8aa08cb2d973f06cbc294099899da881f86a4cb93e39e8e6d8fe7d85bd` |
| PyTorch wheels | `https://mirrors.nju.edu.cn/pytorch/whl/cu128` | torch `2.11.0+cu128`, torchvision `0.26.0+cu128`, torchaudio `2.11.0+cu128` |
| General Python packages | `https://pypi.tuna.tsinghua.edu.cn/simple` | final exact closure is written to `/opt/glm52-vllm-pip-freeze.txt` in the image |
| Ubuntu apt packages | `https://mirrors.tuna.tsinghua.edu.cn/ubuntu/` | package versions are retained in the final image's dpkg database |

Verified Python 3.10 wheel hashes on the Nanjing University mirror (the clean-v2
build itself uses the official base image's Python 3.12 wheels for the same
versions):

- torch: `72d53f3176a69cc20710c4ecb95f7dc4c6ba10c4e4eda45b8396ee79ee40f75a`
- torchvision: `f44bfc61b9be80bcf52a762d34da363cea3125d10c01f37e271583803c7bb97b`
- torchaudio: `034fbae103061b74694eb1963a5e918749bca3c0e998ad5bd05125bcfe903122`

The source archive is a working-tree snapshot of the exact Gitee tag. Its text
files have Windows CRLF line endings; after Git's deterministic
`core.autocrlf=input` normalization, the affected files' blob IDs match the
patch's exact v0.24.0 base blob IDs. The Dockerfile writes the normalized index
back to the Linux worktree before the strict `git apply --check`. Gitee
advertises the exact v0.24.0 commit but does not expose the unmerged PR head
(`not our ref`). The compatible patch was recovered from the already hashed
prior offline image; its embedded provenance records the original full PR diff
SHA-256 `9b6126e460a818806643b712f6f2f00764aabf3f0b82dbd75a184f10aa976a2b`.
The build therefore performs no Git network access and verifies both vendored
files before extraction/application.

The previous image used unrestricted `pip --force-reinstall` while changing
PyTorch. Its build log reported incompatible numpy, cuda-bindings, and
cuda-pathfinder versions. This recipe retains the official non-CUDA dependency
closure, replaces only the CUDA ABI packages, builds a normal non-editable vLLM
wheel, runs `pip check`, loads every required native library, rejects any
cu129-linked extension, and verifies GLM/AWQ/PR-backend registration.

The clean-v2 native wheel build exposed two pre-existing dependency defects in
the vLLM base image. The recipe pins `nixl-cu12==1.2.0`, matching the installed
`nixl==1.2.0`; the verified TUNA Python 3.12 x86_64 wheel SHA-256 is
`ca2f2c387e0bb7f448922212cf0d6485e051289cf9c1b67f1ee4cb2ffd327c51`.
It also installs `pycairo==1.28.0` for the base image's `PyGObject==3.42.1`;
the verified TUNA source archive SHA-256 is
`26ec5c6126781eb167089a123919f87baa2740da2cca9098be8b3a6b91cc5fbc`.

DaoCloud was verified first and advertised the same amd64 digest, but its
2.99GB CUDA layer returned a truncated blob (`short read`, `unexpected EOF`)
during the first build attempt on 2026-07-31. The selected `docker.1ms.run`
mirror was then independently verified to advertise the identical amd64
manifest digest before retrying, but did not finish within a two-hour pull
window. The third domestic mirror, `docker.1panel.live`, was independently
verified to expose that same amd64 digest and selected next. Completed content
layers from the prior attempts remain in Docker's content/build cache.

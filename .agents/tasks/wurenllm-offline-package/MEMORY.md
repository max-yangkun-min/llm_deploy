# wurenllm offline package task memory

Status: active
Last updated: 2026-07-26 20:39 (Asia/Shanghai)

## User objective

Create a minimal offline deployment package at `E:\wurenllm` for the XT dual
server A40 environment. It may use three model-specific Docker images rather
than one shared image.

The final package must contain only required Docker image archives, model
files, startup scripts, and concise documentation. The newer user instruction
requires three fully independent model方案 directories, so each has its own
parameter README plus a top-level index. Do not include the old
system preparation, reconnaissance, download, or other helper scripts.

## Current state

- Three model-profile images were built and statically validated:
  - `wurenllm/minimax-m2.7:vllm0.24.0-cu129`
  - `wurenllm/qwen3.5-397b-a17b:vllm0.24.0-cu129`
  - `wurenllm/kimi-k2.6:vllm0.24.0-cu129`
- The former combined archive was replaced with three fully independent
  archives. Each archive includes all shared layers and its manifest contains
  exactly one corresponding tag:
  - MiniMax: 12,222,927,872 bytes, SHA-256
    `6B0D9980E912A3BA404F79C20F0BF4DB3835E4FC0F258EEEC106BFF25DF38497`.
  - Qwen: 12,222,927,872 bytes, SHA-256
    `8C55174A6C39D15817BFDE32DA4F3B06F10EBC2B0F01994952263BAD0801E372`.
  - Kimi: 12,222,927,360 bytes, SHA-256
    `19942DF37FD8BCF20EFEF29E2AD84868FC7D1F83CF59538AE5F5CB6140BD7079`.
- The selected domestic base is
  `docker.m.daocloud.io/vllm/vllm-openai:v0.24.0-cu129`, digest
  `sha256:6b005c78cd17a1f0215f31e95d183833f4dfd6167c4473241b80d1c8843b91e8`.
  This is the lowest CUDA variant verified for vLLM 0.24.0; the default tag is
  CUDA 13.0. The cu129 image officially allows the R535/R550/R560/R565/R570
  data-center compatibility branches. R570.172.08 or native R575+ is
  recommended; R545 is not in the image allowlist.
- `E:\wurenllm` is now split into three self-contained directories plus a top
  README: `minimax-m2.7-awq`, `qwen3.5-397b-a17b-awq`, and `kimi-k2.6`.
  Each contains only its own README, `start.sh`, image archive, and model tree.
  The old top-level `start.sh`, combined archive, and empty shared
  `images/models` directories were removed. All three final E: scripts passed
  `bash -n`; cross-model reference count in each script is zero.
  The Qwen script additionally supports a non-cluster single-node 8-GPU action:
  `GPU_DEVICES=0,1,2,3,4,5,6,7 PORT=8000 ./start.sh local`, using TP=4,
  PP=2, and the local `mp` executor. Its existing two-node 4+4 Ray actions remain
  separate. The E: script passed `bash -n` after this update.
- Exact domestic-mirror model inventories:
  - MiniMax: `QuantTrio/MiniMax-M2.7-AWQ@c9f219...`, 75 files,
    130,266,976,748 bytes.
  - Qwen: `QuantTrio/Qwen3.5-397B-A17B-AWQ@536f955...`, 96 files,
    244,404,845,704 bytes.
  - Kimi: `moonshotai/Kimi-K2.6@7eb5002...`, 96 files,
    595,204,999,341 bytes. This official artifact is 4-bit
    `compressed-tensors`, not AWQ.
- The old MiniMax local-dir download state was moved within E: into the final
  package to avoid duplication. The sequential downloader subsequently failed
  on MiniMax at 2026-07-24 23:37 because an HTTP transfer ended with
  `ChunkedEncodingError`; it did not start Qwen or Kimi.
- Qwen completed successfully at 2026-07-25 17:45. Its model was moved within
  E: to `E:\wurenllm\qwen3.5-397b-a17b-awq\models\Qwen3.5-397B-A17B-AWQ`;
  the pinned downloader rechecked the new destination and returned COMPLETE.
  Final local check: 82/82 safetensor shards, `config.json` and
  `model.safetensors.index.json` present, zero `.incomplete`/`.lock`, 227.620
  GiB including local cache/metadata. The completed progress window was closed.
  A full integrity audit on 2026-07-25 confirmed exactly 96 runtime files and
  244,404,845,704 runtime bytes (exactly matching the pinned mirror inventory),
  all 82 shard numbers continuous, all nine JSON files parseable, all 82
  safetensors headers and 276,212 tensor offsets valid, all 96 metadata records
  pinned to revision `536f955...`, and all 84 files carrying upstream SHA-256
  metadata matched byte-for-byte (zero missing/mismatched hashes).
- Model state after the split:
  - MiniMax: complete and fully verified against
    `QuantTrio/MiniMax-M2.7-AWQ@c9f2192c7b81f26f9a257ce73d92122fff0aea3d`.
    The audit read 130,266,976,748 bytes in 1m18s: 75/75 official files and
    44/44 AWQ shards matched their pinned SHA-256/Git blob hashes, with zero
    missing, size-mismatched, or hash-mismatched files. With subsequent user
    authorization, the `.cache` metadata tree and two non-repository files
    (`_放这里.txt` and `README-部署.md`) were removed. Final state is exactly
    75 files and 130,266,976,748 bytes, with zero cache or temporary files.
  - Qwen: complete as described above.
  - Kimi: download started at 2026-07-25 18:14 in a dedicated visible
    PowerShell window, using the pinned
    `moonshotai/Kimi-K2.6@7eb5002f6aadc958aed6a9177b7ed26bb94011bb`
    artifact from `https://hf-mirror.com`, two workers, resumable local-dir
    state, and automatic 20-second retries. The wrapper PID was 5420 and its
    active `hf.exe` PID was 10324 at startup. Verification at 18:14 showed 55
    local files, about 995 MB written, two incomplete files, and the first of
    64 safetensor shards actively growing. Status is recorded under
    `E:\llm_models\kimi-k2.6-download\`.
    At 19:48 the first `hf` attempt exited with code 1 and the wrapper resumed
    attempt 2 at 19:49. A slowdown diagnosis around 20:45 found 32/64 shards
    complete and 305.076 GB of model data present. The Python process was alive
    but mostly waiting; two remote connections had entered `CLOSE_WAIT`, and
    the active large-file requests were connected to AWS/CloudFront endpoints.
    A 15-second sample showed only about 52.4 MB of additional E: allocation
    (~3.5 MB/s), while CPU and disk capacity were not limiting. Treat the
    slowdown as CDN/network-path fluctuation.
    The slow HF process was replaced at 21:06 with a ModelScope accelerator
    after verifying the official `moonshotai/Kimi-K2.6` ModelScope repository:
    all 64 weight filenames, byte sizes, and SHA-256 values match the pinned HF
    artifact (the complete repository differs only by about 5 KB of platform
    metadata). Direct HF-mirror measured 4.49 MB/s; ModelScope IPv4 with four
    concurrent range requests measured about 33 MB/s in the preflight test.
    The production downloader reuses all 32 completed shards and uses resumable
    `.modelscope.part` files for the remaining 32. After its progress-display
    restart, wrapper PID 20468 resumed four 1.86-2.09 GB partial files and was
    sustaining about 42.8 MB/s combined at 21:10. Do not start another Kimi
    downloader. Final SHA-256 inventory verification is still required.
    The first progress-management loop then hit a PowerShell variable-name bug:
    `$pid` conflicts case-insensitively with the built-in read-only `$PID`.
    The four orphaned curl processes were stopped after their handles flushed,
    preserving 5.15-5.32 GB per partial shard. The loop variable was corrected
    to `$processId` and the script was syntax checked. The final visible window
    was restarted with `-NoLogo` as PID 17836 at 21:22, using eight concurrent
    IPv4 curl children. It passed the former failure point, resumed the four
    saved 5.74-5.97 GB partial files, started shards 37-40, and measured about
    44.9 MB/s combined during validation.
    A second completion-handling issue was found at 22:02: `Start-Process`
    returned a blank curl `ExitCode`, so full-size `.modelscope.part` files were
    mistakenly queued for retry instead of renamed. The downloader now treats
    an exact expected byte length as completed both during startup and runtime;
    SHA-256 remains the final integrity gate. After safely flushing all active
    handles and stopping one race-created orphan curl, wrapper PID 23180
    restarted at 22:03. It converted nine complete part files to standard
    `.safetensors`, yielding 41/64 final shards, and resumed eight remaining
    partial files. Validation found zero full-size files left with a part suffix.
    The accelerated downloader reported `ALL_SHARDS_COMPLETE` at 23:09. A full
    pinned-inventory audit against
    `moonshotai/Kimi-K2.6@7eb5002f6aadc958aed6a9177b7ed26bb94011bb`
    then read and hashed 595,178,441,545 local bytes in 7m05s. All 88 present
    files matched (64/64 safetensor shard SHA-256 values included), with zero
    size mismatches, zero hash mismatches, and zero unexpected non-cache files.
    The repository is nevertheless incomplete: 8 of 96 pinned files are
    missing, totaling 26,557,796 bytes: `model.safetensors.index.json`,
    `modeling_deepseek.py`, `modeling_kimi_k25.py`,
    `preprocessor_config.json`, `tiktoken.model`, `tokenization_kimi.py`,
    `tokenizer_config.json`, and `tool_declaration_ts.py`. Two stale
    `.incomplete` and two `.lock` files remain under the HF local cache. Do not
    clean the cache or mark Kimi complete until the 8 files are restored and
    their pinned hashes verified.
    The 8 missing files were restored from the verified `hf-mirror.com` pinned
    revision and individually verified (LFS SHA-256 or Git blob SHA-1). Final
    post-cleanup state is exactly 96 files and 595,204,999,341 bytes, with
    64/64 shards, `config.json`, and `model.safetensors.index.json` present;
    there are zero `.part`, `.incomplete`, or `.lock` files. The validated
    `.cache` tree was removed, reclaiming 13,075,763,200 bytes. Kimi is now
    complete and clean. E: had 33,764,188,160 bytes (31.445 GiB) free at the
    final check; MiniMax's model tree measured 113,962,278,518 logical bytes.
- After Qwen completion and the three-way package split, E: had exactly
  684,194,709,504 bytes (637.206 GiB) free when checked on 2026-07-25. The
  pinned Kimi repository needs 595,204,999,341 bytes, so it fits by itself and
  should leave about 88.990 GB (82.878 GiB) before download-cache cleanup.
  With all three pinned repositories and all three independent image archives
  present, the theoretical final reserve is only about 17.661 GB (16.449 GiB),
  excluding small filesystem/cache overhead. Completing all three on this disk
  is therefore possible but leaves very little operating margin.

## Consolidated progress snapshot (2026-07-25 23:54)

- All three model downloads are finished. Do not download MiniMax, Qwen, or
  Kimi again.
- MiniMax is complete, fully pinned-hash verified, and clean: 75 model files,
  130,266,976,748 bytes, 44/44 AWQ shards, zero cache/temp files. Its complete
  independent package is 142,489,907,744 bytes.
- Qwen is complete and fully audited as recorded above: 96 runtime files,
  244,404,845,704 runtime bytes, and 82/82 AWQ shards. It has zero temporary
  files but still retains a harmless `.cache` metadata tree containing 97 files
  and 11,969 bytes. Its current independent package is 256,627,792,192 bytes
  including that cache.
- Kimi is complete, fully pinned-hash verified, and clean: 96 model files,
  595,204,999,341 bytes, 64/64 compressed-tensors shards, zero cache/temp
  files. Its complete independent package is 607,427,931,463 bytes.
- All three independent Docker image archives and startup scripts remain in
  their respective package directories; their image sizes and SHA-256 values
  are recorded above.
- E: total capacity is 1,024,207,089,664 bytes and current free space is
  17,459,421,184 bytes (16.260 GiB). Avoid creating duplicate archives or model
  copies on E:.
- Task remains active only for final package cleanup/static validation and
  target-server runtime validation handoff.

## Final static acceptance (2026-07-26 00:05)

- Qwen's already verified `.cache` was removed: 97 metadata files and 11,969
  bytes. Its final model tree is exactly 96 files and 244,404,845,704 bytes,
  with zero cache/temp files.
- Final `E:\wurenllm` whitelist passed: the top level contains only the three
  independent package directories and `README.md`; each package root contains
  only `README.md`, `start.sh`, `images/`, and `models/`.
- Final independent package sizes:
  - MiniMax: 78 files, 142,489,907,744 bytes; model 75 files,
    130,266,976,748 bytes, 44/44 shards.
  - Qwen: 99 files, 256,627,780,223 bytes; model 96 files,
    244,404,845,704 bytes, 82/82 shards.
  - Kimi: 99 files, 607,427,931,463 bytes; model 96 files,
    595,204,999,341 bytes, 64/64 shards.
- The complete clean package is 277 files and 1,006,545,620,677 bytes. No model
  tree contains `.cache`, `.part`, `.incomplete`, or `.lock` state.
- All three `start.sh` files passed WSL `bash -n`, are UTF-8 without BOM and use
  LF endings. Exact model paths, read-only container mounts, image tags,
  quantization modes, TP/PP settings, Ray/mp backends, and zero cross-model
  references were validated.
- All four READMEs are valid UTF-8 without BOM or replacement characters and
  accurately record the selected model revisions, topologies, archive sizes,
  and image hashes.
- All three Docker archives were rehashed and matched the recorded SHA-256.
  Each `manifest.json` parsed successfully with exactly one entry, the expected
  sole `RepoTag`, and 38 layers.
- E: free space after acceptance is 17,459,453,952 bytes (16.260 GiB). Do not
  create duplicate archives or model copies on E:.
- Offline package preparation and Windows-side static validation are complete.
  No images were loaded and no model was started during this acceptance pass.
  Real GPU/model/Ray/NCCL/throughput validation remains target-server work.

## Target-site driver compatibility (2026-07-26)

- User reported the target A40 server shows NVIDIA driver `550.127.05` and
  `nvidia-smi` CUDA Version `12.4`.
- The archived `vLLM 0.24.0-cu129` image configuration was re-read directly
  from the accepted MiniMax image archive. Its `NVIDIA_REQUIRE_CUDA` explicitly
  allows the R550 branch (`driver>=550,driver<551`), it contains
  `cuda-compat-12-9`, sets `VLLM_ENABLE_CUDA_COMPATIBILITY=1`, and prepends
  `/usr/local/cuda-12.9/compat` to `LD_LIBRARY_PATH`.
- Therefore `550.127.05` is within the package's designed compatibility path.
  The `CUDA Version 12.4` shown by `nvidia-smi` is the host driver's native CUDA
  capability indicator, not a requirement to install a host CUDA 12.9 toolkit;
  the container supplies its CUDA 12.9 user-space runtime and compatibility
  libraries.
- No image rebuild or driver upgrade is required before deployment. This is a
  static compatibility conclusion, not a completed runtime qualification.
  Before model loading, confirm Docker plus NVIDIA Container Toolkit exposes
  the A40 GPUs inside the container and run a small PyTorch CUDA allocation.
  Then proceed with the existing real model/Triton/Ray/NCCL tests. For
  multi-node deployments, both nodes should preferably use the same driver
  version and NVIDIA Container Toolkit configuration.

## Required policy

- Prefer and verify exact artifacts on domestic China mirrors before external
  downloads.
- Tell the user before falling back to an overseas source.
- Record exact image/model versions and revisions for reproducibility.

## Next action

1. Do not download, rebuild, or duplicate any model or image on E:.
2. Copy only the selected independent package directory to its target server(s)
   and follow that directory's README.
3. On the target A40 servers, validate the NVIDIA driver/GPU topology, load the
   image, and perform real model loading, Triton JIT, AWQ/compressed-tensors,
   Ray/NCCL, API, and throughput tests.

## Qwen tool-calling parameter gap (2026-07-26)

- The accepted split Qwen script at
  `E:\wurenllm\qwen3.5-397b-a17b-awq\start.sh` currently omits tool-calling
  and reasoning parser flags in both its `serve` (Ray) and `local` actions.
- The earlier combined source script used
  `--enable-auto-tool-choice --tool-call-parser hermes --reasoning-parser qwen3`,
  but direct inspection of the accepted image and pinned model shows that
  `hermes` is not the best parser choice for this model.
- Direct read-only extraction from the accepted 12.2 GB image archive confirmed
  vLLM 0.24.0 registers `qwen3_coder`, `qwen3_xml`, and `hermes`; the image does
  support native automatic tool calling and does not need rebuilding.
- The pinned Qwen3.5 tokenizer chat template emits Qwen XML calls in the form
  `<tool_call><function=...><parameter=...>`, matching vLLM's `qwen3_coder`
  (`Qwen3EngineToolParser`). The corrected launch flags should therefore be
  `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3`.
- This is a deployment-script regression discovered during target-site testing.
  No file was changed yet because the user asked for diagnosis, not an edit.
  Add the corrected flags to both Qwen launch paths, syntax-check the script,
  and restart the Qwen service before testing automatic tool calling.

## Kimi tool-calling parameter gap (2026-07-26)

- The accepted split Kimi script at `E:\wurenllm\kimi-k2.6\start.sh` also
  omits tool-calling and reasoning parser flags from its `serve` action.
- The accepted Kimi image build explicitly verified that vLLM registers the
  `kimi_k2` tool parser, and the pinned model tokenizer contains the Kimi tool
  control tokens (`<|tool_calls_section_begin|>`, `<|tool_call_begin|>`, etc.).
  The image and model therefore support tool calling; no rebuild is required.
- The earlier combined launch used the intended flags
  `--enable-auto-tool-choice --tool-call-parser kimi_k2 --reasoning-parser kimi_k2`.
  Add them to the split Kimi `serve` command and restart before testing
  OpenAI-compatible automatic tool calls.

## Target-site checkpoint saved at 2026-07-26 20:39

- The user is actively testing the copied Kimi/Qwen packages on the target
  servers. Current model-load/inference success is not yet established; the
  user reported an unchanged `watch nvidia-smi` view but has not yet supplied
  `/v1/models` or the last 100 lines of `/tmp/vllm.log`.
- The E: Qwen script does contain `local` and `local-logs` actions. If the
  target copy does not show them, it is an older script. Current E: Qwen script
  SHA-256 is
  `8C10976E8AB5A9D6DBD840792916CA42092B53F077D60006542C50B5EBAACC2B`.
- No E: package files or target scripts were modified during this diagnostic
  exchange. The pending script correction is to add the Qwen and Kimi parser
  flags recorded above, update their READMEs, run `bash -n`, and then replace
  the target-side scripts before restarting services.
- Recommended initial Qwen coding-agent context is 32,768 tokens (input plus
  output), with 16,384 for higher concurrency and 65,536 only after runtime
  memory/throughput validation. Continue using 8,192 for initial smoke tests.
- For reported garbled text, first compare a direct non-streaming localhost
  vLLM response parsed as UTF-8. If direct output is correct but streaming or
  gateway output is corrupt, inspect incremental UTF-8/SSE decoding; strings
  such as `涓枃` indicate UTF-8 bytes decoded as GBK.

## Embedding model recommendation (2026-07-26)

- Recommended addition: `Qwen/Qwen3-Embedding-8B`, served on one otherwise
  unused A40 as an independent vLLM embedding service. No model files were
  downloaded in making this recommendation.
- The exact domestic ModelScope repository was verified online at
  `Qwen/Qwen3-Embedding-8B`; current `master` commit is
  `fcd9221ff0c460fdd81bfd04f4bc5b014e58da5b`.
- ModelScope reports BF16 weights in four safetensor shards, repository storage
  of 15,150,576,408 bytes, 32K context, up to 4096 dimensions with MRL custom
  dimensions, and vLLM embedding support from vLLM 0.9.2. The existing vLLM
  0.24.0 image is therefore new enough, subject to an actual A40 API test.
- For XT, start with 1024-dimensional normalized vectors and an 8K input cap;
  use 4096 dimensions only if retrieval evaluation proves the extra vector
  storage and bandwidth worthwhile. Query-side instructions should be used;
  documents do not need them.
- If maximum embedding throughput matters more than retrieval quality, the
  fallback is `Qwen/Qwen3-Embedding-4B`; it is not the primary recommendation
  because a dedicated 48GB A40 comfortably accommodates the 8B BF16 model.
- Follow-up selection: for pure-text offline retrieval, retain
  `Qwen3-Embedding-8B`; the preferred quality upgrade is a two-stage pipeline
  with `Qwen/Qwen3-Reranker-8B`, rather than replacing the embedding model.
  ModelScope verified the reranker repository (about 16.39 GB) and reports
  vLLM support from 0.9.2. Retrieve roughly top 30-50 candidates with embedding
  and rerank them to the final top 5-10.
- For image, scanned-PDF, chart, or page-layout retrieval, use the separately
  verified domestic repository `Qwen/Qwen3-VL-Embedding-8B` (about 16.31 GB),
  but do not assume the existing vLLM 0.24.0 image supports its multimodal
  embedding path: the ModelScope metadata did not advertise a vLLM backend, so
  this variant requires a separate runtime/API validation before packaging.
- `BAAI/bge-multilingual-gemma2` also exists on ModelScope (about 36.99 GB and
  vLLM support reported from 0.9.2), but it is not recommended over Qwen3
  Embedding 8B for this Chinese/code deployment on size-quality grounds.

## Target-site image smoke test (2026-07-26)

- The user reported that the Kimi image has reached the target server while the
  model upload is still in progress.
- The first CUDA smoke-test command failed because it overrode the entrypoint
  with `python`. The image build uses `python3`; no `python` alias is guaranteed.
  Retry with `--entrypoint python3`. Full model loading must wait for all model
  files, but image, GPU, CUDA, PyTorch, vLLM, and Ray checks can run now.
- The corrected target-server smoke test passed: PyTorch reported CUDA
  available, all six visible GPUs were NVIDIA A40 devices, and a CUDA tensor
  operation completed on every GPU. Core imports also passed with CUDA 12.9,
  vLLM 0.24.0, and Ray 2.56.1. This qualifies the image and single-node GPU
  runtime at smoke-test level; model loading and two-node Ray/NCCL validation
  remain pending until the model upload completes.
- The same CUDA tensor smoke test on the second server was then reported to
  fail with `RuntimeError: CPU dispatcher tracer already initialized`. The
  preceding error is now known to be `pthread_create failed ... Operation not
  permitted`. This strongly points to the second host's Docker/runc/libseccomp
  default seccomp profile blocking thread creation (commonly `clone3`), rather
  than model-file permissions or a defective image. Confirm by rerunning once
  with `--security-opt seccomp=unconfined`; if that passes, compare/update the
  container runtime stack with server 1 or use an explicitly reviewed seccomp
  workaround. Also rule out a configured PID limit.
- Confirmation completed: the second-server PyTorch/CUDA smoke test passes when
  `--security-opt seccomp=unconfined` is supplied. The second host's default
  seccomp/runtime stack is therefore the confirmed cause. Until Docker/runc/
  libseccomp is aligned with server 1, the Kimi Ray container on server 2 must
  receive the same security option; this is a host-specific workaround with a
  broader container syscall surface.
- Before the first Kimi model load, a capacity risk was identified in the
  accepted 6+6 A40 topology: the pinned repository contains about 595.2 GB of
  compressed weight data, while 12 nominal 48 GB A40s provide only 576 GB raw
  aggregate VRAM before CUDA/runtime/KV-cache overhead. Standard all-GPU vLLM
  loading is therefore likely not feasible on 12 cards. Ray startup can still
  be validated, but a successful model load likely requires additional GPUs,
  a deliberately tested CPU-offload configuration, or a different artifact.

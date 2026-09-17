# kty5l on-site GPU-memory startup incident

Status: GPU conflict cleared; new native segfault during model load under diagnosis
Last updated: 2026-07-27 21:44 (Asia/Shanghai)

## Objective

Diagnose the GLM-5.2 vLLM startup failure shown in the on-site screenshots.

## Diagnosis

- The first actionable exception is vLLM's GPU free-memory guard, not a CUDA
  compatibility or model-path error.
- With `--gpu-memory-utilization 0.90`, vLLM requires about 71.33 GiB free on
  each 79.2 GiB A100 at worker startup.
- The screenshots report only about 3.00 GiB free on `cuda:6` and 31.41 GiB
  free on `cuda:7`. Other processes therefore occupy those devices, and their
  workers fail `init_device`.
- `TRITON_MLA_SPARSE` is selected successfully and the DeepGEMM fallback line
  is expected for this image. Those lines are not the cause.
- The later `Segfault encountered`, `EngineCore failed to start`, and
  `Engine core initialization failed` messages are downstream fallout after
  part of the eight-worker launch fails. Reassess them only if they recur after
  all eight GPUs have enough free memory and no earlier memory-guard exception.

## Retry evidence (2026-07-27 20:11 upload)

- Three retry photos initially showed only the downstream chain:
  `WorkerProc initialization failed` -> `EngineCore failed to start` ->
  `Engine core initialization failed`.
- The subsequently uploaded preceding photo contains the first actionable
  exception: `cuda:6` had only `49.84 GiB` free at worker startup, while
  utilization `0.9` requires `71.33 GiB` free.
- Roughly `29.3 GiB` therefore remained occupied on physical GPU 6. This is
  the same class of conflict as the earlier attempt, although more memory has
  been freed than before.
- The `pid=522` printed beside the traceback is the failed vLLM worker. Do not
  assume it is the external memory owner; identify host processes with
  `nvidia-smi` before stopping anything.
- The retry still shows successful selection of `TRITON_MLA_SPARSE`. The
  DeepGEMM fallback remains expected and is not the failure.

## Coexistence assessment

- Keeping the conflicting service at its current roughly 29.3 GiB GPU-6
  allocation is incompatible with the validated GLM launch configuration.
- On an approximately 79.2 GiB A100, utilization `0.90` allows only about
  7.9 GiB to be occupied before GLM starts; GPU 6 currently exceeds that by
  roughly 21.4 GiB.
- Reducing `GPU_MEMORY_UTILIZATION` to about `0.62` could only bypass the
  initial free-memory guard (`49.84 / 79.2 ~= 0.629`). It would leave almost no
  headroom for this very large INT4 model's per-rank weights and runtime state,
  so a later OOM is likely and this is not a production recommendation.
- Viable non-stop alternatives require moving/reducing the conflicting
  workload until every GLM GPU is nearly free, or giving GLM eight other clean
  GPUs. The target's known eight-GPU layout provides no spare set.

## Retry after conflicting service was stopped

- The user reports stopping the conflicting service and retrying startup.
- Two photos from the new attempt show timestamp `12:26:31` and EngineCore
  `pid=339`, confirming this is a distinct launch from the earlier `12:11:52`
  attempt.
- Both photos contain only the downstream `WorkerProc initialization failed`,
  `EngineCore failed to start`, and API-server `Engine core initialization
  failed` tracebacks. The first worker exception is above the photographed
  region, so these photos alone cannot distinguish residual GPU occupation
  from a new model-load/CUDA/NCCL failure.
- Next evidence needed: filtered complete container logs around the earliest
  `WorkerProc failed to start`, especially `ValueError`, `RuntimeError`, CUDA
  OOM, NCCL, or `free memory on device` lines.

## Full post-cleanup startup sequence

- Four additional photos cover the startup from API-server configuration
  through the first crash.
- The previous free-memory guard exception is absent. Workers initialize the
  eight-rank NCCL world (`world_size=8`, ranks through 7 are visible).
- Rank 0 reaches `Starting to load model /model...`; the required
  `TRITON_MLA_SPARSE` backend is selected, then TP0 immediately prints
  `Segfault encountered` with only Python C-call frames.
- This is now a genuine native-process crash during the beginning of model
  loading, rather than the earlier downstream failure caused by an unavailable
  GPU.
- The repeated missing `vllm._qutlass_C`, deprecated CUDA binding warnings,
  A100/SymmMem unsupported warnings, DeepGEMM Triton fallback, and disabled
  custom all-reduce on more than two PCIe-only GPUs all match the intentionally
  reduced A100 image or expected platform fallbacks; none is the actionable
  exception shown.
- Highest-value next checks are (1) kernel messages for the faulting shared
  object, NVIDIA Xid, or host OOM and (2) full `MANIFEST.sha256` verification,
  especially the approximately 410 GB model weights. The image did not receive
  a full target-side model-load acceptance test before export, so an image
  native-extension fault remains possible if package integrity passes.

## Kernel and container-state evidence

- Host `dmesg` reports `uvicorn[8574]: segfault at 28 ... error 4 in
  python3.11`. This is a user-space read from a near-null address (`0x28`),
  consistent with a null-pointer/native-extension crash.
- No NVIDIA `NVRM`/`Xid` event and no kernel OOM message are visible in the
  filtered output.
- `docker inspect` reports `ExitCode=1`, `OOMKilled=false`, and an empty state
  error. This excludes Docker/host OOM termination and a container-runtime
  launch failure.
- The instruction pointer is attributed to the Python executable rather than
  naming a specific shared object, so the current kernel line does not yet
  distinguish vLLM/PyTorch native code from another C-extension path.
- Full manifest verification is still outstanding. If it passes, inspect any
  systemd coredump for PID 8574 and isolate the image with the packaged smoke
  model if that older on-site package still contains it.

## Manifest-check formatting defect

- Running `sha256sum --quiet -c ./MANIFEST.sha256` from the correct package
  root reports every path as missing with a visible trailing `$'\r'`.
- The manifest has Windows CRLF line endings. `sha256sum` treats the carriage
  return as part of each filename, so this attempt did not open or hash the
  image/model files and is not evidence of missing or corrupt weights.
- Preserve the original manifest and create an LF-normalized copy with
  `sed 's/\r$//' MANIFEST.sha256 > MANIFEST.lf.sha256`, then check the copy.
- This is a packaging/documentation defect to correct in any future package;
  Linux-consumed checksum manifests must be emitted with LF line endings.

## Integrity-check decision

- The user chose not to wait for a complete approximately 425 GB manifest
  verification. The running check may be interrupted with Ctrl+C.
- Model corruption is currently a lower-probability explanation: all 83 weight
  shards are present with plausible sizes, configuration/architecture parsing
  completes, and ordinary truncated/corrupt safetensors metadata normally
  produces an explicit file/header error rather than a near-null CPython
  segfault.
- Integrity is nevertheless not proven. Keep corruption as a residual
  possibility if native-stack isolation does not identify the crash.
- Continue with the existing coredump for PID 8574 and small-model/native-stack
  isolation before changing the driver or rebuilding/replacing large inputs.

## Completed integrity result

- The LF-normalized manifest verification completed.
- All large artifacts, including the image, all 83 safetensors shards, model
  index/configuration, and associated model files passed. Model-copy corruption
  is therefore excluded for this incident.
- Only `README.md` and `scripts/run.sh` mismatch the historical manifest. The
  README is non-runtime data. The failing launch was invoked through root
  `start.sh`, not `scripts/run.sh`, so neither mismatch explains the native
  segfault.
- The remaining fault domain is the image's GLM/AWQ native model-load path (or
  a host interaction exposed by that path). Obtain `coredumpctl info 8574` if
  available, then run a minimal in-image CUDA/vLLM native-extension test to
  separate a general image fault from the GLM-specific path.

## Next action on target

1. Stop the failed `glm52` container with `./start.sh stop`.
2. Use `nvidia-smi`, the compute-process query, `ps`, and `docker ps` to identify
   the owners of GPU memory, especially GPU 6. Do not kill unrelated workloads
   blindly.
3. Stop or move the confirmed conflicting jobs so all eight A100s are nearly
   empty, then run `./start.sh start` and `./start.sh logs` again.
4. Lowering `GPU_MEMORY_UTILIZATION` alone is not a practical fix while GPU 6
   has only about 3 GiB free; the model itself still needs substantial memory.

## Package state

- Continue using `glm52-vllm:0.24.0-pr38476-cu128-native-r570-a100`.
- No package or host-driver change is indicated by these screenshots.

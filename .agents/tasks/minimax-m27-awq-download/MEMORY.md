# MiniMax M2.7 AWQ download task memory

Status: stopped at user request
Last updated: 2026-07-23 (Asia/Shanghai)

## User objective

Download the exact MiniMax M2.7 AWQ model artifacts to `E:\llm_models`,
preferring a verified domestic China mirror.

## Current state

- Selected domestic mirror: `https://hf-mirror.com`.
- Verified repository: `QuantTrio/MiniMax-M2.7-AWQ`.
- Pinned revision: `c9f2192c7b81f26f9a257ce73d92122fff0aea3d`.
- Mirror inventory contains 44 `model-*.safetensors` shards plus
  `model.safetensors.index.json`, tokenizer/configuration, code, license, and
  documentation files.
- Verified total repository size: 130,266,976,748 bytes (about 121.32 GiB).
- Destination: `E:\llm_models\MiniMax-M2.7-AWQ`.
- E: capacity at start: 953.69 GiB free; sufficient for the artifact.
- Download was started with `hf download`, `HF_ENDPOINT=https://hf-mirror.com`,
  and `--max-workers 8`. The active wrapper/process observed at 21:57 was
  `hf` PID 18804 / Python PID 23376. Ten resumable shard downloads were active;
  partial cache size was increasing. The user then requested cancellation.
- Download processes were stopped without deleting data. At cancellation,
  4 shard files were finalized (11.161 GiB) and 10 resumable `.incomplete`
  files occupied 9.873 GiB under the local Hugging Face cache.

## Required policy

- Verify that the domestic mirror contains the exact AWQ artifact before use.
- Record mirror, repository, revision, file inventory/checksums when available,
  and final local path for reproducibility.
- Notify the user before falling back to an overseas source.

## Next action

If the user resumes later, rerun the reproducible command below; the existing
finalized files and `.incomplete` cache can be reused. The model is not
complete and must not be used as a finished checkpoint.

## Reproducible command

```powershell
$env:HF_ENDPOINT='https://hf-mirror.com'
hf download QuantTrio/MiniMax-M2.7-AWQ `
  --revision c9f2192c7b81f26f9a257ce73d92122fff0aea3d `
  --local-dir 'E:\llm_models\MiniMax-M2.7-AWQ' --max-workers 8
```

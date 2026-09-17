# kty5l GLM-5.2 package simplification

Status: complete
Last updated: 2026-07-26 21:24 (Asia/Shanghai)

## Objective

Simplify `kty5l/offline-glm52` to the same deployment-package pattern used by
the accepted XT packages: one model, one selected image archive, one concise
README, and one root-level startup script.

## Decisions

- Keep only the preferred A100/R570 native CUDA 12.8 image:
  `glm52-vllm:0.24.0-pr38476-cu128-native-r570-a100`.
- Remove the optional cu129 compatibility archive and its sidecar; it is not
  needed for the target 8x A100/R570 host.
- Remove build, download, reconnaissance, system-install, patch, fallback,
  and Qwen diagnostic artifacts from the final deployment package.
- Keep the GLM model directory and use a package-relative, read-only mount.
- Replace the multi-stage build/run helper with `start.sh` actions
  `load`, `start`, `logs`, `test`, and `stop`.
- Default to the conservative 32K context baseline. Permit field adjustment
  through environment variables without editing the script.

## Completed result

- Final package root contains exactly `README.md`, `start.sh`, `images/`, and
  `models/`.
- `images/` contains only the selected 16,353,389,056-byte native cu128 image
  archive and its SHA-256 sidecar.
- The superseded 12,123,978,240-byte cu129 archive and sidecar were removed,
  reclaiming about 11.29 GiB.
- Build, preparation, reconnaissance, system-install, patch, fallback, and
  Qwen diagnostic artifacts were removed from the final package.
- `start.sh` uses package-relative paths, a read-only model mount, and the
  actions `load`, `start`, `logs`, `test`, and `stop`.
- Default launch settings are TP=8, 32K context, 16 sequences, 0.90 GPU memory
  utilization, `TRITON_MLA_SPARSE`, GLM tool/reasoning parsers, prefix caching,
  and chunked prefill. Field overrides are environment variables.
- Final whitelist and stale-reference audits passed. README/start are UTF-8
  without BOM or replacement characters and use LF endings. WSL `bash -n`
  passed. The already validated 15.23 GiB archive was not rehashed.

## Remaining target-site work

- Put the complete `cyankiwi/GLM-5.2-AWQ-INT4` repository in the model folder.
- On the 8x A100 host, run `./start.sh load`, `./start.sh start`, inspect the
  required Triton fallback log lines, and perform the API test.

## Tool-calling check (2026-07-26)

- The simplified `start.sh` explicitly enables automatic tool calling with
  `--enable-auto-tool-choice` and uses `--tool-call-parser glm47`.
- It also enables GLM reasoning extraction with `--reasoning-parser glm45`.
- Static launch-parameter inspection passed. A real OpenAI-compatible
  `/v1/chat/completions` request containing `tools` and `tool_choice: "auto"`
  remains required after the complete model is started on the target host.

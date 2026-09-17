# deploy-portal persistent inputs

Last updated: 2026-09-15 (Asia/Shanghai)

No user-uploaded input files are currently registered for this task.

All data this task consumes already lives in the workspace and is read in place:

| Workspace-relative path | Role |
|---|---|
| `model-selector/models.csv` | 19 exact deployment profiles |
| `model-selector/model-families.csv` | 83 model families |
| `model-selector/hardware*.json` | hardware presets served by `/api/presets` |
| `kty5l/GLM-5.2-部署步骤-8xA100.md`, `kty5l/offline-glm52/start.sh` | GLM-5.2 recipe source |
| `xt/offline-xt/models/*/README-部署.md`, `xt/offline-xt/scripts/run.sh` | xt recipe sources |
| `zc5s/大模型选型方案-8x4090-48G.md`, `zc5s/offline-zc5s/scripts/run.sh` | zc5s recipe source |
| `deploy-q4kxl.md` | DeepSeek-V4-Flash GGUF recipe source |
| `kty5l/build-glm52-vllm-cu128/BUILD-SOURCES.md` | verified domestic mirror + digest list |

When an input is added, record it as:

| Workspace-relative path | Size | SHA-256 | Purpose | Added |
|---|---:|---|---|---|
| `path/to/file` | bytes | checksum | why it is needed | date/time |

# wurenllm offline package inputs

Last updated: 2026-07-26 00:05 (Asia/Shanghai)

| Workspace/external path | State | Purpose |
|---|---|---|
| `xt/offline-xt/` | Present | Existing Dockerfile and deployment scaffolding to simplify |
| `E:\llm_models\MiniMax-M2.7-AWQ` | Contents moved; empty directory remains | Previous resumable MiniMax source |
| `E:\wurenllm` | Final static acceptance passed | Clean 277-file, 1,006,545,620,677-byte package with three independent model directories |
| `E:\wurenllm\minimax-m2.7-awq\` | Complete, verified, and clean | Independent MiniMax package with exact 75-file pinned model and no download cache |
| `E:\wurenllm\qwen3.5-397b-a17b-awq\` | Complete, verified, and clean | Independent Qwen package with exact 96-file, 82-shard model and no download cache |
| `E:\wurenllm\kimi-k2.6\` | Complete and verified | Independent Kimi package with exact 96-file pinned repository and no download cache |
| `E:\llm_models\wurenllm-download.log` | Historical log | Earlier sequential model download handoff; no model download remains active |
| `E:\llm_models\qwen3.5-397b-download\` | Completed logs | Dedicated Qwen download history |
| `.agents/tasks/wurenllm-offline-package/download-qwen-visible.ps1` | Present | Pinned Qwen recheck/resume helper updated to the independent Qwen path |
| `.agents/tasks/wurenllm-offline-package/download-kimi-visible.ps1` | Superseded fallback | Original pinned hf-mirror Kimi downloader; stopped after CDN slowdown |
| `.agents/tasks/wurenllm-offline-package/download-kimi-modelscope-visible.ps1` | Completed helper | Verified ModelScope IPv4 resumable Kimi downloader; retained only as task history |
| `E:\llm_models\kimi-k2.6-download\` | Completed logs | Dedicated Kimi download status history |
| `wurenllm-split/` | Present | Source-of-truth copies of the three final scripts and READMEs |

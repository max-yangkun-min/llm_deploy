# model-selector task memory

Status: active
Last updated: 2026-07-24 (Asia/Shanghai)

## User objective

Maintain a local/open-weight model deployment catalog that can take collected
hardware information and recommend the most suitable model and deployment
profile. The work must remain usable across conversations.

## Current deliverables

- `model-selector/model-families.csv`: broad model-family catalog.
- `model-selector/models.csv`: exact or explicitly qualified deployment profiles.
- `model-selector/recommend.py`: hardware matching and recommendation tool.
- `model-selector/collect-hardware.ps1`: Windows hardware collector.
- `model-selector/collect-hardware.sh`: Linux hardware collector.
- `model-selector/README.md`: usage, coverage, and maintenance rules.
- `model-selector/hardware.*.example.json`: A100, A40, and RTX 4090 examples.

## Confirmed state

- Family catalog contains 83 model/size entries from 21 organizations.
- Deployment table contains 19 profiles with 33 fields.
- The catalog distinguishes permissive open-source licenses from open-weight
  model-specific licenses.
- Recommendations separate exact deployment profiles from capacity-only
  estimates so unverified image/version combinations are not presented as
  production-ready.
- Regression scenarios cover 8x A100 80GB, 14x A40 48GB, and 8x RTX 4090 48GB.
- Python compilation, CSV structure/unique IDs, PowerShell parsing, and the three
  recommendation scenarios passed at the last check.
- The XT 14xA40 dual-server handoff is loaded from
  `xt/大模型部署方案对比-2x7xA40.md` and the three per-model deployment guides:
  Kimi K2.6 (12 GPUs, TP=2 x PP=6), Qwen3.5-397B-A17B (8 GPUs,
  TP=4 x PP=2), and MiniMax M2.7 (two independent TP=4 replicas).
- The current practical recommendation is Qwen3.5-397B for the balanced strong
  model, Kimi K2.6 only after an A40 sm_86 performance validation, and M2.7 for
  the simplest/fastest redundant deployment. The optional 8+6 layout runs
  Qwen3.5-397B on the 8-GPU host and M2.7 on the 6-GPU host after physical
  power, cooling, slot, and topology validation.
- `xt/offline-xt/PACKAGE-STATUS.txt` says the non-model offline bundle and vLLM
  image are present and their static/load checks pass. Model weights are not
  included, and real A40 compat-libcuda/Triton/AWQ/Ray validation is pending.

## Key decisions

- Use a two-layer catalog: broad family discovery plus narrower deployable
  profiles.
- Treat model revision, quantization artifact, vLLM image/digest, driver/CUDA
  combination, parser, kernels, and real-GPU testing as one locked deployment
  unit.
- Do not claim that every community fine-tune or quantization repository is a
  separate supported model.
- Apply the workspace domestic-mirror-first policy before any model, image,
  wheel, source, or driver download.

## Current blockers

None.

## Next actions

1. When the user provides new hardware information, save it as a hardware JSON
   input and run `model-selector/recommend.py`.
2. Review both the exact recommendations and capacity-only discoveries with the
   user's workload, quality, throughput, multimodal, context, and license needs.
3. For the selected candidate, verify an exact domestic-mirror artifact and the
   vLLM compatibility stack before adding or promoting its deployment profile.
4. Feed real benchmark and acceptance results back into `models.csv` and update
   this memory.

## Do not repeat

- Do not rebuild the catalog from scratch.
- Do not treat capacity estimates as verified deployment profiles.
- Do not download model weights or images until exact hardware and selected
  candidates are known.

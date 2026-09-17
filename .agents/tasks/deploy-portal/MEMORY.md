# deploy-portal task memory

Status: active
Last updated: 2026-09-17 (Asia/Shanghai) - stage eight: the repository is
published to github.com/max-yangkun-min/llm_deploy, and the first cloud CI run
(which came back red) was diagnosed and fixed. Stage seven (Huawei Ascend dual-
ecosystem support + continuous integration / scheduled checks) is recorded below
and remains valid.

## User objective

Build a website that manages large-model deployment: given provided hardware
resources, recommend a suitable model deployment and give community-validated
deployment methods.

Follow-up requirement (2026-09-15): model entries should come from official
sites / Hugging Face (latest and most complete), and deployment methods should
point at authoritative sources rather than anything written from memory.

Follow-up requirement (2026-09-15, second): add a hard rule of minimal-feature
development - every control rendered in the UI must really work; never show a
placeholder button. The rule is 4.2 in `DEVELOPMENT.md`, the six violations it
caught and their fixes are 4.3 and 5.5.

Follow-up requirement (2026-09-17, third): every number the site shows must be a
real measured value, never an estimate. Stage five below replaced all estimated
catalog values with values read from the real artifact repository at a pinned
revision; `tools/apply_truth.py --check` now reports zero drift.

Deliverable requested (2026-09-15): a development document defining the tech
stack, the system boundaries, and the actual development progress. Written to
`deploy-portal/DEVELOPMENT.md` (v1.3). `README.md` stays user-facing and now
points at it.

Follow-up requirement (2026-09-17, fourth): hardware must be **chosen from a
list of GPUs**, not typed in; the result must be 3-5 plans that genuinely fit
the real hardware **without wasting VRAM**; and the old bias toward the local
plans (kty5l / xt / zc5s) must be removed in favour of whatever actually
matches. Implemented as stage six - see `DEVELOPMENT.md` 5.8.

Follow-up requirement (2026-09-17, fifth): "显卡加上华为系的" - add Huawei
Ascend GPUs. Implemented as stage seven; the spec is
`.codex-specs/ascend-gpu-catalog/spec.md`, design notes in `DEVELOPMENT.md` 5.9.
**Three cards are in the catalog; `910B`/`310P` are deliberately NOT** - see
"Ascend: what was verified" below.

Follow-up requirement (2026-09-17, sixth): reorganise the project around a
terminal-only workflow - `AGENTS.md` as the constitution, an SDD spec layer, a
project map, and **automation: turn the stable checks into a scheduled task /
CI**. Delivered as `tools/ci.py` + `scripts/ci/*` + `.github/workflows/ci.yml` +
`docs/CI.md` + `docs/PROJECT-MAP.md` + `.codex-specs/`. Two Windows scheduled
tasks are registered and verified (`llm-ci-daily`, `llm-ci-weekly`).

## Current deliverables

- `deploy-portal/server.py`: standard-library HTTP server, 11 routes
  (health, meta, gpus, catalog, recipes, deployments, hf-catalog, hf-detail,
  docs, recommend, check). `/api/presets` was removed when `/api/gpus`
  replaced it.
- `deploy-portal/engine.py`: adapter that imports `model-selector/recommend.py`
  as a library so recommendation rules exist in exactly one place. Also holds
  the declaration-vs-measured comparison logic.
- `deploy-portal/data/recipes.json`: 7 recipes + 11 verified domestic mirrors.
- `deploy-portal/data/deployments.json`: kty5l / xt / zc5s ledger.
- `deploy-portal/data/sources.json`: 2 endpoints, 41 organizations,
  28 tracked repos, 37 doc sources.
- `deploy-portal/data/catalog-verified.json`: verification cache, 95
  repositories with pinned revision + endpoint; written by `apply_truth.py` so
  the catalog rewrite is reproducible offline.
- `deploy-portal/data/hf-catalog.json`: generated snapshot, 24,409 index
  entries / 41 organizations / 19 detailed repos / 1 recorded error.
- `deploy-portal/data/doc-sources.json`: 56/56 sources reachable, 0 failures.
- `deploy-portal/data/gpu-catalog.json`: 12 GPUs, 12/12 verified. Every card
  carries the vendor product-page URL, HTTP status, body sha256, check date,
  `vram_basis` and a `failed` list. Written by `tools/sync_gpus.py`.
- `deploy-portal/web/`: dependency-free front end, 6 views.
- `deploy-portal/tools/`: `sync_hf.py`, `sync_docs.py`, `sync_gpus.py`,
  `smoke_test.py`, `apply_truth.py`, `apply_patch.py`,
  `whole_file_replace.py`.
- `deploy-portal/DEVELOPMENT.md` (v1.3): tech stack, boundaries (including the
  4.2 minimal-feature hard rule), progress, gotchas, changelog.
- `deploy-portal/README.md`: usage, API, maintenance rules, boundaries.

## Confirmed state

- Start with `python deploy-portal/server.py --port 8787 --open`; no packages,
  no network needed for the site itself.
- Smoke test passes 76/76 checks: 12 anti-regression checks for fake controls,
  6 that assert every catalog row carries a pinned revision, a
  machine-readable license id, a context-value source and a measured weight,
  and 13 more for stage six (GPU catalog integrity, plan count 3-5, no
  duplicate models, every plan carries a full memory breakdown, occupancy
  <= 90%, single-card case, unverified retrofit cards in the ledger, `gpu_id`
  required, unknown GPU 404, no caller-supplied VRAM, static assets no-store,
  front-end module braces balanced).
- 56/56 authoritative sources reachable (37 registered + 19 model cards).
- `--repair` and `--org` both work; `--org` no longer falls back to a full run.
- Playwright-verified: the 6 views render. Screenshots in `output/playwright/`.
- Reference integrity holds: no dangling `profile_id`, no dangling recipe ids,
  every recipe has `sources`, every ledger `selected_profile` resolves.
- Deliberately NOT copied: `models.csv`, `model-families.csv`, `hardware*.json`.

## Key decisions

- Reuse, do not reimplement: `engine.py` imports `recommend.py` rather than
  duplicating the hard-constraint and scoring logic, so the CLI and the site can
  never disagree.
- Declaration values (`models.csv`) and measured values (HF snapshot) are shown
  side by side and never merged. Only repositories whose quantization class
  matches the profile are used for weight comparison; others are listed and
  flagged `is_reference: false`.
- Capacity-only estimates stay visually separate and can never be presented as
  production-ready.
- Fetch failures are never dropped silently; they land in the snapshot's
  `errors` field and are rendered on the page.
- Do not copy third-party page content. `doc-sources.json` stores only URL,
  HTTP status, content fingerprint and title.
- Server binds `127.0.0.1` only; single-user local tool, no auth.

## Stage three this session: four root causes fixed (all found by real fetches)

1. Large response truncated by the mirror at roughly 360KB, surfacing as a JSON
   parse error rather than an HTTP error. Fix: halve `limit` on truncation,
   floor 25, page via cursor.
2. First-page timeout was treated as "organization has no models". Fix: halve
   the page size and retry before giving up.
3. Still truncated at the minimum page size because the bottleneck is per-record
   `cardData` size. Fix: `LEAN_EXPAND_QUERY` fallback without `cardData`;
   license still readable from the `license:` tag prefix. Also stop the lean pass
   from overwriting an already-fetched license with null.
4. `get_raw()` had no retry at all, so `config.json` timeouts left entries
   permanently "incomplete" and `--repair` re-fetched them forever. Fix: add
   retry, then fall back to the identical `config` object returned by
   `/api/models/<repo>`.

## Stage four this session: minimal-feature rule + six fake controls fixed

The site loaded, every API returned 200, and the controls still did nothing.
Six real cases were found and fixed (full table in `DEVELOPMENT.md` 4.3):

1. Task-type dropdown had only the "all" option: the mirror list API treats
   `expand` as a whitelist, so undeclared `pipeline_tag` / `tags` / `likes`
   were never returned. Fix: added them to `EXPAND_FIELDS` + `expand_query()`.
   Facets went from 1 to 50 task types and 47 licenses.
2. "Likes" sort never changed anything: `likes` was null everywhere, same root
   cause. Now 100% of the 24,412 index entries carry likes.
3. Model library could only show the first 100 rows: the API supported
   `offset` but the view had no pager. Fix: 50 per page + prev/next, reset to
   page one when a filter changes.
4. "View deployment plan" crashed the whole view: `recipes.json` used the key
   `verification` for the acceptance checklist while `server.py` used the same
   key for repo verification results (array vs object), so `.map` threw. Fix:
   checklist renamed to `acceptance` (7/7 records), front end reads that key.
5. "Multimodal only" / "permissive license only" only filtered the profile
   table, never the family table. Fix: `PERMISSIVE_LICENSES`,
   `NON_TEXT_MODALITIES`, `is_multimodal_family()` (modality split on `;`);
   both tables now narrow (19->4 / 83->15).
6. Permanent `favicon.ico` 404 in the console: only `favicon.svg` existed.
   Fix: `server.py` serves the svg for that path.

Verification: all six views were clicked through with Playwright (query, org,
task, license, sort, prev/next, both copy buttons, JSON export, reset, load
example, view plan, ledger check) - 0 console errors, 0 warnings. Screenshots
in `output/playwright/`.

## Stage five this session: catalog numbers replaced by measured values

User requirement (2026-09-17): every displayed number must be real. The catalog
was not hand-edited; a re-runnable tool now derives the numbers from artifacts.

- New `deploy-portal/tools/apply_truth.py` (423 lines). `--check` only reports
  differences, no argument writes back from the verification cache, `--refresh`
  re-fetches upstream. Values come from `data/catalog-verified.json` (95 repos,
  each with revision + endpoint), so the rewrite reproduces offline.
- `model-selector/models.csv` (19 profiles) and `model-families.csv` each gained
  six columns: `verified_repo`, `verified_revision`, `verified_endpoint`,
  `verified_at`, `artifact_params_b`, `license_id`, `context_source`.
- Weight corrections (each traceable to a pinned revision): GLM-5.2 INT4 410 ->
  441.7 GiB; Kimi-K2.6 AWQ 500 -> 554.3; DeepSeek-V3.1 INT4 350 -> 370.8;
  Qwen3.5-397B AWQ 200 -> 227.6; Qwen3-235B AWQ 135 (was flagged "community
  estimate") -> 115.5; MiniMax-M2.7 AWQ 115 -> 121.3; Qwen3.5-122B AWQ 68 ->
  76.5; Qwen3-Coder-30B AWQ 18 -> 15.7; Qwen3-32B AWQ 19 -> 18; Qwen3-14B AWQ
  9 -> 9.3; Qwen3-8B 16 -> 15.3 (BF16) and 5 -> 5.7 (AWQ); Qwen3-4B BF16 8 ->
  7.5.
- Context corrections: GLM-5.2 128K -> 1024K; Qwen3 family 32K -> 128K (32K
  native + YaRN, `context_source=card`); Qwen3.5 / Kimi-K2.6 / Qwen3-235B
  64-128K -> 256K; MiniMax-M2.7 64K -> 192-200K; DeepSeek 128K -> 160K; Yi-1.5
  32K -> 4K and InternVL3 128K -> 32K (the old values had no basis).
- License corrections: Qwen2.5 profiles Apache-2.0 -> Qwen License / Qwen
  Research License; Kimi / MiniMax -> Modified MIT / vendor terms.
- Structural defect solved: `deepseek-r1-bf16` pointed at the official
  `deepseek-ai/DeepSeek-R1`, which ships FP8 only (641.3 GiB). It now points at
  `unsloth/DeepSeek-R1-BF16` (1275 GiB), so the declared/measured pair agrees.
- Two parameter-count conventions are kept in separate columns rather than
  merged: official headline count vs artifact measured (`artifact_params_b`).
  DeepSeek ships MTP layers, about +2%.
- Quantization class of all 19 profiles re-derived from `safetensors` dtypes:
  0 mismatches.
- The one item that could not be verified: `databricks/dbrx-instruct` is gated
  upstream (HTTP 401), so the community mirror `alpindale/dbrx-instruct` was
  used and cross-checked against `LnL-AI/dbrx-base-converted-v2` (both give
  131.6B / 245.1 GiB). Its license is recorded as "未能核实" with the reason in
  `notes`.

Verification: `apply_truth.py --check` -> 0 changes, 0 unverified, 0
quantization mismatches, 28 rows legitimately keeping the model-card context.
`smoke_test.py` -> 63/63. Playwright re-run over the 6 views -> 0 errors,
0 warnings; screenshots in `output/playwright/`.

## Environment defects worth remembering

1. `apply_patch` on this machine is a `.bat` wrapper. Calling it from PowerShell
   mangles a backslash-immediately-followed-by-double-quote sequence inside the
   patch text, which either fails validation or silently corrupts written files.
   Use `python deploy-portal/tools/apply_patch.py <patch-file>` instead; it builds
   argv via subprocess and rejects any patch whose last line is not exactly
   `*** End Patch`. One file may hold only one Begin/End block.
2. The PowerShell console code page garbles Chinese output. Set
   `PYTHONIOENCODING=utf-8` (or read files with `Get-Content -Encoding UTF8`).
3. New this session: a stale server process from an earlier session can hold
   `127.0.0.1:8787` **simultaneously** with a fresh one, so requests get served
   by the old code and look like "404 / page failed to load". Diagnose with
   `netstat -ano | Select-String ':8787.*LISTENING'`, compare `StartTime` via
   `Get-Process -Id <pid>`, and stop the older one.
4. Piping a long-running Python check through `Select-String` or
   `Measure-Object` can kill it with a broken pipe: the count comes back short
   and the exit code is 1 even though nothing failed. Redirect to a file and
   count from there (`python ... > .tmp/out.txt 2>&1`).

## Stage six this session: hardware catalog + real VRAM accounting

1. `tools/sync_gpus.py` (new) verifies 12 GPUs. A card is only admitted if its
   VRAM capacity / memory type / interconnect appear **verbatim** in the vendor
   product page body, and its compute capability appears in the matching tier
   of NVIDIA's official CUDA-Enabled GPUs table. Anything that misses is marked
   `failed` with the reason - never filled in from memory. Cards whose product
   page is gone (A800 / H800 / L20 / A10 / A30 / V100) are not admitted at all.
   `b200-180` derives 180 GiB from the DGX B200 1440 GiB / 8 (the page only
   gives the chassis figure); that basis is recorded in `vram_basis`.
2. `sync_hf.py` gained `attention_shape()` plus nested-config parsing
   (`text_config` / `llm_config` / `language_config` / `decoder_config`), so 18
   of 19 profiles now carry real attention structure. Only
   `llama31-405b-bf16` cannot (gated 401 everywhere) and is left blank.
3. Three KV conventions, and they must NOT be unified into one formula:
   - `mla`: `kv_lora_rank + qk_rope_head_dim`, shared across heads, **no x2**
     (DeepSeek family, GLM-5.2, Kimi-K2.6 - all 576).
   - `hybrid-linear`: only `full_attention` layers count
     (`2 x kv_heads x head_dim`; Qwen3.5-397B 15 of 60 layers, 122B 12 of 48).
   - `gqa`: `2 x kv_heads x head_dim x layers`.
   Treating hybrid-linear as dense inflates Qwen3.5 KV ~4x; treating MLA as GQA
   doubles DeepSeek KV.
4. `recommend.py` now has `kv_gib()` and `assess()` as the single decision
   entry point. `assess()` returns the full `memory` breakdown
   (weight / kv / kv_context_k / kv_basis / attention_kind /
   runtime_overhead_ratio / needed / per_card / tp / cards /
   engaged_vram / utilization / waste / replicas / kv_verified).
   Only three constants are engineering assumptions and are labelled as such in
   the UI: `KV_DTYPE_BYTES=2.0`, `RUNTIME_OVERHEAD=0.10`, `PER_CARD_BUDGET=0.92`.
5. Scoring no longer reads `validation_status` at all - that was the local-plan
   bias. `has_recipe` (+3, comes from `apply_truth.py` reading `recipes.json`,
   so CLI and site share one judgement) is the only bonus. A VRAM-utilisation
   term was added: below `LOW_UTILIZATION=0.45` is penalised (the plan is too
   small for these cards), above `HIGH_UTILIZATION=0.90` is penalised (no
   headroom). Thresholds are shared with the warnings so the two can never
   disagree. Qwen3-Coder-30B-AWQ used to reach the top 3 on 8 x A100 at 26%
   occupancy; it is now demoted and GLM-5.2 INT4 (76%) leads.
6. If the driver field is left blank, a profile with a driver floor no longer
   silently passes; it emits "this profile needs driver >= X, none supplied,
   confirm before going live".
7. `/api/recommend` requires `gpu_id` and ignores any caller-supplied
   `vram_per_gpu_gib` - otherwise a user could type a number and bypass the
   fit check. `/api/check` uses `require_verified=False` so the ledger can
   carry on-site hardware (e.g. the 48 GB retrofit 4090) and reports
   `hardware_verified` / `hardware_gpu_name`.
8. `deploy-portal/tools/whole_file_replace.py` (new) does chunked whole-file
   replacement through `apply_patch.py`, verified byte-for-byte with rollback.

## Serious defect fixed this session (worth remembering)

`web/js/views/recommend.js` lost its final closing brace during a whole-file
replacement. Symptom: **the page sits on "loading..." forever while every API
returns 200**. Chrome only reports `SyntaxError: Unexpected end of input` with
no position, and `node --check` does NOT catch it (it does not resolve relative
ES imports). Diagnosis: `import()` each view module inside the page and see
which one throws. Root cause was the throwaway tool's
`text.split("\n")[:-1]`, which silently drops the last line when the new file
has no trailing newline. Fixed, and a static brace-balance assertion was added
to `smoke_test.py::module_syntax()`.

Also fixed while verifying: static assets had no `Cache-Control`, so the browser
heuristically cached JS/CSS and kept running old code after edits. Static
responses now send `no-store` (asserted by the smoke suite).

## Current blockers

None.

## Ascend: what was verified, and what was refused (stage seven)

Verification paths that actually worked (both tested, not assumed):

- `www.hiascend.com` **fails local SSL chain verification** on this machine
  (Python 3.8 has no `cert.pem`). Do NOT use certifi and do NOT disable
  verification. `sync_gpus.py::fetch()` keeps verification ON and, only when the
  failure is a certificate error, falls back to the same site official
  **http** entry, recording the fallback in the snapshot `transport` field.
  Non-certificate errors (404/timeout) never fall back.
- `e.huawei.com` uses the system trust store and works over https normally.

Cards in the catalog (every marker matched verbatim on the vendor page):

| Card | Vendor page | Markers matched | VRAM |
|---|---|---|---|
| Atlas 350 accelerator (Ascend 950PR) | `www.hiascend.com/hardware/accelerator-card` | `112 GB HBM`, `PCIe 5.0 x16`, lingqu multi-card interconnect | 112 GiB HBM |
| Atlas 300I Duo | `e.huawei.com/cn/products/computing/ascend/atlas-300i-duo` | `LPDDR4X 96GB或48GB`, `280 TOPS INT8`, `408GB/s` | 96 / 48 GiB LPDDR4X |

- Atlas 350 page states support for HiF8/mxFP8/mxFP4, so FP8 is `true` **from the
  vendor page**, not derived. Atlas 300I Duo page has no FP8 wording, so
  `fp8_supported: false` with basis "official page does not state it".
- Atlas 300I Duo page does **not** name a chip. `architecture` is blank with an
  `architecture_basis` note. Do not fill it from memory.
- That page lists 96GB and 48GB on the **same line**, so both capacities are
  separate entries. Do not merge them.

**`910B` and `310P` are NOT in the catalog.** Exhausted: all tabs of
`/hardware/accelerator-card`, `/hardware/ai-server`, `/hardware/processor`,
`/hardware/cluster`, `/llms-content/*.md`, plus
`e.huawei.com/cn/products/computing/ascend/atlas-800t-a2` (that page matches
`HBM`, `显存` and `910` **zero** times - it is a JS shell) and support.huawei.com.
`910B4` matches 0 times anywhere. The only "64 GiB/card" figure in existence here
is this workspace own README (`deepseekv4-flash/offline-dsv4-0731/`), which is
**not** vendor evidence. The site now ships the 950 series instead. If someone
asks for 910B again, find an official archived spec page first.

Real Ascend deployment assets in the workspace (usable, just not yet a recipe):
`deepseekv4-flash/offline-dsv4-0731/` - TP8+EP, `--quantization ascend`,
`--max-model-len 65536`, speculative dspark/7, image
`quay.io/ascend/vllm-ascend:nightly-main` (vLLM 0.26.0 / CANN 9.0.1 / torch_npu),
model `Eco-Tech/DeepSeek-V4-Flash-0731-w8a8` rev `9e8679a9...`. **910B4 has not
been accepted on real hardware yet** (`models/` still only holds
`PUT-MODEL-HERE.txt`), so it cannot become a recipe.

## Continuous integration (stage seven)

- `tools/ci.py` is the **single** gate implementation: 10 offline checks + 2
  online. Exit code = number of failures. `SKIP` is reported separately and is
  **not** a pass, because a check that never ran must not look like one that did.
  (This line said 8 and the table in `docs/CI.md` was missing two rows. Both are
  corrected; the table now lists every check the gate actually runs.)
- `scripts/ci/run-ci.ps1` wraps it and leaves logs in `output/ci/`
  (`ci-latest.log`, `ci-latest.json`).
- `scripts/ci/register-scheduled-task.ps1` registers `llm-ci-daily` (offline
  daily) and `llm-ci-weekly` (online weekly). Registered and verified:
  `LastTaskResult = 0`.
- `.github/workflows/ci.yml` runs the offline gate on push/PR. The first real run
  (push `17331d0`, 2026-09-17 09:24 UTC, run 35204924376) came back **failure**.
  Cause and fix are in stage eight below.
- Two lessons baked into the runner, both learned by getting them wrong first:
  1. Detecting that `bash` exists is **not** the same as that usage working. The
     bare `bash` here is WSL /bin/bash, which needs /mnt/d/... paths. The first
     version probed only `bash -c "echo ok"`, passed, then failed every script on
     paths. It now probes the real usage and tries both path styles.
  2. Third-party trees (`.vendor-fetch-cutlass-v4.4.2`, `source-cache`) must be
     excluded from the gate. Gating on downloaded code makes CI permanently red
     and trains everyone to ignore it - worse than having no CI.

## Stage eight this session: repository published, first cloud CI run red

- Published `main` to `https://github.com/max-yangkun-min/llm_deploy.git`; the old
  `origin` pointed at `.../llm`, which 404s. First push into an empty repository,
  so `git push -u origin main` was the whole job.
- Two real hazards were closed before pushing, both found by inspecting the index
  instead of trusting `.gitignore`:
  1. `git add -A` would have swallowed 12.4 GiB of local artifacts - the 6225.67 MB
     `offline-dsv4-0731-with-image-no-weights-*.tar.gz`, two split image volumes
     (`*.tar.part01` 4386.9 MB / `*.tar.part02` 1682.35 MB) and two ~37 MB vendor
     source tarballs. `.gitignore` only matched `**/images/*.tar`, which never
     matches a `.tar.partNN` volume. Added `*.tar.gz`, `*.tar.zst`, `*.tar.xz`,
     `*.tar.part*`, `**/images/*.tar.*`, `**/vendor-sources/*.tar.gz|*.tgz` and
     re-verified each of the five files with `git check-ignore -v`.
  2. The index carried two mode-`160000` gitlinks pointing at commits that do not
     exist locally (`kty5l/.vendor-fetch-cutlass-v4.4.2` -> `da5e086dab31...`,
     `kty5l/source-cache/vllm` -> `ee0da84ab9...`). Removed from the index with
     `git rm --cached -f -r` (the local checkouts stay on disk) and ignored.
     Pushing them would have created submodule references nobody can initialise.
- What was published: 229 files, 57.3 MB, nothing over 50 MB, and no credentials
  (152 text files scanned for `sk-*`, `ghp_*`, `openai_pat_*`, `AKIA*`, private
  keys, `hf_*`).
- The cloud run was red. Logs and artifacts need auth (401/403), so the failure was
  reproduced locally instead. **The reproduction method matters:** `git archive`
  here honours `core.autocrlf=true`, which rewrote every exported text file to CRLF
  and invented three `bash -n` failures. Only
  `git -c core.autocrlf=false archive` (or a real Linux clone) shows what the
  runner sees; on a faithful tree exactly one check failed, the same count as the
  cloud run.
- Root cause: `deploy-portal/tools/apply_patch.py` hard-coded one Windows
  `codex.exe` path and exited when it was missing. On `ubuntu-latest` there is no
  codex, so `whole_file_replace.py` - and with it the whole "改文件工具" gate -
  could never pass. That is precisely the permanently-red-gate failure mode this
  project already warns about.
- Fix (spec `.codex-specs/ci-portability/`): two patch backends. `codex` is used
  when a **runnable** codex is found - `shutil.which` plus a platform-agnostic npm
  vendor glob, then a real `codex --version` probe, because file existence is not
  usability (WSL proved it: the Windows npm `codex` wrapper that PATH exposes dies
  with `exec: node: not found`). Otherwise the built-in strict engine runs: it
  matches context byte-for-byte, rejects unknown directives, refuses to guess an
  insertion position, and writes only after every operation has been resolved.
  `--backend auto|codex|builtin` or `LLM_DEPLOY_PATCH_BACKEND` selects it, and an
  explicit `--backend codex` that cannot run fails loudly instead of silently
  switching backends.
- `tools/apply_patch.py` was a byte-identical second copy of the same script
  (sha256 `4ee22af60cca05f2`). It is now a forwarder to the single implementation,
  so both documented paths keep working with one behaviour.
- The gate now covers both backends: `改文件工具` runs three real round-trips
  (whole-file replace on the default backend, whole-file replace on the built-in
  engine, add-file on the built-in engine) and checks the bytes. Testing only the
  machine's default backend is how the other one regresses unnoticed.
- New check `Shell 脚本行尾`: indexed `.sh` content must be LF. A CRLF shell script
  on Linux does not fail politely - it sprays `$'\r': command not found`, which is
  the kind of defect that costs a site visit. It reads blobs via
  `git cat-file --batch`, not the working tree, because `core.autocrlf=true` makes
  a working-tree check false-positive.
- Verified: Windows `python tools/ci.py` -> 10 pass / 0 fail / **0 skip** when the
  process can reach WSL (the bare `bash` here is WSL; with the distro reachable the
  shell-syntax check really runs - 21 scripts, path style posix). Inside the agent
  sandbox WSL is blocked (`E_ACCESSDENIED`) and the same check honestly reports
  `SKIP`, which is why a sandboxed run shows 9/0/1. WSL Ubuntu itself (real Linux,
  same tree) -> 9 pass / 0 fail / 1 skip, `EXIT=0`; there the skip is
  `C: 盘可用空间`, because `C:/` does not exist on Linux. Negative control:
  re-applying an applied patch makes the built-in engine report "原文对不上" and
  exit 1 without touching the file.
- Lesson worth keeping: a patch may hold several `@@` hunks, and **each hunk is
  searched forward from the end of the previous one**. Order hunks by position in
  the file; reversed order makes the later hunk report "expected lines not found"
  even though the text is right there. That cost one rejected `docs/CI.md` patch.

## Next actions

1. **Run `python tools/ci.py` after every change** (seconds, offline) and
   `python tools/ci.py --online` before wrapping up. Both scheduled tasks
   already do this; see `docs/CI.md`.
2. Optional: `python deploy-portal/tools/sync_hf.py --repos-only` to refresh the
   28 tracked repositories, then `apply_truth.py --refresh` to re-derive values.
3. Decide whether `deepseek-ai/DeepSeek-V4.1-Flash` should replace the tracked
   `DeepSeek-V4-Flash-0731`.
4. If the user gives real hardware JSON, run it through the hardware page and then
   verify the chosen candidate's exact domestic-mirror artifact before promoting
   its recipe status.
5. Optional, only if asked: decouple `hf-catalog.json` size from first paint,
   add an `organization_kind` filter, add a hardware comparison view.
6. Documentation is up to date at v1.4 (`DEVELOPMENT.md`), plus `docs/CI.md`
   and `docs/PROJECT-MAP.md`. If you change behaviour, the rule is: update the
   spec (`.codex-specs/<feature-id>/`) and add an assertion, not just the prose.
7. Backlog worth doing when asked: derive the maximum context a card can hold at
   a given model (currently the user supplies context and there is no warning
   when KV is near the VRAM ceiling), and expose `--kv-cache-dtype fp8`
   (KV is currently always costed at 2 bytes).
8. If a GPU whose vendor page has gone offline must be supported (A800 / H800),
   find an official archived spec page first; do not add it from memory.

## Do not repeat

- Do not copy `models.csv` / `model-families.csv` / `hardware*.json` into
  `deploy-portal/`; read them from `model-selector/`.
- Do not add third-party front-end or server dependencies; the standard library
  and vanilla ES modules are a deliberate constraint.
- Do not mark `provisional-local` or `candidate` profiles as verified without
  real on-GPU acceptance.
- Do not compare declared values against repositories of a different
  quantization class; that produced a misleading 242% "deviation" earlier.
- Do not let a targeted sync mode fall back to the full organization list; one
  `--org` must never become a ten-minute full run.
- Do not let hardware be typed in on the site, and do not accept a
  caller-supplied `vram_per_gpu_gib` on `/api/recommend`: the whole point of
  stage six is that the fit check uses verified vendor specs.
- Do not unify the three KV conventions into one formula, and do not fill in a
  KV structure you could not verify - leave it blank and say "weight lower
  bound only".
- Do not reintroduce scoring based on `validation_status`; that is the local-plan
  bias the user explicitly asked to remove.
- Do not hand-edit GPU specs. A card either matches the vendor page and the
  official CUDA table, or it is marked `failed` and left out.
- Do not do a whole-file replacement with a throwaway script; use
  `tools/whole_file_replace.py`, which verifies byte-for-byte and rolls back.
- Do not render a control that has no binding, no data, or no visible effect.
  A dropdown whose only option is "all", a sort that never changes order, and a
  button that throws are all dead controls - fix the data or remove the control
  (rule 4.2, checked by `smoke_test.py::dead_controls` and the 63-item suite).
- Do not hand-edit a number in `models.csv` / `model-families.csv`. Every value
  must carry a `verified_repo` + 40-character `verified_revision`, so it has to
  come from `apply_truth.py`; otherwise `smoke_test.py` fails it.
- Do not use a repository of a different quantization class as the reference for
  a profile, and do not merge the two parameter-count conventions into one
  column.
- **Do not map Ascend onto `sm_xx`.** sm is an NVIDIA-only scale. Leave
  `compute_capability` null with a `compute_capability_basis` note, and never
  verify an Ascend card against the NVIDIA CUDA table - that is fake verification.
- **Do not derive FP8 from compute capability for a non-CUDA card.** Read
  `fp8_supported` from the catalog; if it is absent on a non-CUDA card the answer
  is "cannot determine", never "not supported" (that is how a card whose vendor
  page lists HiF8/mxFP8 gets reported as having no FP8).
- **Do not attach a CUDA-stack recipe to an Ascend card**, and do not silently
  default a missing `ecosystem` to cuda on the on-site registration path.
- **Do not weaken an assertion to make CI green.** If the assertion is wrong, fix
  it and say why; if the code is wrong, fix the code. And do not let a `SKIP` pass
  as a `PASS` - a check that never ran must be reported as skipped.
  column.

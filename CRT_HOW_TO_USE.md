# CRT (Truthful Personal AI) — How To Use (Rolling)

This is a living "how-to" for the CRT side of this repo: background jobs, promotion proposals, approvals, and applying approved changes.

## Where we are
- CRT core + stress harness: stable and reproducible (seeded batches used as regression gate).
- Background learning loop: jobs queue + worker produces schema-valid artifacts.
- Human-in-the-loop learning: proposals → decisions → apply (no silent promotions).

## Key concepts (very short)
- **Artifacts**: JSON files that are schema-validated (contracts). They’re the audit trail.
- **Proposals**: candidate memory updates produced by background jobs (NOT automatically applied).
- **Decisions**: explicit approve/reject/defer records (human action).
- **Apply**: the only step that writes approved items into a memory DB.

## Quickstart commands (Windows)

### 1) Run a stress regression (recommended gate)
- `D:/AI_round2/.venv/Scripts/python.exe crt_adaptive_stress_test.py --turns 200 --runs 3 --seed 1337 --challenge-pack all --artifacts-dir artifacts/adaptive_smoke --fresh`

Expected results:
- A batch summary artifact written under the `--artifacts-dir`.
- Pass rate should remain ~100% for known-good seeds unless you intentionally tighten checks.

### 2) Enqueue + run a background job (once)
The worker uses `crt_jobs.db` and writes job artifacts.

- Demo job:
  - `D:/AI_round2/.venv/Scripts/python.exe crt_background_worker.py --db artifacts/crt_jobs.db --artifacts-dir artifacts --enqueue-demo --once`

- Generate promotion proposals from a memory DB:
  - `D:/AI_round2/.venv/Scripts/python.exe crt_background_worker.py --db artifacts/crt_jobs.db --artifacts-dir artifacts/live_promotions --enqueue-propose-promotions --memory-db artifacts/crt_live_memory.db --once --job-id livepromos-YYYYMMDD`

Expected results:
- Job artifact: `artifacts/.../background_jobs/job.<job_id>.json`
- Proposals artifact: `artifacts/.../promotions/proposals.<job_id>.json`

### 3) Review proposals and save decisions (UI)
- `streamlit run crt_dashboard.py`
- Go to **✅ Promotion Approvals**
- Point it at the artifacts root you used (e.g. `artifacts/live_promotions`)
- Save decisions artifact (approve/reject/defer)

Expected results:
- Decisions artifact is created under `<artifacts root>/approvals/decisions.<job_id>.<timestamp>.json`

### 4) Dry-run apply (no DB writes)
- `D:/AI_round2/.venv/Scripts/python.exe crt_apply_promotions.py --memory-db artifacts/crt_live_memory.db --proposals artifacts/live_promotions/promotions/proposals.*.json --decisions artifacts/live_promotions/approvals/decisions.*.json --dry-run --artifacts-dir artifacts/live_promotions`

Expected results:
- Apply result artifact under `<artifacts dir>/promotion_apply/apply_result.<timestamp>.json`
- Output summary reports **Would apply / Skipped / Errors**

### 5) Apply for real (writes to DB)
Strong recommendation: apply to a sandbox DB first.

- Make a sandbox copy:
  - `Copy-Item -Force "D:\\AI_round2\\artifacts\\crt_live_memory.db" "D:\\AI_round2\\artifacts\\crt_live_memory.sandbox.db"`

- Apply:
  - `D:/AI_round2/.venv/Scripts/python.exe crt_apply_promotions.py --memory-db artifacts/crt_live_memory.sandbox.db --proposals artifacts/live_promotions/promotions/proposals.*.json --decisions artifacts/live_promotions/approvals/decisions.*.json --artifacts-dir artifacts/live_promotions`

Expected results:
- Same apply result artifact output, but now `Applied: N` can be non-zero.
- New memory rows are inserted with provenance stored in `context_json`.

## Feature inventory (rolling)

### Background worker
- Jobs DB: `artifacts/crt_jobs.db`
- Worker: `crt_background_worker.py`
- Implemented job types:
  - `summarize_session` (demo stub)
  - `propose_promotions` (produces promotion proposals artifact)

### Promotion workflow
- Proposals schema: `crt_promotion_proposals.v1.schema.json`
- Decisions schema: `crt_promotion_decisions.v1.schema.json`
- Apply result schema: `crt_promotion_apply_result.v1.schema.json`
- Apply CLI: `crt_apply_promotions.py`
- Apply logic: `personal_agent/promotion_apply.py`

### Deterministic gates (runtime safety)
- Gate-style hard refusals/acknowledgements exist to prevent certain adversarial failure modes (system prompt exfiltration, name declaration embellishment).

## Config surface (runtime)
The strict runtime config schema is `crt_runtime_config.v1.schema.json`.

What matters most operationally:
- `learned_suggestions.*`: controls whether training/learning metadata is emitted.
- `provenance.enabled`: whether provenance behaviors are enabled.
- `reflection.*`: output paths and thresholds for reflection/training runs.
- `assistant_profile.*` and `user_named_reference.*`: deterministic response templates.
- `onboarding.*`: whether onboarding questions run automatically.

## How we test going forward (practical)
- **Fast gate**: `python -m pytest -q`
- **Runtime truth gate** (when you touch query/memory behavior): a seeded stress batch (example in Quickstart #1)
- **Artifacts contract gate**: schemas should reject unknown fields (fail closed) and tests should enforce it

## Expected results / invariants
- No silent promotions: only an explicit decisions artifact + apply step can write durable changes.
- Everything is auditable: proposals/decisions/apply_result are all schema-valid JSON artifacts.
- Dry-run is safe and repeatable.

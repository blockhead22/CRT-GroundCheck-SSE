# CRT Thread Handoff Save (2026-01-15)

This file is a **portable handoff snapshot** so another agent (or future-you) can resume exactly where work paused.

## 0) Current state (what is done)

Delivered in this repo now:
- HTTP-first runtime: FastAPI backend in [crt_api.py](crt_api.py) with chat, jobs, and contradictions endpoints.
- Web UI control plane: Vite/React app in [frontend/](frontend/) wired to the API (Chat/Docs/Dashboard/Jobs).
- Background autonomy (durable + auditable): SQLite jobs queue + worker loop + idle scheduler + job events/artifacts logging, surfaced via `/api/jobs/*` and the Jobs page.
- M2 loop (“contradictions become goals”) is implemented end-to-end:
  - `GET /api/contradictions/next`
  - `POST /api/contradictions/asked`
  - `POST /api/contradictions/respond`
  - Frontend dashboard panel to ask/record/resolve.
- Stress harness supports API-mode execution via `POST /api/chat/send` and long runs.

## 1) Latest long-run evidence

- Latest report: [artifacts/crt_stress_report.20260115_093355.md](artifacts/crt_stress_report.20260115_093355.md)
- Raw run log: [artifacts/crt_stress_run.20260115_093355.jsonl](artifacts/crt_stress_run.20260115_093355.jsonl)
- Headline metrics (from the report header):
  - Turns: 300
  - Gates: pass=124 fail=176
  - Contradictions detected: 5

Important observed issue:
- Stress harness M2 followups reported attempted > 0 but succeeded = 0. This strongly suggests silent HTTP failures or an exception path without surfaced logging.

## 2) Roadmap alignment (where we are)

- Milestone M2 (“contradictions become goals”) is implemented, but acceptance criteria is not yet proven in long runs because the harness followup loop isn’t currently succeeding.
- Background tasks (jobs queue, worker, UI) are implemented and auditable (good alignment with M4 “background task agent”).
- Research-mode evidence packets and strict provenance UX are still largely roadmap items (M3).

## 3) Next steps — “1–15 pause”

1) Fix observability of M2 followups in [crt_stress_test.py](crt_stress_test.py): log status code + response body for every followup request (next/asked/respond).
2) Make followup failures non-silent: treat non-2xx as failure with a captured error message in the JSONL run record.
3) Add a tiny API smoke-run mode (e.g. `--m2-followup-only`) that does: create contradiction → next → asked → respond and exits with clear pass/fail.
4) Verify the frontend M2 flow against a real contradiction (manual): open Dashboard → Next contradiction panel → record answer → resolve → verify ledger status changes.
5) Reconcile evaluator expectations for “contradiction inventory” prompts: allow `contradiction_detected=True` when the user explicitly asks about contradictions.
6) Improve long-run “padding” behavior: ensure padding prompts don’t accumulate junk memories and don’t steer identity facts.
7) Target gate pass rate: identify which gate(s) are failing in long runs and whether those are true failures vs overly-strict heuristics.
8) Reduce false contradictions further: sharpen “question vs assertion” classification and claim-level slot matching (avoid semantic drift triggers on non-claims).
9) Add metrics trend reporting: batch runs (N seeds) that produce a single summary artifact with pass rates + contradiction rates.
10) Make learned-model publishing controlled (train → eval → publish) using the existing scripts; define minimum thresholds and write a publish artifact.
11) Add an “audit answer record” write on every API chat response (even a lightweight JSONL) so “why did you say that?” has a durable trace.
12) Formalize permissions for background jobs: permission tier per job type, default-deny for tool-using jobs.
13) Start M3 research/evidence packets on the API path: `search → fetch → quote → summarize` with citations stored as quarantined notes.
14) Wire evidence packets into the UI inspector (view citations/quotes alongside answers).
15) Re-run a 300-turn campaign after (1–8) and compare to the 20260115 baseline; only then expand to multi-run batches.

PAUSE: stop here until M2 followups are observable and the 300-turn baseline improves measurably.

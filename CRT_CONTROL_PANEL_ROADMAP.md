# CRT Control Panel + Background Learning (Local‑First) — Architecture & Roadmap

## Current status (Jan 12, 2026)

Delivered and working in this repo now:
- Control Panel (Streamlit) supports end-to-end **human-in-the-loop promotions**: proposals → decisions → dry-run apply → sandbox apply → gated real apply, with artifacts written for audit.
- Chat UI (Streamlit) is available and can run with an optional local LLM backend (Ollama).
- Deterministic safety/grounding gates have regression coverage (notably name declaration + false-contradiction hardening).
- Learned “suggestions-only” model is now observable over time:
  - training writes `*.meta.json`
  - evaluation writes `*.eval.json`
  - dashboard plots timelines and compares two models (including confusion matrices)

Immediate focus:
- Turn “learning” into a controlled release process: **train → eval → publish latest** with explicit thresholds and artifacts.

This document describes a local-first architecture for a **truthful personal AI** built on CRT + SSE principles, with:
- an intuitive dashboard/control panel
- onboarding + consented memory
- background learning and background research
- optional browser control via Tampermonkey bridge

It is designed to run comfortably on a typical Windows machine today, with a clean path to renting compute later.

---

## North Star (what we’re building)
**A personal AI that learns and grows with you without lying**.

Operationally, “won’t lie” means:
- No unsupported factual assertions presented as certain.
- If a claim is not supported by memory/tool evidence, it must be labeled **uncertain/speculative** or converted into a **question**.
- Conflicts are preserved, surfaced, and resolved via clarification — never silently overwritten.

---

## System Architecture (high level)

### A) Core runtime loop (online)
1) **User message** arrives.
2) **Intent + safety gates** run (assistant_profile, user_named_reference, memory_citation, contradiction_status, etc.).
3) **Retrieval** from multiple memory stores (trust-weighted).
4) **Answer generation** (LLM), constrained by:
   - retrieved context
   - truth contract rules
5) **Truth gate / grounding checks**:
   - if answer claims memory, it must be citeable
   - if answer introduces new entities while claiming memory, downgrade/ask/cite
6) **Writeback**:
   - only user-approved “belief lane” updates
   - everything else stored as low-trust notes or not stored

### B) Background loop (offline)
Background jobs operate on artifacts and produce *candidate updates*:
- session summarization
- slot extraction
- contradiction mining
- research ingestion + cross-source contradiction analysis

Crucially:
- background output is stored as **notes with provenance**
- promotion into stable personal facts requires explicit user consent

---

## Databases & Storage (what we need)

### 1) `crt_memory.db` (SQLite) — Personal memory store
Existing: stores memories + vectors + trust/confidence + tags.

Additions recommended:
- `memory_kind` (fact | pref | episodic | research_note | derived_summary | policy)
- `provenance_json` (urls, timestamps, quotes)
- `promotion_status` (quarantined | proposed | approved | rejected)

### 2) `crt_ledger.db` (SQLite) — Contradiction ledger
Existing: contradictions table.

Additions recommended:
- `resolution_prompt` (the exact question to ask the user)
- `resolution_required` boolean / severity

### 3) `crt_jobs.db` (SQLite) — Background jobs + scheduler
Tables:
- `jobs(id, type, payload_json, status, created_at, started_at, finished_at, error)`
- `job_artifacts(job_id, path, kind, created_at)`
- `job_events(job_id, ts, level, message)`

### 4) `crt_audit.db` (SQLite) — Audit trail ("why did you say/store this")
Tables:
- `answers(answer_id, ts, user_query, answer_text, mode, gate_reason, retrieved_ids_json)`
- `writes(write_id, ts, memory_id, reason, source, prior_value, new_value)`

### 5) SSE indexes (files on disk)
- Store SSE indices under `artifacts/sse/…` (or `personal_agent/sse/…`).
- Index **research corpora** and optionally **memory snapshots**.

### 6) Artifacts store (files)
- `artifacts/background/YYYY-MM-DD/*.json` (daily summaries, proposed promotions, contradiction reports)
- `artifacts/research/<topic>/` (raw fetches, summaries, SSE index)

---

## Control Panel UI (Streamlit) — what it should feel like

### Primary tabs
- **Home / Health**: coherence score, open contradictions, pending approvals, last background run
- **Onboarding**: ask/collect initial facts + preferences (configurable)
- **Memory**: search, filter, view provenance, revoke/forget, export
- **Contradictions**: open ledger items, resolve flows, “ask me next” queue
- **Approvals**: proposed new facts/preferences from background jobs (approve/reject)
- **Research**: queued topics, latest summaries, contradictions across sources
- **Policies**: toggles for strictness, research quarantine, browser permissions
- **Integrations**: browser bridge status, allowlists, tokens

### Key UX properties
- Every stored fact shows “why” (provenance + timestamp + source).
- One-click “forget” and “correct”.
- Clear separation: **facts about you** vs **research notes**.

---

## What can run comfortably on your system right now (local-first)

Given the repo’s current stack, a comfortable local setup is:
- **Ollama** for LLM inference (CPU or GPU if available)
  - `llama3.2:latest` is a good default; `mistral` also works.
- **SentenceTransformers all-MiniLM-L6-v2** for embeddings (already used).
- **SQLite** for all DBs (already used).
- **Streamlit** for dashboard/control panel (already in the venv).
- **WebSocket localhost bridge** for browser read-only research.

This is enough to build a compelling system without renting compute.

When you rent compute later:
- keep the same architecture
- swap the LLM backend (remote GPU inference) and optionally embeddings
- keep DBs local or sync via an encrypted store

---

## Roadmap (complex, but staged)

### Phase 0 — Stabilize the current CRT core (now)
- Lock down CRT contracts (truth/grounding, contradiction discipline, deterministic gates).
- Expand stress harness metrics and run multi-run campaigns.
- Ensure runtime config is stable/test-isolated (done).

Status: largely complete; continuing incremental hardening.

### Phase 1 — Control Panel MVP (local)
- Add a Control Panel app with:
  - onboarding flow
  - policy toggles writing to `crt_runtime_config.json`
  - memory explorer + forget/correct
  - contradiction viewer + resolve prompts

### Phase 2 — Background worker MVP (local)
- Implement `crt_jobs.db` and a background worker process.
- Produce daily artifacts:
  - session summaries
  - proposed fact updates (quarantined)
  - contradiction mining report

### Phase 3 — Research pipeline + SSE contradiction across sources
- Add research ingestion:
  - fetch page text (browser bridge)
  - summarize + store as `research_note` with provenance
  - SSE index per topic
  - contradiction reports across sources

### Phase 4 — Human-in-the-loop promotions
- Approvals UI:
  - promote `research_note` → `fact` only with explicit user approval
  - handle conflicts by generating a single clarifying question

### Phase 5 — “Never lie” hardening
- Add strict truth gating:
  - claim classification (grounded vs speculative vs unknown)
  - automatic downgrade when unsupported
  - stronger eval checks for memory-claim hallucinations

### Phase 6 — Optional: rented compute + multi-device
- Remote inference provider, same API shape.
- Encrypted sync for DBs/artifacts (or export/import).

---

## What to finish on the current system before pivoting hard
If we want to pivot into the big control panel + background learning track cleanly, finish these first:
- A stable set of CRT contracts + stress harness coverage.
- A single, reliable runtime config surface (already in place).
- The Control Panel MVP (Phase 1) so we have a place to expose new features safely.
- A job queue DB + worker skeleton (Phase 2) so “background learning” is real, observable, and reversible.

## Next milestone (recommended)

### Controlled learned-model releases (train → eval → publish)
Add a gated pipeline that:
1) trains a timestamped model artifact
2) evaluates it (on latest N stress runs and/or a held-out eval set)
3) only updates `learned_suggestions.latest.joblib` if it passes thresholds
4) writes a publish report artifact for auditability

---

## Related docs
- `CRT_FOCUS_10K_YARD.md`
- `CRT_ROADMAP_TRUTHFUL_PERSONAL_AI.md`
- `CRT_BACKGROUND_LEARNING.md`
- `BROWSER_BRIDGE_README.md`

# CRT Artifact Schemas (v1)

CRT is a **truth-contract-driven, stateful assistant**. That means “artifacts” (config, audit logs, background job outputs, promotion proposals) need stable, inspectable data contracts.

This document lists the current JSON Schema files for CRT artifacts.

---

## Schemas

### 1) Runtime config
- File: `crt_runtime_config.v1.schema.json`
- Purpose: validates `crt_runtime_config.json` (policy toggles, onboarding, gate templates).
- Notes: strict schema (unknown fields rejected) to keep policy changes intentional.

### 2) Background job artifact ("subconscious" worker)
- File: `crt_background_job.v1.schema.json`
- Purpose: portable JSON record for a background job run (metadata, payload, events, artifacts).
- Notes: `payload` and `result` are intentionally flexible in v1; everything else is strict.

### 3) Promotion proposals (human-in-the-loop)
- File: `crt_promotion_proposals.v1.schema.json`
- Purpose: proposals created by background learning that can be approved/rejected in the Control Panel.
- Notes:
  - proposals can target either lane, but **belief-lane promotion should require explicit approval**.
  - `evidence` supports memory, url, chat, or tool references.

### 4) Audit answer record
- File: `crt_audit_answer_record.v1.schema.json`
- Purpose: portable audit record for a single answer (prompt, output, retrieval ids, mode).

---

## Intended usage (recommended)

- Validate config at startup:
  - Load `crt_runtime_config.json`.
  - Validate against `crt_runtime_config.v1.schema.json`.
  - Fail fast with a clear error if invalid.

- Validate artifacts on write:
  - When emitting background job artifacts or promotion proposals, validate before saving.
  - Keep artifacts immutable once written (append new artifacts; don’t rewrite history).

---

## Relationship to SSE schemas

SSE has its own artifact contracts documented in `ARTIFACT_SCHEMAS.md` (focused on SSE chunk/claim/contradiction outputs). CRT schemas are separate because CRT artifacts represent **agent governance state** (policies, audits, background jobs), not compression outputs.

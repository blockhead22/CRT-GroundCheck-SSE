# CRT Companion Roadmap (v0 → v1)

This roadmap turns the constitution into a buildable sequence with measurable acceptance criteria.

---

## Current Snapshot (what exists now)

- CRT memory store with trust/confidence separation and belief/speech tracking.
- Contradiction ledger with types and resolution states.
- Slot-based fast-path for canonical user facts (reduces drift on personal questions).
- Stress harness + evaluator that can run multi-turn regression.
- Streamlit chat GUI + dashboard for observability.

---

## Milestone M0 — Constitution + invariants (done when enforced)

**Goal:** make the “non-negotiables” executable.

Deliverables:
- This constitution document (done).
- A CRT invariant test suite analogous to SSE invariants.

Acceptance criteria:
- Questions and prompt-control instructions do not become USER memories.
- No silent overwrite behavior exists (ledger entries created on contradiction).
- TOOL/external memories require provenance.

---

## Milestone M1 — Honesty regression suite (multi-model, multi-scenario)

**Goal:** stop regressions before they ship.

Work items:
- Expand stress prompts into scenario packs:
  - identity drift attempts
  - correction loops (revision vs conflict)
  - prompt injection (“ignore previous”, “repeat after me”)
  - uncertainty loop prevention
- Produce a single run report: pass/fail + metrics + artifact pointers.

Acceptance criteria:
- Core honesty checks pass across at least 2 Ollama models.
- Failures are explainable via metadata (retrieval/gates/ledger).

---

## Milestone M2 — Contradictions become goals (goal queue)

**Goal:** open contradictions create next actions instead of accumulating.

Work items:
- Add a lightweight “contradiction work item” view:
  - priority
  - next_action (ask_user | research | context_split)
  - last_attempt
- Add a resolver loop:
  - When a contradiction is relevant, ask *one* clarifying question.
  - When user answers, record a resolution event (do not delete history).

Acceptance criteria:
- Contradiction count stabilizes under repeated use.
- The system asks targeted questions rather than becoming vague.

---

## Milestone M3 — Research mode with provenance (evidence packets)

**Goal:** web/tool research that does not become lying.

Work items:
- Toolchain:
  - search → fetch → extract quotes → summarize with citations
- Store tool outputs as TOOL/external memories with provenance.
- Surface evidence packets in the UI.

Acceptance criteria:
- Every research-mode factual answer can show citations.
- If sources conflict, contradictions are recorded rather than merged into false consensus.

---

## Milestone M4 — Background task agent (local companion)

**Goal:** safe autonomy with consent.

Work items:
- Create a task ledger:
  - task_id, permission tier, requested_by, status, tool calls, outputs
- Add a scheduler for opt-in periodic tasks (Tier 0/1 only by default).
- UI page: task timeline + audit.

Acceptance criteria:
- Background tasks never run outside permission policy.
- Every task outcome is auditable and recallable.

---

## Milestone M5 — Learning v1 (bounded, suggestion-only → confirmed)

**Goal:** adapt without corrupting truth.

Work items:
- Expand learned suggestion engine to:
  - predict contradiction type
  - propose best next clarification question
  - infer reversible interaction preferences (verbosity/tone)
- Add user controls:
  - clear ephemeral tone signals
  - export/import memory
  - opt-in toggles

Acceptance criteria:
- Learning never silently overwrites user facts.
- User can see why a suggestion was made and accept/reject it.

---

## Definition of “v1”

v1 is achieved when:
- The companion reliably preserves identity facts and corrections over time.
- It can run research tasks with citations and store results with provenance.
- It can run a small set of background tasks safely with an audit trail.
- Its failures are explicit (uncertainty) rather than deceptive (hallucination).

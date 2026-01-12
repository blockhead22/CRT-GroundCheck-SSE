# CRT Master Focus Roadmap (Personal + OSS + Product)

This is the consolidated “final focus roadmap” for CRT: what the system is, how it should run long-term, and how we build it in staged milestones **without breaking the truth contract**.

CRT’s core promise is not “magic accuracy.” It’s **coherent, inspectable, consented memory + explicit uncertainty + durable contradiction handling**.

## Current implementation status (Jan 12, 2026)

Implemented and running in this repo now:
- Streamlit Control Panel with human-in-the-loop promotion approvals and gated apply (dry-run/sandbox/real).
- Streamlit Chat UI (optional local LLM integration).
- Deterministic gates with regression tests for key failure modes (e.g., name declaration / false contradictions).
- Learned “suggestions-only” model tracking (train metadata + eval artifacts + dashboard timeline/compare).

Immediate next: make learned-model updates a controlled release process (train → eval → publish latest with thresholds).

---

## 0) North Star

**A personal AI that learns like a subconscious, but never lies.**

Operational meaning of “subconscious” in CRT:
- It runs background jobs that *produce candidate notes, summaries, and prompts*.
- It does **not** silently upgrade background output into “facts about you”.
- Promotions into stable memory require **user approval**.

---

## 1) Product Surface Areas (A/B/C unified)

CRT is one core engine with three distribution targets:

### A) Personal (local-first)
- Runs on one machine.
- Default data stays local.
- Fast iteration and high control.

### B) Open Source
- CRT Core + evaluator harness + local Control Panel.
- Clean plugin boundaries for tools and storage.
- Documentation that teaches “truth contracts for stateful agents.”

### C) Product
- Polished UX, onboarding, backups, sync, permissions, support.
- Optional hosted inference or hybrid compute.
- Strong auditability and policy governance.

**Design rule:** do not fork the architecture. Personal → OSS → Product should all run the same “core loop” and “background loop,” just with different packaging and optional services.

---

## 2) CRT Contracts (the non‑negotiables)

These are the invariants that must stay true as the system grows:

1) **No unsupported facts as certain**
- If a claim is not supported by memory text or cited sources, CRT must label uncertainty, ask a question, or abstain.

2) **Memory-claim grounding**
- If CRT says “I remember / stored memories / from our chat,” it must be grounded to retrieved memory text (or degrade to uncertainty + ask for confirmation).

3) **Contradictions become ledger objects**
- Conflicts do not get silently overwritten.
- Conflicts create an entry with a clarifying question.

4) **Two-lane memory**
- **Belief lane (stable)**: user-approved facts/preferences.
- **Notes lane (quarantined)**: research notes, hypotheses, summaries, unconfirmed extractions.

5) **Deterministic gates fire reliably**
- Assistant profile questions → deterministic “I’m an AI system…” style responses.
- Named reference gates and policy toggles are consistent and testable.

6) **Every stored item is revocable**
- You can delete/forget/correct with a visible audit trail.

---

## 3) Future System Layout (modules)

### 3.1 Runtime (online) components
- **CRT Engine**: query → retrieve → generate → truth-gate → writeback.
- **Memory Store**: long-term memory, trust, provenance, vector index.
- **Contradiction Ledger**: track conflicts, resolutions, and “ask next.”
- **Policy / Runtime Config**: toggles and templates, versioned and editable.
- **Tool Interfaces (optional)**: browser bridge, local files, index search.

### 3.2 Background (offline) components (“subconscious”)
- **Job Queue DB**: durable jobs with status, payloads, and logs.
- **Worker Process**: executes background tasks on a schedule.
- **Artifact Store**: JSON outputs, evidence packets, daily summaries.
- **Promotion Pipeline**: proposes changes; never writes stable facts silently.

### 3.3 UI / Control Plane
- **Control Panel (Streamlit initially)**:
  - Memory explorer + provenance
  - Contradiction inbox
  - Approvals for promotions
  - Policies / permissions
  - Integrations (browser bridge) and health

---

## 4) Data Model (schemas)

Use SQLite for local-first reliability and inspectability.

### 4.1 `crt_memory.db`

**Table: `memories`**
- `id` (pk)
- `kind` enum: `fact | preference | episodic | research_note | derived_summary | policy | tool_log`
- `lane` enum: `belief | notes`
- `key` (slot-like key, optional)
- `value_text`
- `source` enum: `user | chat | research | tool | system`
- `created_at`, `updated_at`
- `trust` float (0..1)
- `confidence` float (0..1)
- `provenance_json` (urls, quotes, timestamps, tool ids)
- `promotion_status` enum: `approved | proposed | rejected | quarantined`
- `supersedes_id` (nullable) – for history preservation

**Table: `memory_embeddings`**
- `memory_id` (fk)
- `embedding_blob`
- `embed_model`
- `created_at`

### 4.2 `crt_ledger.db`

**Table: `contradictions`**
- `id` (pk)
- `a_memory_id`, `b_memory_id` (nullable when conflict is between memory and new statement)
- `summary`
- `severity` enum: `low | medium | high`
- `status` enum: `open | awaiting_user | resolved | dismissed`
- `resolution_question`
- `resolution_answer`
- `created_at`, `resolved_at`

### 4.3 `crt_jobs.db` (subconscious)

**Table: `jobs`**
- `id` (pk)
- `type` enum: `summarize_session | extract_slots | mine_contradictions | research_fetch | research_summarize | research_compare | propose_promotions | monitor_source`
- `payload_json`
- `status` enum: `queued | running | succeeded | failed | canceled`
- `priority` int
- `created_at`, `started_at`, `finished_at`
- `error`

**Table: `job_events`**
- `id` (pk)
- `job_id` (fk)
- `ts`
- `level` enum: `debug | info | warn | error`
- `message`

**Table: `job_artifacts`**
- `id` (pk)
- `job_id` (fk)
- `kind` enum: `summary | evidence_packet | extracted_facts | contradictions | proposal`
- `path`
- `created_at`

### 4.4 `crt_audit.db`

**Table: `answers`**
- `id` (pk)
- `ts`
- `user_text`
- `answer_text`
- `mode` (e.g., `memory | research | uncertain`)
- `gate_reason` (string)
- `retrieved_memory_ids_json`
- `retrieved_doc_ids_json`

**Table: `writes`**
- `id` (pk)
- `ts`
- `memory_id`
- `action` enum: `create | update | delete | promote | reject`
- `reason`
- `before_text`, `after_text`

---

## 5) Runtime Config (policy surface)

Keep policy and product behavior in a versioned JSON config.

Suggested schema (shape, not strict JSON Schema):

```json
{
  "version": "1",
  "truth": {
    "strict_memory_claims": true,
    "require_provenance_for_research_claims": true,
    "operational_facts": {
      "hours_address_phone_are_restricted": true,
      "allowed_if_present_in": ["memory", "research_note"],
      "otherwise": "ask_or_abstain"
    }
  },
  "gates": {
    "assistant_profile": {"enabled": true},
    "user_named_reference": {"enabled": true}
  },
  "background_learning": {
    "enabled": true,
    "schedule": {"daily_summary": "02:00", "monitor_interval_minutes": 60},
    "promotion_requires_approval": true
  },
  "browser_bridge": {
    "enabled": false,
    "allowlist_domains": ["theprintinglair.com"],
    "read_only": true
  }
}
```

---

## 6) Core Runtime Loop (pseudocode)

### 6.1 Online query path

```python
def handle_user_message(user_text: str) -> dict:
    policy = load_runtime_config()

    # 1) Gate checks (deterministic)
    gate = policy_engine.classify(user_text)
    if gate.triggered:
        answer = gate.render_response(user_text)
        return audit_answer(user_text, answer, mode="gate", gate_reason=gate.name)

    # 2) Retrieve
    memories = memory_store.retrieve(user_text, k=K, trust_weighted=True)
    docs = research_index.retrieve(user_text, k=K_DOCS)

    # 3) Generate
    draft = llm.generate(user_text, memories, docs, policy)

    # 4) Truth gate
    verdict = truth_gate.evaluate(user_text, draft, memories, docs, policy)
    if verdict.action == "downgrade_to_uncertain":
        final = truth_gate.rewrite_uncertain(draft, verdict)
    elif verdict.action == "ask_clarifying_question":
        final = truth_gate.ask_clarifier(verdict.question)
    else:
        final = draft

    # 5) Contradiction detection + ledger
    conflict = contradiction_checker.check(final, memories)
    if conflict.found:
        ledger.record(conflict)

    # 6) Writeback (only safe lanes)
    writeback.apply(user_text, final, policy, requires_approval=True)

    return audit_answer(user_text, final, mode=verdict.mode, gate_reason=verdict.reason)
```

### 6.2 Truth gate focus (the “anti-lie governor”)

```python
def evaluate(user_text, draft, memories, docs, policy) -> Verdict:
    if policy.truth.strict_memory_claims and claims_memory(draft):
        if not grounded_to_memory_text(draft, memories):
            return Verdict(action="ask_clarifying_question", question="I don’t have that in memory—what are the correct details?")

    if includes_operational_facts(draft) and policy.truth.operational_facts.hours_address_phone_are_restricted:
        if not supported_by(memory_or_research_notes=memories+docs):
            return Verdict(action="downgrade_to_uncertain", mode="uncertain", reason="operational_fact_ungrounded")

    return Verdict(action="ok", mode="normal")
```

---

## 7) Background Learning (“Subconscious”) Architecture

### 7.1 Principle
Background work is allowed to:
- summarize
- extract candidates
- cross-check sources
- propose actions

Background work is NOT allowed to:
- write stable personal facts without approval
- resolve contradictions silently

### 7.2 Worker loop

```python
def background_worker_tick():
    policy = load_runtime_config()
    if not policy.background_learning.enabled:
        return

    job = jobs.dequeue_next()
    if not job:
        return

    try:
        jobs.mark_running(job)
        result = run_job(job, policy)
        artifacts = persist_artifacts(job, result)

        # Convert results into NOTES lane only
        notes_ids = notes_lane_write(result, artifacts, policy)

        # Optionally produce promotion proposals
        proposals = propose_promotions(notes_ids, policy)
        if proposals:
            store_proposals_for_ui(proposals)

        jobs.mark_succeeded(job)
    except Exception as e:
        jobs.mark_failed(job, error=str(e))
```

### 7.3 Job types (recommended)

1) `summarize_session`
- Input: transcript chunk(s)
- Output: session summary + “what changed” + unresolved questions

2) `extract_slots`
- Input: transcript chunk(s)
- Output: candidate facts/preferences with confidence + quoted evidence spans
- Store into NOTES as `proposed` (not approved)

3) `mine_contradictions`
- Input: memory snapshots + recent notes
- Output: contradiction candidates + a single best clarifying question each

4) `research_fetch`
- Input: URL or topic
- Output: raw page text + extracted quotes

5) `research_summarize`
- Input: fetched page(s)
- Output: summary with citations

6) `research_compare`
- Input: multiple sources
- Output: agreement map + conflicts + questions

7) `propose_promotions`
- Input: notes lane items
- Output: proposals for belief lane changes

### 7.4 Promotion workflow (human-in-the-loop)

State machine for a candidate memory item:
- `quarantined` → `proposed` → (`approved` | `rejected`)

```python
def approve_proposal(proposal_id):
    proposal = load_proposal(proposal_id)
    # Create/replace belief-lane memory, keep history
    belief_id = memory_store.upsert(
        lane="belief",
        kind=proposal.kind,
        key=proposal.key,
        value_text=proposal.value_text,
        provenance_json=proposal.provenance_json,
        promotion_status="approved",
        supersedes_id=proposal.supersedes_id
    )
    audit.log_promotion(proposal_id, belief_id)
```

This is the “subconscious”: constantly generating **candidates**, while your conscious Control Panel decides what becomes “truth.”

---

## 8) Control Panel Layout (future UX)

### 8.1 Pages
- **Home / Health**: pass-rate trends, last background runs, pending approvals, open contradictions
- **Chat**: primary conversation UI (optional)
- **Memory Explorer**: search/filter by lane/kind/source/trust; provenance viewer
- **Approvals**: proposed updates; approve/reject; diff view; provenance citations
- **Contradictions**: open items; resolution question queue; resolution history
- **Research**: topics, evidence packets, source allowlists, contradictions across sources
- **Policies**: toggles and templates; strictness slider; export/import config
- **Integrations**: browser bridge status; tokens; domain allowlist; read-only mode
- **Audit Log**: “why did you say/store this?” trace

### 8.2 Key UX primitives (non-negotiable)
- “Show me what you know about X”
- “Why did you say that?” (must reveal retrieval/provenance)
- “Forget / correct” (must be immediate and durable)
- “Approve” for promotions

---

## 9) Evaluation & Continuous Verification (how we stay honest)

Use the stress harness as a **build gate**:
- seeded, forced probe schedules
- multi-run batches
- metrics over time, not just pass/fail

Minimum standard gates before shipping a new feature:
- `hard/all` challenge pack passes across multiple seeds
- no regressions in “memory-claim hallucination” checks
- deterministic gate tests remain green

---

## 10) Milestones (practical build sequence)

### M0 — Contracts locked
- Contracts documented + automated checks stable.
- Multi-seed batch runs become routine.

### M1 — Control Panel MVP (local)
- Memory explorer
- Contradiction inbox
- Policy toggles
- Basic audit views

### M2 — Subconscious worker MVP (local)
- `crt_jobs.db` + worker process
- Daily summaries + extraction proposals
- Approvals UI

### M3 — Browser research v1 (local-only)
- Browser bridge read-only
- Evidence packets stored with provenance
- Research notes lane + contradictions across sources

### M4 — Product hardening
- Packaging, backups, encryption, exports
- Permission tiers and safety defaults

### M5 — OSS packaging + community
- Clean install, sample data, docs, contribution guide
- Stable plugin surfaces

---

## 11) “Definition of v1” (ship criteria)

CRT v1 is achieved when:
- It preserves identity facts and corrections over time.
- It never claims memory for details it cannot ground.
- It can do research with citations and store results as notes.
- Background learning exists and is observable, reversible, and approval-gated.
- The Control Panel makes policies + memory + contradictions transparent.

---

## 12) Schema contracts (artifact JSON schemas)

CRT uses JSON Schemas as data contracts for its governance artifacts:
- `CRT_ARTIFACT_SCHEMAS.md`
- `crt_runtime_config.v1.schema.json`
- `crt_background_job.v1.schema.json`
- `crt_promotion_proposals.v1.schema.json`
- `crt_audit_answer_record.v1.schema.json`

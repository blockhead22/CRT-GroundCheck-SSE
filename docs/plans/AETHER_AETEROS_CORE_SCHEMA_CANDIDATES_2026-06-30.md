# Aeteros Core Schema Candidates - 2026-06-30

Purpose:

```text
Name the stable data shapes that should graduate from Aether Workbench and the
local-router lab toward reusable Aeteros Core primitives.
```

This is a schema-candidate note, not an extraction patch. The current worktree
already has working behavior; this document marks which shapes are stable
enough to design around before moving code into a shared core package.

## Core Boundary

Aeteros Core should contain small, boring, reusable governance primitives:

```text
trace events
evidence receipts
review candidates
review decisions
contradiction markers
feedback ledger rows
safety contracts
```

It should not contain lab-pack names, task-specific evaluator thresholds,
Workbench component state, local-router replay case ids, or product copy.

## Candidate Schemas

### EvidenceReceipt

Current sources:

```text
D:\AI_round2\aether-core\aether\sidecar\consolidation.py
D:\AI_round2\labs\meaning_compression_lab\local_router_feedback_ledger.py
D:\AI_round2\workbench\src\types.ts
```

Stable fields:

```text
evidence_type
reference_id
summary
observed_at optional
source_authority optional
```

Why it belongs in Core:

```text
Memory review, support review, reflection review, RAG evidence, feedback rows,
and trace packets all need compact evidence that can be shown without exposing
raw hidden chain-of-thought or unsafe memory values.
```

Boundary:

```text
Receipts summarize evidence; they are not confirmed facts by themselves.
```

### ReviewCandidate

Current sources:

```text
D:\AI_round2\aether-core\aether\sidecar\consolidation.py
D:\AI_round2\labs\meaning_compression_lab\local_router_feedback_ledger.py
D:\AI_round2\labs\meaning_compression_lab\workbench_evidence_adapter.py
D:\AI_round2\workbench\src\types.ts
```

Stable fields:

```text
candidate_id
candidate_type
category
candidate_kind
summary
proposed_action
risk
review_route
evidence[]
review_required
memory_write_allowed
confirmed_fact
```

Why it belongs in Core:

```text
This is the shared shape behind Memory, Support, Reflection, Contradiction, and
Evidence candidates. It is the practical center of the governed learner loop.
```

Boundary:

```text
Candidates are proposals. They must not mutate memory, support patterns,
reflections, policy, or model routing until a review decision approves them.
```

### ReviewDecision

Current sources:

```text
D:\AI_round2\aether-core\aether\sidecar\reflections.py
D:\AI_round2\aether-core\aether\sidecar\support_patterns.py
D:\AI_round2\workbench\src\components\ConsolidationDrawer.tsx
```

Stable fields:

```text
decision_id
candidate_id or target_id
action: accept | reject | defer | revise | expire
note
prior_revision_hash
result_target_id optional
created_at
idempotency_key
```

Why it belongs in Core:

```text
The reject/defer non-effect boundary depends on explicit decisions and revision
guards. Review decisions are the difference between "the system noticed this"
and "the system may use this durably."
```

Boundary:

```text
Deferred and rejected decisions must remain behavior-inert. Accepted decisions
may affect future context only through the reviewed target surface.
```

### TraceEvent

Current sources:

```text
D:\AI_round2\workbench\src\types.ts
D:\AI_round2\labs\meaning_compression_lab\workbench_trace_adapter.py
D:\AI_round2\labs\meaning_compression_lab\local_router_cli.py
```

Stable fields:

```text
turn_id
conversation_id
query
status
model
generation_model optional
route_decision optional
plan
packets[]
tool_runs[]
completion optional
local_extensions optional
```

Why it belongs in Core:

```text
TraceEvent is the durable record of what the system believed it was doing:
route, released evidence, withheld evidence, conflict status, verifier state,
repair/fallback, and review candidates.
```

Boundary:

```text
TraceEvent may store structured reasoning metadata, but must not store raw
hidden chain-of-thought as truth.
```

### TracePacket

Current sources:

```text
D:\AI_round2\workbench\src\types.ts
D:\AI_round2\labs\meaning_compression_lab\workbench_trace_adapter.py
```

Stable fields:

```text
request_id
clause_id
clause_text
planner_slot
slot_id
mode
release: answerable | withhold | conflict | no_evidence
reason
contradiction_disposition optional
evidence[]
```

Why it belongs in Core:

```text
TracePacket is the smallest useful unit of governed release. It maps a request
clause to evidence, release decision, and contradiction state.
```

Boundary:

```text
Packets can say why something was released or withheld; they should not leak
restricted conflicting values when the release state is conflict or withhold.
```

### ContradictionMarker

Current sources:

```text
D:\AI_round2\workbench\src\types.ts
D:\AI_round2\aether-core\aether\sidecar\consolidation.py
D:\AI_round2\aether-core\aether\sidecar\route_policy.py
```

Stable fields:

```text
label
confidence
reason
evidence_state_ids[]
slot_id optional
reviewable boolean
```

Why it belongs in Core:

```text
Contradiction handling is one of the central Aether/CRT claims. The marker
needs to travel through routing, trace, review candidates, and Workbench UI.
```

Boundary:

```text
The marker can identify that a conflict exists without exposing the underlying
restricted values in learner previews.
```

### FeedbackLedgerRow

Current sources:

```text
D:\AI_round2\labs\meaning_compression_lab\local_router_feedback_ledger.py
D:\AI_round2\docs\plans\AETHER_WEIGHTED_FEEDBACK_LEDGER_2026-06-29.md
```

Stable fields:

```text
feedback_id
answer_id
trace_id
task_type
route
scaffold_profile
overall
scores
tags[]
human_note
promotion_decision
review_required
```

Why it belongs in Core:

```text
This gives the system a non-neural learning path: repeated evidence can suggest
policy/scaffold review without silently changing behavior.
```

Boundary:

```text
Feedback rows are not training data by default. They become policy or support
changes only through review candidates and accepted decisions.
```

### SafetyContract

Current sources:

```text
D:\AI_round2\labs\meaning_compression_lab\workbench_evidence_adapter.py
D:\AI_round2\aether-core\aether\sidecar\consolidation.py
D:\AI_round2\workbench\src\types.ts
```

Stable fields:

```text
promotion_status
memory_writes_allowed
support_pattern_import_allowed optional
reflection_create_allowed optional
raw_chain_of_thought_stored
silent_policy_mutation_allowed
review_required_before_promotion
```

Why it belongs in Core:

```text
SafetyContract is the guardrail that lets lab evidence and learner candidates
move through Workbench without becoming memory, policy, or hidden mutation.
```

Boundary:

```text
Any candidate/evidence surface without an explicit safe contract should default
to review-only or be rejected.
```

## Implemented Extraction

```text
D:\AI_round2\aether-core\aether\sidecar\review_schema.py
```

The first extraction is now implemented because it reduced duplication across
two live call sites:

```text
D:\AI_round2\aether-core\aether\sidecar\consolidation.py
D:\AI_round2\aether-core\aether\sidecar\archive_import.py
```

Included:

```text
EvidenceReceipt
ReviewCandidate
SafetyContract
review_only_candidate_flags
```

Verification:

```text
python -m pytest aether-core\tests\test_review_schema.py aether-core\tests\test_sidecar_consolidation.py aether-core\tests\test_archive_import_schema.py -q
20 passed
python -m py_compile aether-core\aether\sidecar\review_schema.py aether-core\aether\sidecar\consolidation.py aether-core\aether\sidecar\archive_import.py
passed
```

## Proposed Extraction Order

1. Add `ReviewDecision` after the accepted/rejected/deferred behavior tests are
   stable across Memory, Support, and Reflection.
2. Extract `TraceEvent` and `TracePacket` after the Trace drawer shape stops
   changing.
3. Extract `ContradictionMarker` once memory conflict review and route policy
   share the same labels.
4. Extract `FeedbackLedgerRow` last, after at least one non-lab feedback source
   uses the same row shape.

## ReviewDecision Readiness Audit - 2026-06-30

Current answer:

```text
Do not extract ReviewDecision yet.
```

Why:

```text
Support and Reflection have compatible candidate-review rows:
- action
- note
- idempotency_key
- prior_revision_hash
- created_at
- accepted/rejected/deferred-style status transitions

Memory review is not the same shape yet. It still operates on substrate slots
and states through confirm/correct/quarantine actions with substrate SHA guards:
- confirm_candidate
- correct_slot_value
- quarantine_conflict
```

Live sources checked:

```text
D:\AI_round2\aether-core\aether\sidecar\reflections.py
D:\AI_round2\aether-core\aether\sidecar\support_patterns.py
D:\AI_round2\aether-core\aether\sidecar\app.py
D:\AI_round2\aether-core\aether\sidecar\db.py
D:\AI_round2\aether-core\aether\substrate\review.py
D:\AI_round2\workbench\src\components\ConsolidationDrawer.tsx
```

Extraction condition:

```text
Extract ReviewDecision only after Memory review exposes a candidate/decision
adapter that can describe confirm/correct/quarantine using the same durable
decision envelope as Support and Reflection, or after another non-Memory live
surface needs the same decision record strongly enough to justify a smaller
two-surface primitive.
```

Do not do:

```text
Do not force Memory confirm/correct/quarantine into accept/reject/defer names.
Do not hide substrate SHA / revision guards behind a generic helper.
Do not treat Workbench local "defer/hide session" as a durable ReviewDecision.
```

## Memory Adapter Note - 2026-06-30

Workbench now has a manual, review-only Memory draft handoff for
trace-proposed memory facts:

```text
D:\AI_round2\workbench\src\App.tsx
D:\AI_round2\workbench\src\components\MemoryDrawer.tsx
D:\AI_round2\workbench\src\components\MemoryDrawer.test.tsx
```

What it does:

```text
Learner candidate -> Memory drawer
shows proposed slot, summary, confidence, source candidate, candidate kind, and
evidence receipts
```

What it deliberately does not do:

```text
prefill correction values
confirm a candidate state
quarantine a slot
write memory
turn Memory into accept/reject/defer
```

Interpretation:

```text
This closes a Workbench dogfooding gap, but it is not enough to extract
ReviewDecision. ReviewDecision still waits for a durable adapter that can
represent Memory confirm/correct/quarantine without flattening the substrate
SHA guard semantics.
```

## ContradictionMarker Readiness Audit - 2026-06-30

Current answer:

```text
Do not extract ContradictionMarker yet.
```

What is already real:

```text
D:\AI_round2\aether-core\aether\substrate\slots.py
defines the shared Disposition vocabulary:
resolvable, held, evolving, contextual, stale, policy_bound, unknown.

D:\AI_round2\aether-core\aether\runtime\query.py
classifies conflicted current slot evidence into a contradiction_disposition
dict with label, confidence, reason, and evidence_state_ids.

D:\AI_round2\aether-core\aether\sidecar\route_policy.py
uses contradiction_disposition labels as routing signals for
contradiction_review.

D:\AI_round2\aether-core\aether\sidecar\consolidation.py
turns reviewable conflict packets into review-only Memory candidates.

D:\AI_round2\workbench\src\components\TraceDrawer.tsx
D:\AI_round2\workbench\src\components\MemoryDrawer.tsx
display contradiction disposition labels in trace and memory review surfaces.
```

Why extraction is premature:

```text
The shared part is currently a small vocabulary and packet field, not a full
two-surface Core primitive. Route policy only needs the label to choose
contradiction_review. Memory review still needs substrate slot/state actions:
confirm_candidate, correct_slot_value, and quarantine_conflict with revision
and substrate SHA guards.
```

Extraction condition:

```text
Extract ContradictionMarker only after the same marker object drives at least
two live behaviors, for example:
- route policy chooses contradiction_review from the marker;
- Memory conflict review opens slot/state actions from the marker;
- Trace/Workbench renders the same marker without re-shaping it locally.
```

Do not do:

```text
Do not wrap the current dict in a Core class merely because the field appears
in several files.
Do not move substrate review actions behind a generic contradiction helper.
Do not expose restricted conflicting values through learner candidates.
Do not treat held, stale, or policy_bound conflicts as automatically
reviewable just because they share the same label field.
```

## TraceEvent / TracePacket Readiness Audit - 2026-06-30

Current answer:

```text
Do not extract TraceEvent or TracePacket yet.
```

What is already stable:

```text
D:\AI_round2\workbench\src\types.ts
defines the Workbench-facing Trace and TracePacket interfaces.

D:\AI_round2\aether-core\aether\runtime\query.py
produces governed memory packets with request_id, clause_id, planner_slot,
slot_id, release, reason, contradiction_disposition, and evidence.

D:\AI_round2\aether-core\aether\sidecar\app.py
persists live Workbench trace JSON with query context, packets, route decision,
depth policy, tool runs, memory/document write summaries, completion metadata,
and context-bridge metadata.

D:\AI_round2\labs\meaning_compression_lab\local_router_cli.py
produces lab-local durable trace artifacts with trace_schema, route_selected,
mirus_packet_summary, verifier_flags, repair/fallback, confidence, and
review-only learning candidates.

D:\AI_round2\labs\meaning_compression_lab\workbench_trace_adapter.py
maps lab traces into the Workbench Trace/TracePacket display vocabulary without
turning lab anchors into confirmed memory.
```

Why extraction is premature:

```text
There are two useful trace families right now:

1. Live Workbench trace:
   query-context packets, tool runs, route decision, completion, memory/document
   summaries, and context bridge.

2. Local-router lab trace:
   route/scaffold/Mirus/verifier/replay metadata that gets adapted into
   Workbench display packets.

The adapter is intentionally doing translation work. A Core TraceEvent today
would either be too generic to help, or too specific and would flatten the
difference between live governed memory packets and lab validation metadata.
```

Extraction condition:

```text
Extract TracePacket first, not TraceEvent, once the same packet object is used
unchanged by at least two live call sites:
- GovernedQueryService output;
- Workbench TraceDrawer rendering;
- sidecar consolidation candidate generation;
- lab-to-Workbench trace adapter.

Extract TraceEvent only after Trace drawer, completion metadata, local_router
extensions, and sidecar consolidation all stop adding/changing top-level fields.
```

Do not do:

```text
Do not force local-router lab trace_schema fields into the live Workbench trace
contract.
Do not put local_router_trace.evidence_review or replay pack metadata in Core.
Do not store raw hidden chain-of-thought under a generic trace field.
Do not extract a TraceEvent that is just a permissive dict wrapper.
```

## Do Not Extract Yet

```text
local_router_rag_evidence_review
local_router replay pack metadata
task-specific verifier thresholds
model names and fallback profiles
Workbench local session triage state
adversarial v1/v2 case ids
grant/product wording anchors
```

These are valuable evidence and product scaffolding, but they are not stable
Core primitives.

## Next Implementation Step

Do not expand the schema module just because a candidate exists. Add the next
primitive only when one of these is needed by at least two live call sites:

```text
aether.sidecar.consolidation
archive import/review
Workbench trace adapter
local-router feedback/evidence adapter
```

The most likely next primitive is `ReviewDecision`, but only after Memory,
Support, and Reflection share enough accept/reject/defer behavior to make a
single reusable decision record cheaper than separate local shapes.

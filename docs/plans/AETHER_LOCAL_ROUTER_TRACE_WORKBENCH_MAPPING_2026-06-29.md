# Aether Local-Router Trace To Workbench Mapping - 2026-06-29

Purpose:

```text
Map the local-router lab trace schema into the existing Workbench Trace drawer
shape without storing raw hidden chain-of-thought and without promoting lab
anchors into confirmed memory.
```

Implemented adapter:

```text
D:\AI_round2\labs\meaning_compression_lab\workbench_trace_adapter.py
```

Implemented isolated fixture import:

```text
D:\AI_round2\labs\meaning_compression_lab\workbench_trace_fixture.py
```

Implemented RAG-suite evidence review adapter:

```text
D:\AI_round2\labs\meaning_compression_lab\workbench_evidence_adapter.py
```

Verification:

```text
python -m pytest tests\test_workbench_trace_adapter.py tests\test_local_router_cli.py tests\test_local_router_replay.py -q
28 passed

python -m py_compile labs\meaning_compression_lab\workbench_trace_adapter.py
passed

python -m pytest tests\test_workbench_trace_fixture.py tests\test_workbench_trace_adapter.py tests\test_local_router_cli.py tests\test_local_router_replay.py -q
30 passed

python -m py_compile labs\meaning_compression_lab\workbench_trace_fixture.py labs\meaning_compression_lab\workbench_trace_adapter.py
passed

cd D:\AI_round2\workbench
npm run test:ui -- --run src/components/TraceDrawer.test.tsx
12 passed

npm run build
passed

python -m pytest tests\test_workbench_evidence_adapter.py tests\test_workbench_trace_adapter.py tests\test_workbench_trace_fixture.py -q
7 passed

python -m py_compile labs\meaning_compression_lab\workbench_evidence_adapter.py
passed

cd D:\AI_round2\workbench
npm run test:ui -- --run src/components/TraceDrawer.test.tsx
13 passed

cd D:\AI_round2\workbench
npm run test:ui -- --run src/App.test.tsx src/components/TraceDrawer.test.tsx
29 passed
```

## Mapping

```text
local_router.trace.v0                   Workbench Trace shape
---------------------                   ---------------------
user_request_summary                    query
turn_id                                 turn_id
conversation_id                         conversation_id
model_selected                          model / generation_model
task_type                               route_decision.selected_route
route_selected.model                    route_decision model fields
route_selected.profile                  selected_model_policy / guidance_kind
route_selected.reason                   route_reason / candidate route reason
repair_attempts                         completion.guidance_repaired
fallback_used                           local_router_trace.fallback_used
verifier_flags.passed                   status / plan.status / verifier packet release
verifier receipt/concept hits           plan.coverage
forbidden/leakage/weirdness/truncated   plan.unresolved_clauses
mirus_packet_summary                    local_router_trace + lab:mirus_packet
draft/contract/usefulness scores        local_router_trace score fields
learning_candidates                     stays in source trace; future learner review only
raw_chain_of_thought_stored             local_router_trace boundary flag
```

## Workbench Packets

The adapter creates three renderable packets:

```text
lab:route
  route/model/scaffold selection metadata

lab:mirus_packet
  evidence-anchor and Mirus packet summary

lab:verifier
  answer-side verifier result
```

All three packets use empty `evidence` arrays. This is deliberate. A lab trace
anchor is not a confirmed memory state and should not show up as user memory in
Workbench.

## Route Decision

The adapter emits a normal Workbench `route_decision` object:

```text
selected_route: local_router_<task_type>
selected_model_policy: lab_profile_<scaffold_profile>
tool_policy: no_tools_lab_replay
repair_policy: repair_once or repair_once_then_fallback
memory_write_allowed: false
silent_escalation_allowed: false
model_recommendation.observational_only: true
model_recommendation.model_selection_changed: false
```

This keeps lab evidence observational. It must not switch models, write memory,
or silently escalate.

## UI Boundary

Safe to show now:

```text
route/model/scaffold selected
Mirus packet counts
evidence anchor coverage
verifier pass/fail and flags
repair/fallback status
confidence and promotion status
```

Do not show as truth:

```text
raw hidden chain-of-thought
lab anchors as confirmed memory
learning candidates as accepted behavior
grant/business claims as proven outcomes
```

## Isolated Fixture Import

`import_local_router_trace_fixture(...)` writes an adapted lab trace into a
caller-provided Workbench DB path using the normal WorkbenchDB path:

```text
begin_turn
save_trace
complete_turn
get_trace
```

Safety:

```text
fixture_import_only: true
memory_writes_performed: false
memory_write_allowed: false
refuses ~/.aether/workbench.db by default
```

This proves adapted traces can survive the same persistence/reload path as real
Workbench traces while keeping lab artifacts out of Nick's live database.

## RAG-Suite Evidence Review

`adapt_rag_suite_result_for_workbench_review(...)` converts a full RAG-suite
result artifact into compact review metadata:

```text
kind: local_router_rag_evidence_review
baseline_to_beat: scaffolded_rag
baselines: raw / plain_rag / scaffolded_rag / governed pass rates and scores
governed_delta_vs_scaffolded_rag: pass-count and average-score deltas
review_flags: perfect-score caution, trace completeness, baseline findings
failure_summary: failures by task type per mode
safety_contract: review_only, no memory writes, no raw CoT, no silent mutation
next_review: recommended next evidence/review step
```

This is the Workbench bridge for run-level evidence like:

```text
raw 0/6
plain_rag 1/6
scaffolded_rag 5/6
governed 6/6, trace 6/6
```

It deliberately does not import answer text, retrieved snippets, hidden
thinking, or learning candidates. It is meant for review surfaces and evidence
triage, not memory promotion.

Workbench fixture/UI bridge:

```text
D:\AI_round2\workbench\src\fixtures\localRouterRagEvidenceReview.ts
D:\AI_round2\workbench\src\fixtures\localRouterRagEvidencePreview.ts
D:\AI_round2\workbench\src\components\TraceDrawer.tsx
D:\AI_round2\workbench\src\components\TraceDrawer.test.tsx
D:\AI_round2\workbench\src\App.test.tsx
```

The Trace drawer can now render a nested
`local_router_trace.evidence_review` object as "Local router evidence review":

```text
pack
case count
baseline_to_beat = scaffolded_rag
governed pass/score
scaffolded RAG pass/score
delta vs scaffolded RAG
trace completeness
promotion_status = review_only
memory writes blocked
silent mutation blocked
holdout caution when governed scores are perfect
```

The Learn drawer can also render the same RAG evidence as a preview-only
learner candidate. Opening it routes to Reflect as manual form state only:
nothing is created, accepted, imported, or written to memory.

Generated preview path:

```text
D:\AI_round2\labs\meaning_compression_lab\workbench_evidence_preview_cli.py
```

Usage:

```text
python -m labs.meaning_compression_lab.workbench_evidence_preview_cli labs\meaning_compression_lab\results\local_router_rag_suite_1782766406.json
```

This emits the same review-only learner preview shape used by Workbench:
`reflection_create_performed=false`, `memory_write_allowed=false`, Reflect
route with `requires_adapter=true`, and safety-contract evidence.

Sidecar consolidation bridge:

```text
D:\AI_round2\aether-core\aether\sidecar\consolidation.py
D:\AI_round2\aether-core\tests\test_sidecar_consolidation.py
D:\AI_round2\labs\meaning_compression_lab\workbench_trace_fixture.py
D:\AI_round2\labs\meaning_compression_lab\workbench_trace_evidence_attach_cli.py
D:\AI_round2\tests\test_workbench_trace_fixture.py
```

The sidecar consolidation preview now surfaces RAG evidence only when it is
already embedded in a persisted trace as:

```text
local_router_trace.evidence_review.kind = local_router_rag_evidence_review
```

It refuses the candidate unless the embedded safety contract says:

```text
memory_writes_allowed = false
silent_policy_mutation_allowed = false
raw_chain_of_thought_stored = false
```

The `/v1/consolidation/candidates` endpoint remains read-only: it can expose
the RAG evidence as a Reflect-routed, adapter-required learner candidate, but it
does not create reflections, import support patterns, or write memory.

Trace attachment bridge:

```text
attach_rag_evidence_review_to_trace_fixture(...)
```

This attaches generated `evidence_review` metadata to an existing isolated
Workbench trace row:

```text
trace.local_router_trace.evidence_review = generated review metadata
trace.local_router_trace.evidence_review_fixture_import_only = true
trace.local_router_trace.memory_write_allowed = false
```

It refuses the live Workbench DB by default, updates only the trace JSON, and
returns a receipt with `memory_writes_performed=false`,
`support_pattern_import_performed=false`, and
`reflection_create_performed=false`.

CLI usage:

```text
python -m labs.meaning_compression_lab.workbench_trace_evidence_attach_cli ^
  --db-path <workbench.db> ^
  --turn-id <turn_id> ^
  --rag-result-path <rag_suite_result.json>
```

For the live DB, the command requires both flags:

```text
--allow-live-db --confirm-live-db ATTACH_REVIEW_ONLY_TRACE_EVIDENCE
```

That double opt-in exists so lab evidence cannot be attached to the dogfood DB
by accident. Even with the opt-in, the command writes only trace JSON.

## Next Work

```text
1. Keep the live-DB attach command manual and double-confirmed; do not automate
   it from scheduled lab runs.
2. Decide whether a UI affordance should expose attached evidence_review rows
   for selected historical traces, or whether CLI-only is enough.
3. Feed adapted trace/evidence summaries into Phase 2 learner preview as
   review-only evidence.
4. Use larger blind/adversarial mixes for new evidence; do not keep tuning
   against the same adversarial v1/v2 or targeted perturbed pocket.
```

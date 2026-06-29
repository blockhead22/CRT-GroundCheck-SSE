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

## Next Work

```text
1. Add an optional script/CLI wrapper around the isolated fixture import if it
   becomes useful for manual review.
2. Feed adapted trace summaries into Phase 2 learner preview as review-only
   evidence.
3. Review low-score/no-hard-flag replay failures for anchor fit.
```

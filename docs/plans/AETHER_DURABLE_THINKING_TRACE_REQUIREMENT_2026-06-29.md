# Aether Durable Thinking Trace Requirement - 2026-06-29

## Requirement

Aether needs durable, inspectable thinking traces for CRT/Aether reasoning. This
applies to current turns and historical messages. After restart, the system
should be able to reopen a message and reference the trace that produced it.

This should not store private hidden scratchpad as the source of truth. The
trace should be a structured audit object plus a user-facing thinking/process
drawer that explains system behavior without depending on private model
internals.

The product goal is still a visible thinking-trace experience. Aether should be
able to show how an answer was formed in a dropdown/drawer for current and
historical messages. The displayed trace may include deterministic governance
steps and a bounded public model-authored rationale, but it must be labeled as
public rationale and checked against governed evidence before it is treated as
evidence.

## Trace Object

Each assistant turn should be able to persist:

```text
turn_id
conversation_id
timestamp
user_request_summary
task_type
route_selected
model_selected
scaffold_profile
retrieved_memory_ids
retrieved_chat_ids
mirus_packet_summary
evidence_anchors
allowed_inferences
disallowed_inferences
draft_quality_score
verifier_flags
repair_attempts
fallback_used
final_confidence
contradiction_notes
learning_candidates
promotion_status
public_rationale_lines
tool_consideration_steps
governance_step_events
ui_sections
```

## Why It Matters

The current local-router lab shows that small models get more coherent when the
system externalizes cognition:

```text
classify -> retrieve -> build semantic spine -> draft -> verify -> repair -> store
```

If that loop is not persisted, Aether loses one of the main advantages of the
architecture. Durable traces make the system restartable, inspectable, and able
to learn from prior failures without pretending the model itself remembered
everything.

## UI Pattern

The target pattern is similar to an Activity panel / expandable thinking trace:

```text
Thinking
- Classified as grant_business
- Retrieved 3 memory anchors and 1 past chat
- Built Mirus packet from verified project facts
- Routed to qwen2.5:7b-instruct / section_lock
- Public rationale: "I need to answer this as funding exploration, not medical advice."
- Repaired once for unsupported guarantee language

Memory
- Wisconsin location context
- Printing Lair ownership
- Aeteros/Aether roadmap note

Verifier
- No unsupported numeric claims
- No autonomous-truth claim
- Limit language present

Learning Candidates
- "Grant/business prompts need stricter outcome-promise language"
```

Workbench UI target:

```text
Each assistant message gets a compact "Thinking" affordance.
Opening it shows:

1. Thinking / Process
2. Memory checked
3. Tools considered or used
4. Verifier and repair/fallback
5. Learning candidates

Historical messages should load the same trace after restart.
```

## Roadmap Placement

This belongs in Aether/Core, not only the lab. The lab should prove the trace
schema first, then the main app can adopt it.

The next learning layer should be the weighted feedback ledger:

```text
D:\AI_round2\docs\plans\AETHER_WEIGHTED_FEEDBACK_LEDGER_2026-06-29.md
```

Feedback should attach to answer + trace as scored/taged review data. It should
produce learning candidates, not silent model or memory mutation.

Success criteria:

```text
1. Router CLI writes a trace JSON for every run. DONE in lab.
2. Replay eval can grade both answer quality and trace quality. DONE in lab.
3. A historical run can reload answer + trace after process restart.
4. Learning candidates remain pending until promoted, rejected, or merged.
5. The UI can show a compact trace without exposing private hidden scratchpad.
6. The UI can optionally show model-authored public rationale lines when they
   are intentionally generated for display and verified against the governance
   trace.
```

## Decision

Keep working on the lab only if the next phase builds this trace layer. More
prompt tuning alone is not enough. The lab is worthwhile when it produces the
durable substrate Aether needs: memory, evidence, route, verifier, repair, and
learning traces bound to every message.

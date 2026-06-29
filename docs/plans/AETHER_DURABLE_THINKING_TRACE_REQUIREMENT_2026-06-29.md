# Aether Durable Thinking Trace Requirement - 2026-06-29

## Requirement

Aether needs durable, inspectable thinking traces for CRT/Aether reasoning. This
applies to current turns and historical messages. After restart, the system
should be able to reopen a message and reference the trace that produced it.

This should not store raw hidden chain-of-thought as the source of truth. The
trace should be a structured audit object that explains system behavior without
depending on private model internals.

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

The target pattern is similar to an Activity panel:

```text
Thinking
- Classified as grant_business
- Retrieved 3 memory anchors and 1 past chat
- Built Mirus packet from verified project facts
- Routed to qwen2.5:7b-instruct / section_lock
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

## Roadmap Placement

This belongs in Aether/Core, not only the lab. The lab should prove the trace
schema first, then the main app can adopt it.

Success criteria:

```text
1. Router CLI writes a trace JSON for every run. DONE in lab.
2. Replay eval can grade both answer quality and trace quality. DONE in lab.
3. A historical run can reload answer + trace after process restart.
4. Learning candidates remain pending until promoted, rejected, or merged.
5. The UI can show a compact trace without exposing raw hidden reasoning.
```

## Decision

Keep working on the lab only if the next phase builds this trace layer. More
prompt tuning alone is not enough. The lab is worthwhile when it produces the
durable substrate Aether needs: memory, evidence, route, verifier, repair, and
learning traces bound to every message.

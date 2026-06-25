# Aether Background Consolidation / Governed Mirus Loop - 2026-06-24

Purpose: convert the recovered Mirus/background-loop idea into current Aether
language without creating a silent memory crawler.

## Core Contract

The loop is:

```text
observe -> summarize -> classify -> propose -> review -> apply
```

It may inspect recent turns, traces, route metadata, review outcomes, and
contradiction dispositions. It may produce reviewable candidates. It must not
silently write confirmed memory, confirmed project facts, permanent support
style, or Aether behavior rules.

## Candidate Types

All candidates start with:

- `review_required=true`;
- `memory_write_allowed=false`;
- `confirmed_fact=false`;
- evidence references to turns/traces/review receipts;
- a risk/boundary note.

Initial candidate categories:

| Category | Target Review Surface | Trigger |
| --- | --- | --- |
| `contradiction_review` | Memory drawer/review queue | conflicted trace packet with resolvable/evolving/contextual disposition |
| `support_style_candidate` | Support-pattern review queue | repeated style/support requests such as dork spiral, motivation, courtroom, verbose/deep |
| `project_context_candidate` | Project/context review queue | roadmap/phase/next-step continuity turns |
| `aether_self_improvement` | Reflection review queue | repair fallback, thin answer, stronger-model need, wrong route, weak tool use |

## Current Slice

Implemented pure candidate planner:

```text
D:\AI_round2\aether-core\aether\sidecar\consolidation.py
```

It accepts recent turn/trace dictionaries and returns review-only consolidation
candidates. It does not persist anything. This lets tests lock the safety
contract before a scheduler, API, or UI exists.

Implemented preview endpoint:

```text
GET /v1/consolidation/candidates?limit=...
```

The endpoint reads recent Workbench turns/traces, calls the pure planner, and
returns candidates with explicit preview metadata:

- `mode=preview_only`;
- `writes_performed=false`;
- `memory_ingestion_performed=false`;
- `support_pattern_import_performed=false`;
- `reflection_create_performed=false`.

Implemented review-route metadata:

Each preview candidate now includes `review_route` so the UI/API can send the
candidate toward the correct existing review surface without applying it:

- `contradiction_review` -> Memory review via `GET /v1/slots/{slot_id}`;
- `support_style_candidate` -> Support review draft;
- `project_context_candidate` -> Reflection draft with `subject=project`;
- `aether_self_improvement` -> Reflection draft with `subject=agent`.

Focused tests:

```text
D:\AI_round2\aether-core\tests\test_sidecar_consolidation.py
```

They verify:

- contradiction candidates do not leak conflicted evidence values;
- support-style and project-context candidates remain review-only;
- self-improvement candidates can be proposed from repair/continuation/stronger-model traces;
- no candidate can mark itself as confirmed fact or memory-write allowed.
- the preview endpoint returns candidates without creating reflections, support
  patterns, or memory writes.
- preview candidates include review routes to Memory, Support, or Reflection
  surfaces without directly invoking those surfaces.

## Next Implementation Steps

1. Add a Workbench review drawer/tab for consolidation candidates that uses
`review_route` to open the existing Memory, Support, or Reflection review
surface.

2. Add accept/defer/reject receipts. Acceptance should dispatch through existing
review APIs:

- contradiction review -> memory confirm/correct/quarantine/context action;
- support style -> support-pattern candidate import/review;
- Aether self-improvement -> reflection create/review;
- project context -> reviewed project note or document/context queue.

3. Only after preview and review are stable, wire the automation heartbeat to run
the preview periodically.

## Explicit Non-Goals

- Do not ingest ChatGPT archive bodies into Aether voice.
- Do not infer sensitive personal facts from style requests.
- Do not auto-confirm facts from recent chat momentum.
- Do not let the loop modify prompts directly.
- Do not revive old Mirus/Holden names as user-facing product surface.

## Roadmap Placement

This is the Phase 2 bridge between:

- Phase 1.7 support/tone/reviewed pattern reliability;
- Phase 1.8 contradiction disposition governance;
- Phase 1.9 memory-state/context-compression evals;
- later meaning trace graph / replay work.

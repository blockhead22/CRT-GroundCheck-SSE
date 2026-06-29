# Aether Weighted Feedback Ledger - 2026-06-29

## Decision

Aether should not learn from a bare thumbs-up/thumbs-down signal. Binary
feedback is useful as a surface gesture, but it is too lossy for CRT/Aether.

The system needs a structured feedback ledger attached to answer + trace.

## Why Binary Is Not Enough

An answer can be:

```text
true but emotionally wrong
useful but overconfident
warm but ungrounded
well structured but missing receipts
technically correct but bad for the roadmap
good answer with a bad trace
bad answer with a useful failure signal
```

If all of those collapse into `like` or `dislike`, Aether loses the meaning of
the correction.

## Feedback Object

Each reviewed answer should be able to record:

```text
feedback_id
answer_id
trace_id
task_type
route
scaffold_profile
overall: like | mixed | dislike
scores:
  groundedness: 0-5
  usefulness: 0-5
  tone_fit: 0-5
  receipt_use: 0-5
  overclaim_risk: 0-5
  trace_quality: 0-5
  next_step_clarity: 0-5
tags:
  too_generic
  overpromised
  missed_context
  missing_receipts
  process_leakage
  medical_or_regulated_overreach
  strong_trace
  weak_trace
  good_spiral
  bad_grant_language
human_note
promotion_decision
```

## Learning Levels

Do this in stages:

```text
Level 1: deterministic fixes
  Rules, forbidden terms, route policies, scaffold changes.

Level 2: weighted feedback ledger
  Human/eval feedback with scores and tags.

Level 3: policy tuning
  Use repeated failure tags to update scaffolds, routing, and verifier gates.

Level 4: predictive scorer
  Only after enough labeled examples, predict failure risk or best scaffold.

Level 5: actual learning model
  Much later, only if dataset size and task stability justify it.
```

Current project state is Level 1 moving into Level 2. Do not jump straight to a
neural reward model.

## Programmatic Use

Examples:

```text
If grant_business repeatedly gets overpromised:
  tighten grant scaffold and forbidden language.

If personal_synthesis repeatedly gets too_generic:
  require stronger Mirus receipts before Holden renders.

If trace passes but answer fails:
  rendering/scaffold problem, not trace substrate problem.

If trace fails:
  Mirus/trace issue.

If repair is repeatedly needed:
  primary scaffold or route policy needs adjustment.
```

## Roadmap Placement

This belongs after the durable trace lab proves answer + trace replay:

```text
answer -> trace -> verifier -> weighted feedback
-> failure tags -> review-only learning candidate
-> approved policy/scaffold update
```

Feedback should produce learning candidates, not silent behavioral mutation.

## Near-Term Scheduler Guidance

The scheduler should not implement a predictive model yet.

Good next steps when the replay pass is complete:

```text
1. Add feedback schema constants or a small JSON fixture.
2. Attach manual/eval feedback to replay rows.
3. Produce feedback-derived learning candidates.
4. Summarize repeated tags by route/scaffold.
5. Only then consider whether a predictive scorer is warranted.
```

## Implementation Pass

Implemented after the clean 32/32 replay:

```text
D:\AI_round2\labs\meaning_compression_lab\local_router_feedback_ledger.py
D:\AI_round2\tests\test_local_router_feedback_ledger.py
```

Artifact generated from the final curated replay:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_feedback_ledger_1782716566.json
```

Result:

```text
feedback rows: 32
mode: review_only
writes_performed: false
memory_ingestion_performed: false
support_pattern_import_performed: false
reflection_create_performed: false

tag_counts:
  combined_passed: 32
  raw_failed: 32
  routed_passed: 32
  routed_improved: 32
  strong_trace: 32
  missing_receipts: 12
  repair_used: 5
  fallback_used: 5
```

Workbench preview candidates:

```text
4 review-only candidates
1 reflection candidate for fallback usage
3 support-pattern candidates for repeated weaker receipt coverage
memory_write_allowed: false
confirmed_fact: false
requires_adapter: true
```

Interpretation:

```text
The clean 32/32 replay does not mean "silently learn this." It means the system
has enough trace/eval evidence to create reviewed metadata candidates. The
feedback ledger is now the bridge from passing lab evidence to Workbench review
flow.
```

Verification:

```text
python -m pytest tests\test_local_router_feedback_ledger.py tests\test_local_router_cli.py tests\test_local_router_eval.py tests\test_local_router_replay.py -q
40 passed
```

## Workbench Review Fixture

The 4 feedback-ledger candidates now render through the real Workbench Learn
drawer as preview-only review items:

```text
D:\AI_round2\workbench\src\fixtures\localRouterFeedbackPreview.ts
D:\AI_round2\workbench\src\App.test.tsx
```

Coverage:

```text
1 fallback-use reflection candidate opens as a manual Reflect draft.
3 weak-receipt support-pattern candidates open as manual Support drafts.
writes remain false.
support imports remain manual.
reflection creation remains manual.
memory writes remain blocked.
```

Verification:

```text
python -m pytest tests\test_local_router_feedback_ledger.py -q
2 passed

cd D:\AI_round2\workbench
npm run test:ui -- --run src/App.test.tsx
15 passed
```

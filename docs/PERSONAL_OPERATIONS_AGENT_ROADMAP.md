# Aether Personal Operations Agent â€” Delivery Roadmap

## Delivery principle

Build the reflection substrate before adding proactive behavior. Aether must
first prove that it can observe, propose, accept correction, and preserve
rejection. Only then should it remind, schedule, or intervene.

## Phase 0 â€” Freeze contracts

Deliverables:

- Reflection schema and status transitions.
- High-stakes interpretation policy.
- Evidence-link contract.
- Confidence and expiration rules.
- Ten acceptance fixtures, including incorrect and rejected reflections.

Gate:

- A rejected reflection cannot reappear as accepted memory without new evidence
  and explicit review.
- Observation and interpretation are structurally separate.

## Phase 1 â€” Passive reflection ledger

Backend:

- Add reflection, evidence, and review tables to `workbench.db`.
- Add idempotent create/review/supersede operations.
- Add APIs to list, inspect, accept, reject, revise, and expire reflections.
- Link reflections to turns, documents, slots, tool receipts, and action outcomes.

Workbench:

- Add Reflect drawer.
- Render observation, evidence, alternatives, confidence, and time window.
- Add Accept, Reject, Revise, and Defer.

No proactive prompts, scheduler, or strategy changes yet.

Gate:

- Restart persistence.
- Stale revision rejection.
- Idempotent reviews.
- Rejected hypothesis remains visible but inactive.

## Phase 2 â€” Daily plan and outcome capture

Add:

- Daily plan with one required and up to two optional actions.
- Explicit smallest-next-action field.
- Outcome states: done, reduced, postponed, irrelevant, wrong priority.
- Optional user note and reported effort/stress.
- Manual morning and evening entry points.

Gate:

- Aether can distinguish no outcome from failure.
- Changed priorities do not count as avoidance.
- Plans and outcomes remain editable and auditable.

## Phase 3 â€” Agent reflection

Generate one bounded reflection after enough outcome evidence:

- What strategy was used?
- What response followed?
- Was the intervention helpful, neutral, annoying, or mistimed?
- What smaller adjustment should be tested?

Store it as a provisional reflection requiring review.

Gate:

- No personality labeling.
- No strategy mutation before acceptance.
- Every claim links to intervention and outcome receipts.
- Local model output passes deterministic schema and policy validation.

## Phase 4 â€” Personal and workflow reflection

Candidate types:

- ambiguous-next-action pattern;
- repeated task reduction;
- timing preference;
- workload/completion mismatch;
- project-interest shift;
- language/orientation change around a topic.

Requirements:

- minimum evidence count;
- bounded time window;
- alternatives;
- ask-first language;
- confidence ceiling without explicit confirmation.

Gate:

- Held-out examples distinguish observations from diagnoses.
- Temporary frustration does not become a permanent trait.
- User correction supersedes generated interpretation.

## Phase 5 â€” Reversible experiments

Example:

```text
Hypothesis:
Large morning task lists increase overload.

Experiment:
For three mornings show one required and two optional actions.

Measure:
Starts, completions, postponements, and reported stress.
```

Add:

- experiment proposal and consent;
- bounded duration;
- measurement plan;
- stop/cancel;
- result review;
- keep, reject, or revise strategy.

Gate:

- No covert experiments.
- Experiment cannot expand scope automatically.
- Missing evidence yields inconclusive, not success or failure.

## Phase 6 â€” Manual daily loop

```text
Morning plan
  -> optional intervention
  -> outcome capture
  -> evening reflection
  -> one proposed improvement
  -> user review
```

Still user-initiated. No background scheduler.

Gate:

- Seven-day manual dogfood.
- Measure reflection acceptance, rejection, revision, and annoyance.
- At least one demonstrated self-correction after rejection.

## Phase 7 â€” Scheduled sidecar behavior

Only after Phase 6:

- opt-in scheduler owned by the local sidecar;
- quiet hours;
- maximum intervention frequency;
- snooze, dismiss, irrelevant, and stop controls;
- missed-run and restart behavior;
- no automatic frontier calls.

Gate:

- Every scheduled action has consent, strategy, and evidence.
- Duplicate execution is prevented by idempotency keys.
- Ambiguous timeout completion is detectable.

## Phase 8 â€” Weekly strategy review

Summarize:

- strategies attempted;
- accepted and rejected reflections;
- experiments and outcomes;
- unresolved uncertainty;
- recommended strategy changes.

The user approves strategy changes explicitly.

## First implementation sprint

Give this bounded task to an implementation agent:

1. Add reflection tables and data-access methods.
2. Add reflection API endpoints.
3. Add Reflect drawer with evidence and review actions.
4. Seed deterministic fixtures; do not generate reflections yet.
5. Test persistence, idempotency, rejection, supersession, and stale revision.

Write scope:

- `aether-core/aether/sidecar/db.py`
- `aether-core/aether/sidecar/app.py`
- new `aether-core/aether/sidecar/reflections.py`
- focused sidecar tests
- Workbench API/types/App
- new reflection drawer and tests
- styles needed for that drawer

Explicitly exclude:

- scheduler;
- notifications;
- sentiment model;
- automatic reflection generation;
- automatic strategy changes;
- frontier calls;
- task/calendar integrations.

## Evaluation set

Include at least:

- correct workflow pattern;
- plausible but wrong interpretation;
- insufficient evidence;
- stale evidence;
- contradictory evidence;
- attitude change with multiple explanations;
- user rejection;
- later new evidence after rejection;
- agent intervention that annoyed the user;
- task postponed because priority legitimately changed.

## Next decision after the sprint

Do not immediately add reminders. First inspect whether the reflection ledger
feels understandable and safe. If reviewing reflections is confusing or
burdensome, simplify the evidence/review experience before generating them
automatically.


## Phase 1 implementation status — June 22, 2026

Completed:

- persistent reflection, evidence, and immutable review records;
- revision-hash and idempotency guards;
- accept, reject, defer, expire, and superseding revision transitions;
- Reflect drawer with explicit observation, interpretation, alternatives,
  evidence, confidence, experiment, and review controls;
- deterministic backend and UI fixtures.

Automatic reflection generation, reminders, scheduling, and strategy mutation
remain intentionally disabled.
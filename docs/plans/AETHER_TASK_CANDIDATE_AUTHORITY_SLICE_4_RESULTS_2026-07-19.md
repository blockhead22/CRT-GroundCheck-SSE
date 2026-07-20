# Aether Task Candidate Authority Slice 4 Results

**Date:** 2026-07-19

## Result

Mirus now has a narrow live path from first-person planning language to an
inspectable, review-only task candidate. The candidate is inert until the user
explicitly promotes it in Workbench. Promotion creates one existing,
revisioned task-authority record; rejection creates none.

This closes the Slice 3 product decision in favor of a compact learner-review
surface. It does not grant Mirus automatic task authority and does not turn
ordinary conversation into profile memory.

## Implemented Path

```text
user planning turn
-> deterministic Mirus task-candidate intake
-> durable public trace candidate and evidence receipt
-> Learn / Tasks review queue
-> explicit Promote or Reject
-> review-confirmed open loop or constraint
-> durable decision receipt
```

The first intake slice recognizes direct first-person action items and a small
set of scheduling or conditional constraints. Negated, hypothetical,
third-party, and example language remains ineligible.

The compound purpose-plus-runtime-model meta prompt was also repaired. Aether
now answers both requested jobs while preserving the authoritative distinction
between the deterministic current answer path and the model selected for normal
generative answers.

## Authority Boundary

- Candidate creation writes no task authority and no memory.
- Promotion is explicit, project-scoped, idempotent, and server-validated from
  the persisted trace candidate.
- Open-loop and constraint records use `source_type=review_confirmed`.
- Rejection writes only its review receipt.
- Reviewed candidates remain out of the active queue after page reload and
  sidecar restart.
- The path stores public evidence and decision metadata, not hidden model
  chain-of-thought.

## Verification

Backend focused and adjacent suite:

```text
143 passed
```

Workbench full UI and Electron suites:

```text
73 component tests passed
26 Electron tests passed
```

Workbench production build passed.

Isolated rendered Workbench dogfood used a five-candidate filming-week trace.
Before review, Workbench showed all five as review-only with task authority and
memory writes blocked. Promoting `Edit footage` created exactly one
`review_confirmed` open loop. Rejecting `Meeting possibly Thursday` created no
authority. Three candidates remained after refresh, page reload, and a fresh
sidecar process. The QA substrate remained at zero memory slots, the browser
console was clean, and the desktop viewport had no horizontal overflow.

Backend integration also covers promotion of a constraint, rejected-candidate
non-effect, sidecar restart, and later revocation of the promoted constraint.

## Limits

This is deterministic, narrow intake, not general semantic task understanding,
neural learning, or autonomous execution. It will miss valid planning language
outside its current patterns. Expanding it should be driven by held-out false
positive and false negative evidence, with scaffolded/model-assisted extraction
allowed only behind the same review-only contract.

## Decision

The bounded governed-continuity gate is closed for reviewed task authority:
Aether can retrieve durable open loops, require explicit selection when
ambiguous, carry explicit artifacts and constraints, and let Mirus propose new
task state without silently granting it authority.

The next main product lane is desktop distribution readiness. Keep task intake
expansion tied to daily dogfooding failures rather than speculative taxonomy.

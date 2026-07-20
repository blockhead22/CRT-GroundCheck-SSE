# Aether Task Authority Slice 3 Results

**Date:** 2026-07-19

## Outcome

Aether now has explicit, persistent, revisioned sources for task artifacts and
task constraints. Current artifacts, active constraints, and revoked
constraints enter `TaskContinuationPacket` as separate typed records. They are
not inferred from Git status, archived prose, assistant output, or model text.

The records shape response context only. They do not authorize automatic
execution, workspace tools, profile-memory writes, or any durable write during
`/resume`.

## Persistence Contract

The new task-authority ledger stores:

```text
record kind: artifact | constraint
project root
summary
artifact locator or constraint statement
typed category
source: user_explicit | review_confirmed
status
idempotency key
created/updated time
revision hash
```

Allowed transitions are deliberately narrow:

```text
artifact:   current <-> retired
constraint: active  <-> revoked
```

Every review requires the exact current revision. Stale transitions return a
conflict and cannot silently restore prior authority. Records are scoped by
profile database and continuity project root.

## API And Packet

Project-scoped endpoints now exist for:

```text
GET/POST /v1/continuity/artifacts
POST     /v1/continuity/artifacts/{record_id}/review
GET/POST /v1/continuity/constraints
POST     /v1/continuity/constraints/{record_id}/review
```

`TaskContinuationPacket` releases:

```text
artifacts             current records only
active_constraints    active records only
revoked_constraints   historical records, explicitly not active
```

The receipt records all three counts alongside selected-loop authority and the
existing blocked execution/tool/write fields. The deterministic answer labels
revoked constraints as not active. Workbench Trace renders the same typed
records and counts.

## Frozen Product Regression

Manifest:

```text
tests/fixtures/task_continuation_eval_v1.json
SHA-256: 8ac8540aa1cdc280aa57b36056762273e6273c45d7667983984fd755f0179b90
```

Runner:

```text
python scripts/task_continuation_eval.py
```

The pack contains 36 cases: three synthetic wording variants across twelve
families.

```text
single open loop
no open loop
ambiguous loops
explicit revision-bound choice
stale selection
foreign-profile selection
completed-only state
deferred-only state
current/retired artifact mix
active/revoked constraint mix
rejected assistant output only
combined pending/completed/deferred/artifact/constraint state
```

Result:

```text
36/36 passed
12/12 families passed 3/3
model calls: 0
elapsed: 21.874 seconds
```

Every case seeded state, restarted the sidecar profile, sent `/resume` through
the real API, loaded the persisted trace, and checked status, selection mode,
state counts, content boundaries, zero tool runs, zero memory writes, and
blocked execution.

## Validation

Backend:

```text
python -m pytest tests\test_continuity_task_state.py tests\test_task_continuation.py tests\test_sidecar_continuity_chat.py tests\test_task_continuation_eval.py -q
23 passed

python -m py_compile aether\sidecar\continuity_task_state.py aether\sidecar\task_continuation.py aether\sidecar\app.py aether\sidecar\db.py scripts\task_continuation_eval.py
passed
```

Workbench:

```text
npm test
Vitest: 71 passed
Electron: 26 passed

npm run build
passed
```

## Isolated Rendered Workbench Proof

The rendered probe used a disposable profile with one open loop, one current
artifact, one active constraint, and one revoked constraint.

```text
turn: turn_b17c7c2505cc
task status: selected
selection: automatic_single, valid
artifacts: 1
active constraints: 1
revoked constraints: 1, visibly labeled not active
automatic execution: blocked
workspace tools: blocked
durable writes: 0
profile writes: 0
console warnings/errors: 0
error overlay: no
horizontal overflow: no
```

## Honest Limits

- This is a white-box product regression authored after the implementation,
  not a blind or held-out generalization result.
- The three wording variants per family repeat the same deterministic state
  mechanism; `36/36` means the contract is internally stable, not that broad
  agentic task recovery is solved.
- Artifact locators are governed references. Aether does not dereference,
  verify, or execute them in this slice.
- Workbench displays task authority but does not yet provide a dedicated
  create/retire/revoke/restore review surface.
- The rendered authority probe was not reopened after a fresh sidecar restart;
  automated API and trace tests cover restart persistence.
- No executor consumes the packet. `/resume` still aligns the response only.

## Next Gate

1. Reopen the same artifact/constraint receipt in Workbench after a fresh
   sidecar restart and verify visible rehydration.
2. Decide whether task-authority management remains an advanced API or becomes
   a small explicit Workbench Task State review surface.
3. Close governed continuity only after that product decision and UI
   rehydration evidence are recorded.
4. Then resume desktop distribution readiness rather than reopening router,
   learner, or model-tuning labs.


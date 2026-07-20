# Aether Task Continuation Slice 2 Results

**Date:** 2026-07-19

## Outcome

Workbench can now resolve an ambiguous `/resume` request through an explicit,
revision-bound user choice. The choice aligns the current response to one
durable open loop. It does not authorize automatic execution, workspace tools,
profile memory writes, or any other durable write.

This closes the explicit-selection gap identified by Slice 1. It does not close
the broader continuity gate.

## Implemented Contract

The chat request may carry:

```text
task_continuation_selection.loop_id
task_continuation_selection.revision_hash
```

The sidecar validates both fields against the current project's open-loop
state before authorizing conversational continuation:

```text
matching open loop + exact revision -> selected
changed revision                    -> stale_selection
loop absent from current project    -> selection_unavailable
partial selection                   -> invalid_selection
multiple loops without selection    -> ambiguous
```

The selected packet and receipt record the requested loop, expected revision,
current selected revision, selection mode, validation result, and failure
reason. Old persisted traces remain readable because the new fields are
optional in the Workbench types.

## Product Surface

When `/resume` finds multiple open loops, Workbench shows a compact
`Choose work to resume` panel. Each action carries the exact loop ID and
revision rendered by the ambiguous trace. Stale and unavailable selections
return to the same recoverable choice surface instead of silently selecting a
different loop.

The Trace drawer exposes:

- task-continuation status;
- selection mode;
- whether selection validation passed;
- a bounded failure reason when it did not;
- selected loop and blocked execution/write boundaries.

## Validation

Backend:

```text
python -m pytest tests\test_task_continuation.py tests\test_sidecar_continuity_chat.py -q
15 passed

python -m py_compile aether\sidecar\task_continuation.py aether\sidecar\app.py
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

Coverage includes:

- explicit choice among two open loops;
- exact revision validation;
- stale revision after defer/reopen;
- wrong-project selection that cannot fall through to a local loop;
- selected packet and receipt persistence;
- sidecar restart and historical trace rehydration;
- Workbench request payload and Trace drawer rendering.

## Isolated Rendered Workbench Proof

The browser probe used a disposable Aether home and profile with two synthetic
open loops. It did not touch the live personal substrate.

Ambiguous turn:

```text
turn_e810ef610e35
status: ambiguous
choices rendered: 2
```

Selected turn:

```text
turn_48e5e964b545
selected loop: continuity_loop_897d411dcdb6
selected revision: e88fe33b6fe95f68ad2833a13af598c3d4df87022a8b3f5099a071be78b72d7f
selection mode: explicit_user_choice
selection valid: yes
automatic execution: blocked
workspace tools: blocked
durable writes: 0
profile writes: 0
```

Rendered checks also found:

```text
page title: Aether Workbench
nonblank UI: yes
Vite error overlay: no
console warnings/errors: 0
horizontal overflow: no
```

The rendered pass also exposed one conflicting legacy affordance: an ambiguous
turn could show Done/Defer controls for a coincidentally matched open-loop atom
above the revision-bound picker. Workbench now suppresses loop-management
actions for ambiguous, stale, unavailable, and invalid selections. The picker
is the only continuation action in those states; the post-fix component suite
and production build pass.

## Honest Limits

- This remains response alignment, not task execution recovery.
- No executor consumes the selected packet.
- Structured artifacts and active/revoked constraints still lack dedicated
  authority sources.
- The ordinary continuity answer remains partially checked where evidence
  relevance is not applicable; the task-selection receipt is exact.
- The frozen multi-thread task-state evaluation does not exist yet.
- These tests prove the local contract and UI path, not broad autonomous-agent
  reliability.

## Next Gate

1. Define explicit, revisioned sources for task artifacts and active/revoked
   constraints. Do not infer them from Git status or old prose.
2. Freeze a separate 30-40 case task-state pack covering pending, completed,
   deferred, changed, stale, cross-profile, restart, unavailable, rejected
   assistant output, artifact, and constraint cases.
3. Run the real sidecar and Workbench path against that frozen pack.
4. Close governed continuity only if authority, no-write behavior, direct API,
   visible UI, restart, and trace rehydration agree.

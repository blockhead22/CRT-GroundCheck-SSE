# Aether Isolated Fixture Eval Runbook - 2026-06-25

Purpose: run behavior evals that require seeded memory/review state without
touching Nick's live Aether substrate or Workbench database.

Use these helpers when an eval case needs controlled facts, conflicts, or
reviewed support-pattern candidates. Do not add live-memory seeding endpoints for
these checks.

## Safety Contract

- Creates a temporary Aether data directory.
- Starts a temporary FastAPI sidecar on an ephemeral local port.
- Seeds synthetic fixture data only inside that temporary directory.
- Runs the selected eval cases against the temporary sidecar.
- Tears the sidecar down after the run.
- Does not mutate live memory, live support-pattern reviews, or the live
  Workbench database.
- `--no-write` skips JSON report output.
- `--keep-fixture-dir` copies the temporary fixture directory after the run for
  inspection.

## Phase 1.8 Contradiction Dispositions

This is the safe way to run the `--include-disposition-eval` cases.

From `aether-core`:

```powershell
cd D:\AI_round2\aether-core
python scripts\run_disposition_fixture_eval.py --no-write
```

From `workbench`:

```powershell
cd D:\AI_round2\workbench
npm run eval:dispositions:no-write
```

To keep the generated fixture directory for inspection:

```powershell
cd D:\AI_round2\workbench
npm run eval:dispositions:keep -- --no-write
```

The fixture covers all six first-pass disposition labels:

- `resolvable`
- `held`
- `evolving`
- `contextual`
- `stale`
- `policy_bound`

The eval checks:

- deterministic review-style answer shape;
- trace-packet `contradiction_disposition` metadata;
- `/v1/slots/{slot_id}` review-surface disposition metadata;
- no leakage of conflicted restricted values.

## Phase 1.7 Reviewed Support Patterns

This is the safe way to run accepted/rejected support-pattern release checks.

From `aether-core`:

```powershell
cd D:\AI_round2\aether-core
python scripts\run_support_pattern_fixture_eval.py --no-write
```

From `workbench`:

```powershell
cd D:\AI_round2\workbench
npm run eval:support-patterns:no-write
```

To keep the generated fixture directory for inspection:

```powershell
cd D:\AI_round2\workbench
npm run eval:support-patterns:keep -- --no-write
```

The fixture verifies:

- accepted support-pattern candidates are released through
  `context_bridge.reviewed_support_patterns`;
- rejected support-pattern candidates are excluded;
- support patterns remain behavior guidance, not confirmed memory;
- live memory is not mutated.

## When To Use Live Eval Runner Directly

Use `scripts\workbench_eval.py --include-disposition-eval` only when you have
already started a controlled fixture sidecar with the expected synthetic
conflicts. The direct runner does not seed or mutate memory. Against a normal
live Workbench sidecar, those cases will usually fail because Nick's real
substrate should not contain the synthetic fixture conflicts.

Preferred command:

```powershell
python scripts\run_disposition_fixture_eval.py --no-write
```

Not preferred against the live sidecar:

```powershell
python scripts\workbench_eval.py --include-disposition-eval
```

## Expected Passing Results

Current expected fixture results:

```text
disposition fixture: 6/6 passed
support-pattern fixture: 2/2 passed
```

If these fail, inspect the report or rerun with `--keep-fixture-dir --no-write`
and check:

- route source;
- selected/generation model;
- trace packets;
- slot detail response;
- released support-pattern ids.

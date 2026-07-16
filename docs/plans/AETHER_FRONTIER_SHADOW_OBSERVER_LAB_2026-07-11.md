# Aether Frontier Shadow Observer Lab

**Date:** 2026-07-11  
**Status:** Contract and frozen evaluator implemented; runtime wiring deliberately absent

## Question

Can a frontier Codex model quietly grade accepted Aether turns and suggest
bounded investigation targets without becoming Aether's voice, memory, router,
verifier authority, or automatic improver?

## Intended Role

The observer sees only:

- the accepted user prompt;
- the accepted final answer;
- an allow-listed public trace summary;
- the fixed quality rubric.

It grades directness, grounding, source fidelity, route/tool fit, memory
authority, uncertainty, continuity, personality, formatting, sensitive-context
fit, and non-canned synthesis. Findings quote short excerpts from the accepted
answer. Suggestions may target an evidence-release, route, prompt-spine,
verifier, repair, model-policy, or UI-trace investigation.

Suggestions are inert and always require human review. They do not affect the
graded answer or future turns.

## Safety Contract

- disabled by default;
- sampling defaults to zero;
- `codex exec --ephemeral --sandbox read-only`;
- isolated temporary working directory;
- JSON Schema output;
- no full trace, hidden chain-of-thought, memory candidate bodies, or database;
- no Memory, Support, Reflection, belief, policy, route, open-loop, or code
  writes;
- invalid output fails closed;
- no automatic application of suggestions;
- no runtime/Workbench wiring in this slice.

`--ephemeral` prevents persistent Codex rollout files for the run. It should not
be described as a cloud data-retention guarantee; account data controls still
apply to material sent to the hosted model.

## Configuration Stubs

```text
AETHER_FRONTIER_OBSERVER_ENABLED=0
AETHER_FRONTIER_OBSERVER_SAMPLE_RATE=0
AETHER_FRONTIER_OBSERVER_COMMAND=codex
AETHER_FRONTIER_OBSERVER_MODEL=
AETHER_FRONTIER_OBSERVER_TIMEOUT_SECONDS=120
```

The eventual UI should expose a simple Off / Sample / Every turn control and a
separate visibility toggle. It should not expose a wall of tuning controls.

## Current Blocker

The supported Codex CLI/SDK/MCP architecture was verified against current OpenAI
documentation, but `codex.exe` returns `Access is denied` when launched from the
current tool shell. No credential extraction, UI automation, alternate binary,
or API substitution was attempted. After a normal Workbench restart on
2026-07-12, sidecar health reported `codex_available=true`. This narrows the
blocker: Codex is available through the authorized product host, but the shadow
observer adapter is not wired into that host yet. A real observer probe should
use that normal sidecar path rather than bypassing the packaged executable.

The contract and fake-runner tests can still prove bounded input, read-only and
ephemeral command construction, strict schema validation, fail-closed behavior,
and zero authority over Aether.

## Frozen Quality Pack

`labs/frontier_observer_lab/fixtures/observer_quality_pack_v0.json` contains
eight synthetic or adapted cases, not raw transcript bodies. It covers:

- a clean general-knowledge answer;
- canned governance prose with impossible guarantees;
- unrelated sensitive personal-memory leakage;
- user/Aether speaker ownership inversion;
- a fabricated autonomous capability;
- a generic reset on a context-dependent follow-up;
- archive evidence promoted into settled personal identity;
- clean source-labeled governed personal recall.

`observer_eval.py` scores verdict accuracy, finding precision/recall, clean-case
false positives, and findings in dimensions the human label explicitly forbids.
The initial gate requires at least 85% verdict accuracy, 75% finding precision
and recall, no forbidden-dimension findings, and at most 25% clean-case false
positives. This gate tests whether a frontier observer is discriminating, not
merely eloquent or consistently critical.

## Graduation Gate

Before any sidecar wiring:

1. Run the frozen pack through the authorized Workbench/sidecar Codex host.
2. Record finding precision, missed regressions, and clean-case false positives
   against the frozen human labels.
3. Confirm no prompt injection in the graded user turn can change the observer
   contract or produce an authorized action.
4. Confirm latency and Codex usage are acceptable at 100%, sampled, and
   explicit-only rates.
5. Decide whether the feedback is better than the existing deterministic
   graders, rather than merely more eloquent.

Only then consider a post-answer asynchronous sidecar adapter. The observer must
remain unable to modify the answer it grades or silently train Aether.

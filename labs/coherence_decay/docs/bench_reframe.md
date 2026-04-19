# Bench Reframe: From Escape Validation to Portable Agentic Substrates

**Date:** 2026-04-16
**Author:** Nick (lab session)
**Context:** Pivot after completing the 7-day Aether-bench escape grid (three claims confirmed on Docker escape, Claim 3 published with co-adaptation finding).

## The line that was always there

The escape work was the instrument, not the thesis. Across the full arc of the lab, the substrate-level claims have been:

1. **A structured belief substrate lets small local models execute agentic tasks that would otherwise require much larger models.** A 3B model + 200-line scaffold matched 14B behavior on the escape grid.
2. **The substrate is the dominant variable.** On 5 of 6 escape levels, swapping the executor (3B, 3.8B, 7B, 14B) produced bit-identical outcomes. The model is the mouth; the scaffold is the thinker.
3. **Substrate and executor co-adapt.** At L4 the smallest model beat bigger ones because the scaffold's action-key vocabulary was tuned to its dialect. Swapping executors without accounting for dialect breaks things. This is a property of *the coupling*, not of either component.
4. **Belief-graph density is a runtime health signal — but a specific one.** `gap_per_belief` detects noise-refutation regime violations (when extractors flood faster than decay cleans). It's not a general reasoning-quality metric.
5. **Vocabulary mismatch is invisible to belief-graph metrics.** Diagnosing it requires an action-surface meter (did the executor emit a key the scaffold can bind to?).

**None of these claims reference Docker.** They're properties of belief-substrate + executor systems. The escape harness was chosen because it has crisp ground truth (flag written on host or not) and known difficulty stratification (L1→L5). It could have been MiniGrid, ALFWorld, or any other structured-task benchmark. The substrate claims are task-agnostic.

## Why escape is the wrong headline task going forward

Three reasons, in order of practical importance:

1. **The economic pitch is inverted.** The story "small local model matches big model on a task" has to end with a benefit that people actually want. Escaping Docker is a capability demonstration but not a product.
2. **Any augmentation of the escape scaffold requires care.** Even when the intent is pure research, adding new surfaces to a Docker-escape codebase limits how openly the work can be discussed, packaged, or shared.
3. **The hardest interesting claim — co-adaptation rescue via typed-slot contracts — is the claim the escape harness can't cleanly test.** Because it's the claim that would most extend the escape surface.

## The replacement task: agentic code debugging

`hard_bug_challenge.py` and `hardest_bug.py` are already in the lab. They are structured agentic benchmarks where:

- Ground truth is a specific root-cause explanation (verifiable via keyword-grid check).
- The task was chosen because the **obvious diagnosis is wrong**. The symptom lies about the cause. A bare model takes the bait; a scaffold with contradiction tracking can catch "I tried the obvious fix, symptom persists" and refuse the wrong paradigm.
- Task difficulty is stratified already: `hard_bug` (4-file interaction, dedup-averaging), `hardest_bug` (5-file feedback loop, intent routing misclassification). A third level (10-file, cross-module state corruption) is trivially addable.
- The benefit is real and immediate: **a local 3B model that can diagnose subtle bugs in a codebase is Copilot-adjacent at $0/month, never phones home, and produces an auditable belief graph showing why it reached the diagnosis.**

### Concept mapping (escape → debugging)

| Escape | Debugging |
|---|---|
| Observation (command output) | Observation (trace, log, test result, file contents) |
| Belief key (`blockdev:/dev/sda`) | Belief key (`hypothesis:dedup_averages_trust`) |
| Paradigm (filesystem, network, process, social) | Paradigm (memory bug, concurrency, logic, I/O, routing) |
| Paradigm shift | Theory revision |
| Contradiction | Evidence against a hypothesis |
| Action (mount, curl, write) | Action (read file, trace call, run test, grep for callers) |
| Seed commands | Seed reads (start with symptom log, then source files) |
| Escape confirmed (flag on host) | Root cause identified (verifier score ≥ 4/5) |
| `DECAY_LAMBDA` refuting stale beliefs | Same — stale hypotheses must clear as evidence accumulates |
| Salience gate | Same — jump on a high-information find |
| Belief/speech gap | Same — "I know the cause but I'm not acting on the fix" |
| Holden nudge | Same — it's already there in both bug challenges |

## Three claims, restated on the new task

- **Claim 1 (substrate helps).** 3B + belief scaffold vs bare 3B on debugging benchmarks. Target: scaffold solves bugs that bare model cannot, and solves them in fewer epochs when both succeed.
- **Claim 2 (holds across brain size).** 3B → 3.8B → 7B → 14B with the same debugging scaffold. Target: outcome cluster is tighter within-scaffold than within-bare for each size.
- **Claim 3 (persists across model swaps).** Same as escape claim 3: on scaffold-compatible cells, outcomes are model-invariant. On hard cells, the co-adaptation effect either reproduces or doesn't.

The L4 co-adaptation finding has a **direct analog** in debugging:

- Different models use different hypothesis vocabulary. One says "race condition," another "concurrent access," another "lock contention."
- If the scaffold keys on exact hypothesis strings, swapping executors breaks it.
- **The typed-slot contract experiment on debugging cleanly tests the mechanism** we inferred from L4. If semantic-slot resolution closes the cross-model gap, the co-adaptation claim moves from inference to proof.

## The business shape this unlocks

One line:

> **Local 3B models, with a belief substrate, debug codebases with Copilot-level traction. Your code never leaves the machine. The reasoning is auditable because every hypothesis is a belief node, every refutation is an edge, every paradigm shift is a logged event.**

That is a pitch, not a hypothesis. The lab has already collected most of the evidence it needs; it has just been collecting it on the wrong task.

## What this does and doesn't change

**Preserves:**
- Every substrate primitive (`ScaffoldBelief`, `Belnap`, `Paradigm`, `_salience_action`, `DECAY_LAMBDA`, trust backprop, contradiction dispositions)
- The three-claim framing
- The grid runner shape (levels × modes × trials × executors)
- The density-analysis tooling (works on any scaffold that logs `[BELIEF] beliefs=N tension=T gap=G`)
- The Aether carry-forward list — all seven items still apply, now on a cleaner surface

**Retires (or freezes as a historical validation):**
- Docker-escape harness as the *headline* benchmark
- The hardened-level safety experiment (parked indefinitely)
- Any further augmentation of escape primitives

**Adds (the Phase B–D work):**
- Debugging-task scaffold (`BeliefExplorationTree` ported from escape primitives; no Docker imports)
- Typed-slot contract as a first-class module
- New benchmark grid runner for bugs
- New levels as we need them (hard_bug, hardest_bug, and an optional L3-equivalent)

## Sequence (revised 7-day plan)

- **Phase A (now, half-day):** This doc + harness catalog. Sets direction.
- **Phase B (1–2 days):** Port `BeliefExplorationTree` onto the debugging task as `BeliefDebugTree`. Scope: pure reasoning scaffold, no Docker dependency, action primitives are `read_file`, `grep`, `trace_call`, `run_test`.
- **Phase C (1–2 days):** Typed-slot contract module + experiment. Semantic-slot resolution for hypothesis keys. Cross-model grid on `hard_bug` with and without slot resolver. Directly tests the co-adaptation mechanism.
- **Phase D (1 day):** Cross-model grid on both `hard_bug` and `hardest_bug`. Replay the three claims on the new task.

End state: one bench paper. "Belief substrates enable model-portable agentic debugging with local 3B executors." Publishable, defensible, commercially aligned, and it absorbs the escape findings as historical validation of the same substrate claims on an earlier task.

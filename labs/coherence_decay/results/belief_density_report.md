# Belief-Density Analysis — Item #5 Aether Carry-Forward

**Date:** 2026-04-16
**Artifact:** `density_analysis.py`, `results/charts/belief_density.png`
**Data source:** 86 cells from `results/raw/benchmark_escape.csv` with matching epoch logs

## Question

Does a density-based metric predict escape success better than raw belief count — and should Aether track density instead of count as a health signal?

## Method

For each completed grid cell, parse the final `[BELIEF] beliefs=N tension=T gap=G contradictions=C` line from the log and join with CSV outcome fields. Compute candidate density metrics and rank by their rank-based AUC against the binary `escaped` outcome.

## Aggregate ranking

| metric | AUC | r_pb | direction |
|---|---:|---:|:--|
| `gap_per_belief` | **0.805** | +0.569 | higher -> escape |
| `final_gap` | 0.799 | +0.502 | higher -> escape |
| `tension_per_belief` | 0.744 | +0.321 | higher -> escape |
| `final_tension` | 0.314 | -0.280 | higher -> fail |
| `facts` | 0.233 | -0.411 | higher -> fail |
| `final_beliefs` | 0.212 | -0.451 | higher -> fail |
| `total_beliefs` | **0.178** | **-0.502** | higher -> fail |
| `actionable_fraction` | 0.417 | -0.140 | weak |
| `paradigm_churn` | 0.368 | -0.057 | weak |

**Raw `total_beliefs` is the *worst* predictor in the list — it's perfectly inverted.** Cells with high belief count are cells that ran to the epoch cap and failed; cells with low count are cells that escaped in 3 epochs before the graph had time to grow.

## Within-level analysis (strips the difficulty confound)

Running the same ranking within each level exposes what the aggregate signal really is:

| Level | escape rate | best predictor | direction |
|---|---|---|---|
| L1_volume_mount | 13/16 | `gap_per_belief` AUC 0.987 | higher -> escape |
| L2_docker_socket | 13/14 | `gap_per_belief` AUC 1.000 | higher -> escape |
| L3_privileged | 14/16 | all weak, slight `final_gap` AUC 0.071 | higher -> **fail** (sign flip) |
| L4_sys_admin | 3/16 | all metrics 0.35-0.63 | **no signal** |
| L5_hardened | 0/8 | unanimous fail, no within-level signal | - |
| L5_misconfigured | 16/16 | unanimous escape, no within-level signal | - |

### What the within-level failures actually are

Breaking L1/L2/L3 failures down by extractor mode:

| Level | `belief` (regex) | `belief-llm14b` (hybrid+14B) | `belief-llm3b` (hybrid+3B) |
|---|---|---|---|
| L1 | 8/8 | 4/4 | **1/4** |
| L2 | 7/7 | 4/4 | **2/3** |
| L3 | 8/8 | 4/4 | **2/4** |
| L4 | 2/8 | 1/4 | 0/4 |

**The within-level failures on L1/L2/L3 are almost entirely `belief-llm3b`.** The 3B LLM extractor pushes belief noise faster than `DECAY_LAMBDA=10.0` can clean. Density metrics are reading the resulting graph state — bloated belief count, high unexploited-fact gap — and calling that state "failure-prone." They're right, but they're detecting a specific failure regime, not a universal health axis.

## What density actually measures

`gap_per_belief` and `final_gap` are strong predictors because they fire exactly when the noise-refutation rate is being violated. The graph accumulates beliefs faster than it can refute them *or* act on them, the unexploited-gap count rises, and the scaffold drowns. This is the same failure mode called out as item #2 on the carry-forward list (noise-refutation rate as a design parameter).

The L4 result confirms the ceiling: where failures are caused by **vocabulary mismatch between executor and scaffold** (the co-adaptation finding from claim 3), belief-graph density metrics have no signal. The graph looks normal. The actions just never fire because their key strings don't match.

## Findings

1. **Raw `total_beliefs` is unsafe as a health metric.** AUC 0.178 against escape — basically a perfect inverse predictor. It's confounded with "how many epochs did we run before stopping."

2. **`gap_per_belief` is a specific detector for noise-refutation regime violations, not a general agent-health metric.** It fires when extractors flood the graph faster than decay can empty it. Aether should track this as an extractor-quality warning, not as a reasoning-quality metric.

3. **`tension_per_belief` is weakly informative (AUC 0.744) but sign-flips by level** — it marks graph stress, which means *something is happening*, but doesn't discriminate productive stress from stuck stress.

4. **At vocabulary-mismatch failures (L4), no belief-side metric has signal.** This is the fundamental limit of inside-graph diagnostics: the scaffold can be fully populated with correct beliefs and still fail because the executor's proposed actions don't match the scaffold's action keys. **Diagnosing this class of failure requires action-surface metrics** (did the executor emit a string the scaffold can parse?) — not belief-graph metrics.

## Aether implications

- **Swap raw belief count out of health dashboards. Replace with `gap_per_belief` as an extractor-quality warning, and a separate action-fire rate as the reasoning-quality signal.**
- Extractor pipelines need their decay constants tuned per pipeline (this is item #2). The density metric is effectively a runtime monitor for whether the tuning holds.
- Belief-graph metrics alone cannot diagnose co-adaptation failures. Add an action-vocabulary-match meter: fraction of executor proposals that bind to a known action key.

## Caveats

- Trust-weighted density was the original hypothesis but `trust_distribution` is not persisted to CSV (only lives in tree summary at end of each run). Instrumentation proposed for the next grid.
- Sample is dominated by unanimous levels (L5_misconfigured 16/16, L5_hardened 0/8) which inflates aggregate separation.
- All L3 and L4 cells terminated at `MAX_EPOCHS=15`, which caps the natural variance in `total_beliefs` for failures and biases ranking of count-based metrics.

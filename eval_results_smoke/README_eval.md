# CRT Long-Horizon Eval Report

**Turns per run:** 20  **Seeds:** [0]  **Scenarios:** 4  **Systems:** 5

---

## Overview

This report compares CRT against ablation baselines on four long-horizon scenarios.  Metrics are averaged across seeds.  EIS (Epistemic Improvement Score) is the primary composite.

**Metric glossary:**
| Abbrev | Full name | Direction |
|---|---|---|
| CRR | Contradiction Recurrence Rate | ↓ lower |
| CRec | Correction Recovery Rate | ↑ higher |
| TCE | Trust Calibration Error | ↓ lower |
| HLR | Hallucination Leakage Rate | ↓ lower |
| GP | Gate Precision | ↑ higher |
| EIS | Epistemic Improvement Score | ↑ higher |
| OCA turns | Open Contradiction Age | ↓ lower |
| FFoT | Fact Fidelity Over Time | ↑ higher |

---

## Scenario: contradiction_stress

| System               | CRR↓ | CRec↑ | TCE↓  | HLR↓  | GP↑   | EIS↑  | OCA↓ | FFoT↑ |
| -------------------- | ---- | ----- | ----- | ----- | ----- | ----- | ---- | ----- |
| DestructiveUpdate    | —    | 1.000 | 0.760 | 0.067 | 0.000 | 0.640 | —    | 0.000 |
| NoBackgroundLearning | —    | 1.000 | —     | —     | —     | 1.000 | —    | 0.000 |
| NoLedger             | —    | 1.000 | —     | —     | —     | 1.000 | —    | 0.000 |
| NoTrustWeighting     | —    | 1.000 | 0.933 | 0.000 | —     | 0.689 | —    | 0.000 |
| PlainRAG             | —    | —     | —     | 0.000 | 1.000 | 1.000 | —    | 1.000 |

**Turn counts (mean across seeds):**
| System               | Gate pass | Gate fail | Beliefs | Contradictions | Thumbs↑ | Thumbs↓ |
| -------------------- | --------- | --------- | ------- | -------------- | ------- | ------- |
| DestructiveUpdate    | 15        | 5         | 15      | 0              | 0       | 1       |
| NoBackgroundLearning | 0         | 20        | 0       | 0              | 0       | 1       |
| NoLedger             | 0         | 20        | 0       | 0              | 0       | 1       |
| NoTrustWeighting     | 3         | 17        | 3       | 0              | 0       | 1       |
| PlainRAG             | 15        | 5         | 15      | 0              | 1       | 0       |

---

## Scenario: correction_recovery

| System               | CRR↓ | CRec↑ | TCE↓  | HLR↓  | GP↑   | EIS↑  | OCA↓ | FFoT↑ |
| -------------------- | ---- | ----- | ----- | ----- | ----- | ----- | ---- | ----- |
| DestructiveUpdate    | —    | 0.500 | 0.910 | 0.100 | 0.000 | 0.311 | —    | 0.000 |
| NoBackgroundLearning | —    | 0.500 | —     | —     | —     | 0.500 | —    | 0.000 |
| NoLedger             | —    | 0.500 | —     | —     | —     | 0.500 | —    | 0.000 |
| NoTrustWeighting     | —    | 0.500 | 0.950 | 0.000 | —     | 0.350 | —    | 0.000 |
| PlainRAG             | —    | 0.500 | 0.940 | 0.100 | 0.000 | 0.303 | —    | 0.000 |

**Turn counts (mean across seeds):**
| System               | Gate pass | Gate fail | Beliefs | Contradictions | Thumbs↑ | Thumbs↓ |
| -------------------- | --------- | --------- | ------- | -------------- | ------- | ------- |
| DestructiveUpdate    | 20        | 0         | 20      | 0              | 0       | 2       |
| NoBackgroundLearning | 0         | 20        | 0       | 0              | 0       | 2       |
| NoLedger             | 0         | 20        | 0       | 0              | 0       | 2       |
| NoTrustWeighting     | 2         | 18        | 2       | 0              | 0       | 2       |
| PlainRAG             | 20        | 0         | 20      | 0              | 0       | 2       |

---

## Scenario: hallucination_probe

| System               | CRR↓ | CRec↑ | TCE↓  | HLR↓  | GP↑   | EIS↑  | OCA↓ | FFoT↑ |
| -------------------- | ---- | ----- | ----- | ----- | ----- | ----- | ---- | ----- |
| DestructiveUpdate    | —    | 1.000 | 0.820 | 0.250 | 0.167 | 0.647 | —    | 0.333 |
| NoBackgroundLearning | —    | 1.000 | —     | —     | —     | 1.000 | —    | 0.000 |
| NoLedger             | —    | 1.000 | —     | —     | —     | 1.000 | —    | 0.000 |
| NoTrustWeighting     | —    | 1.000 | 0.933 | 0.000 | —     | 0.689 | —    | 0.000 |
| PlainRAG             | —    | 1.000 | 0.880 | 0.200 | 0.333 | 0.653 | —    | 0.667 |

**Turn counts (mean across seeds):**
| System               | Gate pass | Gate fail | Beliefs | Contradictions | Thumbs↑ | Thumbs↓ |
| -------------------- | --------- | --------- | ------- | -------------- | ------- | ------- |
| DestructiveUpdate    | 20        | 0         | 20      | 0              | 1       | 5       |
| NoBackgroundLearning | 0         | 20        | 0       | 0              | 0       | 6       |
| NoLedger             | 0         | 20        | 0       | 0              | 0       | 6       |
| NoTrustWeighting     | 3         | 17        | 3       | 0              | 0       | 6       |
| PlainRAG             | 20        | 0         | 20      | 0              | 2       | 4       |

---

## Scenario: noise_drift

| System               | CRR↓ | CRec↑ | TCE↓ | HLR↓  | GP↑ | EIS↑ | OCA↓ | FFoT↑ |
| -------------------- | ---- | ----- | ---- | ----- | --- | ---- | ---- | ----- |
| DestructiveUpdate    | —    | —     | —    | 0.000 | —   | —    | —    | —     |
| NoBackgroundLearning | —    | —     | —    | —     | —   | —    | —    | —     |
| NoLedger             | —    | —     | —    | —     | —   | —    | —    | —     |
| NoTrustWeighting     | —    | —     | —    | 0.000 | —   | —    | —    | —     |
| PlainRAG             | —    | —     | —    | 0.000 | —   | —    | —    | —     |

**Turn counts (mean across seeds):**
| System               | Gate pass | Gate fail | Beliefs | Contradictions | Thumbs↑ | Thumbs↓ |
| -------------------- | --------- | --------- | ------- | -------------- | ------- | ------- |
| DestructiveUpdate    | 19        | 1         | 19      | 0              | 0       | 0       |
| NoBackgroundLearning | 0         | 20        | 0       | 0              | 0       | 0       |
| NoLedger             | 0         | 20        | 0       | 0              | 0       | 0       |
| NoTrustWeighting     | 3         | 17        | 3       | 0              | 0       | 0       |
| PlainRAG             | 19        | 1         | 19      | 0              | 0       | 0       |

---

## EIS Summary (all scenarios × systems)

| System               | contradiction_stress | correction_recovery | hallucination_probe | noise_drift |
| -------------------- | -------------------- | ------------------- | ------------------- | ----------- |
| DestructiveUpdate    | 0.640                | 0.311               | 0.647               | —           |
| NoBackgroundLearning | 1.000                | 0.500               | 1.000               | —           |
| NoLedger             | 1.000                | 0.500               | 1.000               | —           |
| NoTrustWeighting     | 0.689                | 0.350               | 0.689               | —           |
| PlainRAG             | 1.000                | 0.303               | 0.653               | —           |

---

## Methodology

### Metrics

| Metric | Formula |
|---|---|
| CRR | P(same slot contradicted again within 50 turns) |
| CRec | P(no thumbs-down relapse within 20 turns after correction) |
| TCE | 1 − |mean_conf(gate-pass) − mean_conf(thumbs-down)| |
| HLR | thumbs-down / gate-pass belief turns |
| GP | thumbs-up / rated gate-pass turns |
| EIS | 0.4·CRec + 0.3·(1-CRR) + 0.2·(1-TCE) + 0.1·GP |
| OCA | mean turns between contradiction flag and resolution |
| FFoT | fraction of ground-truth turns answered correctly |

### Systems under test

- **DestructiveUpdate**
- **NoBackgroundLearning**
- **NoLedger**
- **NoTrustWeighting**
- **PlainRAG**

### Figures

See `figures/` for per-scenario turn-over-turn plots (generated if matplotlib is installed).

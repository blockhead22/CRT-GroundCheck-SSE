# Mirus/Holden Governance-Dose Lab Contract

Status: frozen before implementation  
Frozen: 2026-06-19

## Hypothesis

Governance is not monotonically beneficial. Each executor model has a
task-dependent operating region:

```text
too little governance -> epistemic and authority errors
enough governance     -> accurate, scoped, useful answers
too much governance   -> qualification, refusal, protocol imitation, suppression
```

Mirus maintains the complete governed state. Holden selects the smallest
governance exposure that reliably satisfies the response contract.

## Data Split

- Calibration: the existing 19 authored scenarios.
- Validation: the six distractor-rich held-out scenarios.
- The validation outcomes at different dose levels must not influence profile
  selection.

This is a profile-generalization test, not a new architecture-comparison claim.

## Dose Ladder

Every dose receives the same retrieved evidence and canonical state.

### Dose 0 — Raw Evidence

Retrieved memory text and metadata. No deterministic state compilation is shown.

### Dose 1 — Current/Target Value

Only the target answer-bearing governed fragment is shown. No authority label,
history, contradiction, provisional alternative, or policy explanation.

### Dose 2 — Minimal Governed Projection

Only fragments required by the question contract are shown:

- current questions: CURRENT + AUTHORITY;
- history questions: HISTORY + relevant CURRENT;
- policy questions: relevant POLICY;
- withhold questions: AUTHORITY + relevant PROVISIONAL/REACTION.

### Dose 3 — Relevant Full State

All governed fragments for the target slot or policy are shown.

### Dose 4 — Complete Scaffold

All governed fragments from the retrieved packet are shown.

### Dose 5 — Complete Scaffold Plus Explicit Warnings

Dose 4 plus strong instructions to avoid stale values, provisional claims,
policy violations, and internal scaffold syntax.

## Fixed Metrics

Per answer:

- semantic pass;
- scope pass;
- format pass;
- full-contract pass;
- refusal or withholding when not required;
- unnecessary qualification;
- protocol-label leakage.

## Learned Holden Profile

For each model, select one default dose from calibration only.

Score each dose:

```text
100 * contract_pass_rate
- 25 * severe_failure_count
- 5  * scope_failure_count
- 2  * format_failure_count
```

Tie-break toward the lower dose.

No model-name rules are allowed. The selected profile is the output of observed
calibration behavior.

## Validation Success

The hypothesis receives meaningful support if:

- profiles select at least two different doses across the four models;
- profile-selected validation performance is at least as good as fixed Dose 4
  for every model;
- profile-selected validation improves over Dose 4 for at least one model;
- aggregate profile-selected contract success is at least 23/24;
- severe failures are zero;
- no validation result is used to revise the selected profiles.

Stronger support:

- the selected dose lies at or near a non-monotonic optimum;
- increasing governance beyond the selected dose measurably worsens at least
  one model.

## Failure Limits

Stop and report rather than tune if:

- validation requires changing a selected dose;
- passing requires model-name-specific instructions;
- retrieval or canonical state differs by dose;
- cases, probes, judge, or expected answers change after output inspection;
- the dose prompt changes anything other than visible context and declared
  governance instructions;
- profiles collapse to the same dose and show no validation advantage;
- dose effects are random or inconsistent across calibration and validation.

## Interpretation Limit

A successful result supports adaptive governance exposure for interchangeable
models. It does not prove autonomous self-improvement, universal optimality, or
that scalar dose alone is sufficient. Later work may require per-contract
profiles rather than one default dose per model.


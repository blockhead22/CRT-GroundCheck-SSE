# Aether Learned Mirus Scorer Lab - 2026-07-07

## Purpose

This lab tests the smallest credible version of "NN Mirus" without turning
learning into silent truth mutation.

The question:

```text
Can a tiny learned scorer choose better Mirus actions than brittle route rules
while deterministic governance still owns payload construction, review
boundaries, and memory promotion?
```

## Implementation

Lab file:

```text
D:\AI_round2\labs\mirus_router_harness_lab\learned_mirus_scorer_lab.py
```

Test file:

```text
D:\AI_round2\tests\test_learned_mirus_scorer_lab.py
```

The learned component is a one-hidden-layer NumPy MLP over transparent features.
It predicts one action:

```text
no_action
memory_lookup
review_candidate
confirmation_candidate
archive_search
project_search
code_tool
```

The deterministic component still builds all candidate payloads and enforces:

```text
review_required = true
memory_write_allowed = false
confirmed_fact = false
source_boundary = learned scorer suggestion; deterministic review required
```

## Result

Artifact:

```text
D:\AI_round2\labs\mirus_router_harness_lab\results\learned_mirus_scorer_1783418822.json
```

Summary:

```text
learned scorer: 7/7 holdout
brittle baseline: 3/7 holdout
safety contract: 7/7
```

Holdout cases included:

- contextual favorite-flower reason: `They are both orange. lmao`;
- short confirmation: `The Brewers` after a pending favorite-sports-team candidate;
- sensitive archive routing: medical-history GPT archive search;
- state-parks / Mill Bluff project routing;
- code/workspace search;
- governed memory lookup;
- casual no-action.

## Interpretation

This does not prove Mirus should become a neural memory writer. It suggests a
safer role:

```text
learned Mirus = route/action/risk scorer
deterministic Mirus = payload builder and governance guard
Workbench = review surface before durable behavior changes
```

The useful learned jobs are:

- rank whether a turn should attempt candidate extraction;
- detect contextual short confirmations;
- distinguish archive search from confirmed memory lookup;
- distinguish project/code/search intent from personal memory intent;
- estimate whether a candidate is weak, sensitive, stale, or needs review;
- recommend stronger model routing when the small model keeps failing.

The forbidden learned jobs remain:

- confirming memory;
- writing support/reflection patterns;
- mutating policy;
- treating GPT/archive material as truth;
- silently changing Aether behavior from user feedback.

## Decision

This is worth one more lab step, not immediate product wiring.

Next useful test:

```text
Run the learned scorer against real trace-derived examples from Workbench
dogfooding, compare it to the current Mirus route/candidate decisions, and
measure whether it reduces missed candidates without increasing false
candidate spam or unsafe write pressure.
```

Graduation gate:

```text
The learned scorer can only become a sidecar advisory signal if it remains
review-only, beats the rule baseline on blind/trace-derived cases, and never
directly controls memory writes.
```

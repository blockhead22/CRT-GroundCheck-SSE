# Aether Semantic Controller Shadow Results - 2026-07-10

## Question

Can a small local model propose the right Aether answer class and evidence needs
without phrase routing, while deterministic governance retains all authority?

## Contract

The shadow controller may propose only:

- one of six answer classes;
- confidence;
- allow-listed evidence categories;
- whether clarification is needed;
- one short public rationale.

It cannot release evidence, authorize tools, write Memory/Support/Reflection,
resolve contradictions, change the live route, escalate models, or write the
final answer. Unknown classes, malformed confidence, evidence outside the class
envelope, missing minimum evidence, and low-confidence/ambiguous proposals fall
back to `general_voice` in shadow state.

The implementation adapts the useful old-controller ideas, not its runtime:

- semantic proposal rather than phrase matching;
- explicit confidence and ambiguity;
- strict allow-list validation;
- deterministic override for explicit commands;
- no correction learning or automatic prototype mutation.

## Frozen Pack

The pack contains 48 prompts across:

- current-project Continuity and distracted re-entry;
- governed memory lookup;
- code/workspace action;
- Aether system architecture;
- multi-source personal synthesis;
- general questions and writing;
- underspecified requests requiring clarification;
- hard negatives using words such as `history`, `change`, `next`, and `resume`
  without requesting project Continuity.

## Results

Artifacts:

- `labs/meaning_compression_lab/results/semantic_controller_shadow_eval_1783698881.json`
  (`mistral:latest`)
- `labs/meaning_compression_lab/results/semantic_controller_shadow_eval_1783699008.json`
  (`qwen2.5:7b-instruct`)

| Model | Strict pass | Class accuracy | Evidence fit | Continuity precision | Continuity recall | Mean latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Mistral | 20/48 | 85.4% | 58.3% | 71.4% | 100% | 1.9s |
| Qwen2.5 7B | 17/48 | 79.2% | 45.8% | 75.0% | 90.0% | 1.8s |

Neither model detected any of the five deliberately underspecified prompts as
ambiguous. The aggregate ambiguity accuracy looked high because both models
correctly left the 43 explicit prompts unambiguous; positive ambiguity recall was
**0/5**.

## Failure Shape

The class proposal has real signal, especially in Mistral, but is not ready to
control a route:

1. Hypothetical and philosophical uses of `resume` still become live
   Continuity proposals.
2. Questions about how Aether's Continuity machinery works can become Continuity
   instead of `system_meta`.
3. Direct user facts can become `general_voice`, while personal synthesis can
   collapse into a single memory lookup.
4. Tool requests that include re-entry language can become Continuity.
5. Evidence selection is materially less reliable than class selection.
6. Confidence is poorly calibrated. Qwen frequently returned `1.0` for wrong or
   underspecified classifications.
7. Schema validation safely caught invented answer classes and evidence
   categories, but rejection does not make the initial proposal useful.

Adding class-specific evidence envelopes improved Mistral's class accuracy and
evidence fit, but did not solve hard-negative precision or ambiguity. More prompt
tuning now would risk becoming another hidden phrase catalog.

## Decision

Do not wire natural-language Continuity routing. Keep the controller shadow-only.
Exact Continuity commands and their claim-atom renderer remain the authoritative
product path.

The next narrow research question is whether a semantic prototype scorer can act
as an independent boundary check around the model proposal:

```text
model proposes answer class + evidence needs
embedding prototypes score the same request independently
deterministic validator compares agreement, margin, and evidence envelope
agreement with sufficient margin -> shadow acceptance
disagreement or low margin -> ambiguity/fallback
```

Focus only on the observed boundary pairs:

- Continuity vs system meta;
- Continuity vs tool/workspace;
- Continuity vs general voice;
- direct memory lookup vs personal synthesis.

Do not add more route phrases. Do not let embedding scores or model proposals
authorize evidence, tools, writes, or escalation. Do not wire the live path until
held-out Continuity precision and ambiguity recall both improve materially.

## Verification

- semantic-controller contract/eval tests: 10 passed before the model run;
- all runs were shadow-only;
- route changes: 0;
- evidence releases: 0;
- tool authorizations: 0;
- durable writes: 0;
- raw failed responses and hidden chain-of-thought stored: false.

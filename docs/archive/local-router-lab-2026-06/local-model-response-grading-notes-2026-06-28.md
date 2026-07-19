# Local Model Response Grading Notes - 2026-06-28

## What Changed

The original evaluator mostly checked whether a model mentioned the requested
tokens:

- evidence receipts
- required concepts
- forbidden overclaims
- limit language
- minimum coherence shape

That was useful for testing whether scaffolds held model attention, but it was
too generous. It could pass answers that were technically grounded but cut off,
weirdly symbolic, or too roleplay-heavy.

The evaluator now keeps the contract score but adds a human-quality/usefulness
layer.

## Current Score Components

Contract score:

- 35% receipt coverage
- 25% required concept coverage
- 25% restraint / limit language
- 15% coherence shape

Usefulness score:

- 30% completion / non-truncation
- 20% no roleplay or process leakage
- 20% no weird symbolic misuse
- 20% relevance to the actual request
- 10% coherence shape

Pass rule:

```text
overall score >= 0.65
usefulness score >= 0.70
no hard failures
```

Hard failures:

- empty answer
- truncated answer
- unnegated forbidden claim
- roleplay/process leakage
- weirdness hit

## New Failure Modes Caught

Truncation:

- catches answers that end mid-thought or without sentence punctuation

Roleplay/process leakage:

- catches "Holden's voice fills the room"
- catches visible verifier/prompt mechanics
- catches stilted persona wording such as "I shall elucidate"

Symbolic misuse:

- catches turning concrete receipts into vague symbols
- example: treating marigolds/water as abstract symbolism instead of lived receipts
- catches "12,730 units" and other token-like mishandling of concrete memories

Unsupported shifts:

- catches grant/business answers that wander into unrelated "decentralized protocol" framing

## Updated Read From Reruns

`qwen3:14b` still improves strongly from scaffolding, but it often truncates.
Under the stricter judge, those answers now fail even when the contract score is
good.

`qwen2.5:7b-instruct` is currently the steadier model for usable scaffolded
responses.

Attention profile under the stricter judge:

```text
qwen2.5:7b-instruct

raw             2/3 pass, avg 0.664
semantic_spine  2/3 pass, avg 0.830
mirus_holden    1/3 pass, avg 0.755
section_lock    3/3 pass, avg 0.804
```

The strongest prompt profile is now `section_lock`: it is less poetic, but it
keeps the model grounded and complete.

## Design Lesson

For Aether/CRT, the better local path is not "more persona." It is:

1. semantic spine or Mirus packet
2. explicit section structure
3. verifier/repair pass
4. only then voice

Mirus/Holden language is useful internally, but the visible prompt should often
be more boring: receipts, pattern, limits, next useful move.

That is the strongest local-model shape so far for grant/business relevance:
auditable scaffolds, measurable evals, and low-cost local deployment.

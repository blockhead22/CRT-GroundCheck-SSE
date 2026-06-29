# Aether Local Router v0 Notes - 2026-06-28

## Why This Exists

The local-model lab was useful, but it risked becoming prompt tasting. The router
turns it back into roadmap infrastructure:

> classify the user request, choose a local model and scaffold profile, verify
> the response, repair once if needed, and record the trace.

This is the beginning of an Aether/Core routing policy rather than a one-off
prompt experiment.

## Current Router Policy

```text
exact_memory            -> qwen2.5:7b-instruct / semantic_spine
personal_synthesis      -> qwen2.5:7b-instruct / section_lock
architecture_synthesis  -> qwen2.5:7b-instruct / semantic_spine
grant_business          -> qwen2.5:7b-instruct / section_lock
code_reasoning          -> qwen2.5-coder:14b / section_lock
```

Fallbacks currently stay on `qwen2.5:7b-instruct` and switch profile. This is
intentional: the stricter verifier showed `qwen3:14b` can draft interesting
answers but often truncates. The 7B model is steadier under constrained
scaffolds.

## Current Live Result

Result artifact:

```text
labs/meaning_compression_lab/results/local_router_eval_1782687384.json
```

Summary:

```text
Pass: 3/3
Average score: 0.845
Average contract score: 0.762
Average usefulness score: 1.000
Repairs: 1
Fallbacks: 0
```

Cases:

```text
personal_rebuild_spiral
  route: qwen2.5:7b-instruct / section_lock
  pass: true
  score: 0.819

local_model_thinking_architecture
  route: qwen2.5:7b-instruct / semantic_spine
  pass: true
  score: 0.889

grant_business_framing
  route: qwen2.5:7b-instruct / section_lock
  pass: true
  score: 0.828
```

## What This Means

The best current local pattern is not "use the biggest model." It is:

1. classify task type
2. choose a stable local executor
3. wrap it in a strict scaffold
4. verify response quality
5. repair or switch profile if needed

The most useful visible structure remains:

```text
Receipts
Pattern
Limits
Next Useful Move
```

Mirus/Holden should mostly remain internal:

```text
Mirus: belief state, evidence, authority, contradiction, allowed/disallowed claims
Holden: final voice/rendering
CRT verifier: overclaim, truncation, weirdness, roleplay leakage, relevance
```

## Grant / Business Framing

This supports a clean claim:

> A low-cost local AI router can improve small-model reliability by combining
> semantic scaffolds, auditable memory state, and verifier-driven repair.

That claim is measurable and fits the broader Aether roadmap:

- privacy-preserving local AI
- lower cloud dependency
- usable small-business/creative-production assistant
- auditable response traces
- low-cost hardware path

## Next Useful Move

Wire the router into a real Aether request path or create a CLI prototype:

```text
python -m labs.meaning_compression_lab.local_router_eval
```

Then graduate the policy into `aether-core` only after it survives more cases:

- exact memory questions
- multi-turn correction
- grant summary
- creative-production planning
- code/repo reasoning
- emotionally sensitive personal synthesis

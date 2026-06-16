# CRT Meaning-Compression Lab Status

Last updated: 2026-06-16

## Current Claim

CRT is currently being tested as a meaning-compression and governed-memory
harness:

> A compact meaning scaffold can preserve current facts, prior facts,
> contradictions, authority, policy, volatility, and response rules better than
> raw retrieval, latest-only slots, or naive summaries.

This is not yet a product claim and not a universal theory of meaning.

## Current Evidence

Focused validation currently covers 15 fixture scenarios:

- 5 original deterministic scenarios
- 10 adversarial starter scenarios behind `--include-adversarial`

Latest focused pytest run:

```text
29 passed
```

Latest adversarial smoke results:

```text
Meaning compression lab: CRT compressed 15/15
Structural baseline eval: CRT governed 15/15, raw baselines 0/15
Plain-RAG simulated eval: CRT 15/15, plain RAG 4/15
Meaning scaffold eval: scaffold 15/15, raw transcript fragments 4/15, avg scaffold ratio 0.442
Meaning scaffold Ollama eval: qwen2.5 raw RAG 7/15, qwen2.5 scaffold 15/15, avg scaffold ratio 0.468
Meaning scaffold model sweep: scaffold advantage 4/4 models, avg raw rate 0.417, avg scaffold rate 0.833
```

Latest scaffold Ollama result:

```text
labs/meaning_compression_lab/results/scaffold_eval_ollama_1781581382.json
labs/meaning_compression_lab/results/scaffold_model_sweep_1781598325.json
```

Cross-model scaffold sweep:

```text
qwen2.5:7b-instruct  raw 7/15, scaffold 15/15
phi3:3.8b            raw 7/15, scaffold 14/15
llama3.2:latest      raw 4/15, scaffold 13/15
mistral:latest       raw 7/15, scaffold 8/15
```

## What The Current Lab Shows

- Current facts can supersede older facts without deleting history.
- Contradictions can be preserved as explicit meaning-bearing structure.
- Provisional/social/tool/model fragments can be kept from overriding confirmed user facts.
- Locked policy can survive compression as a refusal rule.
- Raw retrieved text can follow attractive but wrong fragments.
- A compressed meaning scaffold can carry the load-bearing pieces needed for answer behavior.

## What Is Still Weak

- The adversarial pack is still hand-authored and small.
- Plain RAG is still mostly deterministic/simulated unless Ollama mode is run.
- The scaffold eval has only been run on four local models; Mistral shows scaffold/executor coupling weakness.
- Dynamic slot discovery is not solved.
- Policy extraction is narrow.
- Real-world memory scale is not proven.

## Immediate Next Work

1. Analyze scaffold failures by model and tighten the scaffold contract without overfitting.
2. Expand adversarial scenarios toward 25-30 cases.
3. Harden plain-RAG retrieval and judging.
4. Add a claim matrix report.

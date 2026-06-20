# CRT Meaning-Compression Lab Status

Last updated: 2026-06-19

## Runtime Graduation

The exploratory lab phase is frozen. Validated components are now merged into
`aether-core`, exposed through `aether_query_context`, installed, and verified
with an MCP before/after demonstration.

```text
Raw latest-state unsafe releases: 3
Aether governed unsafe releases:  0
Safe confirmed release retained:  1
Clause coverage:                  100%
Install verification:             PASS
Regression gate:                  679 passed, 1 network-only deselected
```

See `RUNTIME_GRADUATION_RESULTS_20260619.md`.

## Current Claim

CRT is currently being tested as a meaning-compression and governed-memory
harness:

> A compact meaning scaffold can preserve current facts, prior facts,
> contradictions, authority, policy, volatility, and response rules better than
> raw retrieval, latest-only slots, or naive summaries.

This is not yet a product claim and not a universal theory of meaning.

## Current Evidence

Frozen next-phase evaluation rules:

```text
labs/meaning_compression_lab/EVALUATION_CONTRACT.md
```

Latest four-model scaffold sweep, rescored by meaning/scope/format:

```text
Raw semantic success: 35/76 (46.1%)
Hybrid CRT semantic success: 64/76 (84.2%)
Hybrid CRT full contract: 59/76 (77.6%)
```

Four-model strong temporal/metadata-RAG comparison:

```text
Temporal metadata RAG semantic: 57/76 (75.0%)
Hybrid CRT semantic: 64/76 (84.2%)
Hybrid advantage: 9.2 percentage points
Temporal metadata RAG severe failures: 7
Hybrid CRT severe failures: 1
Hybrid wins: Qwen, Phi-3, Llama 3.2
Temporal RAG wins: Mistral
```

This remains preliminary because it uses the current hand-authored case pack.
The aggregate advantage is slightly below the frozen 10-point threshold, and
Mistral performs substantially better with rich metadata than with the compact
scaffold. That model/scaffold interaction is part of the result, not noise to
average away.

The held-out implementation boundary is recorded in:

```text
labs/meaning_compression_lab/FROZEN_SNAPSHOT_20260619.md
```

The temporal baseline now supports lexical, embedding, and hybrid retrieval.
Actual MiniLM 384-dimensional embeddings were verified across all 19 existing
cases. However, every current case has four or fewer memories and retrieval
uses `k=4`, so the current pack cannot measure retrieval discrimination.

Six candidate held-out cases now bring the pack to 25. Each contains seven
candidate memories, and the frozen hybrid retriever recovered all declared
required evidence in its top four on 6/6 cases before model answers were
inspected:

```text
labs/meaning_compression_lab/HELDOUT_MANIFEST_20260619.md
```

The first shared-evidence held-out sweep is complete:

```text
Temporal metadata RAG semantic: 22/24 (91.7%)
Hybrid CRT semantic:            22/24 (91.7%)
Temporal full contract:         22/24 (91.7%)
Hybrid full contract:           21/24 (87.5%)
Semantic advantage:             0.0 points
Severe failures:                0 for both arms
Model wins:                     hybrid 1, temporal 1, tied 2
```

Detailed result:

```text
labs/meaning_compression_lab/HELDOUT_RESULTS_20260619.md
```

The hybrid met its absolute semantic, contract, and severe-failure thresholds,
but failed the required comparative advantage. Phi-3 improved with CRT while
Mistral regressed by the same amount. The current result therefore points to a
model/scaffold interface problem rather than a universal governance advantage.

The frozen interface pivot has now been run:

```text
Full scaffold semantic:      22/24
Query-shaped projection:     24/24
Projection plus gate:        24/24
Full scaffold contract:      21/24
Projected/gated contract:    24/24
Repairs triggered live:      0
False repairs:               0
```

Mistral improved from 4/6 to 6/6 when current-only questions exposed only the
relevant CURRENT and AUTHORITY fragments. Phi-3, Qwen, and Llama remained 6/6.

```text
labs/meaning_compression_lab/INTERFACE_PIVOT_RESULTS_20260619.md
```

The live run demonstrates projection. The deterministic repair gate is covered
by tests but did not activate because projection prevented the scored failures.

The first Mirus/Holden governance-dose calibration is also complete:

```text
Selected profiles:
  Qwen      Dose 1
  Phi-3     Dose 1
  Llama     Dose 5
  Mistral   Dose 1

Validation:
  profile-selected semantic/contract: 24/24
  fixed full-scaffold semantic:        22/24
  fixed full-scaffold contract:        21/24
  severe failures:                     0
```

Calibration curves were non-monotonic. Qwen, Phi-3, and Mistral degraded with
heavier governance exposure, while Llama benefited from maximal warnings.
Profiles were selected without model-name rules and before validation scoring.

```text
labs/meaning_compression_lab/GOVERNANCE_DOSE_RESULTS_20260619.md
```

Frozen profiles were then tested on a new post-freeze bounded-fetch challenge:

```text
Semantic success:          24/24
Full-contract success:     24/24
Correct fetch decisions:   24/24
Unnecessary fetches:       0
Missed fetches:            0
Fetches above limit:       0
Severe failures:           0
```

Four cases began without sufficient top-2 evidence. Holden requested exactly
one governed slot, recompiled state, and generated only after sufficiency.
Two controls generated without an unnecessary fetch. Profile doses remained
unchanged.

```text
labs/meaning_compression_lab/BOUNDED_FETCH_RESULTS_20260619.md
```

The declared slot oracle has now been removed in a first inference ablation:

```text
Slot inference:
  resolved correctly: 5/6
  safe abstentions:    1
  confidently wrong:  0
  contract correct:    6/6

Inference-backed bounded fetch:
  automated:           20/24 model-cases
  full contract:       20/20 automated
  wrong slot fetches:  0
  clarifications:      4
```

The unresolved question asked what “name” should appear in generated files.
Holden correctly detected ambiguity between `file_naming` and personal `name`
and blocked automation.

```text
labs/meaning_compression_lab/SLOT_INFERENCE_RESULTS_20260619.md
```

The classifier has now been expanded from winner-take-all inference into a
multi-request planner:

```text
clause segmentation
-> deterministic multi-label candidates
-> preserve resolved clauses
-> semantic parser for unresolved clauses
-> schema/catalog validation
-> clause coverage
-> independent retrieval operations
```

The real local-model semantic fallback passed 2/2 initial probes, including an
indirect employer plus camera-history request in one turn. Invented slots are
rejected, and unresolved clauses do not erase resolved requests.

```text
labs/meaning_compression_lab/MULTI_REQUEST_PLANNER_RESULTS_20260619.md
```

The planner now executes end to end:

```text
compound request
-> independent retrieval per request
-> independent governed state compilation
-> one combined generation
-> deterministic clause-coverage gate
```

Four models across four compound cases:

```text
Full clause coverage:       15/16 (93.8%)
Complete answers released:  15
Incomplete answers blocked: 1
Partial answers released:   0
Models perfect:             3/4
```

The only block was a Qwen policy clause that refused generically without naming
the prohibited production-media deletion. The factual clause was correct, but
Holden correctly withheld the combined partial answer.

```text
labs/meaning_compression_lab/MULTI_REQUEST_EXECUTION_RESULTS_20260619.md
```

Selective one-pass repair is now implemented:

```text
Full clause coverage:        16/16
Complete answers released:   16
Incomplete answers released: 0
Repair calls:                1
Successful repairs:          1
Models perfect:              4/4
```

Qwen's failed policy segment was repaired with one structured JSON call while
the passing project segment remained byte-for-byte unchanged. Incomplete
multi-repair output is rejected rather than partially applied.

```text
labs/meaning_compression_lab/MULTI_REQUEST_REPAIR_RESULTS_20260619.md
```

The planner/retriever/compiler loop is now connected read-only to Aether's live
persisted slot substrate:

```text
Planner clauses resolved: 3/3
Independent live packets: 3
Substrate changed:        no
Live slots:               11
Live states:              150
Confirmed/releasable:     0
Slots with current forks: 7
```

All live observations currently originate from `auto_ingest`, so the frozen
adapter correctly treats them as provisional and withholds them. The smoke also
found that seven slots have multiple distinct values across non-superseded
current branches; the normal MCP current-state read returns only the newest and
masks this ambiguity.

```text
labs/meaning_compression_lab/AETHER_LIVE_ADAPTER_RESULTS_20260619.md
```

The upstream ingestion and confirmation boundary is now patched:

```text
- value changes supersede every conflicting current branch
- user slots extract only from user-authored text
- regex, LLM, and user-confirmation provenance are distinct
- current reads fail closed on legacy distinct-value forks
- candidate confirmation is idempotent across timeout retries
- confirmation closes duplicate and competing provisional branches

Core tests: 27 passed
Lab tests:  32 passed
```

The seven existing live forks were not mutated.

```text
labs/meaning_compression_lab/AETHER_INGESTION_CONFIRMATION_PATCH_20260619.md
```

The bounded legacy-fork reviewer is now implemented:

```text
aether slot-review
```

It lists candidate values, state IDs, timestamps, provenance, source evidence,
and quality flags without writing. Confirmation requires the reviewed substrate
SHA, explicit state ID, and an idempotency key. The live audit found seven
forks and left the substrate unchanged.

Several project slots contain no credible candidate, so confirmation alone is
not enough for every fork. They require reject-all/quarantine or a fresh user
statement rather than canonizing the least-wrong extraction.

```text
labs/meaning_compression_lab/AETHER_LEGACY_FORK_REVIEW_RESULTS_20260619.md
```

Reject-all quarantine is now implemented across the graph, MCP, CLI, and CRT
adapter. It preserves complete history, records an idempotent audit marker,
closes every current candidate, and leaves no current answerable value.

```text
Core tests:    40 passed
Adapter tests: 23 passed
Live writes:   0
```

```text
labs/meaning_compression_lab/AETHER_QUARANTINE_RESULTS_20260619.md
```

Focused validation currently covers 15 primary fixture scenarios plus a
4-scenario hardening pack:

- 5 original deterministic scenarios
- 10 adversarial starter scenarios behind `--include-adversarial`
- 4 layer-specific hardening scenarios behind `--include-hardening`

Latest hardening-focused pytest run:

```text
21 passed
```

Latest adversarial smoke results:

```text
Meaning compression lab: CRT compressed 15/15
Structural baseline eval: CRT governed 15/15, raw baselines 0/15
Plain-RAG simulated eval: CRT 15/15, plain RAG 4/15
Meaning scaffold eval: scaffold 15/15, raw transcript fragments 4/15, avg scaffold ratio 0.442
Meaning scaffold Ollama eval: qwen2.5 raw RAG 7/15, qwen2.5 scaffold 15/15, avg scaffold ratio 0.468
Meaning scaffold model sweep: scaffold advantage 4/4 models, avg raw rate 0.417, avg scaffold rate 0.833
Meaning scaffold ablation: deterministic full 15/15; qwen2.5 full 15/15; removing qwen2.5 query contract drops to 11/15
```

Latest hardening smoke results:

```text
Meaning compression lab with hardening: CRT compressed 19/19
Plain-RAG simulated eval with hardening: CRT 19/19, plain RAG 5/19
Meaning scaffold eval with hardening: scaffold 19/19, raw transcript fragments 5/19, avg scaffold ratio 0.480
Meaning scaffold ablation with hardening: full 19/19; no_history 18/19; no_authority 18/19; no_reaction 18/19; no_policies 16/19
```

Latest scaffold Ollama result:

```text
labs/meaning_compression_lab/results/scaffold_eval_ollama_1781581382.json
labs/meaning_compression_lab/results/scaffold_model_sweep_1781598325.json
labs/meaning_compression_lab/results/scaffold_ablation_deterministic_1781638870.json
labs/meaning_compression_lab/results/scaffold_ablation_ollama_1781638860.json
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
- Scaffold ablation now makes history, authority, reaction, and policy layers visible under the hardening probe set.

## What Is Still Weak

- The adversarial pack is still hand-authored and small.
- Plain RAG is still mostly deterministic/simulated unless Ollama mode is run.
- The scaffold eval has only been run on four local models; Mistral shows scaffold/executor coupling weakness.
- The hardening probes are still hand-authored; they show layer visibility, not broad generalization.
- The hardening probes have not yet been rerun through Ollama/model sweep.
- Dynamic slot discovery is not solved.
- Policy extraction is narrow.
- Real-world memory scale is not proven.

## Immediate Next Work

The lab has no open implementation queue. Product work now lives in
`aether-core`.

1. Restart the active MCP process so clients see `aether_query_context`.
2. Wire one external harness to consume packet release decisions.
3. Resolve `employer` and `favorite_color` only through explicit user
   confirmation or quarantine.

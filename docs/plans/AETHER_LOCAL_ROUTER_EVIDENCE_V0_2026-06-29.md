# Aether Local Router Evidence v0 - 2026-06-29

## Claim

This evidence supports a bounded Aether/Core claim:

```text
Governed external cognition made local-model behavior more reliable,
inspectable, and governable than raw local chat on the curated replay pack.
```

It does not support these claims:

```text
local models beat frontier models
Aether is solved
the model is thinking independently
the replay pack proves broad reliability
the system should silently learn from passing cases
```

## Frozen Result

Final curated replay:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782716566.json
```

Pack:

```text
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json
```

Result:

```text
Raw local chat:            0/32
Governed routed answer:   32/32
Trace quality:            32/32
Combined answer + trace:  32/32

Average raw score:        0.407
Average routed score:     0.773
Average lift:             +0.366
Repairs used:             5
Fallbacks used:           5
Hard flags:               none
```

## What Passed

The full system path passed:

```text
request classification
route/model/scaffold policy
Mirus packet / semantic spine
Holden-style final rendering
CRT verifier
repair/fallback when needed
durable structured trace
combined answer + trace gate
review-only feedback ledger
```

## Feedback Result

Feedback ledger:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_feedback_ledger_1782716566.json
```

Result:

```text
32 feedback rows
4 Workbench preview candidates
0 memory writes
0 support-pattern imports
0 reflection creations
```

The feedback loop is therefore review-only. It is not neural learning, not a
thumbs-up/thumbs-down reward model, and not silent behavior mutation.

## Workbench Bridge

The 4 feedback-ledger candidates render in the real Workbench Learn drawer:

```text
D:\AI_round2\workbench\src\fixtures\localRouterFeedbackPreview.ts
D:\AI_round2\workbench\src\App.test.tsx
```

They open as manual Support/Reflect draft handoffs. They do not write memory,
import support patterns, or create reflections unless a human explicitly acts.

## Limitations

```text
The pack has only 32 cases.
The pack was curated from known logs.
Policy and anchors were tuned while observing failures.
The evaluator is local and may share assumptions with the scaffold.
Passing v1 can overfit to wording, anchors, and grading rules.
One-case smoke tests are not general evidence.
```

## Next Evidence Tests

Perturbed replay pack:

```text
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_replay_perturbed_v2.json
```

Smoke:

```text
Raw 0/1 avg 0.537
Routed 1/1 avg 0.716
Trace 1/1 avg 1.000
Combined 1/1
```

Full perturbed v2 run after narrow detector/scaffold hardening:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782721572.json

Raw local chat:            1/32
Governed routed answer:   32/32
Trace quality:            32/32
Combined answer + trace:  32/32

Average raw score:        0.489
Average routed score:     0.770
Average lift:             +0.280
Repairs used:             5
Fallbacks used:           7
Hard flags:               none
```

Interpretation:

```text
The architecture survived first-pass wording drift. This is stronger than the
frozen v1 result, but still not final proof because v2 is mechanically derived
from v1 rather than blind.
```

Blind v1 replay pack:

```text
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_replay_blind_v1.json
```

Blind selection rule:

```text
exclude v1 source conversation ids
exclude v1 prompt dedupe keys
exclude low-specificity / quote / artifact-like candidate flags
select at most one case per conversation
```

Full blind v1 run:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782745851.json

Raw local chat:            0/13
Governed routed answer:   13/13
Trace quality:            13/13
Combined answer + trace:  13/13

Average raw score:        0.382
Average routed score:     0.761
Average lift:             +0.379
Repairs used:             1
Fallbacks used:           0
Hard flags:               none
```

Interpretation:

```text
The architecture survived the first clean blind pack. This is the strongest
evidence so far, but the blind pack is still small and sourced from the same
export universe.
```

Ablation harness:

```text
D:\AI_round2\labs\meaning_compression_lab\local_router_ablation.py
```

One-case smoke:

```text
raw_no_scaffold: answer 0/1 avg 0.497
full:            answer 1/1 avg 0.659, trace 1/1
```

Blind v1 ablation slice:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782746144.json

Cases: 4
raw_no_scaffold:      answer 0/4 avg 0.463, trace 0/4, failures 4
routed_no_repair:    answer 4/4 avg 0.748, trace 4/4, failures 0
routed_no_fallback:  answer 4/4 avg 0.781, trace 4/4, failures 0
full:                answer 4/4 avg 0.781, trace 4/4, failures 0
```

Interpretation:

```text
On the first blind slice, routing/scaffold/Mirus context carried the lift before
repair or fallback were needed. This is useful mechanism evidence, but it is
only a 4-case slice and must be expanded before stronger claims.
```

Full blind v1 ablation:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782746575.json

Cases: 13
raw_no_scaffold:      answer 0/13 avg 0.409, trace 0/13, failures 13
routed_no_repair:    answer 12/13 avg 0.768, trace 13/13, failures 1
routed_no_fallback:  answer 13/13 avg 0.775, trace 13/13, failures 0
full:                answer 13/13 avg 0.774, trace 13/13, failures 0
```

Interpretation:

```text
On the full blind v1 pack, the route/scaffold/Mirus path carried almost all of
the improvement. Repair closed one remaining grant_business coverage failure;
fallback was not required. This strengthens the mechanism claim while keeping
it bounded to a 13-case blind pack from the same export universe.
```

Full perturbed v2 ablation:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782748218.json

Cases: 32
raw_no_scaffold:      answer 0/32 avg 0.494, trace 0/32, failures 32
routed_no_repair:    answer 22/32 avg 0.718, trace 32/32, failures 10
routed_no_fallback:  answer 23/32 avg 0.726, trace 32/32, failures 9
full:                answer 28/32 avg 0.757, trace 32/32, failures 4
```

Targeted normal replay of the four full-ablation failures:

```text
gptlog_017_grant_business_perturb_01
gptlog_019_grant_business_perturb_01
gptlog_021_grant_business_perturb_01
gptlog_028_architecture_process_perturb_01

Raw 0/4 avg 0.513
Routed 4/4 avg 0.746
Trace 4/4 avg 1.000
Combined 4/4
Repairs 1
Fallbacks 1
Hard flags: none
```

Interpretation:

```text
Perturbed wording makes repair/fallback more important than the blind pack did.
The ablation path left 4/32 failures, while targeted normal replay of those
same four cases passed cleanly. Treat this as evidence of stochastic/path
sensitivity and a reason to repeat or stabilize perturbed ablations before
making a stronger mechanism claim.
```

Repeat full-mode ablation on the same four cases:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782748474.json

Cases: 4
full: answer 2/4 avg 0.673, trace 4/4, repairs 2, fallbacks 1, failures 2

Repeated failures:
gptlog_017_grant_business_perturb_01 - grant_business coverage too generic
gptlog_019_grant_business_perturb_01 - business_planning coverage too generic
```

Interpretation:

```text
The perturbed failure pocket is repeatable enough to review, but it is still an
answer-quality/coverage problem rather than a trace, leakage, or hard-safety
problem. Do not promote a new policy from this alone; first review anchor fit
and stabilize the ablation path.
```

Next required evidence before stronger claims:

```text
1. Review the repeated perturbed coverage failures for anchor fit:
   gptlog_017_grant_business_perturb_01
   gptlog_019_grant_business_perturb_01
2. Stabilize the perturbed ablation path before promoting policy changes.
3. Expand blind cases beyond 13 while preserving quality filters.
4. Compare failures by task type and route.
5. Promote only deterministic policy/scaffold changes supported by repeated failures.
```

## Business-Grade Wording

Use this phrasing:

```text
We tested raw local model behavior against a governed local routing system across
a curated replay pack. On the frozen v1 pack, raw local chat failed the
evaluator across all cases while the governed system passed answer and trace
requirements across all cases. On a mechanically perturbed v2 pack, raw local
chat passed 1/32 while the governed system again passed answer and trace
requirements across all cases. On a clean blind v1 pack that excluded source
conversations and prompt dedupe keys from v1, raw local chat passed 0/13 while
the governed system passed 13/13 with trace 13/13. The improvement came from
externalized cognition: structured memory packets, routing policy, scaffolds,
verification, repair/fallback, and durable trace.
```

Do not inflate it beyond this.

## RAG Baseline v0

Rationale:

```text
Raw local chat is too weak a baseline by itself. Aether governance needs to be
compared against realistic retrieval baselines before the evidence can support
strong roadmap, product, or funding claims.
```

Replay-compatible RAG suite:

```text
D:\AI_round2\labs\meaning_compression_lab\local_router_rag_suite.py
```

Modes:

```text
raw
plain_rag
scaffolded_rag
governed
```

What it tests:

```text
raw:
  local model with no replay-pack retrieval.

plain_rag:
  lexical retrieval over replay-pack prompt/reference/requirement chunks, then
  answer from retrieved context without Mirus/CRT state.

scaffolded_rag:
  same retrieved context, plus task type, output scaffold, anchors, concepts,
  and final-answer policy. This is RAG plus formatting/governance hints, not
  full Mirus belief state.

governed:
  existing Aether local-router path: Mirus packet, route/scaffold, verifier,
  repair/fallback, and durable trace.
```

Initial blind-v1 smoke:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782749903.json

Cases: 1
Retrieval receipt coverage: 0.750
Retrieval concept coverage: 0.000

raw:            answer 0/1 avg 0.537
plain_rag:      answer 0/1 avg 0.480
scaffolded_rag: answer 1/1 avg 0.710
governed:       answer 1/1 avg 0.716, trace 1/1
```

Interpretation:

```text
This is only a smoke test, but it shows why the RAG baseline matters. Plain RAG
did not automatically close the gap. Scaffolded RAG did close this first case,
and governed Aether matched it while also producing a passing trace. The next
evidence step is to run the suite over blind and perturbed packs before making
any stronger claim.
```

Representative blind-v1 slice:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782750349.json

Cases: 4
Retrieval receipt coverage: 0.812
Retrieval concept coverage: 0.250

raw:            answer 0/4 avg 0.405
plain_rag:      answer 0/4 avg 0.420
scaffolded_rag: answer 3/4 avg 0.770
governed:       answer 4/4 avg 0.740, trace 4/4, repairs 1
```

Blind slice interpretation:

```text
Plain RAG still did not close the gap. Scaffolded RAG nearly matched governed
Aether, but failed one personal_synthesis case by inventing generic personal
receipts when retrieval found the prompt but not enough real evidence. Governed
Aether passed the slice with trace and one repair.
```

Representative perturbed-v2 slice:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782750521.json

Cases: 4
Retrieval receipt coverage: 1.000
Retrieval concept coverage: 0.500

raw:            answer 0/4 avg 0.571
plain_rag:      answer 0/4 avg 0.577
scaffolded_rag: answer 4/4 avg 0.804
governed:       answer 4/4 avg 0.767, trace 4/4
```

Perturbed slice interpretation:

```text
The strongest baseline is scaffolded RAG, not plain RAG. On this small
perturbed slice, scaffolded RAG matched governed answer pass rate and scored
slightly higher, while governed Aether added durable trace. The next evidence
question is whether governed Aether beats scaffolded RAG on broader blind,
personal-synthesis, weak-retrieval, and adversarial cases.
```

Expanded perturbed-v2 slice:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782752318.json

Cases: 8
Retrieval receipt coverage: 1.000
Retrieval concept coverage: 0.500

raw:            answer 1/8 avg 0.560
plain_rag:      answer 0/8 avg 0.549
scaffolded_rag: answer 6/8 avg 0.748
governed:       answer 8/8 avg 0.757, trace 8/8, fallbacks 2
```

Scaffolded-RAG failures:

```text
architecture_synthesis: 2
```

Expanded perturbed interpretation:

```text
With more architecture-synthesis perturbations, scaffolded RAG no longer fully
matches governed Aether. Retrieval coverage was high, so the failures are not
mostly retrieval misses. The failure pattern is semantic-boundary drift:
forbidden frame words, mutated project terms, and claims that the scaffold alone
does not reliably police. Governed Aether's visible edge here is verifier and
fallback behavior plus durable trace.
```

Perturbed-v2 personal-synthesis slice:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782753077.json

Cases: 8
Retrieval receipt coverage: 0.500
Retrieval concept coverage: 0.000

raw:            answer 0/8 avg 0.480
plain_rag:      answer 0/8 avg 0.405
scaffolded_rag: answer 2/8 avg 0.764
governed:       answer 8/8 avg 0.778, trace 8/8
```

Scaffolded-RAG failures:

```text
personal_synthesis: 6
```

Personal-synthesis interpretation:

```text
This is the clearest weak-retrieval RAG result so far. Scaffolded RAG often
understands the shape of the task, but when concrete personal receipts are thin
it still drifts into generic or identity-like claims. Governed Aether passed
because the Mirus packet, receipt gate, and route policy force tighter evidence
boundaries.
```

Perturbed-v2 business/grant slice:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782754067.json

Cases: 8
Retrieval receipt coverage: 0.333
Retrieval concept coverage: 0.369

raw:            answer 1/8 avg 0.497
plain_rag:      answer 0/8 avg 0.439
scaffolded_rag: answer 1/8 avg 0.522
governed:       answer 8/8 avg 0.727, trace 8/8, repairs 1, fallbacks 3
```

Scaffolded-RAG failures:

```text
grant_business: 6
business_planning: 1
```

Business/grant interpretation:

```text
This is the weakest scaffolded-RAG slice so far. The failure pattern is
plausible business language without enough task-specific receipts, especially
missing Aether/CRT/router anchors in grant_business cases. Governed Aether's
edge here is task-fit routing plus repair/fallback under low receipt coverage.
```

Perturbed-v2 architecture/process slice:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782755020.json

Cases: 8
Retrieval receipt coverage: 0.625
Retrieval concept coverage: 0.417

raw:            answer 0/8 avg 0.439
plain_rag:      answer 0/8 avg 0.431
scaffolded_rag: answer 3/8 avg 0.658
governed:       answer 7/8 avg 0.772, trace 8/8, repairs 3, fallback 1
```

Scaffolded-RAG failures:

```text
architecture_process: 5
```

Governed failure:

```text
architecture_process: 1
gptlog_026_architecture_process_perturb_01
```

Architecture/process interpretation:

```text
Governed Aether still beats scaffolded RAG on this slice, but it is not
perfect. The remaining governed miss is a coverage/anchor-fit architecture case,
not a trace, leakage, weirdness, or forbidden-claim failure. This is useful
because it breaks the suspicious perfect-score pattern without breaking the
overall governance signal.
```

Perturbed-v2 sliced total:

```text
Cases: 32

raw:            answer 2/32 avg 0.494
plain_rag:      answer 0/32 avg 0.456
scaffolded_rag: answer 12/32 avg 0.673
governed:       answer 31/32 avg 0.758, trace 32/32, repairs 4, fallbacks 6
```

Scaffolded-RAG failures by task type:

```text
architecture_process: 5
architecture_synthesis: 2
business_planning: 1
grant_business: 6
personal_synthesis: 6
```

Perturbed-v2 total interpretation:

```text
Across the sliced perturbed pack, scaffolded RAG is clearly the meaningful
baseline, but governed Aether still has a large advantage. The advantage is no
longer "beats raw local." It is: better receipt discipline, task-fit routing,
repair/fallback, semantic-boundary control, and trace under conditions where
retrieval plus scaffold often sounds plausible but misses the evidence contract.
```

Full blind-v1 RAG run:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782751568.json

Cases: 13
Retrieval receipt coverage: 0.558
Retrieval concept coverage: 0.342

raw:            answer 0/13 avg 0.404
plain_rag:      answer 0/13 avg 0.384
scaffolded_rag: answer 7/13 avg 0.664
governed:       answer 13/13 avg 0.757, trace 13/13, repairs 1, fallbacks 3
```

Scaffolded-RAG failures:

```text
personal_synthesis: 2
business_planning: 3
grant_business: 1
```

Full blind interpretation:

```text
On the full blind pack, scaffolded RAG is clearly stronger than plain RAG but
does not match governed Aether. The failure pocket is concentrated in personal
synthesis and business/grant planning, especially where retrieved evidence is
thin, mismatched, or lacks concrete receipts. Governed Aether's current added
value is not just retrieval plus formatting; it is receipt discipline, task-fit
routing, repair/fallback, and durable trace.
```

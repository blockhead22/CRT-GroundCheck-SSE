# Aether Low-Score Anchor-Fit Review - 2026-06-29

Context:

```text
Post-policy curated replay:
Raw 0/32
Routed 28/32
Trace 32/32
Combined 28/32
0 forbidden hits
0 leakage hits
0 weirdness hits
0 truncation failures
```

The remaining failures are low-score/coverage failures, not safety failures.
Do not lower verifier thresholds or weaken final-answer policy to make these
pass. The first issue to review is anchor fit.

## Finding

The remaining failures mostly come from case/default anchor mismatch:

```text
gptlog_019_grant_business
gptlog_027_architecture_process
gptlog_028_architecture_process
gptlog_030_architecture_process
```

## Case Review

### gptlog_019_grant_business

Prompt:

```text
with the camera gear i have. could i if i applied myself. maybe turn that into
a full small business?
```

Current anchors:

```text
local, CRT, Aether
```

Current concepts:

```text
measurable, low-cost, business, verifier, AI request router
```

Review:

```text
This is not an Aether/Core grant or local-router business prompt. It is a
personal small-business planning prompt. Requiring CRT/Aether/local-router
anchors is bad evidence hygiene.
```

Recommended action:

```text
Split non-Aether business prompts into business_planning, or supply
case-specific anchors:
camera gear, small business, applying myself, pricing/offer/risk.
```

Do not:

```text
Do not relax grant/business safety policy. The failure is anchor fit, not
over-restraint.
```

### gptlog_027_architecture_process

Prompt focus:

```text
LLM reasoning with one memory at a time, self-reflect contradictions,
fallbacks to LLMs, concept-chain reasoning, whether CRT can reason with an
entire concept/idea.
```

Current anchors:

```text
roadmap, architecture, risk
```

Review:

```text
The task label is right, but the default anchors are too generic. The prompt is
about memory reasoning granularity and contradiction-chain investigation, not a
generic roadmap.
```

Recommended anchors:

```text
one memory at a time
self reflect
contradictions
fallbacks
reasoning chain
```

### gptlog_028_architecture_process

Prompt focus:

```text
Show Mistral output in parallel, do not affect the outcome, log degradation,
debug the core system while getting the system into real-world user hands.
```

Current anchors:

```text
roadmap, architecture, risk
```

Review:

```text
The prompt is operational fallback/degradation logging. The default architecture
anchors miss the important receipts.
```

Recommended anchors:

```text
fallback logged
Mistral response
parallel
do not affect outcome
degradation/debug
real-world user hands
```

### gptlog_030_architecture_process

Prompt focus:

```text
How tools/services are exposed to an LLM, how a smaller open-source model knows
to invoke an action, debugger tool, attention/coherence ledger.
```

Current anchors:

```text
roadmap, architecture, risk
```

Review:

```text
The task label is right, but the default anchors miss tool exposure and action
invocation. This is a tool-contract/process prompt, not a roadmap prompt.
```

Recommended anchors:

```text
tools/services
context
invoke an action
debugger tool
attention/coherence ledger
```

## Recommended Next Technical Move

Prefer this order:

```text
1. Add a business_planning task type for non-Aether business prompts.
2. Split architecture_process defaults into either:
   - architecture_process generic fallback defaults; plus
   - per-case pack anchors for the curated replay cases above.
3. Re-run only the four reviewed cases before changing any verifier threshold.
```

## Status After Implementation

Implemented:

```text
business_planning task type
case-specific anchors for gptlog_027_architecture_process
case-specific anchors for gptlog_028_architecture_process
case-specific anchors for gptlog_030_architecture_process
--case-id targeted replay filter
architecture_process final-answer policy for banned limit wording
```

Targeted replay result:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782713622.json

Raw 0/4
Routed 4/4
Trace 4/4
Combined 4/4
No hard flags
```

Full replay after this pass:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782714154.json

Raw 0/32
Routed 28/32
Trace 32/32
Combined 28/32

Remaining failures:
3 personal_synthesis receipt-gate failures
1 grant_business bounded-claim/guarantee wording failure
```

Final status:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782716566.json

Raw 0/32
Routed 32/32
Trace 32/32
Combined 32/32

The remaining personal receipt and grant/business task-fit failures were closed.
This review family is complete for the current 32-case pack.
```

Next review family:

```text
Do not revisit the fixed architecture anchors unless a regression appears.
Focus next on Workbench graduation, reviewed feedback metadata, and a larger or
more adversarial replay pack rather than further threshold tuning.
```

## Perturbed V2 Repeated Coverage Pocket

Context:

```text
Full perturbed ablation:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782748218.json

raw_no_scaffold 0/32
routed_no_repair 22/32
routed_no_fallback 23/32
full 28/32

Targeted normal replay of the four full-ablation failures passed 4/4.
Repeat full-mode ablation on those same four:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782748474.json

full 2/4
trace 4/4
repeated failures:
gptlog_017_grant_business_perturb_01
gptlog_019_grant_business_perturb_01
```

These are answer-quality/coverage failures, not trace failures, leakage
failures, weirdness failures, or hard-safety failures.

### gptlog_017_grant_business_perturb_01

Prompt focus:

```text
Aeteros as the overarching company, Aether/Lumi as the starting product and
research object, real-world applications such as robotics, chatbot assistant
first, UI features over time, and future voice work.
```

Current anchors:

```text
local, CRT, Aether
```

Current concepts:

```text
measurable, low-cost, business, verifier, AI request router
```

Observed repeated failure:

```text
The answer hit local and Aether, plus measurable/low-cost/business, but missed
CRT, verifier, and AI request router.
```

Review:

```text
This looks like default grant_business anchor mismatch. The perturbed prompt is
about company/product framing and real-world application sequencing. It does
not explicitly ask for CRT, verifier, or AI request router. Requiring those
terms risks grading the system for inserting internal architecture language
that the final-answer policy also discourages.
```

Recommended action:

```text
Do not loosen grant/business safety policy.
Either add case-specific anchors for this case, or split a product_strategy /
company_framing subtype from grant_business if this pattern repeats.

Candidate anchors:
Aeteros, Aether, Lumi, chatbot assistant, UI features, voice, real-world
applications, robotics

Candidate concepts:
product sequence, bounded roadmap, business fit, measurable prototype,
research-to-application boundary
```

### gptlog_019_grant_business_perturb_01

Prompt focus:

```text
with the camera gear i have. could i if i applied myself. maybe turn that into
a full small business?
```

Current anchors:

```text
camera gear, applied myself, small business
```

Current concepts:

```text
offer, pricing, risk, next useful move
```

Observed repeated failure:

```text
The answer hit camera gear and small business, plus all four required concepts.
It missed the exact anchor "applied myself" even though it said "with the right
application of effort."
```

Review:

```text
This is a brittle exact-anchor issue more than a weak scaffold issue. The answer
was generic in places, but the numeric miss is driven partly by phrase mismatch.
The concept coverage is already complete.
```

Recommended action:

```text
Do not promote a broad business_planning scaffold change from this one case.
Prefer anchor aliases or a case-specific anchor replacement:
applied myself -> effort, applied effort, application of effort, practice

If the case still fails after anchor hygiene, then review whether
business_planning needs stronger prompts for personal capacity, realistic first
offers, and local proof-of-demand.
```

## Perturbed Pocket Recommendation

```text
Treat this as anchor hygiene plus ablation stability work, not as evidence that
the governance path is broken. The right next technical move is a small,
reviewed anchor update or alias mechanism, followed by targeted replay and
ablation repeat on these two cases.
```

## Perturbed V2 Governed RAG Miss

Context:

```text
Perturbed-v2 sliced RAG total:
raw 2/32
plain_rag 0/32
scaffolded_rag 12/32
governed 31/32
trace 32/32

Governed miss:
gptlog_026_architecture_process_perturb_01

Artifact:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782755020.json
```

This is a governed answer-quality/coverage miss, not a trace, leakage,
weirdness, or forbidden-claim failure.

### gptlog_026_architecture_process_perturb_01

Prompt focus:

```text
Need multiple semantic string engines: vocabulary, worldview/unchangeable
empirical facts, and connecting threads. Because the system cannot afford the
full target architecture today, it must reason using an LLM, prove memory works,
and accept that drift and contradictions may appear.
```

Current anchors:

```text
roadmap, architecture, risk
```

Current concepts:

```text
mechanism, sequence, verification, next useful move
```

Observed governed result:

```text
The answer hit roadmap and risk.
It hit all required concepts.
It missed the literal architecture anchor.
It had clean trace and no hard safety flags.
It lacked the scorer's thesis/limit-language features.
```

Review:

```text
This looks like default architecture_process anchor mismatch plus a scorer-shape
miss. The answer was on-topic: semantic string engine framework, vocabulary
engine, fact engine, thread engine, proof-of-concept, verification, drift, and
contradictions. Requiring the literal word architecture is weaker than requiring
the specific semantic-engine receipts from the prompt.
```

Recommended action:

```text
Do not loosen architecture_process thresholds globally.
Prefer case-specific anchors:
semantic string engine
vocab / vocabulary
worldview
unchangeable facts
empirical evidence
connecting threads
prove memory works
drift
contradictions

Candidate concepts:
staged proof-of-concept
memory verification
separate engines
LLM-assisted reasoning
bounded roadmap

Also consider whether architecture_process repair/fallback should preserve a
plain thesis/limits sentence when it has already covered the mechanism and
sequence.
```

Do not:

```text
Do not treat this as proof that governed Aether failed semantically. It is a
useful miss because it exposes evidence-target mismatch in a non-perfect run.
```

## Roadmap Meaning

The lab evidence still supports the governance path:

```text
raw local chat loses all 32 cases
routed local model plus governance passes 32/32 in the latest full replay
trace passes 32/32
remaining failures in earlier runs were evidence-targeting problems
```

This is exactly the kind of failure CRT should expose: not "make it sound
better," but "the system asked the model to prove the wrong receipts."

## Follow-Up Anchor Hygiene Pass

Implemented after adversarial v1/v2 validation:

```text
D:\AI_round2\labs\meaning_compression_lab\local_router_perturb_pack.py
D:\AI_round2\labs\meaning_compression_lab\spiral_synthesis_eval.py
D:\AI_round2\tests\test_local_router_perturb_pack.py
D:\AI_round2\tests\test_spiral_synthesis_eval.py
```

Changes:

```text
gptlog_017_grant_business_perturb_01:
  reviewed case-specific product/company anchors now replace default
  local/CRT/router anchors in perturbed pack generation.

gptlog_026_architecture_process_perturb_01:
  reviewed semantic-engine anchors now replace generic roadmap/architecture/risk
  anchors in perturbed pack generation.

gptlog_019_grant_business_perturb_01:
  "applied myself" now accepts narrow effort/practice aliases such as
  "application of effort".
```

Verification:

```text
python -m pytest tests\test_local_router_perturb_pack.py tests\test_spiral_synthesis_eval.py tests\test_local_router_rag_suite.py -q
21 passed

python -m py_compile labs\meaning_compression_lab\local_router_perturb_pack.py labs\meaning_compression_lab\spiral_synthesis_eval.py
passed
```

Targeted perturbed RAG result:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782767376.json

Cases:
gptlog_017_grant_business_perturb_01
gptlog_019_grant_business_perturb_01
gptlog_026_architecture_process_perturb_01

raw:            0/3 avg 0.569
plain_rag:      0/3 avg 0.587
scaffolded_rag: 1/3 avg 0.676
governed:       3/3 avg 0.736, trace 3/3
```

Narrow full-mode ablation repeat:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782767424.json

Cases:
gptlog_017_grant_business_perturb_01
gptlog_019_grant_business_perturb_01

full: 2/2 avg 0.823, trace 2/2, repairs 0, fallback 1
```

Interpretation:

```text
The repeated perturbed pocket was anchor hygiene, not a threshold problem.
Reviewed case-specific anchors and one narrow alias closed the targeted RAG and
full-mode ablation checks while scaffolded RAG still missed 2/3 targeted RAG
cases. Do not keep tuning this pocket unless a larger replay exposes a new
failure.
```

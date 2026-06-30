# Aether Local-Router Lab Graduation - 2026-06-30

Purpose:

```text
Close the local-router / durable trace / RAG-baseline lab as an active tuning
lane and hand the usable pieces back to the Aether Workbench roadmap.
```

## Decision

```text
The lab is graduated as Aether/Core validation infrastructure.
```

It should no longer run as open-ended prompt tuning, model shopping, or repeated
adversarial v1/v2 retesting. Future work should touch this lane only when it
serves a specific Workbench, trace, review, or evidence question.

## What It Proved

The lab supports this bounded claim:

```text
A governed local system can materially improve small/local model reliability
over raw chat and plain/scaffolded RAG by moving cognition into inspectable
external structure: route, Mirus packet, scaffold, verifier, repair/fallback,
durable trace, and review-only learning candidates.
```

Evidence:

```text
curated v1:
raw 0/32
governed 32/32
trace 32/32

blind v1:
raw 0/13
governed 13/13
trace 13/13

perturbed sliced RAG:
raw 2/32 avg 0.494
plain_rag 0/32 avg 0.456
scaffolded_rag 12/32 avg 0.673
governed 31/32 avg 0.758
trace 32/32

adversarial v1:
scaffolded_rag 7/9
governed 9/9
trace 9/9

adversarial v2:
scaffolded_rag 5/6
governed 6/6
trace 6/6

targeted perturbed pocket:
scaffolded_rag 1/3
governed 3/3
trace 3/3
```

This is evidence for governance, not evidence that local models compete with
frontier models globally.

## What It Does Not Prove

Do not claim:

```text
local models are frontier-equivalent
Aether can autonomously learn truth
perfect replay scores are final proof
the evaluator is complete
the adversarial packs are broad enough for product claims
grant/business outcomes are guaranteed
personal synthesis is safe without receipts
```

The strongest competitor is `scaffolded_rag`, not raw local chat. Keep
`scaffolded_rag` as the baseline in any future evidence work.

## Graduated Mechanisms

Carry forward:

```text
task routing
Mirus packet / semantic spine
scaffold selection
answer verifier
repair/fallback
trace quality scoring
RAG baseline comparison
review-only feedback ledger
review-only RAG evidence metadata
Workbench Trace drawer evidence panel
Learn drawer preview-only evidence candidate
sidecar consolidation candidate from embedded trace evidence
explicit trace evidence attach CLI with live-DB double confirmation
```

Do not carry forward:

```text
silent memory mutation
silent support/reflection imports
raw hidden chain-of-thought storage
automatic live-DB evidence attachment
further adversarial v1/v2 tuning
random model download loops
```

## Workbench Bridge

Implemented bridge files:

```text
D:\AI_round2\labs\meaning_compression_lab\workbench_trace_adapter.py
D:\AI_round2\labs\meaning_compression_lab\workbench_trace_fixture.py
D:\AI_round2\labs\meaning_compression_lab\workbench_evidence_adapter.py
D:\AI_round2\labs\meaning_compression_lab\workbench_evidence_preview_cli.py
D:\AI_round2\labs\meaning_compression_lab\workbench_trace_evidence_attach_cli.py
D:\AI_round2\aether-core\aether\sidecar\consolidation.py
D:\AI_round2\workbench\src\components\TraceDrawer.tsx
D:\AI_round2\workbench\src\fixtures\localRouterRagEvidenceReview.ts
D:\AI_round2\workbench\src\fixtures\localRouterRagEvidencePreview.ts
```

Safety contract:

```text
memory_writes_allowed = false
raw_chain_of_thought_stored = false
silent_policy_mutation_allowed = false
review_required_before_promotion = true
```

The live Workbench DB remains protected. The attach CLI requires:

```text
--allow-live-db --confirm-live-db ATTACH_REVIEW_ONLY_TRACE_EVIDENCE
```

Even then, it writes only trace JSON.

## Stop Conditions

Stop scheduled lab work when:

```text
1. The work would only retune already-passing adversarial v1/v2 cases.
2. The work would add another import surface without a product need.
3. The work would compare only against raw chat and ignore scaffolded_rag.
4. The work would turn evidence into memory/support/reflection without review.
5. The work would broaden claims beyond the packs and evaluator.
```

Resume this lane only for:

```text
specific regression
new blind/adversarial evidence question
Trace drawer or Learn drawer review workflow bug
sidecar consolidation candidate bug
grant/product evidence summary
controlled model/API routing comparison with the same evaluator
```

## Roadmap Return

Next main-roadmap task:

```text
Phase 2 governed learner heartbeat:
recent traces/turns -> review-only Memory, Support, Reflection, Contradiction,
and Evidence candidates -> Workbench review -> durable behavior only after
operator approval.
```

Immediate next work:

```text
1. Make the learner review queue feel complete enough for daily dogfooding.
2. Show why each candidate exists from trace evidence.
3. Prove rejected/deferred candidates do not affect behavior.
4. Decide which schemas should be extracted toward Aeteros Core.
5. Keep RAG/local-router evidence as Research/Product Evidence, not daily
   tuning work.
```

One-line status:

```text
The local-router lab has become a load-bearing Workbench/Core evidence path:
small models are not magically smarter, but Aether can make them more reliable,
inspectable, and reviewable by externalizing cognition into governed trace.
```

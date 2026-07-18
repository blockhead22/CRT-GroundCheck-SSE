# Aether / Aeteros Master Plan - 2026-06-26

> **Current-roadmap notice (2026-07-16):** This document remains authoritative
> for the product thesis and layer split. Current sequencing, completion state,
> milestone gates, and side-lane disposition are consolidated in
> [AETHER_UNIFIED_ROADMAP_2026-07-16.md](AETHER_UNIFIED_ROADMAP_2026-07-16.md).

Purpose: define the product, the split, and the roadmap re-entry after the
Lumi/CRT archaeology pass.

## Product Thesis

The first product is Aether Workbench:

```text
A local-first governed-memory assistant for high-context work.
```

Shorter:

```text
AI memory with receipts.
```

Aether is not primarily a model. It is the governance layer around models:
memory review, provenance, contradiction handling, route visibility, trace,
context compression, and reviewed learning.

## Build Strategy

Build Aether for Nick first, with the explicit intent to extract the reusable
product core later.

```text
Aether-for-Nick = proof loop + daily tool + stress test
Aeteros Core = reusable governed-memory machinery extracted from the proof loop
Product Aether = Aeteros Core + user-owned memory layer + polished Workbench
```

Rule:

```text
Personalize the content. Generalize the mechanism.
```

Examples:

- "Nick prefers blunt warmth and low-key spiral mode" is Nick Layer.
- "Users can approve support-style guidance extracted from archives" is product.
- "Nick is building Aeteros and has specific folders/projects" is Nick Layer.
- "Project memory has provenance, volatility, confidence, and review state" is
  product.
- "Nick's GPT archive is a private source" is Nick Layer.
- "Archives become candidate memories/support patterns, never automatic truth"
  is product.

## Layer Split

Use four labels everywhere:

- Nick Layer: Nick's archive, projects, preferences, private memory, support
  style, and life/work context.
- Workbench: the local app and sidecar where Aether is dogfooded.
- Aeteros Core: reusable governed-memory, trace, routing, contradiction,
  review, compression, and eval primitives.
- Research/Product Evidence: baselines, traces, evals, demos, benchmarks, grant
  evidence, and product proof.

The product emerges when the Nick Layer can be removed and the rest still works.

## What Carries Forward From Lumi / CRT

Carry forward:

- continuity as the product contract;
- Mirus/Holden as belief-intake versus speech-reconstruction;
- contradiction dispositions;
- memory as a region with source, confidence, trust, volatility, and authority;
- trace/collapse trails as evidence;
- fallback quarantine;
- route/model telemetry;
- depth and continuation as engineered behavior;
- reviewed learner heartbeat.

Do not carry forward raw:

- automatic memory mutation;
- hidden anchor reinjection;
- self-awareness or feeling claims;
- fallback output as trusted memory;
- autonomous `promote_to_truth`;
- hardcoded Nick assumptions in reusable core;
- arbitrary file-compression claims;
- old all-in-one Lumi/CRT shells.

## Split Timing

Language split: now.

Every new feature, eval, memory, import, route behavior, and model policy should
be tagged by layer.

Code split: after the Phase 2 review heartbeat is real in Workbench.

Minimum before extraction:

- consolidation candidates exist;
- Workbench can review, apply, defer, and reject them;
- traces explain why each candidate was proposed;
- Memory, Support, Reflection, and Contradiction candidates share one review
  pattern.

Legal/company split: later.

Do not form or position Aeteros around private Nick memory. Consider formal
company/grant steps when there is:

- a reusable Aeteros Core demo;
- eval evidence versus prompt-only/retrieval-only/summary baselines;
- a clean product/research deck;
- a grant, pilot, collaborator, or customer target that needs an entity.

## Roadmap Re-Entry

Phase 1.10 route/model selection can pause as observational unless Nick chooses
to add a manual "try recommended model" gate.

2026-06-29 update: the local-router/meaning-compression lab is now a roadmap
bridge, not a side quest. It should continue only as validation infrastructure
for Aether/Core:

```text
classify request
-> retrieve / build Mirus packet
-> choose model + scaffold
-> render
-> verify with CRT gates
-> repair/fallback
-> persist durable trace
-> create review-only learning candidates
```

The durable trace requirement is now product-relevant. Aether should preserve
structured thinking/process traces for current and historical messages so a
restarted system can show what it remembered, inferred, refused to claim,
repaired, and flagged for possible learning.

This should become a first-class Workbench UI affordance, similar to an
expandable Activity / Thinking drawer on each assistant answer:

```text
Thinking / Process
Memory checked
Tools considered or used
Verifier and repair/fallback
Learning candidates
```

This is not private hidden scratchpad storage as durable truth. It is an
inspectable audit object plus optional public model-authored rationale lines
generated specifically for display and checked against the governance trace.

Current lab evidence:

```text
Raw local answers:     0/12 pass, avg 0.405
Routed local answers: 10/12 pass, avg 0.761
Average lift:         +0.356
```

Treat this as preliminary evidence until a curated 30-50 case replay pack
confirms the lift.

The active build lane should move to Phase 2 while carrying the router/trace
lab forward:

```text
reviewed learner heartbeat
  -> recent traces/turns
  -> proposed memory/support/contradiction/reflection candidates
  -> Workbench review
  -> durable guidance only after approval
```

Next product-critical work:

1. Make learner candidates visible and reviewable in Workbench.
2. Unify Memory, Support, Reflection, and Contradiction review affordances.
3. Make trace evidence explain why each candidate exists.
4. Add answer-level expandable Thinking/Process trace UI for current and
   historical messages.
5. Add evals proving rejected candidates do not affect behavior.
6. Start extracting shared schemas into an Aeteros Core boundary inside the
   current repo, without a separate repo yet.
7. Add durable structured trace JSON to the local router CLI.
8. Extend replay evals to grade trace quality as well as answer quality.
9. Prove answer + trace reload after restart before wiring the lab router into
   Workbench UI.

## Endgame Direction

Aether:

```text
The dogfooded assistant and eventual user-facing product.
```

Aether Workbench:

```text
The local proof environment for governed memory.
```

Aeteros Core:

```text
Reusable governed-memory infrastructure for AI agents.
```

Aeteros:

```text
The possible company/research container around Aeteros Core.
```

Grant/product framing:

```text
Aeteros develops local-first governed memory, trace, and evaluation systems for
AI agents that need reliable long-term context without opaque or unsafe memory.
```

The near-term job is not to make the system more mystical. It is to make the
review loop sturdy enough that memory can become useful without becoming
uncontrolled.

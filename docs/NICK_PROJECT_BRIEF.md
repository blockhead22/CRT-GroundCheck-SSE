# Aether / Aeteros - Plain-English Brief

## The One-Sentence Version

Aether is a local AI workbench that gives AI memory receipts: what it knows, where it came from, how confident it is, and what conflicts with it.

## The Simple Version

Most AI assistants sound continuous, but they are not actually continuous. They forget prior sessions, flatten context, and sometimes give opposite advice with the same confidence.

Aether is built around the idea that memory should not be a pile of saved facts. It should be governed.

That means every important memory should have:

- a source;
- a confidence level;
- a trust level;
- a review state;
- a contradiction history;
- a reason it was allowed into an answer.

The model is still useful. It writes, explains, reasons, and helps. But the model is the mouth. The memory and governance layer is the part that should persist.

## What Aether Is

Aether Workbench is the dogfooded local app.

It is where Nick uses the system, tests the ideas, reviews memories, catches bad behavior, and turns old research concepts into working product mechanisms.

Current Aether can already:

- answer with governed memory context;
- show trace evidence for why an answer was shaped a certain way;
- preserve contradictions instead of silently overwriting them;
- label conflicts as resolvable, held, evolving, contextual, stale, or policy-bound;
- use reviewed support/reflection guidance without treating it as confirmed fact;
- keep model-routing recommendations visible without silently switching models;
- run evals that compare raw context, summaries, scaffolds, and compressed memory representations.

## What Aeteros Is

Aeteros is the possible company or research wrapper.

Aeteros Core is the reusable part we eventually extract from Aether:

- governed memory;
- contradiction handling;
- trace and review flows;
- route/model policy;
- context compression;
- eval harnesses.

The rule is:

```text
Personalize the content. Generalize the mechanism.
```

Nick's private memories are not the product. The product is the machinery that lets a user own, review, correct, and trust their AI memory over time.

## The Real Thesis

The project is not "AI with memory."

The project is:

```text
AI memory needs governance before it becomes safe or useful.
```

Without governance, memory can make things worse. It can preserve hallucinations, overwrite real facts, retrieve stale context, or make a model sound certain when the evidence is weak.

Aether tries to fix that by making memory reviewable and auditable.

## The Coolest Core Idea

Contradictions are not automatically bugs.

Sometimes a contradiction means the user changed. Sometimes the context changed. Sometimes an old fact is stale. Sometimes the model guessed. Sometimes both sides are true in different situations.

Aether should not erase that tension. It should preserve it, label it, show the evidence, and ask for review when needed.

## What Is Actually Strong Right Now

The strongest current evidence is not that Aether has solved all memory.

The strongest evidence is that structured memory and scaffolding can make smaller/local models behave more reliably than raw retrieval or prompt-only approaches.

The representation replay results are especially important:

- governed scaffold: 19/19;
- CRT compressed state: 19/19;
- slot-only and raw retrieval: much weaker;
- naive summary: weakest.

That supports the practical product claim:

```text
The shape of the context matters.
```

## What Still Needs Proof

The project should be honest about open work:

- contradiction detection is not complete for all natural language;
- archive import must stay review-first;
- external validation is still needed;
- public claims need tighter evidence links;
- Aether is still a proof loop, not polished product packaging;
- automatic model switching should stay off until eval evidence is stronger.

## The Roadmap Right Now

Phase 1.10 route/model policy can pause as observational.

The next real work is Phase 2:

```text
reviewed learner heartbeat
```

That means recent turns and traces should create reviewable candidates:

- memory candidates;
- support-style candidates;
- reflection candidates;
- contradiction-review candidates;
- Aether self-improvement candidates.

Nothing should become durable memory or behavior until Nick reviews it.

## How To Describe It To People

Short:

```text
I am building AI memory with receipts.
```

Slightly longer:

```text
Aether is a local-first AI workbench for governed memory. It helps an assistant remember across time without silently overwriting contradictions or treating generated text as truth.
```

Business/research:

```text
Aeteros builds governed memory infrastructure for AI agents: source-aware memory, contradiction tracking, review workflows, traceability, and evals for long-term reliability.
```

Plain human:

```text
I am trying to make AI that can remember responsibly.
```

## The North Star

Do not make the system more mystical.

Make it more reviewable, more honest, more useful, and harder to fool.


# Aeteros / Aether Layer Split - 2026-06-25

This document exists to keep the project understandable to future Nick, future
agents, and possible collaborators.

The current work can look confusing because it is simultaneously:

- Nick's personal AI assistant;
- a local Workbench product prototype;
- a research system for governed memory;
- a possible Aeteros business/grant platform.

The way to keep that sane is not to pick only one. The way is to label the
layers clearly.

## Short Version

```text
Aether        = Nick's dogfooded local assistant / proof loop.
Aether Workbench = the app and sidecar where the proof loop runs.
Aeteros Core  = reusable governed-memory primitives extracted from Aether.
Aeteros       = the possible company/research container around the general core.
Nick Layer    = personal facts, archive, projects, tone, support style.
Evidence Layer = evals, baselines, traces, and research/product proof.
```

Permanent design rule:

```text
Every new feature, memory, eval, archive import, support pattern, route behavior,
or model policy must be labeled as Nick Layer, Workbench, Aeteros Core, or
Research/Product Evidence.
```

## Mission

Make AI memory trustworthy over time.

In practical terms, this means an assistant should be able to preserve useful
context, admit uncertainty, handle contradiction, remember with review, expose
why it answered, and improve across model changes without silently turning
temporary context or another assistant's interpretation into permanent truth.

## Aether

Aether is the dogfood system.

It is allowed to be personal, messy, emotionally textured, and tuned to Nick's
actual usage. That is the point. Nick stress-tests the system with real
longitudinal use:

- project planning and doubt;
- long context and deep/spiral requests;
- local model switching;
- code and workspace questions;
- GPT archive import;
- memory correction and contradiction;
- support style and tone calibration;
- business/research framing;
- ordinary re-entry after distractions or life interruptions.

Aether is not the general product by itself. It is the proof loop where the
requirements become real.

## Aether Workbench

Aether Workbench is the local app and sidecar that make the proof loop usable.

Current Workbench responsibilities:

- local chat through Ollama;
- governed memory release;
- trace-visible routing;
- depth/continuation;
- contradiction disposition;
- support-pattern review;
- reflection review;
- learner candidate preview;
- archive import/replay;
- code-context tools;
- route/model evals.

Workbench should stay practical. It is not the business entity, and it should
not become a sprawling legacy frontend/API revival.

## Nick Layer

The Nick Layer is personal and should remain separable from the reusable core.

Examples:

- Nick's name, projects, LLC/Aeteros context, print shop context, and working
  environment;
- Nick's tone preferences: laid back, concise, sometimes blunt, warm, playful,
  not fake-intimate, not generic;
- archive-derived support stance from Nick's GPT history;
- Nick-specific phrases such as courtroom/grace/re-entry/dork spiral;
- private personal history, health context, motivation patterns, and current
  life/work context;
- personal memory facts and support preferences.

Nick Layer material can inspire core requirements, but it should not be treated
as the product surface for other users.

Rule:

```text
Nick Layer can be highly personalized. Aeteros Core cannot depend on Nick being
the user.
```

## Aeteros Core

Aeteros Core is the reusable governed-memory substrate extracted from Aether.

Core primitives:

- memory review gates;
- source authority and provenance;
- user-authored fact separation;
- assistant interpretation separation;
- support-pattern separation;
- contradiction disposition;
- stale/evolving/contextual fact handling;
- confidence and uncertainty boundaries;
- imported-chat provenance;
- trace-visible route decisions;
- local model evals by route;
- representation replay / meaning compression evals;
- context budget control;
- deterministic meta/governance answers;
- no-silent-write policy;
- no-silent-frontier-escalation policy.

These are the grant/product candidates.

If a feature works for Nick only because it knows Nick's archive, language, or
projects, it is not Aeteros Core yet. If the mechanism would help any user bring
their own archive, memory, contradictions, and preferences into a governed local
assistant, it may belong in Aeteros Core.

## Evidence Layer

The Evidence Layer turns the personal proof loop into research/product proof.

Evidence should include:

- baseline comparisons:
  - prompt-only;
  - retrieval-only;
  - naive summary;
  - raw local model;
  - governed scaffold;
  - CRT compressed state;
- held-out prompts;
- synthetic users;
- eventually volunteer users;
- route/model sweep results;
- failure-mode logs;
- latency and context-size measurements;
- trace examples showing memory used, withheld, contradicted, or reviewed.

The research question:

```text
Can governed memory, contradiction disposition, trace-visible routing, and
eval-driven local model selection improve agent reliability beyond prompt-only,
retrieval-only, and naive-summary baselines?
```

## Aeteros

Aeteros is the possible company/research container around the general core.

Business formation, legal structure, accounting, and registration remain
outside this technical roadmap until Nick decides to handle them separately.
This document only preserves the technical/product/research framing.

Suggested mission statement:

```text
Aeteros builds governed memory infrastructure for trustworthy AI agents.
```

Suggested tagline:

```text
AI driven by meaning.
```

Sharper variant:

```text
Aeteros: AI memory driven by meaning.
```

Grant/product framing:

```text
Aeteros develops local-first governed memory, trace, and evaluation systems for
AI agents that need reliable long-term context without opaque or unsafe memory.
```

## Layer Labels

Use these labels in roadmap docs, eval notes, and future implementation plans.

### Nick Layer

Personal data, personal support style, personal archive, personal project
context, private life/work details.

### Workbench

The local app/sidecar implementation used to dogfood and test Aether.

### Aeteros Core

General reusable memory-governance, routing, trace, provenance, contradiction,
compression, and eval primitives.

### Research/Product Evidence

Baselines, held-out tests, synthetic/volunteer user tests, grant evidence,
product-positioning evidence, and measured reliability deltas.

## Decision Checklist

Before adding or promoting a feature, ask:

1. Is this Nick-specific content, or a reusable mechanism?
2. Does it create confirmed memory, proposed memory, support guidance, or a
   reflection?
3. Is the source user-authored, assistant-authored, inferred, imported, or
   generated?
4. Can the behavior be tested outside Nick's archive?
5. Does this improve reliability compared with prompt-only, retrieval-only, or
   naive-summary baselines?
6. Is the result trace-visible?
7. Does it preserve no-silent-write and no-silent-escalation boundaries?

## Near-Term Roadmap Insert

Add a Phase 1.11 layer-split discipline:

```text
Phase 1.11 - Aether / Aeteros Layer Split

Goal:
Prevent the system from becoming either too Nick-specific to generalize or too
generic to remain useful.

Implementation:
- label new features and evals by layer;
- keep Nick support/profile material in the Nick Layer;
- extract general mechanisms into Aeteros Core;
- expand non-Nick synthetic and held-out evals;
- preserve grant/product evidence in docs and eval reports.
```

This phase does not block Phase 1.10. It is an organizing rule that should run
alongside route/model selection, archive import, and future learner work.

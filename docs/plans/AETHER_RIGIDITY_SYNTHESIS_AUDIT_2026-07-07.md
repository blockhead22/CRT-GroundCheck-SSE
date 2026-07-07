# Aether Rigidity / Generative Synthesis Audit - 2026-07-07

## Why This Audit Exists

Live Workbench dogfooding has exposed a real product flaw:

```text
Aether is safer than raw local chat in many cases, but too many fixes are
currently implemented as deterministic final answers. That prevents some
hallucinations, but it can make Aether feel like regex plus canned cards rather
than a governed system that can synthesize from known evidence.
```

The CRT/CORE question is the clearest example. The deterministic patch stopped
the local model from inventing `CRT = Comprehensive Research and Technology`,
which was necessary. But the current response is still essentially a routed
fixed answer. It protects epistemic integrity while hurting aliveness and
semantic synthesis.

## Honest Current State

The system has meaningful pieces:

- governed memory slots with confirmed/conflicted/historical/quarantined states;
- document/archive search with source boundaries;
- semantic tool routing for project/code/search tasks;
- Mirus review-only candidate creation;
- route policy, verifier/repair/fallback paths;
- Thinking / Process trace UI;
- regression packs for live dogfood failures.

But the composition layer is immature.

The sidecar often does this:

```text
match prompt shape -> select deterministic answer -> return final prose
```

What Aether should increasingly do is:

```text
classify intent -> retrieve evidence -> build governed answer spine ->
render through model or deterministic prose depending on risk ->
verify against spine -> repair/fallback -> show trace
```

The first path is safer but stiff. The second path is the actual Aether thesis.

## Where Deterministic Final Answers Are Appropriate

Keep deterministic final answers for narrow, high-authority, low-style cases:

- confirmed memory lookup: favorite color, favorite flower, employer;
- explicit memory write acknowledgement;
- unresolved memory boundary: "I do not have this confirmed yet";
- unsafe/current-event boundary: no live news/sports validation;
- exact tool receipt: workspace file found, map command emitted, test command suggested;
- sensitive archive boundary when source evidence is too weak;
- verifier failure / insufficient evidence response.

These should be crisp, not performative.

## Where Current Behavior Is Too Rigid

These should not stay as canned final prose long-term:

- CRT / CORE / epistemic integrity architecture explanations;
- "what is Aether's purpose" when the user asks for synthesis across memory,
  color, health, project history, or AI architecture;
- "why does this matter" / "is this system valid" / "what holds me back";
- archive theme summaries after document_search;
- state-parks project explanations such as "why does Mill Bluff matter";
- personality/voice answers;
- project/business/grant synthesis;
- any prompt where the user is asking for relationship between two or more
  facts, not a single fact recall.

These need governed synthesis, not a fixed card.

## Proposed Product Rule

```text
Governance may be deterministic. Final language should be generative when the
task asks for synthesis, unless risk is high or evidence is insufficient.
```

In other words:

- Mirus owns evidence, slots, candidate facts, source boundaries, and answer
  spine.
- Holden/model renders the human-facing answer from that spine.
- CRT verifies that the rendered answer did not invent, overclaim, leak, or
  collapse uncertainty.
- Workbench shows the trace.

## Near-Term Implementation Direction

### 1. Add a route outcome distinction

Current trace often says `generation_model=deterministic`.

Add clearer render modes:

```text
deterministic_final
governed_spine_model_render
governed_spine_deterministic_fallback
tool_receipt_final
insufficient_evidence_final
```

This makes canned behavior visible and auditable.

### 2. Convert canned concept answers into answer spines

Example: CRT question should build a structured spine:

```text
Intent: explain epistemic integrity + CRT implementation.
Evidence:
- aether.crt is math/volatility/trust/contradiction layer.
- aether.integrations.crt bridges older CRT facts.
- sidecar governance uses route policy, context bridge, substrate, Mirus,
  verifier, repair/fallback, trace receipts.
Forbidden:
- do not invent acronym expansions.
- do not claim CRT is one module or one prompt.
Answer arc:
- define epistemic integrity.
- map CRT/CORE to current architecture.
- name what is implemented vs still aspirational.
- close with why this matters for small models.
```

Then let the model render from that spine, with repair if it violates the
forbidden list.

### 3. Add a "cannedness" quality check

Hard dogfood should grade:

- did the answer answer only one fact from a compound prompt?
- did it return the same paragraph for different but related questions?
- did it fail to connect available evidence?
- did it sound like a policy card instead of Aether?
- did it claim tool/search/memory behavior that did not happen?

This should become a real quality dimension beside correctness/governance.

### 4. Prefer synthesis for multi-fact prompts

If a prompt contains more than one anchor, e.g.

```text
purpose + favorite color
CRT + architecture
state parks + Mill Bluff
GPT logs + what holds me back
favorite flower + why
```

the system should avoid single-slot direct answer mode unless the user only
asked for lookup.

### 5. Keep deterministic safety boundaries

Do not remove the guardrails. The right fix is not "let Qwen freewheel."

The fix is:

```text
deterministic contract, generative rendering, deterministic verification.
```

## What This Means For The Roadmap

This is not a side quest. This is the next product-critical Aether issue.

The local-router/RAG labs proved that governed structure helps. The Workbench
dogfood now shows the next ceiling: if governance only blocks failures by
returning fixed text, Aether becomes safer but not deeply useful.

The next roadmap lane should be:

```text
Governed Synthesis Layer
```

Its purpose:

- turn deterministic final answers into governed answer spines where possible;
- let a small/local model render from verified source packets;
- repair/fallback when rendering drifts;
- show the whole process in the Thinking drawer;
- preserve safety boundaries without making the assistant feel canned.

## Stop Condition For This Lane

The lane is successful when a small dogfood pack passes cases where Aether must
connect multiple facts without hallucinating or falling back to fixed-card prose:

- CRT / epistemic integrity / implementation;
- Aether purpose + favorite color + AI relevance;
- favorite flower + orange + leukemia-awareness boundary;
- state parks project + Mill Bluff importance;
- GPT/archive "what holds me back" + follow-up continuity;
- code/search prompt with exact file evidence;
- sensitive archive medical-history source-bound summary.

Passing means:

- correct facts and source boundaries;
- no invented acronym expansions;
- no confirmed-memory mutation unless explicit;
- no generic local-model ramble;
- no obvious canned duplicate answer;
- readable formatting and Aether-like voice.


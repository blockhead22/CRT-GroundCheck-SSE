---
name: theory_persistence_layer
description: Core architectural thesis — the model is the mouth, persistence is the self. Multi-agent governance requires epistemic state that survives model switching. Emerged from variance experiment + GPT dialogue 2026-03-28.
type: project
---

# The Persistence Layer Thesis

**Date: 2026-03-28**
**Source: Nick Block insight during GPT dialogue, building on variance experiment findings**

## The Core Insight

The model is the mouth. The persistent governance layer is the self.

Switching models in an agentic system is not dangerous because models are different. It's dangerous because most systems let the mouth become the self at every step. Every handoff is a tiny identity wipe — new assumptions, new confidence levels, new failure modes, new hallucination patterns.

## The Requirement

Do not switch models or agents without switching a stable epistemic control state along with them.

Three things must persist across model handoffs:
1. **Shared task state** — what are we doing, what did the user mean
2. **Shared support/uncertainty state** — what do we know, how well, what's unresolved
3. **Shared governance state** — what rules apply, what's held, what's forbidden

If any of these reset at handoff, the system drifts even when every individual model is "working as designed."

## Why the Variance Experiment Proves This Matters

Four models under the same probe show four distinct fragility regimes:
- Qwen3: selective fracture (cracks hard on some factuals)
- Mistral: selective spread (diffuses on morals, locks on facts)
- DeepSeek: uniform softness (everything moves, nothing locks or cracks)
- GPT-4o-mini: global compression (resists movement even at high temperature)

When an agentic system routes from one model to another, it's not just swapping capability. It's swapping instability style. The same topic that was safely handled by Model A's locked regime might land in Model B's fracture zone. Without governance continuity, nobody catches the transition.

## How This Maps to Mirus/Holden

**Mirus** is not just "encoder." It is the persistence layer — holds meaning, support, contradiction, trust, continuity across model switches.

**Holden** is not "the whole system." It is the expression layer. The mouth. Replaceable. Swappable. Governed.

**Immune agents** watch the boundary — making sure the new mouth doesn't violate the laws the old mouth was obeying.

## The Architecture Consequence

The persistent system is the mind. The active model is the mouth.

This means:
- Stop asking the model to remember, govern, verify, AND speak with equal authority
- Let it do what it's good at: generating language, transforming representations, specialized reasoning
- But the continuity lives somewhere more durable — in the governance layer, the belief state, the fragility map

## The Problem Statement for Multi-Agent Systems

Every multi-model agent system today does "good luck, new brain" at every handoff. The governance resets. The fragility profile changes silently. The uncertainty state evaporates.

The fix: a persistent epistemic control layer that carries task state, support state, and governance state across every model switch. The variance experiment provides the fragility maps that tell this layer what to watch for in each model.

## One Sentence

"The problem is not switching mouths. The problem is losing the self between them."

## How to Apply

- When building agentic pipelines: governance layer must be model-external
- When routing between models: fragility profile of the target model must be known
- When handing off tasks: contradiction state, confidence levels, and unresolved ambiguities must transfer
- The immune agents ARE the enforcement mechanism for this transfer
- The variance probe IS the tool that maps each model's fragility profile in advance

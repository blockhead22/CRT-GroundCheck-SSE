---
name: theory_contradiction_drive
description: Contradiction as motivation - proto-AGI sub-problem. Heartbeat that acts on tension, not just observes it. Closes gaps toward autonomous epistemic behavior.
type: project
---

# Contradiction as Drive — Active Heartbeat Design

**Context:** April 9, 2026. End of a massive session (backprop, wobble, compression, SSE revival, Experiment A/B, trust-weighted fine-tuning). Nick asked: "contradiction as drive — what closes our gaps? Is this a heartbeat pass?"

## The Idea

The existing heartbeat is passive: observe system state, log self-model, update execution beliefs. A contradiction-driven heartbeat would be active: measure tension in the belief graph and ACT on it between conversations.

## What "Drive" Means Here

Not human motivation. Measurable graph tension that implies action.

- Open contradictions = unresolved tension
- High domain volatility = unstable knowledge area
- Stale high-trust memories never re-verified = assumed confidence
- Self-model beliefs diverging from execution data = self-deception
- Wobble patterns that repeatedly co-activate unconnected nodes = missing edges

Each of these is a signal the heartbeat can measure and a threshold that triggers action.

## The Active Heartbeat Loop

```
Every N minutes (idle time between conversations):

1. MEASURE TENSION
   - Count open contradictions per domain
   - Compute domain volatility scores
   - Identify stale beliefs (high trust, low recent access)
   - Check self-model vs execution reality gap
   - Track wobble co-activation patterns for edge discovery

2. PRIORITIZE
   - Rank domains by: contradiction_count * volatility * recency
   - This is NOT random — the graph tells you where attention is needed
   - High-pressure domains float to the top
   - This IS motivation derived from the belief state

3. ACT (graduated)
   Level 1: Queue reflection task (async, background)
     "Re-evaluate the employment contradiction — trust scores diverged"
   
   Level 2: Prepare clarification question for next conversation
     "Next time Nick mentions work, ask about the design studio"
   
   Level 3: Flag for detraining
     "This belief has been contradicted 3x, mark for adapter removal"
   
   Level 4: Flag for training promotion
     "This belief cluster has been stable 30+ days, promote to adapter"

4. LOG
   - What tension was measured
   - What action was taken
   - What the state was before/after
   - This IS the self-model updating from its own behavior
```

## What This Closes

| AGI Gap | How Heartbeat Addresses It |
|---------|---------------------------|
| Motivation | Contradiction pressure IS the drive. Not "wants to." "The graph says." |
| Goal derivation | High-pressure domains become implicit goals |
| Persistence of intent | Queued actions survive session boundaries |
| Autonomous planning | Graduated action levels = multi-step planning about own state |
| Self-awareness | Self-model beliefs are nodes being measured in the same pass |

## What This Doesn't Close

- World model (the system reasons about user beliefs, not world knowledge)
- Novel reasoning (the system corrects, it doesn't discover)
- Transfer (what it learns about one user doesn't generalize)

## Connection to Existing Architecture

- Heartbeat loop: already exists (`heartbeat_loop.py`), currently passive
- Reflection queue: existed in 2025 (`self_reflect.py`), was dropped, needs revival
- Domain volatility: validated tonight in backprop labs
- Backward influence: validated tonight, fires on correction
- Wobble co-activation: validated tonight, could drive edge discovery
- Fidelity mirror: post-generation check, could feed tension measurement
- Training/detraining pipeline: Experiment B in progress, adapter trains from trust scores

## Key Insight from Nick

"Prolonged earned facts that become clusters become beliefs. Beliefs that continually get reinforced get promoted to training. But the system needs to be applied in reverse — if a contradiction becomes strong enough it's a signal that detraining is needed."

Training and detraining from the same graph. Same signal. Different direction. The heartbeat is the clock that measures when each threshold is crossed.

## Implementation Path

1. Add tension measurement to existing heartbeat (passive → measuring)
2. Add graduated action queue (measuring → planning)
3. Wire action queue to next conversation (planning → acting)
4. Wire training/detraining flags to adapter pipeline (acting → evolving)
5. The model evolves between conversations through earned tension

## Status

Design note. Not scoped. Not implemented. Next session should prototype the tension measurement on production data — how many open contradictions exist, what the domain volatility distribution looks like, what a "tension score" would produce if computed right now.

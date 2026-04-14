# Theory: Epistemic Intent Routing — CRT Applied to Agent Decision-Making

**Date**: 2026-03-30
**Status**: Conceptual, Layer 1 (measurement) shipped

## The Core Idea

Intent routing shouldn't be a classifier. It should be a belief system.

Current agent frameworks: message → classifier → route → execute. The classifier is a dumb model (GPT-4o-mini, llama3.2) that guesses what the user wants. It's wrong 30% of the time. There's no learning, no memory, no earned trust.

CRT approach: message → **epistemic evaluation** → route → execute → **measure outcome** → update beliefs. The routing decision is a belief with a trust score. It earns trust through evidence, same as "Nick's favorite color is orange" earns trust through consistency.

## What This Means Concretely

After 100 orchestrator runs, the system has beliefs like:

- "Messages containing file paths → need tools, trust 0.95" (95 out of 100 succeeded with tools)
- "Messages under 10 words with '?' → direct response, trust 0.82"
- "Messages mentioning 'write' + 'function' → multi-step, avg 4.2 tools, trust 0.88"
- "Messages starting with 'Aether,' → LOOKS conversational but 30% actually need tools — routing trust only 0.70"

That last one is critical. The system learns that its own classification is unreliable for certain patterns. The epistemic weight on the routing decision tells the system: "I'm not sure about this one — maybe ask before assuming."

## Prediction, Not Just Classification

With enough data, the system can predict:
- Which **tool sequence** will succeed for this type of request
- Whether it needs to **verify** its work (earned from failure data)
- How many **iterations** this will take (calibrated from similar past runs)
- Whether it will **drift** (some task types have high drift rates)

This is the agent equivalent of the cascade paper's convergence theorem — but applied to execution patterns instead of belief propagation. Do certain task types "converge" (reach stable completion) or "diverge" (drift and fail)?

## The Belief/Speech Gap for Agents

The variance probe from the Qwen3/Mistral experiments applies here too:
- Agent says "done, confidence 0.9" → but actual success rate at 0.9 confidence is only 0.65
- That's a belief/speech gap: the agent CLAIMS confidence it hasn't EARNED
- CRT catches this: "Your stated confidence is 0.9 but your track record at that level is 0.65. Adjusting displayed confidence."

Nick called this the "calibration" metric. It's literally the same measurement we already do for memory beliefs, applied to agent self-assessment.

## Why This Is Different From Fine-Tuning

Fine-tuning: train the model on task data → model internally learns patterns → black box
CRT routing: observe outcomes → store as explicit beliefs → transparent, auditable, editable

You can ASK the system "why did you choose to use tools here?" and it can point to specific evidence: "In my last 47 runs with this message pattern, tools were needed 89% of the time. Here are the 5 most similar past runs."

The beliefs are in the database. You can correct them. You can inspect them. You can watch them evolve. No retraining needed.

## Connection to Existing CRT Concepts

| CRT Concept | Memory Application | Agent Application |
|---|---|---|
| Trust scores | How reliable is this fact? | How reliable is this routing decision? |
| Contradiction detection | Fact A conflicts with fact B | Step 3 contradicts step 1's assumption |
| Held contradictions | Preserve tension, don't auto-resolve | Some tasks legitimately need divergent approaches |
| Cascade propagation | Revising fact A affects dependent facts | Failing step 2 affects all downstream steps |
| Belief/speech gap | Agent says X but evidence shows Y | Agent claims 90% confidence but succeeds 65% |
| Provisional authority | New facts start unverified | New routing patterns start at low trust |
| Verification | Memory confirmed through consistency | Task verified through execution |

## Nick's Intuition

"Is this intent routing training based on heuristic weighting of the epistemic value?"

Yes. Exactly. The heuristic weight IS the epistemic value. They're the same thing. The system doesn't have separate "heuristics" and "beliefs" — the heuristics ARE beliefs, earned through evidence, stored with trust scores, subject to contradiction and revision.

"We can possibly predict the route? Maybe predict the logic?"

Yes. With enough run data, the system predicts not just WHICH route to take, but WHAT STEPS to take within that route, based on earned patterns from similar past runs. The "logic" is emergent from accumulated epistemic weight, not programmed.

## What's Built So Far

- [x] Run log captures every orchestrator execution (Layer 1)
- [x] Analytics: success rate, drift, verification, calibration
- [ ] Pre-step alignment checking (Layer 2)
- [ ] Post-step contradiction detection (Layer 3)
- [ ] Belief-weighted routing from run data (Layer 4)
- [ ] Self-model beliefs about execution patterns (Layer 5)

## Nick's Direction

"Don't split chat and coding. Cookie is the brain for everything. The system learns from what works."

The architecture is: one smart brain (Cookie/Opus), one persistence layer (CRT), one measurement layer (run log). The brain is swappable. The persistence is the self. The measurement is how the self learns.

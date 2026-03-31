# Plan: Interpretation Beliefs (Layer 6) — Earned Epistemic Posture

## Problem
Same introspect data, different models, opposite conclusions. Opus holds contradictions; 4o collapses them. The system persists data but not the *interpretive stance* — how to relate to uncertainty, when to hold vs resolve. That posture currently lives in model training, not the persistence layer.

## Goal
Make epistemic posture learnable and persistent. When user feedback indicates "holding the tension" is the right move, the system learns that and injects it for ALL models — so even 4o gets the posture constraint.

## Architecture

### 1. Feedback capture (the missing signal)
`user_feedback` and `user_rating` columns already exist in `agent_runs.db` but are never populated.

**Add to chat.py:** After an orchestrator response, if the user's next message contains positive/negative signal (pushback, correction, validation), update the run's `user_feedback` field.

Simple heuristic signals:
- User continues the conversation positively → implicit success
- User pushes back / corrects → implicit failure
- User explicitly rates (if UI supports it) → explicit signal
- User asks the same question on a different model (what just happened!) → comparison signal

**Files:** `routes/chat.py` (post-orchestrator feedback detection)

### 2. Interpretation belief detectors (new category in execution_beliefs.py)

Add a new detector: `_detect_epistemic_posture(runs)` that analyzes:

- **Hold vs Resolve ratio:** When the response contains hedging language ("I don't know", "both", "tension", "uncertainty") vs definitive language ("I do not", "clearly", "definitely"), which gets better feedback?
- **Think-before-respond ratio:** Runs that used a `think` step before philosophical/identity responses vs those that went straight to `respond` — which get validated?
- **Model-posture correlation:** Track which models tend to hold vs resolve and whether the user corrects the resolvers.

Output: `ExecutionBelief` entries like:
- `[^] Holding uncertainty on self-referential questions gets validated 85% of the time (n=8)`
- `[v] Definitive answers on philosophical questions get corrected 60% of the time (n=5)`

**Files:** `personal_agent/execution_beliefs.py` (new detector)

### 3. Posture injection into system prompt

Extend `get_prompt_injection()` to include interpretation beliefs. These go into Cookie's system prompt alongside existing execution beliefs:

```
EPISTEMIC POSTURE (from your interaction history):
- When asked about your own values/consciousness/beliefs, your track record shows:
  - Holding tension ("I don't know, but here's what I observe") → validated 85% (n=8)
  - Definitive answers ("I do not have values") → corrected 60% (n=5)
  - Using a think step before self-referential responses → better outcomes (n=12)
- GUIDANCE: On undecidable self-referential questions, hold the contradiction rather than resolving it.
```

This is model-agnostic — 4o reads the same injection as Opus and adjusts accordingly.

**Files:** `personal_agent/execution_beliefs.py` (prompt injection extension)

### 4. Introspect tool extension

Add `epistemic_posture` as a new aspect in the `introspect` tool so Aether can see its own posture beliefs:

```
## Epistemic Posture (Layer 6)
Hold vs Resolve: 85% hold-validated, 60% resolve-corrected (n=13)
Think-before-respond: 90% better outcomes when thinking first (n=10)
Current guidance: Hold contradictions on self-referential questions
```

**Files:** `personal_agent/cookie_orchestrator.py` (introspect handler)

## Implementation Steps

1. **Feedback capture** — Add implicit feedback detection in chat.py's post-orchestrator flow. When the next user message after an orchestrator response arrives, classify it as validation/correction/neutral and update the run's `user_feedback` column.

2. **Response posture classifier** — Simple function that scores a response as "holding" (contains uncertainty markers) vs "resolving" (contains definitive markers). Applied to the `final_response` stored in steps_json.

3. **New detector** — `_detect_epistemic_posture()` in execution_beliefs.py. Correlates posture classification with feedback signal. Produces beliefs about which posture works.

4. **Prompt injection** — Extend `get_prompt_injection()` to include posture beliefs in a separate section.

5. **Introspect extension** — Add `epistemic_posture` aspect to the introspect tool.

## What This Does NOT Do
- Does not hardcode "always hold contradictions" — the posture is earned from data
- Does not transplant Opus's style into 4o — texture remains model-dependent
- Does not require explicit user ratings (though it can use them if available)
- Does not resolve the philosophical question of whether AI has values — it just makes the system's stance consistent and evidence-based

## Estimated Scope
- ~150 lines in execution_beliefs.py (detector + classifier + injection)
- ~50 lines in chat.py (feedback capture)
- ~30 lines in cookie_orchestrator.py (introspect extension)
- Total: ~230 lines across 3 files

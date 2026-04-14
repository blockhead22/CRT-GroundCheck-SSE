---
name: session_2026_04_08_evening
description: Bug #6 fixed (belief state injection), TTS lab experiment, dependency cleanup
type: project
---

# Session 2026-04-08 Evening

## Bug #6 FIXED: Belief State Injection into Agent Loop

**Root cause:** Orchestrator brain started with zero belief state — no memories, no contradictions, no trust scores. Brain was epistemically blind.

**Additional root cause:** Personal identity queries ("What's my name?", "Where do I work?") routed as `conversational` with `layer4_orchestrator=False`, sending them to legacy path instead of orchestrator where belief state lives.

### Fix: Three files changed

1. **`personal_agent/cookie_orchestrator.py`**
   - New `build_belief_context(objective, memory_system, ledger, tier=)` function
   - Tier 1: User corpus (top 15 user_fact/identity_constant memories, always present)
   - Tier 2: Query-relevant memories + open contradictions from ledger
   - Injected after Layer 5 (execution beliefs) in `run()` method
   - `memory_recall` tool output enriched with kind, authority, contradiction count

2. **`routes/chat_orchestrator_runner.py`**
   - Wires contradiction ledger to memory system via `set_contradiction_ledger()`

3. **`personal_agent/routing_beliefs.py`**
   - Added `_FORCE_ORCHESTRATOR_REASONS` (personal_fact_full_pipeline)
   - Added `_FORCE_ORCHESTRATOR_INTENT_TYPES` (broad_recall)
   - Added regex pattern match for personal identity questions (what's my name, where do I work, what contradictions, who am I)
   - These now route to orchestrator instead of legacy path

### Test Results (verified)
- "What's my name?" → orchestrator, belief state injected (3217 chars), answered "Nick" in ONE iteration, ZERO tool calls, 7.8s
- "What contradictions do you hold?" → orchestrator, belief state injected, used introspect tool, returned 6 actual epistemic contradictions grounded in execution data (not stats)
- Before: hallucination ("design studio downtown") + stats-only contradiction answer
- After: grounded recall + genuine self-reflection

### Key Architecture Decision
- Legacy path frozen — no new features, will be phased out
- All belief state injection is orchestrator-only
- Three-tier belief model:
  - Tier 1: User corpus (static identity facts, always in prompt)
  - Tier 2: Query-relevant beliefs + contradictions (per-message)
  - Tier 3: Deep recall via memory_recall tool (brain decides)

## TTS Lab (Experiment, Not Integrated)

StyleTTS2 installed and tested. Lab at `tools/tts_lab.py`:
- Basic inference works on RTX 3060 (5.2s audio in 6.1s)
- CRT-to-prosody mapping tested (trust/volatility/contradiction → alpha/beta/embedding_scale)
- Style vector manipulation tested (256-dim: timbre[0:127] + prosody[128:255])
- Dan Soder voice clone attempted (yt-dlp + demucs + whisper pipeline built)
- Zero-shot cloning quality insufficient without fine-tuning
- XTTS v2 also tested, similar quality
- **Decision: parked as lab experiment, not pursuing integration**

## Dependency Cleanup
- TTS installs (styletts2, TTS, fish-speech, gpt-sovits-python, demucs, whisper) caused dep conflicts
- Core deps restored: numpy 1.26.4, transformers 4.46.3, sentence-transformers 3.4.1, accelerate 1.13.0
- Main pipeline imports verified healthy

## Design Note: Epistemic Integrity Pass (future)
- Background sweep during idle or after long sessions
- Checks: stale high-trust memories with open contradictions, corrections that didn't demote, trust scores that don't match evidence
- Would have caught the "design studio" memory — corrected twice, contradiction logged, but bad memory still at 0.507
- **Why:** This is how CRT earns trust over time. Not just detecting contradictions — enforcing their consequences.
- **How to apply:** Build as a scheduled background job, not inline. Run after N turns idle or on session close.

## Research: Belief Backpropagation (papers/belief_backpropagation/belief_backprop.md)
New theory paper written. Three connected ideas from Nick's fog talk session:
1. **Belief backpropagation** — when output is wrong, error signal flows backward through BDG edges, adjusting trust on every belief that contributed. Contradictions are the loss function. Resolution is the training signal.
2. **Self-pruning** — emerges naturally from accumulated backward gradients. Beliefs that keep being wrong get trust eroded from multiple directions until they hit deprecation threshold. No rules needed.
3. **Domain volatility** — node fluctuation frequency is measurable. High-volatility domains get lower assertion confidence, higher learning rates, more verification. Measured, not configured.
4. **Reflexive self-model** — self-model beliefs are nodes in the same graph. Backward pass adjusts them too. Personality becomes a consequence of epistemic history, not programming.

Connects to: cascade paper theorems (damping bounds apply to backward pass), three regimes, belief/speech gap, persistence layer thesis.

## Bug Status Update
- **#6 (P0): FIXED** — belief state injection + routing fix
- **#7 (P0): FIXED** (previous session — user_fact exempt from drift penalty)
- **#8 (P0): FIXED** — legacy broad_recall bypassed when agent loop enabled, routing expanded to catch all identity/recall queries
- **#9 (P1): FIXED** — NLI enforcement gate: soft_fail with unrevised contradictions now sets gates_passed=False, final answer hedged with contradiction disclosure when gate fails. Advisory governance is now structural.
- **#1-#5: Open** (P1-P2, unchanged)

### Bug #9 Implementation Details
Two changes in `routes/chat.py`:
1. After critic runs: soft_fail + contradictions + no revision = gates_passed=False (previously only hard_fail gated)
2. Before final return: if gates_passed=False with contradiction reason, answer prefixed with disclosure ("My response may conflict with what I have on record" + stored beliefs listed)
3. Verified: "Where do I work?" now correctly answers "self-employed" citing trust scores, no hallucination, no hedge needed because belief injection prevented the error upstream

### Session Score: 4 bugs fixed (3 P0, 1 P1), 1 theory paper, backprop engine validated
Board: 148 done, 0 in progress, 5 up next

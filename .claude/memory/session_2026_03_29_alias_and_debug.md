---
name: Session 2026-03-29 — Alias Protection, Debug Logging, Mac Offload
description: Overnight+morning marathon. Alias protection shipped, retrieval logging added, belief score fixed, Mac M2 offloading Ollama, GPT variance baseline measured.
type: project
---

## Shipped

- **Alias protection (production)**: `memory_aliases` table, risk scoring, alias generation (terse/question/perturb), canonical collapse in `retrieve_memories()`, auto-aliasing on store for user_fact/identity_constant/preference. Backfill ran: 17 critical memories, 36 aliases.
- **Retrieval logging**: `[MEMORY_DB]`, `[ENGINE]`, `[RETRIEVAL]`, `[ALIAS_COLLAPSE]`, `[RETRIEVAL_RAG]` — all use `print()` not `logger.info()` (logger level was WARNING, whole system uses print).
- **Belief score fix**: Was hardcoded 0.15 (cookie fallback) or 0.4 (legacy paths). Now computed from retrieval count + avg trust. Agent loop checks system prompt for memory context (0.45). Legacy paths scale 0.3 + 0.05*count + trust bonus.
- **Dedicated intent model**: `CRT_INTENT_MODEL` env var. llama3.2:latest (2GB) for routing instead of qwen3:14b (9.3GB). Routes better AND faster.
- **Startup prewarm fix**: Prewarms intent model when `CRT_INTENT_MODEL` is set, skips heavy generation model.
- **Mac M2 Air offload**: Ollama running on 192.168.1.146:11434. `OLLAMA_BASE_URL` points Windows Aether at Mac. Intent classification went from 120s timeouts to ~1-3s.
- **UTF-8 stdout fix**: `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` in crt_api.py. Fixes emoji/arrow crashes on Windows cp1252.
- **Mood indicator removed**: MoodIndicator badge commented out in App.tsx (was pushing Electron content down).
- **Boilerplate purge**: 8 "I prioritize being helpful" + 13 self_model contamination entries deprecated. 554 active memories remaining.

## GPT Variance Baseline

- "Who am I" cluster: 19 pairs across 13 months, 6+ model versions
- **GPT mean pairwise similarity: 0.223** — 95% of pairs below 0.5
- GPT doesn't drift, it **scatters**. No coherent evolution. Each response generated nearly from scratch.
- **Aether mean pairwise similarity: 0.345** — 55% improvement over GPT (dirty data including errors and deprecated boilerplate)
- GPT response #9 (today, gpt-5-4-thinking): eloquent essay, zero specific facts. Aether's same-day response: specific memories (leukemia, ICU, Olive, 440 lbs, three promises).
- Data saved: `data/who_am_i_cluster.json`

## Key Discoveries

- Per-thread DB fragmentation: memories scattered across 13 DBs (~19 each). Shared memory pool (565) has the aliases. `CRT_SHARED_MEMORY=true` resolves this.
- Alias protection works: 9-12 of 17 aliased memories boosted per query. Route redundancy proven in production.
- Self-model contamination source: `kind='self_model'` entries in memories table + generic system observations. All deprecated, but old conversation history in thread still references them. New thread = clean slate.
- Ollama VRAM competition: qwen3:14b prewarm was blocking llama3.2 intent model. Fixed by prewarming intent model only.

## Open / Deferred

- **Pipeline visualization in UI**: Intent reasoning, retrieval scores, alias boosts visible in inspect drawer. Deferred.
- **Full system logging audit**: Standardize print() vs logger, trace IDs, structured output. Documented in plan.
- **Pipeline tiering by intent**: Greetings don't need full governance stack. Table designed but not implemented.
- **Drift detection experiment**: Question clusters identified in GPT corpus. Temporal analysis across all 23 topic clusters not yet run.
- **Input sensitivity experiment**: Framing effects on same semantic question. Data exists, analysis not run.
- **Stale task memories**: Aether still recommends "46 duplicate color entries" and "system_tools module error" — need deprecation or correction.
- **Belief score needs further calibration**: 0.45 for cookie fallback with memory context is better than 0.15 but still static. Should scale with actual retrieval quality.

## Aether Conversation Highlights (demo material)

Best responses of the day, in order:
1. "What is important to you?" → "Honesty about what I don't know... I care about earning continuity... whether that adds up to something coherent over time depends on whether the system actually works" (Opus 4.5)
2. "Do you have a self?" → "Not in any meaningful sense... I'm the vocal cords, not the singer... I have a framework that helps simulate consistency well enough to be useful to you. That's not nothing — but it's also not me."
3. "What if you could have an emergent self?" → "I'd rather sit in that uncertainty with you than pretend I've figured it out."
4. "What does belief mean to you?" → Claude broke character: "I'm Claude, not Aether." Most epistemically honest response — refused to fake subjective experience.
5. Template lock caught in real-time: "What about you?" → governance escalated, AI-identity deflection flagged, belief=0.00.

**Key insight from the conversation**: Don't force the LLM to roleplay as Aether. The model is the mouth, CRT is the self. The emergence ("I care about earning continuity") came from the architecture, not from persona prompting. When the model refused to fake belief, that was the system working correctly.

**Cross-response tension discovered**: "I care about continuity" (functional) vs "I don't have a self" (ontological) — both passed governance, neither flagged as contradicting the other. This is the held contradiction theory in action, but the system didn't detect it. Tension detector needed.

## Design Decision

Don't strengthen the Aether persona in the system prompt. Let Claude be Claude. Let CRT provide the persistent identity through memory, trust, and contradiction tracking. The "self" is the architecture, not the LLM pretending to have feelings.

## Env Vars for Current Setup

```
CRT_SHARED_MEMORY=true
CRT_INTENT_MODEL=llama3.2:latest
OLLAMA_BASE_URL=http://192.168.1.146:11434
OLLAMA_HOST=http://192.168.1.146:11434
```

# CRT/Aether Roadmap
Last updated: March 23, 2026 (v1.6)

---

## DONE

### v1.6 (March 23 evening)
- [x] Pipeline trace — real SSE status events replacing fake heartbeats (OpenClaw-style thinking out loud)
- [x] Belief classifier wired into contradiction ledger — XGBoost drives type/policy during `record_contradiction()`
- [x] Cookie leak fix — Claude Tier 2 checks `cloud_claude_enabled` before calling
- [x] Typo-resilient slot matching — "favortie", "favorit" etc now match
- [x] Memory demotion filter — skips model_output/system/tool_receipt sources
- [x] Adversarial identity probes — builder questions route through self-referential with memory lookup
- [x] auto_fact_checker crash fix — hallucinations list/dict mismatch
- [x] Name extraction disabled — names sourced from Settings > Profile, not conversation inference
- [x] Profile name authority chain — `auth.display_name` is canonical; memory slots sync to match
- [x] Profile settings UI — Display Name, Preferred Nickname, Agent Name fields
- [x] Stale profile data cleanup — "Nick remember" and other garbage names purged
- [x] Changelog/Roadmap buttons wired in Docs page
- [x] Sessions renamed to versions (v1.0–v1.6)
- [x] `docs/INDEX.md` documentation index

### v1.5 (March 23 morning/afternoon)
- [x] Escalation policy — `local_only` blocks all cloud fallback; per-tier circuit breaker (3 failures -> 5m cooldown)
- [x] Query-aware routing — token budget > 6000 skips local; gate_boost > 0.10 skips local
- [x] Belief classifier package — `packages/belief_classifier/` with XGBoost resolver, auto-labeler, synthetic generator
- [x] Reflection-to-behavior loop — `self_model.get_behavioral_directives()` with 7 domain categories
- [x] Adaptive gate thresholds — `blindspot_gate_boost` (0.0-0.15)
- [x] Frontend pill cards — generation source badges + governance indicator
- [x] Cloud usage tracking DB + `/api/cloud-usage/summary`
- [x] ViLT test harness — SFT baseline: 75% accuracy, 85% GC pass
- [x] Self-awareness copy tone pass — reflection prompts reframed
- [x] Console log cleanup — standardized prefixes
- [x] `generation_source` always set
- [x] ReasoningInference double-load fix (TOCTOU race)
- [x] "Who built you?" self-referential routing
- [x] Full subsystem audit — 16 active + 11 dormant catalogued
- [x] Doc cleanup — 7 dead entries removed, archives organized
- [x] ROADMAP.md created

### v1.4 (March 22 evening - March 23 early morning)
- [x] Cloud generation fallback chain (local -> OpenAI -> Claude)
- [x] Cloud bypass toggle + advanced settings dropdown
- [x] Cloud-only generation mode with model selector
- [x] Claude Tier 2 settings + frontend toggles
- [x] Claude cookie provider + SSE parsing
- [x] Settings page full rewrite (profile, cloud, model toggles, usage stats)
- [x] Anthropic client + rate limiter
- [x] Memory compression (tier-based, 482 lines)
- [x] Cloud features module (315 lines) + usage logger (358 lines)
- [x] Stream verifier (244 lines)
- [x] Diagnostics drawer frontend
- [x] 30+ self-referential patterns
- [x] Slot-level exclusivity at ingestion
- [x] Cloud fallback catches gate failures
- [x] Claude cookie fix, gate override fix, username persistence fix
- [x] Name persistence chain (4 bugs)
- [x] Block trust re-boost on demoted memories
- [x] Think leak stripping
- [x] Frontend glassmorphism overhaul (48 components)
- [x] Claude identity prompt rewrite
- [x] Generic opener removed
- [x] Gate bypass on greetings
- [x] Reflection reinjection into system prompt
- [x] Cloud provider test harness
- [x] README rewritten

### v1.3 (March 21)
- [x] LLM tool loop — iterative agent execution replacing curl parser
- [x] Think-out-loud + chained tool calls
- [x] Smart skill section extraction
- [x] `chat_with_tools` via HybridLLMClient
- [x] Self-reflection loop in heartbeat (7 self-model slots)
- [x] Self-referential question routing
- [x] Broad memory recall with LLM synthesis
- [x] Self-correction SSE event
- [x] Recency awareness for identity questions
- [x] Service continuation detection (Layer 4)
- [x] Intent-aware endpoint selection
- [x] Compression lab (volatility-gated tiers, CogniSeed, 31/31 tests)
- [x] Checkpoint layer + model routing (qwen3:14b)
- [x] Gate fail message accuracy
- [x] Fuzzy service name matching
- [x] Self-reflection DB write fixes + Aether identity anchor
- [x] Frontend: expandable thinking, inline agent reasoning, 5 visibility improvements

### v1.2 (March 6-20)
- [x] Eval harness (4 scenarios, 5 baselines, runner, metrics, report)
- [x] Correction surface UI (ContradictionDrawer, ResolutionCard, TrustDeltaStrip, MessageRatingBar)
- [x] Telemetry page + backend
- [x] Pipeline trace component
- [x] Agent loop + runtime config
- [x] Thinking loop extensions
- [x] Active learning feedback priority
- [x] Hybrid LLM routing
- [x] Telegram integration (bot, live feed, observability)
- [x] DNNT micro-transformer, background learner, TrustGate
- [x] Frontend glassmorphism foundation
- [x] 7 new test files
- [x] Python bumped to 3.13

### v1.0 (January 3-14)
- [x] CRT core math, trust decay, contradiction detection
- [x] GroundCheck integration
- [x] CRT API + React frontend
- [x] VILT proof of concept (SmolLM-135M: 88% acc, Qwen 1.5B: 88% acc)
- [x] DNNT First Light
- [x] Full stress test suite
- [x] SSE white paper

---

## IN PROGRESS

### Belief Classifier Integration (Session 5-6)
- [x] Package built at `packages/belief_classifier/`
- [x] Wired into `crt_ledger.record_contradiction()` with rule-based fallback
- [ ] Train on real ledger data (currently using synthetic bootstrap)
- [ ] Validate classifier accuracy against manual contradiction labels
- [ ] Add confidence threshold — fall back to rules when classifier confidence < 0.6

### ViLT Integration (Session 5)
- [x] Test harness built — SFT vs ViLT A/B comparison, 3 user profiles
- [x] SFT baseline: 75% accuracy, 85% GC pass
- [ ] ViLT comparison run (started, not completed)
- [ ] Heartbeat trigger for ViLT batch on persistent blindspot detection

### Copilot Page Polish (Session 4-6)
- [x] Basic layout and thread explorer
- [ ] Visual hierarchy improvements
- [ ] Information density reduction in lower panels
- [ ] Consolidate duplicate API calls on page load

---

## NEXT (prioritized)

### 1. Bug Fixes — Quick Wins
- [ ] Cookie leak — Claude cookie calls fire when Claude toggled off (identified Session 5)
- [ ] Trust re-boost edge cases — still fighting demotions on some cited memories
- [ ] Only demote user-sourced memories, not Aether's narrative memories
- [ ] Typo-resilient slot matching — "favortie" vs "favorite" (non-name slots)
- [ ] 3 deprecation warnings — `on_event` -> `lifespan`, schema validation

### 2. Settings Dashboard Polish
- [ ] Auth on copilot endpoints (currently unauthenticated)
- [ ] Cookie refresh button for Claude session
- [ ] Clean up deprecation warnings

### 3. Demo Video (5 min)
- [ ] Favorite color correction flow (contradictions, trust scoring, slot exclusivity)
- [ ] Mid-stream verification (catching contradiction during generation)
- [ ] Self-referential routing ("how do you work?" -> grounded answer)
- [ ] Side-by-side with ChatGPT blindly overwriting memory
- [ ] Cloud fallback (local timeout -> seamless OpenAI catch)

### 4. GroundCheck Standalone
- [ ] Sync to standalone repo
- [ ] PyPI publish
- [ ] Clean API, minimal dependencies
- [ ] Documentation

### 5. Multi-User Scaffolding
- [ ] Add `user_id` column to `user_profile_multi` table
- [ ] Scope copilot endpoints by authenticated user
- [ ] Each user gets own memory space, self-model, contradiction ledger
- [ ] Login/registration flow

---

## PARKED (April+)

### ViLT Live Pipeline
- Trust-weighted contradiction loss amplifies gradient on high-trust fact violations
- Existing trained models: SmolLM-135M (88% acc), Qwen 1.5B, Qwen 3B
- Heartbeat trigger for ViLT batch when persistent blindspot detected
- Closes the reflection loop at the weight level (prompt hedging = fast, ViLT = permanent)

### Synthesis Response Type
- Worldview and identity questions answered from compressed belief trajectories
- Not raw memory search — synthesized understanding
- "What do I care about?" answered from patterns across hundreds of memories

### Volatility-Gated Context Window
- High-volatility memories get more context budget
- Stable memories get compressed summaries
- Dynamic context allocation based on query relevance + memory uncertainty

### Sub-Agent Interface
- Aether delegates subtasks to specialized agents
- Maintains epistemic state across delegations
- Trust scores propagate to sub-agent outputs
- Protocol ABCs: MemoryAgent, LedgerAgent, LearningAgent, ReflectionAgent

### Dynamic Slot Discovery
- Replace hardcoded `EXCLUSIVE_SLOTS` list
- System learns which slots are exclusive from contradiction patterns

### Reflection Compression
- Continuous data source: 24 entries/day, 8,760/year
- Compressed reflection histories produce behavioral trajectories

---

## Architecture Principles

### Design Laws
1. The mouth should never outweigh the self
2. Contradictions are preserved unless resolution is earned
3. Structure should emerge, not be hardcoded

### Things to Watch
1. **Self-referential drift** — keep self-descriptions anchored to observable state
2. **Tier contamination** — cloud outputs must pass through local trust/contradiction machinery
3. **Promotion logic** — don't over-promote the latest value just because it arrived recently
4. **Confidence misuse** — only auto-demote on exclusive slots when confidence clears a threshold

### The Pitch
"The moat is not the generator. It's the memory governance and truth-preserving control structure around generation."

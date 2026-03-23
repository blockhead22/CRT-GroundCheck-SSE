# CRT/Aether Roadmap
Last updated: March 23, 2026 (end of Session 6)

## Completed — Session 6 (March 23 evening)
- [x] Pipeline trace with real statuses — OpenClaw-style thinking out loud
- [x] auto_fact_checker crash fix
- [x] Cookie leak fix — Claude cookie calls no longer fire when Claude toggled off
- [x] Typo-resilient slot matching ("favortie" vs "favorite")
- [x] Memory demotion filter — skip model_output/system sources
- [x] Adversarial identity probes — builder/creator questions routed correctly
- [x] Belief classifier wired into contradiction lifecycle
- [x] Name extraction disabled — names sourced from settings only
- [x] Profile settings UI — Display Name, Preferred Nickname, Agent Name fields
- [x] Stale profile data cleanup

## Completed — Session 5 (March 23 morning/afternoon)
- [x] Escalation policy enforcement — `local_only` blocks all cloud fallback paths (primary + late-stage + promotion)
- [x] Console log cleanup — standardized `[GENERATION]`, `[GOVERNANCE]`, `[REQUEST_SUMMARY]` prefixes; removed redundant debug lines
- [x] Frontend pill cards — color-coded generation source (Local/GPT/Claude/Fallback) + governance badge
- [x] Cloud usage tracking DB — `cloud_usage_log` table with full metadata per cloud call; `/api/cloud-usage/summary` endpoint
- [x] `result["generation_source"]` always set (was missing on local success path)
- [x] Self-awareness copy tone pass — reflection prompts reframed from self-flagellation to governed calibration
- [x] "Who built you?" context gap — added creator/builder patterns to self-referential routing
- [x] ReasoningInference double load fix — engine cache race condition (TOCTOU) fixed with lock-during-creation
- [x] ViLT test harness built — SFT baseline: 10% to 75% accuracy, 85% GC pass, 2 hallucinations in 200 steps
- [x] Belief classifier package — `packages/belief_classifier/` with XGBoost contradiction resolver, 26 tests passing
- [x] Full subsystem audit — catalogued 16 active + 11 dormant systems; triage: 6 keep, 13 ignore, 4 merge
- [x] Doc cleanup — removed 7 dead entries from doc_map, fixed ViLT writeup date, archived IMPLEMENTATION_PLAN.md
- [x] Reflection-to-behavior loop — `self_model.get_behavioral_directives()` with domain-specific caution flags
- [x] Adaptive gate thresholds — `blindspot_gate_boost` (0.0-0.15) raises alignment bars on blindspot queries

## Completed — Session 4 (March 22 overnight + March 23 morning)
- [x] Cloud bypass toggle — raw model access with CRT skip
- [x] Advanced settings dropdown — chevron opens side card with Bypass CRT and Enable Tooling toggles
- [x] Claude cookie fix — fresh session cookie, SSE parsing working
- [x] Gate override fix — cloud answers no longer hidden by local gate failure
- [x] Claude identity prompt rewrite — product integration framing
- [x] CRT name fix — "Contradiction-aware Reconciliation and Trust" in system prompt
- [x] Username persistence fix — stopwords + frontend race condition guard
- [x] set_profile_facts 500 fix — replaced broken import with direct engine call

## Completed — Session 3 (March 22 evening)
- [x] Slot-level exclusivity at ingestion
- [x] Fix gate on greetings
- [x] Wire reflection reinjection into system prompt
- [x] Block trust re-boost on demoted memories
- [x] Clean stale memory_facts on demotion
- [x] Fix auto_fact_checker crash
- [x] Think leak heuristic stripping
- [x] Cloud generation fallback (local -> OpenAI -> Claude)
- [x] Cloud-only generation mode with model selector UI
- [x] Claude Tier 2 settings + frontend toggles
- [x] Name persistence chain (4 bugs fixed)
- [x] Health poll spam reduced
- [x] 30+ self-referential patterns added
- [x] Cloud fallback catches gate failures
- [x] Claude cookie provider configured
- [x] README rewritten
- [x] Generic opener removed

## This Week (March 24-28) — Priority: Polish and Ship

### 1. XGBoost Classifier Integration Testing
Belief classifier package exists at `packages/belief_classifier/` — needs live pipeline integration testing.
- Run classifier against real contradiction ledger data
- Validate REFINEMENT / REVISION / TEMPORAL / CONFLICT categorization accuracy
- Wire policy classifier output into resolution endpoint
- Benchmark: classifier decisions vs "preserve everything" baseline on real data

### 2. Copilot Page Polish
- Visual hierarchy improvements
- Information density reduction in lower panels
- Consolidate duplicate API calls on page load

### 3. Remaining Bug Fixes
- Trust re-boost still fighting demotions on some cited memories (edge cases)
- Only demote user-sourced memories, not Aether's narrative memories

## Next Two Weeks (March 29 - April 11) — Ship It

### GroundCheck Standalone
- Sync to standalone repo
- PyPI publish
- Clean API, minimal dependencies
- Documentation

### Demo Video (5 min)
- Show favorite color correction flow (contradictions, trust scoring, slot exclusivity)
- Show mid-stream verification (catching contradiction during generation)
- Show self-referential routing ("how do you work?" gives grounded architecture answer)
- Side-by-side with ChatGPT blindly overwriting memory
- Show cloud fallback (local timeout leads to seamless OpenAI catch)

### Settings Dashboard Polish
- Auth on copilot endpoints (currently unauthenticated)
- Cookie refresh button for Claude session
- Clean up 3 deprecation warnings (on_event to lifespan, schema validation)

### Multi-User Scaffolding
- Add user_id column to user_profile_multi table
- Scope copilot endpoints by authenticated user
- Each user gets own memory space, self-model, contradiction ledger
- Login/registration flow

## April+ — The Bigger Picture

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

### ViLT Integration into Live Pipeline
- Test harness built (Session 5): SFT vs ViLT A/B comparison across 3 user profiles
- Trust-weighted contradiction loss amplifies gradient on high-trust fact violations
- Existing trained models: SmolLM-135M (88% acc), Qwen 1.5B, Qwen 3B
- Next: heartbeat trigger for ViLT batch when persistent blindspot detected
- Closes the reflection loop at the weight level (prompt hedging = fast path, ViLT = permanent fix)

### Dynamic Slot Discovery
- Replace hardcoded EXCLUSIVE_SLOTS list
- System learns which slots are exclusive from contradiction patterns
- "Every time someone updates favorite_color, the old value gets contradicted" = exclusive

### Reflection Compression
- Continuous data source: 24 entries/day, 8,760/year
- Compressed reflection histories produce behavioral trajectories
- "I was bad at X for a week, adjusted, got better" — that's where emergence lives

## Architecture Principles (from GPT review)

### Things to Watch:
1. **Self-referential drift** — keep self-descriptions anchored to observable state, not polished mythology
2. **Tier contamination** — cloud outputs must pass through local trust/contradiction machinery. Never harden into belief without local verification
3. **Promotion logic** — don't over-promote the latest value just because it arrived most recently. Earned current belief, not successful ingestion
4. **Confidence misuse** — only auto-demote on exclusive slots when cloud confidence clears a threshold or utterance has strong correction language

### Design Laws:
1. The mouth should never outweigh the self
2. Contradictions are preserved unless resolution is earned
3. Structure should emerge, not be hardcoded

### The Pitch:
"The moat is not the generator. It's the memory governance and truth-preserving control structure around generation."

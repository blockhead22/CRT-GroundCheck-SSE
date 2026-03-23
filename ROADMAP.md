# CRT/Aether Roadmap
Last updated: March 22, 2026

## Completed — Session 3 (March 22 evening)
- [x] Slot-level exclusivity at ingestion
- [x] Fix gate on greetings
- [x] Wire reflection reinjection into system prompt
- [x] Block trust re-boost on demoted memories
- [x] Clean stale memory_facts on demotion
- [x] Fix auto_fact_checker crash
- [x] Think leak heuristic stripping
- [x] Cloud generation fallback (local → OpenAI → Claude)
- [x] Cloud-only generation mode with model selector UI
- [x] Claude Tier 2 settings + frontend toggles
- [x] Name persistence chain (4 bugs fixed)
- [x] Health poll spam reduced
- [x] 30+ self-referential patterns added
- [x] Cloud fallback catches gate failures
- [x] Claude cookie provider configured
- [x] README rewritten
- [x] Generic opener removed

## This Week (March 23-28) — Priority: Close the Loop

### 1. ~~Reflection-to-Behavior Loop~~ ✅ SHIPPED (Session 5)
Closed the gap between reflection observing and reflection acting.
- `self_model.get_behavioral_directives(query)` parses blindspots/uncertainty/correction slots into domain-specific caution flags
- Prompt injection expanded: BEHAVIORAL CALIBRATION block with hedging instructions injected when query touches weak domain
- Adaptive gate thresholds: `blindspot_gate_boost` (0.0–0.15) raises alignment bars on blindspot queries
- 7 domain categories (temporal, names, numerical, preference, recency, recall, accuracy) with keyword matching
- Narrow, auditable, reversible — biases future handling without rewriting history

### 2. Train XGBoost Classifiers (AFTER reflection loop)
- Generate training data from the live contradiction ledger
- Train belief classifier (REFINEMENT / REVISION / TEMPORAL / CONFLICT)
- Train policy classifier (OVERRIDE / PRESERVE / ASK_USER)
- Drop pkl files at personal_agent/ml_models/xgboost.pkl and policy_xgboost.pkl
- "Better classifiers on top of an open cognitive loop mostly make the system more precise at noticing things it still cannot metabolize" — GPT

### 3. Self-Awareness Copy Tone Pass
- Reframe from self-flagellation to governed adaptation
- "Trust is eroding" → "3 corrections applied — trust recalibrating"
- "Insufficient data to identify strengths" → "Calibrating — 2 sessions of baseline data collected"
- One lead insight per checkpoint, expandable supporting detail
- Frame as the system WORKING, not the system FAILING

### 4. Copilot Page Polish
- Visual hierarchy improvements
- Information density reduction in lower panels
- Consolidate duplicate API calls on page load

### 5a. ~~Escalation Policy~~ ✅ SHIPPED (Session 5)
Smart tier routing with circuit breaker. Prevents eating 300s Ollama timeouts repeatedly.
- `personal_agent/escalation_policy.py` — EscalationPolicy with per-tier circuit breaker (3 failures → 5m cooldown)
- Query-aware routing: token budget estimate > 6000 → skip local; reflection gate_boost > 0.10 → skip local
- Wired into `routes/chat.py`: decide() before generation, record_success/failure at all outcomes
- Configurable via `runtime_config.py` escalation_policy block
- In-memory state, no DB — resets on restart

### 5b. Remaining Bug Fixes
- "Who is building this system?" should pull creator context from memories
- ~~Ollama timeouts on follow-up "Explain more"~~ — mitigated by escalation policy circuit breaker
- Trust re-boost still fighting demotions on some cited memories (edge cases)
- Typo-resilient slot matching ("favortie" vs "favorite")
- Only demote user-sourced memories, not Aether's narrative memories
- ReasoningInference model loading multiple times at startup

## Next Two Weeks (March 29 - April 11) — Ship It

### GroundCheck Standalone
- Sync to standalone repo
- PyPI publish
- Clean API, minimal dependencies
- Documentation

### Demo Video (5 min)
- Show favorite color correction flow (contradictions, trust scoring, slot exclusivity)
- Show mid-stream verification (catching contradiction during generation)
- Show self-referential routing ("how do you work?" → grounded architecture answer)
- Side-by-side with ChatGPT blindly overwriting memory
- Show cloud fallback (local timeout → seamless OpenAI catch)

### Settings Dashboard Polish
- Auth on copilot endpoints (currently unauthenticated)
- Cookie refresh button for Claude session
- Clean up 3 deprecation warnings (on_event → lifespan, schema validation)

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
- Hot-swap qwen3 for ViLT-finetuned model on fact-heavy queries
- Trained models exist (Qwen 1.5B, 3B) but aren't serving
- A/B testing framework: ViLT vs base model on same queries

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

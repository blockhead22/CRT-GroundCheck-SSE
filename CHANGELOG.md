# CRT/Aether Changelog

All notable changes to the CRT (Cognitive Reflective Trust) / Aether project.
Organized by version. Categories: Feature, Fix, Polish, Infra, Docs, Test.

---

## v1.6 — March 23, 2026

Identity hardening, belief classifier integration, pipeline trace, 5 bug fixes, profile authority cleanup.

### Feature
- Pipeline trace — real SSE status events via contextvar queue replacing fake heartbeat cycling; `stream_checkpoint` and `stream_stopped` handlers wired in frontend; PipelineTrace component updated with generating/classifying-slots classifications
- Belief classifier wired into contradiction ledger — XGBoost `ContradictionResolver` drives type/policy decisions during `record_contradiction()`, falling back to rule-based classification when models are absent
- Profile settings UI — Display Name, Preferred Nickname, Agent Name fields in Settings; all explicit user-controlled, not inferred
- Changelog and Roadmap buttons wired in Docs page; sessions renamed to versions (v1.0–v1.6)

### Fix
- Cookie leak — Claude Tier 2 fallback now checks `cloud_claude_enabled` before calling (both primary and late fallback paths)
- Typo-resilient slot matching — "favortie", "favorit", "favourte" all match via expanded regex
- Memory demotion filter — skips `model_output`/`system`/`tool_receipt` source kinds; only user-sourced memories get demoted on exclusive slot conflict
- Adversarial identity probes — builder/creator questions route through self-referential with memory-grounded context injection
- auto_fact_checker crash — `hallucinations` list vs dict type mismatch (`AttributeError: 'list' object has no attribute 'items'`)
- Name extraction disabled — conversation-inferred names produced garbage ("Nick remember", "high", "gonna quick run"); gated behind `_EXTRACT_NAMES_FROM_CONVERSATION = False`; names sourced exclusively from Settings > Profile
- Profile name authority chain — `/api/memory/profile` reads `auth.display_name` as canonical source
- Stale profile data cleaned — "Nick remember" and other garbage purged from `user_profile_multi`

### Polish
- Removed fake keyword-based pipeline hints (analyzing query, searching memory duplicates)

### Docs
- `CHANGELOG.md` — comprehensive changelog from git history covering v1.0 through v1.6
- `ROADMAP.md` — restructured into DONE/IN PROGRESS/NEXT/PARKED sections with version labels
- `docs/INDEX.md` — organized documentation index

---

## v1.5 — March 23, 2026 (morning/afternoon)

Major subsystem audit, escalation policy, ViLT testing, belief classifier package, observability improvements.

### Feature
- Escalation policy enforcement — `local_only` blocks all cloud fallback paths (primary, late-stage, promotion)
- `EscalationPolicy` with per-tier circuit breaker (3 failures triggers 5-minute cooldown)
- Query-aware routing — token budget > 6000 skips local; reflection gate_boost > 0.10 skips local
- Belief classifier package — `packages/belief_classifier/` with XGBoost contradiction resolver, auto-labeler, synthetic data generator
- Reflection-to-behavior loop — `self_model.get_behavioral_directives()` parses blindspots into domain-specific caution flags
- Adaptive gate thresholds — `blindspot_gate_boost` (0.0-0.15) raises alignment bars on blindspot queries; 7 domain categories with keyword matching
- Frontend pill cards — color-coded generation source (Local/GPT/Claude/Fallback) + governance badge on messages
- Cloud usage tracking DB — `cloud_usage_log` table with full metadata per cloud call; `/api/cloud-usage/summary` endpoint
- ViLT test harness — SFT vs ViLT A/B comparison across 3 user profiles; moved from root `_patch_chat.py` to `scripts/vilt_test_harness.py`
- CRT RAG document map extended for new docs

### Fix
- `result["generation_source"]` always set (was missing on local success path)
- ReasoningInference double-load fix — engine cache TOCTOU race condition fixed with lock-during-creation
- "Who is building this system?" now pulls creator context via self-referential routing
- Heartbeat system hardened — cloud usage logging integrated, timer adjustments

### Polish
- Self-awareness copy tone pass — reflection prompts reframed from self-flagellation to governed calibration
- Console log cleanup — standardized `[GENERATION]`, `[GOVERNANCE]`, `[REQUEST_SUMMARY]` prefixes

### Test
- ViLT test harness: SFT baseline 10% to 75% accuracy, 85% GC pass, 2 hallucinations in 200 steps (35 min)
- Belief classifier: 26 tests passing
- Benchmark script: classifier decisions vs "preserve everything" baseline

### Infra
- Full subsystem audit — catalogued 16 active + 11 dormant systems in AI_round2, 73 files in D:\CRT; triage: 6 keep, 13 ignore, 4 merge
- `_patch_chat.py` removed from root (410 lines); functionality moved to `scripts/vilt_test_harness.py`

### Docs
- Doc cleanup — removed 7 dead entries from doc_map, fixed ViLT writeup date, archived IMPLEMENTATION_PLAN.md
- ROADMAP.md created with session-by-session status tracking

---

## v1.4 — March 22, 2026 (evening through March 23 early morning)

Cloud integration, design system overhaul, settings pages, memory compression, anthropic client, advanced settings UI.

### Feature
- Cloud generation fallback chain — local timeout flows to OpenAI then Claude seamlessly
- Cloud-only generation mode with model selector UI in frontend
- Cloud bypass toggle — raw model access with CRT pipeline skip
- Advanced settings dropdown — chevron opens side card with Bypass CRT and Enable Tooling toggles
- Claude Tier 2 settings + frontend toggles
- Claude cookie provider configured for SSE streaming
- Settings page (full rewrite) — profile, cloud settings, model toggles, usage stats
- Docs page expanded — 574-line rewrite with architecture sections and code widgets
- Anthropic client — 400-line `personal_agent/anthropic_client.py` with rate limiting
- Rate limiter — `personal_agent/rate_limiter.py` for cloud API call management
- Memory compression — `personal_agent/memory_compression.py` (482 lines) with tier-based compression and integration tests
- Cloud features module — `personal_agent/cloud_features.py` (315 lines) for cloud model routing
- Cloud usage logger — `personal_agent/cloud_usage_logger.py` (358 lines) with per-call metadata tracking
- Stream verifier — `personal_agent/stream_verifier.py` (244 lines) for SSE integrity checking
- V2 page — 400-line experimental frontend page
- Diagnostics drawer — frontend panel for runtime debugging with log viewer
- Settings modal — expanded with cloud provider toggles and advanced options
- 30+ self-referential patterns added to routing
- Slot-level exclusivity at ingestion — contradicting values on exclusive slots trigger resolution
- Cloud fallback catches gate failures — gate fail on local answer triggers cloud retry

### Fix
- Claude cookie fix — fresh session cookie with SSE parsing working
- Gate override fix — cloud answers no longer hidden by local gate failure
- Username persistence fix — stopwords filter + frontend race condition guard
- set_profile_facts 500 fix — replaced broken import with direct engine call
- Name persistence chain (4 bugs fixed across fact_slots, crt_memory, routes)
- Health poll spam reduced
- Block trust re-boost on demoted memories
- Clean stale memory_facts on demotion
- auto_fact_checker crash fix — exception handling hardened
- Think leak heuristic stripping — `<think>` tags filtered from output
- Ollama client connection fixes and retry logic improvements
- Task agent improvements — multi-step execution, budget extension, 3-failure auto-stop
- CRT memory thread-scoped improvements — 218-line rewrite of memory retrieval

### Polish
- Frontend: complete glassmorphism design system overhaul — 48 component files updated in single pass
- Frontend: CSS variable system with `design-system.css` rework
- Frontend: sidebar, topbar, composer, message bubble, pipeline trace restyled
- Frontend: dark-mode consistent backgrounds and spacing
- Claude identity prompt rewrite — product integration framing
- CRT name fix — "Contradiction-aware Reconciliation and Trust" in system prompt
- Generic opener removed — "Hello! I'm your AI assistant" blocked
- Gate bypass on greetings — greeting messages skip memory gate
- Wire reflection reinjection into system prompt

### Infra
- Cloud provider test harness — `tests/cloud_providers/` with Chrome session automation, prompt library, multi-provider runner (263 + 174 + 365 + 211 lines)
- `.claude/settings.local.json` updated with provider configs
- Auth routes expanded — cloud settings CRUD, API key management
- Route registration updated with logs endpoint

### Docs
- README rewritten to reflect agentic execution, self-reflection, and tool loop advances

---

## v1.3 — March 21, 2026

Massive feature session: 17 backend + 3 frontend commits. Self-reflection, tool loop, broad recall, service routing, compression lab.

### Feature
- LLM tool loop — iterative agent execution (OpenClaw-style) replacing flat curl parser; default 8 calls, expandable to 15; 3 consecutive failures auto-stop
- Think-out-loud prompting — LLM narrates reasoning before/after each tool call
- Chained tool calls — follow-up prompt nudges LLM to continue if more data needed
- Smart skill section extraction — keyword-scored API doc sections replace naive first-8KB truncation
- `chat_with_tools` delegated through HybridLLMClient (was only on OllamaClient)
- Self-reflection loop wired into heartbeat executor — writes 7 self-model slots (uncertainty_domains, correction_pattern, trust_trajectory, known_blindspots, growing_confidence, user_relationship, response_style)
- Self-referential question routing — "how do you work?" gives doc-grounded architecture answer
- Broad memory recall with LLM synthesis — "what do you know about me?" returns synthesized summary, not raw fact dump
- Self-correction SSE event — catches "I don't know" when data exists and follows up
- Recency awareness for identity questions
- Service continuation detection (Layer 4) — "any new threads?" inherits moltbook context from last completed task
- Intent-aware endpoint selection for service queries (keyword scoring)
- Compression lab — adaptive semantic compression with volatility-gated tier promotion (10D/64D/384D), CogniSeed reconstruction guides, 85%+ storage savings
- Checkpoint layer + model routing — answer gen routed to qwen3:14b with timeout fix
- Moltbook skill doc added (1024 lines)

### Fix
- Gate fail messages match actual failure reason
- Fuzzy service name matching — "molt book" resolves to "moltbook"
- Fix self-referential answers — bump tokens 400 to 800, practical examples prompt
- Fix self-reflection DB writes — add vector_json and sse_mode to INSERT (NOT NULL constraint)
- Strengthen Aether identity — replace generic opener with "You are Aether" anchor
- Fix LLM tool loop — context-aware prompting + query-safe tools (remove http_post for query actions)
- Fix credential XOR decode, smart key naming, skip re-registration
- Fix broad recall DB query — use context_json column name
- Fix SSEMode value — 'LOSSLESS' to 'L' in self-model writes
- Add `SELF_REFLECTION` to MemorySource enum (was 'reflection' only)
- CRT RAG and resolution pattern fixes

### Polish
- Frontend: expandable thinking trace during streaming (ThinkingPreview with line count)
- Frontend: stream agent reasoning + tool calls inline (visible narration instead of hidden collapse)
- Frontend: 5 visibility improvements — correction SSE rendering, enriched pipeline steps with memory count and trust scores, gate fail amber border with reason badge
- Frontend: agent thinking strip improvements, CRT inspector updates
- Phase 1/2/3 quick fixes — max_tokens, fuzzy service names, recall patterns

### Test
- Compression lab: 31/31 tests passing; semantic similarity preserved, contradiction-triggered promotion validated
- Live session fix tests added (150 lines)

---

## v1.2 — March 6-20, 2026

Foundation building: eval harness, correction surface UI, personality/reflection systems, Telegram integration, hybrid LLM routing, frontend overhaul.

### Feature
- Eval harness — `eval/` directory with 4 scenarios (ContradictionStress, CorrectionRecovery, HallucinationProbe, NoiseDrift), 5 baselines (PlainRAG, DestructiveUpdate, NoLedger, NoTrustWeighting, NoBackgroundLearning), runner, metrics, and report generation
- Correction surface UI — ContradictionDrawer, ContradictionResolutionCard, TrustDeltaStrip, MessageRatingBar (thumbs up/down with categories)
- Telemetry page — `TelemetryPage.tsx` (371 lines) with `routes/misc.py` backend (233 lines)
- Copilot page v2 — thread explorer, memory browser, fact slot viewer
- Threads route — `routes/threads.py` (99 lines) for thread management
- Pipeline trace component — `PipelineTrace.tsx` (127 lines) showing live generation steps
- Agent loop — `personal_agent/agent_loop.py` with agent reasoning module
- Runtime config — `personal_agent/runtime_config.py` with JSON schema validation
- Fact store improvements — memory store sync idempotency, slot guard, thread scope
- Thinking loop extensions — context reads own thoughts, trust deltas, open contradictions
- Active learning feedback priority — severity-weighted ordering for DNNT queue
- Heartbeat system expansions — self-reflection pass, personality checkpoints, trust decay integration
- Hybrid LLM routing and observability (two-tier: local Ollama + cloud fallback)
- Telegram live stream integration — bot, RAG fixes, start script, LiveFeedPage route
- Observability — pipeline timing instrumentation, Telegram live events
- Streaming chat endpoint with real-time reasoning
- Copilot route improvements — trust trends, memory scopes, dashboard surfaces
- Adaptive style profiling and tone control
- Background loop streaming and inspector UI
- Continuous reflection and personality profiling loops
- Episodic memory system and API endpoints
- Skill registry, routes, memory bridge
- DNNT micro-transformer, background learner, hot-reload, TrustGate
- OpenClaw bridge tests and handoff tests

### Fix
- Fix encoding mojibake, enable two-tier LLM, async tasks
- Avoid role phrases parsed as names
- Fast memory count and increase bridge timeout
- Enforce second-person user facts and pet heuristics
- Improve name extraction for apostrophe variations and conjunctions
- Fix slot query answers to return actual fact values
- Chat gate fail sanitization, meta provenance fallback, repetition sanitization
- Contradiction thread filter fixes
- Fact store thread scope fixes
- Query with intent meta bypass

### Polish
- Frontend: glassmorphism UI revamp — ChatThreadView, MessageBubble, Composer, CRT inspector restyled
- Frontend: dark mode backgrounds, font-display, animation refinements
- Frontend: pipeline UI, contradiction tray, user settings panel, model selection
- Frontend: draft label, gradient mask, auto-scroll for streaming
- Frontend: message bubble rating integration, trust delta display
- Copilot route refactoring for cleaner API surfaces

### Infra
- Python bumped to 3.13; updated configs
- Auth: bcrypt, rate-limit, startup fixes
- Route extraction: auth, jobs, learning, memory, copilot routes separated
- Eval results directory with smoke test CSV and README

### Test
- 7 new test files — dashboard surface scopes, effective profile surface, memory search slot guard, memory store API, memory store sync idempotency, thread reset clears fact store, chat pipeline regressions
- Adversarial challenge results across multiple dates
- OpenClaw bridge and handoff tests (97 + 186 lines)
- Agent loop fallback tools test, name refinement gate test

### Docs
- README updates (multiple passes)
- Eval results README with smoke test analysis

---

## v1.0 — January 3 - 14, 2026

Project genesis: SSE engine, CRT core, GroundCheck integration, frontend app, VILT experiments, stress testing.

### Feature
- Initial commit — multi-document SSE engine, coherence tracking, navigator
- CRT core — cognitive-reflective memory and contradiction modules
- CRT chat CLI, dashboard, GUI, and agent modules
- CRT API backend (`crt_api.py`) and initial React frontend
- GroundCheck integration — SSE and SemanticMatcher into CRT Core
- FactStore and IntentRouter (ReAct orchestration)
- Contradiction detection pipeline — ML-based (20% to 80% detection rate), NL resolution, gate blocking
- Two-tier fact extraction integrated into contradiction detection and memory pipeline
- Assertive contradiction resolution — pick newest value with caveat
- Denial contradiction detection and ledger reset
- Dynamic fact storage + expanded resolution patterns
- Trust cap on contested memories (90% reduction)
- Contradiction resolution endpoint (OVERRIDE/PRESERVE/ASK_USER policies)
- Contradiction worklog and API endpoints for user clarification
- VILT proof of concept — verification-in-the-loop training
- VILT scaled: Qwen2.5-1.5B (1.54B params), 88% accuracy, 3.05GB peak VRAM
- VILT Pretrained: SmolLM-135M + LoRA + GroundCheck = 88% accuracy
- DNNT v2 batch distillation and First Light via GitHub Models API
- CRT promotion apply pipeline and CLI
- Controlled train-eval-publish pipeline for learned model
- Thread export and reset API endpoints
- Dashboard and memory endpoints
- Thread renaming lightbox
- Background jobs API, worker, and idle scheduler
- Training loop API endpoints and config support
- Optional Ollama LLM integration to CRT chat
- CRT MCP tools + copilot API endpoints
- LLM integration and sticker website demo
- Multi-agent system implementation

### Fix
- Fix critical contradiction detection bugs (20% to 80% detection rate)
- Fix gate blocking on resolved contradictions
- Fix NL resolution for all patterns
- Fix trust update NaN/None validation
- Fix database connection leak and state consistency
- Fix age extraction, SQLite MIN, age query inference
- Fix sqlite3.Row access in /correct endpoint
- Align Memory constructor with GroundCheck v0.5.1 API

### Infra
- GroundCheck vendored via git subtree, editable install
- CRT renamed: Cognitive Reflective Trust (was Cognitive-Reflective Transformer)
- Phase 0.1/0.2: kill list + WAL centralization + exception handling
- Phase 6 enforcement docs and CI workflow
- Adversarial boundary enforcement test suite
- Phase 6.2 client library and tests
- Markdown cleanup script and archive old docs
- Schema validation for runtime config
- Artifact store module and schema write tests
- Browser bridge and control panel setup

### Test
- Full CRT stress test suite — interactive assessment, adaptive, 30-turn hard stop
- A/B scoring and heuristic comparison in stress reports
- Adversarial challenge results (multiple rounds)
- Comprehensive system testing with market assessment
- Contradiction resolution unit tests
- Two-tier integration tests
- UX regression pack added to stress test and eval

### Docs
- SSE white paper for contradiction-preserving AI
- CRT quick reference and implementation summary
- Integration docs and demo script
- HOW_IT_WORKS.md, HOW_MULTI_AGENT_WORKS.md
- CRT roadmap, schemas documentation
- Thread handoff snapshot
- Automated handoff assessment and test status notes

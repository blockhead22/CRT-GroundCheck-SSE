# CRT/Aether Changelog

All notable changes to the CRT (Cognitive Reflective Trust) / Aether project.
Organized by version. Categories: Feature, Fix, Polish, Infra, Docs, Test.

---

## v3.8 — March 30, 2026

Agent Governance & Cookie Orchestrator — three-layer governance framework for agent runs, plus a brain/hands orchestrator architecture that lets Claude Opus direct local tool execution. Production cascade wiring replaces all 12 `record_contradiction()` call sites with real BDG propagation. Agent run logging captures every orchestrator execution to SQLite for Layer 2+ alignment checks.

### Feature
- **Cookie-Opus Orchestrator** (`personal_agent/cookie_orchestrator.py`) — brain/hands architecture where Claude Opus (brain) directs local tool execution (hands). Provider abstraction supports multiple LLM backends. 7 tools: file_read, file_write, dir_list, search_code, memory_recall, web_search, shell_exec. Multi-turn continuity with conversation context. Sandbox constraints for safe execution
- **Agent Governance Layers 1-3** — Layer 1: measurement (RunLog, RunStep, DriftEvent dataclasses with SQLite persistence capturing every orchestrator run). Layer 2: alignment check (planned). Layer 3: contradiction detection (planned). Layer 4: epistemic routing (planned)
- **Agent Run Log** (`personal_agent/agent_run_log.py`) — structured logging of orchestrator runs with step-level granularity, drift event tracking, SQLite persistence for post-hoc analysis
- **Code Intelligence Agent** (`personal_agent/code_intel.py`) — 4 modes: `file_map` (structural overview), `trace` (call chain analysis), `detect` (pattern detection), `full_audit` (comprehensive code review)
- **LiveBDG cascade wiring** — replaced all 12 `record_contradiction()` call sites across `crt_rag.py`, `crt_memory.py`, `crt_ledger.py`, `crt_critic.py`, and `routes/chat.py` with real BDG cascade propagation via `LiveBDG.singleton()`
- **Provisional authority gate** — new memory assertions excluded from retrieval results until contradiction check passes, preventing unverified claims from influencing responses
- **Slot demotion block** — prevents governance from downgrading already-classified intents during slot filling

### Fix
- **Cascade paper theorems patched** — all 6 theorems (4.1-4.4 + Prop 5.4) fixed: definitional contradictions resolved, multi-parent gap closed, wrong reduction replaced, fake proof rewritten with real BDG validation data (599 nodes from production)
- **Time awareness** — system prompt now includes current date/time for temporal reasoning
- **last_accessed tracking** — memory retrieval now updates `last_accessed` timestamps correctly
- **Profile trust gate** — profile/identity memories bypass low-trust filtering
- **Auto-resolve removal** — removed automatic contradiction resolution that was silently resolving held contradictions
- **Real memory IDs** — memory lookups use actual DB IDs instead of fabricated ones
- **Retrieval prefix stripping** — removes `[MEMORY_DB]` and similar prefixes before embedding search
- **NLI critic fix** — critic no longer blocks on NLI comparison failures

### Infra
- **New file**: `personal_agent/cookie_orchestrator.py`
- **New file**: `personal_agent/code_intel.py`
- **New file**: `personal_agent/agent_run_log.py`
- **New file**: `papers/cascade_complexity/real_bdg.py` — real BDG validation against production data
- **Modified file**: `personal_agent/memory_graph.py` — BeliefDependencyGraph class + LiveBDG singleton
- **Modified file**: `routes/chat.py` — cascade wiring, provisional gate, orchestrator routing

---

## v3.7 — March 29, 2026

Alias Protection & Retrieval Overhaul — memory retrieval hardened against alias fragmentation. 36 aliases mapped across 17 critical memories with canonical collapse at query time. Belief scores computed from real data instead of hardcoded values. Mac M2 Ollama offload cuts intent classification from 120s to 1-3s.

### Feature
- **Alias protection system** — new `memory_aliases` table with risk scoring and alias generation (terse/question/perturb strategies). Canonical collapse in `retrieve_memories()` with backfill for 17 critical memories (36 aliases total)
- **Computed belief scores** — belief scores derived from retrieval count + average trust instead of hardcoded 0.15/0.4
- **Mac M2 Ollama offload** — intent classification routed to Mac at `192.168.1.146:11434` via `OLLAMA_BASE_URL`. Latency dropped from 120s to 1-3s
- **Dedicated intent model** — `llama3.2:latest` for routing (2GB) instead of `qwen3:14b` (9.3GB). Set via `CRT_INTENT_MODEL` env var
- **Retrieval logging** — tagged log lines: `[MEMORY_DB]`, `[ENGINE]`, `[RETRIEVAL]`, `[ALIAS_COLLAPSE]`, `[RETRIEVAL_RAG]` for full pipeline visibility
- **GPT variance baseline** — established 0.223 mean pairwise similarity for GPT-4o-mini (vs Aether 0.345), 5K vectors collected

### Fix
- **Startup prewarm** — skips heavy generation model pull when dedicated intent model is configured
- **UTF-8 stdout** — catches `UnicodeEncodeError` on Windows cp1252 console (emoji/arrow characters)
- **Boilerplate purge** — 21 entries deprecated (8 "helpful assistant" patterns + 13 self_model contamination entries)
- **Mood indicator removed** from Electron UI

### Infra
- **Modified file**: `personal_agent/crt_rag.py` — alias collapse, retrieval logging
- **Modified file**: `personal_agent/crt_memory.py` — alias table, computed belief scores
- **Modified file**: `personal_agent/litellm_client.py` — Mac offload routing
- **Modified file**: `personal_agent/llm_intent_router.py` — dedicated intent model support
- **New env vars**: `OLLAMA_BASE_URL`, `CRT_INTENT_MODEL`

---

## v3.6 — March 28, 2026

Robustness Sweep & Immune Agents — three-model variance experiment confirms distinct failure regimes. Five immune agents (31/31 tests) enforce CRT's epistemic laws at runtime. Production governance validated against real experiment data.

### Feature
- **Three variance regimes confirmed** (16/16 robust across all models):
  - Qwen3 = Selective Fracture (mode-splitting on factual domains)
  - Mistral = Selective Spread (gradient erosion, no mode splits)
  - DeepSeek = Uniform Softness (fog pattern, even degradation)
  - GPT-4o-mini = Damped (provisional, runner fixed to 47 req/s)
- **Five immune agents** (`personal_agent/immune_agents/`), all 31/31 tests passing:
  - `SpeechLeakDetector` — speech cannot upgrade belief
  - `TemplateDetector` — low variance ≠ confidence
  - `PrematureResolutionGuard` — preserve contradictions before resolution
  - `MemoryCorruptionGuard` — degraded reconstruction cannot overwrite originals
  - `GapAuditor` — outward confidence bounded by internal support
- **Density analysis** — 10 metrics computed per model (cluster compactness, mass distribution, silhouette scores, template similarity). Three-metric table (spread, modes, template similarity across domains)
- **Governance validation** — 5/6 checks passed on real Qwen3 data (blind spot: assertive template collapse identified for future fix)
- **3D belief splat viewer** — Three.js visualization of variance distributions with temperature animation

### Docs
- **New file**: `docs/whitepaper.html` — CRT white paper
- **New file**: `docs/immune-agents.html` — immune agent architecture documentation
- **New file**: `docs/variance-probing.html` — variance probing methodology and results
- **New file**: `personal_agent/immune_agents/ARCHITECTURE.md` — 5 laws, 5 agents, coordination layer, two-axis taxonomy

### Infra
- **New directory**: `personal_agent/immune_agents/` (5 agent modules + `__init__.py`)
- **New file**: `belief_variance_experiment/analyze_density.py`
- **Modified file**: `belief_variance_experiment/runner.py` — GPT-4o-mini batching fix (12.49s→47 req/s)

---

## v3.5 — March 28, 2026

Electron Desktop App & Feature Sprint — 20+ features shipped in a single session. Frameless Electron shell with system tray, heartbeat learning loop, ambient mode, MCP server with 12 tools, clipboard monitoring, file drag-and-drop, and a comprehensive set of pipeline optimizations.

### Feature
- **Electron shell** (`electron/`) — frameless window with custom titlebar, system tray with status icons (green/amber/red), global hotkey `Ctrl+Space`, single instance lock, backend lifecycle manager (health polling, auto-restart up to 5x, graceful shutdown)
- **Heartbeat learning** (`personal_agent/heartbeat_learning.py`) — extracts facts from conversations, deduplicates via cosine similarity ≥ 0.82, stores as provisional beliefs
- **Contradiction detection** — triggers on `drift_meaning ≥ 0.28` combined with `similarity ≥ 0.4`
- **Training log persistence** (`personal_agent/training_log.py`) — JSONL per day, logs all 6 response paths
- **Clipboard monitoring** (`electron/clipboard-monitor.js`) — polls every 2s, OS notification on change, tray toggle
- **File drag-and-drop** (`routes/ingest.py`) — supports txt/md/py/json/pdf, chunked storage into memory
- **Ambient mode** (`routes/ambient.py`, `electron/ambient-monitor.js`) — screen capture + vision analysis at 60s intervals
- **Aether MCP server** (`personal_agent/aether_mcp_server.py`) — 12 tools in 4 tiers via FastMCP protocol
- **Enhanced model selector** — inline accordion in frontend, dynamically populated from `/api/tooling/models`
- **Context feed** (`personal_agent/context_feed.py`) — aggregates recent context for system prompt enrichment
- **Reminder fast-path** — deterministic time parsing before agent loop, saves full LLM round-trip
- **Correction handler** — dual memory search on correction, trust demotion to 0.15 for contradicted entries

### Fix
- **Identity fix** — "You are Aether, deployed using Claude" across all system prompts (was inconsistent)
- **Self-model reset** — nuked fabricated self-model entries, replaced with "still calibrating" placeholders
- **Plan engine skip** — conversational messages bypass plan creation heuristic, saves 2-5s
- **Governance skip** — conversational intents bypass OpenAI slot classification
- **CRT critic opinion skip** — opinion-type messages skip contradiction gate

### Infra
- **New files**: `personal_agent/heartbeat_learning.py`, `training_log.py`, `aether_mcp_server.py`, `context_feed.py`
- **New files**: `electron/clipboard-monitor.js`, `ambient-monitor.js`
- **New files**: `routes/ambient.py`, `routes/ingest.py`
- **Modified file**: `electron/main.js` — frameless config, tray integration, hotkey binding
- **Modified file**: `crt_api.py` — static file serving for SPA

---

## v3.4 — March 27, 2026

LLM Belief Variance Experiment — three-model robustness study (Qwen3 7.5K responses, Mistral ~81%, GPT-4o-mini in progress). Domain inversion finding: factual topics 10x more susceptible to temperature-induced drift than moral topics. Adaptive temperature governance framework. Consciousness mapping validates CRT satisfies Higher-Order Theory + Predictive Processing criteria.

### Feature
- **Variance experiment runner** (`belief_variance_experiment/runner_ollama.py`) — checkpoint/resume, multi-temperature sweep (0.0-1.5), 10 prompts × 10 completions per temperature per model
- **Domain inversion finding** — factual topics show 10x more variance susceptibility than moral topics across all models
- **Learned hedging detection** — temperature-invariant hedge templates identified (models hedge identically regardless of temperature setting)
- **Adaptive temperature governance** — proposed T-policy framework: lock to T=0 for factual, allow range for opinion, flag inversion domains
- **Contradiction classifier** (`belief_variance_experiment/classify_contradictions.py`) — DBSCAN clustering for held contradictions vs variants vs drift
- **3D WebGL belief splat viewer** (`belief_variance_experiment/viewer.py`) — Three.js visualization with temperature animation slider

### Research
- **Motive theory** — contradiction reframed as engine of agency, not error to resolve
- **Consciousness mapping** — CRT architecture shown to satisfy Higher-Order Theory (belief about beliefs) + Predictive Processing (prediction error minimization via contradiction detection)
- **Business framing** — diagnostic probe, library, therapy applications, EU AI Act compliance angle

### Infra
- **New directory**: `belief_variance_experiment/` with runner, analyzer, classifier, viewer
- **New file**: `belief_variance_experiment/FINDINGS.md`

---

## v3.3 — March 27, 2026

Electron Shell — standalone desktop wrapper for the Aether frontend. FastAPI static file serving enables SPA mode. Backend lifecycle management with health polling and auto-restart.

### Feature
- **Electron desktop shell** (`electron/main.js`) — BrowserWindow loading local FastAPI server, preload script for IPC
- **Backend lifecycle** (`electron/backend.js`) — spawns `python crt_api.py`, health check polling at 10s intervals, auto-restart on failure (max 5 retries)
- **System tray** (`electron/tray.js`) — status icons (green=healthy, amber=connecting, red=down), right-click menu with show/quit
- **FastAPI static serving** — SPA routes + asset serving from `frontend/dist/` added to `crt_api.py`

### Fix
- **Self-referential verbosity** — responses about Aether's own capabilities capped at 300 tokens / 3-5 sentences
- **Health check flapping** — requires 3 consecutive failures before marking unhealthy (was 1)

### Infra
- **New files**: `electron/main.js`, `backend.js`, `tray.js`, `preload.js`
- **Modified file**: `crt_api.py` — static file serving routes

---

## v3.2 — March 26, 2026

Deep Research Sprint — 8 research modules built and tested in a single session. Cascade complexity paper drafted with formal BDG definitions, 5 theorems, and empirical validation. Active inference module enables uncertainty-driven clarification requests.

### Feature
- **Disposition classifier** (`personal_agent/disposition_classifier.py`) — 18/18 tests: classifies contradictions as resolvable/held/evolving/contextual
- **Memory graph** (`personal_agent/memory_graph.py`) — NetworkX-based belief dependency graph with CONTRADICTS/SUPERSEDES/RELATED_TO edge types, cascade propagation, firewall support, cycle detection
- **Temporal governance** (`personal_agent/temporal_governance.py`) — type-dependent decay curves, recency scoring for retrieval ranking
- **Memory splats** (`personal_agent/memory_splats.py`) — Gaussian belief representation with covariance + confidence (memories as distributions, not points)
- **Predictive contradiction** (`personal_agent/predictive_contradiction.py`) — convergence trend detection, urgency classification for proactive contradiction handling
- **Belief topology** (`personal_agent/belief_topology.py`) — persistent homology via ripser, detects belief restructuring events and avoidance patterns (H1 persistence=0.28)
- **Belief/speech separation** (`personal_agent/belief_speech_engine.py`) — auditable gap tracking between internal belief state and external speech, policy-driven disclosure rules
- **Information geometry** (`personal_agent/info_geometry.py`) — Fisher-Rao distance metric, per-dimension decomposition reveals hidden confidence differences (3.16x separation)
- **Active inference** (`personal_agent/active_inference.py`) — uncertainty scanning across belief space, generates clarification requests when expected free energy exceeds threshold
- **Cascade complexity paper** (`papers/cascade_complexity/cascade_paper.md`) — 8 sections, formal definitions 3.1-3.6, theorems 4.1-4.4, conjecture 4.5 (NP-hardness). All 5 experiments pass. Damping curve matches Theorem 4.3 exactly (depth 14 vs bound 15)

### Research
- **Key finding**: two-mode geometry — static beliefs cluster by cosine similarity, dynamic beliefs separate by overlap trend
- **Fisher metric reranking** — reranks retrieval results by certainty, revealing 3.16x hidden confidence differences
- **Belief/speech gap** — average magnitude 0.38 across test corpus, fully auditable

### Infra
- **New files**: `disposition_classifier.py`, `temporal_governance.py`, `memory_splats.py`, `predictive_contradiction.py`, `belief_topology.py`, `belief_speech_engine.py`, `info_geometry.py`, `active_inference.py`
- **New file**: `papers/cascade_complexity/cascade_paper.md`
- **New file**: `papers/cascade_complexity/experiments.py` — 5 empirical validations
- **New file**: `papers/cascade_complexity/np_hardness_proof.md` — 3 reduction attempts documented
- **Modified file**: `personal_agent/memory_graph.py` — BeliefDependencyGraph class

### Docs
- **New file**: `docs/CRT_RESEARCH_LOG.md`
- **New file**: `docs/continuity-blind.html` — continuity blind contradiction findings
- **New file**: `research/continuity_blind_contradiction/FINDINGS.md`

---

## v3.1 — March 24, 2026

Agentic Tool Loop — LLM-driven ReAct loop for the main chat pipeline. Replaces the classify-once-execute-blind pattern with a true iterative tool-calling loop where the LLM sees intermediate results and decides what to do next. The LLM calls tools, observes results, and repeats until the task is complete. Multi-step compound requests ("read this file and copy it to X") now work in a single user message without manual intervention.

### Currently Working On
- **Ollama JSON 400 on tool continuation** — after checkpoint confirmation, Ollama's parser chokes on tool result payloads containing curly braces (`"Value looks like object, but can't find closing '}' symbol"`). File content with `{`/`}` breaks the JSON parser. Needs content escaping or truncation before re-sending to Ollama.
- **Tooling settings tab** — new Settings tab to configure per-tool model selection and fallback policy. Controls which model (local/cloud) handles which tool, and what happens when the primary model fails.

### Feature
- **AgentToolLoop** (`personal_agent/agent_tool_loop.py`, ~530 lines) — core loop engine: sends conversation + tool definitions to the LLM, processes tool calls, appends results to context, repeats until LLM returns text or hits max iterations. Supports both local Ollama and cloud LLMs via `chat_with_tools()`. Yields SSE events in real-time for the frontend
- **Checkpoint integration** — Layer 3+ tools (file_write, shell_exec, git_exec) still require user confirmation inside the loop. On checkpoint, the loop pauses, stores state in the session DB, and resumes on the next message after user confirms/denies. Denied actions are communicated back to the LLM so it can adapt
- **Tool execution bridge** — unified `_execute_tool()` function that dispatches to the existing tool implementations (file_tools, shell_tools, web_tools, etc.) with action receipt logging
- **Loop resume on confirmation** — when a user confirms a checkpoint from the agent loop, the system executes the confirmed tool, then continues the loop with the result in context. Supports chained checkpoints (tool A confirmed → tool B needs confirmation → etc.)
- **Runtime config** — new `agent_loop` section: `enabled` (bool, default False), `model` (auto/local/cloud), `max_iterations` (1-25, default 10), `show_thinking` (bool, default True)
- **Graceful fallback** — if the agent loop fails or is disabled, falls through to the legacy classify → plan → execute path automatically
- **2 new SSE event types** — `agent_loop_start` (emits available tools + max iterations) and `agent_loop_complete` (emits tools used, iteration count, total duration)
- **Frontend support** — new event types added to StreamEventType, StreamCallbacks, and event handler switch in api.ts. Agent loop events render using existing tool_start/tool_result/agent_checkpoint UI components

### Infra
- **New file**: `personal_agent/agent_tool_loop.py` (~530 lines)
- **Modified file**: `routes/chat.py` — agent loop path inserted before legacy task route (~120 lines), checkpoint resume handler for agent loop state (~130 lines)
- **Modified file**: `personal_agent/runtime_config.py` — new `agent_loop` config section with 4 settings
- **Modified file**: `frontend/src/lib/api.ts` — 2 new event types, 2 new callbacks, 2 new event handler cases

### Docs
- **New file**: `docs/AGENT_LOOP.md` — architecture, configuration, SSE events, testing guide

---

## v3.0 — March 24, 2026

Browser Agent — Playwright-based web automation with DOM-first intelligence. The agent can navigate websites, read page content, click links, fill forms, extract information, and perform web searches autonomously. Uses the same ReAct pattern as the desktop agent (observe → think → act → verify) but reads the DOM directly instead of relying on vision for most tasks. Full safety gates mirror the desktop system.

### Feature
- **BrowserController** (`personal_agent/browser_control.py`, ~400 lines) — Playwright wrapper: navigation, DOM reading (page text, links, form fields, interactive elements), actions (click, fill, select, scroll), screenshots, persistent browser context (cookies/sessions saved to `data/browser_profile/`)
- **BrowserAgent** (`personal_agent/browser_agent.py`, ~500 lines) — ReAct loop: observe DOM state → LLM decides next action → execute via BrowserController → verify result. Safety gates: blocked domains (banking), blocked form fields (passwords/CC/SSN), confirmation for submissions/purchases, rate limiting (30 actions/min, 10 navigations/min, 5 submissions/min)
- **Two new tools**: `web_browse` (open-ended browser tasks, layer 3, medium checkpoint) and `web_search` (quick search queries, layer 2, no checkpoint)
- **DOM-first intelligence** — most tasks use structured DOM reading (text, selectors, form fields) instead of vision. Vision provider available as fallback for complex visual layouts
- **Sync bridge** — async Playwright bridged to sync TaskAgent via `asyncio.to_thread()`, same pattern as desktop agent
- **10 integration points in task_agent.py** — regex patterns, gate logic, classification, slot filling, acknowledgments, intent-tool mapping, plan building, execution dispatch, deterministic summaries, memory persistence
- **Browser settings** — 8 settings in new Browser tab: enabled toggle, headed/headless mode, engine (chromium/firefox/webkit), session persistence, confirmation mode (all/submissions/never), max steps, domain allowlist, domain blocklist
- **SSE events** — browser_start, browser_navigate, browser_action, browser_screenshot, browser_extract, browser_done, browser_error, browser_confirm

### Infra
- **New file**: `personal_agent/browser_control.py` (~400 lines)
- **New file**: `personal_agent/browser_agent.py` (~500 lines)
- **Modified file**: `personal_agent/tool_registry.py` — 2 new tools (web_browse, web_search)
- **Modified file**: `personal_agent/task_agent.py` — 10 integration points (~200 lines added)
- **Modified file**: `routes/auth.py` — 8 browser settings in whitelist
- **Modified file**: `frontend/src/pages/SettingsPage.tsx` — Browser tab with all 8 settings
- **Modified file**: `.gitignore` — `data/browser_profile/`
- **New dependency**: `playwright>=1.40.0` + `playwright install chromium`

---

## v2.9.3 — March 24, 2026

Task Plan System — multi-step work plans that persist across messages and threads. Plans break complex requests into concrete steps, track progress, and advance automatically as tools execute. Three creation paths: user describes work (Aether structures it), complex request triggers a plan proposal, or manual creation via the Plans UI. Plans are linked to chat threads with a compact progress widget.

### Feature
- **Plans database layer** — 3 new SQLite tables (`plans`, `plan_steps`, `thread_plan_links`) in ThreadSessionDB with 15 CRUD methods: create/get/list/update/delete plans, add/get/update/delete/reorder steps, link/unlink/get thread-plan associations, advance plan cursor
- **Plans REST API** (`routes/plans.py`) — 12 endpoints: full CRUD for plans and steps, thread linking, step reordering. Route ordering fix: `/thread/{thread_id}` registered before `/{plan_id}` to avoid path conflicts
- **PlanEngine** (`personal_agent/plan_engine.py`) — plan generation from natural language via LLM, step advancement after tool execution, user-input handling for `waiting_input` steps, progress summary generation. Keyword + multi-action + sentence-count heuristics for `should_create_plan()`
- **Chat pipeline integration** — after tool execution in task_agent.py, active plan steps auto-advance. Emits `plan_update` and `plan_complete` SSE events with progress metadata
- **Jobs page split** — renamed to "Plans & Jobs". New `PlansSection` component at top with plan list (expandable steps, progress bars, status badges), "New Plan" form (title, description, dynamic step list with add/remove), and plan actions (pause/resume/archive/delete). Existing Jobs section preserved below
- **PlanWidget** (`frontend/src/components/PlanWidget.tsx`) — compact collapsible plan display for in-chat use. Shows SVG progress ring with percentage, plan title, current step name. Expands to show all steps with status icons (✓ ► ? ✗ — ○), descriptions, tool badges, and plan metadata
- **Plan settings** — 3 new settings in Behavior tab: auto-plan threshold (always_ask / auto_simple / auto_all), plan notifications toggle, plan widget chat visibility toggle
- **3 new SSE event types** — `plan_proposal`, `plan_update`, `plan_complete` added to StreamEventType

### Infra
- **New file**: `routes/plans.py` (240 lines)
- **New file**: `personal_agent/plan_engine.py` (195 lines)
- **New file**: `frontend/src/components/PlanWidget.tsx` (150 lines)
- **Modified file**: `personal_agent/db_utils.py` — 3 tables + 15 methods (~300 lines added)
- **Modified file**: `routes/register.py` — plans_router registered (priority position)
- **Modified file**: `routes/models.py` — 7 Pydantic models (CreatePlanRequest, PlanResponse, StepResponse, UpdatePlanRequest, UpdateStepRequest, ReorderStepsRequest, CreateStepRequest)
- **Modified file**: `routes/auth.py` — 3 new settings keys in whitelist (plan_auto_threshold, plan_notifications, plan_chat_visibility)
- **Modified file**: `personal_agent/task_agent.py` — plan advancement after tool execution (~25 lines)
- **Modified file**: `frontend/src/pages/JobsPage.tsx` — PlansSection component + page rename (~230 lines added)
- **Modified file**: `frontend/src/pages/SettingsPage.tsx` — Plans & Workflow section in Behavior tab
- **Modified file**: `frontend/src/lib/api.ts` — Plan/PlanStep types, 12 API client functions, 3 new SSE event types (~150 lines added)

---

## v2.9.2 — March 24, 2026

Full settings expansion — user-facing controls for every major subsystem. Reorganized the Settings page from 6 tabs to 8 with new Heartbeat and Behavior tabs, fixed silent-drop bugs, and wired 20+ new setting keys end-to-end (backend defaults, API whitelist, frontend UI).

### Feature
- **Heartbeat tab** — enable/disable heartbeat, configure interval (300-86400s), active hours window, news monitoring with topic list, curiosity engine toggle
- **Behavior tab** — greeting enable/style (time_based, time_of_day, simple), conflict warning toggle, provenance footer toggle with world-check sub-toggle, background jobs master toggle with sub-controls for auto-resolve contradictions, auto web research (with privacy warning), auto learning
- **Web search settings** — max results (1-20) and search region selector (US, UK, CA, AU, DE, FR, JP)
- **Model Selection section** (Advanced tab) — generation mode picker (local/cloud_openai/cloud_claude), OpenAI model ID input, Claude model ID input, routing LLM model override
- **Response Synthesis** moved into Advanced pipeline controls section alongside Bypass CRT and Enable Tooling

### Fix
- **`preferred_nickname` and `agent_name` silently dropped** — added both to API whitelist in `routes/auth.py`. Previously SettingsPage sent these but the backend rejected them as unknown keys
- **4 API-whitelisted keys had no UI** — `generation_mode`, `cloud_model_openai`, `cloud_model_claude`, `routing_llm_model` now have controls in the Advanced > Model Selection section
- **`synthesis_enabled` toggle logic** — fixed true/false handling to match other boolean toggles

### Polish
- Extracted reusable `SectionCard` component for consistent card styling across all tabs
- Settings tabs use `flex-wrap` to handle narrow viewports

### Infra
- **Modified file**: `auth.py` — 20 new keys in `CLOUD_SETTING_DEFAULTS`
- **Modified file**: `routes/auth.py` — 20 new keys in `allowed_keys` whitelist
- **Rewritten file**: `frontend/src/pages/SettingsPage.tsx` — 8 tabs (Profile, Cloud, Desktop, Heartbeat, Behavior, Advanced, Facts, Account)

---

## v2.9.1 — March 24, 2026

Response Synthesis Layer — the LLM now interprets tool results before responding instead of dumping raw output. When you say "read this file and tell me about it," the system reads the file AND thinks about what it found. Synthesis mode per tool (always/smart/on_request/never) so `git status` stays raw but `project_scan` gets intelligent interpretation. Hallucination guards constrain the LLM to only reference actual tool results.

### Feature
- **ResponseSynthesizer** (`personal_agent/response_synthesis.py`) — `should_synthesize()` decides per-request based on tool's synthesis_mode + user intent signals (keywords: "tell me about", "summarize", "explain", "what does this mean"). `synthesize()` runs LLM pass with tool results + user message, producing a natural response
- **synthesis_mode field** on ToolDefinition — `"always"` (project_scan, memory_recall), `"smart"` (file_read, system_info, fetch_url), `"on_request"` (dir_list), `"never"` (shell_exec, git_exec, file_write, desktop_action, commitments, generate_content)
- **TaskAgent rewired** — deterministic if/elif response chain replaced with synthesis-or-fallback path. Existing formatting moved to `_format_deterministic_response()` as fallback. If synthesis fails, falls through silently
- **Synthesis toggle** — `synthesis_enabled` setting (boolean, default true) in Advanced tab. Allows user to disable synthesis and get raw tool output
- **Enhanced conversational prompt** — dot-connecting guidance and interpretation nudge added to reasoning system prompt

### Fix
- **Windows emoji crash** — `_safe_print()` helper in chat.py catches `UnicodeEncodeError` on Windows console output

### Infra
- **New file**: `personal_agent/response_synthesis.py`
- **Modified file**: `personal_agent/tool_registry.py` — `synthesis_mode` field on ToolDefinition
- **Modified file**: `personal_agent/task_agent.py` — synthesis pass replaces deterministic chain
- **Modified file**: `routes/auth.py` — `synthesis_enabled` in settings whitelist
- **Modified file**: `frontend/src/pages/SettingsPage.tsx` — synthesis toggle in Advanced tab
- **Modified file**: `personal_agent/reasoning.py` — enhanced conversational prompt
- **Modified file**: `routes/chat.py` — `_safe_print()` for Windows

---

## v2.9 — March 24, 2026

Hybrid LLM Intent Router — the system's "brain" for understanding what you want. Replaces rigid regex-only classification with a three-tier system: regex (instant, free) → local LLM via Ollama (fast, free) → cloud LLM escalation (smart, costs tokens). Self-improving: successful LLM-routed classifications are logged, and after enough similar patterns cluster, new regex rules are auto-generated so common requests graduate to the instant tier over time.

### Feature
- **Tool Registry** (`personal_agent/tool_registry.py`) — unified `ToolDefinition` dataclass with name, description, parameters, access_layer, checkpoint_tier, examples, intent_type. 17 tools registered. `to_llm_schema()` generates OpenAI-compatible function-calling schemas. `get_routing_schemas()` for LLM routing, `get_all_llm_schemas()` for full set
- **LLMIntentRouter** (`personal_agent/llm_intent_router.py`) — sends user message + tool schemas to LLM for function-calling-based routing. System prompt constrains to tool selection only. `_build_slots()` normalizes tool arguments into TaskIntent format. File path extraction from `[file: X]` patterns, quoted paths, bare paths. Factory functions: `create_local_router()`, `create_cloud_router()`
- **Three-tier hybrid classifier** in `classify_intent_hybrid()` — Tier 1: regex (confidence ≥ 0.90, instant). Tier 2: local LLM router (confidence ≥ 0.70, ~200ms). Tier 3: cloud escalation (hybrid mode only, confidence ≥ 0.60). Fallback: embedding classifier (legacy). Final: conversational
- **Route Learning** (`personal_agent/route_learning.py`) — `RouteLearningDB` with SQLite tables `route_log` + `learned_patterns`. Logs every LLM-routed classification. `get_pattern_candidates()` finds clusters of 5+ similar messages. `generate_regex_from_examples()` uses LLM or heuristic to create regex patterns. `review_route_patterns()` called from heartbeat periodically
- **Routing mode setting** — `routing_mode` (local_only / cloud_only / hybrid) in Settings > Advanced with radio buttons and descriptions
- **Heartbeat integration** — step 10 in heartbeat_executor runs `review_route_patterns()` for periodic pattern mining

### Infra
- **New file**: `personal_agent/tool_registry.py`
- **New file**: `personal_agent/llm_intent_router.py`
- **New file**: `personal_agent/route_learning.py`
- **Modified file**: `personal_agent/task_agent.py` — `classify_intent_hybrid()` rewritten with 3-tier flow
- **Modified file**: `personal_agent/heartbeat_executor.py` — route pattern review step
- **Modified file**: `routes/auth.py` — `routing_mode`, `routing_llm_model` in settings whitelist
- **Modified file**: `frontend/src/components/SettingsModal.tsx` — Intent Routing section with radio buttons

---

## v2.8 — March 24, 2026

Telegram full-pipeline integration. The Telegram channel now uses `/api/chat/stream` (SSE) instead of `/api/chat/send`, giving it the complete task pipeline: intent classification, sub-agent orchestration, capability re-route, intuition check, and trust propagation. Previously Telegram was conversational-only — asking "what apps are open?" would get an LLM guess instead of actually running system_info.

### Feature
- **CRTBridge stream mode** (`channels/base.py`) — new `_send_stream()` method consumes SSE events from `/api/chat/stream`. Parses all event types: intent_preview, agent_checkpoint, task_acknowledged, tool_start/result, subtask_start/done, orchestration_done, token, task_done, done, error
- **Two-stream checkpoint handling** — when a checkpoint gate fires, the bridge auto-confirms low-risk intents (system_info, dir_list, git_action, file_read) by sending a follow-up "yes" stream and consuming the task result. High-risk intents (file_write, shell_exec, desktop_action) can be gated via an optional `checkpoint_callback`
- **Task visibility in Telegram** — task responses show a `🔧 intent_type` header. Multi-agent orchestrations show `🔧 N subtasks · trust XX%`
- **Graceful fallback** — if the stream endpoint fails, the bridge falls back to `/api/chat/send` (conversational-only) automatically
- **ChannelResponse enrichment** — new fields: `route`, `intent_type`, `task_steps`, `orchestration` for downstream visibility

### Infra
- **Modified file**: `channels/base.py` (rewritten, ~280 lines)
- **Modified file**: `channels/telegram_bot.py` (task header in replies)
- **Dependency**: `python-telegram-bot[job-queue]` now installed with apscheduler support

---

## v2.7 — March 24, 2026

Intuition Check — lightweight LLM side-channel for situational awareness. A gpt-4o-mini "quick check" that fires at three moments: ambiguous input (clarify before routing), post-task completion (suggest next step from context), and reconnect after idle (welcome back with open task context). Runs in ~150ms, doesn't block the main pipeline, and degrades gracefully when cloud is unavailable.

### Feature
- **IntuitionCheck** (`personal_agent/intuition_check.py`) — singleton class with three public methods: `clarify()`, `suggest_next()`, `reconnect()`. Each makes a single gpt-4o-mini call with a focused system prompt and returns structured JSON
- **Clarify check** — fires when intent classifier returns conversational with confidence < 0.75. Asks the intuition check if the message needs clarification before routing. Emits `intuition_check` SSE event with the question
- **Post-task suggest check** — fires after every task_done event. Passes completed task metadata + open tasks to the intuition check, gets back a natural follow-up suggestion. Embedded in the `done` event metadata as `intuition_check.message`
- **Reconnect check** — fires before the conversational pipeline when `last_active` is >5 minutes old. Generates a context-aware welcome-back message referencing open tasks. Emits `intuition_check` SSE event
- **`get_last_message_ts()`** — new method on `ThreadSessionDB` to read idle duration from the existing `last_active` column

### Infra
- **New file**: `personal_agent/intuition_check.py` (270 lines)
- **CloudFeatureService** — 3 new daily limit categories: `intuition_check_clarify` (20/day), `intuition_check_suggest` (20/day), `intuition_check_reconnect` (10/day)
- **New SSE event type**: `intuition_check` with `tap_action` metadata field (clarify | suggest | reconnect)

---

## v2.6 — March 24, 2026

Sub-agent interface + delegation protocol (Sprint 8). Aether can now decompose multi-intent requests into independent subtasks and run them in parallel via specialized sub-agents. Each agent wraps existing tool functions, carries trust metadata through the execution chain, and logs receipts tied to a parent orchestration. The frontend shows real-time orchestration progress with per-agent status tracking.

### Feature
- **SubAgent protocol** (`personal_agent/sub_agents.py`) — abstract base class with async `execute()`, trust computation, receipt logging. 8 concrete agents: SystemInfoAgent, FileAgent, ShellAgent, GitAgent, WebFetchAgent, DesktopToolAgent, GenerationAgent, CommitmentAgent
- **TaskOrchestrator** (`personal_agent/orchestrator.py`) — decomposes multi-intent messages into a dependency graph. Independent subtasks run concurrently via `asyncio.gather()`. Dependent subtasks chain sequentially with output piping
- **Dependency detection** — sequential language markers ("then", "after that") make tasks chain. Structural rules: generate_content → file_write, url_fetch → service_action
- **Trust propagation** — CRT weakest-link model: `propagated_trust = min(confidence, source_trust)`. Orchestration merged trust = minimum across all branches. Per-agent confidence constants from 0.95 (SystemInfo) down to 0.60 (Generation)
- **`run_stream_async()`** — async generator on CRTTaskAgent using the orchestrator. Events stream via `asyncio.Queue` to the caller
- **Async bridge** — multi_intent tasks in chat.py spawn a background thread with its own event loop. Events bridge to the sync SSE generator via thread-safe queue. Single-intent tasks use existing sync path with zero overhead
- **4 new SSE events** — `orchestration_start` (subtask manifest), `subtask_start` (agent begins), `subtask_done` (agent finishes with duration + status), `orchestration_done` (merged trust + completion stats)
- **Orchestration UI** — AgentThinkingStrip shows subtask rows: agent name, intent type, live status indicator (pending ○ / running ⟳ / ok ✓ / error ✗), duration, and merged trust percentage on completion
- **Agent receipts** — `action_receipts` table extended with `agent_name` and `orchestration_id` columns. `log_orchestration_receipt()` creates parent receipt tying all sub-agent receipts together

### Infra
- **New files**: `personal_agent/sub_agents.py` (480 lines), `personal_agent/orchestrator.py` (260 lines)
- **Schema migration**: `action_receipts.db` auto-adds `agent_name` and `orchestration_id` columns on startup

---

## v2.5 — March 24, 2026

Belief synthesis + volatility-gated context (Sprints 9 & 10). The intelligence layer that makes Aether understand the *shape* of what it knows about you — not just individual facts, but themes, trajectories, and tensions.

### Feature
- **Belief synthesis engine** (`personal_agent/belief_synthesis.py`) — answers worldview questions from compressed belief trajectories. Three synthesis modes:
  - **Thematic**: "What do I care about?" → clusters hundreds of memories into themes (career, technology, values, etc.) via agglomerative clustering on 384D embeddings
  - **Trajectory**: "How have I changed?" → temporal belief analysis showing preference/opinion drift over time per slot, detects oscillation vs monotonic change
  - **Contradiction-aware**: "What are my contradictions?" → surfaces unresolved tensions from the contradiction ledger, frames complexity as a feature
- **Synthesis query classifier** — 25+ regex patterns across three categories. Replaces the old `_is_synthesis_query()` simple pattern matcher. Backward compatible with existing patterns
- **Trust-weighted clustering** — cluster centroids weighted by memory trust scores. Cluster labels auto-generated from dominant fact slots or keywords
- **Representativeness scoring** — measures how well synthesis covers the evidence corpus, penalized by contradiction density
- **Deterministic fallback** — when cloud LLM unavailable, generates structured bullet-point summaries instead of prose
- **Volatility-gated context** (`personal_agent/volatility_context.py`) — dynamic context budget allocation based on memory uncertainty:
  - Volatile memories (V(t) > 0.6) always get full text in prompts
  - Stable high-trust facts (τ > 0.85, V < 0.15) compressed to slot=value pairs
  - Middle tier gets first-sentence summaries
  - Budget overflow gracefully demotes lowest-priority allocations
- **Proactive volatility alerts** — when user recently changed their mind about something (resolved contradiction in last 7 days), system proactively surfaces it: "You recently changed your mind about [slot]"
- **Volatility re-ranking** — retrieved memories boosted by volatility in ranking, so uncertain facts get more attention
- **Volatility annotations in prompts** — volatile/recently-changed memories tagged in the reasoning prompt so the LLM hedges appropriately

### API
- `POST /api/synthesis` — run thematic/trajectory/contradiction synthesis on full memory corpus
- `GET /api/belief-trajectory/{slot}` — temporal trajectory for a specific fact slot
- `GET /api/context-budget?query=...` — inspect context budget allocation for debugging
- `GET /api/memory/{id}/volatility` — volatility profile for a single memory
- `GET /api/volatile-memories` — list memories with V(t) above threshold

### Integration
- `crt_rag.py` synthesis detection upgraded from simple string matching to subtype classifier (thematic/trajectory/contradiction_aware)
- Thematic synthesis uses k=30 retrieval (up from k=15) to gather broader belief landscape
- `reasoning.py` prompt builder annotates volatile memories with [VOLATILE] / [RECENTLY CHANGED] tags
- `memory_compression.py` gains `compute_volatility_from_item()` convenience wrapper
- Synthesis results include structured metadata: cluster count, trajectory count, tension count, representativeness

---

## v2.4 — March 24, 2026

Task triage & orchestration layer (Sprint 12). Adds a "pause to think" step between message classification and tool execution. The system now acknowledges tasks with a real natural-language message before working, and the UI pulses the input area to indicate activity. Fixes the silent routing failure where embedding errors killed the entire classification.

### Feature
- **Task triage layer** (`triage_message()` in `task_agent.py`) — determines task category, planning requirements, tool needs, and generates a natural acknowledgment before execution begins
- **TriageResult dataclass** — structured triage output: category, requires_planning, estimated_steps, tools_needed, acknowledgment
- **Task acknowledgment SSE event** — new `task_acknowledged` event emitted before task execution. Frontend renders it as a real assistant message bubble
- **Template-based acknowledgments** — 13 intent types with natural templates ("On it — I'll handle that on your desktop. Give me a moment."). No cloud latency
- **Composer pulse animation** — accent-colored box-shadow pulse on the input container while a task is executing. Stops when task completes or errors
- **Capability self-knowledge seeds** — 8 new tool capability facts in `seed_self_knowledge.py` (desktop control, system info, file ops, shell exec, content generation, commitments, URL fetch, desktop safety limits). Stored as SYSTEM-source memories with 0.95 trust so the LLM can answer "can you do X?" from real capabilities
- **Post-task memory writer** — `_write_facts()` now stores what the agent did for desktop_action, system_info, file_write, file_read, dir_list, shell_exec, and git_action tasks. Follow-up questions like "what apps are open?" now have context from previous actions
- **Capability-aware re-route** — new `_capability_reroute()` in chat.py catches messages that the classifier sent to conversational but clearly match a tool capability (e.g. "what apps are open?" re-routes to system_info, "take a screenshot" re-routes to desktop_action)

### Fix
- **Silent routing failure** — `classify_intent_hybrid()` now wraps the embedding classification path in its own try/except. Previously, if `router.classify()` threw (VRAM conflict, model not loaded), the exception propagated up to `chat.py:4678` which set `_task_intent = None`, causing desktop_action requests to silently fall through to conversational. Now the regex result (e.g. `desktop_action` at 0.88 confidence) survives embedding failures
- **Error logging upgrade** — intent classifier exception handler in chat.py promoted from `logger.warning` to `logger.error` so failures are impossible to miss in terminal output
- **detect_multi_intent safety** — wrapped in its own try/except so multi-intent detection failures don't kill the classification
- **"What apps are open?" routing** — previously fell through to conversational and returned "I don't have visibility." Now correctly routes to system_info tool via capability re-route

### Polish
- **Settings toggle accent color** — Toggle component now uses `var(--accent)` instead of hardcoded `bg-blue-500/80` for the active state
- **Idle task input debounce** — Desktop settings idle task text input changed from `onChange` (PATCH per keystroke) to `onBlur` (single PATCH on blur)
- **Nested button DOM warning** — Sidebar thread items changed from `<motion.button>` to `<motion.div role="button">` to eliminate `<button>` nested inside `<button>` React warnings. All three instances fixed (pinned, recent, mobile)

---

## v2.3 — March 23, 2026

Desktop control (Sprint 11). Cloud vision + local action loop. Aether can now see and control the user's desktop via a ReAct loop: screenshot → Claude vision analysis → execute action → verify → repeat. Memory-grounded — injects verified facts about the user's system so the vision model knows exact paths, preferences, and app locations.

**How it works:**
1. `DesktopController` captures a full-resolution screenshot via `mss` (e.g. 4592x2048 on ultrawide)
2. Screenshot resized to 1280px wide, compressed to JPEG, base64-encoded
3. `CookieVisionProvider` uploads the image to `claude.ai/api/{org}/upload` via multipart form (curl_cffi CurlMime), gets back a file UUID
4. Sends chat completion to `claude.ai` with the file UUID + structured prompt asking for one JSON action
5. Parses SSE response into `VisionAnalysis` with a single `DesktopAction` (type, coordinates, text, reasoning, confidence)
6. `DesktopAgent` scales coordinates from 1280px vision-space back to actual screen resolution (e.g. ×3.59 for ultrawide)
7. Executes action via `pyautogui` (click, type, hotkey, scroll, etc.)
8. Loops back to step 1 with fresh screenshot. Stops on `done`, `failed`, `need_info`, or max 25 steps

**Live test result:** "open notepad" completed in 4 steps / 70 seconds:
- Step 1: `hotkey(win)` → opened Start menu (19s vision latency)
- Step 2: `type("notepad")` → searched in Start menu (24s vision latency)
- Step 3: `click(606, 692)` scaled to `(2175, 2484)` → launched Notepad (9s vision latency)
- Step 4: `done` → recognized Notepad was open (13s vision latency)

### Feature
- **Desktop control module** (`personal_agent/desktop_control.py`) — DesktopController class wrapping pyautogui (mouse/keyboard), mss (fast screenshots), Pillow (image processing). Screenshot capture, region capture, base64 encoding with resize, mouse clicks/drags, keyboard typing/hotkeys, window management via pygetwindow
- **Desktop vision module** (`personal_agent/desktop_vision.py`) — VisionProvider ABC with two cloud implementations:
  - `ClaudeVisionProvider` — uses Anthropic API key via `AnthropicClient.chat_with_image()`
  - `CookieVisionProvider` — uses claude.ai session cookie, uploads images via multipart form, no API key needed. Full pipeline: decode base64 → compress to 1280px JPEG → upload via `curl_cffi` CurlMime → send completion with file UUID → parse SSE response
- **Desktop ReAct agent** (`personal_agent/desktop_agent.py`) — DesktopAgent with screenshot→think→act→verify loop. Max 25 steps, configurable callbacks for checkpoints and step logging. Rate limiting (20 actions/min, 10 clicks/min, 200 keystrokes/min)
- **Coordinate scaling** — vision model sees 1280px-wide images but actual screen may be 3440px+ (ultrawide, high DPI). Agent computes `scale = screen_width / vision_width` and multiplies all action coordinates before execution. Restricted region checks applied after scaling so they use real screen coordinates
- **Cookie image upload** — `CookieProvider._upload_image()` sends multipart form to `claude.ai/api/{org}/upload`, returns file UUID. `complete_with_image()` references the UUID in the chat completion payload
- **Chat with image** — `AnthropicClient.chat_with_image()` method for API key path (base64 image + text prompt)
- **Lightweight gating** — no initial checkpoint for desktop tasks. Safe actions (open app, click tab, scroll, type in search) execute freely. Only dangerous actions gate mid-loop: send, submit, delete, purchase, uninstall, etc.
- **Screenshot preview in ActionCard** — `ActionCard.tsx` renders `screenshot_b64` as inline JPEG with target description overlay
- **Desktop API routes** (`routes/desktop.py`) — `POST /api/desktop/execute`, `POST /api/desktop/stop`, `GET /api/desktop/screenshot`, `GET /api/desktop/history`
- **Action receipts** — every desktop action step logged to SQLite via existing action_receipts system
- **Memory-grounded vision** — verified facts from CRT memory injected into vision prompt (paths, preferences, app locations). When user says "open my portfolio in VS Code," vision model knows the exact path
- **Deterministic responses** — "Desktop task completed in N steps (Xms). {summary}" or "Desktop task failed after N steps: {error}"
- **LocalVisionProvider stub** — prepared interface for future local vision model (moondream2, Qwen2-VL) when VRAM permits
- **Live test runner** — `tests/desktop_control/run_live.py`: CLI tool for interactive desktop task testing with step-by-step logging, 3-second countdown, checkpoint prompts for dangerous actions

### Safety
- **Blocked apps** — 18 entries: password managers (1Password, Bitwarden, KeePass, LastPass), banking (Chase, Wells Fargo, PayPal, Venmo), admin tools (regedit, Task Manager, Device Manager, Credential Manager, Windows Security, Disk Management, Group Policy, Firewall, Services, certificates)
- **Hard-blocked targets** — password fields, credit card inputs, SSN, bank account, routing number, CVV — these never execute, even with confirmation
- **Confirmation keywords** — send, submit, delete, remove, purchase, buy, pay, publish, post, confirm, sign out, log out, uninstall, format, erase, reset, shutdown, restart
- **Rate limiting** — sliding-window limiters prevent runaway loops (20 actions/min, 10 clicks/min, 200 keystrokes/min)
- **Restricted screen regions** — system tray area blocked by default, checked after coordinate scaling
- **pyautogui.FAILSAFE** — move mouse to top-left corner (0,0) to abort all automation

### Fix
- **Coordinate scaling bug** — initial implementation sent raw vision-space coordinates (1280px) to pyautogui on a 4592px screen. Cursor appeared to not move because clicks landed at ~1/3.6 of the intended position. Fixed by computing scale factor from actual screen resolution and applying before execution

### Test
- 42/42 unit tests passing: screenshot capture, cursor position, window detection, blocked app detection (11 cases), confirmation logic (7 cases), hard-blocked targets (4 cases), restricted regions (3 cases), agent ReAct loop (5 cases), vision response parsing (3 cases)
- Vision benchmark harness: 22 annotated scenarios, interactive screenshot capture, accuracy metrics with gate check
- Live integration test: "open notepad" end-to-end via cookie vision provider — 4 steps, 70s, successful

### Desktop Control Settings (v2.3.1)

Added user-facing controls for desktop automation in Settings > Desktop tab.

#### Feature
- **Desktop Control toggle** — master enable/disable for all desktop automation (`desktop_control_enabled`). Off by default; task_agent and API route return error when disabled
- **Max steps per task** — configurable limit on vision-action loop iterations per task (default 15, max 50). Controls cost and runaway prevention
- **Max actions per session** — total desktop actions allowed per session before requiring re-enable (default 50)
- **Confirmation mode** — three levels: "Never" (fully autonomous), "Dangerous actions only" (default — gates send/delete/purchase/uninstall), "Every action" (pause before each step)
- **Vision provider selector** — switch between cookie session (no API key) and API key (`ANTHROPIC_API_KEY`) for screenshot analysis
- **Heartbeat idle control** — when enabled + system idle (CPU < 10%, no GPU), automatically runs a configurable desktop task. E.g. "organize my downloads folder"
- **Idle task text field** — freeform natural language task that runs during idle detection
- **Settings persistence** — all desktop settings stored in `user_settings` SQLite table via existing `PATCH /api/auth/settings` endpoint
- **Settings enforcement** — `task_agent._run_desktop_action()` and `routes/desktop.py` both check `desktop_control_enabled` before executing. Returns clear error message directing user to Settings when disabled
- **Heartbeat integration** — `heartbeat_executor.py` checks `desktop_heartbeat_idle_control` + `desktop_control_enabled` + `desktop_idle_task` on each idle trigger. Runs task via `DesktopAgent` with configured max steps. Guarded by `_desktop_idle_running` flag to prevent overlapping tasks

#### Frontend
- **Desktop tab** in Settings page with Toggle, number input, select dropdown, and text input controls
- **Warning banner** when desktop control is enabled — reminds user about emergency stop (mouse to top-left corner)
- **Conditional idle task field** — only shown when heartbeat idle control is enabled

---

## v2.2 — March 25, 2026

Semantic intent router (Sprint 7). Replaces fragile regex-based intent classification with embedding similarity against 140+ prototype phrases. Hybrid routing preserves all existing regex as fallback while the embedding model fills gaps — semantic equivalents, typos, multi-intent messages, and ambiguous queries now route correctly.

### Feature
- **Semantic intent router** (`personal_agent/semantic_intent_router.py`) — `SemanticIntentRouter` class using `all-MiniLM-L6-v2` (already loaded for memory search). 16 intent types with 5-13 prototype phrases each. Classifies via cosine similarity against centroids + individual phrase matching
- **Hybrid routing** — `classify_intent_hybrid()` in task_agent: regex at >= 0.90 confidence wins, embedding fills gaps below. Logs both results for comparison, warns on disagreements
- **Multi-intent detection** — `detect_multi_intent()` identifies compound messages ("check my system and read the config") where top 2+ intents are close in confidence. Plan builder creates combined plans
- **Ambiguity handling** — confidence between 0.45-0.75 triggers clarification via action card with candidate intents as buttons. User clicks to disambiguate
- **Intent correction learning** — `intent_corrections.db` tracks misclassifications. `record_correction()` fires on user disambiguation and task success/failure. `_apply_learned_corrections()` adjusts future scores based on similar past corrections
- **Heartbeat self-improvement** — every 20th tick, `review_corrections()` auto-adds prototype phrases from 3+ repeated corrections to the same intent
- **Intent debug API** (`routes/intents.py`) — `GET /api/intents/classify?message=...` (debug), `/prototypes` (list/add/remove), `/corrections` (history), `/stats` (accuracy metrics)
- **Lazy loading** — router initializes on first classification, graceful fallback to regex if embedding model unavailable
- **Source chip** — `AgentThinkingStrip.tsx` shows blue badge when embedding router classified the intent

### Test
- External test lab: 97% accuracy across clear, semantic, typo, multi-intent, and conversational categories

---

## v2.1 — March 25, 2026

Dynamic slot discovery (Sprint 6). The system's third design law — "structure should emerge, not be hardcoded" — now ships in code. Replaces the hardcoded `EXCLUSIVE_SLOTS` list with a learned model that discovers slot behavior from contradiction and fact patterns.

### Feature
- **Slot discovery module** (`personal_agent/slot_discovery.py`) — `SlotType` enum (EXCLUSIVE, ADDITIVE, TEMPORAL, HIERARCHICAL, UNKNOWN), `SlotProfile` dataclass with evidence tracking
- **Slot classification** — `classify_slot()` analyzes contradiction resolution history and concurrent value patterns. EXCLUSIVE: always override. ADDITIVE: multiple values coexist. TEMPORAL: values change over time. HIERARCHICAL: containment relationships
- **Confidence scoring** — `compute_slot_confidence()` based on evidence volume and consistency. 1 contradiction = 0.3, 4+ consistent = 0.85, 10+ = 0.95
- **Dynamic lookup** — `get_slot_type()` replaces all hardcoded `EXCLUSIVE_SLOTS` checks in `crt_memory.py`, `routes/chat.py`, `routes/memory.py`. Learned profiles → seed lists → UNKNOWN fallback chain
- **Resolution policy engine** — `suggest_resolution_policy()` recommends override/preserve/archive/merge/ask_user based on learned type
- **Event hooks** — `on_contradiction_recorded()`, `on_fact_stored()`, `on_contradiction_resolved()` fire on every relevant action, incrementally updating slot profiles
- **Counter-evidence tracking** — when user resolves differently than suggested (e.g. "Keep Both" on an EXCLUSIVE slot), classification confidence decreases
- **Heartbeat discovery pass** — periodic `run_discovery_pass()` does full batch analysis from ledger
- **Slot lineage logging** — `slot_discovery_log` table with audit trail: old_type → new_type, trigger, evidence, timestamp
- **Slot discovery API** (`routes/slot_discovery.py`) — profiles CRUD, manual override, trigger analysis, stats
- **TEMPORAL demotion** — temporal slots get 0.6x demotion vs 0.4x for exclusive (old values were true, just not current)

### Fix
- **Seed lists preserved** — `_SEED_EXCLUSIVE` and `_SEED_ADDITIVE` remain as fallback for slots without enough contradiction data to classify

---

## v2.0 — March 24-25, 2026

Proactive & scheduled actions (Sprint 4). Aether goes from reactive to proactive. Commitments system for reminders and scheduled tasks, browser notifications, proactive conversation triggers, and heartbeat resource management.

### Feature
- **Commitment governance** (`personal_agent/commitments.py`) — `Commitment` dataclass with intent, status (pending/fired/done/missed/cancelled), deadline, recurrence, priority, consequence. SQLite `commitments` table with full CRUD
- **Natural language time parsing** (`personal_agent/time_parser.py`) — handles "at 10:30pm", "every weekday at 9am", "in 5 minutes", "tomorrow morning", "tonight", cron expressions. Zero external dependencies
- **Commitment agent tools** — `create_commitment`, `list_commitments`, `cancel_commitment` intents with checkpoint gates (medium tier for create/cancel, no gate for list)
- **Time-aware heartbeat** — commitment scanner added to heartbeat tick: checks for due commitments within 60s lookahead, fires notifications, updates status, computes next_fire_at for recurring
- **Browser notifications** — `commitment_notification` SSE event type. Frontend shows `Notification` API popup + injects system message in active chat
- **Proactive triggers** (`personal_agent/proactive_triggers.py`) — pattern detection: trip planning, deadline mentions, health concerns, project references. Fires contextual suggestions appended to response metadata
- **Heartbeat resource management** — `_resources_reduced` state flag. Gaming detected (GPU > 90% + game process) → kill ollama. Idle detected → restart ollama. Dynamic API-only mode
- **Deterministic commitment responses** — "Reminder set: {description}. Next fire: {time}. Recurrence: {pattern}." No LLM hallucination
- **Commitment API** — `POST /api/commitments`, `GET /api/commitments`, `PUT /api/commitments/{id}/status`, `DELETE /api/commitments/{id}`, `GET /api/commitments/due`

### Fix
- **Commitment tool fallthrough** — commitment tools were falling through to LLM generation path instead of returning deterministic answers; added to the deterministic response chain in task_agent answer generation

---

## v1.9 — March 24, 2026

Action execution layer (Sprint 3) + file reference UI + content generation. Aether can now write files, generate code from descriptions, run shell commands, and execute git operations — all gated by checkpoint confirmation with diff/command preview in the action card. Every action logged as a receipt to SQLite. File paths in agent responses render as interactive pills.

### Feature
- **File write tool** — `write_file()` and `apply_edit()` in `file_tools.py`. Path validation against allowed paths, reads existing content for diff before writing. Returns diff preview via `difflib.unified_diff`
- **Content generation tool** — `generate_content` step in task_agent: when user describes what a file should contain (instead of providing literal content), LLM generates the actual code/content then writes it. Detects description-vs-literal via word count + file extension heuristic
- **Shell execution tool** (`personal_agent/shell_tools.py`) — `execute_command()` with blocked command safety list (`rm -rf /`, `format`, `shutdown`, etc.), output truncation at 5000 chars. `execute_git()` wrapper for git operations
- **Action receipts** (`personal_agent/action_receipts.py`) — `ActionReceipt` dataclass: receipt_id, tool_name, action, target, result, reversible, reverse_action, checkpoint_approved. Persisted to SQLite `action_receipts` table. `GET /api/action-receipts` endpoint
- **Git tool** — commit, push, branch ops via `git_exec`, gated by high-tier checkpoint
- **Checkpoint gate for Layer 3-4** — `file_write`, `shell_exec`, `git_action` intents all require confirmation with `checkpoint_tier: "high"`. Metadata passes diff_preview, command, and target_path to the action card
- **Diff viewer in action card** — `ActionCard.tsx` renders syntax-highlighted unified diff (green additions, red removals, blue hunk headers) in a `<pre>` block above Yes/No buttons when `checkpointMeta.diff_preview` is present
- **Command preview in action card** — shell/git commands shown as `$ command` in a `<code>` block before execution
- **Tool context carry-forward** — when a conversational follow-up arrives within 120s of a completed tool task, recent tool output is injected into generation context. Fixes hallucinated responses to follow-up questions
- **FilePill component** (`frontend/src/components/ui/FilePill.tsx`) — interactive inline chip for file paths: file/folder icon, shortened filename, full path tooltip on hover, click-to-copy. Terracotta accent, matches warm dark theme
- **Auto-detect file paths in messages** — `MessageBubble.tsx` post-processes assistant messages to render file paths (`D:/path/file.ext`, backtick-wrapped paths) as clickable FilePill components instead of plain text
- **`referenced_files` metadata field** — `CtrMessageMeta` extended with optional `referenced_files` array for structured file references from agent tool results
- **Composer + button** — attachment menu in bottom-left of chat input with: Add file path (native OS file picker), Add folder path (full path prompt), Working directory shortcut, Type path manual entry
- **Attached path pills** — selected files/folders appear as removable pills in the top bar next to LOG button, prepended as `[file: path]` / `[dir: path]` when message is sent
- **Backslash path normalization** — `_FILE_PATH_RE` regex now matches Windows backslash paths (`D:\path\file`), auto-normalized to forward slashes in intent classifier
- **`[dir:]` / `[file:]` prefix parsing** — intent classifier extracts attached path references from Composer prefix tags, uses them as target directory for file operations
- **Claude and OpenAI logos** — model selector shows brand logos (Claude starburst, OpenAI knot) alongside local server icon; icons inherit `currentColor` for uniform selected/unselected styling

### Fix
- **Deterministic responses for Layer 2 tools** — `file_read`, `dir_list`, `project_scan` now show actual file/directory content in structured format instead of passing through LLM (which hallucinated file contents)
- **Folder picker full path** — replaced `showDirectoryPicker()` (which only returns folder name) with direct path prompt to capture absolute paths like `D:\lumi`
- **Typo-tolerant file write regex** — `g[en]*e?r?a?te` catches "gnerate", "genrate", "generate" and other common typos
- **Drive path regex greediness** — drive-letter paths (`D:\path`) no longer consume command words like "create" as part of the path
- **Content extraction** — "with hello world as the content" correctly extracts to "hello world" (trims "as the content" suffix)

---

## v1.8 — March 24, 2026

System awareness, stop generation, file/project tools (Sprints 1-2). Aether can see system state, read files, scan projects, and the heartbeat reacts to system load.

### Feature
- System info tool (`personal_agent/system_info.py`) — `psutil` wrapper: CPU, RAM, GPU (pynvml), disk, top 5 processes with game detection, active window (pygetwindow). Exposed as agent tool (Layer 1, no checkpoint gate) and API endpoint (`GET /api/system/status`)
- `system_info` intent classifier — matches "system status", "cpu usage", "what am I running", etc. Routes to task agent at 0.95 confidence
- Heartbeat system awareness — system snapshot sampled every heartbeat cycle; gaming detection (GPU > 85% + game process) and idle detection (CPU < 10%) logged in actions_taken for reflection context
- Stop generation button — AbortController wired into `streamFromCrtApi()`, square stop icon replaces send button during streaming, Escape key shortcut, partial response finalized as assistant message with `gate_reason: 'stopped_by_user'`
- **File read tool** (`personal_agent/file_tools.py`) — `read_file()`, `list_directory()` with allowed paths enforcement, `git_status()` via subprocess, `scan_project()` combining git + dir listing + project type detection
- **Project scanner** — detects project type (node/python/rust/go), entry points, git branch/status/commits
- **Allowed paths config** — `_ALLOWED_PATHS` with `GET/PUT /api/settings/allowed-paths`, persisted to `.file_tools_settings.json`
- **File/project API endpoints** — `GET /api/files/read`, `/api/files/list`, `/api/project/scan`
- **3 new agent tools** — `file_read`, `dir_list`, `project_scan` intents with regex classification, Layer 2 no-gate, plan builder, execute step dispatch
- **Heartbeat behavioral triggers** — gaming (GPU > 90% + game process), high_load (CPU/RAM > 90%), idle (CPU < 10%) logged as `behavioral_trigger` actions

---

## v1.7 — March 23, 2026 (evening)

Action layer foundation, checkpoint-driven UX, moltbook pipeline validated, skill install pipeline.

### Feature
- Action card UI — checkpoint-driven floating quick-reply card (Yes / No / Custom) above composer; only appears when backend emits `agent_checkpoint` SSE event, not from text pattern matching
- Silent checkpoint confirmation — button press sends response without rendering a user message bubble in chat history
- `handleSend` accepts `{ silent: true }` option for invisible message dispatch
- Moltbook end-to-end pipeline validated — skill.md → curl parser → credential injection → API call → result rendered through CRT governance
- Skill.md template created (`data/managed_skills/_template/SKILL.md`) — reusable pattern for adding new services: site API, git ops, weather, etc. Follows curl parser format with proper credential injection hooks
- **Skill install pipeline** — "add skill from URL" intent: fetches skill.md, parses YAML frontmatter, saves to `data/managed_skills/{name}/`, registers in `_KNOWN_SERVICES` at runtime, stores skill_url + api_base in credential store, rebuilds service regex. Falls back to URL hostname when frontmatter name is missing
- `skill_install` intent classifier — regex matches add/install/register/connect + skill/service/tool + URL
- Deterministic skill install response — reports what was installed, prompts for API key
- Skill installs written as memory facts (T:0.95) — Aether remembers which skills are installed

### Polish
- Copilot page hero graph — sticky behind content, slides over on scroll
- Sidebar flush-left with no rounded corners
- Showcase page removed
- Docs page Changelog/Roadmap buttons wired to backend `doc_map`

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

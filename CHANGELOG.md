# Changelog

All notable changes to Aether/CRT are documented here.
For architecture decisions see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
For the full roadmap see [ROADMAP.md](ROADMAP.md).

---

## [Unreleased] — 2026-04-07

### Added — Session 2026-04-07 (18 features)

#### Governance & Security
- **Governance bridge** (`personal_agent/governance_bridge.py`): Three bidirectional feedback loops connecting memory trust to belief/speech tracking. Bridge 1: topic drift penalizes supporting memories (-0.03 to -0.05 per cycle). Bridge 2: trust drops below 0.3 reclassify stale belief_speech entries to speech. Bridge 3: new beliefs in unstable topics get trust dampened 15%. Wired into variance_tracker (post-analysis), crt_memory (update_trust + record_belief), heartbeat_executor, and crt_rag engine init.
- **Prompt injection defense** (`crt_memory.py`): `sanitize_memory_for_prompt()` strips role markers (`System:`, `[INST]`, `<|system|>`), instruction overrides ("ignore above instructions"), and behavioral hijacks ("you are now a") via regex. `detect_injection_risk()` flags at storage time. Wired into chat.py prompt building and context_feed.py. Frontend `cleanMemoryText()` also strips injection patterns from display.
- **Cross-channel injection hardening**: Per-channel trust ceilings (`CHANNEL_TRUST_CEILINGS`): mcp_client=0.6, file_ingest=0.7, telegram/discord=0.5, ambient=0.4. Injection-flagged memories capped at confidence 0.4. File ingestion chunks scanned for injection patterns, flagged chunks downgraded to provisional authority.
- **Execution drift detection** (`agent_run_log.py` + `cookie_orchestrator.py`): Tool category tracking (memory/web/file/system/code) across agent loop steps. Live detection: category switch + alignment < 0.25 triggers `execution_drift` SSE event. Post-run detection: `detect_execution_drift()` flags scattered execution (3+ category switches). Events emitted as `epistemic_event` type for frontend display.

#### Pipeline & Governance Metrics
- **Cascade pressure as live metric** (`memory_graph.py`): SUM aggregation of incoming cascade impacts per node (vs existing MAX for trust updates). New fields on `CascadeResult`: `incoming_pressure`, `max_pressure`, `avg_pressure`. SSE status event emitted after cascade runs. Metadata stored in ledger entries.
- **Adaptive response depth** (`chat.py`): Replaced 3-tier cliff (150/500/4096 tokens) with smooth power-law curve: `100 + 3996 * belief^0.7`. Hedge threshold lowered to 0.35. ReasoningMode capped by confidence: <0.3 forces quick, <0.5 caps deep/research to thinking. SSE event shows depth decision. `[ADAPTIVE_DEPTH]` logging.
- **Structural transformation gates** (`agent_tool_loop.py` + `cookie_orchestrator.py`): `is_transformation_intent()` detects rewrite/fix/convert/optimize tasks (25 verb stems + structural patterns). After agent loop, verification LLM call checks before/after state. Results stored in `agent_runs.db` (`transformation_verified`, `verification_reason`). Both AgentToolLoop and orchestrator paths covered.
- **Cloud spending gradient limiter** (`cloud_features.py`): Smooth cost curve `1 - (daily_cost/ceiling)^0.6` reduces cloud access as spend increases ($0=100%, $3=51%, $5=34%, $10=0%). `record_cost()` accumulates daily spend. Gradient multiplier applied to all feature limits. `GET /api/cloud/budget` endpoint. `[GRADIENT_LIMITER]` logging.

#### Frontend
- **Clickable mini-graph**: SVG nodes and memory labels in PipelineCollapse now clickable, navigating to `/belief-map` page. Hover shows dashed ring + tooltip (first 40 chars of memory text). Bidirectional hover sync between graph and label list. "click -> full map" legend hint.
- **GateFailDrawer** (`frontend/src/components/chat/GateFailDrawer.tsx`): Right-sliding drawer for gate failure details. Color-coded reason badges, intent/memory/grounding metrics vs thresholds (FAIL/PASS badges), affected memories list, slot info, conflict detail. Actions: Retry, View Contradictions, Dismiss. Wired into MessageBubble.tsx.
- **RunLogPage** (`frontend/src/pages/RunLogPage.tsx`): Agent run analytics dashboard. Top stats: runs/success/iterations/latency/drift. Recent runs table (50 rows). Tool usage bar chart (top 10). Activation stats. Dead memories list. Auto-refresh 30s. Wired into App/Sidebar/types as `agent-runs` nav.
- **Pipeline Stepper** (`frontend/src/components/PipelineStepper.tsx`): Standalone 12-step vertical stepper showing all CRT pipeline phases. 4 visual states (pending/active/complete/skipped). Click-to-expand details with timing. Animate replay button. PipelineStepperPage with 3 example datasets. Wired into nav as `pipeline-stepper`.
- **Usage & Billing settings tab** (`SettingsPage.tsx`): Daily spend progress bar with gradient multiplier indicator. Per-feature limits table (base/effective/used/status). SVG spending curve visualization. Budget ceiling control + auto-downgrade toggle. 30s auto-refresh.
- **/beliefs page fix**: Expanded filter from `user_belief` only to `user_belief + user_fact`. Added BELIEF/FACT kind badge. `kind` field added to API response and frontend types.

#### Action Receipts
- **Receipt verification fields** (`action_receipts.py`): Added `verification_passed`, `verification_reason`, `expectation_keywords`, `run_step_id`, `model_attribution` to ActionReceipt dataclass. ALTER TABLE migration for existing DBs. `update_receipt_verification()` patches receipts after tool execution. `get_receipt_summary()` for aggregate stats. `GET /api/action-receipts/summary` endpoint.

#### Intent Routing
- **Personal-fact pattern routing** (`task_agent.py`): 11 regex patterns ("where do I work", "what is my name", "who am I", etc.) route to full CRT pipeline (conversational) instead of broad_recall. Placed BEFORE route learning cache to prevent stale misclassifications from overriding. `broad_recall` removed from `_MEMORY_ONLY_INTENTS`.

#### Immune Agents
- **TemplateDetector assertive collapse fix** (`template_detector.py`): Added `_check_assertive_repetition()` — normalizes responses, checks uniqueness ratio. If < 0.3 (70%+ identical), classifies as TEMPLATE_LOCK even without hedge patterns. `assertive_collapse` field added to DetectionResult. Closes 5/6 → 6/6 governance validation.

### Fixed
- **cleanMemoryText** regex: handles truncated/unclosed `[SYSTEM NOTE` blocks by stripping everything after the marker.
- **Route learning cache override**: Personal-fact patterns now fire before cache lookup, preventing stale broad_recall classifications from replaying.

### Changed
- **Mini-graph**: Removed broken full-map-in-pipeline background attempt (wrong data source: belief_speech vs memories). Graph is now the simple 5-node retrieval view with click-through to full map page.
- **Auto-collapse timing**: Removed PCA-specific 4s delay, back to 1.5s universal.

---

### Added — Session 2026-04-05

- **CogniMap compression**: 6.5x memory savings validated, lossless image beats zlib 15.6%
- **Frontend polish**: Confidence badge, gate dots, cost display, memory cards, epistemic graph
- **Structural governance**: Confidence-gated response depth (precursor to adaptive depth)
- **Playdough formalism**: Connected to Riemannian manifold theory

---

## [Unreleased] — 2026-04-01 (Evening session)

### Added
- **Codex matrix audit**: Saved `docs/audits/system_matrix_audit_2026-04-02.md` with ROI-ordered subsystem tightening priorities.
- **Runtime status surface**: Added `GET /api/runtime/status` to expose the active runtime data root and resolved mutable-store paths.
- **GovernedTask durability**: Added `personal_agent/governed_task.py`, durable governed task/event persistence, and `/api/tasks/active` recovery endpoint.
- **Chat split modules**: Added `routes/chat_runtime.py`, `routes/chat_governed_resume.py`, `routes/chat_agent_loop_runner.py`, and `routes/chat_orchestrator_runner.py`.
- **Route split coverage**: Added `tests/test_chat_route_split.py` to assert `chat_stream` delegates to the extracted runner modules.
- **Cookie Rule 11 — SEARCH/LIST EFFICIENCY**: Prevents file-read verification loops after search/list tasks. Cookie now responds directly from `search_code` results without re-reading individual files.
- **Plan → pipeline thinking routing**: Cookie's `plan` action now emits a `type: "thinking"` SSE event instead of streaming as visible response tokens. Plan text (+ steps) appears as an italic stub in the Agent Loop panel, not in the chat bubble.
- **`drift` SSE event wired end-to-end**: Backend `record_turn` result already emitted drift events; frontend now parses them (api.ts + ws.ts), dispatches `onDrift` callback, and renders as an `epistemic` step in PipelineCollapse.
- **`session_state` SSE event wired end-to-end**: Cumulative density + open contradiction count after each turn flows through the same chain and renders as a `status` step.
- **PipelineCollapse summary line upgrade**: Collapsed summary now shows `N thoughts · N tools · N mem · N shifts · Xs` (thought count, shift/drift events included).
- **Session notes section in PipelineCollapse expanded view**: `density`/`open conflict` status strings collected into a footer section separate from agent loop items.
- **SSE debug logger extended**: `thinking`, `drift`, `session_state`, `retrieval`, `trust_shift` event types now included in dev-mode logger.
- **Electron DevTools**: Added `--devtools` CLI flag (auto-enable in dev) to open Chrome DevTools in the Electron shell.
- **Claude Code source analysis** (`src/src/`): 5-layer architecture mapped (QueryEngine, Coordinator/Worker, Tool System, Task/Daemon, Memory/Context). 9 absorbable patterns identified: concurrent tool executor, task taxonomy, coordinator/swarm, deferred tool loading, selective reinjection, lifecycle hooks, permission classifier, bridge, speculation. Pattern mapping table added to strategy_repo_split.md (interfaces→crt-core, wiring→AI_round2).
- **Suspend/resume remaining budget**: Both `ask_user` and `diff_write` suspend paths now store `remaining_iterations`. Resume uses `max(3, stored_remaining)` instead of hardcoded 8. Nested ask_user re-suspend also carries budget.
- **Followup suggestion chips (frontend)**: Centered clickable chips above composer. `[followup]` prefix forces agent loop routing. Full SSE chain: respond→followup_suggest→api.ts+ws.ts→App.tsx→ChatThreadView chips.
- **Cookie → Agent Loop rename**: 11 files updated. `_needs_cookie`→`_needs_agent_loop`, `_cookie_entry`→`_orch_entry`, `generation_source: "agent_loop"`. Comments/docstrings updated. Browser cookie auth preserved.
- **FORCE_RESPOND override**: If agent tries tool_call on last iteration, code forces respond from accumulated reasoning. Guarantees an answer.
- **Response depth (Rule 12)**: Agent instructed to include evidence, show don't summarize. Token limit 800→3000 on last 2 iterations.
- **Auto-continuation plan**: Design doc at `docs/plans/auto_continuation.md`. Backend detects `complete:false`, auto-fires next run. Max 3 continuations. Not yet implemented.

### Changed
- **Runtime-state writes externalized**: Core mutable stores now resolve through runtime path helpers instead of assuming repo-local DB locations.
- **SSE/WS contract frozen**: Stream event handling now flows through a single normalized backend/frontend contract boundary.
- **Governed task lifecycle made durable**: suspended-loop and checkpoint compatibility now sit on DB-backed governed task state instead of in-memory primary truth.
- **`chat.py` shifted toward coordination**: stream runtime, governed resume, agent-tool-loop execution, and orchestrator execution now delegate through extracted modules.

### Fixed
- **Runtime observability gap**: the process can now report where it is actually writing runtime state, reducing hidden DB-path confusion.
- **Event drift risk**: SSE/WS emission/parsing now shares one normalized contract instead of separate ad hoc paths.
- **Agent-loop lifecycle fragility**: task state now survives restart/recovery through governed task persistence.
- **search_code timeout + large file guard**: Added `--max-filesize 256K` to rg, excluded `*.min.js`, `*.min.css`, `*.lock`, `*.map`, `_write_copilot_page.py`. Python fallback also skips files >256KB. Prevents 159s+ hangs on generated/bundled code.
- **`file_pattern` arg support**: Cookie was passing `file_pattern: "frontend/**/*.{tsx,ts}"` which search_code silently ignored, causing full-tree scans. Now parsed into path + extensions automatically.
- **Cookie iteration budget fundamentally fixed**: `for` loop → `while` loop with explicit counter. `plan` no longer consumes an iteration slot (it's a declaration, not work). `think`, `tool_call`, `spawn_agent` increment explicitly. Safety cap `_total_turns = max_iterations + 5` prevents infinite plan loops. Net effect: plan+read+write = plan (free) + 10 working slots.
- **Cookie warning threshold**: Changed from `remaining <= 1` + "You MUST respond now" to `remaining == 0` + "Last action slot". Stops Claude from panic-responding one slot early.
- **Routing gate**: Layer 4 `_layer4_orchestrator` now bypasses `_needs_cookie`. `_cookie_entry = _layer4_orchestrator OR (agent_loop_skipped AND _needs_cookie)`. Layer 4 decisions go straight through; `_needs_cookie` only gates the redirect path.
- **file_read/file_write** added to `_TOOL_REQUIRING_INTENTS` — covers redirect path even if Layer 4 doesn't fire.
- **llm_local redirect**: `llm_local` mode redirected to Cookie instead of falling through to broken agent loop (LiteLLM/Ollama not running).
- **Context bleed (Cookie conflating tasks)**: Orchestrator history window reduced `window=6, 300 chars` → `window=2, 150 chars`. History label changed to `"PRIOR CONTEXT (previous exchange — for continuity only, NOT the current task)"`.
- **Token indices sequence length > 512 warning**: Root cause — unbounded text passed to `sentence-transformers`. Fixed at `EmbeddingEngine.encode()` / `encode_batch()` with `_MAX_INPUT_CHARS = 1600`. All callers benefit automatically.
- **`_MAX_ALIGN_CHARS = 400`**: Added truncation in `agent_run_log.py` `score_alignment()` and `detect_step_contradictions()`.
- **TOOL_GATE `ALL_TOOLS` error**: `search_code` was excluded from Cookie's allowed tool list. Fixed.
- **`file_extensions` param crash**: `search_code` failed when `file_extensions` passed as a string. Added normalization guard.
- **VERIFY `diff_preview` skip**: Verification action attempted `diff_preview` tool calls that didn't exist. Added guard.
- **`_emit_pipeline_event` in generator path**: Initial plan routing used threaded-path helper; orchestrator is a generator. Fixed to `yield _sse({...})`.
- **`onThinking` not wired in App.tsx**: Added handler to push `{ kind: 'thinking', content }` into pipelineSteps.
- **`status` steps silently dropped in groupSteps**: `sessionNotes` added to `groupSteps` return; density/conflict strings now collected into expanded footer section.
- **Pipeline history showing "1 step"**: `pipelineStepsRef` now captures live step list at `done` time for full persistence.
- **Followup routing crash**: `[followup]` prefix forces agent loop entry. Prevents conversational followups crashing on legacy path timeout.
- **spawn_agent LogStep crash**: `result=` → `result_preview=` field name mismatch in RunStep dataclass.
- **spawn_agent context crash**: Removed invalid `context=` kwarg from `child.run()`.
- **project_scan/search_code/multi_intent routing**: Added to `_TOOL_REQUIRING_INTENTS` so they always route to agent loop.
- **dir_list missing directory**: Returns explicit error + lists real project directories instead of empty string.
- **dir_list src/ redirect**: Returns "NOTE: third-party reference code" for Claude Code source dump directory.
- **PipelineTrace/ToolRow toLowerCase guard**: Prevents crash on undefined values from legacy path events.

### Docs
- **ROADMAP.md** — updated through v3.7 with full March 25–April 1 history, new IN PROGRESS / NEXT UP sections
- **CHANGELOG.md** — Claude Code analysis + Cookie loop fixes added to Unreleased
- **docs/INDEX.md** — version bumped to v3.7
- **Memory**: session_2026_04_01_claude_code_analysis.md, strategy_repo_split.md updated with pattern mapping

---

## [v3.0] — 2026-03-31

### Added
- ALL 10 CRT transformations shipped
- Compaction, density extraction, prompt cache boundary (6 axioms), inspectable index
- Context decay, execution belief verification, away/resume diff, consolidation, intent-gated tools
- Belief-aware compaction: trust-tiered compression, compaction decay, 3 API endpoints
- CRT Session State: running belief state, density-weighted extraction, session-aware compaction
- Prompt cache boundary: static epistemology prefix, `cache_control`, unified across 3 prompt paths
- Introspect tool; Layer 6 interpretation beliefs; The Mirror (structural posture gate)
- User belief system: classifier + storage routing + `/api/beliefs` endpoint

### Fixed
- 4 Cookie loop fixes: plan-free iteration, softer warning, budget through suspend/resume, checkpoint metadata

---

## [v2.9] — 2026-03-30

### Added
- Cookie-Opus orchestrator: brain/hands architecture, provider abstraction, sandbox, multi-turn continuity
- 14 Cookie tools: `search_code`, `read_file`, `write_file`, `run_tests`, `shell_command`, etc.
- Code intelligence agent: `file_map`, `trace`, `detect`
- Agent run log Layer 1: per-run measurement to SQLite
- Governance L4 (epistemic routing) + L5 (execution beliefs)
- Discord bot + Telegram live; image upload pipeline
- BeliefDependencyGraph class; LiveBDG cascade wiring (12 call sites)
- Provisional authority gate; slot demotion block
- 6 integrity fixes; NLI critic fix; cascade paper math (all 6 theorems patched)

---

## [v2.8] — 2026-03-28 to 29

### Added
- Electron shell: frameless, tray, hotkey, auto-detect backend
- Heartbeat learning, ambient mode, MCP server (12 tools), clipboard, file drop, model selector
- Alias protection: 36 aliases, canonical collapse
- Mac M2 offload (Ollama over LAN); intent model split (llama3.2)
- Robustness sweep: three regimes (Qwen3=fracture, Mistral=gradient, DeepSeek=fog)
- ALL 5 immune agents (31/31 tests)

---

## [v2.7] — 2026-03-26 to 27

### Added
- 10 publishable contributions validated; 8 research modules built and tested
- Dedup benchmark (567 unique vectors), RVQ, predictive contradiction detection
- Active inference module; three-model experiment; domain inversion proven
- Cascade complexity paper: full draft + 5 experiments pass

---

## [v2.6] — 2026-03-21 to 25

### Added
- 17 backend + 3 frontend commits shipped
- GroundCheck v2, LiteLLM integration
- Agentic spec: intent/direction gates, action receipts, checkpoint tiers, belief/speech separation

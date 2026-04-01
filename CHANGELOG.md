# Changelog

All notable changes to Aether/CRT are documented here.
For architecture decisions see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
For the full roadmap see [ROADMAP.md](ROADMAP.md).

---

## [Unreleased] — 2026-04-01 (Evening session)

### Added
- **Cookie Rule 11 — SEARCH/LIST EFFICIENCY**: Prevents file-read verification loops after search/list tasks. Cookie now responds directly from `search_code` results without re-reading individual files.
- **Plan → pipeline thinking routing**: Cookie's `plan` action now emits a `type: "thinking"` SSE event instead of streaming as visible response tokens. Plan text (+ steps) appears as an italic stub in the Agent Loop panel, not in the chat bubble.
- **`drift` SSE event wired end-to-end**: Backend `record_turn` result already emitted drift events; frontend now parses them (api.ts + ws.ts), dispatches `onDrift` callback, and renders as an `epistemic` step in PipelineCollapse.
- **`session_state` SSE event wired end-to-end**: Cumulative density + open contradiction count after each turn flows through the same chain and renders as a `status` step.
- **PipelineCollapse summary line upgrade**: Collapsed summary now shows `N thoughts · N tools · N mem · N shifts · Xs` (thought count, shift/drift events included).
- **Session notes section in PipelineCollapse expanded view**: `density`/`open conflict` status strings collected into a footer section separate from agent loop items.
- **SSE debug logger extended**: `thinking`, `drift`, `session_state`, `retrieval`, `trust_shift` event types now included in dev-mode logger.
- **Electron DevTools**: Added `--devtools` CLI flag (auto-enable in dev) to open Chrome DevTools in the Electron shell.

### Fixed
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

# CRT/Aether Roadmap
Last updated: March 23, 2026 (v2.3)

---

## DONE

### v2.3 (March 23)
- [x] Desktop control module — `personal_agent/desktop_control.py`: pyautogui + mss + Pillow for screenshots, mouse, keyboard, window management
- [x] Desktop vision module — `personal_agent/desktop_vision.py`: VisionProvider ABC, ClaudeVisionProvider (API key), CookieVisionProvider (session cookie — uploads image to claude.ai, no API key needed)
- [x] Desktop ReAct agent — `personal_agent/desktop_agent.py`: screenshot→think→act→verify loop, max 25 steps, rate limiting
- [x] Cookie vision provider — uploads screenshots via `claude.ai/api/{org}/upload`, references file UUID in chat completion. Uses `curl_cffi` with CurlMime for multipart upload. Full image→upload→prompt→SSE parse pipeline working
- [x] Coordinate scaling — vision model receives 1280px-wide screenshots, agent scales coordinates back to actual screen resolution (e.g. 3.59x on 4592x2048 ultrawide). Restricted region checks applied after scaling
- [x] Claude vision integration — `AnthropicClient.chat_with_image()` for API key path; `CookieProvider.complete_with_image()` for cookie path
- [x] Live test validated — "open notepad" completed in 4 steps / 70s: Win key → type "notepad" → click search result → done. Cookie vision latency 10-24s per step
- [x] Desktop action intent — regex pattern matching "open chrome", "click on", "switch to", "take a screenshot" etc.
- [x] Lightweight gating — no initial checkpoint gate; only dangerous actions (send, delete, purchase, uninstall) gate mid-loop. Safe actions (open app, click tab, scroll, type in search) run freely
- [x] ActionCard screenshot preview — inline JPEG with target description overlay
- [x] Desktop API — `POST /api/desktop/execute`, `POST /api/desktop/stop`, `GET /api/desktop/screenshot`, `GET /api/desktop/history`
- [x] Safety: 18 blocked apps, hard-blocked targets (passwords, credit cards, SSN), confirmation keywords, rate limiting, restricted regions
- [x] Memory-grounded vision — verified facts from CRT memory injected into vision prompt
- [x] LocalVisionProvider stub — ready for local vision model swap when VRAM permits
- [x] Live test runner — `tests/desktop_control/run_live.py` for interactive testing with step-by-step logging
- [x] 42/42 unit tests passing + 22-scenario vision benchmark harness
- [x] Desktop control settings — Settings > Desktop tab: enable/disable, max steps, max actions/session, confirmation mode (never/dangerous/always), vision provider (cookie/api_key), heartbeat idle control with configurable idle task
- [x] Settings enforcement — task_agent + API route check `desktop_control_enabled` before executing. Off by default
- [x] Heartbeat idle automation — when enabled + system idle, runs configured desktop task via DesktopAgent

### v2.2 (March 25)
- [x] Semantic intent router — `all-MiniLM-L6-v2` embedding similarity against 140+ prototype phrases across 16 intent types
- [x] Hybrid routing — regex at >= 0.90 confidence wins, embedding fills gaps below that; all existing regex preserved as fallback
- [x] Multi-intent detection — compound messages like "check my system and read the config" route to multiple tools
- [x] Ambiguity handling — low-confidence intents trigger clarification via action card instead of wrong routing
- [x] Intent correction learning — `intent_corrections.db` tracks misclassifications, `record_correction()` on disambiguation
- [x] Heartbeat self-improvement — auto-adds prototypes from 3+ repeated corrections
- [x] Intent debug API — `GET /api/intents/classify`, `/prototypes`, `/corrections`, `/stats`
- [x] Lazy loading — SemanticIntentRouter initializes on first use, graceful fallback if model unavailable
- [x] Source chip in AgentThinkingStrip — blue badge when embedding router is used

### v2.1 (March 25)
- [x] Dynamic slot discovery — `personal_agent/slot_discovery.py` with `SlotType` enum (EXCLUSIVE, ADDITIVE, TEMPORAL, HIERARCHICAL, UNKNOWN)
- [x] Slot classification from contradiction/fact patterns — rule-based with evidence-weighted confidence scoring
- [x] Replaced hardcoded `EXCLUSIVE_SLOTS` in `crt_memory.py` with dynamic `get_slot_type()` lookup
- [x] Seed lists preserved as fallback — `_SEED_EXCLUSIVE`, `_SEED_ADDITIVE` for bootstrap before enough data
- [x] Resolution policy engine — `suggest_resolution_policy()`: override/preserve/archive/merge/ask_user based on learned type
- [x] Event hooks — `on_contradiction_recorded()`, `on_fact_stored()`, `on_contradiction_resolved()` fire on every relevant action
- [x] Counter-evidence tracking — user disagreeing with suggested resolution lowers classification confidence
- [x] Heartbeat discovery pass — periodic `run_discovery_pass()` reclassifies slots from full ledger
- [x] Slot lineage logging — `slot_discovery_log` table tracks every reclassification with trigger and evidence
- [x] Slot discovery API — `GET /api/slots/profiles`, `POST /api/slots/analyze`, `PUT /api/slots/profiles/{name}/override`, `GET /api/slots/stats`
- [x] TEMPORAL slots get lighter demotion (0.6x vs 0.4x for EXCLUSIVE) in `crt_memory.py`

### v2.0 (March 24-25)
- [x] Commitment governance — `personal_agent/commitments.py` with Commitment dataclass, SQLite `commitments` table
- [x] Natural language time parsing — `personal_agent/time_parser.py`: "at 10:30pm", "every weekday at 9am", "in 5 minutes", "tomorrow morning"
- [x] Commitment agent tools — `create_commitment`, `list_commitments`, `cancel_commitment` intents with checkpoint gates
- [x] Time-aware heartbeat — commitment scanner checks for due commitments each tick, fires notifications
- [x] Browser notifications via SSE — `commitment_notification` event type, system message injection in chat
- [x] Proactive triggers — `personal_agent/proactive_triggers.py`: trip planning, deadlines, health concern, project mention patterns
- [x] Heartbeat resource management — kill/restart ollama based on gaming/idle detection (`_resources_reduced` state)
- [x] Deterministic commitment responses — "Reminder set: {description}. Next fire: {time}. Recurrence: {pattern}."
- [x] Commitment API — `POST /api/commitments`, `GET /api/commitments`, `PUT /api/commitments/{id}/status`, `DELETE /api/commitments/{id}`

### v1.9 (March 24)
- [x] File write tool — `write_file()`, `apply_edit()`, `generate_diff()` with path validation and unified diff preview
- [x] Content generation tool — LLM generates file content from descriptions (e.g. "create an HTML file with flat CSS theme"), then writes it
- [x] Shell execution tool — `execute_command()` with blocked command safety list, `execute_git()` wrapper
- [x] Action receipts — `ActionReceipt` dataclass, SQLite `action_receipts` table, `GET /api/action-receipts` endpoint
- [x] Git tool — commit, push, branch ops via `git_exec`, gated by high-tier checkpoint
- [x] All Layer 3-4 tools require checkpoint confirmation — diff/command preview shown in action card
- [x] Diff viewer in action card — syntax-highlighted unified diff (green/red/blue) rendered above Yes/No buttons
- [x] Command preview in action card — `$ command` shown in code block before shell execution
- [x] Deterministic responses for Layer 2 tools — file_read, dir_list, project_scan show actual content, not LLM summary
- [x] Tool context carry-forward — recent tool output injected into conversational context for follow-up questions (120s window)
- [x] FilePill component — interactive inline file path chips in chat messages (icon, tooltip, click-to-copy)
- [x] Auto-detect file paths in messages — regex detection renders paths as FilePills in assistant messages
- [x] `referenced_files` metadata field in message type for structured file references
- [x] Composer + button — attachment menu (file picker, folder picker, working dir, manual path entry)
- [x] Attached path pills — removable pills in top bar, prepended to message on send
- [x] `[dir:]` / `[file:]` prefix parsing — intent classifier extracts attached path references for file operations
- [x] Backslash path normalization — Windows `\` paths matched and normalized to `/` in intent classifier
- [x] Full path folder picker — replaced browser API (name only) with direct path prompt for absolute paths
- [x] Typo-tolerant file write regex — catches "gnerate", "genrate", etc.
- [x] Claude/OpenAI brand logos in model selector with uniform `currentColor` styling
- [x] File read tool — read files, list directories, gated by allowed paths
- [x] Project scanner — git status, branch, recent commits, file tree via subprocess
- [x] Allowed paths config — `GET/PUT /api/settings/allowed-paths`, enforced on all file ops

### v1.8 (March 24 early morning)
- [x] System info tool — `psutil` wrapper: CPU, RAM, GPU, disk, running processes, active window
- [x] System info agent intent — "how's my system?", "what am I running?" routes to `system_info` tool (Layer 1, no gate)
- [x] System info API endpoint — `GET /api/system/status`
- [x] Heartbeat system awareness — system snapshot sampled every heartbeat cycle with gaming/idle detection
- [x] Stop generation button — abort active SSE stream via AbortController, finalize partial response, Escape key wired
- [x] Skill install pipeline validated on live site (nickblockdesigns.com/SKILL.md)

### v1.7 (March 23 late evening)
- [x] Action card UI — checkpoint-driven quick-reply (Yes/No/Custom), replaces pattern-matching approach
- [x] Silent checkpoint confirmation — button press sends without user message bubble in chat
- [x] Moltbook end-to-end — skill.md parsed, credentials injected, API called, result rendered through pipeline
- [x] Skill.md template — reusable pattern for new services (`data/managed_skills/_template/SKILL.md`)
- [x] Skill install pipeline — "add skill from URL" fetches, parses frontmatter, saves locally, registers, prompts for API key
- [x] Skill install memory facts — Aether remembers installed skills
- [x] Deterministic skill install response — no LLM hallucination on install results
- [x] Copilot page hero graph (sticky behind content, slides over on scroll)
- [x] Sidebar flush-left with no rounded corners
- [x] Showcase page removed
- [x] Docs page Changelog/Roadmap buttons wired to backend doc_map

### v1.6 (March 23 evening)
- [x] Pipeline trace — real SSE status events replacing fake heartbeats
- [x] Belief classifier wired into contradiction ledger — XGBoost drives type/policy during `record_contradiction()`
- [x] Cookie leak fix — Claude Tier 2 checks `cloud_claude_enabled` before calling
- [x] Typo-resilient slot matching — "favortie", "favorit" etc now match
- [x] Memory demotion filter — skips model_output/system/tool_receipt sources
- [x] Adversarial identity probes — builder questions route through self-referential with memory lookup
- [x] auto_fact_checker crash fix — hallucinations list/dict mismatch
- [x] Name extraction disabled — names sourced from Settings > Profile, not conversation inference
- [x] Profile name authority chain — `auth.display_name` is canonical; memory slots sync to match
- [x] Profile settings UI — Display Name, Preferred Nickname, Agent Name fields
- [x] Stale profile data cleanup
- [x] Sessions renamed to versions (v1.0–v1.6)
- [x] `docs/INDEX.md` documentation index

### v1.5 (March 23 morning/afternoon)
- [x] Escalation policy — `local_only` blocks all cloud fallback; per-tier circuit breaker
- [x] Query-aware routing — token budget > 6000 skips local; gate_boost > 0.10 skips local
- [x] Belief classifier package — `packages/belief_classifier/`
- [x] Reflection-to-behavior loop — `self_model.get_behavioral_directives()` with 7 domain categories
- [x] Adaptive gate thresholds — `blindspot_gate_boost` (0.0-0.15)
- [x] Frontend pill cards — generation source badges + governance indicator
- [x] Cloud usage tracking DB + `/api/cloud-usage/summary`
- [x] ViLT test harness — SFT baseline: 75% accuracy, 85% GC pass
- [x] Full subsystem audit — 16 active + 11 dormant catalogued
- [x] ROADMAP.md created

### v1.4 (March 22 evening - March 23 early morning)
- [x] Cloud generation fallback chain (local -> OpenAI -> Claude)
- [x] Settings page full rewrite (profile, cloud, model toggles, usage stats)
- [x] Memory compression (tier-based, 482 lines)
- [x] Cloud features module (315 lines) + usage logger (358 lines)
- [x] Frontend glassmorphism overhaul (48 components)
- [x] README rewritten

### v1.3 (March 21)
- [x] LLM tool loop — iterative agent execution
- [x] Self-reflection loop in heartbeat (7 self-model slots)
- [x] Compression lab (volatility-gated tiers, CogniSeed, 31/31 tests)
- [x] Checkpoint layer + model routing (qwen3:14b)

### v1.2 (March 6-20)
- [x] Eval harness, correction surface UI, telemetry page
- [x] Agent loop + runtime config
- [x] Hybrid LLM routing, Telegram integration
- [x] DNNT micro-transformer, background learner, TrustGate

### v1.0 (January 3-14)
- [x] CRT core math, trust decay, contradiction detection
- [x] GroundCheck integration
- [x] CRT API + React frontend
- [x] VILT proof of concept (SmolLM-135M: 88% acc, Qwen 1.5B: 88% acc)

---

## IN PROGRESS — Intelligence & Autonomy Layer (v2.3+)

### Sprint 5: External Integrations (ad hoc, no dedicated sprint)
Skill.md files + credentials through existing pipeline. Add as needed:
- [ ] Weather, calendar, maps, email — each is ~30 min of skill.md + credential setup

### Sprint 8: Sub-Agent Interface + Delegation Protocol ← NEXT
- [ ] Agent protocol ABCs — MemoryAgent, ToolAgent, ReflectionAgent, LearningAgent
- [ ] Delegation — Aether breaks complex requests into subtasks, assigns to specialized agents
- [ ] Trust propagation — sub-agent outputs inherit trust scores from their source data
- [ ] Agent receipts — every sub-agent action logged through the same receipt system
- [ ] Parallel execution — independent subtasks run concurrently with result aggregation
- [ ] "Plan a trip" → flight agent + hotel agent + maps agent → results merged through CRT governance

### Sprint 9: Synthesis Responses
- [ ] Worldview questions answered from compressed belief trajectories, not individual fact recall
- [ ] "What do I care about?" — patterns across hundreds of memories distilled into thematic summary
- [ ] "How have I changed?" — temporal belief trajectory analysis showing opinion/preference drift
- [ ] Synthesis confidence — how representative is the summary vs. cherry-picked memories
- [ ] Contradiction-aware synthesis — surfaces unresolved tensions in the user's belief system

### Sprint 10: Volatility-Gated Context Window
- [ ] High-volatility memories get more context budget during retrieval
- [ ] Dynamic context allocation based on query relevance + memory uncertainty
- [ ] Volatile facts surfaced proactively — "you recently changed your mind about X, using the new value"
- [ ] Context compression — stable high-trust facts compressed, volatile low-trust facts preserved in full
- [ ] Budget-aware retrieval — total context window managed as a resource, not unlimited

---

## BACKLOG (do whenever, not blocking)

### Productization
- [ ] Auto-login / default session on localhost (uid=1)
- [ ] GroundCheck → PyPI (standalone package)
- [ ] Eval harness on live system
- [ ] Multi-user scaffolding (user_id scoping, separate memory spaces)

### Training & Classification
- [ ] Belief classifier on real ledger data
- [ ] ViLT live pipeline — heartbeat triggers weight-level correction on persistent blindspots

### Frontend Polish
- [ ] Copilot page visual hierarchy + API dedup
- [ ] Code page (dedicated project/file interface with syntax highlighting)

---

## Architecture Principles

### Design Laws
1. The mouth should never outweigh the self
2. Contradictions are preserved unless resolution is earned
3. Structure should emerge, not be hardcoded

### Access Layer Model
```
Layer 1: Read system info     → no gate (heartbeat, passive)
Layer 2: Read files/projects  → low gate (first access checkpoint, then trusted)
Layer 3: Write files/code     → high gate (always checkpoint, show diff)
Layer 4: Shell execution      → highest gate (always checkpoint, show command)
Layer 5: External APIs        → per-service gate (skill system, already built)
Layer 6: Desktop control      → action-level gate (safe actions free, dangerous actions checkpoint)
```

### The Pitch
"The moat is not the generator. It's the memory governance and truth-preserving control structure around generation."

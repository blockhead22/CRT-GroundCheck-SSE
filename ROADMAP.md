# CRT/Aether Roadmap
Last updated: March 24, 2026 (v1.9)

---

## DONE

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

## IN PROGRESS — Personal Assistant & Intelligence Layer (v2.0+)

### Sprint 4: Proactive & Scheduled Actions ← NEXT
- [ ] Commitment governance — reminders/scheduled tasks as commitments with status/deadline/consequence
- [ ] Time-aware heartbeat — scans for due commitments each tick, fires notifications
- [ ] Natural language time parsing — "at 10:30pm", "every weekday at 9am", "in 5 minutes"
- [ ] Notification delivery — browser Web Notifications via SSE + system message injection in chat
- [ ] Proactive triggers — pattern detection (trip planning, deadlines, health) fires contextual suggestions
- [ ] Heartbeat resource management — kill/restart ollama based on gaming/idle detection

### Sprint 5: External Integrations (ad hoc, no dedicated sprint)
Skill.md files + credentials through existing pipeline. Add as needed:
- [ ] Weather, calendar, maps, email — each is ~30 min of skill.md + credential setup

### Sprint 6: Dynamic Slot Discovery
- [ ] Mine contradiction ledger for slot exclusivity patterns — which slots always resolve to one value vs. coexist
- [ ] Replace hardcoded `EXCLUSIVE_SLOTS` list with learned slot behavior model
- [ ] Slot type classifier — exclusive (favorite_color), additive (hobby), temporal (location), hierarchical (role)
- [ ] Feedback loop — new contradictions auto-classified with resolution policy based on learned patterns
- [ ] Slot confidence scores — how certain is the system that a slot is exclusive vs. additive

### Sprint 7: Intent Router (replace keyword routing)
- [ ] ML-based intent classifier replacing regex patterns in `classify_intent()`
- [ ] Multi-intent detection — "check my system and read the package.json" routes to two tools
- [ ] Ambiguity handling — low-confidence intents trigger clarification instead of wrong routing
- [ ] Intent embeddings — semantic similarity to intent prototypes instead of keyword matching
- [ ] Graceful fallback — unknown intents route to conversational with explanation, not silent failure

### Sprint 8: Sub-Agent Interface + Delegation Protocol
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
```

### The Pitch
"The moat is not the generator. It's the memory governance and truth-preserving control structure around generation."

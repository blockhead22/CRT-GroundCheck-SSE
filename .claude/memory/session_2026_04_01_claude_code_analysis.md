---
name: Session 2026-04-01 — Claude Code Source Analysis + Cookie Loop Fixes
description: Deep analysis of leaked Claude Code source (src/src/), architectural comparison to CRT, patterns worth absorbing vs what CRT does better. Four Cookie orchestrator loop fixes shipped.
type: project
---

## Claude Code Source Analysis

Full source at `D:\AI_round2\src\src\` — 53 top-level entries, TypeScript codebase.

### Architecture (5 Layers)

**Layer 1: Query Engine** (`QueryEngine.ts`, `query.ts`)
- One instance per conversation, maintains mutable messages across turns
- System prompt assembly: memoized sections with cache invalidation
- Token budgeting per-turn and per-conversation
- Tool orchestration via `StreamingToolExecutor` (concurrent reads, serial writes)
- Compaction: 50K post-compact budget, restores top 5 files by relevance, 5K per skill, 25K skills total

**Layer 2: Coordinator/Worker** (`coordinator/`)
- Coordinator AI synthesizes research, directs workers
- Workers spawned via Agent tool, run autonomously with restricted tool subsets
- Simple mode: Bash/Read/Edit only. Full mode: all tools + MCP
- Cross-worker state: durable scratchpad directory
- Workers report via `<task-notification>` XML blocks

**Layer 3: Tool System** (`Tool.ts`, `tools.ts`)
- 60+ tools with `buildTool()` registration
- `shouldDefer`: tools not loaded until ToolSearch round-trip finds them (context savings)
- `alwaysLoad`: bypass defer for critical tools
- `isConcurrencySafe()`: reads parallel, writes serial
- Permission: per-tool deny/allow/ask rules + AI-powered auto-classifier

**Layer 4: Task/Daemon Runtime** (`Task.ts`, `tasks/`)
- 6 task types: bash, agent, remote_agent, teammate, workflow, monitor + dream (proactive/Kairos)
- State machine: pending → running → completed/failed/killed
- Disk-buffered output with resume-safe `outputOffset`
- Task registry in AppState for UI

**Layer 5: Memory/Context** (`memdir/`, `context.ts`, `services/compact/`)
- MEMORY.md index → topic files in directory
- Auto-discovery: recursive CLAUDE.md walk, dedup injection
- Epistemically flat — no trust, no contradictions, no belief/speech separation

### Supporting Systems
- `bridge/` — always-on REPL ↔ claude.ai (HTTP+WebSocket, state machine)
- `hooks/` — pre/post compact, post-sampling, stop-failure lifecycle hooks
- `skills/` — directory-based `.md`/`.js` skill loading with frontmatter
- `buddy/` — animated companion sprite (Kairos-only, cosmetic)
- `voice/` — voice input
- `vim/` — vim keybinding mode
- `plugins/` — plugin system with marketplace
- `remote/` — CCR daemon execution

### Patterns Worth Absorbing (ranked by CRT leverage)

1. **Concurrent tool executor** — `isConcurrencySafe()` per tool, reads parallel, writes serial
2. **Task taxonomy** — 6 typed task states with disk-buffered output and resume offsets
3. **Coordinator/swarm mode** — dedicated coordinator prompt, worker restrictions, shared scratchpad
4. **Deferred tool loading** — `shouldDefer` saves context window, ToolSearch round-trip
5. **Selective file reinjection post-compact** — top 5 by relevance, token budgets
6. **Lifecycle hooks at compaction boundaries** — where belief corruption happens
7. **AI-powered permission classifier** — separate classifier call with denial history
8. **Bridge architecture** — daemon mode state machine (ready→connected→reconnecting→failed)
9. **Speculation pipeline** — background prediction while user idle, abort capability

### What CRT Already Does Better (Do Not Regress)
- Trust-weighted memory vs flat markdown
- Contradiction preservation (they don't have one)
- Belief/speech separation (they don't have one)
- 6 immune agents with lazy eval + tier escalation (they have permission rules)
- Authority-gated writes with trust ceilings (they have sandbox rules)
- Trust-tiered compaction (preserves what matters, not just what's recent)

### Irrelevant to CRT
- Buddy/sprite system, vim mode, plugin marketplace, voice, bridge to claude.ai

---

## Cookie Loop Fixes Shipped

### Fix 1: `for` → `while` loop (plan doesn't consume iteration slot)
**File:** `personal_agent/cookie_orchestrator.py`
- Plan is a declaration, not work — shouldn't cost a slot
- `think`, `tool_call`, `spawn_agent` increment `iteration` explicitly
- `respond` and `ask_user` break the loop (no increment)
- Safety cap: `_total_turns = max_iterations + 5` prevents infinite plan loops

### Fix 2: Warning threshold `<= 1` → `== 0`, softer language
**File:** `personal_agent/cookie_orchestrator.py`
- Old: "You MUST respond now" at 1 slot remaining → Claude panics, never writes
- New: "Last action slot" at 0 remaining → Cookie can still execute final step

### Fix 3: Remaining budget through suspend/resume
**File:** `routes/chat.py`
- `ask_user`, `diff_write`, and nested ask_user suspend paths store `remaining_iterations`
- Resume path: `max(3, _r_remaining)` instead of hardcoded `8`
- Log shows remaining iterations on resume

### Fix 4: Checkpoint metadata verified
- `_write_path` and `_write_content` present in orchestrator event (lines 1627-1628)
- Resume accesses via `diff_data._raw_meta._write_path`
- Storage is in-memory dict — no serialization/truncation risk

**Net effect:** plan+read+write = plan (free) + 10 working slots. Was: plan (slot 0) + 9 slots with panic at slot 8.

### Prior fixes from GPT (same session, before Claude Code analysis)
- Routing gate: Layer 4 `_layer4_orchestrator` now bypasses `_needs_cookie` (was being vetoed)
- `file_read`/`file_write` added to `_TOOL_REQUIRING_INTENTS`
- `llm_local` mode redirected to Cookie instead of broken agent loop path

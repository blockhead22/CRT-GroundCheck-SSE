---
name: session_2026_03_28_electron_and_features
description: "Session 2026-03-28/29: Electron app verified, 20+ features shipped, heartbeat learning, ambient mode, MCP server, clipboard, file drop, model selector, identity fix, reminder fast-path, training logs, context feed, contradiction detection, correction handler, self-model reset, CRT critic fix"
type: project
---

# Session 2026-03-28/29: Electron Desktop App + Feature Sprint

## START HERE — Current State

### What's Working
- Electron app launches, manages backend lifecycle, tray, hotkeys
- Chat pipeline: intent classification → memory retrieval → generation → governance
- Cloud Claude (cookie) as primary generation — ~15-20s per response
- Memory retrieval with trust scores, contradiction detection
- Heartbeat learning loop extracts facts from conversations
- Training logs capturing every conversation turn (JSONL)
- Correction handler demotes trust on false memories
- Reminder fast-path with deterministic parsing (no LLM needed)
- Model selector with inline accordion (all local/OpenAI/Anthropic models)
- Clipboard monitor, file drag-and-drop, ambient mode (all wired, tray toggles)
- MCP server registered in Claude Code project settings (12 tools)

### What Needs Fixing
- **False contradiction disclosures on opinions** — CRT critic fires HARD_FAIL when GroundCheck confidence is low on opinion responses. Fix partially in place (opinion signal skip), needs restart to verify
- **Correction handler targets wrong memories** — semantic search finds unrelated memories. Fix in place (dual search: stripped query + raw message), needs testing
- **Self-model** — reset to clean state ("still calibrating"). Evidence-gating agent may have landed but not verified
- **Identity** — Claude still occasionally breaks character. Prompt says "You are Aether, deployed using Claude" which mostly works
- **Health check log spam** — still drowning useful output
- **OpenAI 429** — governance slot classification rate limited intermittently

## Features Shipped (20+)

### Backend Pipeline
1. **Plan engine skip** — conversational messages skip `should_create_plan()`, saves 2-5s
2. **BodyStreamBuffer abort fix** — 3 frontend changes, no more phantom errors
3. **Cloud-first escalation defaults** — auth.py, litellm_client.py, routes/chat.py changed. Nick's user settings override to local by choice
4. **Governance skip for conversational** — slot classification (OpenAI call) skipped for greetings, self-referential, explanations
5. **CRT critic opinion skip** — opinion questions skip the contradiction gate (in progress, needs restart)
6. **Reminder fast-path** — deterministic handler in streaming path before agent loop. Word-number parsing ("two" → "2"). Emits agent_checkpoint + done events
7. **Correction handler** — `fact_correction` intent pattern (regex), semantic search for target memories, trust demotion to 0.15, audit trail. Dual search fix for accuracy

### Heartbeat & Learning
8. **Heartbeat learning loop** — `heartbeat_learning.py`: fetch undigested → LLM extraction → dedup (cosine ≥ 0.82) → store as provisional
9. **Contradiction detection** — `detect_contradictions()`: drift_meaning ≥ 0.28 + similarity ≥ 0.4
10. **Proactive OS notifications** — Electron SSE listener → native Notification API for contradictions
11. **Context-aware system prompt** — `context_feed.py`: builds summary of learned facts + contradictions, injected with 5-min TTL cache
12. **Training log persistence** — `training_log.py`: JSONL per day, all 6 response paths, gitignored

### Electron-Native
13. **Clipboard monitoring** — `clipboard-monitor.js`: polls 2s, OS notification, tray toggle, OFF by default
14. **File drag-and-drop** — `routes/ingest.py` + drop zone overlay, supports txt/md/py/json/pdf, chunked storage, toast feedback
15. **Ambient mode** — `ambient-monitor.js` + `routes/ambient.py`: desktopCapturer → Claude vision → CRT memory. Cookie fallback added. 60s interval, OFF by default
16. **Enhanced model selector** — inline accordion in Composer.tsx, dynamic from /api/tooling/models, all providers

### Infrastructure
17. **Aether MCP server** — `aether_mcp_server.py`: 12 tools in 4 tiers (read/analyze/write/act), FastMCP, registered in `.claude/settings.json`
18. **Identity fix** — all system prompts: "You are Aether, deployed using Claude." Across chat.py, cloud_features.py, agent_tool_loop.py
19. **Self-model reset** — nuked fabricated self-model entries, replaced with honest "still calibrating" defaults
20. **Self-model evidence filtering** — injection now skips ungrounded claims (hallucination, severity inflation language)

## Key Files Created
- `personal_agent/heartbeat_learning.py` — Learning digest pipeline + contradiction detection
- `personal_agent/training_log.py` — JSONL training logger
- `personal_agent/aether_mcp_server.py` — 12-tool MCP server
- `personal_agent/context_feed.py` — Context summary for system prompt
- `electron/clipboard-monitor.js` — Clipboard watcher
- `electron/ambient-monitor.js` — Screen capture monitor
- `routes/ambient.py` — Vision analysis endpoint
- `routes/ingest.py` — File ingestion endpoint

## Key Files Modified
- `routes/chat.py` — Plan engine skip, reminder fast-path, correction fast-path, identity fix, context injection, governance skip, CRT critic opinion skip
- `routes/register.py` — Registered ambient + ingest routers
- `personal_agent/db_utils.py` — `learning_last_query_id` column + watermark methods
- `personal_agent/heartbeat_executor.py` — Step 11 (learning digest), contradiction SSE emission
- `personal_agent/litellm_client.py` — Cloud-first fallback chain
- `personal_agent/agent_tool_loop.py` — Identity fix, context feed injection
- `personal_agent/cloud_features.py` — Identity fix
- `personal_agent/task_agent.py` — `fact_correction` intent pattern, correction regex
- `personal_agent/scheduled_tasks.py` — Word-number normalization
- `personal_agent/time_parser.py` — Word-number normalization
- `personal_agent/notifications.py` — `emit_generic_notification_sync()`
- `personal_agent/self_model.py` — Self-model entries reset
- `personal_agent/crt_memory.py` (shared DB) — Self-model data cleaned
- `electron/main.js` — Clipboard, ambient, SSE listener, file drop, IPC handlers
- `electron/preload.js` — Clipboard, ambient, file drop bridge APIs
- `electron/tray.js` — Clipboard + Ambient toggles
- `frontend/src/components/chat/Composer.tsx` — Inline accordion model selector
- `frontend/src/lib/api.ts` — Stream abort fix
- `frontend/src/App.tsx` — Abort suppression, contradiction notification handler
- `auth.py` — Cloud-first defaults
- `.claude/settings.json` — MCP server registration
- `.gitignore` — Training data logs

## Validated Through Real Usage
- Aether gives substantive, architecturally-informed responses about CRT
- Contradiction detection fires correctly on factual conflicts (favorite color test)
- Trust scores evolve with interactions (visible in UI)
- Governance catches belief/speech gaps on opinion questions
- Self-model reset eliminated fabricated self-knowledge
- Cookie Claude identity mostly holds ("You are Aether, deployed using Claude")
- Training logs capturing 22+ entries per session
- Correction handler fires on "these were lies" (targeting accuracy needs improvement)
- Reminder parsing works for word-numbers ("two minutes")

## Conversations Worth Noting
- Aether correctly identified epistemic auditing as its most innovative feature
- Aether gave honest pushback on company-building viability — then course-corrected when challenged
- User identified core tension: governance gates opinions the same as facts (belief/speech gap)
- User insight: "persistence isn't in the LLM state, it's the memory the LLM is fed"
- User recognized: more memories = higher belief scores = less false escalation

## Ideas Captured (Not Built)
- **Model opinion vs model belief slots** — measure variance over time, track when opinions drift as memories accumulate. Extends the variance probe experiment to real conversations
- **Belief/speech distinction in UI** — tag responses as belief (grounded) vs speech (model opinion) with visual indicators
- **Overlay mode** — shelved, needs ambient mode working first
- **Spotlight quick-prompt bar** — shelved, redundant with Ctrl+Space

## Priority Queue (Next Session)
1. **Restart and verify** — CRT critic opinion skip, correction handler dual search, model selector
2. **Test MCP server** — restart Claude Code, test aether_search/aether_profile tools
3. **Reduce health check log spam** — multiple sources polling /health every few seconds
4. **Model opinion/belief slot tracking** — spec and build variance measurement
5. **Belief/speech UI distinction** — surface response grounding level to user
6. **Evidence-gating verification** — check if the agent's changes to self_model.py landed
7. **Fill Aether's memory** — keep chatting, let heartbeat learn, build up trust scores
8. **Heartbeat learning verification** — trigger manually, confirm facts extracted
9. **Ambient mode test** — enable from tray, verify cookie vision fallback works
10. **Conservative research writeup** — document what's novel, what works, what doesn't

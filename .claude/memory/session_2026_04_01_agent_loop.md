---
name: Session 2026-04-01 Night to 04-02 — Agent Loop Shipped
description: Full agent loop working end-to-end. spawn_agent, followup chips, FORCE_RESPOND, response depth, Cookie to Agent Loop rename, auto-continuation planned.
type: project
---

## CODEX-ONLY CONTINUATION

For the follow-on hardening work completed by Codex on 2026-04-02, see:
- `session_2026_04_02_codex_tightening.md`

That note contains the clearly separated **CODEX-ONLY SECTION** and **Worklog** for:
- runtime-state externalization
- SSE/WS contract freeze
- GovernedTask lifecycle v1
- `chat.py` split around GovernedTask

## What shipped

**Agent Loop (formerly Cookie) fully operational**
- Routing gate: project_scan, search_code, multi_intent, web_search all route correctly
- Plan to thinking: no preamble in response text
- FORCE_RESPOND: hard override on last iteration guarantees an answer
- Response depth: Rule 12 + 3000 token limit on last 2 iterations
- Context bleed fix: window=2, 150 chars, labeled "NOT the current task"

**spawn_agent end-to-end**
- Parent spawns child with budget splitting (max(3, parent_remaining//2))
- Child runs own tool loop, returns summary to parent
- Fixes: LogStep result to result_preview, context kwarg removed
- Known: child plan eats 1 of 3 iterations (same bug parent had, not fixed)
- Tested: memory_recall searches, gpt_log_search + gpt_log_context

**Followup suggestion chips**
- Backend: respond action accepts followups[] + complete:bool
- SSE: followup_suggest event flows through api.ts + ws.ts
- Frontend: centered chips in ChatThreadView with dismiss button
- Routing: [followup] prefix forces agent loop entry (fixes crash where conversational followups hit legacy path)

**Cookie to Agent Loop rename**
- 11 files updated: cookie_orchestrator.py, chat.py, spawn_agent.py, App.tsx, MessageBubble.tsx, SettingsPage.tsx, ActionCard.tsx, ChatThreadView.tsx, routing_beliefs.py, test_orchestrator.py, litellm_client.py
- Variables: _needs_cookie to _needs_agent_loop, _cookie_entry to _orch_entry
- generation_source: "agent_loop" (was "cookie_orchestrator")
- Browser cookie auth references preserved

**search_code hardening**
- --max-filesize 256K on rg
- file_extensions and file_pattern arg support
- Excluded: *.min.js, *.min.css, *.lock, *.map, _write_copilot_page.py, src/src
- Python fallback: getsize() guard, .claude in skip dirs

**dir_list improvements**
- Missing directory: returns error + project directory hints
- src/ directory: returns "NOTE: third-party reference code, NOT project code"

**Pipeline viz**
- PipelineCollapse: thinking stubs, tool rows with timing, drift events with alignment
- Summary: "N thoughts . N tools . N drift"
- History persistence via pipelineStepsRef
- drift + session_state SSE events wired end-to-end
- Token 742>512 warning silenced
- toLowerCase crash guards

**Project board updated** at D:\projectboard (port 5199)
- 8 cards moved to DONE, 6 new DONE cards, 6 new PLANNED cards

## Not yet done

- **Auto-continuation**: Plan at docs/plans/auto_continuation.md. Not implemented.
- **Child plan budget**: Plan costs 1 of 3 child iterations.
- **Proactive turns (WS registry)**: ConnectionRegistry + OutboxQueue.
- **Discord token**: Still broken.
- **ask_user generic e2e test**: Diff path tested, generic untested.
- **Subagent visual nesting**: Pipeline panel shows flat.
- **System tightening**: chat.py split, DB externalization, event contract freeze. See audit notes.

## Next session priorities

1. **System tightening** (recommended first): Externalize DBs, split chat.py, freeze event contract
2. **Auto-continuation**: Plan ready at docs/plans/auto_continuation.md
3. **Child plan budget fix**: Make plan free for child agents
4. **Proactive turns**: WS registry for async push

## Key files modified this session

- personal_agent/cookie_orchestrator.py — Rules 11+12, FORCE_RESPOND, token limit, fixes, rename
- routes/chat.py — followup_suggest SSE, [followup] routing, _TOOL_REQUIRING_INTENTS, rename
- personal_agent/spawn_agent.py — context fix, rename
- personal_agent/embeddings.py — truncation + warning filter
- frontend/src/App.tsx — followups, drift, session_state, thinking handlers
- frontend/src/components/chat/ChatThreadView.tsx — followup chips
- frontend/src/components/chat/PipelineCollapse.tsx — summary, session notes, timer
- frontend/src/lib/api.ts + ws.ts — new event types + parsers
- docs/plans/auto_continuation.md — next feature plan

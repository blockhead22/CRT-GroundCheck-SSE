---
name: Session 2026-04-02 - Codex Tightening Pass
description: Codex-only implementation log for boundary hardening: runtime-state externalization, stream contract freeze, GovernedTask lifecycle, and chat.py split.
type: project
---

# CODEX-ONLY SECTION

This file is a **Codex-only continuity note**.

Purpose:
- record implementation work completed by Codex after the Agent Loop session
- separate architectural tightening from the broader product/research narrative
- give the next agent a clean technical handoff

Scope of this pass:
- runtime/data boundary hardening
- SSE/WS contract freeze
- first-class governed task lifecycle
- `chat.py` split around governed-task orchestration

Out of scope:
- auto-continuation
- proactive turns / WS registry
- belief-aware worker handoff packets
- broader repo split execution

## Worklog

### 1. Matrix audit saved
- Full system matrix audit saved at `D:/AI_round2/docs/audits/system_matrix_audit_2026-04-02.md`
- Priority order established:
  1. externalize runtime state
  2. freeze SSE/WS event contract
  3. make task lifecycle first-class
  4. split `routes/chat.py`
  5. add system acceptance coverage

### 2. Runtime state externalization shipped
- Added shared runtime path layer in `personal_agent/runtime_paths.py`
- Core mutable stores now resolve through runtime-root helpers instead of assuming repo-local DB paths
- Added `GET /api/runtime/status` in `routes/misc.py` to report the active runtime data root and resolved write locations
- Added smoke coverage:
  - `tests/test_runtime_paths.py`
  - `tests/test_runtime_state_smoke.py`

Outcome:
- repo tree is no longer the implicit source of truth for hot runtime state
- runtime write locations are now inspectable

### 3. SSE/WS stream contract frozen
- Added backend stream normalizer in `personal_agent/stream_events.py`
- Unified SSE + WS event normalization and frontend dispatch paths
- Chat/WS/frontend now share one canonical event envelope instead of drifting independently
- Coverage:
  - `tests/test_stream_event_contract.py`

Outcome:
- stream/event boundary is now explicit
- frontend/backend contract drift should be much lower

### 4. GovernedTask Lifecycle v1 shipped
- Added durable governed task model in `personal_agent/governed_task.py`
- Extended `ThreadSessionDB` in `personal_agent/db_utils.py` with:
  - `governed_tasks`
  - `governed_task_events`
- Added `/api/tasks/active` in `routes/tasks.py`
- Threaded governed-task persistence/status through agent-loop/orchestrator paths
- Compatibility adapters keep `get_pending_checkpoint()` / `get_suspended_loop()` DB-backed during transition
- Coverage:
  - `tests/test_governed_task_runtime.py`

Outcome:
- task lifecycle state is durable, inspectable, and restart-safe
- in-memory suspended-loop state is no longer primary truth

### 5. `chat.py` split around GovernedTask
- Added:
  - `routes/chat_runtime.py`
  - `routes/chat_governed_resume.py`
  - `routes/chat_agent_loop_runner.py`
  - `routes/chat_orchestrator_runner.py`
- `routes/chat.py` now delegates:
  - stream runtime/event tagging
  - governed resume/checkpoint handling
  - agent-tool-loop execution
  - orchestrator execution
- Added route-level split coverage:
  - `tests/test_chat_route_split.py`

Outcome:
- `chat.py` is now more coordinator-like
- task/runtime semantics are no longer owned only by one giant route body

Important note:
- `chat.py` still contains some legacy compatibility branches as fallback code
- the delegation cutover is live, but a future cleanup pass can delete the residual inline paths once confidence is high

## Verification

Focused checks that passed during this Codex pass:
- `pytest -q tests/test_runtime_paths.py tests/test_runtime_state_smoke.py`
- `pytest -q tests/test_governed_task_runtime.py tests/test_stream_event_contract.py`
- `pytest -q tests/test_chat_route_split.py tests/test_governed_task_runtime.py tests/test_stream_event_contract.py`
- `py_compile` for the new route/runtime modules and `routes/chat.py`

Known note:
- `tests/test_chat_pipeline_regressions.py` still has unrelated existing failures around retrieval/profile-summary behavior; Codex did not treat those as part of this tightening pass

## Current System Position

The highest-ROI hardening sequence is now:
1. runtime boundary
2. event contract
3. task lifecycle
4. `chat.py` split

That means the next phase can shift back toward features, but on safer footing.

## Next Recommended Work

1. system acceptance suite for:
   - ask_user suspend/resume
   - checkpoint approve/deny
   - followup `complete=false`
   - `/api/tasks/active` recovery
   - completion/failure/cancel states
2. auto-continuation on top of `needs_followup`
3. proactive turns / WS registry
4. belief-aware worker handoff packets

## Handoff Summary

If the next agent starts here, read in this order:
1. this file
2. `D:/AI_round2/docs/audits/system_matrix_audit_2026-04-02.md`
3. `D:/AI_round2/docs/plans/auto_continuation.md`
4. `D:/AI_round2/routes/chat.py`
5. the new route modules under `D:/AI_round2/routes/`

---

## Addendum - Evening Runtime / Delivery Pass

### Intent

The intent for the evening follow-on pass was:
- finish the missing runtime/delivery spine after GovernedTask + route split
- make selected cloud provider preference actually govern legacy paths too
- turn proactive turns from a concept into a reconnect-safe WS-delivered behavior
- update the project board so it reflects dependency order rather than mixed history

### Additional Worklog

### 6. Acceptance coverage shipped
- Added broader acceptance coverage for:
  - `ask_user` suspend/resume
  - checkpoint approve/deny
  - `complete=false` followups
  - `/api/tasks/active` recovery
  - failure/inactive-task behavior
- Coverage:
  - `D:/AI_round2/tests/test_chat_acceptance_suite.py`

Outcome:
- governed task lifecycle now has route-level acceptance proof, not just unit/runtime proof

### 7. Auto-continuation shipped
- Implemented bounded auto-continuation on orchestrator followups
- Added frontend suppression of followup chips during `complete=false` continuation phases
- Coverage:
  - `D:/AI_round2/tests/test_orchestrator_auto_continuation.py`

Outcome:
- incomplete orchestrator responses can continue in the same turn instead of always surfacing manual followups

### 8. Agentic routing + tool grounding hardened
- Tightened routing for clearly agentic prompts that were falling into conversational fallback
- Hardened orchestrator tool grounding so invented tool names are rejected/corrected against the valid tool registry
- Coverage:
  - `D:/AI_round2/tests/test_agentic_routing_and_tool_grounding.py`

Outcome:
- fewer obvious task prompts should miss the agentic path
- fewer orchestrator runs should die on fake tool names like `Read`

### 9. Auto-continuation observability added
- Added explicit logging / status breadcrumbs for:
  - `followup_suggest`
  - `complete=false`
  - continuation count / pending followup count in terminal metadata

Outcome:
- next live run can distinguish “model never emitted continuation” from “handler dropped it”

### 10. Request-scoped cloud provider routing shipped
- Added request-scoped provider resolution so frontend cloud preference controls primary/fallback order
- Current intended semantics:
  - `cloud_claude` => Claude primary, OpenAI fallback
  - `cloud_openai` => OpenAI primary, Claude fallback
- Legacy broad-recall / synthesis paths were patched so cloud mode no longer accidentally implies Ollama/local
- Coverage:
  - `D:/AI_round2/tests/test_chat_provider_routing.py`

Outcome:
- “selected cloud provider” is now much closer to a real runtime contract across legacy and orchestrator paths

### 11. ConnectionRegistry + OutboxQueue shipped
- Added push-listener support to `D:/AI_round2/personal_agent/outbox.py`
- Reworked `D:/AI_round2/routes/ws.py` into a thread-aware `ConnectionRegistry`
- Removed the old polling-style outbox drain loop in favor of event-driven flush on:
  - thread subscribe
  - outbox push
- Coverage:
  - `D:/AI_round2/tests/test_ws_registry_outbox.py`

Outcome:
- proactive delivery now has a real WS/runtime spine
- outbox delivery is thread-aware and reconnect-friendly on the backend side

### 12. Proactive turns + WS delivery registry started
- Client-side WS behavior patched so the app now:
  - opens the shared WS connection from the main app
  - persists/replays thread subscriptions after reconnect
  - subscribes to known thread channels
  - preserves proactive turns on their target thread instead of dropping them when the thread is not active
  - creates a placeholder thread if a proactive message arrives for an unknown thread
  - tracks unread/background proactive state and surfaces badges in the sidebar
- Touched files:
  - `D:/AI_round2/frontend/src/lib/ws.ts`
  - `D:/AI_round2/frontend/src/App.tsx`
  - `D:/AI_round2/frontend/src/components/Sidebar.tsx`
  - `D:/AI_round2/frontend/src/types.ts`

Outcome:
- proactive delivery now works end-to-end better, but this card is not done yet
- remaining work is validation + richer producer coverage, not basic transport

### 13. Project board corrected to real dependency order
- Board was cleaned so it reflects actual sequencing rather than a mixed ledger/backlog
- `Build ConnectionRegistry + OutboxQueue` moved to done
- `Proactive turns + WS delivery registry` moved to in-progress
- Added missing governance-gap items surfaced by live/system self-audit:
  - `Verified self-audit mode`
  - `Execution beliefs`
  - `Action receipts + verification`
  - `Structural gates for transformation tasks`

Outcome:
- board is now a more accurate roadmap for what should be built next

## Current Position

At this point:
- GovernedTask lifecycle / route split / acceptance / auto-continuation are shipped
- provider preference routing is largely unified for cloud modes
- WS/outbox transport spine is shipped
- proactive turns are partially shipped and currently the active work lane

The main architectural shift from today’s live/system self-audit:
- the next major quality gap is **governed execution**
- not “more intelligence,” but structural verification around actions

## Immediate Next Work

1. finish `Proactive turns + WS delivery registry`
   - live reconnect validation
   - ensure background-thread proactive updates are reliable
   - tighten any remaining producer->outbox paths
2. `Live reconnect/recovery acceptance pass`
   - verify WS reconnect + proactive delivery + governed-task recovery together
3. `Verified self-audit mode`
   - introspection/self-audit prompts may make qualitative claims freely
   - quantitative claims must be trace/ledger-backed or downgraded to qualitative wording
4. `Execution beliefs`
5. `Action receipts + verification`
6. `Structural gates for transformation tasks`

## Practical Resume Point

If resuming implementation, start here:
1. `D:/AI_round2/routes/ws.py`
2. `D:/AI_round2/personal_agent/outbox.py`
3. `D:/AI_round2/frontend/src/lib/ws.ts`
4. `D:/AI_round2/frontend/src/App.tsx`
5. `D:/AI_round2/frontend/src/components/Sidebar.tsx`

If resuming strategy/governance planning, start here:
1. `C:/Users/block/.claude/projects/D--AI-round2/memory/session_2026_04_02_claude_code.md`
2. this file
3. the project board at `D:/projectboard`

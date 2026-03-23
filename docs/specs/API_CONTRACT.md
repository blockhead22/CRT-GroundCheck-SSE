# CRT API Contract Specification

**Version:** 0.9.0-freeze  
**Date:** February 8, 2026  
**Status:** FROZEN — canonical API contract for all clients

---

## Overview

- **Base URL:** `http://localhost:8000`
- **Protocol:** HTTP/1.1 + SSE (Server-Sent Events for streaming)
- **Auth:** Session-token based (cookie)
- **Content-Type:** `application/json` (except SSE streams)
- **Total Endpoints:** 94 application + 5 framework = 99 routes
- **Routers:** 10 modular APIRouter modules

---

## Router Registry

| Module | Prefix | Endpoints | Domain |
|--------|--------|-----------|--------|
| `auth.py` | `/api/auth` | 6 | Authentication & session management |
| `chat.py` | `/api/chat` | 3 | Conversation (sync, stream, intent) |
| `memory.py` | — | 13 | Memory, profile, facts, docs, dashboard |
| `contradictions.py` | — | 8 | Contradiction ledger & resolution |
| `learning.py` | — | 10 | Training, active learning, feedback |
| `jobs.py` | `/api/jobs` | 4 | Background job management |
| `threads.py` | — | 8 | Thread CRUD, export, reset |
| `scheduled_tasks.py` | — | 7 | Reminders, scheduled thoughts |
| `agent.py` | `/api/agent` | 3 | ReAct autonomous agent |
| `misc.py` | — | 33 | Reasoning, reflection, journal, training, introspection, loops, episodic, research, heartbeat |

---

## 1. Authentication — `/api/auth`

| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| POST | `/api/auth/register` | Register new user | `AuthRegisterRequest` | `AuthLoginResponse` |
| POST | `/api/auth/login` | Login | `AuthLoginRequest` | `AuthLoginResponse` |
| POST | `/api/auth/logout` | Logout | — | `{status}` |
| GET | `/api/auth/me` | Current user | — | `AuthMeResponse` |
| POST | `/api/auth/sync-chats` | Sync threads | `SyncChatRequest` | `SyncChatResponse` |
| GET | `/api/auth/load-chats` | Load threads | — | `SyncChatResponse` |

## 2. Chat — `/api/chat`

| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| POST | `/api/chat/send` | Synchronous chat | `ChatSendRequest` | `ChatSendResponse` |
| POST | `/api/chat/stream` | SSE streaming chat | `ChatSendRequest` | `StreamingResponse` (SSE) |
| POST | `/api/chat/intent` | Intent-routed query | `IntentQueryRequest` | `IntentQueryResponse` |

**`/api/chat/send` pipeline:** Memory retrieval → Mirus resonance → DNNT inference → LLM fallback → GroundCheck → Trust evolution → Contradiction check → SSE compression → Response

**`/api/chat/stream` SSE events:** `thinking`, `reasoning`, `content`, `memory`, `contradiction`, `done`, `error`

## 3. Memory — `/api/memory`, `/api/profile`, `/api/facts`, `/api/docs`, `/api/dashboard`

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| GET | `/api/memory/recent` | Recent memories | `list[MemoryListItem]` |
| GET | `/api/memory/search?q=...` | Search memories | `list[MemoryListItem]` |
| GET | `/api/memory/{id}` | Single memory | `MemoryListItem` |
| GET | `/api/memory/{id}/trust` | Trust history | `list[dict]` |
| GET | `/api/profile` | User profile | `ProfileResponse` |
| POST | `/api/profile/consolidate` | Fix multi-value slots | `dict` |
| POST | `/api/profile/set_name` | Set name | `ChatSendResponse` |
| GET | `/api/docs` | List docs | `list[DocListItem]` |
| GET | `/api/docs/{doc_id}` | Get doc | `DocGetResponse` |
| POST | `/api/facts/extract` | Extract facts | `FactExtractionResponse` |
| GET | `/api/facts/structured` | Structured facts for `thread`, `global`, or `effective` scope | `StructuredFactsResponse` |
| GET | `/api/facts/search` | Search structured facts, typically with `scope=effective` | `list[EffectiveFactItem]` |
| GET | `/api/facts/history/{slot}` | Fact slot history | `FactHistoryResponse` |
| GET | `/api/dashboard/overview` | Dashboard stats | `DashboardOverviewResponse` |

## 4. Contradictions — `/api/contradictions`, `/api/ledger`

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| GET | `/api/ledger/open` | Open contradictions | `list[ContradictionListItem]` |
| POST | `/api/ledger/resolve` | Resolve via method | `dict` |
| GET | `/api/contradictions` | All for thread | `dict` |
| GET | `/api/contradictions/work-items` | Prioritized work items | `list[ContradictionWorkItem]` |
| GET | `/api/contradictions/next` | Next highest-priority | `ContradictionNextResponse` |
| POST | `/api/contradictions/asked` | Mark as asked | `dict` |
| POST | `/api/contradictions/respond` | User response | `ContradictionRespondResponse` |
| POST | `/api/resolve_contradiction` | Policy resolution | `ResolveContradictionPolicyResponse` |

**Resolution policies:** `OVERRIDE` (replace), `PRESERVE` (keep original), `ASK_USER` (defer)

## 5. Learning & Feedback — `/api/learn`, `/api/learning`, `/api/feedback`

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| GET | `/api/learn/status` | Training loop status | `LearnStatusResponse` |
| POST | `/api/learn/run` | Trigger training | `dict` |
| GET | `/api/learning/stats` | Learning statistics | `LearningStatsResponse` |
| GET | `/api/learning/events` | Events needing correction | `list[dict]` |
| GET | `/api/learning/corrections` | Recent corrections | `list[CorrectionItem]` |
| POST | `/api/learning/correct/{id}` | Submit correction | `dict` |
| POST | `/api/feedback/thumbs` | Thumbs up/down | `dict` |
| POST | `/api/feedback/correction` | Submit correction | `dict` |
| POST | `/api/feedback/report` | Report issue | `dict` |
| GET | `/api/feedback/stats` | Feedback stats | `dict` |

## 6. Jobs — `/api/jobs`

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| GET | `/api/jobs/status` | Worker status | `JobsStatusResponse` |
| GET | `/api/jobs` | List jobs | `JobsListResponse` |
| GET | `/api/jobs/{job_id}` | Job details | `JobDetailResponse` |
| POST | `/api/jobs` | Enqueue job | `EnqueueJobResponse` |

## 7. Threads — `/api/threads`, `/api/thread`

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| GET | `/api/threads` | List threads | `list[ThreadListItem]` |
| POST | `/api/threads` | Create thread | `ThreadListItem` |
| PUT | `/api/threads/{id}` | Update thread | `ThreadListItem` |
| DELETE | `/api/threads/{id}` | Delete thread | `dict` |
| GET | `/api/thread/export` | Export thread data | `ThreadExportResponse` |
| POST | `/api/thread/reset` | Reset thread | `ThreadResetResponse` |
| POST | `/api/thread/purge_memories` | Purge memories | `ThreadPurgeMemoriesResponse` |
| POST | `/api/tracing/enable` | Toggle tracing | `dict` |

## 8. Scheduled Tasks — `/api/scheduled-tasks`

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| POST | `/api/scheduled-tasks` | Create task | `ScheduledTaskResponse` |
| GET | `/api/scheduled-tasks` | List tasks | `dict` |
| GET | `/api/scheduled-tasks/{id}` | Get task | `dict` |
| DELETE | `/api/scheduled-tasks/{id}` | Cancel task | `dict` |
| POST | `/api/scheduled-tasks/parse-time` | Parse time expression | `dict` |
| POST | `/api/quick-reminder` | Natural language reminder | `dict` |
| POST | `/api/schedule-thought` | Schedule thought | `dict` |

## 9. Agent — `/api/agent`

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| POST | `/api/agent/run` | Run ReAct agent | `AgentRunResponse` |
| POST | `/api/agent/analyze-triggers` | Analyze triggers | `AgentTriggersResponse` |
| GET | `/api/agent/status` | Agent status | `AgentStatusResponse` |

## 10. Misc — reasoning, reflection, journal, training, introspection, loops, episodic, research, heartbeat

### Health
| GET | `/health` | Health check | `HealthResponse` |

### Reasoning Traces
| GET | `/api/reasoning/traces` | List traces | `dict` |
| GET | `/api/reasoning/traces/{id}` | Get trace | `dict` |
| GET | `/api/reasoning/recent` | Recent traces | `dict` |

### Reflection
| GET | `/api/reflection/traces/{id}` | Get reflection trace | `dict` |
| GET | `/api/reflection/thread/{id}` | Thread reflections | `dict` |
| GET | `/api/reflection/journal/{id}` | Journal entries | `dict` |
| POST | `/api/reflection/journal/reply` | Journal reply | `JournalReplyResponse` |

### Journal Settings
| GET | `/api/journal/settings` | Get settings | `JournalSettingsResponse` |
| POST | `/api/journal/settings` | Set settings | `JournalSettingsResponse` |

### Training Data
| GET | `/api/training/stats` | Collection stats | `dict` |
| GET | `/api/training/export` | Export data | `dict` |

### Introspection
| GET | `/api/introspection` | Inner state | `dict` |

### Background Loops
| GET | `/api/loops/stream` | SSE loop updates | `StreamingResponse` |
| POST | `/api/loops/run` | Trigger loops | `LoopRunResponse` |

### Episodic Memory
| GET | `/api/episodic/context` | User context | `dict` |
| POST | `/api/episodic/finalize-session` | Finalize session | `dict` |
| GET | `/api/episodic/preferences` | User preferences | `dict` |
| GET | `/api/episodic/patterns` | Interaction patterns | `dict` |
| GET | `/api/episodic/concepts` | Knowledge graph | `dict` |
| GET | `/api/episodic/summaries` | Session summaries | `dict` |

### Research
| POST | `/api/research/search` | Research query | `ResearchSearchResponse` |
| GET | `/api/research/citations/{id}` | Citations | `ResearchCitationsResponse` |
| POST | `/api/research/promote` | Promote to belief | `ResearchPromoteResponse` |

### Heartbeat
| GET | `/api/heartbeat/status` | Loop status | `dict` |
| POST | `/api/heartbeat/start` | Start loop | `dict` |
| POST | `/api/heartbeat/stop` | Stop loop | `dict` |
| GET | `/api/threads/{id}/heartbeat/config` | Thread config | `HeartbeatConfigResponse` |
| POST | `/api/threads/{id}/heartbeat/config` | Update config | `HeartbeatConfigResponse` |
| POST | `/api/threads/{id}/heartbeat/run-now` | Manual trigger | `HeartbeatRunResponse` |
| GET | `/api/threads/{id}/heartbeat/history` | Run history | `HeartbeatHistoryResponse` |
| GET | `/api/heartbeat/heartbeat.md` | Get HEARTBEAT.md | `HeartbeatMDResponse` |
| POST | `/api/heartbeat/heartbeat.md` | Update HEARTBEAT.md | `HeartbeatMDResponse` |

---

## Pydantic Model Registry

67 shared models in `routes/models.py`. Additional heartbeat models imported from `personal_agent.heartbeat_api`.

### Core Request Models

| Model | Fields |
|-------|--------|
| `ChatSendRequest` | `message`, `thread_id?`, `style?`, `verbosity?`, `emoji?`, `format?` |
| `IntentQueryRequest` | `query`, `thread_id?` |
| `FactExtractionRequest` | `text`, `thread_id?` |
| `AuthRegisterRequest` | `username`, `password` |
| `AuthLoginRequest` | `username`, `password` |
| `ResolveContradictionRequest` | `ledger_id`, `method`, `winner?`, `reason?` |
| `AgentRunRequest` | `task`, `thread_id?`, `max_steps?` |
| `CreateScheduledTaskRequest` | `thread_id`, `task_type`, `trigger_at`, `payload` |

### Core Response Models

| Model | Key Fields |
|-------|------------|
| `ChatSendResponse` | `response`, `thread_id`, `turn`, `memories_used`, `contradictions`, `reasoning_trace?` |
| `HealthResponse` | `status`, `version`, `uptime` |
| `DashboardOverviewResponse` | `total_memories`, `total_contradictions`, `trust_distribution`, `recent_activity` |
| `ProfileResponse` | `facts`, `name`, `thread_id` |
| `MemoryListItem` | `memory_id`, `text`, `trust`, `confidence`, `source`, `timestamp` |
| `ContradictionListItem` | `ledger_id`, `status`, `claim_a`, `claim_b`, `drift_score`, `created_at` |

---

## Error Conventions

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 400 | Bad request (validation error) |
| 401 | Not authenticated |
| 404 | Resource not found |
| 409 | Conflict (contradiction in resolution) |
| 422 | Validation error (FastAPI/Pydantic) |
| 500 | Internal server error |

---

*This contract is frozen at v0.9.0. Any change to paths, methods, or model shapes requires a version bump.*

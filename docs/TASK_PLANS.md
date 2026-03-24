# Task Plans (v2.9.3)

Multi-step work plans that persist across messages and threads. Plans break complex requests into concrete steps, track progress, and advance automatically as tools execute.

---

## Overview

The plan system adds a persistent layer above individual tool executions. Before plans, every message was isolated — the system had no concept of "we're on step 3 of 5, I need your input before step 4." Plans provide:

- **Structured decomposition** — complex requests broken into ordered steps
- **Persistence** — plans survive across messages, threads, and browser sessions
- **Auto-advancement** — steps complete automatically when tools finish
- **User-input gates** — steps can pause for user input before continuing
- **Thread linking** — one active plan per chat thread, with cursor tracking

## Plan Creation

Three ways plans get created:

1. **User describes work** — "today I want to refactor routing, add tests, and update docs" → Aether structures it into a 3-step plan
2. **Complex request** — Aether proposes a plan → user approves → plan becomes active
3. **Manual creation** — user adds plans directly on the Plans & Jobs page

### Auto-Plan Detection

The `PlanEngine.should_create_plan()` method uses heuristics to decide when a message warrants a plan:

- **Keyword detection** — "plan", "steps", "todo", "today I want to", "first... then...", "workflow", "checklist"
- **Multi-action patterns** — 3+ comma/and-separated clauses
- **Sentence count** — 3+ sentences in messages over 100 characters

The auto-plan threshold is user-configurable in Settings > Behavior:
- `always_ask` (default) — always ask before creating a plan
- `auto_simple` — auto-create for 3+ step tasks, ask for complex ones
- `auto_all` — auto-create for any multi-step task

## Data Model

### Plans Table

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT PK | UUID |
| title | TEXT | Plan title |
| description | TEXT | Optional longer description |
| status | TEXT | `active`, `paused`, `completed`, `archived` |
| created_by | TEXT | `user`, `aether`, `manual` |
| created_at | REAL | Unix timestamp |
| updated_at | REAL | Unix timestamp (bumped on any change) |
| completed_at | REAL | Set when all steps complete |
| metadata_json | TEXT | Flexible JSON metadata |

### Plan Steps Table

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT PK | UUID |
| plan_id | TEXT FK | Parent plan |
| step_number | INTEGER | Ordering (1-based) |
| title | TEXT | Action phrase |
| description | TEXT | Optional detail |
| status | TEXT | `pending`, `in_progress`, `waiting_input`, `completed`, `skipped`, `failed` |
| tool_name | TEXT | Optional: specific tool this step uses |
| input_json | TEXT | Pre-filled tool input |
| output_json | TEXT | Result after execution |
| needs_user_input | TEXT | Description of what's needed |
| user_input | TEXT | User's response |

### Thread-Plan Links

| Column | Type | Description |
|--------|------|-------------|
| thread_id | TEXT PK | One active plan per thread |
| plan_id | TEXT FK | Linked plan |
| current_step_id | TEXT | Active step cursor |
| linked_at | REAL | When the link was created |

## API Endpoints

All endpoints are under `/api/plans`.

### Plans

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/plans` | List all plans (optional `?status=active`) |
| POST | `/api/plans` | Create a plan with optional steps array |
| GET | `/api/plans/{plan_id}` | Get plan with all steps |
| PUT | `/api/plans/{plan_id}` | Update title, description, or status |
| DELETE | `/api/plans/{plan_id}` | Delete plan + steps + links |

### Steps

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/plans/{plan_id}/steps` | Add a step |
| PUT | `/api/plans/{plan_id}/steps/{step_id}` | Update step fields |
| DELETE | `/api/plans/{plan_id}/steps/{step_id}` | Remove a step |
| POST | `/api/plans/{plan_id}/reorder` | Reorder steps (body: `{step_ids: [...]}`) |

### Thread Linking

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/plans/thread/{thread_id}` | Get plan linked to thread |
| POST | `/api/plans/{plan_id}/link/{thread_id}` | Link plan to thread |
| DELETE | `/api/plans/{plan_id}/link/{thread_id}` | Unlink plan from thread |

## Chat Pipeline Integration

### Step Advancement

After tool execution in `task_agent.py`, the system checks for an active plan on the current thread. If one exists:

1. The current `in_progress` step is marked `completed` with the tool output stored
2. `advance_plan()` finds the next `pending` step
3. If the next step has `needs_user_input`, it's set to `waiting_input`
4. A `plan_update` SSE event is emitted with progress info
5. If all steps are done, a `plan_complete` event fires

### SSE Event Types

| Event | When | Metadata |
|-------|------|----------|
| `plan_proposal` | Aether proposes a plan for approval | Plan object |
| `plan_update` | A step status changed | plan_id, next_step, progress string |
| `plan_complete` | All steps finished | plan_id |

## Frontend Components

### Plans & Jobs Page

The existing Jobs page is split into two sections:

- **Plans section** (top) — list of all plans with status badges, expandable step lists, progress bars. "New Plan" button opens a creation form with title, description, and dynamic step list (add/remove steps)
- **Jobs section** (bottom) — existing job queue UI, unchanged

### PlanWidget (In-Chat)

A compact collapsible bar shown above the message input when a plan is linked to the active thread:

- **Collapsed**: SVG progress ring (percentage), plan title, current step name
- **Expanded**: all steps with status icons (✓ ► ? ✗ — ○), descriptions, tool badges, plan metadata

The widget polls `GET /api/plans/thread/{thread_id}` on mount and refreshes after each message.

## Settings

Three plan-related settings in Settings > Behavior > Plans & Workflow:

| Setting | Key | Values | Default |
|---------|-----|--------|---------|
| Auto-plan creation | `plan_auto_threshold` | `always_ask`, `auto_simple`, `auto_all` | `always_ask` |
| Plan notifications | `plan_notifications` | `true`, `false` | `true` |
| Show plan widget in chat | `plan_chat_visibility` | `true`, `false` | `true` |

## Architecture Notes

- Plans coexist with the existing `pending_tasks` table (used by checkpoint/confirmation flow). They are a higher-level concept — plans contain multiple steps, each of which may trigger a pending task
- Plan operations work without an LLM — manual creation and management is pure CRUD
- The PlanEngine generates plans via a single LLM call that returns structured JSON
- Error handling: failed steps are marked `failed` but don't stop the plan. Users can retry, skip, or abort

## Files

| File | Purpose |
|------|---------|
| `personal_agent/db_utils.py` | Plan/step/link tables + CRUD methods |
| `personal_agent/plan_engine.py` | PlanEngine class |
| `routes/plans.py` | REST API |
| `routes/models.py` | Pydantic models |
| `personal_agent/task_agent.py` | Plan advancement after tool execution |
| `frontend/src/components/PlanWidget.tsx` | In-chat plan widget |
| `frontend/src/pages/JobsPage.tsx` | Plans & Jobs page |
| `frontend/src/pages/SettingsPage.tsx` | Plan settings |
| `frontend/src/lib/api.ts` | Plan API client functions |

# Session Prompt: Task Plan System (v2.9.2)

## Context

This is a personal AI agent called Aether. Recent work completed:
- **v2.9** — Hybrid LLM intent router (regex → local LLM → cloud LLM) with self-improving route learning
- **v2.9.1** — Response synthesis layer (LLM thinks about tool results before responding)

The system can now correctly route messages to tools AND respond with depth. What's missing: **the system has no concept of multi-step work that persists across messages.** Every message is isolated. There's no way to say "here's a plan with 5 steps, we're on step 3, I need your input before step 4."

## What to Build: Task Plan System

A two-layer planning system:
1. **Persistent plans** — stored in a dedicated DB table, survive across threads and sessions
2. **Thread cursor** — links an active plan to the current chat thread, tracks which step we're on

Three ways plans get created:
1. **User describes work** → Aether structures it into a plan ("today I want to refactor routing, add tests, and update docs")
2. **Complex request** → Aether proposes a plan → user approves ("This will take a few steps, here's my plan")
3. **Manual creation** — user adds items directly on the Plans UI page

### UI Locations
- **Jobs page** — split into two sections: **Plans** (top) and **Jobs** (bottom, existing cron system)
- **Active chat thread** — shows the active plan inline when one is linked to the thread
- **New threads** — clean, no plan shown

---

## Storage Architecture

### Plans Table (new, in the main thread session DB)

```sql
CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,                    -- uuid
    title TEXT NOT NULL,                    -- "Refactor routing layer"
    description TEXT,                       -- optional longer description
    status TEXT NOT NULL DEFAULT 'active',  -- active, paused, completed, archived
    created_by TEXT NOT NULL DEFAULT 'user', -- 'user', 'aether', 'manual'
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    completed_at REAL,
    metadata_json TEXT                      -- flexible metadata (tags, priority, etc.)
);
```

### Plan Steps Table (new)

```sql
CREATE TABLE IF NOT EXISTS plan_steps (
    id TEXT PRIMARY KEY,                    -- uuid
    plan_id TEXT NOT NULL,                  -- FK to plans.id
    step_number INTEGER NOT NULL,           -- ordering (1-based)
    title TEXT NOT NULL,                    -- "Create tool registry"
    description TEXT,                       -- optional detail
    status TEXT NOT NULL DEFAULT 'pending', -- pending, in_progress, waiting_input, completed, skipped, failed
    tool_name TEXT,                         -- optional: specific tool this step uses
    input_json TEXT,                        -- optional: pre-filled tool input
    output_json TEXT,                       -- result after execution
    needs_user_input TEXT,                  -- null or description of what's needed ("What language?")
    user_input TEXT,                        -- the user's response when input was needed
    started_at REAL,
    completed_at REAL,
    FOREIGN KEY(plan_id) REFERENCES plans(id)
);
CREATE INDEX IF NOT EXISTS idx_plan_steps_plan ON plan_steps(plan_id, step_number);
```

### Thread-Plan Link (new)

```sql
CREATE TABLE IF NOT EXISTS thread_plan_links (
    thread_id TEXT PRIMARY KEY,             -- one active plan per thread
    plan_id TEXT NOT NULL,                  -- FK to plans.id
    current_step_id TEXT,                   -- which step is active right now
    linked_at REAL NOT NULL,
    FOREIGN KEY(plan_id) REFERENCES plans(id)
);
```

Add these tables to `ThreadSessionDB.__init__()` in `personal_agent/db_utils.py` alongside the existing `pending_tasks` table.

---

## Backend Implementation

### Phase 1: Database Layer

In `personal_agent/db_utils.py`, add methods to `ThreadSessionDB`:

```python
# Plan CRUD
def create_plan(self, title, description=None, created_by='user', steps=None) -> dict
def get_plan(self, plan_id) -> Optional[dict]
def list_plans(self, status=None, limit=50) -> List[dict]
def update_plan(self, plan_id, **kwargs) -> None
def delete_plan(self, plan_id) -> None

# Step CRUD
def add_plan_step(self, plan_id, title, description=None, tool_name=None, step_number=None) -> dict
def get_plan_steps(self, plan_id) -> List[dict]
def update_step(self, step_id, **kwargs) -> None
def advance_plan(self, plan_id) -> Optional[dict]  # move to next pending step

# Thread linking
def link_plan_to_thread(self, thread_id, plan_id) -> None
def get_thread_plan(self, thread_id) -> Optional[dict]  # returns plan + steps + cursor
def unlink_plan_from_thread(self, thread_id) -> None
```

### Phase 2: API Routes

Create `routes/plans.py`:

```python
router = APIRouter(prefix="/api/plans", tags=["plans"])

# GET  /api/plans              — list all plans (filterable by status)
# POST /api/plans              — create a plan (with optional steps array)
# GET  /api/plans/{plan_id}    — get plan with all steps
# PUT  /api/plans/{plan_id}    — update plan (title, description, status)
# DELETE /api/plans/{plan_id}  — delete plan

# POST /api/plans/{plan_id}/steps          — add a step
# PUT  /api/plans/{plan_id}/steps/{step_id} — update a step (status, output, user_input)
# DELETE /api/plans/{plan_id}/steps/{step_id} — remove a step
# POST /api/plans/{plan_id}/reorder        — reorder steps (accepts ordered list of step_ids)

# POST /api/plans/{plan_id}/link/{thread_id}   — link plan to thread
# DELETE /api/plans/{plan_id}/link/{thread_id}  — unlink plan from thread

# GET  /api/plans/thread/{thread_id}       — get the plan linked to this thread (if any)
```

Register this router in `routes/register.py`.

Add Pydantic models in `routes/models.py`:
- `CreatePlanRequest` (title, description, steps[])
- `PlanResponse` (id, title, description, status, steps[], created_by, timestamps)
- `CreateStepRequest` (title, description, tool_name)
- `StepResponse` (id, title, status, tool_name, output, needs_user_input, etc.)

### Phase 3: Plan Intelligence (Aether creating/managing plans)

Create `personal_agent/plan_engine.py`:

```python
class PlanEngine:
    """Generates, manages, and executes plans from natural language."""

    def __init__(self, llm_client, session_db):
        self.llm_client = llm_client
        self.db = session_db

    def generate_plan(self, user_message, conversation_history=None) -> dict:
        """Ask the LLM to break a request into a structured plan with steps."""
        # System prompt: "Break this request into concrete steps.
        #   For each step, provide: title, description, tool_name (if applicable),
        #   and whether it needs user input.
        #   Return as JSON: {title, description, steps: [{title, description, tool_name, needs_user_input}]}"
        # Call LLM
        # Parse response into plan + steps
        # Save to DB
        # Return the plan

    def should_create_plan(self, message, intent) -> bool:
        """Decide if a message warrants a plan vs direct execution."""
        # Heuristics:
        # - Message mentions multiple distinct actions ("X, Y, and Z")
        # - Message describes a project or workflow
        # - Message uses words like "plan", "steps", "todo", "today I want to"
        # - Intent is complex/multi-tool
        # Simple keyword check first, LLM fallback if ambiguous

    def advance_step(self, plan_id, step_result=None) -> Optional[dict]:
        """Mark current step complete, return next step (or None if done)."""
        # Update current step status + output
        # Find next pending step
        # If next step needs_user_input, set status to 'waiting_input'
        # If no more steps, mark plan as completed
        # Return next step or None

    def handle_user_input(self, plan_id, user_input) -> dict:
        """Process user input for a step that was waiting."""
        # Find the waiting_input step
        # Store user_input
        # Advance to execution
        # Return the step ready for execution
```

### Phase 4: Wire into Chat Pipeline

In the chat route (`routes/chat.py`) and task agent, add plan awareness:

1. **Before routing**: Check if the thread has an active plan with a `waiting_input` step. If yes, and the user's message looks like a response (not a totally new topic), route to `plan_engine.handle_user_input()` instead of normal classification.

2. **During routing**: If `plan_engine.should_create_plan()` returns True for the message, generate a plan and present it to the user for approval before executing. Yield a new event type `plan_proposal` that the frontend renders as an interactive plan card.

3. **After tool execution**: If a plan is active, call `plan_engine.advance_step()` to move the cursor. Include plan progress in the response ("Step 2 of 5 complete. Next: setting up the test suite.").

4. **New event types** for SSE streaming:
   - `plan_proposal` — Aether proposes a plan (rendered as a card with approve/edit/reject)
   - `plan_update` — a step status changed (frontend updates the plan display)
   - `plan_complete` — all steps done

### Phase 5: Frontend — Jobs Page Split

Modify `frontend/src/pages/JobsPage.tsx`:

**Top section: Plans**
- List of all plans with status badges (active, paused, completed)
- Click to expand → shows steps with checkmarks, status, descriptions
- "New Plan" button → modal with title, description, and dynamic step list (add/remove/reorder steps)
- Each step row: drag handle (reorder), title input, status badge, delete button
- Plan actions: pause, resume, archive, delete
- Active plan has a highlight/accent border

**Bottom section: Jobs (existing)**
- Keep the existing jobs UI exactly as-is, just visually separated with a divider and section header

### Phase 6: Frontend — In-Chat Plan Display

When a plan is linked to the active thread, show a compact plan widget in the chat area. Options for where to put it:

**Recommended: Collapsible panel above the message input**
- Shows: plan title, progress bar (3/5 steps), current step name
- Expandable: click to see all steps with statuses
- Minimal when collapsed — just a single line with progress
- Doesn't clutter the chat but is always accessible

Implementation:
- New component: `frontend/src/components/PlanWidget.tsx`
- Polls `GET /api/plans/thread/{thread_id}` on mount and after each message
- Renders inline in the chat layout (between messages and input, or as a pinned bar)

**SSE integration**: The plan_update events from the stream update the widget in real-time without polling.

### Phase 7: Settings

Add to the Settings page under a new "Plans" or "Workflow" section:

**Settings to add:**

1. **Auto-plan threshold** — dropdown or slider
   - `"always_ask"` — Always ask before creating a plan (default)
   - `"auto_simple"` — Auto-create plans for 3+ step tasks, ask for complex ones
   - `"auto_all"` — Auto-create plans for any multi-step task without asking

2. **Plan notifications** — toggle (default: on)
   - When on, show step completion and plan progress in chat responses
   - When off, plans run silently in the background

3. **Default plan visibility in chat** — toggle (default: on)
   - Whether the plan widget shows in the chat thread when a plan is active

Add these to `routes/auth.py` settings whitelist:
- `plan_auto_threshold` (string: "always_ask" | "auto_simple" | "auto_all")
- `plan_notifications` (boolean)
- `plan_chat_visibility` (boolean)

Frontend: Add these controls to SettingsPage.tsx under a "Plans & Workflow" tab or section within the existing Advanced tab.

---

## Files Summary

### New Files
1. `personal_agent/plan_engine.py` — PlanEngine class (generation, advancement, input handling)
2. `routes/plans.py` — REST API for plans CRUD
3. `frontend/src/components/PlanWidget.tsx` — compact in-chat plan display

### Modified Files
1. `personal_agent/db_utils.py` — Add plans/steps/links tables + CRUD methods to ThreadSessionDB
2. `routes/register.py` — Register plans router
3. `routes/models.py` — Add plan/step Pydantic models
4. `routes/auth.py` — Add plan settings to whitelist
5. `routes/chat.py` — Add plan awareness (check for active plan, handle plan-linked messages)
6. `personal_agent/task_agent.py` — After tool execution, advance plan step if one is active
7. `frontend/src/pages/JobsPage.tsx` — Split into Plans (top) + Jobs (bottom) sections
8. `frontend/src/pages/SettingsPage.tsx` — Add plan settings controls
9. `frontend/src/lib/api.ts` — Add plan API client functions

---

## Testing Scenarios

1. **Manual plan creation**: Go to Jobs page → click "New Plan" → add title + steps → save → verify it appears in the list
2. **Aether-generated plan**: Say "today I want to refactor the router, add tests, and update the docs" → Aether should propose a 3-step plan → approve → plan appears in chat widget
3. **Plan execution**: With an active plan, say "let's start" → system executes step 1 → widget updates → response includes "Step 1 complete, next: ..."
4. **User input step**: Plan has a step that needs input ("What language?") → system asks → user responds → system continues
5. **Thread linking**: Start a plan in thread A → open new thread B → no plan shown → say "continue the routing plan" → plan links to thread B
6. **Plan persistence**: Create a plan → close browser → reopen → plan is still there on Jobs page
7. **Settings**: Toggle auto-plan to "auto_simple" → send a multi-step request → plan auto-creates without asking

## Important Notes

- The existing `pending_tasks` table in `ThreadSessionDB` is a simpler predecessor. Don't remove it — it's still used by the checkpoint/confirmation flow. Plans are a higher-level concept that can coexist.
- Plans should be lightweight to create. Don't overthink the LLM plan generation — a simple prompt that returns JSON is fine. Fancy chain-of-thought planning is a future optimization.
- The plan widget in chat should be unobtrusive. If it feels heavy, users will hate it. Keep it to one line when collapsed.
- Error handling: if a plan step fails, mark it as `failed` but don't stop the whole plan. Let the user decide to retry, skip, or abort.
- All plan operations should work without an LLM running — manual creation and management is pure CRUD, no LLM needed.

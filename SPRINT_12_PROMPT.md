# Sprint 12 — Task Triage & Orchestration Layer

## The Problem

The current system has no "pause to think" between receiving a message and executing. It hard-switches: either a regex/embedding matches a tool intent and runs that tool immediately, OR it dumps to conversational LLM generation. There is no middle ground.

This causes three failures:
1. **Routing failures** — "open notepad and write hello world" falls through to conversational because the classify_intent call silently errors (exception caught at `routes/chat.py:4678`, sets `_task_intent = None`, falls to conversational). The user sees "I can't directly open applications" instead of desktop control executing.
2. **No task decomposition** — complex requests like "open VS Code, create a new file, and write a function that calculates fibonacci" need multiple tools in sequence (desktop_action → file_write → content_generation). Currently there's no planner that breaks this down.
3. **No task acknowledgment** — when the system enters task mode, it should immediately generate a REAL response from the model telling the user what it's doing ("I'm going to open Notepad and type a joke for you — give me a moment"). Then the UI message box should pulse/flash until the task completes. Currently there's zero feedback between "user sends message" and "task finishes or fails silently."

## Current Architecture (read these files first)

```
routes/chat.py (5280 lines)
  └─ POST /api/chat/stream → generate_stream()
       ├─ Line 4676: _task_intent = _classify_intent(req.message)
       ├─ Line 4678-4682: except Exception → _task_intent = None (SILENT FAILURE)
       ├─ Line 4685: if _task_intent.route == "task" → CRTTaskAgent.run_stream()
       └─ else → conversational pipeline (memory retrieval, system prompt, LLM streaming)

personal_agent/task_agent.py (4862 lines)
  ├─ _classify_intent_regex() — line 695: 15+ regex patterns including _DESKTOP_ACTION_RE
  ├─ classify_intent_hybrid() — line 1133: regex first, then embedding if regex < 0.90
  ├─ _get_semantic_router() — line 1112: lazy-loads SemanticIntentRouter, catches all exceptions
  ├─ CRTTaskAgent.run_stream() — line 1451: gate → plan → execute → generate answer
  ├─ _build_plan() — line 2922: maps intent to tool steps
  ├─ _execute_step() — line 3252: dispatches to tool functions
  ├─ _run_desktop_action() — line 3687: creates DesktopAgent, runs ReAct loop
  └─ _stream_generate_answer() — line 4752: builds final answer from tool outputs

personal_agent/semantic_intent_router.py (602 lines)
  ├─ INTENT_PROTOTYPES dict — 18 intent types, 140+ seed phrases
  ├─ classify() — cosine similarity against centroids + individual phrases
  ├─ detect_multi_intent() — finds compound messages
  └─ handle_ambiguity() — routes to clarify/execute/conversational

personal_agent/desktop_control.py — pyautogui + mss automation primitives
personal_agent/desktop_vision.py — VisionProvider ABC, ClaudeVisionProvider, CookieVisionProvider
personal_agent/desktop_agent.py — ReAct loop: screenshot→think→act→verify, max 25 steps
personal_agent/anthropic_client.py (461 lines) — AnthropicClient with chat_with_image()
personal_agent/cloud_features.py (823 lines) — CloudFeatureService, cookie provider, daily limits
personal_agent/action_receipts.py — ActionReceipt dataclass, SQLite logging
personal_agent/system_info.py — active window, processes, GPU state
personal_agent/heartbeat_executor.py — timer-based, gaming/idle detection, resource management
crt_api.py — FastAPI app, registers 18 routers
routes/register.py — router mount order
frontend/src/pages/SettingsPage.tsx — Settings UI with Desktop tab
frontend/src/components/chat/ActionCard.tsx — checkpoint UI with screenshot preview
```

## What To Build

### Phase 1: Fix the Silent Routing Failure

The immediate bug: `_classify_intent()` throws an exception inside `generate_stream()` (chat.py:4676), gets caught at line 4678, and silently sets `_task_intent = None`. The user's desktop_action request falls through to conversational.

**Debug first:**
1. Add a visible log at the exception handler (chat.py:4678): `logger.error("[STREAM] INTENT CLASSIFIER ERROR: %s", _cie, exc_info=True)` — change from `warning` to `error` so it's impossible to miss.
2. Test by sending "open notepad" with the backend running. Check the terminal output.
3. The likely cause: `_get_semantic_router()` fails because the embedding model isn't loaded (VRAM conflict with ollama, or `sentence-transformers` import error in the backend process). The exception propagates up through `classify_intent_hybrid()`.

**Fix:**
- Make `classify_intent_hybrid()` truly fault-tolerant: if the semantic router fails, return the regex result instead of propagating the exception.
- The regex result for "open notepad" should be `desktop_action` at confidence 0.88. The bug is that the exception kills the entire classification, not just the embedding path.
- Add try/except specifically around the embedding path (lines 1146-1197), not just at the top level.

### Phase 2: Task Triage Layer

Add a triage step between message receipt and tool execution. This is the missing "pause to think."

**New function: `triage_message()`**

```python
class TriageResult:
    category: str          # "task", "question", "conversation", "clarification"
    requires_planning: bool # does this need multi-step decomposition?
    intent: TaskIntent      # the classified intent (may be multi_intent)
    acknowledgment: str     # what to tell the user immediately
    estimated_steps: int    # rough estimate for UI progress indication
    tools_needed: list[str] # which tools this will require
```

The triage flow:
```
message arrives
  → classify_intent_hybrid() (existing, but now fault-tolerant)
  → if single tool intent with high confidence:
      category = "task"
      requires_planning = False (single tool, execute directly)
      acknowledgment = generate_acknowledgment(intent, message)
  → if multi_intent or complex request:
      category = "task"
      requires_planning = True
      → call cloud LLM to decompose into subtasks
      acknowledgment = generate_acknowledgment(intent, message)
  → if conversational:
      category = "conversation"
      requires_planning = False
      → proceed to existing conversational pipeline
  → if ambiguous:
      category = "clarification"
      → emit clarify checkpoint (existing behavior)
```

**Key design point:** The acknowledgment is NOT a placeholder. It must be a real LLM-generated message that reflects understanding of the task. Examples:
- "open notepad and type a joke" → "I'll open Notepad and write something funny for you — this'll take about 30 seconds."
- "search for weather in Denver" → "Let me pull up Chrome and search for Denver weather. Hang tight."
- "organize my downloads folder" → "I'm going to take a look at your Downloads and tidy things up. I'll sort by file type and clean up duplicates."

Generate this via a fast cloud call (cookie provider, short prompt: "Generate a brief, natural 1-sentence acknowledgment for this task: {task}. Be conversational, not robotic. Mention what you'll actually do.").

OR — if cloud latency is too high for an acknowledgment — use a template system:
```python
TASK_TEMPLATES = {
    "desktop_action": [
        "On it — I'll {action_verb} for you. Give me a moment.",
        "Let me handle that. I'm going to {action_verb} now.",
    ],
    "file_write": [
        "I'll create that file for you. Let me draft it up.",
    ],
    # etc.
}
```

### Phase 3: Task Acknowledgment + UI Pulse

**Backend:**
When triage determines this is a task, emit a NEW SSE event before execution begins:

```python
yield f"data: {json.dumps({'type': 'task_acknowledged', 'data': {'message': acknowledgment, 'estimated_steps': estimated_steps, 'tools': tools_needed}})}\n\n"
```

Then proceed with execution as normal (plan → execute → answer).

**Frontend:**
In the chat stream handler, when `task_acknowledged` arrives:
1. Render the acknowledgment as a real assistant message bubble (not a status pill)
2. Start a pulse/glow animation on the message input area (or the last message bubble) to indicate "working"
3. The pulse stops when `task_done` or the final `done` event arrives

CSS for the pulse:
```css
@keyframes task-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(212, 132, 92, 0.3); }
  50% { box-shadow: 0 0 12px 4px rgba(212, 132, 92, 0.15); }
}
.task-working {
  animation: task-pulse 2s ease-in-out infinite;
}
```

Use the theme accent color (`--accent: #D4845C`) not blue.

### Phase 4: Multi-Step Task Orchestration (Sprint 8 lite)

For compound requests that need multiple tools in sequence:

```python
async def decompose_task(message: str, intent: TaskIntent) -> list[TaskStep]:
    """Break a complex request into ordered subtasks."""
    # For now, handle the common patterns deterministically:

    # Pattern: "open X and do Y in it"
    if intent.intent_type == "desktop_action":
        # The ReAct loop already handles multi-step desktop tasks internally
        # Just pass the full message as the task — the vision model will figure it out
        return [TaskStep(tool="desktop_action", input={"task": message})]

    # Pattern: "create a file with X content"
    if intent.intent_type == "file_write" and needs_content_generation(message):
        return [
            TaskStep(tool="content_generation", input={"description": message}),
            TaskStep(tool="file_write", input={"content": "$prev_output"}),
        ]

    # For truly complex multi-tool requests, call cloud LLM to decompose:
    # "research X, then write a summary, then email it to Y"
    # → [web_search, content_generation, file_write, ??? (no email tool yet)]
```

This is a lightweight version — NOT the full sub-agent delegation system (that's Sprint 8 proper). Just handle the common 2-3 step patterns deterministically.

### Phase 5: Settings Page Fixes

**Problem 1: Toggle/button colors are blue instead of theme accent**

The Toggle component (SettingsPage.tsx:32) uses `bg-blue-500/80` for the active state. Change to theme accent:

```tsx
// BEFORE
className={`... ${checked ? 'bg-blue-500/80' : 'bg-white/10'}`}

// AFTER
style={checked ? { backgroundColor: 'var(--accent)' } : undefined}
className={`... ${checked ? '' : 'bg-white/10'}`}
```

The tab buttons already use `var(--accent)` (line 248) — those should be fine. But verify they're rendering correctly.

**Problem 2: Desktop settings buttons not persisting**

The backend must be running for settings to save. The `handleCloudToggle`, `handleCloudSelect`, `handleCloudNumberInput` handlers all call `updateCloudSettings()` which hits `PATCH /api/auth/settings`. If the backend is down, the optimistic UI update shows the toggle flipping, but it reverts on error (line 169).

Also: the idle task text input (line 662) uses `handleCloudSelect` which fires on every keystroke — this sends a PATCH request per character typed. Change to a debounced input or onBlur handler:

```tsx
// Use onBlur instead of onChange for text inputs
onBlur={(e) => handleCloudSelect('desktop_idle_task', e.target.value)}
onChange={(e) => setCloudSettingsState({...cloudSettings, desktop_idle_task: e.target.value})}
```

**Problem 3: `<button>` nested inside `<button>` warning**

Console shows: "validateDOMNesting(...): <button> cannot appear as a descendant of <button>." This is in the Sidebar — likely a clickable element inside another clickable element. Find and fix in `Sidebar.tsx`.

### Phase 6: Update ROADMAP.md and CHANGELOG.md

Add entries for whatever gets built. Follow the existing format exactly. Key things to document:
- The triage layer
- Task acknowledgment SSE event
- UI pulse animation
- Silent routing failure fix
- Settings page theme color fix
- Any orchestration work

## Implementation Order

1. **Fix silent failure** — add error logging at chat.py:4678, make classify_intent_hybrid fault-tolerant
2. **Verify routing** — restart backend, send "open notepad", confirm it routes to desktop_action
3. **Add triage_message()** — new function in task_agent.py
4. **Task acknowledgment** — SSE event + frontend rendering + pulse animation
5. **Settings fixes** — theme colors, debounced text input, nested button warning
6. **Test everything** — send 10+ messages covering: desktop actions, file ops, conversational, ambiguous, typo'd intents
7. **Update ROADMAP + CHANGELOG**

## Do NOT:
- Rewrite the intent classification system — it works, just needs fault tolerance
- Build full sub-agent delegation — that's Sprint 8
- Touch the ReAct loop in desktop_agent.py — it works
- Add new intent types — the existing 18 are sufficient
- Change the embedding model or prototype phrases
- Modify the cookie vision provider — it works
- Skip testing the routing fix before building the triage layer

## Key Design Requirement (from user):
"When the system enters task mode, it should generate a response to tell the user what it's doing. It can't be a placeholder. It must be full intent from the model. Like 'hey I'm going to take some time and work on this.' Then the UI message box will flash till the task is done."

This is the most important UX change. The user should never wonder "is it doing something or did it fail silently?"

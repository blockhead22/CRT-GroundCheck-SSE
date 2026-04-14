# Project: Agentic Pipeline — Full Architecture Design
*Created: 2026-04-01. This is the canonical design doc for the Cookie orchestrator pipeline.*

---

## The Problem

The Cookie orchestrator loop as currently built:
- Fires immediately with no user-visible plan
- Accepts any `route == task` message (too broad — generic convos get routed in)
- Has no pause/ask mechanism — `ask_user` action fires and is ignored
- Has no follow-up system — after `respond`, the loop is dead
- Has no proactive push — subagents can't send results back to the user

---

## Target Pipeline

```
message
  → intent classify
  → [route == conv]              → legacy path ✓
  → [route == task, needs_tools] → Cookie:

       ① PLAN        Cookie declares intent upfront
                     shown to user as first tokens
                     "I'll read X, then check Y..."
                     user sees this before any tool fires

       ② ASK?        if ambiguous / destructive:
                     Cookie pauses — yields ask_user event
                     loop suspends, waits for reply
                     user answers → loop resumes with answer
                     if no answer in N seconds → timeout/cancel

       ③ EXECUTE     tools fire sequentially
                     each tool shown in pipeline panel (ToolRow)
                     thinking stubs shown between tool calls
                     user can see exactly what is happening

       ④ RESPOND     Cookie gives final answer
                     plan + tools + response = full turn

       ⑤ FOLLOWUP?   Cookie can suggest next steps
                     "Want me to also check X?"
                     user can reply → new loop starts
                     OR: proactive push via WS registry
```

---

## Layer 1: Routing Gate

**Problem**: `_layer4_orchestrator` fires for too many things. `needs_tools` is not a real signal.

**Design**:
```python
# Only enter Cookie when:
# 1. route == 'task' (not conversational)
# 2. intent_type is in the tool-requiring set
# 3. confidence is high enough to act

_TOOL_REQUIRING_INTENTS = {
    'file_op', 'code_task', 'code_read', 'code_write',
    'web_search', 'web_fetch', 'research',
    'shell_exec', 'run_python',
    'memory_write', 'memory_search',  # writes only
    'multi_step', 'plan_create',
}

_SKIP_COOKIE_INTENTS = {
    'broad_recall', 'inquiry', 'question', 'conversational',
    'memory_query',  # reads go to legacy
    'self_reflection', 'greeting',
}

_needs_cookie = (
    _task_intent is not None
    and _task_intent.route == 'task'
    and _task_intent.intent_type in _TOOL_REQUIRING_INTENTS
    and _task_intent.confidence >= 0.75
    and len(req.message.split()) >= 4  # not a one-liner
)
```

**Files to change**: `routes/chat.py` — replace `_layer4_orchestrator` gate logic

---

## Layer 2: Cookie Plan Action

**Status**: BUILT, loop disabled.

**Design**:
- First response from Cookie MUST be `{"action": "plan", "message": "...", "steps": [...]}`
- Yielded immediately as visible `token` in the stream
- User sees "I'll read chat.py, look for the pipeline gate, then explain what I find" before any tool fires
- `_orch_answer` seeded with plan text so settled message is consistent

**Files**: `personal_agent/cookie_orchestrator.py` ORCHESTRATOR_SYSTEM Rule 2, `run()` plan handler
**`routes/chat.py`**: `plan` event → yield token

---

## Layer 3: ask_user Pause / Resume

**Problem**: `ask_user` action is yielded but the loop continues immediately. No actual pause.

**Design**:

### Suspend side (backend)
```python
elif _etype == "ask_user":
    _question = _orch_event.get("content", "")
    # 1. Yield the question as a visible response
    yield _sse({"type": "token", "content": _question})
    # 2. Store loop state in session DB under thread_id
    #    State = {"generator": <paused>, "iteration": N, "question": ...}
    # 3. Yield done event with metadata: {"ask_user": True, "loop_suspended": True}
    _session_db.set_suspended_loop(req.thread_id, _orch_state)
    yield _sse({"type": "done", ..., "metadata": {"loop_suspended": True}})
    return  # end this request
```

### Resume side (backend)
```python
# At top of generate_stream(), before intent classify:
_suspended = _session_db.get_suspended_loop(req.thread_id)
if _suspended:
    # User's current message is the reply to Cookie's question
    # Inject into the paused generator and continue
    _session_db.clear_suspended_loop(req.thread_id)
    # ... resume loop with user reply as tool result
```

### Frontend
- `metadata.loop_suspended == true` → show reply input differently (not a new message, a reply)
- OR: use existing `pendingCheckpoint` system — already handles this pattern
- After user replies → sends message → backend detects suspended loop → resumes

**Note**: Generator objects can't be serialized. Suspension needs to serialize the loop STATE (iteration count, tool results so far, objective) not the generator itself. Resume reconstructs from state.

**Files**: `routes/chat.py`, `personal_agent/session_state.py` (add suspended loop storage)

---

## Layer 4: Follow-up Suggest

**Problem**: After `respond`, Cookie dies. No "want me to also...?"

**Design**:

### Orchestrator side
```python
# In respond action handler:
if action == "respond":
    _response_text = decision.get("message", "")
    _followup = decision.get("followup", "")  # optional field
    yield {"type": "response", "content": _response_text}
    if _followup:
        yield {"type": "followup_suggest", "content": _followup}
```

### System prompt addition
```
- When responding, if there is an obvious next step the user might want,
  add "followup": "Want me to also X?" to your respond action.
  Keep it to one concrete suggestion. Don't add it for simple questions.
```

### Frontend
- `followup_suggest` event → shows action card below response
- "Yes" → sends followup text as new message → new Cookie loop
- "No" / dismiss → card disappears

**Files**: `cookie_orchestrator.py` ORCHESTRATOR_SYSTEM, `routes/chat.py` followup handler, `App.tsx` followup card

---

## Layer 5: Proactive Turns (WS Registry)

**Problem**: Subagents run async. They have no way to push results back to the user after the request ends.

**Design**:

### ConnectionRegistry
```python
# personal_agent/ws_registry.py (new file)
class ConnectionRegistry:
    _registry: Dict[str, WebSocket] = {}
    _outbox: Dict[str, Queue] = {}

    def register(self, thread_id: str, ws: WebSocket):
        self._registry[thread_id] = ws
        # drain any queued messages
        if thread_id in self._outbox:
            while not self._outbox[thread_id].empty():
                ws.send_json(self._outbox[thread_id].get())

    def push(self, thread_id: str, message: dict):
        ws = self._registry.get(thread_id)
        if ws:
            ws.send_json(message)
        else:
            # client disconnected, queue for reconnect
            self._outbox.setdefault(thread_id, Queue()).put(message)

    def unregister(self, thread_id: str):
        self._registry.pop(thread_id, None)
```

### EventBus new types
```python
# proactive_turn    — new top-level assistant message (not within-turn status)
# subagent_complete — subagent finished, has a result to push
# scheduled_followup — background process wants to send something
```

### WS handler upgrade
```python
# ws.py — persistent listen loop
async for event in event_bus.subscribe(thread_id):
    if event["type"] == "proactive_turn":
        await ws.send_json({
            "type": "proactive_message",
            "role": "assistant",
            "content": event["content"],
            "trigger": event.get("trigger"),
        })
```

### Frontend
```typescript
// ws.ts — new handler
case 'proactive_message':
  // append new assistant message to chat without user prompt
  // show "autonomous" badge so Nick knows it wasn't triggered by him
  onProactiveMessage?.(event.content, event.trigger)
```

**Files**: `personal_agent/ws_registry.py` (new), `routes/ws.py`, `frontend/src/lib/ws.ts`, `frontend/src/App.tsx`

---

## Implementation Order

```
Phase 1 (unblock)
  [ ] Routing gate — stop generic convos hitting Cookie
  [ ] Test with loop re-enabled on real task messages

Phase 2 (core behavior)
  [ ] ask_user pause — serialize loop state, yield done
  [ ] ask_user resume — detect suspended loop, reconstruct + continue
  [ ] Frontend: suspended loop reply UI (use pendingCheckpoint)

Phase 3 (polish)
  [ ] followup suggest — Cookie emits, frontend shows action card
  [ ] plan action test — already built, needs loop re-enabled

Phase 4 (proactive)
  [ ] ConnectionRegistry + OutboxQueue
  [ ] EventBus proactive_turn type
  [ ] WS handler persistent loop
  [ ] Frontend proactive message path
  [ ] Wire Cookie subagent completion to registry.push()
```

---

## Current Code State

| File | Change | Status |
|------|--------|--------|
| `routes/chat.py` | Loop disabled (`and False`) | Done |
| `routes/chat.py` | `_pipeline_event_queue` + drain | Done |
| `routes/chat.py` | `plan` event → token yield | Done |
| `routes/chat.py` | Ack text before loop entry | Done |
| `personal_agent/cookie_orchestrator.py` | `plan` action in system prompt | Done |
| `personal_agent/cookie_orchestrator.py` | `plan` handler in `run()` | Done |
| `personal_agent/crt_critic.py` | False contradiction fixes | Done |
| `frontend/src/components/chat/PipelineCollapse.tsx` | Full rewrite v2 | Done |
| `frontend/src/components/chat/ToolRow.tsx` | NEW — Lucide icons | Done |
| `frontend/src/components/chat/ChatThreadView.tsx` | Duplicate fix | Done |
| `frontend/src/components/chat/PipelineTrace.tsx` | Green bar fix | Done |
| `personal_agent/prompt_prefix.py` | Anti-sycophancy rules | Done |

---

## Adaptive Depth + Mid-Updates + Subagents

These three are the same mechanism at different scales.

### Adaptive Depth
`max_iterations=10` is hardcoded. The `plan` action (already added) is the hook:
```json
{"action": "plan", "message": "...", "steps": [...], "estimated_depth": 6}
```
Cookie declares upfront how deep it needs to go. Orchestrator allocates accordingly.
**Status**: plan action exists, `estimated_depth` field just needs to be read in `run()`.

### Mid-Tooling Updates
`reasoning` field is computed on every tool action and logged to RunLog but never
surfaced to the user. Showing it = mid-updates. Already computed, just needs display.
The `tool_call` events already carry `alignment` now. Add `reasoning` to the yield too.

### Subagents — The Key Insight
A subagent = a Cookie loop running with a narrower objective in a separate context,
streaming results back to a parent loop.

```
Parent loop iteration 3:
  reasoning: "This is too deep for one loop"
  action: {"action": "spawn_agent",
           "objective": "Map all event handlers in routes/chat.py",
           "max_depth": 4}
  → Child loop starts (separate thread)
  → Child streams mid-updates back to parent
  → Child completes, returns summary
  → Parent resumes with summary as tool result
```

spawn_agent is structurally identical to ask_user pause:
```
ask_user:     suspend → wait for human reply     → resume
spawn_agent:  suspend → wait for child loop done → resume
```

Same primitive. ask_user pause MUST be built first — spawn_agent falls out of it.

### Build Order
```
1. Routing gate           — stop noise, unblocks everything
2. ask_user pause/resume  — establishes the suspend/resume primitive
3. Mid-updates            — surface reasoning field on tool actions (tiny)
4. Adaptive depth         — plan action reads estimated_depth field (tiny)
5. spawn_agent action     — reuses suspend/resume, child = new Cookie run
6. Proactive turns        — registry + outbox (child pushes to parent/user)
```

Steps 3+4 are nearly free. Step 5 falls out of step 2. Step 6 is the full WS arch.

---

## Open Questions

1. **ask_user serialization**: generator state can't be pickled. Options:
   - Serialize tool results + iteration count, replay from checkpoint
   - asyncio + celery task
   - Store full state dict in session DB, reconstruct on resume

2. **routing gate confidence threshold**: 0.75 is a guess. Tune from run log data.

3. **proactive turn UX**: subtle badge vs prominent indicator. Nick needs to know
   Aether initiated it autonomously.

4. **Cookie tool gaps vs old loop**: not fully audited. Some tools in old loop may
   not be registered in Cookie. Audit needed before old loop retirement.

5. **spawn_agent depth limit**: child loops need a hard cap to prevent infinite
   recursion. Max depth = 2 levels (parent → child, no grandchildren) initially.

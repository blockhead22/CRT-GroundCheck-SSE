# WebSocket Migration Plan

## What We're Building

A WebSocket server on the FastAPI backend that replaces both:
1. `POST /api/chat/stream` (SSE fetch-based streaming for chat)
2. `GET /api/notifications/stream` (SSE for proactive push)

One persistent bidirectional connection per client. Electron, mobile (Expo), and web all use the same protocol.

## Why

- **Mobile app needs it** — Expo over Cloudflare tunnel needs WS, not SSE+POST
- **Aether-initiated push** — proactive messages, contradiction alerts, task completions without polling
- **Real-time trust surface** — stream granular trust shifts, thinking stubs, tool progress as they happen
- **One connection replaces two** — no more separate notification SSE + chat fetch

## Architecture

```
Client (Electron / Expo / Web)
  ↕ WebSocket (wss:// or ws://)
FastAPI /ws endpoint
  ↕ ConnectionManager (tracks all connected clients)
  ↕ EventBus (pipeline emits events → WS broadcasts)
```

## Event Schema

Every WebSocket message is JSON with a `type` field:

### Client → Server
```json
{ "type": "chat",       "thread_id": "xxx", "message": "hello" }
{ "type": "ping" }
{ "type": "subscribe",  "channels": ["thread:xxx", "notifications"] }
```

### Server → Client (during chat pipeline)
```json
{ "type": "status",        "content": "searching memory" }
{ "type": "thinking",      "content": "Need to check GPT logs..." }
{ "type": "tool_start",    "tool": "gpt_log_search", "args": {...} }
{ "type": "tool_result",   "tool": "gpt_log_search", "result": {...}, "duration_ms": 14 }
{ "type": "retrieval",     "memories": [{ "id": "x", "text": "...", "trust": 0.70, "score": 0.45 }] }
{ "type": "trust_shift",   "memory_id": "x", "from": 0.70, "to": 0.74, "reason": "cited" }
{ "type": "token",         "content": "Your " }
{ "type": "done",          "content": "full response", "meta": { "steps": 4, "trust_shifts": 2 } }
```

### Server → Client (Aether-initiated, no prompt)
```json
{ "type": "notification",   "subtype": "contradiction", "content": "...", "data": {...} }
{ "type": "notification",   "subtype": "task_complete", "content": "...", "data": {...} }
{ "type": "notification",   "subtype": "reminder",      "content": "...", "data": {...} }
{ "type": "notification",   "subtype": "proactive",     "content": "...", "data": {...} }
{ "type": "pong" }
```

## Implementation Steps

### Step 1: WebSocket Server Endpoint (`routes/ws.py`)

New file. FastAPI WebSocket endpoint at `/ws`.

- `ConnectionManager` class — tracks active connections, supports broadcast and per-thread messaging
- Auth via query param token (`/ws?token=xxx`) since WS can't do headers easily
- Ping/pong keepalive (30s interval for Cloudflare compatibility)
- `on_connect`: register, subscribe to default channels
- `on_message`: dispatch `chat` messages into the existing pipeline
- `on_disconnect`: cleanup

### Step 2: EventBus (`personal_agent/event_bus.py`)

New file. A simple pub/sub that pipeline code emits to, and the WS manager listens to.

```python
class EventBus:
    async def emit(event_type: str, data: dict, thread_id: str = None)
    def subscribe(callback: Callable)
    def unsubscribe(callback: Callable)
```

The chat pipeline (`routes/chat.py`), orchestrator (`cookie_orchestrator.py`), and notification system all emit events to this bus instead of yielding SSE strings. The WS connection manager subscribes and forwards to the right clients.

### Step 3: Pipeline Event Emission

Modify the existing pipeline to emit events through the EventBus. The key emit points:

**In `routes/chat.py` stream pipeline:**
- Replace `yield _status(...)` → `event_bus.emit("status", ...)`
- Replace `yield _sse({"type": "token", ...})` → `event_bus.emit("token", ...)`
- Same for thinking, tool_start, tool_result, done, error

**In `cookie_orchestrator.py`:**
- Each orchestrator iteration emits `thinking` (the brain's reasoning)
- Each `execute_tool` emits `tool_start` and `tool_result`
- Trust shifts during the run emit `trust_shift`

**New events not in current SSE:**
- `thinking` — orchestrator brain's reasoning stubs (currently only in logs)
- `trust_shift` — individual memory trust changes as they happen
- `retrieval` — the full set of retrieved memories with scores before filtering

### Step 4: Keep SSE Working (Backward Compat)

Don't delete the SSE endpoints yet. The EventBus feeds both:
- WebSocket clients (new path)
- SSE generator (existing path, thin adapter that reads from EventBus)

This means Electron can migrate incrementally — switch to WS when ready, SSE still works during transition.

### Step 5: Frontend WebSocket Client (`frontend/src/lib/ws.ts`)

New file. Replaces `streamFromCrtApi()` and the notification SSE connection.

```typescript
class AetherSocket {
  connect(url: string, token?: string): void
  send(message: ClientMessage): void
  onEvent(type: string, handler: (data: any) => void): void
  disconnect(): void

  // Auto-reconnect with exponential backoff
  // Ping/pong keepalive
  // Queue messages while disconnected
}
```

The existing `StreamCallbacks` type maps directly to WS event handlers — same callback signatures, different transport.

### Step 6: Wire Notifications Through WS

Replace the notification SSE stream (`/api/notifications/stream`) with WS push.

- `personal_agent/notifications.py` currently uses `register_sse_connection()` with asyncio queues
- Change to: emit to EventBus with `type: "notification"`, WS manager delivers to connected clients
- Electron main process switches from SSE listener to WS listener

### Step 7: Electron Updates

- `electron/main.js`: Replace the SSE notification listener with a WS connection
- `frontend/src/lib/api.ts`: Add `AetherSocket` alongside existing fetch (gradual migration)
- `frontend/src/components/chat/ChatThreadView.tsx`: Wire new event types (thinking, trust_shift, retrieval)

## Files Created
- `routes/ws.py` — WebSocket endpoint + ConnectionManager
- `personal_agent/event_bus.py` — pub/sub EventBus

## Files Modified
- `routes/register.py` — register WS route
- `crt_api.py` — mount WS endpoint
- `routes/chat.py` — emit events to EventBus (alongside existing SSE yields)
- `personal_agent/cookie_orchestrator.py` — emit thinking/tool/trust events
- `personal_agent/notifications.py` — emit to EventBus instead of/alongside SSE queues
- `frontend/src/lib/api.ts` — add AetherSocket class
- `electron/main.js` — switch notification listener to WS

## Frontend Redesign

The WS migration is also the moment to redesign the chat UI. These changes depend on the new event types (thinking, trust_shift, retrieval) that only exist in the WS path.

### Step 8: Kill the Bubbles — Borderless Message Layout

**Current**: User messages in terracotta pill boxes, assistant in bordered containers.
**New**: Text flows directly on the background. No boxes, no borders.

- User messages: right-aligned, slightly faded/muted text, no container
- Assistant messages: left-aligned, full opacity, no container
- Timestamps inline and subtle
- Clean separation via spacing, not borders

**Files**:
- `frontend/src/components/chat/MessageBubble.tsx` — strip gradient/border/box-shadow styles, render as plain text blocks
- `frontend/src/index.css` — remove `.user-bubble` and `.assistant-bubble` container styles

### Step 9: Structured Tool Results (Inline Cards)

When the orchestrator calls tools, results render as structured cards inside the message flow:

```
◈ GPT LOG SEARCH
  query: "CRT evolution"
  → 4 hits · 14ms
  ▸ CRT Roadmap (May '25) — 0.676
  ▸ Code Debugging (Apr '25) — 0.671
```

Cards are compact, monospace-ish, with subtle background tint. Expandable on tap.

**Files**:
- `frontend/src/components/chat/ToolResultCard.tsx` — **NEW** component
- `frontend/src/components/chat/ChatThreadView.tsx` — render ToolResultCards inline from `tool_result` WS events

### Step 10: Thinking Stubs (Orchestrator Reasoning)

The `thinking` WS event shows WHY the next tool call happens:

```
💭 Need to search GPT logs for early CRT mentions,
   then cross-reference with current memory state
```

Rendered inline between tool calls during streaming. Lighter text, slightly indented.

**Files**:
- `frontend/src/components/chat/ThinkingStub.tsx` — **NEW** component
- `frontend/src/components/chat/ChatThreadView.tsx` — render ThinkingStubs from `thinking` WS events

### Step 11: Live Trust Score Display

The `retrieval` and `trust_shift` WS events power a real-time trust visualization:

**During retrieval:**
```
T:0.70 ██████████░░ "under the hood work"
T:0.97 ████████████ "full db dump"
T:0.46 █████░░░░░░░ "did nothing but prompt"
```

**During reasoning (trust shifts):**
```
T:0.70→0.73 ▲ "under the hood work"     ← cited, trust bumped
T:0.97 ──── "full db dump"               ← stable
T:0.46→0.51 ▲ "did nothing but prompt"   ← corroborated
```

Trust bars animate — slide right on increase, shrink on decrease. The user watches Aether weigh evidence.

**Files**:
- `frontend/src/components/chat/TrustBar.tsx` — **NEW** animated trust bar component
- `frontend/src/components/chat/RetrievalPanel.tsx` — **NEW** renders retrieved memories with trust bars
- `frontend/src/components/chat/ChatThreadView.tsx` — wire `retrieval` and `trust_shift` events

### Step 12: Auto-Collapsing Pipeline Steps

While streaming, all thinking stubs + tool results + trust shifts are visible. When `done` arrives, they auto-collapse:

**While streaming:**
```
💭 Need to search GPT logs...
◈ GPT LOG SEARCH → 4 hits
T:0.70→0.74 ▲
💭 Earliest is March '25...
◈ GPT LOG CONTEXT → 5 messages
● generating...
```

**After complete — auto-collapsed:**
```
▸ 4 steps · 4 searches · 2 trust shifts
```

**Tapped open:**
```
▾ 4 steps · 4 searches · 2 trust shifts
┊ 💭 Need to search GPT logs...
┊ ◈ GPT LOG SEARCH → 4 hits
┊ T:0.70→0.74 ▲
┊ 💭 Earliest is March '25...
┊ ◈ GPT LOG CONTEXT → 5 messages
└───────────────────────────
```

Same UX pattern as the current "9 pipeline steps" dropdown — just richer content inside.

**Files**:
- `frontend/src/components/chat/PipelineTrace.tsx` — refactor to accept thinking/tool/trust events and render structured content instead of flat status strings
- `frontend/src/components/chat/AgentThinkingStrip.tsx` — merge with PipelineTrace or replace

### Step 13: Metadata Footer

After each response, a compact metadata line:

```
☁ Claude · ✓ Governance · 5 memories · 3 GPT logs · 2 trust shifts
```

Clicking opens the collapsed pipeline trace.

**Files**:
- `frontend/src/components/chat/MessageFooter.tsx` — **NEW** (or refactor existing footer in MessageBubble)

## New Frontend Files
- `frontend/src/lib/ws.ts` — AetherSocket WebSocket client
- `frontend/src/components/chat/ToolResultCard.tsx` — inline tool result cards
- `frontend/src/components/chat/ThinkingStub.tsx` — orchestrator reasoning display
- `frontend/src/components/chat/TrustBar.tsx` — animated trust score bar
- `frontend/src/components/chat/RetrievalPanel.tsx` — retrieved memories with trust bars
- `frontend/src/components/chat/MessageFooter.tsx` — compact post-response metadata

## Modified Frontend Files
- `frontend/src/components/chat/MessageBubble.tsx` — remove bubble containers, borderless layout
- `frontend/src/components/chat/ChatThreadView.tsx` — wire all new WS event types, render new components
- `frontend/src/components/chat/PipelineTrace.tsx` — structured content + auto-collapse
- `frontend/src/components/chat/AgentThinkingStrip.tsx` — merge into PipelineTrace or simplify
- `frontend/src/lib/api.ts` — add AetherSocket alongside existing fetch
- `frontend/src/index.css` — remove bubble styles, update spacing for borderless layout

## What This Does NOT Change (Yet)
- SSE module (`sse/`) — separate retirement session
- Mobile app (Expo) — needs WS server first, then build app
- Cloudflare tunnel setup — needs WS server first

## Order of Operations

**Backend (WS foundation):**
1. EventBus + WS server endpoint (backend, test with wscat)
2. Pipeline event emission (backend, events flow through bus)
3. Notification migration (replace notification SSE with WS push)

**Frontend (UI redesign, depends on WS):**
4. Frontend WS client (`ws.ts` — AetherSocket)
5. Electron main process update (replace SSE listener with WS)
6. Kill bubbles — borderless message layout
7. Structured tool result cards
8. Thinking stubs
9. Live trust score bars + retrieval panel
10. Auto-collapsing pipeline steps
11. Metadata footer

Each step is independently testable. The SSE path stays alive throughout the backend migration. Frontend steps 6-11 can be done incrementally — each one is a visual improvement on its own.

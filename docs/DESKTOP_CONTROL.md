# Desktop Control System

**Version:** v2.3 (March 23, 2026)
**Sprint:** 11
**Layer:** 6 — action-level gating
**Files:** `personal_agent/desktop_control.py`, `personal_agent/desktop_vision.py`, `personal_agent/desktop_agent.py`, `routes/desktop.py`



# Planned: Local Vision & Control Processing
### Status: 3/24/2026 - not started
The current desktop agent sends every screenshot to Claude's vision API (via `ClaudeVisionProvider` or `CookieVisionProvider`) for action selection. This works but has drawbacks:
- Every ReAct step costs a cloud API call (5-15 per task)
- Dependent on Claude API availability and cookie freshness
- Latency per step includes round-trip to cloud

### Planned Changes

**Local vision model integration:**
- Add `LocalVisionProvider` implementing the existing `VisionProvider` interface
- Candidate models: `moondream2`, `Qwen2-VL`, `Florence-2` (all runnable via Ollama on modest hardware)
- Cloud vision becomes Tier 2 fallback, not primary

**Local action selection:**
- The LLM deciding "what to do next" in the ReAct loop should run on the local Ollama model by default
- For the browser agent specifically, DOM text provides sufficient context — no vision model needed for most tasks
- Vision only escalates for: complex visual layouts, canvas/WebGL content, visual verification ("does this look right?")

**Routing mode integration:**
- Local/cloud/hybrid setting from the Settings panel applies to vision and control processing, not just intent routing
- User controls cost vs capability tradeoff per their preference

**Target**: v3.1+ (after browser agent stabilizes)


---

## Overview

Aether can see and control the user's desktop through a ReAct (Reason + Act) loop. A vision-capable LLM analyzes screenshots, decides on a single action, the agent executes it, takes a new screenshot, and repeats until the task is done or fails.

The system is memory-grounded: verified facts from CRT memory (paths, preferences, app locations) are injected into the vision prompt so the model has real context about the user's environment.

---

## Architecture

```
User: "open notepad"
        │
        ▼
┌─────────────────┐
│  DesktopAgent    │  ← ReAct loop (max 25 steps)
│  (Orchestrator)  │
└───────┬─────────┘
        │
   ┌────┴────┐
   ▼         ▼
┌──────┐  ┌──────────────┐
│Screen│  │VisionProvider│
│Capture│  │(Cloud LLM)   │
└──┬───┘  └──────┬───────┘
   │             │
   ▼             ▼
┌──────────────────────┐
│  DesktopController   │  ← pyautogui + mss + Pillow
│  (Mouse/KB/Window)   │
└──────────────────────┘
```

### Step-by-step flow

1. `DesktopController` captures a full-resolution screenshot via `mss` (e.g. 4592x2048 on ultrawide)
2. Screenshot resized to 1280px wide, compressed to JPEG, base64-encoded
3. `VisionProvider` sends image + task + action history + memory context to a vision LLM
4. LLM returns a single JSON action: click, type, hotkey, scroll, done, failed, or need_info
5. `DesktopAgent` scales coordinates from 1280px vision-space back to actual screen resolution
6. Safety checks: blocked apps, hard-blocked targets, rate limits, restricted regions, confirmation gating
7. Action executed via `pyautogui`
8. Loop back to step 1 with fresh screenshot. Stops on `done`, `failed`, `need_info`, or max steps

---

## Components

### DesktopController (`desktop_control.py`)

Low-level automation primitives. No AI awareness. Wraps pyautogui, mss, and Pillow.

| Method | Purpose |
|--------|---------|
| `take_screenshot(monitor=0)` | Full-screen capture (monitor=0 = all monitors) |
| `screenshot_to_base64(img, max_width=1280, quality=75)` | Resize + JPEG compress + base64 encode |
| `screenshot_region(x, y, width, height)` | Capture a specific rectangle |
| `get_cursor_position()` | Current mouse position |
| `move_mouse(x, y, duration=0.3)` | Move cursor |
| `click(x, y, button="left", clicks=1)` | Mouse click |
| `double_click(x, y)` | Double-click |
| `right_click(x, y)` | Right-click |
| `drag(start_x, start_y, end_x, end_y, duration=0.5)` | Click-drag |
| `type_text(text, interval=0.03)` | Type string (ASCII via typewrite, unicode via write) |
| `press_key(key)` | Press single key (enter, tab, escape, etc.) |
| `hotkey(*keys)` | Key combination (e.g. ctrl+c) |
| `scroll(amount, x=None, y=None)` | Scroll wheel (positive=up, negative=down) |
| `get_active_window()` | Current window title, position, size |
| `find_window(title_substring)` | Search windows by title |
| `focus_window(title_substring)` | Bring window to front |
| `get_action_history(limit=20)` | Recent action log |

Every action is recorded in an internal `_action_history` list with timestamps.

**Safety defaults:**
- `pyautogui.FAILSAFE = True` — move mouse to (0,0) corner to abort all automation
- `pyautogui.PAUSE = 0.3` — delay between actions for human intervention

**Dependencies:** pyautogui, mss, Pillow — all optional with graceful degradation if missing.

---

### VisionProvider (`desktop_vision.py`)

Abstract interface for screenshot analysis via vision-capable LLMs.

#### Action Types

| ActionType | Description |
|------------|-------------|
| `CLICK` | Left-click at coordinates |
| `DOUBLE_CLICK` | Double-click at coordinates |
| `RIGHT_CLICK` | Right-click at coordinates |
| `TYPE` | Type text string |
| `HOTKEY` | Key combination |
| `PRESS_KEY` | Single key press |
| `SCROLL` | Mouse wheel |
| `DRAG` | Click-drag between coordinates |
| `WAIT` | Pause for N seconds |
| `DONE` | Task completed successfully |
| `FAILED` | Task cannot be completed |
| `NEED_INFO` | Need clarification from user |

#### Data Structures

**`DesktopAction`** — single action returned by vision model:
- `action_type`, `x`, `y`, `text`, `key`, `keys`, `scroll_amount`, `end_x`, `end_y`, `wait_seconds`, `reasoning`, `confidence` (0-1), `target_description`

**`VisionAnalysis`** — full vision response:
- `actions` (list of DesktopAction), `screen_description`, `task_progress` (starting/in_progress/almost_done/done/stuck), `observations`

#### Implementations

**`ClaudeVisionProvider`** — uses Anthropic API key via `AnthropicClient.chat_with_image()`. Direct API call with base64 image.

**`CookieVisionProvider`** — uses claude.ai session cookie (no API key needed):
1. Decodes base64 screenshot
2. Re-compresses to 1280px wide JPEG at 70% quality
3. Uploads via multipart form to `claude.ai/api/{org}/upload` using `curl_cffi` CurlMime
4. Gets back a file UUID
5. Sends chat completion referencing the file UUID
6. Parses SSE response into `VisionAnalysis`

**`LocalVisionProvider`** — stub for future local models (moondream2, Qwen2-VL). Raises `NotImplementedError`.

---

### DesktopAgent (`desktop_agent.py`)

The core ReAct loop orchestrator. Owns a `DesktopController` and a `VisionProvider`.

#### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_steps` | 25 | Maximum iterations before abort |
| `step_timeout` | 30.0s | Timeout per vision call |

#### ReAct Loop (per iteration)

1. Rate limit check (overall actions/min)
2. Take screenshot, compute scale factor (`screen_width / 1280`)
3. Check active window against blocked apps list
4. Call `vision.analyze_screenshot()`
5. Handle terminal states: DONE → success, FAILED → error, NEED_INFO → error with clarification
6. Hard-blocked target check (passwords, credit cards, etc.)
7. Click/keystroke rate limiting (2s cooldown on click limit)
8. Confirmation check via `on_checkpoint` callback for dangerous actions
9. Scale coordinates from vision-space to screen-space
10. Restricted region check (system tray blocked)
11. Execute action via `DesktopController`
12. Log entry, call `on_step` callback, 0.5s pause

#### Result

`DesktopTaskResult`: `success`, `steps_taken`, `total_duration_ms`, `final_screenshot_b64`, `action_log`, `error`, `task_summary`

---

## Safety System

### Blocked Applications (18 entries)

Actions abort immediately if active window matches any of these:

**Password managers:** 1Password, LastPass, Bitwarden, KeePass
**Banking/payments:** Chase, Wells Fargo, PayPal, Venmo
**Admin tools:** Registry Editor, Task Manager, Device Manager, Credential Manager, Windows Security, Disk Management, Services, Group Policy, Certificates, Firewall, PowerShell ISE

### Hard-Blocked Targets (never executed, even with confirmation)

- Password fields
- Credit card inputs
- SSN / Social Security
- Bank account / Routing number
- CVV

### Confirmation Keywords (checkpoint gate mid-loop)

Actions matching these words in the target description require user confirmation before executing:

send, submit, delete, remove, purchase, buy, pay, publish, post, confirm, sign out, log out, uninstall, format, erase, reset, shutdown, restart

### Rate Limiting (sliding window)

| Limiter | Max per minute |
|---------|---------------|
| Overall actions | 20 |
| Clicks | 10 |
| Keystrokes | 200 |

### Restricted Screen Regions

System tray area blocked by default (coordinates checked after scaling to real screen space).

### Emergency Stop

- Move mouse to screen corner (0,0) — pyautogui.FAILSAFE aborts everything
- `POST /api/desktop/stop` — sets `_running = False` on active agent
- Escape key in frontend

---

## Coordinate Scaling

Vision models receive 1280px-wide screenshots regardless of actual resolution. The agent computes:

```
scale = actual_screen_width / 1280
real_x = vision_x * scale
real_y = vision_y * scale
```

Example: On a 4592px ultrawide monitor, scale = 3.59. Vision returns click at (606, 692) → actual click at (2175, 2484).

All safety checks (restricted regions, blocked areas) are applied after scaling to real coordinates.

---

## API Endpoints

**Router:** `/api/desktop`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/desktop/execute` | Execute a desktop task |
| POST | `/api/desktop/stop` | Stop the running task |
| GET | `/api/desktop/screenshot` | Take a screenshot |
| GET | `/api/desktop/history` | Action receipt history |

### POST /api/desktop/execute

**Request:**
```json
{
  "task": "open notepad",
  "thread_id": "desktop",
  "max_steps": 25
}
```

- `task` (required): natural language task description
- `thread_id` (default "desktop"): for receipt logging
- `max_steps` (1-50, default 25): iteration limit

**Behavior:**
- Returns 409 if a task is already running (singleton lock)
- Retrieves CRT memory (trust >= 0.7, top_k=10) for memory-grounded context
- Creates DesktopController + CookieVisionProvider + DesktopAgent
- Logs each action step as an ActionReceipt
- Returns `DesktopExecuteResponse` with success, steps, duration, summary, action_log

### POST /api/desktop/stop

Returns 404 if no task running. Sets stop flag on active agent.

### GET /api/desktop/screenshot

Returns base64 JPEG screenshot, dimensions, and active window title.

### GET /api/desktop/history

Query params: `thread_id` (default "desktop"), `limit` (default 20).
Returns action receipts filtered to `tool_name == "desktop_action"`.

---

## Frontend Integration

`ActionCard.tsx` renders `screenshot_b64` as an inline JPEG preview with the target description overlaid. The action card appears for dangerous-action checkpoints, showing the screenshot and Yes/No/Custom buttons.

---

## Memory Grounding

When executing a desktop task, the system retrieves up to 10 verified facts (trust >= 0.7) from CRT memory and injects them into the vision prompt. This means the vision model knows:

- Exact file paths the user works with
- Application preferences and locations
- Project directories and workspace layout

Example: "open my portfolio in VS Code" — the vision model receives the actual path from memory instead of guessing.

---

## Performance

Live test: "open notepad" completed in 4 steps / 70 seconds:
1. `hotkey(win)` → opened Start menu (19s vision latency)
2. `type("notepad")` → searched (24s vision latency)
3. `click(606, 692)` scaled to `(2175, 2484)` → launched Notepad (9s vision latency)
4. `done` → recognized Notepad was open (13s vision latency)

Cookie vision provider latency: 10-24 seconds per step (network + LLM inference).

---

## Testing

- **42/42 unit tests passing**: screenshot capture, cursor position, window detection, blocked app detection (11 cases), confirmation logic (7 cases), hard-blocked targets (4 cases), restricted regions (3 cases), agent ReAct loop (5 cases), vision response parsing (3 cases)
- **Vision benchmark harness**: 22 annotated scenarios with interactive screenshot capture and accuracy metrics
- **Live integration test**: end-to-end via cookie vision provider
- **Live test runner**: `tests/desktop_control/run_live.py` — CLI tool with step-by-step logging, 3-second countdown, checkpoint prompts

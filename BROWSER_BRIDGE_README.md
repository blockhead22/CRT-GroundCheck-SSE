# Browser Bridge (local-only) — Tampermonkey + WebSocket

This is a **local-only** bridge that lets a browser tab send events to a local server and (optionally) accept a limited set of commands.

**Goal**: enable background research / page-reading workflows while keeping safety and user consent explicit.

## Safety model (important)
- **Local only**: the server binds to `127.0.0.1`.
- **Token handshake**: the browser must present a shared token (`BROWSER_BRIDGE_TOKEN`).
- **Domain allowlist**: the userscript only enables command execution on allowlisted domains.
- **User confirmation**: “write” actions (click/type/navigate) require a confirmation prompt by default.

This is intended for **your own browsing**. Do not use to automate actions you’re not authorized to perform.

## Setup

### 1) Install Python dependency
Add `websockets` to your environment:
- `pip install websockets`

(Or run `pip install -r requirements.txt` after updating it.)

### 2) Start the bridge server
In a terminal from repo root:
- `set BROWSER_BRIDGE_TOKEN=change-me`
- `D:/AI_round2/.venv/Scripts/python.exe -m browser_bridge.server`

Server default: `ws://127.0.0.1:8765`

### 3) Install the Tampermonkey userscript
- Install Tampermonkey.
- Create a new script and paste: `userscripts/crt_browser_bridge.user.js`
- Set the token + allowlist in the userscript.

### 4) Try a read-only command
- Open an allowlisted page
- Run:
  - `D:/AI_round2/.venv/Scripts/python.exe -m browser_bridge.client_cli get-page-text`

## Message types (JSON)
From browser → server:
- `{"type":"hello","token":"...","tab":{"url":"...","title":"..."}}`
- `{"type":"event","name":"selection","data":{...}}`
- `{"type":"result","id":"<cmd-id>","ok":true,"data":{...}}`

From server → browser:
- `{"type":"command","id":"<cmd-id>","name":"get_page_text","args":{...}}`

## Next steps
- Add a background worker that queues research tasks and uses the bridge to fetch pages.
- Add per-command policies (read-only vs write), throttling, and per-domain permissions.

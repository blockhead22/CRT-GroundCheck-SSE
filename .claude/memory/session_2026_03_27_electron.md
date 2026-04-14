---
name: session_2026_03_27_electron
description: Electron shell built for Aether, self-referential verbosity fix, health check flapping fix
type: project
---

## Session: 2026-03-27 — Electron Shell + Fixes

### What shipped

**1. Electron desktop shell (`electron/`)**
- `package.json` — electron 33, electron-builder, electron-store
- `main.js` — frameless window, titleBarOverlay (Windows), loading spinner, auto-detect running backend, global hotkey (Ctrl+Space → Alt+Space fallback), system tray, single instance lock, hide-to-tray on close
- `backend.js` — child process manager for crt_api.py, health polling (10s interval, 3 consecutive failures before unhealthy), auto-restart (max 5), graceful shutdown with taskkill on Windows
- `tray.js` — system tray with colored circle icons (green/amber/red), right-click menu (show/hide, restart backend, quit)
- `preload.js` — secure IPC bridge exposing `window.aether` API (backend status, logs, window controls)
- CSS injection for drag region + topbar padding for window controls
- JS injection to pad topbar 140px right for native min/max/close buttons

**2. FastAPI static file serving**
- `crt_api.py` now mounts `frontend/dist/assets` and has catch-all SPA route
- Electron production mode loads `http://localhost:8000` instead of `file://` (which broke asset paths)
- CORS updated to include `app://aether`

**3. Self-referential response verbosity fix**
- `routes/chat.py` `_answer_self_referential()`: system prompt changed from "explain with concrete examples" (produced 500-word walls) to "3-5 sentences MAX, no bullet lists"
- `max_tokens` reduced from 800 → 300

**4. Health check flapping fix**
- Was marking unhealthy on single missed HTTP response even though /health returned 200
- Root cause: Windows TCP recycling + Ollama blocking GIL caused occasional timeouts
- Fix: require 3 consecutive failures (UNHEALTHY_THRESHOLD), interval increased 5s → 10s, timeout increased 3s → 5s

### Known issues / open questions
- Nick asked: "if I flip from local to claude on the chat UI, do settings actually affect the loop?" — **NOT YET INVESTIGATED**, needs checking next session
- Topbar padding injection uses MutationObserver + querySelector which is fragile — should eventually be a React-native check for `window.aether.isElectron`
- Ctrl+Space conflicts with IME on Windows, falls back to Alt+Space
- GPU cache permission errors on startup (harmless Chromium noise)
- Nick wants to explore: ambient mode (screen capture), MCP server (CRT as tool provider), voice (Whisper), cross-device sync

### Architecture decisions
- Chose Electron over Tauri (bigger ecosystem, same as Claude Desktop/VS Code, agents can scaffold)
- Frontend served through backend HTTP (not file://) to avoid absolute path issues in Vite builds
- Backend manager detects already-running backend and attaches instead of spawning duplicate

### Nick's interest areas discussed
- Ambient mode: screen capture + local vision model + CRT memory integration
- MCP server: Aether itself as an MCP server other AI tools can query
- Cross-device belief state: login from any machine, same CRT memories
- Voice with wake word: local Whisper, always-on
- Overlay mode: transparent floating panel on top of any app

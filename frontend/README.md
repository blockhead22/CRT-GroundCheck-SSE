# CRT Frontend (React + Tailwind + Framer Motion)

This is a standalone UI prototype inspired by the provided reference layout, using an earthy olive palette (`#636B2F`).
It now includes a **real multi-thread chat UI** connected to the Python CRT backend via a minimal HTTP API.

## Run

From `frontend/`:

```bash
npm install
npm run dev
```

Then open the URL Vite prints (usually `http://localhost:5173`).

## Backend API

Start the CRT API server from the repo root:

```bash
python -m pip install -r requirements.txt
python crt_api.py
```

The frontend calls `http://127.0.0.1:8123` by default.

To override, create `frontend/.env` (you can copy `frontend/.env.example`) and set:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8123
```

## What works (UI)

- Sidebar navigation + search
- Recent chat thread switching
- Chat thread view with message bubbles + timestamps
- Composer (enter to send)
- Quick action cards (click to seed a prompt)
- Typing indicator + Framer Motion transitions
- Assistant response badges + expandable CRT details (response type, gates, contradictions, retrieved memories)

## Tech

- React + TypeScript (Vite)
- TailwindCSS
- Framer Motion

## Next steps

- Expand CRT metadata rendering (provenance, ledger details, suggestions)
- Add auth/user profile + real persistence for chat threads

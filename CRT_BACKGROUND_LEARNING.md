# Background learning + background research (design notes)

## Goals
- Let the assistant “grow with you” via:
  - passive capture of user-approved signals (preferences, long-term projects)
  - background research tasks (read pages, summarize, cross-check contradictions)
- Maintain the core truth constraint: **don’t lie / don’t invent**.

## Principle: learning must be provenance-first
Everything learned should carry:
- source: user | chat | research | tool
- timestamp
- confidence/trust
- provenance: URL(s) or quoted memory text
- revocability: can be removed on request

## Two-step promotion
1) Background tasks can write **notes** (low-trust) like:
   - “Research note: X appears on <url> (timestamp)”
2) Only explicit user confirmation promotes a note into a stable personal fact/preference.

## Background worker (recommended shape)
- A queue of tasks: `research(topic)`, `monitor(url)`, `summarize_page(url)`, `compare_sources(topic)`.
- Runs on a local schedule (cron-style) or on idle.
- Writes artifacts to `artifacts/background/…` and optionally creates memory entries as *research notes*.

## Browser bridge (for live research)
Use a local-only browser bridge (Tampermonkey + WebSocket) so the assistant can:
- read page text / selected text
- extract specific DOM text via CSS selector

Default stance:
- **read-only commands** enabled
- write actions (click/type/navigate) require user confirmation + domain allowlist

See: `BROWSER_BRIDGE_README.md`.

## Why this helps “won’t lie”
- Background research does not become “belief” unless the user says so.
- When answering, the assistant can cite:
  - exact stored memory text
  - URLs/timestamps from research notes
- Anything else must be labeled uncertainty/speculation.

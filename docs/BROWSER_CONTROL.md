# Browser Control

**Version:** v2.9+ (March 24, 2026)
**Status:** In development
**Layer:** 5 — action-level gating (shares safety model with Desktop Control)
**Files:** `routes/desktop.py` (browser actions), `personal_agent/desktop_agent.py` (browser mode)

---

## Overview

Browser Control extends the Desktop Control system to interact with web browsers programmatically. Instead of raw screenshot-based vision for every action, the browser agent can leverage DOM text, page structure, and browser automation APIs for faster and cheaper interactions.

This is a companion to [Desktop Control](DESKTOP_CONTROL.md) — they share the same vision-action architecture but the browser agent has additional tools optimized for web content.

---

## Capabilities

### Current (via Desktop Control)

The browser is already controllable through the desktop vision-action loop:
- Navigate to URLs
- Click elements identified by vision
- Type text into form fields
- Scroll pages
- Read visible text from screenshots

### Planned (Browser-Native)

- DOM-aware element selection (no vision needed for most interactions)
- Form auto-fill from memory slots
- Tab management
- Cookie/session awareness
- Network request inspection
- JavaScript execution for page state queries

---

## Web Search Integration

Web search is a core capability that will live under Browser Control. The agent can search the web using external search APIs and return summarized results.

### Current State

Web search is functional as a tool in the task agent pipeline:
- Triggered by intents like "search for", "look up", "find latest"
- Uses configured search API (DuckDuckGo, Brave, or similar)
- Results are summarized by the LLM before being returned

### Settings

The following settings exist in the UI (Behavior tab > Web Search) but are **currently stubbed**:

| Setting | Default | Description |
|---------|---------|-------------|
| `web_search_max_results` | `8` | Maximum results per query |
| `web_search_region` | `us-en` | Locale for search results |

These save to `user_settings` but the search tool reads from hardcoded values. Wiring is planned for the browser control sprint.

---

## Architecture

```
User message: "search for latest AI news"
  │
  ├── Intent Router → web_search intent
  │
  ├── Task Agent → WebFetchAgent (sub-agent)
  │    ├── Search API call (DuckDuckGo/Brave)
  │    ├── Fetch top N results
  │    ├── Summarize via LLM (if synthesis_enabled)
  │    └── Return structured results
  │
  └── Response with sources + summaries
```

For browser automation tasks (not just search):

```
User message: "go to github and check my notifications"
  │
  ├── Intent Router → desktop_action intent (browser mode)
  │
  ├── Desktop Agent (browser mode)
  │    ├── Screenshot → Vision LLM → Action
  │    ├── Navigate to github.com
  │    ├── Screenshot → identify notifications
  │    ├── Click notifications bell
  │    ├── Screenshot → read notification list
  │    └── Summarize findings
  │
  └── Response with notification summary
```

---

## Safety

- Same confirmation policies as Desktop Control (`desktop_require_confirmation`)
- No automatic form submission without user confirmation for sensitive data
- Cookie/credential handling follows the desktop agent's security model
- Web search queries are logged for audit trail
- Auto web research (via heartbeat) requires explicit opt-in due to privacy implications

---

## Related Docs

- [Desktop Control](DESKTOP_CONTROL.md) — parent system for vision-action loop
- [Settings Page](SETTINGS.md) — web search settings (currently stubbed)
- [Sub-Agents & Orchestration](SUB_AGENTS.md) — WebFetchAgent details

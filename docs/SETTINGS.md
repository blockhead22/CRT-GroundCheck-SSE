# Settings Page

**Version:** v2.9.2 (March 24, 2026)
**Files:** `frontend/src/pages/SettingsPage.tsx`, `routes/auth.py`, `auth.py`

---

## Overview

The Settings page (`/settings`) provides user-facing controls for every major CRT/Aether subsystem. Settings are stored per-user in the `user_settings` SQLite table as key-value pairs and served via the `/api/auth/settings` endpoints.

### Architecture

```
SettingsPage.tsx  →  PATCH /api/auth/settings  →  auth.set_user_setting()  →  user_settings table
                     GET  /api/auth/settings   →  auth.get_user_settings() →  defaults + overrides
```

Each setting key must exist in three places to be fully wired:
1. **`CLOUD_SETTING_DEFAULTS`** in `auth.py` — default value
2. **`allowed_keys`** in `routes/auth.py` — API whitelist (rejects unknown keys silently)
3. **Frontend UI** in `SettingsPage.tsx` — user-facing control

---

## Tabs

The page is organized into 8 tabs:

| Tab | Purpose | Setting count |
|-----|---------|---------------|
| **Profile** | Display name, nickname, agent name | 3 |
| **Cloud** | OpenAI (Tier 1), Claude (Tier 2), Intuition Check, Usage | ~18 |
| **Desktop** | Vision-action loop, limits, confirmation, idle automation | 7 |
| **Heartbeat** | Proactive background loop, news monitoring, curiosity | 6 |
| **Behavior** | Greeting, conflict warnings, provenance, background jobs, web search | 10 |
| **Advanced** | Pipeline bypass, tooling, model selection, routing mode | 8 |
| **Facts** | View/edit known memory facts (slots) | — |
| **Account** | Username, user ID (read-only) | — |

---

## Wiring Status

### Fully Wired (backend reads these and changes behavior)

| Key | Read by | Effect |
|-----|---------|--------|
| `bypass_crt` | `routes/chat.py` | Skips entire CRT pipeline, direct cloud generation |
| `generation_mode` | `routes/chat.py` | Selects local / cloud_openai / cloud_claude |
| `cloud_model_openai` | `routes/chat.py` | Which OpenAI model to use |
| `cloud_model_claude` | `routes/chat.py` | Which Claude model to use |
| `cloud_slot_classification` | `routes/chat.py` | Cloud-powered fact extraction |
| `cloud_nli_contradiction` | `routes/chat.py` | Cloud NLI contradiction detection |
| `cloud_reflection_validation` | `heartbeat_system.py` | Epistemic audit of self-model |
| `cloud_escalation_policy` | `routes/chat.py` | When to escalate local → cloud |
| `cloud_confidence_threshold` | `routes/chat.py` | Escalation confidence gate |
| `cloud_daily_limit_multiplier` | `cloud_features.py` | Scale daily call limits |
| `cloud_claude_enabled` | `cloud_features.py` | Master Claude toggle |
| `cloud_claude_generation` | `cloud_features.py` | Claude for generation fallback |
| `cloud_claude_reflection` | `cloud_features.py` | Claude for reflection audits |
| `cloud_claude_daily_limit` | `cloud_features.py` | Max Claude calls per day |
| `cloud_claude_max_tokens` | `cloud_features.py` | Max tokens per Claude call |
| `desktop_control_enabled` | `routes/desktop.py` | Desktop vision-action loop |
| `desktop_max_steps_per_task` | `routes/desktop.py` | Max ReAct iterations |
| `desktop_max_actions_per_session` | `routes/desktop.py` | Session-wide action cap |
| `desktop_require_confirmation` | `routes/desktop.py` | Gate dangerous actions |
| `desktop_vision_provider` | `routes/desktop.py` | Cookie vs API key for vision |
| `desktop_heartbeat_idle_control` | `heartbeat_executor.py` | Idle desktop automation |
| `desktop_idle_task` | `heartbeat_executor.py` | What to run when idle |
| `routing_mode` | `task_agent.py` | hybrid / local_only / cloud_only |
| `routing_llm_model` | `task_agent.py` | Model override for routing |
| `synthesis_enabled` | `task_agent.py` | LLM interprets tool results |
| `intuition_check_enabled` | `intuition_check.py` | Master toggle |
| `intuition_check_clarify` | `intuition_check.py` | Clarify ambiguous input |
| `intuition_check_suggest` | `intuition_check.py` | Suggest next steps |
| `intuition_check_reconnect` | `intuition_check.py` | Welcome back after idle |
| `intuition_check_model` | `intuition_check.py` | Which model for checks |
| `intuition_check_escalation` | `intuition_check.py` | Cloud fallback policy |
| `preferred_nickname` | Settings API | What agent calls user |
| `agent_name` | Settings API | AI agent's display name |
| `enable_tooling` | `routes/chat.py` | Allow function calling |

### Stubbed (UI saves value, backend not yet reading)

These settings save to the database but the backend services currently read from `runtime_config.py` or `heartbeat_config_json` instead. They are placeholders for future wiring.

| Key | Intended target | Current source |
|-----|----------------|----------------|
| `heartbeat_enabled` | `heartbeat_system.py` | `heartbeat_config_json` on `thread_sessions` table |
| `heartbeat_interval_seconds` | `heartbeat_system.py` | `heartbeat_config_json` |
| `heartbeat_active_hours_start` | `heartbeat_system.py` | `heartbeat_config_json` |
| `heartbeat_active_hours_end` | `heartbeat_system.py` | `heartbeat_config_json` |
| `heartbeat_news_monitoring` | `heartbeat_system.py` | `heartbeat_config_json` |
| `heartbeat_news_topics` | `heartbeat_system.py` | `heartbeat_config_json` |
| `heartbeat_curiosity_enabled` | `heartbeat_system.py` | `heartbeat_config_json` |
| `greeting_enabled` | `runtime_config["greeting"]` | `crt_runtime_config.json` |
| `greeting_style` | `runtime_config["greeting"]` | `crt_runtime_config.json` |
| `conflict_warning_enabled` | `runtime_config["conflict_warning"]` | `crt_runtime_config.json` |
| `provenance_enabled` | `runtime_config["provenance"]` | `crt_runtime_config.json` |
| `provenance_world_check` | `runtime_config["provenance"]` | `crt_runtime_config.json` |
| `background_jobs_enabled` | `runtime_config["background_jobs"]` | `crt_runtime_config.json` |
| `background_auto_resolve` | `runtime_config["background_jobs"]` | `crt_runtime_config.json` |
| `background_auto_research` | `runtime_config["background_jobs"]` | `crt_runtime_config.json` |
| `background_auto_learning` | `runtime_config["background_jobs"]` | `crt_runtime_config.json` |
| `web_search_max_results` | web search tool | Hardcoded |
| `web_search_region` | web search tool | Hardcoded |

To fully wire a stubbed setting, the backend service needs to call `auth.get_user_setting(user_id, key, default)` and use the result instead of (or merged with) the runtime config value.

---

## API Endpoints

### GET /api/auth/settings

Returns all settings for the authenticated user, merged with defaults.

```json
{
  "ok": true,
  "settings": {
    "cloud_slot_classification": "off",
    "generation_mode": "local",
    "heartbeat_enabled": "true",
    ...
  }
}
```

### PATCH /api/auth/settings

Upserts settings. Accepts a flat `{key: value}` dict. Unknown keys are silently ignored.

```json
// Request
{ "generation_mode": "cloud_openai", "greeting_style": "simple" }

// Response
{ "ok": true, "updated": { "generation_mode": "cloud_openai", "greeting_style": "simple" } }
```

### GET /api/auth/cloud-usage

Returns real-time cloud usage stats including per-feature call counts, estimated tokens, and daily limits.

---

## Adding a New Setting

1. Add default to `CLOUD_SETTING_DEFAULTS` in `auth.py`
2. Add key to `allowed_keys` in `routes/auth.py`
3. Add UI control in appropriate tab in `SettingsPage.tsx`
4. Wire backend: call `auth.get_user_setting(user_id, key, default)` in the service that should respond to it
5. Test: change value in UI → verify backend behavior changes

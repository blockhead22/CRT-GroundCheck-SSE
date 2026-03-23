# Configuration & Environment Variables

CRT/Aether uses two configuration layers: environment variables for secrets and host-level settings, and a JSON runtime config file for application behavior.

## Runtime Config

**File:** `crt_runtime_config.json` in the project root

**Loader:** `personal_agent/runtime_config.py` — `load_runtime_config()`

Resolution order:
1. Explicit `config_path` argument
2. `CRT_RUNTIME_CONFIG_PATH` env var
3. `./crt_runtime_config.json` if it exists
4. Built-in defaults (`_DEFAULT_CONFIG` dict)

The loader deep-merges your JSON file over the defaults, so you only need to specify the keys you want to change.

## Environment Variables

### Core Server

| Variable | Default | Where Read | Description |
|----------|---------|-----------|-------------|
| `CRT_HOST` | `127.0.0.1` | `crt_api.py:1442` | Bind address for the FastAPI server |
| `PORT` | `8000` | `crt_api.py:1443` | Server port |
| `CRT_CORS_ORIGINS` | `http://localhost:5173,...` | `crt_api.py:1053` | Comma-separated allowed CORS origins |

### LLM / Model

| Variable | Default | Where Read | Description |
|----------|---------|-----------|-------------|
| `CRT_OLLAMA_MODEL` | `llama3.2:latest` | `crt_api.py:1096`, `hybrid_llm_client.py:526` | Default local model for Ollama |
| `CRT_ENABLE_LLM` | `true` | `crt_api.py:1103` | Enable/disable LLM generation entirely |
| `CRT_PRODUCT_MODE` | `local_only` | `hybrid_llm_client.py:522` | `local_only` or `hybrid_verified` |
| `CRT_CLOUD_MODEL` | (none) | `hybrid_llm_client.py:537` | Cloud provider model name |
| `CRT_CLOUD_BASE_URL` | `https://api.openai.com/v1` | `hybrid_llm_client.py:539` | Base URL for cloud API |
| `CRT_CLOUD_TIMEOUT_SECONDS` | `120` | `hybrid_llm_client.py:540` | Cloud API request timeout |
| `CRT_ANTHROPIC_MODEL` | `claude-sonnet-4-6` | `hybrid_llm_client.py:556` | Anthropic model name |
| `CRT_ANTHROPIC_RPM` | `50` | `hybrid_llm_client.py:581` | Anthropic rate limit (requests per minute) |
| `CRT_ANTHROPIC_TPD` | `1000000` | `hybrid_llm_client.py:582` | Anthropic rate limit (tokens per day) |
| `CRT_MODEL_FAST` | `qwen3:14b` | `routes/chat.py:1307` | Fast model for lightweight tasks |
| `CRT_MODEL_ROLE_<ROLE>` | (from config) | `hybrid_llm_client.py:215` | Per-role model override (e.g., `CRT_MODEL_ROLE_ANSWER`) |

### API Keys

| Variable | Default | Where Read | Description |
|----------|---------|-----------|-------------|
| `OPENAI_API_KEY` | (none) | `hybrid_llm_client.py:74` | OpenAI API key for Tier 1 cloud features |
| `ANTHROPIC_API_KEY` | (none) | `hybrid_llm_client.py:561` | Anthropic API key for Tier 2 |

### Memory

| Variable | Default | Where Read | Description |
|----------|---------|-----------|-------------|
| `CRT_SHARED_MEMORY` | `false` | `crt_api.py:1135` | Use shared memory database across all threads |
| `CRT_MEMORY_DB` | (none) | `self_model.py:51` | Override path for memory database |

### Heartbeat & Reflection

| Variable | Default | Where Read | Description |
|----------|---------|-----------|-------------|
| `CRT_HEARTBEAT_LOOP_ENABLED` | (from config) | via runtime config | Enable the periodic heartbeat scheduler |
| `CRT_THINKING_ENABLED` | `true` | `thinking_loop.py:504` | Enable the background thinking loop |
| `CRT_THINKING_INTERVAL_SECONDS` | `600` | `thinking_loop.py:503` | Thinking loop interval (seconds) |

### Chat Behavior

| Variable | Default | Where Read | Description |
|----------|---------|-----------|-------------|
| `CRT_CHAT_TIMING` | `1` | `routes/chat.py:1924` | Enable pipeline timing in response metadata |
| `CRT_TASKING_INTERVAL_SECONDS` | `0` | `routes/chat.py:64` | Minimum seconds between task processing runs |

### GroundCheck Bridge

| Variable | Default | Where Read | Description |
|----------|---------|-----------|-------------|
| `CRT_GROUNDCHECK_BRIDGE_INTERVAL_SECONDS` | `120` | `routes/chat.py:214` | Sync interval for GroundCheck bridge |
| `CRT_GROUNDCHECK_BRIDGE_MIN_TRUST` | `0.2` | `routes/chat.py:235` | Minimum trust for bridge sync |
| `CRT_GROUNDCHECK_BRIDGE_RAW_LIMIT` | `400` | `routes/chat.py:239` | Max raw memories to sync |
| `CRT_GROUNDCHECK_BRIDGE_NARRATIVE_LIMIT` | `120` | `routes/chat.py:243` | Max narrative memories to sync |
| `CRT_GROUNDCHECK_BRIDGE_SOURCES` | `user,inferred` | `routes/chat.py:247` | Comma-separated source types to sync |
| `GROUNDCHECK_DB` | (none) | `trust_decay.py:153` | Path to GroundCheck database |

### Telegram Channel

| Variable | Default | Where Read | Description |
|----------|---------|-----------|-------------|
| `TELEGRAM_BOT_TOKEN` | (none) | `channels/telegram_bot.py:97` | Telegram bot API token |
| `CRT_API_URL` | `http://127.0.0.1:8123` | `channels/telegram_bot.py:98` | CRT API URL for Telegram bot to call |
| `TELEGRAM_LIVE_LOG_PATH` | `ai_logs/telegram_live.jsonl` | `channels/telegram_bot.py:103` | Path for Telegram live log |
| `TELEGRAM_ALLOWED_USERS` | `8793030650` | `channels/telegram_bot.py:106` | Comma-separated allowed Telegram user IDs |

### Schema Validation

| Variable | Default | Where Read | Description |
|----------|---------|-----------|-------------|
| `CRT_STRICT_SCHEMA_VALIDATION` | `false` | `runtime_config.py:383` | Raise errors on schema violations instead of warning |
| `CRT_RUNTIME_CONFIG_PATH` | (none) | `runtime_config.py:420` | Explicit path to runtime config JSON |

### Training / Learning

| Variable | Default | Where Read | Description |
|----------|---------|-----------|-------------|
| `CRT_LEARNED_MODEL_PATH` | (none) | `routes/learning.py:44` | Path to the trained suggestion model |

## Runtime Config Sections

The full default config is defined in `personal_agent/runtime_config.py` in `_DEFAULT_CONFIG`. Key sections:

### `background_jobs`
Controls async research, promotion proposals, and auto-resolution. Disabled by default.

### `agent_tool_policy`
OpenClaw-style governance for tool use. Default max: 24 tool calls per run. Individual tools (execute_code, store_memory, search_web, read_file, list_files) have per-tool limits and approval requirements.

### `greeting`
Time-based greeting system with customizable templates. Generates contextual greetings based on absence duration.

### `product_mode`
Where generation happens vs where authority lives. `mode: "local_only"` keeps everything local; `mode: "hybrid_verified"` enables cloud generation with local verification.

### `generation_stack`
Provider configuration for local, cloud, and anthropic tiers. Includes routing rules, PII deny lists, and model role mappings.

### `journal_behavior`
Controls the style of reflection journal entries. Default: `reddit_thread` style.

### `training_loop`
Dev-facing periodic train/eval/publish loop for the suggestion-only model. Disabled by default.

### `dnnt_retraining`
DNNT background retraining loop that distills trusted traces into local model updates. Disabled by default.

### `assistant_profile`
Deterministic, non-chat-backed answers for questions about the assistant itself. Customizable per-topic responses.

### `onboarding`
First-run onboarding questions. When memory is empty, prompts the user for name, pronouns, title, employer, location, communication style, and goals.

# Requirements & Dependencies

**Last updated:** v2.8 (March 24, 2026)

---

## System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **Python** | 3.13+ | 3.13 |
| **Node.js** | 18+ | 20+ |
| **OS** | Windows 10/11, Linux, macOS | Windows 11 |
| **RAM** | 8 GB | 16+ GB |
| **VRAM** | — (CPU-only mode) | 8+ GB (for local LLM via Ollama) |
| **Disk** | 2 GB (code + models) | 10+ GB (with Ollama models) |

---

## External Tools

| Tool | Required? | Purpose |
|------|-----------|---------|
| **git** | Yes | Version control, project scanning, git agent tools |
| **Ollama** | Optional | Local LLM serving (qwen2.5-coder:14b, llama3.2). Heartbeat auto-manages: kills on gaming, restarts on idle |
| **Chrome + ChromeDriver** | Optional | Cloud provider test harness (Selenium-based) |

---

## Python Dependencies

### Core (Required)

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | >=0.100.0 | API server |
| `uvicorn[standard]` | >=0.22.0 | ASGI server with WebSocket + HTTP/2 |
| `sentence-transformers` | >=2.2.0 | all-MiniLM-L6-v2 for memory search and intent routing (384D embeddings) |
| `numpy` | >=1.24.0 | Vector math, cosine similarity, clustering |
| `scikit-learn` | >=1.3.0 | ML utilities, preprocessing |
| `xgboost` | >=1.7.0 | Belief classifier, contradiction resolver |
| `jsonschema` | >=4.0.0 | Runtime config validation |
| `requests` | >=2.31.0 | HTTP client for skill API calls, web fetch |
| `beautifulsoup4` | >=4.12.0 | HTML parsing for web search results |
| `python-dotenv` | >=1.2.0 | Environment variable loading from .env |
| `bcrypt` | >=5.0.0 | Password hashing for auth |
| `cryptography` | >=41.0.0 | Credential encryption (XOR encode for skill API keys) |
| `pymysql` | >=1.0.0 | Database connectivity |
| `psutil` | — | System info: CPU, RAM, disk, process monitoring |

### Desktop Control (Optional — graceful degradation if missing)

| Package | Feature Flag | Purpose |
|---------|-------------|---------|
| `pyautogui` | `HAS_PYAUTOGUI` | Mouse, keyboard, hotkey automation |
| `mss` | `HAS_MSS` | Fast multi-monitor screenshot capture |
| `Pillow` | `HAS_PIL` | Image resize, JPEG compression, base64 encoding |
| `pygetwindow` | — | Active window detection (Windows only) |
| `curl_cffi` | — | Cookie vision provider: multipart upload to claude.ai |

### System Monitoring (Optional)

| Package | Purpose |
|---------|---------|
| `pynvml` | GPU monitoring (NVIDIA). Falls back gracefully if not installed |
| `psutil` | CPU, RAM, disk, process enumeration |

### LLM Integration (Optional)

| Package | Install Group | Purpose |
|---------|--------------|---------|
| `openai` | `pip install .[llm]` | OpenAI API (GPT-4o, gpt-4o-mini for side model tap) |
| `anthropic` | `pip install .[llm]` | Anthropic API (Claude vision, Tier 2 fallback) |
| `ollama` | — | Python client for local Ollama server |

### Training & ML (Optional)

| Package | Install Group | Purpose |
|---------|--------------|---------|
| `torch` | `pip install .[full]` | DNNT micro-transformer, ViLT training |
| `transformers` | `pip install .[full]` | Model fine-tuning (SmolLM, Qwen) |
| `pandas` | `pip install .[full]` | Training data management |
| `matplotlib` | `pip install .[full]` | Eval visualization |
| `seaborn` | `pip install .[full]` | Statistical plots |
| `hdbscan` | `pip install .[full]` | Density-based clustering |
| `datasets` | `pip install .[full]` | HuggingFace dataset loading |
| `scipy` | — | Agglomerative clustering for belief synthesis |

### Channels (Optional)

| Package | Install Group | Purpose |
|---------|--------------|---------|
| `python-telegram-bot[job-queue]` | `pip install .[channels]` | Telegram bot integration with proactive polling |
| `duckduckgo-search` | — | Web search for heartbeat news monitoring |
| `opencv-python` | — | Image processing |

### MCP (Optional)

| Package | Install Group | Purpose |
|---------|--------------|---------|
| `mcp` | `pip install .[mcp]` | Model Context Protocol server (crt-mcp) |

### Development

| Package | Install Group | Purpose |
|---------|--------------|---------|
| `pytest` | `pip install .[dev]` | Test runner |
| `pytest-asyncio` | `pip install .[dev]` | Async test support |
| `ruff` | `pip install .[dev]` | Linter |

---

## Internal Packages

### GroundCheck (`packages/groundcheck/`)

Vendored semantic verification library. Zero core dependencies (pure Python). Optional neural mode requires `sentence-transformers` and `transformers`.

Install: `pip install -e packages/groundcheck`

### Belief Classifier (`packages/belief_classifier/`)

XGBoost-based contradiction resolver. Requires `xgboost`, `scikit-learn`, `numpy`.

Install: `pip install -e packages/belief_classifier`

---

## Frontend Dependencies (npm)

### Runtime

| Package | Version | Purpose |
|---------|---------|---------|
| `react` | ^18.3.1 | UI framework |
| `react-dom` | ^18.3.1 | React DOM renderer |
| `react-router-dom` | ^6.30.3 | Client-side routing |
| `framer-motion` | ^11.0.0 | Animations (sidebar, transitions, orchestration UI) |
| `react-markdown` | ^10.1.0 | Markdown rendering (docs page, chat messages) |
| `remark-gfm` | ^4.0.1 | GitHub-flavored markdown (tables, strikethrough) |
| `@monaco-editor/react` | ^4.6.0 | Code editor component |
| `monaco-editor` | ^0.52.0 | Monaco editor core |
| `lucide-react` | ^0.563.0 | Icon library |

### Build & Dev

| Package | Version | Purpose |
|---------|---------|---------|
| `vite` | ^5.4.2 | Build tool and dev server |
| `@vitejs/plugin-react` | ^4.3.1 | React plugin for Vite |
| `typescript` | ^5.5.4 | Type checking |
| `tailwindcss` | ^3.4.10 | Utility-first CSS |
| `postcss` | ^8.4.38 | CSS processing |
| `autoprefixer` | ^10.4.19 | CSS vendor prefixes |

---

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `CRT_OLLAMA_MODEL` | Local model name (e.g. `qwen2.5-coder:14b`) |

### Optional — Cloud LLM

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key (enables GPT-4o Tier 1 fallback + side model tap) |
| `CLAUDE_SESSION_COOKIE` | Claude.ai session cookie (enables Claude Tier 2 fallback + cookie vision provider) |
| `ANTHROPIC_API_KEY` | Anthropic API key (alternative to session cookie for Claude vision) |

### Optional — Features

| Variable | Default | Description |
|----------|---------|-------------|
| `CRT_ENABLE_LLM` | `true` | Enable/disable LLM extraction |
| `CRT_SHARED_MEMORY` | `false` | All threads share one memory DB |
| `CRT_GROUNDCHECK_BRIDGE_BACKGROUND_ENABLED` | `false` | Background GroundCheck sync |

---

## Install Groups (Quick Reference)

```bash
# Minimal (API + memory + local LLM)
pip install -e .

# With cloud LLM support
pip install -e ".[llm]"

# With Telegram bot
pip install -e ".[channels]"

# Full ML/training stack
pip install -e ".[full]"

# Everything
pip install -e ".[llm,full,channels,mcp,dev]"

# Internal packages
pip install -e packages/groundcheck
pip install -e packages/belief_classifier

# Frontend
cd frontend && npm install
```

---

## Database Files (auto-created)

| File | Purpose |
|------|---------|
| `personal_agent/crt_memory_{thread}.db` | Per-thread memory store (SQLite) |
| `personal_agent/crt_ledger_{thread}.db` | Per-thread contradiction ledger (SQLite) |
| `data/commitments.db` | Commitment/reminder store |
| `data/skills_registry.db` | Installed skills registry |
| `personal_agent/action_receipts.db` | Action audit trail |
| `personal_agent/slot_discovery.db` | Learned slot type profiles |
| `personal_agent/intent_corrections.db` | Intent router corrections |
| `personal_agent/thread_sessions.db` | Thread session state + heartbeat config |

All databases use SQLite with WAL journal mode for concurrent read access.

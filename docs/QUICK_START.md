# Quick Start Guide

Get CRT/Aether running locally in about 10 minutes.

## Prerequisites

- **Python 3.11+** (3.13 tested)
- **Node.js 18+** (for the frontend)
- **Ollama** installed and running (for local LLM generation)
- A local Ollama model pulled (e.g., `ollama pull llama3.2:latest` or `ollama pull qwen2.5-coder:14b`)

## 1. Clone and Install Backend

```bash
git clone <repo-url> AI_round2
cd AI_round2

# Create virtual environment
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt
```

The `requirements.txt` includes: FastAPI, uvicorn, sentence-transformers, numpy, scikit-learn, xgboost, jsonschema, requests, beautifulsoup4, python-dotenv, and the vendored GroundCheck package.

## 2. Environment Variables

Create a `.env` file in the project root (or set these in your shell):

```bash
# Required: which Ollama model to use for generation
CRT_OLLAMA_MODEL=qwen2.5-coder:14b

# Optional: Cloud providers (leave unset for local-only mode)
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# Optional: Server binding
# CRT_HOST=127.0.0.1
# PORT=8000

# Optional: Shared memory across threads (default: false, each thread gets its own DB)
# CRT_SHARED_MEMORY=true
```

## 3. Runtime Config (Optional)

Copy or create `crt_runtime_config.json` in the project root to customize behavior. If this file doesn't exist, defaults are used. Key settings to consider:

```json
{
  "product_mode": {
    "mode": "local_only"
  },
  "generation_stack": {
    "local": {
      "enabled": true,
      "default_model": "qwen2.5-coder:14b"
    }
  },
  "greeting": {
    "enabled": true,
    "style": "time_based"
  },
  "onboarding": {
    "enabled": true,
    "auto_run_when_memory_empty": true
  }
}
```

## 4. Start the Backend

```bash
python crt_api.py
```

The FastAPI server starts on `http://127.0.0.1:8000` by default. You should see log output indicating:
- Runtime config loaded
- LLM client initialized (or lazy init on first request)
- Model router configured
- Routes registered

## 5. Install and Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server starts on `http://localhost:5173`.

## 6. Open the Browser

Navigate to `http://localhost:5173`. You should see the Aether chat interface.

## First Conversation Walkthrough

### Onboarding

If `onboarding.enabled` is true and the memory store is empty, Aether will ask you a series of setup questions:

1. **"What name should I call you?"** — Stored as `FACT: name = <your answer>`
2. **"What pronouns should I use?"** — Stored as fact (optional)
3. **"What's your job title/role?"** — Stored as fact (optional)
4. **"Who do you work for?"** — Stored as fact (optional)
5. **"Where are you located?"** — Stored as fact (optional)
6. **"How should I communicate?"** — Stored as preference
7. **"What are you hoping to use this assistant for?"** — Stored as preference

Each answer creates a memory with initial trust based on the source (user = 0.7).

### Testing Memory

After onboarding, try these:

```
You: What's my name?
```
Aether should recall what you told it, citing the stored memory.

```
You: Actually, my name is Alex now.
```
This triggers correction detection — the old name memory gets a trust penalty, a contradiction ledger entry is created, and the new name is stored with boosted confidence.

```
You: What's my name?
```
Should return "Alex" with the updated trust score.

### Testing Self-Awareness

```
You: How are you doing?
```
Triggers the self-referential path. If the heartbeat has run, Aether will ground its response in actual self-model data. If the self-model is empty (first run), it will honestly say so.

```
You: What are you uncertain about?
```
Reads the `uncertainty_domains` slot from the self-model and answers from evidence.

## Useful Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat/send` | POST | Synchronous chat |
| `/api/chat/stream` | POST | SSE streaming chat |
| `/api/memory/facts` | GET | List stored facts for a thread |
| `/api/memory/contradictions` | GET | List contradiction ledger entries |
| `/api/docs` | GET | List available documentation |
| `/api/docs/{id}` | GET | Get a specific doc as markdown |
| `/api/profile` | GET | Get user profile (stored facts) |
| `/api/heartbeat/config` | GET | Get heartbeat configuration |

## Frontend Routes

| Path | Description |
|------|-------------|
| `/` | Main chat interface |
| `/docs` | Documentation viewer (this page system) |
| `/dashboard` | System dashboard with memory stats |

## Troubleshooting

**"No LLM available"** — Make sure Ollama is running (`ollama serve`) and you have a model pulled (`ollama list`).

**CORS errors** — The default CORS origins include `localhost:5173` and `localhost:5174`. If your frontend runs on a different port, set `CRT_CORS_ORIGINS` to include it.

**Empty memory after restart** — By default, each thread gets its own SQLite database. Check that the `personal_agent/` directory exists and is writable. Enable `CRT_SHARED_MEMORY=true` if you want all threads to share one database.

**Slow first response** — The sentence-transformers model downloads on first use (~100MB). Subsequent startups are faster due to caching.

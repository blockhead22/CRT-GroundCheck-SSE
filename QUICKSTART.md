# Quickstart - CRT v0.9-beta
**Get running in 5 minutes**

---

## Why CRT?

**Most AI memory systems lie by omission.** They silently overwrite contradictory information, then confidently present uncertain facts as truth.

CRT is different: When the system has conflicting information, **you see it—always**. Contradicted memories are flagged in data and disclosed in language.

**→ Read [PURPOSE.md](PURPOSE.md) for the full "why this matters" explanation**

This guide shows you **how to run CRT**. The philosophy doc shows you **why it exists**.

---

## Prerequisites

### Required
- **Python 3.10+**
- **Ollama** (for natural language responses)
  - Download: https://ollama.com/download
  - Install model: `ollama pull llama3.2:latest`
  - Start server: `ollama serve`

### Optional
- **Node.js 18+** (for web UI only)

### System
- 2GB RAM minimum
- 5GB disk space (for Ollama model)

**Note:** Without Ollama running, API will return `[Ollama error: ...]` messages but memory storage, contradiction detection, and invariant flags still work.

---

## Option 1: Full Stack (Recommended)

### Step 0: Start Ollama (if not running)
```bash
# In a separate terminal
ollama serve

# Verify
ollama list  # Should show llama3.2:latest
```

### Step 1: Install Python Dependencies
```bash
cd d:\AI_round2
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux

pip install -r requirements.txt
```

### Step 2: Start API Server
```bash
# Terminal 1
python -m uvicorn crt_api:app --reload --host 127.0.0.1 --port 8123
```

Wait for: `INFO:     Uvicorn running on http://127.0.0.1:8123`

### Step 3: Start Web UI
```bash
# Terminal 2
cd frontend
npm install
npm run dev
```

Wait for: `Local:   http://localhost:5173/`

### Step 4: Open Browser
Navigate to: **http://localhost:5173**

You should see the CRT chat interface.

---

## Option 2: CLI Only (No Frontend)

### Step 1: Install + Run
```bash
cd d:\AI_round2
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python personal_agent_cli.py
```

### Step 2: Chat
```
You: My name is Alex
CRT: Thanks — noted: your name is Alex.

You: I work at DataCore
CRT: That's great to know, you work at DataCore.

You: What's my name?
CRT: Alex
```

Type `exit` to quit.

---

## Option 3: Streamlit GUI

### Step 1: Install + Run
```bash
cd d:\AI_round2
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

streamlit run crt_chat_gui.py
```

### Step 2: Browser Opens Automatically
If not, navigate to: **http://localhost:8501**

---

## Demo Script (Copy/Paste to Test)

Start a conversation and paste these lines one at a time:

```
My name is Jordan Chen.
I work as a data scientist at Vertex Analytics.
My favorite programming language is Rust.
I live in Austin, Texas.
I have a golden retriever named Murphy.
My current project is building a recommendation engine.
I graduated from MIT in 2018.
I prefer dark roast coffee.
My weekend hobby is rock climbing.
I'm reading 'Designing Data-Intensive Applications'.
```

Now introduce a contradiction:

```
Actually, my name is Alex Chen.
```

The system should detect this and either:
1. Ask for clarification, OR
2. Note the contradiction in its response

Check the contradiction ledger:

```
List all contradictions you've detected.
```

---

## Verify It's Working

### Test 1: Memory Persistence
1. Tell CRT: `My favorite color is blue`
2. Restart the API server (Ctrl+C, then restart)
3. Ask: `What's my favorite color?`
4. **Expected**: CRT remembers "blue"

### Test 2: Contradiction Detection
1. Tell CRT: `I live in Seattle`
2. Tell CRT: `I live in Portland`
3. Ask: `Where do I live?`
4. **Expected**: CRT mentions the contradiction or asks for clarification

### Test 3: API Access
```bash
# In a new terminal
curl "http://127.0.0.1:8123/api/chat/send" \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"test","message":"Hello"}'
```

**Expected**: JSON response with `"answer"` field

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'X'"
**Fix**: Make sure venv is activated and dependencies installed
```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

### "Address already in use" (port 8123 or 5173)
**Fix**: Kill existing process or use different port
```bash
# Windows
netstat -ano | findstr :8123
taskkill /PID <PID> /F

# Mac/Linux
lsof -ti:8123 | xargs kill -9
```

### Web UI shows "Failed to connect to API"
**Fix**: Make sure API server is running on port 8123
```bash
curl http://127.0.0.1:8123/api/chat/send
# Should return: {"detail":"Method Not Allowed"}  (that's fine, means server is up)
```

### "Database is locked"
**Fix**: Only one process can write to SQLite at a time
```bash
# Stop all CRT processes, then restart API server
```

---

## Configuration (Optional)

Create `.env` file in project root:

```bash
# .env
OPENAI_API_KEY=your-key-here
CRT_DB_PATH=./personal_agent/crt_memory.db
CRT_LEDGER_PATH=./personal_agent/crt_ledger.db
LOG_LEVEL=INFO
```

**Note**: Default LLM backend required. Check [README.md](README.md) for LLM setup.

---

## What to Try Next

1. **Stress Test**: `python tools/adaptive_stress_test.py my_test 40 60`
2. **View Memories**: Open web UI → Dashboard → Memories tab
3. **Check Contradictions**: `curl "http://127.0.0.1:8123/api/contradictions?thread_id=default"`
4. **Read Docs**: See [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) for beta issues

---

## Need Help?

- **Known issues**: [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)
- **Full docs**: [CRT_HOW_TO_USE.md](CRT_HOW_TO_USE.md)
- **Architecture**: [CRT_WHITEPAPER.md](CRT_WHITEPAPER.md)
- **Report bugs**: GitHub Issues

---

**Beta Status**: Core works, some rough edges. See [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) for details.

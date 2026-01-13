# CRT Chat GUI - Setup & Launch Guide

**Streamlit Chat Interface with Ollama Integration**

## Quick Start

### 1. Install Ollama

**macOS:**
```bash
brew install ollama
```

**Or download from:** https://ollama.ai

### 2. Start Ollama Server

```bash
ollama serve
```

Keep this running in a terminal.

### 3. Pull a Model

In another terminal:

```bash
# Recommended: Llama 3 (best balance)
ollama pull llama3

# OR other options:
ollama pull mistral    # Fast and good
ollama pull phi3       # Smaller, faster
ollama pull codellama  # Better for code
```

### 4. Launch CRT Chat GUI

```bash
streamlit run crt_chat_gui.py
```

Visit: http://localhost:8502 (or the port Streamlit shows)

### (Recommended) Launch Unified CRT App (Chat + Dashboard)

```bash
streamlit run crt_app.py
```

Then use the Streamlit sidebar page selector to open **Chat** or **Dashboard**.

---

## Features

### ✅ What Works Now:

**Real AI Integration:**
- 🤖 **Ollama LLM** - Real responses, not placeholders
- 🧠 **Semantic Embeddings** - sentence-transformers for meaning
- 💬 **Natural Conversation** - Chat with memory

**CRT Features:**
- 📊 **Trust-Weighted Retrieval** - Memories ranked by trust
- ⚠️ **Contradiction Detection** - Automatically spots conflicts
- 🔐 **Belief vs Speech** - Gates ensure coherent responses
- 📈 **Trust Evolution** - Memories gain/lose trust over time

**UI Features:**
- 🟢 **BELIEF Badge** - High-trust, gated response
- 🟠 **SPEECH Badge** - Fallback response
- 🔴 **CONTRADICTION Badge** - Conflict detected
- 📊 **Metadata Panel** - See trust, gates, retrieved memories
- ⭐ **Importance Marking** - Flag important memories
- 🗑️ **Clear Chat** - Start fresh
- 🔄 **Model Switching** - Change Ollama models on the fly

---

## UI Guide

### Main Chat Area

**Chat with CRT:**
- Type in the input box at the bottom
- Check "⭐ Important" to mark memories as significant
- Responses show with color-coded badges

**Badges:**
- 🟢 **BELIEF** = Response from trusted memory, gates passed
- 🟠 **SPEECH** = Fallback response, gates failed
- 🔴 **CONTRADICTION** = New info contradicts existing memory

### Sidebar

**LLM Settings:**
- Switch between Ollama models
- Model changes take effect immediately

**Display Options:**
- Toggle metadata visibility
- Shows trust scores, gates, contradictions

**System Status:**
- Live stats: memory count, contradictions, belief ratio

**Actions:**
- Clear chat history
- Restart CRT system

### Metadata Panel

Click "📊 CRT Metadata" under any response to see:

**Confidence:** How certain the AI is  
**Mode:** quick/thinking/deep reasoning  
**Gates:** Intent & memory alignment checks  
**Contradiction:** If detected, shows drift score  
**Retrieved Memories:** What memories were used  

---

## Example Conversations

### Basic Memory Building

```
You: My favorite color is blue
CRT: Got it! I'll remember that your favorite color is blue.
[🟢 BELIEF] - Stored with high confidence

You: What's my favorite color?
CRT: Your favorite color is blue.
[🟢 BELIEF] - Retrieved from trusted memory
```

### Contradiction Detection

```
You: I work at TechCorp
CRT: I'll remember that you work at TechCorp.
[🟢 BELIEF]

You: I work at StartupXYZ now
CRT: I notice you previously mentioned working at TechCorp. 
     I'll record this new information about StartupXYZ.
[🔴 CONTRADICTION] - Drift: 0.67
```

### Belief vs Speech

```
You: What's the weather like today?
CRT: I don't have real-time weather information, but I can 
     help you with that if you share your location.
[🟠 SPEECH] - Fallback, no relevant memories

You: I prefer working in the morning
CRT: I'll remember that you prefer working in the morning.
[🟢 BELIEF] - High confidence, stored
```

---

## Troubleshooting

### "Failed to initialize: connection refused"

**Problem:** Ollama server not running

**Solution:**
```bash
# Start Ollama in a terminal
ollama serve
```

### "Model 'llama3' not found"

**Problem:** Model not downloaded

**Solution:**
```bash
ollama pull llama3
```

### "Embedding model loading..."

**Problem:** First run downloads ~80MB model

**Solution:** Wait for download to complete (happens once)

### Slow responses

**Possible causes:**
- Large model on CPU (no GPU)
- Low RAM

**Solutions:**
- Use smaller model: `phi3` instead of `llama3`
- Close other apps to free RAM
- Use GPU if available (Ollama auto-detects)

### Chat not updating

**Problem:** Session state issue

**Solution:** Click "🔄 Restart System" in sidebar

---

## Model Comparison

| Model | Size | Speed | Quality | Best For |
|-------|------|-------|---------|----------|
| **llama3** | 8B | Medium | High | Recommended - best balance |
| **mistral** | 7B | Fast | Good | Quick responses |
| **phi3** | 3.8B | Very Fast | Decent | Low-resource systems |
| **codellama** | 7B | Medium | High | Code-heavy conversations |
| **llama2** | 7B | Medium | Good | General use |

**Recommendation:** Start with `llama3`, switch to `phi3` if too slow.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│           Streamlit Chat GUI                │
│  (crt_chat_gui.py)                         │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│          CRT RAG Engine                     │
│  • Trust-weighted retrieval                 │
│  • Contradiction detection                  │
│  • Belief vs speech gates                   │
└──────────────┬──────────────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
┌──────────────┐ ┌──────────────┐
│ Ollama LLM   │ │ Embeddings   │
│ (llama3)     │ │ (sentence-   │
│              │ │ transformers)│
└──────────────┘ └──────────────┘
       │               │
       └───────┬───────┘
               ▼
     ┌──────────────────┐
     │   SQLite DBs     │
     │ • crt_memory.db  │
     │ • crt_ledger.db  │
     └──────────────────┘
```

---

## Performance Tips

### Fast Startup

```python
# Pre-download embedding model
from sentence_transformers import SentenceTransformer
SentenceTransformer('all-MiniLM-L6-v2')
```

### Memory Usage

- **Ollama:** ~4-8GB RAM (depending on model)
- **Embeddings:** ~500MB RAM
- **Streamlit:** ~200MB RAM

**Total:** ~5-9GB RAM recommended

### GPU Acceleration

Ollama automatically uses GPU if available:
- **Apple Silicon:** Uses Metal (M1/M2/M3)
- **NVIDIA:** Uses CUDA
- **AMD:** Uses ROCm

No configuration needed!

---

## Next Steps

### Enhance Memory

**Store important facts:**
```
You: !important My birthday is March 15th
CRT: [🟢 BELIEF] - Stored as important memory
```

### View System Health

Check sidebar for:
- Memory count
- Open contradictions  
- Belief ratio

### Explore Dashboard

Run both simultaneously:
```bash
# Terminal 1: Chat GUI
streamlit run crt_chat_gui.py

# Terminal 2: Dashboard
streamlit run crt_dashboard.py --server.port 8501
```

- **Chat:** http://localhost:8502
- **Dashboard:** http://localhost:8501

---

## Advanced: Custom Models

### Use Different Ollama Models

```bash
# Pull specialized models
ollama pull deepseek-coder  # For coding
ollama pull solar           # High quality
ollama pull orca-mini       # Fast, small
```

Select in sidebar dropdown.

### Fine-tuned Models

If you have a custom GGUF model:
```bash
ollama create mymodel -f Modelfile
```

Then select `mymodel` in the GUI.

---

## Files Created

```
crt_chat_gui.py              - Streamlit chat interface
personal_agent/
├── embeddings.py            - Real semantic embeddings
├── ollama_client.py         - Ollama integration
└── reasoning.py             - Updated with Ollama
```

---

## Support

**Issues?**

1. Check Ollama is running: `ollama serve`
2. Verify model installed: `ollama list`
3. Restart CRT: Click "🔄 Restart System"
4. Check terminal for errors

**Common Error Messages:**

- `connection refused` → Start Ollama
- `model not found` → Run `ollama pull llama3`
- `out of memory` → Use smaller model (phi3)

---

**Ready to chat!** 🚀

Launch with: `streamlit run crt_chat_gui.py`

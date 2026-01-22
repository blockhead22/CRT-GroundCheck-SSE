# CRT Integration Quickstart

**Get contradiction tracking running in 5 minutes**

---

## Prerequisites

- **Python 3.10+**
- **Ollama** (for natural language responses)
  ```bash
  # Install from: https://ollama.com/download
  ollama pull llama3.2:latest
  ollama serve
  ```
- **Node.js 18+** (for web UI, optional)

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/blockhead22/AI_round2.git
cd AI_round2
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the CRT API Server

```bash
python crt_api.py
```

The API will start on `http://127.0.0.1:8123`

### 4. Start the Frontend (Optional)

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:5173`

---

## Quick Test

### Using cURL

```bash
# Send a message
curl -X POST http://127.0.0.1:8123/chat \
  -H "Content-Type: application/json" \
  -d '{
    "threadId": "test-thread",
    "message": "I work at Microsoft",
    "history": []
  }'

# Create a contradiction
curl -X POST http://127.0.0.1:8123/chat \
  -H "Content-Type: application/json" \
  -d '{
    "threadId": "test-thread",
    "message": "I work at Amazon now",
    "history": []
  }'

# Ask a question
curl -X POST http://127.0.0.1:8123/chat \
  -H "Content-Type: application/json" \
  -d '{
    "threadId": "test-thread",
    "message": "Where do I work?",
    "history": []
  }'
```

### Using Python

```python
import requests

API_BASE = "http://127.0.0.1:8123"

def send_message(thread_id, message):
    response = requests.post(
        f"{API_BASE}/chat",
        json={
            "threadId": thread_id,
            "message": message,
            "history": []
        }
    )
    return response.json()

# Create facts
result1 = send_message("test-thread", "I work at Microsoft")
print(result1["answer"])

# Create contradiction
result2 = send_message("test-thread", "I work at Amazon now")
print(result2["answer"])

# Check disclosure
result3 = send_message("test-thread", "Where do I work?")
print(result3["answer"])
# Expected: "You work at Amazon (changed from Microsoft)"
```

---

## API Response Format

```json
{
  "answer": "You work at Amazon (changed from Microsoft).",
  "response_type": "disclosure",
  "gates_passed": true,
  "gate_reason": null,
  "session_id": "session-123",
  "metadata": {
    "confidence": 0.85,
    "intent_alignment": 0.9,
    "memory_alignment": 0.95,
    "contradiction_detected": true,
    "unresolved_contradictions_total": 1,
    "retrieved_memories": [
      {
        "memory_id": "m1",
        "text": "User works at Microsoft",
        "trust": 0.6,
        "timestamp": 1234567890
      },
      {
        "memory_id": "m2",
        "text": "User works at Amazon",
        "trust": 0.9,
        "timestamp": 1234567900
      }
    ]
  }
}
```

---

## Key Fields Explained

- **`answer`**: The AI response with disclosure (if needed)
- **`response_type`**: One of:
  - `"speech"` - Normal response
  - `"disclosure"` - Contradiction disclosed
  - `"ask_user"` - Clarification needed
  - `"refusal"` - Cannot answer
- **`gates_passed`**: Whether CRT verification passed
- **`metadata.contradiction_detected`**: True if contradiction found
- **`metadata.retrieved_memories`**: Memories used in response

---

## Next Steps

1. **Add to your chatbot**: See [Custom RAG Integration](./custom_rag_integration.md)
2. **Use with LangChain**: See [LangChain Integration](./langchain_integration.md)
3. **Use with LlamaIndex**: See [LlamaIndex Integration](./llamaindex_integration.md)
4. **Deploy to production**: See [Deployment Guide](../deployment_guide.md)

---

## Troubleshooting

### API Server Won't Start

**Problem:** Port 8123 already in use

**Solution:**
```bash
# Kill existing process
lsof -ti:8123 | xargs kill -9

# Or change port
export CRT_API_PORT=8124
python crt_api.py
```

### Ollama Connection Error

**Problem:** Cannot connect to Ollama

**Solution:**
```bash
# Start Ollama
ollama serve

# Verify it's running
curl http://localhost:11434/api/tags
```

### No Contradictions Detected

**Problem:** CRT not detecting obvious contradictions

**Solution:**
- Check that facts use exact slot patterns (e.g., "I work at X", "My employer is X")
- View contradiction ledger: `curl http://127.0.0.1:8123/contradictions/open?threadId=test-thread`
- Enable debug mode: `export DEBUG=1` and restart API

---

## Support

- **Documentation**: [docs/](../)
- **Examples**: [examples/](../../examples/)
- **Issues**: [GitHub Issues](https://github.com/blockhead22/AI_round2/issues)

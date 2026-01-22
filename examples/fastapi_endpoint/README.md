# FastAPI Endpoint with CRT Integration

This example demonstrates how to create a FastAPI-based chatbot API with CRT (Contradiction Resolution & Trust) integration.

## Features

- ✅ RESTful API for chatbot interactions
- ✅ CRT contradiction tracking and disclosure
- ✅ CORS enabled for frontend integration
- ✅ Automatic API documentation (Swagger/OpenAPI)
- ✅ Health checks and error handling
- ✅ Type-safe request/response models

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start CRT API Server

In the repository root:

```bash
python crt_api.py
```

The CRT API will start on `http://127.0.0.1:8123`

### 3. Start FastAPI Server

```bash
python main.py
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### POST /chat

Send a message and get a response with CRT verification.

**Request:**
```json
{
  "thread_id": "user-123",
  "message": "Where do I work?",
  "history": []
}
```

**Response:**
```json
{
  "answer": "You work at Amazon (changed from Microsoft).",
  "response_type": "disclosure",
  "contradiction_detected": true,
  "contradictions": [
    {
      "slot": "employer",
      "old_value": "Microsoft",
      "new_value": "Amazon"
    }
  ],
  "retrieved_memories": [...],
  "session_id": "session-123"
}
```

### GET /contradictions/{thread_id}

Get contradiction ledger for a thread.

**Example:**
```bash
curl http://localhost:8000/contradictions/user-123?status=open
```

### GET /memories/{thread_id}

Get memories for a thread.

**Example:**
```bash
curl http://localhost:8000/memories/user-123?limit=50&min_trust=0.75
```

### GET /profile/{thread_id}

Get user profile slots for a thread.

**Example:**
```bash
curl http://localhost:8000/profile/user-123
```

### GET /health

Check API and CRT server health.

**Response:**
```json
{
  "status": "healthy",
  "crt_connected": true,
  "timestamp": "2026-01-22T12:00:00"
}
```

## Testing

### Using cURL

```bash
# Create a fact
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test-123",
    "message": "I work at Microsoft",
    "history": []
  }'

# Create a contradiction
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test-123",
    "message": "I work at Amazon now",
    "history": []
  }'

# Ask a question (should get disclosure)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test-123",
    "message": "Where do I work?",
    "history": []
  }'
```

### Using Python

```python
import requests

API_URL = "http://localhost:8000"

def send_message(thread_id, message):
    response = requests.post(
        f"{API_URL}/chat",
        json={
            "thread_id": thread_id,
            "message": message,
            "history": []
        }
    )
    return response.json()

# Test
result = send_message("test-123", "Where do I work?")
print(result["answer"])
print(f"Contradiction detected: {result['contradiction_detected']}")
```

### Using the Interactive Docs

1. Open http://localhost:8000/docs
2. Click on any endpoint
3. Click "Try it out"
4. Fill in the parameters
5. Click "Execute"

## Deployment

### Docker

Create a `Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
docker build -t crt-api .
docker run -p 8000:8000 crt-api
```

### Production Settings

For production, update `main.py`:

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable in production
        workers=4,     # Multiple workers for concurrency
        log_level="info",
        access_log=True
    )
```

## Frontend Integration

This API is designed to work with any frontend. Example with React:

```typescript
async function sendMessage(threadId: string, message: string) {
  const response = await fetch('http://localhost:8000/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: threadId,
      message: message,
      history: []
    })
  })
  
  const data = await response.json()
  
  if (data.contradiction_detected) {
    console.log('⚠️ Contradiction detected!')
    console.log(data.contradictions)
  }
  
  return data.answer
}
```

## Configuration

### Environment Variables

```bash
# CRT API URL (default: http://127.0.0.1:8123)
export CRT_API_URL=http://localhost:8123

# API Port (default: 8000)
export API_PORT=8000

# CORS Origins (default: *)
export CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### Custom Settings

Modify `main.py`:

```python
# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Specific methods
    allow_headers=["*"],
)

# API Configuration
CRT_API_URL = os.getenv("CRT_API_URL", "http://127.0.0.1:8123")
```

## Troubleshooting

### CRT Service Unavailable

**Error:** `503 CRT service unavailable`

**Solution:**
1. Check CRT API is running: `curl http://127.0.0.1:8123/health`
2. Verify `CRT_API_URL` environment variable
3. Check firewall/network settings

### CORS Errors

**Error:** CORS policy blocking requests

**Solution:** Update `allow_origins` in CORS middleware to include your frontend URL.

### Timeout Errors

**Error:** Request timeout

**Solution:** Increase timeout in API calls:
```python
response = requests.post(..., timeout=60)  # 60 seconds
```

## Next Steps

- Add authentication/authorization
- Implement rate limiting
- Add request logging
- Set up monitoring (Prometheus, Grafana)
- Add caching (Redis)
- Deploy to cloud (AWS, GCP, Azure)

## License

MIT

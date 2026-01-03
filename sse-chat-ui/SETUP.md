# SSE Chat UI - Setup and Configuration Guide

## Quick Start

### Minimum Setup (5 minutes)

1. **Backend**
```bash
cd sse-chat-ui
pip install -r requirements.txt
python app.py
```

2. **Frontend** (new terminal)
```bash
cd sse-chat-ui
npm install
npm start
```

3. **Access**
- Frontend: http://localhost:3000
- Backend API: http://localhost:5000

## Detailed Setup

### Prerequisites

Ensure you have installed:
- Python 3.9+ (`python --version`)
- Node.js 16+ (`node --version`)
- npm 8+ (`npm --version`)

### Backend Setup

#### Step 1: Create Virtual Environment
```bash
python -m venv venv
```

On Windows:
```bash
venv\Scripts\activate
```

On macOS/Linux:
```bash
source venv/bin/activate
```

#### Step 2: Install Python Dependencies
```bash
pip install -r requirements.txt
```

**Note**: First install may take 5-10 minutes due to torch and transformers.

#### Step 3: Configure Environment
Create `.env` file in project root:
```bash
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///sse_chat.db
DEBUG=True
```

#### Step 4: Run Backend
```bash
python app.py
```

Expected output:
```
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://0.0.0.0:5000
```

### Frontend Setup

#### Step 1: Install Dependencies
```bash
npm install
```

This installs:
- React 18.2
- Socket.io-client 4.5
- React Scripts 5.0

#### Step 2: Configure Environment
Create `.env` file in frontend root:
```bash
REACT_APP_API_URL=http://localhost:5000
```

#### Step 3: Run Frontend
```bash
npm start
```

Expected output:
```
Compiled successfully!

You can now view sse-chat-ui in the browser.

  Local:            http://localhost:3000
  On Your Network:  http://192.168.x.x:3000
```

### Verify Setup

1. **Frontend loads**: http://localhost:3000
2. **Can register**: Username/password form works
3. **Can login**: After registration
4. **Can chat**: Send test message
5. **SSE analysis**: See claims extracted

## Docker Setup

### Build and Run

```bash
# Build images
docker-compose build

# Run containers
docker-compose up

# Access
# Frontend: http://localhost:3000
# Backend: http://localhost:5000

# Stop
docker-compose down
```

### Troubleshooting Docker

**Port already in use**
```bash
docker-compose down
# Or specify different ports
docker-compose up -p 8000:5000 -p 3001:3000
```

**Memory issues**
```bash
# Allocate more RAM to Docker
docker-compose down
# Increase Docker memory limit in settings
docker-compose up
```

## Configuration Options

### Backend Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| FLASK_ENV | development | Environment mode |
| SECRET_KEY | dev-key | Session encryption |
| DATABASE_URL | sqlite:///sse_chat.db | Database location |
| DEBUG | True | Debug mode |
| PORT | 5000 | Server port |

### Frontend Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| REACT_APP_API_URL | http://localhost:5000 | Backend URL |
| REACT_APP_ENV | development | Environment |

### SSE Configuration

These are set in `app.py`:

```python
# Embedding model
embedding_model = "all-MiniLM-L6-v2"  # or "all-mpnet-base-v2"

# Chunking
max_chunk_size = 200
chunk_overlap = 50

# Contradiction detection
use_ollama = False  # Set True to use local LLM
ollama_model = "mistral"  # if use_ollama=True

# Deduplication threshold
similarity_threshold = 0.85
```

## Database Management

### Initialize Database
Database automatically initializes on first run. Schema includes:
- users
- conversations  
- messages
- claims
- contradictions
- context_memory

### View Database

Using SQLite CLI:
```bash
sqlite3 sse_chat.db
sqlite> .tables
sqlite> SELECT COUNT(*) FROM messages;
sqlite> .quit
```

Using Python:
```python
import sqlite3
conn = sqlite3.connect('sse_chat.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM users LIMIT 5")
print(cursor.fetchall())
```

### Reset Database
```bash
rm sse_chat.db
# Restart app - will recreate schema
```

### Backup Database
```bash
cp sse_chat.db sse_chat.db.backup
```

## Common Issues and Solutions

### Issue: "ModuleNotFoundError: No module named 'sse'"

**Solution**: Ensure SSE directory is in Python path:
```python
# In app.py
sys.path.insert(0, str(Path(__file__).parent.parent / "AI_round2"))
```

### Issue: "Port 5000 already in use"

**Solution**: Kill process using port
```bash
# macOS/Linux
lsof -i :5000
kill -9 <PID>

# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

### Issue: "Frontend can't connect to backend"

**Solution**: Check CORS configuration
```python
# In app.py
CORS(app, resources={r"/api/*": {"origins": "*"}})
```

### Issue: "Slow message processing"

**Solutions**:
1. Use lighter embedding model: `all-MiniLM-L6-v2` (default)
2. Batch messages together
3. Increase chunk size in SSE analyzer
4. Use Ollama for local inference

### Issue: "Database locked"

**Solution**: Close other connections
```bash
# Check for processes
ps aux | grep python
# Kill if needed
kill -9 <PID>
```

## Performance Tuning

### Backend Optimization

```python
# In app.py SSEAnalyzer class

# 1. Increase chunk size (faster, less precise)
chunks = chunk_text(text, max_chars=500)  # Default: 200

# 2. Skip ambiguity analysis if not needed
# claims = extract_claims_from_chunks(...)
# # Comment out ambiguity analysis

# 3. Cache embeddings
embedding_cache = {}
if text in embedding_cache:
    embeddings = embedding_cache[text]
```

### Frontend Optimization

```javascript
// In App.jsx

// 1. Lazy load message history
useEffect(() => {
  if (messages.length > 100) {
    // Show only last 50 + load more button
  }
}, [messages])

// 2. Debounce socket events
const debounceEmit = (event, data, delay = 300) => {
  clearTimeout(emitTimeout);
  emitTimeout = setTimeout(() => socket.emit(event, data), delay);
}

// 3. Virtual scrolling for long conversations
import { FixedSizeList } from 'react-window';
```

## Advanced Configuration

### Using PostgreSQL Instead of SQLite

1. Install PostgreSQL
2. Update requirements.txt:
```
psycopg2-binary==2.9.0
```

3. Update app.py:
```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:password@localhost/sse_chat'
```

### Using Ollama for Local LLM

1. Install Ollama: https://ollama.ai
2. Run model: `ollama run mistral`
3. Update SSE analyzer:
```python
from sse.ollama_utils import get_ollama_client

sse_analyzer.use_ollama = True
sse_analyzer.ollama_client = get_ollama_client()
```

### Enabling HTTPS

```python
# In app.py
from flask_talisman import Talisman

Talisman(app)

# Or with custom certificate
socketio.run(
    app,
    ssl_context=('path/to/cert.crt', 'path/to/key.key')
)
```

## Monitoring and Logging

### Backend Logging

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Message sent")
logger.error("Connection failed")
```

### Frontend Logging

```javascript
// In App.jsx
const enableDebug = process.env.REACT_APP_DEBUG === 'true';

const debug = (msg, data) => {
  if (enableDebug) {
    console.log(`[DEBUG] ${msg}`, data);
  }
};
```

### Monitoring Metrics

Track in database:
- Messages per hour
- Average response time
- Claims per message
- Contradiction detection rate
- User engagement

## Testing

### Manual Testing Checklist

- [ ] Backend API health check: `curl http://localhost:5000/api/health`
- [ ] User registration works
- [ ] User login works
- [ ] Create conversation works
- [ ] Send message works
- [ ] Receive message works
- [ ] SSE analysis visible
- [ ] Claims extracted correctly
- [ ] Contradictions detected
- [ ] Messages persist after refresh

### Automated Testing

```bash
# Backend tests
pytest tests/

# Frontend tests
npm test

# Integration tests
pytest tests/integration/
```

## Production Deployment

### Pre-deployment Checklist

- [ ] Change SECRET_KEY to secure random value
- [ ] Set FLASK_ENV=production
- [ ] Configure production database
- [ ] Set up HTTPS/TLS
- [ ] Configure CORS properly
- [ ] Set resource limits
- [ ] Configure logging
- [ ] Set up monitoring
- [ ] Test with production data
- [ ] Set up backups

### Deployment Commands

```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Run production containers
docker-compose -f docker-compose.prod.yml up -d

# Check logs
docker-compose logs -f

# Scale services
docker-compose up -d --scale backend=3
```

## Next Steps

1. **Customize AI responses** in `generate_ai_response()` function
2. **Add LLM integration** using Ollama or OpenAI API
3. **Extend SSE analysis** with additional modules
4. **Add user features** like preferences, themes, etc.
5. **Deploy to production** using Docker/Kubernetes

## Support Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [React Documentation](https://react.dev/)
- [Socket.io Documentation](https://socket.io/docs/)
- [SSE Documentation](../AI_round2/README.md)

---

**Estimated setup time**: 10-15 minutes for first-time setup

**For issues**: Check logs first, then consult troubleshooting section

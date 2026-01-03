# SSE Chat UI - Quick Reference

## Start Application (5 minutes)

```bash
# Terminal 1: Backend
cd sse-chat-ui
pip install -r requirements.txt
python app.py

# Terminal 2: Frontend (new terminal)
cd sse-chat-ui
npm install
npm start
```

**Access**: http://localhost:3000

## Project Structure
```
sse-chat-ui/
├── app.py                          # Flask backend (750+ lines)
├── memory.py                        # Memory system (400+ lines)
├── src/
│   ├── App.jsx                     # React component (400+ lines)
│   └── App.css                     # Styling (400+ lines)
├── public/index.html               # HTML entry point
├── requirements.txt                # Python deps
├── package.json                    # Node deps
├── docker-compose.yml              # Docker setup
├── README.md                       # Feature overview
├── SETUP.md                        # Detailed setup
├── IMPLEMENTATION_GUIDE.md         # This document
└── .gitignore                      # Version control
```

## Key Features

**Frontend** ✨
- Modern chat UI with sidebar
- Real-time message updates
- SSE analysis display
- User authentication
- Conversation management
- Responsive design

**Backend** 🧠
- REST API (7 endpoints)
- WebSocket support
- User authentication
- SSE claim extraction
- Contradiction detection
- Persistent memory

**Database** 💾
- SQLite with 6 tables
- Chat history
- Claims & contradictions
- Context memory
- User accounts

**Memory System** 🔄
- MemoryManager (persistence)
- ContextAnalyzer (context)
- ConversationSummarizer (summaries)
- RelevanceScoringEngine (ranking)

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | /api/auth/register | Register user |
| POST | /api/auth/login | Login user |
| GET | /api/conversations | List conversations |
| POST | /api/conversations | Create conversation |
| GET | /api/conversations/<id>/messages | Get messages |
| POST | /api/analyze | Analyze text |
| GET | /api/health | Health check |

## WebSocket Events

| Event | Direction | Purpose |
|-------|-----------|---------|
| connect | ← | Client connects |
| disconnect | ← | Client disconnects |
| join_conversation | → | Join room |
| send_message | → | Send message |
| message_received | ← | Receive message |

## Database Tables

| Table | Purpose |
|-------|---------|
| users | User accounts |
| conversations | Chat sessions |
| messages | Messages |
| claims | Extracted claims |
| contradictions | Detected contradictions |
| context_memory | Persistent memory |

## Environment Variables

**Backend** (.env):
```
FLASK_ENV=development
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///sse_chat.db
DEBUG=True
```

**Frontend** (.env):
```
REACT_APP_API_URL=http://localhost:5000
```

## Common Commands

```bash
# Backend
python app.py                  # Start backend
pip install -r requirements.txt # Install deps

# Frontend
npm start                      # Start dev server
npm build                      # Build for production
npm test                       # Run tests

# Docker
docker-compose up              # Start both services
docker-compose down            # Stop services
docker-compose logs -f         # View logs

# Database
sqlite3 sse_chat.db           # Open database
.tables                        # List tables
SELECT COUNT(*) FROM messages; # Query messages
```

## Usage Flow

1. **Register/Login**
   - Click Register button
   - Enter username/password
   - Login with credentials

2. **Create Conversation**
   - Click "New Chat" button
   - Conversation appears in sidebar

3. **Send Message**
   - Type in input box
   - Press Send button
   - Message appears with analysis

4. **View Analysis**
   - Click "Analysis" dropdown
   - See claims extracted
   - See contradictions found

## File Locations

| File | Lines | Purpose |
|------|-------|---------|
| app.py | 750+ | Main Flask app |
| memory.py | 400+ | Memory management |
| App.jsx | 400+ | React component |
| App.css | 400+ | Styling |
| README.md | 300+ | Features |
| SETUP.md | 400+ | Setup guide |

## Extending

### Add API Endpoint
```python
@app.route('/api/new', methods=['GET'])
def new_endpoint():
    return jsonify({'data': 'value'}), 200
```

### Add WebSocket Event
```python
@socketio.on('event_name')
def handle_event(data):
    emit('response', {'result': 'value'})
```

### Add Database Table
```python
cursor.execute('''
    CREATE TABLE IF NOT EXISTS new_table (
        id TEXT PRIMARY KEY,
        data TEXT
    )
''')
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Port in use | Kill process on port 5000/3000 |
| Can't import SSE | Ensure SSE in parent directory |
| Frontend can't connect | Check REACT_APP_API_URL |
| Database locked | Restart backend |
| Slow performance | Increase chunk size or use lighter model |

## Performance Tips

- Use all-MiniLM-L6-v2 (lightweight embedding model)
- Batch multiple messages
- Cache embeddings
- Increase max_chunk_size
- Use PostgreSQL in production
- Add database indices

## Deployment

### Docker
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Cloud
- Heroku: Use Procfile
- AWS: ALB + ECS + RDS
- Azure: App Service + SQL Database
- GCP: Cloud Run + Firestore

## Production Checklist

- [ ] Change SECRET_KEY
- [ ] Use PostgreSQL
- [ ] Enable HTTPS
- [ ] Set DEBUG=False
- [ ] Configure logging
- [ ] Set up monitoring
- [ ] Configure backups
- [ ] Test thoroughly

## Tech Stack

```
Frontend:
  React 18.2.0
  Socket.io-client 4.5.4
  CSS3

Backend:
  Flask 2.3.3
  Flask-SocketIO 5.3.4
  SQLite3

AI/ML:
  Sentence Transformers
  Scikit-learn
  NumPy
```

## Support Resources

| Resource | Link |
|----------|------|
| Flask Docs | https://flask.palletsprojects.com/ |
| React Docs | https://react.dev/ |
| Socket.io | https://socket.io/docs/ |
| SSE Repo | ../AI_round2/ |

## Key Statistics

| Metric | Value |
|--------|-------|
| Lines of Code | ~2000 |
| Lines of Docs | ~1500 |
| Python Files | 2 |
| JavaScript Files | 2 |
| Database Tables | 6 |
| API Endpoints | 7 |
| WebSocket Events | 5 |
| Setup Time | 5-15 min |

## Next Steps

1. ✅ Start application
2. ✅ Register & login
3. ✅ Create conversation
4. ✅ Send test messages
5. ✅ View SSE analysis
6. → Customize AI responses
7. → Add LLM integration
8. → Deploy to production

---

**Ready to chat?** http://localhost:3000

**Need help?** See SETUP.md or IMPLEMENTATION_GUIDE.md

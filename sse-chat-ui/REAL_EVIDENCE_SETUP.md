# Running the Real Evidence Chat

This wires everything together: Python evidence API + Express proxy + React UI.

## Requirements

You need to have already run the fixture setup that created the index:

```bash
cd sse-chat-ui
python ../sse/multi_doc.py build --input ../fixtures/*.txt --output ../output_index
```

This creates the index that the evidence API will use.

## Architecture

```
User Query
    ↓
[React Chat UI] (localhost:3000)
    ↓ /api/chat
[Express Server] (localhost:3000)
    ↓ calls
[Python Evidence API] (localhost:5000)
    ↓ calls
[SearchAdapter + EvidencePacket] 
    ↓
Real evidence (claims + contradictions + topology)
```

## Start Everything

**Terminal 1: Python Evidence API**
```bash
cd sse-chat-ui
python evidence_api.py
```
Should print:
```
🚀 Evidence API Server
   Running on http://localhost:5000
   POST /api/search - Search for evidence
```

**Terminal 2: Build & Start Express**
```bash
cd sse-chat-ui
npm run build
npm start
```
Should print:
```
🚀 Chat Server running at http://localhost:3000
```

Then open **http://localhost:3000** in browser.

## What You'll See

1. **Type a question** → "What is capitalism?"
2. **Express calls Python API** → Python searches index
3. **Python returns EvidencePacket** → Contains real claims + contradictions
4. **React displays**:
   - Chat bubble: "Here's the evidence for: 'What is capitalism?'"
   - SearchResults panel: Claims with contradiction graph
   - Topology indicators: contradiction count, cluster membership

## Troubleshooting

**Port 5000 in use?**
```bash
# Change in evidence_api.py
app.run(host='localhost', port=5001, ...)
# And update server.js fetch to http://localhost:5001
```

**No index found?**
```bash
# Build the index first
cd ..
python sse/multi_doc.py build --input fixtures/*.txt --output output_index
```

**Python API errors?**
Check that Flask is installed:
```bash
pip install flask
```

## Next Steps

1. Test with questions that match your fixture data
2. Customize the neutral response text in `server.js` line ~50
3. Later: Add optional LLM "commentary" layer (outside packet)

This is the clean architecture - Python = source of truth, Node = dumb proxy, React = structure display.

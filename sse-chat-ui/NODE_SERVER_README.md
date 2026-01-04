# SSE Chat - Node/Express Server Quick Start

## Installation & Running

### 1. Install Dependencies
```bash
cd sse-chat-ui
npm install
```

### 2. Development (Two terminals)

**Terminal 1 - Frontend (Webpack Dev Server)**
```bash
npm run dev
```
Opens on `http://localhost:3001` with hot reload.

**Terminal 2 - Backend (Express Server)**
```bash
npm run server:dev
```
Runs on `http://localhost:3000` with auto-reload.

### 3. Production
```bash
npm run build
npm start
```
Single server on `http://localhost:3000`.

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat` | POST | Send message: `{"message": "..."}` |
| `/api/chat/history` | GET | Get all messages |
| `/api/chat/history` | DELETE | Clear chat history |
| `/api/health` | GET | Health check |

---

## What's Inside

✅ **Express Backend** - Node.js server with chat API  
✅ **React Frontend** - ChatGPT-style UI  
✅ **Framer Motion** - Smooth animations  
✅ **Tailwind CSS** - Dark theme styling  
✅ **Webpack** - Module bundling & hot reload  

---

## File Structure

```
sse-chat-ui/
├── server.js              # Express backend
├── webpack.config.js      # Webpack bundling
├── package.json           # Dependencies
├── tailwind.config.js     # Tailwind config
├── public/index.html      # HTML entry
├── src/
│   ├── App.jsx           # Main chat component
│   ├── index.jsx         # React entry point
│   ├── index.css         # Global styles
│   └── components/
│       ├── ChatMessage.jsx
│       ├── ChatInput.jsx
│       ├── TypingIndicator.jsx
│       └── Header.jsx
└── dist/                 # Built bundle (production)
```

See [SETUP.md](SETUP.md) (old Flask backend docs) for full details.

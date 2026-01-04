import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import cors from 'cors';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Serve static files from dist (built by Webpack)
app.use(express.static(path.join(__dirname, 'dist')));

// Chat history (in-memory for demo)
let chatHistory = [];
const MAX_HISTORY = 50;

// Routes

/**
 * Health check
 */
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

/**
 * Chat endpoint
 * POST /api/chat
 * Body: { message: string }
 * Returns: { id, message, response, timestamp }
 */
app.post('/api/chat', (req, res) => {
  try {
    const { message } = req.body;

    if (!message || typeof message !== 'string') {
      return res.status(400).json({ error: 'Message required' });
    }

    const userMessage = message.trim().substring(0, 2000);
    const messageId = `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // Simulate thinking time (in real app, would call LLM or RAG adapter)
    const response = generateResponse(userMessage);

    // Store in history
    const entry = {
      id: messageId,
      userMessage,
      aiResponse: response,
      timestamp: new Date().toISOString(),
    };

    chatHistory.push(entry);
    if (chatHistory.length > MAX_HISTORY) {
      chatHistory = chatHistory.slice(-MAX_HISTORY);
    }

    res.json({
      id: messageId,
      message: userMessage,
      response,
      timestamp: entry.timestamp,
    });
  } catch (error) {
    console.error('Chat error:', error);
    res.status(500).json({ error: 'Chat processing failed' });
  }
});

/**
 * Get chat history
 * GET /api/chat/history
 */
app.get('/api/chat/history', (req, res) => {
  res.json(chatHistory);
});

/**
 * Clear chat history
 * DELETE /api/chat/history
 */
app.delete('/api/chat/history', (req, res) => {
  chatHistory = [];
  res.json({ message: 'History cleared' });
});

/**
 * Serve index.html for all other routes (SPA)
 */
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});

// Error handling
app.use((err, req, res, next) => {
  console.error('Server error:', err);
  res.status(500).json({ error: 'Server error' });
});

// Start server
app.listen(PORT, () => {
  console.log(`\n🚀 Chat Server running at http://localhost:${PORT}`);
  console.log(`📝 API endpoints:`);
  console.log(`   POST   /api/chat              - Send message`);
  console.log(`   GET    /api/chat/history      - Get history`);
  console.log(`   DELETE /api/chat/history      - Clear history`);
  console.log(`   GET    /api/health            - Health check\n`);
});

/**
 * Simple response generator
 * In production, this would call RAG adapter or LLM
 */
function generateResponse(userMessage) {
  const lower = userMessage.toLowerCase();

  // Simple pattern matching for demo
  if (lower.includes('hello') || lower.includes('hi')) {
    return 'Hello! How can I help you understand the contradictions in your evidence? I can explain the topology of claims, point out contradictions, or help you organize your thinking.';
  }

  if (lower.includes('contradiction')) {
    return 'A contradiction occurs when two claims make incompatible statements. I can show you which claims contradict each other and help you understand the topology of disagreements in your evidence.';
  }

  if (lower.includes('search')) {
    return 'You can search for claims, and I\'ll show you how they relate to each other through the contradiction graph. The UI displays topology indicators like contradiction count and cluster membership.';
  }

  if (lower.includes('help')) {
    return 'I can help you:\n• Understand contradictions between claims\n• Explore the topology of your evidence\n• Find related claims\n• Clarify your questions\n\nWhat would you like to know?';
  }

  if (lower.includes('topology')) {
    return 'Topology describes the structure of how claims relate to each other. I focus on structural relationships (contradictions, clusters) rather than making truth judgments. This helps you see the landscape of evidence without bias.';
  }

  // Default response
  return `I understand you're asking about: "${userMessage}"\n\nI can help you navigate contradictions in your evidence. Try asking me about:\n• Specific claims\n• Contradictions between claims\n• The topology of evidence\n• How to understand disagreements\n\nWhat aspect would you like to explore?`;
}

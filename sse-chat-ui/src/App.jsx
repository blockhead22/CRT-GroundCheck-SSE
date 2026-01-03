import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import './App.css';

const SOCKET_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  
  const [conversations, setConversations] = useState([]);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  const [socket, setSocket] = useState(null);
  const messagesEndRef = useRef(null);

  // Initialize socket connection
  useEffect(() => {
    if (isAuthenticated) {
      const newSocket = io(SOCKET_URL);
      setSocket(newSocket);
      
      newSocket.on('connected', (data) => {
        console.log(data.message);
      });
      
      newSocket.on('message_received', (data) => {
        setMessages(prev => [...prev, data]);
      });
      
      newSocket.on('error', (data) => {
        setError(data.message);
      });
      
      return () => newSocket.close();
    }
  }, [isAuthenticated]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Fetch conversations on auth
  useEffect(() => {
    if (isAuthenticated) {
      fetchConversations();
    }
  }, [isAuthenticated]);

  // Fetch messages when conversation changes
  useEffect(() => {
    if (currentConversation && isAuthenticated) {
      fetchMessages(currentConversation);
    }
  }, [currentConversation, isAuthenticated]);

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    
    try {
      const response = await fetch(`${SOCKET_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
        credentials: 'include'
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error);
      }
      
      // Login after successful registration
      handleLogin(e);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    
    try {
      const response = await fetch(`${SOCKET_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
        credentials: 'include'
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error);
      }
      
      setIsAuthenticated(true);
      setUsername('');
      setPassword('');
    } catch (err) {
      setError(err.message);
    }
  };

  const fetchConversations = async () => {
    try {
      const response = await fetch(`${SOCKET_URL}/api/conversations`, {
        credentials: 'include'
      });
      const data = await response.json();
      setConversations(data);
      
      if (data.length > 0 && !currentConversation) {
        setCurrentConversation(data[0].conversation_id);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const fetchMessages = async (conversationId) => {
    try {
      const response = await fetch(
        `${SOCKET_URL}/api/conversations/${conversationId}/messages`,
        { credentials: 'include' }
      );
      const data = await response.json();
      setMessages(data);
    } catch (err) {
      setError(err.message);
    }
  };

  const createNewConversation = async () => {
    try {
      const response = await fetch(`${SOCKET_URL}/api/conversations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: `Conversation ${new Date().toLocaleDateString()}` }),
        credentials: 'include'
      });
      
      if (!response.ok) throw new Error('Failed to create conversation');
      
      const data = await response.json();
      setConversations(prev => [data, ...prev]);
      setCurrentConversation(data.conversation_id);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleSendMessage = (e) => {
    e.preventDefault();
    
    if (!input.trim() || !socket || !currentConversation) return;
    
    setIsLoading(true);
    
    socket.emit('send_message', {
      conversation_id: currentConversation,
      content: input
    });
    
    setInput('');
    setIsLoading(false);
  };

  if (!isAuthenticated) {
    return (
      <div className="auth-container">
        <div className="auth-box">
          <h1>SSE Chat</h1>
          <p>Semantic Contradiction Extractor Chat</p>
          
          {error && <div className="error-message">{error}</div>}
          
          <form onSubmit={handleLogin}>
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button type="submit">Login</button>
          </form>
          
          <button onClick={handleRegister} className="secondary">
            or Register
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-container">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>SSE Chat</h2>
          <button onClick={createNewConversation} className="new-chat-btn">
            + New Chat
          </button>
        </div>
        
        <div className="conversations-list">
          {conversations.map(conv => (
            <div
              key={conv.conversation_id}
              className={`conversation-item ${
                currentConversation === conv.conversation_id ? 'active' : ''
              }`}
              onClick={() => setCurrentConversation(conv.conversation_id)}
            >
              <span>{conv.title}</span>
              <small>{new Date(conv.created_at).toLocaleDateString()}</small>
            </div>
          ))}
        </div>
      </aside>
      
      <main className="chat-main">
        <div className="chat-header">
          <h2>
            {conversations.find(c => c.conversation_id === currentConversation)?.title || 'Chat'}
          </h2>
          <span className="user-info">{username}</span>
        </div>
        
        {error && <div className="error-message">{error}</div>}
        
        <div className="messages-container">
          {messages.length === 0 ? (
            <div className="empty-state">
              <p>Start a conversation</p>
              <p className="hint">Ask anything and the system will extract claims and detect contradictions</p>
            </div>
          ) : (
            messages.map(msg => (
              <div key={msg.message_id} className={`message ${msg.role}`}>
                <div className="message-content">
                  <p>{msg.content}</p>
                  
                  {msg.analysis && msg.role === 'user' && (
                    <details className="analysis-details">
                      <summary>Analysis ({msg.analysis.claims?.length || 0} claims)</summary>
                      
                      {msg.analysis.claims && msg.analysis.claims.length > 0 && (
                        <div className="claims-list">
                          <strong>Claims:</strong>
                          {msg.analysis.claims.map((claim, i) => (
                            <div key={i} className="claim-item">
                              <p>{claim.claim_text}</p>
                              {claim.supporting_quotes && (
                                <small>Quotes: {claim.supporting_quotes.length}</small>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                      
                      {msg.analysis.contradictions && msg.analysis.contradictions.length > 0 && (
                        <div className="contradictions-list">
                          <strong>Contradictions Found:</strong>
                          <p>{msg.analysis.contradictions.length} contradiction(s)</p>
                        </div>
                      )}
                    </details>
                  )}
                </div>
                <small className="message-time">
                  {new Date(msg.created_at || msg.timestamp).toLocaleTimeString()}
                </small>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
        
        <form onSubmit={handleSendMessage} className="input-form">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading || !input.trim()}>
            {isLoading ? 'Sending...' : 'Send'}
          </button>
        </form>
      </main>
    </div>
  );
}

export default App;

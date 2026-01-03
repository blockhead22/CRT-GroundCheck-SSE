"""
SSE Chat UI - Backend Flask Application

A ChatGPT-like interface that integrates the SSE (Semantic Contradiction Extractor)
to extract claims, detect contradictions, and maintain persistent memory.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import SSE
sys.path.insert(0, str(Path(__file__).parent.parent / "AI_round2"))

from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
import numpy as np

from sse.chunker import chunk_text
from sse.embeddings import EmbeddingStore
from sse.extractor import extract_claims_from_chunks
from sse.contradictions import detect_contradictions, clear_nli_cache
from sse.clustering import cluster_claims
from sse.ambiguity import analyze_ambiguity

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///sse_chat.db')

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize embedding store once at startup
embedding_store = None
users = {}  # In-memory user sessions


class DatabaseManager:
    """Manages SQLite database for chat history and memory."""
    
    def __init__(self, db_path='sse_chat.db'):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database schema."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Conversations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
            )
        ''')
        
        # Extracted claims table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS claims (
                claim_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                claim_text TEXT NOT NULL,
                supporting_quotes TEXT,
                ambiguity TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id),
                FOREIGN KEY (message_id) REFERENCES messages(message_id)
            )
        ''')
        
        # Contradictions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contradictions (
                contradiction_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                claim_id_a TEXT NOT NULL,
                claim_id_b TEXT NOT NULL,
                label TEXT,
                evidence_quotes TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id),
                FOREIGN KEY (claim_id_a) REFERENCES claims(claim_id),
                FOREIGN KEY (claim_id_b) REFERENCES claims(claim_id)
            )
        ''')
        
        # Context/Memory table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS context_memory (
                memory_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                conversation_id TEXT,
                context_type TEXT,
                content TEXT,
                importance_score REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
            )
        ''')
        
        conn.commit()
        conn.close()


db = DatabaseManager()


class SSEAnalyzer:
    """Analyzes messages using SSE to extract claims and contradictions."""
    
    def __init__(self):
        self.emb_store = EmbeddingStore("all-MiniLM-L6-v2")
    
    def analyze_message(self, text: str) -> dict:
        """
        Analyze a message using SSE pipeline.
        
        Returns:
            {
                'chunks': List[Dict],
                'claims': List[Dict],
                'contradictions': List[Dict],
                'clusters': List[Dict],
                'ambiguities': List[Dict]
            }
        """
        try:
            # Chunk text
            chunks = chunk_text(text, max_chars=200, overlap=50)
            if not chunks:
                return self._empty_analysis()
            
            # Embed chunks
            embeddings = self.emb_store.embed_texts([c['text'] for c in chunks])
            
            # Extract claims
            claims = extract_claims_from_chunks(chunks, embeddings)
            
            # Analyze ambiguity
            for claim in claims:
                claim['ambiguity'] = analyze_ambiguity(claim['claim_text'])
            
            # Embed claims for contradiction detection
            if claims:
                claim_embeddings = self.emb_store.embed_texts([c['claim_text'] for c in claims])
                clear_nli_cache()
                contradictions = detect_contradictions(claims, claim_embeddings, use_ollama=False)
            else:
                contradictions = []
            
            # Cluster claims
            if claims:
                clusters = cluster_claims(claims, embeddings=claim_embeddings)
            else:
                clusters = []
            
            return {
                'chunks': chunks,
                'claims': claims,
                'contradictions': contradictions,
                'clusters': clusters,
                'success': True
            }
        
        except Exception as e:
            print(f"Error in SSE analysis: {e}")
            return self._empty_analysis()
    
    def _empty_analysis(self):
        """Return empty analysis structure."""
        return {
            'chunks': [],
            'claims': [],
            'contradictions': [],
            'clusters': [],
            'success': False
        }


sse_analyzer = SSEAnalyzer()


# Routes and WebSocket handlers

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})


@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user."""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        user_id = f"user_{int(datetime.utcnow().timestamp() * 1000)}"
        password_hash = generate_password_hash(password)
        
        cursor.execute('''
            INSERT INTO users (user_id, username, password_hash)
            VALUES (?, ?, ?)
        ''', (user_id, username, password_hash))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'user_id': user_id,
            'username': username,
            'message': 'Registration successful'
        }), 201
    
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username already exists'}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user."""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, password_hash FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if not user or not check_password_hash(user['password_hash'], password):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        session['user_id'] = user['user_id']
        users[user['user_id']] = {'username': username, 'session_id': None}
        
        return jsonify({
            'user_id': user['user_id'],
            'username': username,
            'message': 'Login successful'
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Get user's conversations."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT conversation_id, title, created_at
            FROM conversations
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        conversations = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify(conversations), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    """Create new conversation."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    title = data.get('title', 'New Conversation')
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        conversation_id = f"conv_{int(datetime.utcnow().timestamp() * 1000)}"
        cursor.execute('''
            INSERT INTO conversations (conversation_id, user_id, title)
            VALUES (?, ?, ?)
        ''', (conversation_id, user_id, title))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'conversation_id': conversation_id,
            'title': title,
            'created_at': datetime.utcnow().isoformat()
        }), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/conversations/<conversation_id>/messages', methods=['GET'])
def get_messages(conversation_id):
    """Get messages in a conversation."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Verify user owns this conversation
        cursor.execute(
            'SELECT user_id FROM conversations WHERE conversation_id = ?',
            (conversation_id,)
        )
        conv = cursor.fetchone()
        
        if not conv or conv['user_id'] != user_id:
            conn.close()
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Get messages
        cursor.execute('''
            SELECT message_id, role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
        ''', (conversation_id,))
        
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify(messages), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze', methods=['POST'])
def analyze_text():
    """Analyze text using SSE."""
    data = request.json
    text = data.get('text')
    
    if not text:
        return jsonify({'error': 'Text required'}), 400
    
    try:
        analysis = sse_analyzer.analyze_message(text)
        return jsonify(analysis), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# WebSocket events

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    user_id = session.get('user_id')
    if user_id and user_id in users:
        users[user_id]['session_id'] = request.sid
        emit('connected', {'message': 'Connected to SSE Chat'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    user_id = session.get('user_id')
    if user_id and user_id in users:
        users[user_id]['session_id'] = None


@socketio.on('join_conversation')
def on_join_conversation(data):
    """Join a conversation room."""
    user_id = session.get('user_id')
    conversation_id = data.get('conversation_id')
    
    if not user_id or not conversation_id:
        emit('error', {'message': 'Invalid conversation'})
        return
    
    join_room(conversation_id)
    emit('joined_conversation', {'conversation_id': conversation_id}, to=request.sid)


@socketio.on('send_message')
def on_send_message(data):
    """Handle incoming message."""
    user_id = session.get('user_id')
    conversation_id = data.get('conversation_id')
    content = data.get('content')
    
    if not user_id or not conversation_id or not content:
        emit('error', {'message': 'Invalid message'})
        return
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Store user message
        message_id = f"msg_{int(datetime.utcnow().timestamp() * 1000)}"
        cursor.execute('''
            INSERT INTO messages (message_id, conversation_id, role, content)
            VALUES (?, ?, ?, ?)
        ''', (message_id, conversation_id, 'user', content))
        
        conn.commit()
        conn.close()
        
        # Analyze message with SSE
        analysis = sse_analyzer.analyze_message(content)
        
        # Emit message to conversation room
        emit('message_received', {
            'message_id': message_id,
            'role': 'user',
            'content': content,
            'analysis': analysis,
            'timestamp': datetime.utcnow().isoformat()
        }, to=conversation_id)
        
        # Generate AI response (simple for now)
        ai_response = generate_ai_response(content, analysis)
        
        # Store AI response
        ai_message_id = f"msg_{int(datetime.utcnow().timestamp() * 1000)}"
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (message_id, conversation_id, role, content)
            VALUES (?, ?, ?, ?)
        ''', (ai_message_id, conversation_id, 'assistant', ai_response))
        conn.commit()
        conn.close()
        
        # Emit AI response
        emit('message_received', {
            'message_id': ai_message_id,
            'role': 'assistant',
            'content': ai_response,
            'timestamp': datetime.utcnow().isoformat()
        }, to=conversation_id)
    
    except Exception as e:
        emit('error', {'message': str(e)})


def generate_ai_response(user_message: str, analysis: dict) -> str:
    """Generate AI response based on message and SSE analysis."""
    claims_count = len(analysis.get('claims', []))
    contradictions_count = len(analysis.get('contradictions', []))
    
    response_parts = []
    
    if claims_count > 0:
        response_parts.append(f"I identified {claims_count} claim(s) in your message.")
    
    if contradictions_count > 0:
        response_parts.append(f"I found {contradictions_count} potential contradiction(s) to explore.")
    
    if not response_parts:
        response_parts.append("That's interesting. Tell me more about your thoughts on this.")
    
    response = " ".join(response_parts)
    
    # Add contextual response
    if any(word in user_message.lower() for word in ['help', 'how', 'what']):
        response += " How can I assist you further?"
    
    return response


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

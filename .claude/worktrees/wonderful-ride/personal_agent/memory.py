"""
Memory System for Personal Agent

THIS IS PHASE D+: Learning, state persistence, user modeling.
This is intentional. This is a personal tool, not a product.
"""

import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path


class MemorySystem:
    """
    Persistent memory for personal agent.
    
    WARNING: This violates SSE Phase 6 boundaries.
    This is intentional - it's a personal experimental system.
    
    Capabilities (all Phase D+):
    - Stores conversations
    - Learns user preferences
    - Tracks what approaches work
    - Remembers successful strategies
    - Builds user model over time
    """
    
    def __init__(self, db_path: str = "personal_agent/memory.db"):
        """Initialize memory system with persistent storage."""
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _get_connection(self, timeout: float = 30.0) -> sqlite3.Connection:
        """
        Create a properly configured SQLite connection with:
        - WAL mode for better concurrent access
        - Busy timeout to retry on lock conflicts
        """
        conn = sqlite3.connect(self.db_path, timeout=timeout)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")  # 30 second busy timeout
        return conn
    
    def _init_db(self):
        """Create database schema."""
        conn = self._get_connection()
        c = conn.cursor()
        
        # Conversations table
        c.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_message TEXT NOT NULL,
                agent_response TEXT NOT NULL,
                context TEXT,
                contradictions_found TEXT,
                approach_used TEXT
            )
        ''')
        
        # User preferences (Phase D+ learning)
        c.execute('''
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                last_updated TEXT NOT NULL
            )
        ''')
        
        # Successful strategies (Phase D+ outcome measurement)
        c.execute('''
            CREATE TABLE IF NOT EXISTS strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                situation TEXT NOT NULL,
                approach TEXT NOT NULL,
                outcome TEXT,
                success_score REAL,
                timestamp TEXT NOT NULL
            )
        ''')
        
        # Knowledge contradictions (SSE integration)
        c.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_contradictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_a TEXT NOT NULL,
                claim_b TEXT NOT NULL,
                context TEXT,
                user_resolution TEXT,
                timestamp TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def store_conversation(
        self,
        user_message: str,
        agent_response: str,
        context: Optional[str] = None,
        contradictions: Optional[List[Dict]] = None,
        approach: Optional[str] = None
    ) -> int:
        """
        Store a conversation turn.
        
        Phase D+ violation: Outcome measurement.
        This tracks conversations to learn patterns.
        """
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO conversations 
            (timestamp, user_message, agent_response, context, contradictions_found, approach_used)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            user_message,
            agent_response,
            context,
            json.dumps(contradictions) if contradictions else None,
            approach
        ))
        
        conv_id = c.lastrowid
        conn.commit()
        conn.close()
        return conv_id
    
    def get_recent_conversations(self, limit: int = 10) -> List[Dict]:
        """
        Retrieve recent conversations for context.
        
        Phase D+ violation: State persistence across queries.
        """
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT timestamp, user_message, agent_response, context, contradictions_found
            FROM conversations
            ORDER BY id DESC
            LIMIT ?
        ''', (limit,))
        
        rows = c.fetchall()
        conn.close()
        
        return [
            {
                'timestamp': row[0],
                'user_message': row[1],
                'agent_response': row[2],
                'context': row[3],
                'contradictions': json.loads(row[4]) if row[4] else None
            }
            for row in reversed(rows)  # Return in chronological order
        ]
    
    def learn_preference(self, key: str, value: str, confidence: float = 0.7):
        """
        Learn a user preference.
        
        Phase D+ violation: User modeling.
        This builds a persistent model of the user.
        """
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT OR REPLACE INTO preferences (key, value, confidence, last_updated)
            VALUES (?, ?, ?, ?)
        ''', (key, value, confidence, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_preference(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a learned preference."""
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute('SELECT value, confidence, last_updated FROM preferences WHERE key = ?', (key,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return {
                'value': row[0],
                'confidence': row[1],
                'last_updated': row[2]
            }
        return None
    
    def record_strategy_outcome(
        self,
        situation: str,
        approach: str,
        outcome: str,
        success_score: float
    ):
        """
        Record whether a strategy worked.
        
        Phase D+ violation: Outcome measurement and learning.
        This measures success and uses it to improve.
        """
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO strategies (situation, approach, outcome, success_score, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (situation, approach, outcome, success_score, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_successful_strategies(self, situation: str, min_score: float = 0.6) -> List[Dict]:
        """
        Get strategies that worked in similar situations.
        
        Phase D+ violation: Learning from patterns.
        This is how the agent gets better over time.
        """
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT approach, outcome, success_score, timestamp
            FROM strategies
            WHERE situation LIKE ? AND success_score >= ?
            ORDER BY success_score DESC
            LIMIT 5
        ''', (f'%{situation}%', min_score))
        
        rows = c.fetchall()
        conn.close()
        
        return [
            {
                'approach': row[0],
                'outcome': row[1],
                'success_score': row[2],
                'timestamp': row[3]
            }
            for row in rows
        ]
    
    def store_contradiction_resolution(
        self,
        claim_a: str,
        claim_b: str,
        context: str,
        user_resolution: str
    ):
        """
        Store how user resolved a contradiction.
        
        Phase D+ violation: Learning user's decision patterns.
        """
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO knowledge_contradictions 
            (claim_a, claim_b, context, user_resolution, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (claim_a, claim_b, context, user_resolution, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_conversation_count(self) -> int:
        """Get total number of conversations."""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM conversations')
        count = c.fetchone()[0]
        conn.close()
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        conn = self._get_connection()
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM conversations')
        conv_count = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM preferences')
        pref_count = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM strategies')
        strat_count = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM knowledge_contradictions')
        contra_count = c.fetchone()[0]
        
        conn.close()
        
        return {
            'conversations': conv_count,
            'preferences_learned': pref_count,
            'strategies_recorded': strat_count,
            'contradictions_resolved': contra_count
        }

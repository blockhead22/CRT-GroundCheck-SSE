"""
Memory and Context Management System for SSE Chat

Maintains persistent memory of claims, contradictions, and user context
across conversations for informed AI responses.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import numpy as np
from sklearn.preprocessing import normalize


class MemoryManager:
    """Manages persistent memory of claims, contradictions, and context."""
    
    def __init__(self, db_path='sse_chat.db'):
        self.db_path = db_path
    
    def get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def store_message_analysis(self, conversation_id: str, message_id: str, 
                              claims: List[Dict], contradictions: List[Dict]) -> None:
        """Store extracted claims and contradictions."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Store claims
            for claim in claims:
                claim_id = f"clm_{conversation_id}_{message_id}_{claims.index(claim)}"
                cursor.execute('''
                    INSERT INTO claims (claim_id, conversation_id, message_id, 
                                      claim_text, supporting_quotes, ambiguity)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    claim_id,
                    conversation_id,
                    message_id,
                    claim['claim_text'],
                    json.dumps(claim.get('supporting_quotes', [])),
                    json.dumps(claim.get('ambiguity', {}))
                ))
            
            # Store contradictions
            for contradiction in contradictions:
                cont_id = f"cont_{conversation_id}_{message_id}_{contradictions.index(contradiction)}"
                cursor.execute('''
                    INSERT INTO contradictions (contradiction_id, conversation_id,
                                              claim_id_a, claim_id_b, label,
                                              evidence_quotes)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    cont_id,
                    conversation_id,
                    contradiction['pair']['claim_id_a'],
                    contradiction['pair']['claim_id_b'],
                    contradiction.get('label', 'potential_contradiction'),
                    json.dumps(contradiction.get('evidence_quotes', []))
                ))
            
            conn.commit()
        finally:
            conn.close()
    
    def get_conversation_context(self, conversation_id: str, limit: int = 10) -> Dict:
        """Get context from recent messages and claims."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get recent claims
            cursor.execute('''
                SELECT DISTINCT claim_text, ambiguity
                FROM claims
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (conversation_id, limit))
            claims = [dict(row) for row in cursor.fetchall()]
            
            # Get recent contradictions
            cursor.execute('''
                SELECT claim_id_a, claim_id_b, label
                FROM contradictions
                WHERE conversation_id = ?
                ORDER BY detected_at DESC
                LIMIT ?
            ''', (conversation_id, limit))
            contradictions = [dict(row) for row in cursor.fetchall()]
            
            # Get conversation messages for context
            cursor.execute('''
                SELECT role, content
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT 5
            ''', (conversation_id,))
            recent_messages = [dict(row) for row in cursor.fetchall()]
            
            return {
                'claims': claims,
                'contradictions': contradictions,
                'recent_messages': recent_messages,
                'total_claims': len(claims),
                'total_contradictions': len(contradictions)
            }
        finally:
            conn.close()
    
    def get_user_memory(self, user_id: str) -> Dict:
        """Get important memories for user across all conversations."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT memory_id, content, importance_score, context_type
                FROM context_memory
                WHERE user_id = ?
                ORDER BY importance_score DESC
                LIMIT 20
            ''', (user_id,))
            
            memories = [dict(row) for row in cursor.fetchall()]
            return {
                'total_memories': len(memories),
                'memories': memories,
                'top_topics': self._extract_top_topics(memories)
            }
        finally:
            conn.close()
    
    def store_memory(self, user_id: str, conversation_id: Optional[str],
                    context_type: str, content: str, 
                    importance_score: float = 1.0) -> None:
        """Store important information in user's memory."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            memory_id = f"mem_{int(datetime.utcnow().timestamp() * 1000)}"
            cursor.execute('''
                INSERT INTO context_memory (memory_id, user_id, conversation_id,
                                          context_type, content, importance_score)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (memory_id, user_id, conversation_id, context_type, 
                  content, importance_score))
            conn.commit()
        finally:
            conn.close()
    
    def _extract_top_topics(self, memories: List[Dict]) -> List[str]:
        """Extract top topics from memories."""
        topics = []
        for mem in memories[:10]:
            content = mem.get('content', '')
            # Simple topic extraction - could be enhanced with NLP
            words = content.lower().split()
            topics.extend([w for w in words if len(w) > 5])
        
        # Return unique top words
        return list(set(topics))[:5]
    
    def update_memory_importance(self, memory_id: str, score: float) -> None:
        """Update importance score of a memory."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE context_memory
                SET importance_score = ?
                WHERE memory_id = ?
            ''', (score, memory_id))
            conn.commit()
        finally:
            conn.close()
    
    def cleanup_old_memories(self, days: int = 30) -> int:
        """Remove memories older than specified days."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            cursor.execute('''
                DELETE FROM context_memory
                WHERE created_at < ?
                AND importance_score < 0.5
            ''', (cutoff.isoformat(),))
            
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


class ContextAnalyzer:
    """Analyzes conversation context and generates context summaries."""
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
    
    def generate_context_summary(self, conversation_id: str) -> str:
        """Generate a summary of conversation context."""
        context = self.memory.get_conversation_context(conversation_id)
        
        summary = []
        
        if context['total_claims'] > 0:
            summary.append(f"We've discussed {context['total_claims']} main claims.")
        
        if context['total_contradictions'] > 0:
            summary.append(f"Found {context['total_contradictions']} contradictions worth exploring.")
        
        # Add top claims
        if context['claims']:
            top_claims = [c['claim_text'] for c in context['claims'][:3]]
            summary.append(f"Key points: {'; '.join(top_claims)}")
        
        return " ".join(summary) if summary else "Starting a new conversation"
    
    def should_reference_memory(self, current_message: str, user_id: str) -> bool:
        """Determine if user memory should be referenced."""
        # Simple heuristic: reference if keywords match
        memory = self.memory.get_user_memory(user_id)
        topics = memory.get('top_topics', [])
        
        message_words = set(current_message.lower().split())
        return any(topic in message_words for topic in topics)
    
    def get_relevant_memory(self, user_id: str, message: str, limit: int = 3) -> List[Dict]:
        """Get memory relevant to current message."""
        memory = self.memory.get_user_memory(user_id)
        
        if not self.should_reference_memory(message, user_id):
            return []
        
        # Filter memories by relevance
        relevant = []
        message_words = set(message.lower().split())
        
        for mem in memory['memories']:
            content_words = set(mem['content'].lower().split())
            overlap = len(message_words & content_words)
            
            if overlap > 0:
                relevant.append({
                    **mem,
                    'relevance_score': overlap / len(message_words)
                })
        
        # Sort by relevance and return top matches
        relevant.sort(key=lambda x: x['relevance_score'], reverse=True)
        return relevant[:limit]


class ConversationSummarizer:
    """Summarizes conversations for context preservation."""
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
    
    def summarize_conversation(self, conversation_id: str) -> str:
        """Create a brief summary of entire conversation."""
        conn = self.memory.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT role, content
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
            ''', (conversation_id,))
            
            messages = [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
        
        # Generate summary
        user_messages = [m['content'] for m in messages if m['role'] == 'user']
        
        if not user_messages:
            return "Empty conversation"
        
        # Simple summarization: concatenate key points
        summary_parts = [
            f"Conversation had {len(user_messages)} user messages",
            f"Topics: {', '.join(user_messages[:3])}",
        ]
        
        return ". ".join(summary_parts)
    
    def extract_key_points(self, conversation_id: str, limit: int = 5) -> List[str]:
        """Extract key points from conversation."""
        context = self.memory.get_conversation_context(conversation_id, limit)
        
        key_points = []
        
        # Add claims as key points
        for claim in context['claims'][:limit]:
            key_points.append(f"Claim: {claim['claim_text']}")
        
        # Add contradictions
        if context['contradictions']:
            key_points.append(
                f"Contradiction: {context['total_contradictions']} " +
                "potential contradictions found"
            )
        
        return key_points[:limit]


class RelevanceScoringEngine:
    """Scores relevance of messages for memory and retrieval."""
    
    def __init__(self):
        self.access_count = {}  # Track how often memories are accessed
    
    def score_memory_relevance(self, memory: Dict, current_message: str, 
                               embedding_similarity: float = 0.0) -> float:
        """Score how relevant a memory is to current context."""
        base_score = memory.get('importance_score', 1.0)
        
        # Boost score if frequently accessed
        memory_id = memory.get('memory_id', '')
        access_boost = self.access_count.get(memory_id, 0) * 0.1
        
        # Boost score based on recency (inverse)
        created_at = datetime.fromisoformat(memory.get('created_at', ''))
        age_days = (datetime.utcnow() - created_at).days
        recency_boost = max(0, 1.0 - (age_days / 30))
        
        # Consider embedding similarity if provided
        similarity_boost = embedding_similarity * 0.3
        
        total_score = base_score + access_boost + recency_boost + similarity_boost
        return min(total_score, 2.0)  # Cap at 2.0
    
    def track_access(self, memory_id: str) -> None:
        """Track when a memory is accessed."""
        self.access_count[memory_id] = self.access_count.get(memory_id, 0) + 1
    
    def get_top_scoring_memories(self, memories: List[Dict], 
                                current_message: str, limit: int = 3) -> List[Dict]:
        """Get highest scoring memories."""
        scored = []
        
        for mem in memories:
            score = self.score_memory_relevance(mem, current_message)
            scored.append({**mem, 'relevance_score': score})
        
        # Sort by relevance and return top
        scored.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Track access for top memories
        for mem in scored[:limit]:
            self.track_access(mem['memory_id'])
        
        return scored[:limit]


# Convenience function for creating memory system
def create_memory_system(db_path='sse_chat.db'):
    """Factory function to create memory system components."""
    memory_mgr = MemoryManager(db_path)
    context_analyzer = ContextAnalyzer(memory_mgr)
    summarizer = ConversationSummarizer(memory_mgr)
    relevance_engine = RelevanceScoringEngine()
    
    return {
        'memory': memory_mgr,
        'analyzer': context_analyzer,
        'summarizer': summarizer,
        'relevance': relevance_engine
    }

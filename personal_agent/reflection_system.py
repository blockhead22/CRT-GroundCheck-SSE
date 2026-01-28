"""
Directed Reflection System for CRT Memory
-----------------------------------------
Runs a reflection pass after LLM responses to assess confidence
and optionally re-query with stricter grounding.
"""

import json
import sqlite3
import uuid
import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict
import ollama


@dataclass
class ReflectionResult:
    """Result of a reflection pass"""
    trace_id: str
    confidence_score: float  # 0.0 - 1.0
    confidence_label: str    # "high", "medium", "low"
    reasoning: str           # Why this confidence level
    suggested_action: str    # "accept", "refine", "re-query"
    fact_checks: list        # List of fact verification results
    hallucination_risk: str  # "low", "medium", "high"
    timestamp: str


class ReflectionEngine:
    """
    Performs directed reflection on LLM responses.
    
    Flow:
    1. Take response + thinking trace
    2. Prompt LLM to rate confidence given facts
    3. If low confidence → trigger re-query with stricter grounding
    4. Store reflection as separate trace type
    """
    
    REFLECTION_PROMPT = """You are a critical self-assessment module. Analyze the following response and thinking process.

ORIGINAL QUESTION:
{question}

RESPONSE GIVEN:
{response}

THINKING TRACE (if available):
{thinking}

KNOWN FACTS FROM MEMORY:
{facts}

YOUR TASK:
1. Rate confidence in the response accuracy (0.0 to 1.0)
2. Identify any potential hallucinations or unsupported claims
3. Check if the response contradicts any known facts
4. Suggest whether to: ACCEPT (confidence >= 0.7), REFINE (0.4-0.7), or RE-QUERY (< 0.4)

Respond in this exact JSON format:
{{
    "confidence_score": <float 0.0-1.0>,
    "confidence_label": "<high|medium|low>",
    "reasoning": "<why this confidence level>",
    "suggested_action": "<accept|refine|re-query>",
    "fact_checks": [
        {{"claim": "<claim from response>", "supported": <true|false>, "evidence": "<why>"}}
    ],
    "hallucination_risk": "<low|medium|high>",
    "issues_found": ["<issue1>", "<issue2>"]
}}"""

    STRICT_REQUERY_PROMPT = """You are answering a question where a previous response had LOW CONFIDENCE.

ORIGINAL QUESTION:
{question}

PREVIOUS RESPONSE (LOW CONFIDENCE):
{previous_response}

ISSUES IDENTIFIED:
{issues}

VERIFIED FACTS ONLY:
{facts}

INSTRUCTIONS:
- ONLY use information from the verified facts above
- If you cannot answer with high confidence, say "I don't have enough verified information"
- Do NOT speculate or make assumptions
- Cite which facts support your answer

Provide a more grounded response:"""

    def __init__(self, model: str = "deepseek-r1:8b"):
        self.model = model
        self.client = ollama.Client()
    
    def reflect(
        self,
        question: str,
        response: str,
        thinking: str = "",
        facts: list = None,
        thread_id: str = None
    ) -> ReflectionResult:
        """
        Run reflection pass on a response.
        
        Args:
            question: Original user question
            response: LLM's response
            thinking: Thinking trace (if available)
            facts: Known facts from memory for grounding
            thread_id: Thread ID for storage
            
        Returns:
            ReflectionResult with confidence assessment
        """
        facts = facts or []
        facts_text = "\n".join([f"- {f}" for f in facts]) if facts else "(No facts provided)"
        
        prompt = self.REFLECTION_PROMPT.format(
            question=question,
            response=response,
            thinking=thinking or "(No thinking trace)",
            facts=facts_text
        )
        
        try:
            # Use a faster model for reflection to reduce latency
            reflection_response = self.client.chat(
                model="llama3.2:latest",  # Faster model for reflection
                messages=[{"role": "user", "content": prompt}],
                format="json"
            )
            
            content = reflection_response.message.content
            result_data = json.loads(content)
            
            # Validate and normalize
            confidence = max(0.0, min(1.0, float(result_data.get("confidence_score", 0.5))))
            
            if confidence >= 0.7:
                label = "high"
                action = "accept"
            elif confidence >= 0.4:
                label = "medium"
                action = "refine"
            else:
                label = "low"
                action = "re-query"
            
            return ReflectionResult(
                trace_id=f"reflect_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
                confidence_score=confidence,
                confidence_label=result_data.get("confidence_label", label),
                reasoning=result_data.get("reasoning", ""),
                suggested_action=result_data.get("suggested_action", action),
                fact_checks=result_data.get("fact_checks", []),
                hallucination_risk=result_data.get("hallucination_risk", "unknown"),
                timestamp=datetime.utcnow().isoformat()
            )
            
        except Exception as e:
            # Fallback on error
            return ReflectionResult(
                trace_id=f"reflect_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
                confidence_score=0.5,
                confidence_label="unknown",
                reasoning=f"Reflection failed: {str(e)}",
                suggested_action="accept",
                fact_checks=[],
                hallucination_risk="unknown",
                timestamp=datetime.utcnow().isoformat()
            )
    
    def requery_with_grounding(
        self,
        question: str,
        previous_response: str,
        issues: list,
        facts: list
    ) -> Tuple[str, str]:
        """
        Re-query with stricter grounding after low confidence.
        
        Returns:
            Tuple of (new_response, new_thinking)
        """
        facts_text = "\n".join([f"- {f}" for f in facts]) if facts else "(No verified facts)"
        issues_text = "\n".join([f"- {i}" for i in issues]) if issues else "(No specific issues)"
        
        prompt = self.STRICT_REQUERY_PROMPT.format(
            question=question,
            previous_response=previous_response,
            issues=issues_text,
            facts=facts_text
        )
        
        response = self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3},  # Lower temperature for more factual
            think=True
        )
        
        new_thinking = getattr(response.message, 'thinking', '') or ''
        new_content = response.message.content or ''
        
        return new_content, new_thinking


class ReflectionDB:
    """Database operations for reflection traces"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """Create reflection_traces table if not exists"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reflection_traces (
                    trace_id TEXT PRIMARY KEY,
                    thread_id TEXT,
                    message_id TEXT,
                    confidence_score REAL,
                    confidence_label TEXT,
                    reasoning TEXT,
                    suggested_action TEXT,
                    fact_checks TEXT,
                    hallucination_risk TEXT,
                    was_requeried INTEGER DEFAULT 0,
                    requery_trace_id TEXT,
                    created_at TEXT,
                    UNIQUE(trace_id)
                )
            """)
            conn.commit()
    
    def store_reflection(
        self,
        result: ReflectionResult,
        thread_id: str,
        message_id: str = None,
        was_requeried: bool = False,
        requery_trace_id: str = None
    ) -> str:
        """Store reflection result"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO reflection_traces
                (trace_id, thread_id, message_id, confidence_score, confidence_label,
                 reasoning, suggested_action, fact_checks, hallucination_risk,
                 was_requeried, requery_trace_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.trace_id,
                thread_id,
                message_id,
                result.confidence_score,
                result.confidence_label,
                result.reasoning,
                result.suggested_action,
                json.dumps(result.fact_checks),
                result.hallucination_risk,
                1 if was_requeried else 0,
                requery_trace_id,
                result.timestamp
            ))
            conn.commit()
        return result.trace_id
    
    def get_reflection(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve reflection by trace_id"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM reflection_traces WHERE trace_id = ?",
                (trace_id,)
            ).fetchone()
            
            if row:
                data = dict(row)
                data['fact_checks'] = json.loads(data.get('fact_checks') or '[]')
                return data
            return None
    
    def get_thread_reflections(self, thread_id: str, limit: int = 50) -> list:
        """Get all reflections for a thread"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM reflection_traces 
                WHERE thread_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (thread_id, limit)).fetchall()
            
            results = []
            for row in rows:
                data = dict(row)
                data['fact_checks'] = json.loads(data.get('fact_checks') or '[]')
                results.append(data)
            return results


class TrainingDataCollector:
    """
    Collects reflection data for future model training.
    
    Captures:
    - Question/response pairs with confidence scores
    - Hallucination examples
    - Successful re-query improvements
    """
    
    def __init__(self, db_path: str = "data/training_data.db"):
        self.db_path = db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create training data tables"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            # Reflection training samples
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reflection_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT,
                    response TEXT,
                    thinking TEXT,
                    confidence_score REAL,
                    confidence_label TEXT,
                    fact_checks TEXT,
                    hallucination_risk TEXT,
                    was_useful INTEGER,
                    created_at TEXT
                )
            """)
            
            # Successful re-query improvements
            conn.execute("""
                CREATE TABLE IF NOT EXISTS requery_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT,
                    original_response TEXT,
                    issues TEXT,
                    improved_response TEXT,
                    confidence_improvement REAL,
                    created_at TEXT
                )
            """)
            
            # Preference pairs for RLHF
            conn.execute("""
                CREATE TABLE IF NOT EXISTS preference_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT,
                    chosen_response TEXT,
                    rejected_response TEXT,
                    reason TEXT,
                    created_at TEXT
                )
            """)
            conn.commit()
    
    def log_reflection(
        self,
        question: str,
        response: str,
        thinking: str,
        result: ReflectionResult,
        was_useful: bool = True
    ):
        """Log a reflection for training"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO reflection_samples
                (question, response, thinking, confidence_score, confidence_label,
                 fact_checks, hallucination_risk, was_useful, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                question,
                response,
                thinking,
                result.confidence_score,
                result.confidence_label,
                json.dumps(result.fact_checks),
                result.hallucination_risk,
                1 if was_useful else 0,
                datetime.utcnow().isoformat()
            ))
            conn.commit()
    
    def log_requery_improvement(
        self,
        question: str,
        original: str,
        issues: list,
        improved: str,
        confidence_improvement: float
    ):
        """Log successful re-query improvement"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO requery_samples
                (question, original_response, issues, improved_response,
                 confidence_improvement, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                question,
                original,
                json.dumps(issues),
                improved,
                confidence_improvement,
                datetime.utcnow().isoformat()
            ))
            conn.commit()
    
    def log_preference(
        self,
        question: str,
        chosen: str,
        rejected: str,
        reason: str
    ):
        """Log preference pair for RLHF training"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO preference_samples
                (question, chosen_response, rejected_response, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                question,
                chosen,
                rejected,
                reason,
                datetime.utcnow().isoformat()
            ))
            conn.commit()
    
    def export_for_training(self, format: str = "jsonl") -> str:
        """Export training data in specified format"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Export reflection samples
            reflections = conn.execute("SELECT * FROM reflection_samples").fetchall()
            requeries = conn.execute("SELECT * FROM requery_samples").fetchall()
            preferences = conn.execute("SELECT * FROM preference_samples").fetchall()
        
        if format == "jsonl":
            lines = []
            
            # Reflection training format
            for r in reflections:
                lines.append(json.dumps({
                    "type": "reflection",
                    "input": f"Question: {r['question']}\nResponse: {r['response']}\nThinking: {r['thinking']}",
                    "output": json.dumps({
                        "confidence": r['confidence_score'],
                        "label": r['confidence_label'],
                        "hallucination_risk": r['hallucination_risk']
                    })
                }))
            
            # Preference pairs for DPO/RLHF
            for p in preferences:
                lines.append(json.dumps({
                    "type": "preference",
                    "prompt": p['question'],
                    "chosen": p['chosen_response'],
                    "rejected": p['rejected_response']
                }))
            
            return "\n".join(lines)
        
        return json.dumps({
            "reflections": [dict(r) for r in reflections],
            "requeries": [dict(r) for r in requeries],
            "preferences": [dict(r) for r in preferences]
        }, indent=2)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get training data statistics"""
        with sqlite3.connect(self.db_path) as conn:
            reflection_count = conn.execute("SELECT COUNT(*) FROM reflection_samples").fetchone()[0]
            requery_count = conn.execute("SELECT COUNT(*) FROM requery_samples").fetchone()[0]
            preference_count = conn.execute("SELECT COUNT(*) FROM preference_samples").fetchone()[0]
            
            avg_confidence = conn.execute(
                "SELECT AVG(confidence_score) FROM reflection_samples"
            ).fetchone()[0] or 0
            
            high_risk_count = conn.execute(
                "SELECT COUNT(*) FROM reflection_samples WHERE hallucination_risk = 'high'"
            ).fetchone()[0]
        
        return {
            "total_reflections": reflection_count,
            "total_requeries": requery_count,
            "total_preferences": preference_count,
            "average_confidence": round(avg_confidence, 3),
            "high_hallucination_risk_count": high_risk_count
        }


# Convenience function for streaming integration
def run_reflection_pass(
    question: str,
    response: str,
    thinking: str,
    thread_id: str,
    db_path: str,
    facts: list = None,
    auto_requery: bool = True,
    collect_training_data: bool = True
) -> Tuple[ReflectionResult, Optional[str], Optional[str]]:
    """
    Run full reflection pass with optional re-query.
    
    Returns:
        Tuple of (ReflectionResult, requery_response or None, requery_thinking or None)
    """
    engine = ReflectionEngine()
    db = ReflectionDB(db_path)
    
    # Run reflection
    result = engine.reflect(
        question=question,
        response=response,
        thinking=thinking,
        facts=facts,
        thread_id=thread_id
    )
    
    requery_response = None
    requery_thinking = None
    
    # Auto re-query on low confidence
    if auto_requery and result.suggested_action == "re-query":
        issues = [fc.get('claim', '') for fc in result.fact_checks if not fc.get('supported', True)]
        requery_response, requery_thinking = engine.requery_with_grounding(
            question=question,
            previous_response=response,
            issues=issues,
            facts=facts or []
        )
    
    # Store reflection
    db.store_reflection(
        result=result,
        thread_id=thread_id,
        was_requeried=requery_response is not None
    )
    
    # Collect training data
    if collect_training_data:
        collector = TrainingDataCollector()
        collector.log_reflection(question, response, thinking, result)
        
        if requery_response:
            # Log preference: improved response is "chosen"
            collector.log_preference(
                question=question,
                chosen=requery_response,
                rejected=response,
                reason=f"Re-queried due to low confidence ({result.confidence_score})"
            )
    
    return result, requery_response, requery_thinking

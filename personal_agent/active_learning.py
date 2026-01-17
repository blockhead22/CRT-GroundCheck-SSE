"""
Active Learning Coordinator for CRT

Monitors gate decisions, collects corrections, triggers retraining,
and hot-reloads improved models without system restart.

This is the "self-improving" magic - the system learns from every
user correction and automatically gets better over time.

Architecture:
1. Gate Event Logger - Records every gate decision
2. Correction Tracker - Captures user overrides/corrections
3. Training Trigger - Decides when to retrain (data threshold)
4. Model Trainer - Spawns background training job
5. Hot Reloader - Swaps model without restart (thread-safe)
6. Stats Reporter - Dashboard integration

Philosophy:
- Never block user interactions (async training)
- Conservative retraining (need enough data to improve)
- Graceful degradation (if training fails, keep old model)
- Auditable (every decision logged)
"""

import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from queue import Queue
import subprocess
import os


@dataclass
class GateEvent:
    """A single gate decision event."""
    event_id: str
    timestamp: float
    question: str
    response_type_predicted: str  # From classifier
    response_type_actual: Optional[str]  # From user correction
    intent_align: float
    memory_align: float
    grounding_score: float
    gates_passed: bool
    gate_reason: str
    user_override: Optional[bool]  # Did user correct us?
    correction_timestamp: Optional[float]
    thread_id: str
    session_id: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
@dataclass
class LearningStats:
    """Current learning system statistics."""
    total_gate_events: int
    total_corrections: int
    correction_rate: float
    total_training_runs: int
    last_training_at: Optional[float]
    last_training_success: Optional[bool]
    current_model_version: str
    current_model_accuracy: Optional[float]
    pending_corrections: int
    next_training_threshold: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ActiveLearningCoordinator:
    """
    Coordinates active learning across CRT gate system.
    
    Key responsibilities:
    1. Log every gate decision to SQLite
    2. Track user corrections (overrides)
    3. Trigger retraining when threshold met
    4. Manage background training jobs
    5. Hot-reload new models
    6. Provide learning statistics
    
    Thread-safety: All public methods are thread-safe.
    """
    
    def __init__(
        self,
        db_path: str = "personal_agent/active_learning.db",
        model_path: str = "models/response_classifier.joblib",
        training_threshold: int = 50,  # Retrain after N corrections
        training_script: str = "tools/train_response_classifier.py",
    ):
        self.db_path = Path(db_path)
        self.model_path = Path(model_path)
        self.training_threshold = training_threshold
        self.training_script = Path(training_script)
        
        # Thread safety
        self._lock = threading.RLock()
        self._model_lock = threading.RLock()
        
        # Current loaded model
        self._current_model = None
        self._current_model_version = "v0_bootstrap"
        
        # Training state
        self._training_in_progress = False
        self._training_thread: Optional[threading.Thread] = None
        self._training_queue: Queue = Queue()
        
        # Stats cache (updated periodically)
        self._stats_cache: Optional[LearningStats] = None
        self._stats_cache_time: float = 0
        self._stats_cache_ttl: float = 5.0  # 5 second TTL
        
        # Initialize
        self._init_db()
        self._load_model_if_exists()
        
        # Start background training worker
        self._start_training_worker()
    
    def _init_db(self):
        """Initialize SQLite database for event logging."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Gate events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gate_events (
                event_id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                question TEXT NOT NULL,
                response_type_predicted TEXT NOT NULL,
                response_type_actual TEXT,
                intent_align REAL NOT NULL,
                memory_align REAL NOT NULL,
                grounding_score REAL NOT NULL,
                gates_passed INTEGER NOT NULL,
                gate_reason TEXT,
                user_override INTEGER,
                correction_timestamp REAL,
                thread_id TEXT,
                session_id TEXT
            )
        """)
        
        # Create indexes separately
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON gate_events(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_correction ON gate_events(user_override, correction_timestamp)")
        
        # Training runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at REAL NOT NULL,
                finished_at REAL,
                success INTEGER,
                model_version TEXT NOT NULL,
                training_examples INTEGER,
                validation_accuracy REAL,
                error_message TEXT,
                model_path TEXT
            )
        """)
        
        # Model versions table (for hot-reload tracking)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_versions (
                version TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                model_path TEXT NOT NULL,
                accuracy REAL,
                training_examples INTEGER,
                is_active INTEGER DEFAULT 0
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _load_model_if_exists(self):
        """Load existing model if available."""
        if not self.model_path.exists():
            return
        
        try:
            import joblib
            with self._model_lock:
                self._current_model = joblib.load(self.model_path)
                self._current_model_version = self._get_latest_model_version()
        except Exception as e:
            print(f"Warning: Could not load model from {self.model_path}: {e}")
    
    def _get_latest_model_version(self) -> str:
        """Get latest model version from DB."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT version FROM model_versions 
            WHERE is_active = 1 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else "v0_bootstrap"
    
    def record_gate_event(
        self,
        question: str,
        response_type_predicted: str,
        intent_align: float,
        memory_align: float,
        grounding_score: float,
        gates_passed: bool,
        gate_reason: str,
        thread_id: str = "default",
        session_id: str = "default",
    ) -> str:
        """
        Record a gate decision event.
        
        Returns event_id for later correction tracking.
        """
        import uuid
        
        event = GateEvent(
            event_id=str(uuid.uuid4()),
            timestamp=time.time(),
            question=question,
            response_type_predicted=response_type_predicted,
            response_type_actual=None,
            intent_align=intent_align,
            memory_align=memory_align,
            grounding_score=grounding_score,
            gates_passed=gates_passed,
            gate_reason=gate_reason,
            user_override=None,
            correction_timestamp=None,
            thread_id=thread_id,
            session_id=session_id,
        )
        
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO gate_events (
                    event_id, timestamp, question, response_type_predicted,
                    response_type_actual, intent_align, memory_align,
                    grounding_score, gates_passed, gate_reason,
                    user_override, correction_timestamp, thread_id, session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id, event.timestamp, event.question,
                event.response_type_predicted, event.response_type_actual,
                event.intent_align, event.memory_align, event.grounding_score,
                1 if event.gates_passed else 0, event.gate_reason,
                None, None, event.thread_id, event.session_id
            ))
            conn.commit()
            conn.close()
        
        return event.event_id
    
    def record_user_correction(
        self,
        event_id: str,
        actual_response_type: str,
        user_feedback: Optional[str] = None,
    ):
        """
        Record user correction of a gate decision.
        
        This is a TRAINING SIGNAL - the user told us we got it wrong.
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Update event with correction
            cursor.execute("""
                UPDATE gate_events 
                SET response_type_actual = ?,
                    user_override = 1,
                    correction_timestamp = ?
                WHERE event_id = ?
            """, (actual_response_type, time.time(), event_id))
            
            conn.commit()
            
            # Check if we should trigger retraining
            cursor.execute("""
                SELECT COUNT(*) FROM gate_events
                WHERE user_override = 1
                AND correction_timestamp > (
                    SELECT COALESCE(MAX(started_at), 0) FROM training_runs
                )
            """)
            pending_corrections = cursor.fetchone()[0]
            conn.close()
            
            # Trigger retraining if threshold met
            if pending_corrections >= self.training_threshold:
                self._trigger_training()
    
    def _trigger_training(self):
        """Trigger background model retraining."""
        if self._training_in_progress:
            return  # Already training
        
        print(f"[ActiveLearning] Triggering retraining (threshold met)")
        self._training_queue.put("TRAIN")
    
    def _start_training_worker(self):
        """Start background worker thread for model training."""
        def worker():
            while True:
                try:
                    msg = self._training_queue.get(timeout=1.0)
                    if msg == "TRAIN":
                        self._run_training()
                except:
                    pass  # Timeout, continue
        
        thread = threading.Thread(target=worker, daemon=True, name="training-worker")
        thread.start()
    
    def _run_training(self):
        """Execute model training in background."""
        with self._lock:
            if self._training_in_progress:
                return
            self._training_in_progress = True
        
        try:
            print(f"[ActiveLearning] Starting model training...")
            
            # Record training run start
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            started_at = time.time()
            
            cursor.execute("""
                INSERT INTO training_runs (started_at, model_version, training_examples)
                VALUES (?, ?, ?)
            """, (started_at, f"v{int(started_at)}", 0))
            run_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Export training data to temp file
            training_file = Path(f"training_data/corrections_{int(started_at)}.jsonl")
            training_file.parent.mkdir(parents=True, exist_ok=True)
            
            self._export_training_data(training_file)
            
            # Run training script
            result = subprocess.run(
                [
                    "python", str(self.training_script),
                    "--input", str(training_file),
                    "--output", str(self.model_path),
                ],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            
            success = result.returncode == 0
            finished_at = time.time()
            
            # Parse accuracy from training output (assumes script prints it)
            accuracy = None
            if success:
                for line in result.stdout.split('\n'):
                    if 'accuracy' in line.lower():
                        try:
                            accuracy = float(line.split(':')[-1].strip().rstrip('%')) / 100
                        except:
                            pass
            
            # Update training run record
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE training_runs
                SET finished_at = ?, success = ?, validation_accuracy = ?,
                    error_message = ?, model_path = ?
                WHERE run_id = ?
            """, (
                finished_at, 1 if success else 0, accuracy,
                result.stderr if not success else None,
                str(self.model_path) if success else None,
                run_id
            ))
            conn.commit()
            conn.close()
            
            if success:
                # Hot-reload the new model
                self._hot_reload_model()
                print(f"[ActiveLearning] Training complete! Accuracy: {accuracy:.1%}")
            else:
                print(f"[ActiveLearning] Training failed: {result.stderr}")
        
        except Exception as e:
            print(f"[ActiveLearning] Training error: {e}")
        
        finally:
            with self._lock:
                self._training_in_progress = False
    
    def _export_training_data(self, output_file: Path):
        """Export corrected examples to JSONL for training."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Get all events with corrections
        cursor.execute("""
            SELECT question, response_type_predicted, response_type_actual,
                   intent_align, memory_align, grounding_score, gates_passed
            FROM gate_events
            WHERE user_override = 1
        """)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for row in cursor.fetchall():
                example = {
                    'question': row[0],
                    'response_type': row[2],  # Use actual (corrected) label
                    'predicted': row[1],
                    'intent_align': row[3],
                    'memory_align': row[4],
                    'grounding_score': row[5],
                    'gates_passed': bool(row[6]),
                }
                f.write(json.dumps(example) + '\n')
        
        conn.close()
    
    def _hot_reload_model(self):
        """Hot-reload new model without restart (thread-safe)."""
        if not self.model_path.exists():
            return
        
        try:
            import joblib
            
            # Load new model
            new_model = joblib.load(self.model_path)
            
            # Atomic swap with lock
            with self._model_lock:
                old_version = self._current_model_version
                self._current_model = new_model
                self._current_model_version = f"v{int(time.time())}"
            
            print(f"[ActiveLearning] Model hot-reloaded: {old_version} → {self._current_model_version}")
            
            # Record new version
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Deactivate old versions
            cursor.execute("UPDATE model_versions SET is_active = 0")
            
            # Add new version
            cursor.execute("""
                INSERT INTO model_versions (version, created_at, model_path, is_active)
                VALUES (?, ?, ?, 1)
            """, (self._current_model_version, time.time(), str(self.model_path)))
            
            conn.commit()
            conn.close()
        
        except Exception as e:
            print(f"[ActiveLearning] Hot-reload failed: {e}")
    
    def get_current_model(self):
        """Get current model (thread-safe read)."""
        with self._model_lock:
            return self._current_model
    
    def predict_response_type(self, question: str) -> str:
        """
        Predict response type using current model.
        
        Falls back to heuristics if no model loaded.
        """
        model = self.get_current_model()
        
        if model is None:
            # Fallback heuristic
            return self._heuristic_response_type(question)
        
        try:
            # Assuming model is sklearn pipeline with predict method
            prediction = model.predict([question])[0]
            return prediction
        except Exception as e:
            print(f"[ActiveLearning] Prediction error: {e}, using fallback")
            return self._heuristic_response_type(question)
    
    def _heuristic_response_type(self, question: str) -> str:
        """Fallback heuristic if no model loaded."""
        q = question.lower().strip()
        
        if any(word in q for word in ['what is my', 'where do i', 'when did i']):
            return "factual"
        elif any(word in q for word in ['how', 'why', 'explain', 'tell me about']):
            return "explanatory"
        else:
            return "conversational"
    
    def get_stats(self, force_refresh: bool = False) -> LearningStats:
        """
        Get current learning statistics.
        
        Cached for performance (5s TTL).
        """
        now = time.time()
        
        if not force_refresh and self._stats_cache and (now - self._stats_cache_time) < self._stats_cache_ttl:
            return self._stats_cache
        
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Total events
            cursor.execute("SELECT COUNT(*) FROM gate_events")
            total_events = cursor.fetchone()[0]
            
            # Total corrections
            cursor.execute("SELECT COUNT(*) FROM gate_events WHERE user_override = 1")
            total_corrections = cursor.fetchone()[0]
            
            # Correction rate
            correction_rate = total_corrections / total_events if total_events > 0 else 0.0
            
            # Training runs
            cursor.execute("SELECT COUNT(*) FROM training_runs WHERE success = 1")
            total_training_runs = cursor.fetchone()[0]
            
            # Last training
            cursor.execute("""
                SELECT started_at, success, validation_accuracy
                FROM training_runs
                ORDER BY started_at DESC
                LIMIT 1
            """)
            last_training = cursor.fetchone()
            last_training_at = last_training[0] if last_training else None
            last_training_success = bool(last_training[1]) if last_training else None
            current_accuracy = last_training[2] if last_training else None
            
            # Pending corrections
            cursor.execute("""
                SELECT COUNT(*) FROM gate_events
                WHERE user_override = 1
                AND correction_timestamp > COALESCE(
                    (SELECT MAX(started_at) FROM training_runs WHERE success = 1),
                    0
                )
            """)
            pending_corrections = cursor.fetchone()[0]
            
            conn.close()
            
            stats = LearningStats(
                total_gate_events=total_events,
                total_corrections=total_corrections,
                correction_rate=correction_rate,
                total_training_runs=total_training_runs,
                last_training_at=last_training_at,
                last_training_success=last_training_success,
                current_model_version=self._current_model_version,
                current_model_accuracy=current_accuracy,
                pending_corrections=pending_corrections,
                next_training_threshold=self.training_threshold,
            )
            
            self._stats_cache = stats
            self._stats_cache_time = now
            
            return stats
    
    def get_recent_corrections(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent user corrections for dashboard display."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT question, response_type_predicted, response_type_actual,
                   gates_passed, correction_timestamp
            FROM gate_events
            WHERE user_override = 1
            ORDER BY correction_timestamp DESC
            LIMIT ?
        """, (limit,))
        
        corrections = []
        for row in cursor.fetchall():
            corrections.append({
                'question': row[0],
                'predicted': row[1],
                'actual': row[2],
                'gates_passed': bool(row[3]),
                'timestamp': row[4],
            })
        
        conn.close()
        return corrections
    
    def get_events_needing_correction(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent gate events that haven't been corrected yet."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT event_id, question, response_type_predicted, gates_passed,
                   intent_score, memory_score, grounding_score, timestamp
            FROM gate_events
            WHERE user_override = 0
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        events = []
        for row in cursor.fetchall():
            events.append({
                'event_id': row[0],
                'user_query': row[1],
                'predicted_type': row[2],
                'gates_passed': bool(row[3]),
                'intent_score': row[4],
                'memory_score': row[5],
                'grounding_score': row[6],
                'timestamp': row[7],
                'correction_submitted': False,
            })
        
        conn.close()
        return events


# Singleton instance for global access
_coordinator: Optional[ActiveLearningCoordinator] = None


def get_active_learning_coordinator() -> ActiveLearningCoordinator:
    """Get or create global coordinator instance."""
    global _coordinator
    if _coordinator is None:
        _coordinator = ActiveLearningCoordinator()
    return _coordinator

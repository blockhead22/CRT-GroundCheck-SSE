"""
Logging Infrastructure for ML Training Data Collection

This module provides the infrastructure for collecting interaction data,
user feedback, and training labels for ML model development.

Philosophy:
- Log everything (but respect privacy)
- Make feedback frictionless
- Extract training labels automatically
- Support continuous learning
"""

import sqlite3
import json
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class FeedbackType(Enum):
    """Types of user feedback."""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    CORRECTION = "correction"
    DISCLOSURE_FLAG = "disclosure_flag"
    POLICY_FEEDBACK = "policy_feedback"


@dataclass
class InteractionLog:
    """Complete record of a single user interaction."""
    
    # Identifiers
    interaction_id: str
    user_id_hash: str  # SHA-256 hash for privacy
    timestamp: str  # ISO 8601 format
    
    # Input
    query: str
    retrieved_memories: List[Dict]  # List of Memory.to_dict()
    
    # Processing
    extracted_facts: Dict[str, Dict]  # slot -> ExtractedFact.to_dict()
    extraction_method: str  # 'regex', 'neural', or 'hybrid'
    extraction_confidence: float
    extraction_latency_ms: float
    
    # Contradictions
    detected_contradictions: List[Dict]  # List of ContradictionDetail.to_dict()
    contradiction_method: str  # 'rule_based', 'nli', or 'hybrid'
    
    # Trust scores
    trust_scores: Dict[str, float]  # memory_id -> trust score
    trust_method: str  # 'rule_based' or 'learned'
    
    # Policy
    applied_policies: Dict[str, str]  # contradiction_id -> policy
    policy_method: str  # 'rule_based' or 'learned'
    
    # Output
    generated_text: str
    verification_passed: bool
    hallucinations: List[str]
    disclosure_required: bool
    
    # Metadata
    model_versions: Dict[str, str]  # component -> version
    total_latency_ms: float
    experiment_group: Optional[str] = None  # A/B test assignment
    
    # Feedback (populated later)
    user_feedback_type: Optional[str] = None
    user_feedback_timestamp: Optional[str] = None
    user_correction: Optional[str] = None
    policy_feedback: Optional[str] = None


@dataclass
class FactExtractionExample:
    """Training example for fact extraction model."""
    
    example_id: str
    text: str
    predicted_facts: Dict[str, Dict]  # What model extracted
    true_facts: Dict[str, Dict]  # Ground truth from feedback
    extraction_method: str
    confidence: float
    feedback_type: str  # 'correction' or 'confirmation'
    timestamp: str


@dataclass
class TrustScoreExample:
    """Training example for trust score model."""
    
    example_id: str
    memory_id: str
    features: Dict[str, float]  # Features used for prediction
    predicted_trust: float
    true_trust: float  # Calculated from outcome
    was_corrected: bool
    days_until_update: Optional[int]
    timestamp: str


@dataclass
class PolicyDecisionExample:
    """Training example for policy learning."""
    
    example_id: str
    contradiction_id: str
    features: Dict[str, float]  # Features for decision
    applied_policy: str
    user_feedback: str  # 'correct', 'over_disclosure', 'under_disclosure', 'wrong_resolution'
    preferred_policy: Optional[str]  # User's preferred policy if provided
    timestamp: str


# =============================================================================
# DATABASE SCHEMA
# =============================================================================

class InteractionDatabase:
    """
    SQLite database for storing interaction logs and training data.
    
    Tables:
    - interactions: All user interactions
    - fact_extraction_examples: Training data for fact extraction
    - trust_score_examples: Training data for trust scores
    - policy_decision_examples: Training data for policy learning
    - experiments: Active A/B tests
    - metrics: Performance metrics over time
    """
    
    def __init__(self, db_path: str = "interactions.db"):
        """
        Initialize database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        
        # Main interactions table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                interaction_id TEXT PRIMARY KEY,
                user_id_hash TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                query TEXT NOT NULL,
                retrieved_memories TEXT,  -- JSON
                extracted_facts TEXT,  -- JSON
                extraction_method TEXT,
                extraction_confidence REAL,
                extraction_latency_ms REAL,
                detected_contradictions TEXT,  -- JSON
                contradiction_method TEXT,
                trust_scores TEXT,  -- JSON
                trust_method TEXT,
                applied_policies TEXT,  -- JSON
                policy_method TEXT,
                generated_text TEXT,
                verification_passed INTEGER,
                hallucinations TEXT,  -- JSON
                disclosure_required INTEGER,
                model_versions TEXT,  -- JSON
                total_latency_ms REAL,
                experiment_group TEXT,
                user_feedback_type TEXT,
                user_feedback_timestamp TEXT,
                user_correction TEXT,
                policy_feedback TEXT
            )
        """)
        
        # Fact extraction training examples
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS fact_extraction_examples (
                example_id TEXT PRIMARY KEY,
                interaction_id TEXT,
                text TEXT NOT NULL,
                predicted_facts TEXT,  -- JSON
                true_facts TEXT,  -- JSON
                extraction_method TEXT,
                confidence REAL,
                feedback_type TEXT,
                timestamp TEXT,
                FOREIGN KEY (interaction_id) REFERENCES interactions(interaction_id)
            )
        """)
        
        # Trust score training examples
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS trust_score_examples (
                example_id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                features TEXT,  -- JSON
                predicted_trust REAL,
                true_trust REAL,
                was_corrected INTEGER,
                days_until_update INTEGER,
                timestamp TEXT
            )
        """)
        
        # Policy decision training examples
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS policy_decision_examples (
                example_id TEXT PRIMARY KEY,
                interaction_id TEXT,
                contradiction_id TEXT,
                features TEXT,  -- JSON
                applied_policy TEXT,
                user_feedback TEXT,
                preferred_policy TEXT,
                timestamp TEXT,
                FOREIGN KEY (interaction_id) REFERENCES interactions(interaction_id)
            )
        """)
        
        # A/B test experiments
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                component TEXT NOT NULL,
                control_version TEXT,
                treatment_version TEXT,
                traffic_percentage REAL,
                start_date TEXT,
                end_date TEXT,
                status TEXT,  -- 'running', 'completed', 'failed'
                results TEXT  -- JSON
            )
        """)
        
        # Performance metrics
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                metric_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                component TEXT NOT NULL,
                version TEXT,
                metric_name TEXT NOT NULL,
                metric_value REAL,
                experiment_id TEXT,
                user_id_hash TEXT
            )
        """)
        
        # Create indices for common queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_interactions_timestamp 
            ON interactions(timestamp)
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_interactions_user 
            ON interactions(user_id_hash)
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_interactions_experiment 
            ON interactions(experiment_group)
        """)
        
        self.conn.commit()


# =============================================================================
# INTERACTION LOGGER
# =============================================================================

class InteractionLogger:
    """
    Logs all system interactions for training data collection.
    
    Features:
    - Privacy-preserving (hashes user IDs)
    - Automatic PII redaction
    - Structured logging
    - Efficient storage
    """
    
    def __init__(self, db_path: str = "interactions.db"):
        """
        Initialize logger.
        
        Args:
            db_path: Path to database
        """
        self.db = InteractionDatabase(db_path)
        
        # Privacy settings
        self.redact_pii = True
        self.hash_user_ids = True
        
        # Performance tracking
        self.log_count = 0
    
    def log_interaction(
        self,
        user_id: str,
        query: str,
        memories: List['Memory'],
        extracted_facts: Dict,
        extraction_metadata: Dict,
        contradictions: List['ContradictionDetail'],
        trust_scores: Dict[str, float],
        policies: Dict[str, str],
        output: str,
        verification: 'VerificationReport',
        metadata: Dict
    ) -> str:
        """
        Log a complete interaction.
        
        Args:
            user_id: User identifier
            query: User query
            memories: Retrieved memories
            extracted_facts: Extracted facts from query
            extraction_metadata: Extraction method, confidence, etc.
            contradictions: Detected contradictions
            trust_scores: Memory trust scores
            policies: Applied policies
            output: Generated output
            verification: Verification report
            metadata: Additional metadata
            
        Returns:
            interaction_id for this log entry
        """
        import uuid
        
        # Generate interaction ID
        interaction_id = str(uuid.uuid4())
        
        # Hash user ID for privacy
        user_id_hash = self._hash_user_id(user_id) if self.hash_user_ids else user_id
        
        # Redact PII if enabled
        if self.redact_pii:
            query = self._redact_pii(query)
            output = self._redact_pii(output)
        
        # Create log entry
        log_entry = InteractionLog(
            interaction_id=interaction_id,
            user_id_hash=user_id_hash,
            timestamp=datetime.now().isoformat(),
            query=query,
            retrieved_memories=[m.to_dict() for m in memories],
            extracted_facts={k: v.to_dict() for k, v in extracted_facts.items()},
            extraction_method=extraction_metadata.get('method', 'unknown'),
            extraction_confidence=extraction_metadata.get('confidence', 0.0),
            extraction_latency_ms=extraction_metadata.get('latency_ms', 0.0),
            detected_contradictions=[c.to_dict() for c in contradictions],
            contradiction_method=metadata.get('contradiction_method', 'rule_based'),
            trust_scores=trust_scores,
            trust_method=metadata.get('trust_method', 'rule_based'),
            applied_policies=policies,
            policy_method=metadata.get('policy_method', 'rule_based'),
            generated_text=output,
            verification_passed=verification.passed,
            hallucinations=verification.hallucinations,
            disclosure_required=verification.requires_disclosure,
            model_versions=metadata.get('model_versions', {}),
            total_latency_ms=metadata.get('total_latency_ms', 0.0),
            experiment_group=metadata.get('experiment_group')
        )
        
        # Store in database
        self._store_interaction(log_entry)
        
        self.log_count += 1
        
        return interaction_id
    
    def update_feedback(
        self,
        interaction_id: str,
        feedback_type: FeedbackType,
        correction: Optional[str] = None,
        policy_feedback: Optional[str] = None
    ):
        """
        Add user feedback to existing interaction.
        
        Args:
            interaction_id: ID of interaction to update
            feedback_type: Type of feedback
            correction: Corrected text (if applicable)
            policy_feedback: Policy feedback (if applicable)
        """
        self.db.conn.execute("""
            UPDATE interactions
            SET user_feedback_type = ?,
                user_feedback_timestamp = ?,
                user_correction = ?,
                policy_feedback = ?
            WHERE interaction_id = ?
        """, (
            feedback_type.value,
            datetime.now().isoformat(),
            correction,
            policy_feedback,
            interaction_id
        ))
        
        self.db.conn.commit()
        
        # Extract training examples from feedback
        self._extract_training_examples(interaction_id, feedback_type, correction)
    
    def _store_interaction(self, log: InteractionLog):
        """Store interaction in database."""
        self.db.conn.execute("""
            INSERT INTO interactions VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            log.interaction_id,
            log.user_id_hash,
            log.timestamp,
            log.query,
            json.dumps(log.retrieved_memories),
            json.dumps(log.extracted_facts),
            log.extraction_method,
            log.extraction_confidence,
            log.extraction_latency_ms,
            json.dumps(log.detected_contradictions),
            log.contradiction_method,
            json.dumps(log.trust_scores),
            log.trust_method,
            json.dumps(log.applied_policies),
            log.policy_method,
            log.generated_text,
            1 if log.verification_passed else 0,
            json.dumps(log.hallucinations),
            1 if log.disclosure_required else 0,
            json.dumps(log.model_versions),
            log.total_latency_ms,
            log.experiment_group,
            log.user_feedback_type,
            log.user_feedback_timestamp,
            log.user_correction,
            log.policy_feedback
        ))
        
        self.db.conn.commit()
    
    def _hash_user_id(self, user_id: str) -> str:
        """Hash user ID for privacy."""
        return hashlib.sha256(user_id.encode()).hexdigest()
    
    def _redact_pii(self, text: str) -> str:
        """
        Redact PII from text.
        
        Replace names, emails, phone numbers with placeholders.
        """
        import re
        
        # Email addresses
        text = re.sub(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            '[EMAIL]',
            text
        )
        
        # Phone numbers
        text = re.sub(
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            '[PHONE]',
            text
        )
        
        # Social Security Numbers
        text = re.sub(
            r'\b\d{3}-\d{2}-\d{4}\b',
            '[SSN]',
            text
        )
        
        return text
    
    def _extract_training_examples(
        self,
        interaction_id: str,
        feedback_type: FeedbackType,
        correction: Optional[str]
    ):
        """Extract training examples from feedback."""
        
        # Get original interaction
        cursor = self.db.conn.execute("""
            SELECT query, extracted_facts, extraction_method, extraction_confidence
            FROM interactions
            WHERE interaction_id = ?
        """, (interaction_id,))
        
        row = cursor.fetchone()
        if not row:
            return
        
        query, extracted_facts_json, method, confidence = row
        extracted_facts = json.loads(extracted_facts_json)
        
        # Create training example based on feedback type
        if feedback_type == FeedbackType.THUMBS_UP:
            # Positive example: predicted facts are correct
            self._add_fact_extraction_example(
                interaction_id=interaction_id,
                text=query,
                predicted_facts=extracted_facts,
                true_facts=extracted_facts,  # Confirmed correct
                method=method,
                confidence=confidence,
                feedback_type='confirmation'
            )
        
        elif feedback_type == FeedbackType.CORRECTION and correction:
            # Negative example: extract true facts from correction
            from groundcheck.fact_extractor import extract_fact_slots
            
            true_facts = extract_fact_slots(correction)
            
            self._add_fact_extraction_example(
                interaction_id=interaction_id,
                text=query,
                predicted_facts=extracted_facts,
                true_facts={k: v.to_dict() for k, v in true_facts.items()},
                method=method,
                confidence=confidence,
                feedback_type='correction'
            )
    
    def _add_fact_extraction_example(
        self,
        interaction_id: str,
        text: str,
        predicted_facts: Dict,
        true_facts: Dict,
        method: str,
        confidence: float,
        feedback_type: str
    ):
        """Add fact extraction training example."""
        import uuid
        
        example_id = str(uuid.uuid4())
        
        self.db.conn.execute("""
            INSERT INTO fact_extraction_examples VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            example_id,
            interaction_id,
            text,
            json.dumps(predicted_facts),
            json.dumps(true_facts),
            method,
            confidence,
            feedback_type,
            datetime.now().isoformat()
        ))
        
        self.db.conn.commit()


# =============================================================================
# TRAINING DATASET BUILDER
# =============================================================================

class TrainingDatasetBuilder:
    """
    Build training datasets from logged interactions.
    
    Capabilities:
    - Fact extraction dataset
    - Trust score dataset
    - Policy learning dataset
    - Data augmentation
    - Train/val/test splits
    """
    
    def __init__(self, db_path: str = "interactions.db"):
        """
        Initialize dataset builder.
        
        Args:
            db_path: Path to database
        """
        self.db = InteractionDatabase(db_path)
    
    def build_fact_extraction_dataset(
        self,
        min_examples: int = 1000
    ) -> Dict[str, List]:
        """
        Build dataset for fact extraction model.
        
        Args:
            min_examples: Minimum examples required
            
        Returns:
            Dict with 'train', 'val', 'test' splits
        """
        # Query all fact extraction examples
        cursor = self.db.conn.execute("""
            SELECT text, predicted_facts, true_facts, feedback_type
            FROM fact_extraction_examples
            ORDER BY timestamp DESC
        """)
        
        examples = []
        for row in cursor.fetchall():
            text, predicted_json, true_json, feedback_type = row
            examples.append({
                'text': text,
                'predicted_facts': json.loads(predicted_json),
                'true_facts': json.loads(true_json),
                'feedback_type': feedback_type
            })
        
        if len(examples) < min_examples:
            raise ValueError(
                f"Not enough examples: {len(examples)}/{min_examples}"
            )
        
        # Split: 80% train, 10% val, 10% test
        train_size = int(0.8 * len(examples))
        val_size = int(0.1 * len(examples))
        
        return {
            'train': examples[:train_size],
            'val': examples[train_size:train_size+val_size],
            'test': examples[train_size+val_size:]
        }
    
    def build_trust_score_dataset(self) -> List[Dict]:
        """Build dataset for trust score model."""
        cursor = self.db.conn.execute("""
            SELECT features, predicted_trust, true_trust, was_corrected
            FROM trust_score_examples
            ORDER BY timestamp DESC
        """)
        
        examples = []
        for row in cursor.fetchall():
            features_json, predicted, true, corrected = row
            examples.append({
                'features': json.loads(features_json),
                'predicted_trust': predicted,
                'true_trust': true,
                'was_corrected': bool(corrected)
            })
        
        return examples
    
    def build_policy_dataset(self) -> List[Dict]:
        """Build dataset for policy learning."""
        cursor = self.db.conn.execute("""
            SELECT features, applied_policy, user_feedback, preferred_policy
            FROM policy_decision_examples
            WHERE user_feedback IS NOT NULL
            ORDER BY timestamp DESC
        """)
        
        examples = []
        for row in cursor.fetchall():
            features_json, applied, feedback, preferred = row
            
            # Determine label
            if preferred:
                label = preferred
            elif feedback == 'correct':
                label = applied
            else:
                label = self._infer_correct_policy(feedback, applied)
            
            examples.append({
                'features': json.loads(features_json),
                'label': label,
                'feedback': feedback
            })
        
        return examples
    
    def _infer_correct_policy(
        self,
        feedback: str,
        applied_policy: str
    ) -> str:
        """Infer correct policy from negative feedback."""
        # Map feedback to correct policy
        feedback_to_policy = {
            'over_disclosure': 'prefer_newer',  # Don't disclose for minor changes
            'under_disclosure': 'require_disclosure',  # Should have disclosed
            'wrong_resolution': 'ask_user'  # Let user decide
        }
        
        return feedback_to_policy.get(feedback, applied_policy)


# =============================================================================
# METRICS TRACKER
# =============================================================================

class MetricsTracker:
    """
    Track model performance metrics over time.
    
    Metrics:
    - Accuracy (fact extraction, contradiction detection)
    - Latency (p50, p95, p99)
    - User satisfaction
    - Error rates
    """
    
    def __init__(self, db_path: str = "interactions.db"):
        """
        Initialize metrics tracker.
        
        Args:
            db_path: Path to database
        """
        self.db = InteractionDatabase(db_path)
    
    def record_metric(
        self,
        component: str,
        version: str,
        metric_name: str,
        metric_value: float,
        experiment_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """
        Record a metric value.
        
        Args:
            component: Component name (e.g., 'fact_extraction')
            version: Model version
            metric_name: Metric name (e.g., 'accuracy', 'latency_p95')
            metric_value: Metric value
            experiment_id: Optional experiment ID
            user_id: Optional user ID
        """
        import uuid
        
        metric_id = str(uuid.uuid4())
        user_id_hash = hashlib.sha256(user_id.encode()).hexdigest() if user_id else None
        
        self.db.conn.execute("""
            INSERT INTO metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metric_id,
            datetime.now().isoformat(),
            component,
            version,
            metric_name,
            metric_value,
            experiment_id,
            user_id_hash
        ))
        
        self.db.conn.commit()
    
    def get_metrics(
        self,
        component: str,
        metric_name: str,
        version: Optional[str] = None,
        days: int = 7
    ) -> List[float]:
        """
        Get metric values for time period.
        
        Args:
            component: Component name
            metric_name: Metric name
            version: Optional model version filter
            days: Number of days to look back
            
        Returns:
            List of metric values
        """
        from datetime import timedelta
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        if version:
            cursor = self.db.conn.execute("""
                SELECT metric_value
                FROM metrics
                WHERE component = ? AND metric_name = ? 
                  AND version = ? AND timestamp >= ?
            """, (component, metric_name, version, cutoff))
        else:
            cursor = self.db.conn.execute("""
                SELECT metric_value
                FROM metrics
                WHERE component = ? AND metric_name = ? AND timestamp >= ?
            """, (component, metric_name, cutoff))
        
        return [row[0] for row in cursor.fetchall()]
    
    def get_average_metric(
        self,
        component: str,
        metric_name: str,
        version: Optional[str] = None,
        days: int = 7
    ) -> float:
        """Get average metric value."""
        values = self.get_metrics(component, metric_name, version, days)
        return sum(values) / len(values) if values else 0.0


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

def example_usage():
    """Example of how to use the logging infrastructure."""
    
    # Initialize logger
    logger = InteractionLogger(db_path="production.db")
    
    # Log an interaction
    interaction_id = logger.log_interaction(
        user_id="user_123",
        query="I work at Microsoft",
        memories=[],  # Retrieved memories
        extracted_facts={'employer': ExtractedFact('employer', 'Microsoft', 'microsoft')},
        extraction_metadata={'method': 'regex', 'confidence': 0.95, 'latency_ms': 1.2},
        contradictions=[],
        trust_scores={},
        policies={},
        output="You work at Microsoft.",
        verification=VerificationReport(passed=True, hallucinations=[]),
        metadata={'model_versions': {'fact_extraction': 'regex_v1'}}
    )
    
    # Later: User provides feedback
    logger.update_feedback(
        interaction_id=interaction_id,
        feedback_type=FeedbackType.THUMBS_UP,
        correction=None
    )
    
    # Build training dataset (after collecting 1000+ examples)
    dataset_builder = TrainingDatasetBuilder(db_path="production.db")
    dataset = dataset_builder.build_fact_extraction_dataset(min_examples=1000)
    
    print(f"Training examples: {len(dataset['train'])}")
    print(f"Validation examples: {len(dataset['val'])}")
    print(f"Test examples: {len(dataset['test'])}")
    
    # Track metrics
    metrics = MetricsTracker(db_path="production.db")
    metrics.record_metric(
        component='fact_extraction',
        version='regex_v1',
        metric_name='accuracy',
        metric_value=0.85
    )
    
    # Get average accuracy over last 7 days
    avg_accuracy = metrics.get_average_metric(
        component='fact_extraction',
        metric_name='accuracy',
        days=7
    )
    print(f"Average accuracy (7 days): {avg_accuracy:.2%}")


if __name__ == "__main__":
    example_usage()

#!/usr/bin/env python3
"""
CRT Probability Calibration System.

Provides probabilistic fact validation using logistic regression instead of
hard thresholds. This enables:
1. Smooth probability curves instead of binary decisions
2. Feature-based validation (similarity, recency, confidence, action type)
3. Online learning from user feedback
4. Yellow zone routing for uncertain cases

Usage:
    from tools.crt_calibration import ProbabilityCalibrator, YellowZoneHandler
    
    calibrator = ProbabilityCalibrator()
    prob = calibrator.predict_probability(claimed_fact, memory_facts)
    
    handler = YellowZoneHandler()
    action = handler.handle_uncertain_fact(claimed_fact, prob)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable

import numpy as np

logger = logging.getLogger(__name__)

# Try to import sklearn, but make it optional
try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    logger.warning("sklearn not available - probability calibration limited")

# Try to import joblib for model persistence, but make it optional
try:
    import joblib
    HAS_JOBLIB = True
except ImportError:
    HAS_JOBLIB = False
    logger.warning("joblib not available - model persistence disabled")
try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    logger.warning("sklearn not available - probability calibration limited")


@dataclass
class ValidationFeatures:
    """
    Features extracted for fact validation.
    
    These features are used by the logistic regression model to predict
    P(valid) for a claimed fact.
    """
    cosine_similarity: float = 0.0
    recency_score: float = 0.0
    memory_confidence: float = 0.0
    claimed_confidence: float = 0.0
    action_is_add: float = 0.0
    action_is_update: float = 0.0
    action_is_deprecate: float = 0.0
    slot_is_high_stakes: float = 0.0
    entity_match: float = 0.0
    attribute_match: float = 0.0
    
    def to_array(self) -> np.ndarray:
        """Convert to numpy array for model input."""
        return np.array([
            self.cosine_similarity,
            self.recency_score,
            self.memory_confidence,
            self.claimed_confidence,
            self.action_is_add,
            self.action_is_update,
            self.action_is_deprecate,
            self.slot_is_high_stakes,
            self.entity_match,
            self.attribute_match,
        ])
    
    @classmethod
    def feature_names(cls) -> List[str]:
        """Get list of feature names in order."""
        return [
            "cosine_similarity",
            "recency_score",
            "memory_confidence",
            "claimed_confidence",
            "action_is_add",
            "action_is_update",
            "action_is_deprecate",
            "slot_is_high_stakes",
            "entity_match",
            "attribute_match",
        ]


class ProbabilityCalibrator:
    """
    Predicts P(valid) for claimed facts using logistic regression.
    
    Instead of hard thresholds, this calibrator outputs smooth probabilities
    that can be used for nuanced decision-making.
    
    Features used:
    - Cosine similarity between claimed and memory values
    - Recency score of memory (newer = higher weight)
    - Confidence scores from both claimed and memory facts
    - Action type (add/update/deprecate)
    - Whether the slot is high-stakes
    - Entity and attribute match scores
    
    Example:
        >>> calibrator = ProbabilityCalibrator()
        >>> calibrator.train(labeled_data)
        >>> prob = calibrator.predict_probability(claimed, memory_facts)
        >>> print(f"P(valid) = {prob:.2f}")
    """
    
    # High-stakes attributes that affect validation
    HIGH_STAKES_SLOTS: set = {
        "name", "employer", "medical_diagnosis", "medication",
        "legal_status", "account_balance", "age",
    }
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        similarity_func: Optional[Callable[[str, str], float]] = None,
    ):
        """
        Initialize probability calibrator.
        
        Args:
            model_path: Path to saved model (optional)
            similarity_func: Function to compute similarity (optional)
        """
        self.model = None
        self.scaler = None
        self._similarity_func = similarity_func
        self._embedding_model = None
        
        if model_path and Path(model_path).exists():
            self.load(model_path)
    
    def _get_similarity_func(self) -> Callable[[str, str], float]:
        """Get or create similarity function."""
        if self._similarity_func is not None:
            return self._similarity_func
        
        # Load embedding model lazily
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            except ImportError:
                # Fallback to string matching
                return self._string_similarity
        
        def embedding_similarity(text1: str, text2: str) -> float:
            emb1 = self._embedding_model.encode(text1, convert_to_numpy=True)
            emb2 = self._embedding_model.encode(text2, convert_to_numpy=True)
            return float(np.dot(emb1, emb2) / (
                np.linalg.norm(emb1) * np.linalg.norm(emb2)
            ))
        
        return embedding_similarity
    
    def _string_similarity(self, text1: str, text2: str) -> float:
        """Simple string similarity fallback."""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _compute_recency_score(
        self,
        timestamp: float,
        max_age_days: float = 365,
    ) -> float:
        """
        Compute recency score (0-1) based on timestamp.
        
        Newer = higher score using exponential decay.
        """
        age_seconds = time.time() - timestamp
        age_days = age_seconds / 86400
        
        # Exponential decay with half-life of 30 days
        half_life = 30
        return float(np.exp(-age_days * np.log(2) / half_life))
    
    def extract_features(
        self,
        claimed_value: str,
        claimed_confidence: float,
        claimed_action: str,
        claimed_attribute: str,
        memory_value: str,
        memory_confidence: float,
        memory_timestamp: float,
        memory_entity: str = "User",
        claimed_entity: str = "User",
    ) -> ValidationFeatures:
        """
        Extract features for validation.
        
        Args:
            claimed_value: Value from the claim
            claimed_confidence: Confidence of the claim
            claimed_action: Action type (add, update, deprecate)
            claimed_attribute: Attribute being claimed
            memory_value: Value from memory
            memory_confidence: Confidence of memory
            memory_timestamp: Timestamp of memory
            memory_entity: Entity in memory
            claimed_entity: Entity in claim
            
        Returns:
            ValidationFeatures object
        """
        sim_func = self._get_similarity_func()
        
        # Compute similarity
        similarity = sim_func(claimed_value, memory_value)
        
        # Recency score
        recency = self._compute_recency_score(memory_timestamp)
        
        # Action type one-hot encoding
        action_lower = claimed_action.lower()
        
        # High stakes check
        is_high_stakes = 1.0 if claimed_attribute in self.HIGH_STAKES_SLOTS else 0.0
        
        # Entity match
        entity_match = 1.0 if claimed_entity.lower() == memory_entity.lower() else 0.0
        
        # Attribute match (simplified - same string)
        attribute_match = 1.0  # Assumed same attribute if we're comparing
        
        return ValidationFeatures(
            cosine_similarity=similarity,
            recency_score=recency,
            memory_confidence=memory_confidence,
            claimed_confidence=claimed_confidence,
            action_is_add=1.0 if action_lower == "add" else 0.0,
            action_is_update=1.0 if action_lower == "update" else 0.0,
            action_is_deprecate=1.0 if action_lower == "deprecate" else 0.0,
            slot_is_high_stakes=is_high_stakes,
            entity_match=entity_match,
            attribute_match=attribute_match,
        )
    
    def train(
        self,
        labeled_data: List[Tuple[ValidationFeatures, int]],
    ) -> Dict[str, Any]:
        """
        Train the logistic regression model.
        
        Args:
            labeled_data: List of (features, label) where label is 0 or 1
            
        Returns:
            Training metrics
        """
        if not HAS_SKLEARN:
            raise RuntimeError("sklearn is required for training")
        
        if len(labeled_data) < 10:
            raise ValueError("Need at least 10 training examples")
        
        # Prepare data
        X = np.array([f.to_array() for f, _ in labeled_data])
        y = np.array([label for _, label in labeled_data])
        
        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Train model
        self.model = LogisticRegression(
            C=1.0,
            max_iter=1000,
            class_weight='balanced',
        )
        self.model.fit(X_scaled, y)
        
        # Compute metrics
        y_pred = self.model.predict(X_scaled)
        accuracy = float(np.mean(y_pred == y))
        
        # Feature importances (coefficients)
        feature_names = ValidationFeatures.feature_names()
        importances = dict(zip(feature_names, self.model.coef_[0].tolist()))
        
        logger.info(f"Trained model with accuracy: {accuracy:.3f}")
        
        return {
            "accuracy": accuracy,
            "n_samples": len(labeled_data),
            "feature_importances": importances,
        }
    
    def predict_probability(
        self,
        features: ValidationFeatures,
    ) -> float:
        """
        Predict P(valid) for given features.
        
        Args:
            features: Extracted validation features
            
        Returns:
            Probability between 0 and 1
        """
        if self.model is None:
            # Fallback to similarity-based heuristic
            return self._heuristic_probability(features)
        
        X = features.to_array().reshape(1, -1)
        X_scaled = self.scaler.transform(X)
        prob = float(self.model.predict_proba(X_scaled)[0][1])
        
        return prob
    
    def _heuristic_probability(self, features: ValidationFeatures) -> float:
        """
        Fallback heuristic when model is not trained.
        
        Uses a simple weighted combination of features.
        """
        # Weighted combination
        prob = (
            features.cosine_similarity * 0.5 +
            features.recency_score * 0.2 +
            features.memory_confidence * 0.15 +
            features.claimed_confidence * 0.15
        )
        
        # Clamp to valid range
        return max(0.0, min(1.0, prob))
    
    def save(self, path: str) -> None:
        """Save model to file."""
        if self.model is None:
            raise ValueError("No model to save")
        
        if not HAS_JOBLIB:
            raise RuntimeError("joblib is required for model persistence")
        
        data = {
            "model": self.model,
            "scaler": self.scaler,
            "version": "1.0",
        }
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(data, path)
        logger.info(f"Saved model to {path}")
    
    def load(self, path: str) -> None:
        """Load model from file."""
        if not HAS_JOBLIB:
            raise RuntimeError("joblib is required for model persistence")
        
        data = joblib.load(path)
        self.model = data["model"]
        self.scaler = data["scaler"]
        logger.info(f"Loaded model from {path}")


class YellowZoneHandler:
    """
    Handles uncertain facts that fall in the "yellow zone" probability range.
    
    Yellow zone is defined as facts with P(valid) between 0.4 and 0.9.
    These cases require additional handling:
    1. Ask user for confirmation
    2. Log for manual review
    3. Apply lower confidence
    
    Example:
        >>> handler = YellowZoneHandler()
        >>> action = handler.handle_uncertain_fact(fact, 0.65)
        >>> print(action)  # "ask_user"
    """
    
    # Default zone boundaries (tuned for reduced over-flagging)
    GREEN_THRESHOLD = 0.75  # Above this = accept
    RED_THRESHOLD = 0.30    # Below this = reject
    
    def __init__(
        self,
        green_threshold: float = 0.75,
        red_threshold: float = 0.30,
        confirmation_callback: Optional[Callable[[Any], bool]] = None,
    ):
        """
        Initialize yellow zone handler.
        
        Args:
            green_threshold: P(valid) above this = accept
            red_threshold: P(valid) below this = reject
            confirmation_callback: Optional callback for user confirmation
        """
        self.green_threshold = green_threshold
        self.red_threshold = red_threshold
        self._confirmation_callback = confirmation_callback
    
    def handle_uncertain_fact(
        self,
        fact: Any,
        probability: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Determine action for a fact with uncertain probability.
        
        Args:
            fact: The fact being evaluated
            probability: P(valid) from the calibrator
            context: Optional context information
            
        Returns:
            Action string: "accept", "reject", "ask_user", or "log_for_review"
        """
        # Green zone: Accept
        if probability >= self.green_threshold:
            return "accept"
        
        # Red zone: Reject
        if probability < self.red_threshold:
            return "reject"
        
        # Yellow zone: Uncertain
        # Check if we can ask the user
        if self._confirmation_callback is not None:
            return "ask_user"
        
        # Check context for high-stakes
        if context and context.get("is_high_stakes"):
            return "ask_user"
        
        # Default: log for review but proceed with caution
        return "log_for_review"
    
    def get_confidence_adjustment(self, probability: float) -> float:
        """
        Get confidence adjustment factor for yellow zone facts.
        
        Facts in the yellow zone should have reduced confidence.
        
        Args:
            probability: P(valid) from calibrator
            
        Returns:
            Confidence multiplier (0.5 - 1.0)
        """
        if probability >= self.green_threshold:
            return 1.0
        if probability < self.red_threshold:
            return 0.0
        
        # Linear interpolation in yellow zone
        range_size = self.green_threshold - self.red_threshold
        position = (probability - self.red_threshold) / range_size
        
        # Map to 0.5 - 1.0 range
        return 0.5 + 0.5 * position


@dataclass
class OnlineLearningState:
    """State for online learning from user feedback."""
    training_data: List[Tuple[ValidationFeatures, int]] = field(default_factory=list)
    feedback_count: int = 0
    last_retrain_at: int = 0
    retrain_interval: int = 100  # Retrain every N feedback samples


class OnlineCalibration:
    """
    Online learning from user feedback.
    
    Records user confirmations/rejections and periodically retrains
    the probability calibrator to improve over time.
    
    Example:
        >>> online = OnlineCalibration(calibrator)
        >>> online.record_feedback(features, user_confirmed=True)
        >>> # After enough feedback, model is automatically retrained
    """
    
    def __init__(
        self,
        calibrator: ProbabilityCalibrator,
        retrain_interval: int = 100,
        min_samples_for_retrain: int = 50,
    ):
        """
        Initialize online learning.
        
        Args:
            calibrator: The probability calibrator to update
            retrain_interval: Retrain model every N feedback samples
            min_samples_for_retrain: Minimum samples needed to retrain
        """
        self.calibrator = calibrator
        self.state = OnlineLearningState(retrain_interval=retrain_interval)
        self.min_samples = min_samples_for_retrain
    
    def record_feedback(
        self,
        features: ValidationFeatures,
        user_confirmed: bool,
    ) -> bool:
        """
        Record user feedback on a fact validation.
        
        Args:
            features: Features of the validated fact
            user_confirmed: True if user confirmed, False if rejected
            
        Returns:
            True if model was retrained
        """
        label = 1 if user_confirmed else 0
        self.state.training_data.append((features, label))
        self.state.feedback_count += 1
        
        # Check if we should retrain
        samples_since_retrain = (
            self.state.feedback_count - self.state.last_retrain_at
        )
        
        if (samples_since_retrain >= self.state.retrain_interval and
            len(self.state.training_data) >= self.min_samples):
            return self._retrain()
        
        return False
    
    def _retrain(self) -> bool:
        """Retrain the calibrator with accumulated feedback."""
        if not HAS_SKLEARN:
            logger.warning("sklearn not available - cannot retrain")
            return False
        
        try:
            metrics = self.calibrator.train(self.state.training_data)
            self.state.last_retrain_at = self.state.feedback_count
            
            logger.info(
                f"Retrained calibrator with {len(self.state.training_data)} samples. "
                f"Accuracy: {metrics['accuracy']:.3f}"
            )
            return True
            
        except Exception as e:
            logger.warning(f"Failed to retrain: {e}")
            return False
    
    def save_state(self, path: str) -> None:
        """Save online learning state."""
        data = {
            "training_data": [
                (f.to_array().tolist(), label)
                for f, label in self.state.training_data
            ],
            "feedback_count": self.state.feedback_count,
            "last_retrain_at": self.state.last_retrain_at,
        }
        
        with open(path, 'w') as f:
            json.dump(data, f)
    
    def load_state(self, path: str) -> None:
        """Load online learning state."""
        with open(path) as f:
            data = json.load(f)
        
        # Reconstruct training data
        self.state.training_data = []
        for arr, label in data["training_data"]:
            features = ValidationFeatures(
                cosine_similarity=arr[0],
                recency_score=arr[1],
                memory_confidence=arr[2],
                claimed_confidence=arr[3],
                action_is_add=arr[4],
                action_is_update=arr[5],
                action_is_deprecate=arr[6],
                slot_is_high_stakes=arr[7],
                entity_match=arr[8],
                attribute_match=arr[9],
            )
            self.state.training_data.append((features, label))
        
        self.state.feedback_count = data["feedback_count"]
        self.state.last_retrain_at = data["last_retrain_at"]

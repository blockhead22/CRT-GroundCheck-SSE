"""
ML-Based Contradiction Detection

Uses trained XGBoost models from Phase 2/3 to detect contradictions
and recommend resolution policies.

Replaces hardcoded slot checks with semantic ML classification.
"""

import pickle
import numpy as np
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Set
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import time

logger = logging.getLogger(__name__)


# ============================================================================
# RETRACTION PATTERN DETECTION
# Patterns that indicate a user is retracting a denial (double negative)
# Organized in pairs: comma variant, space variant
# ============================================================================

RETRACTION_PATTERNS = [
    "actually no,", "actually no ",
    "wait no,", "wait no ",
    "no wait,", "no wait "
]


def _has_retraction_pattern(text: str) -> bool:
    """
    Check if text contains a retraction pattern.
    
    Args:
        text: The text to check (should be lowercase)
    
    Returns:
        True if text starts with or contains a retraction pattern
    """
    return any(text.startswith(pattern) or f" {pattern}" in text 
               for pattern in RETRACTION_PATTERNS)


def _extract_remainder_after_retraction(text: str) -> str:
    """
    Extract the text content after a retraction pattern.
    
    Args:
        text: The text to parse (should be lowercase)
    
    Returns:
        The remainder of text after the first matching retraction pattern,
        or the original text if no pattern matches
    """
    for pattern in RETRACTION_PATTERNS:
        if pattern in text:
            return text.split(pattern, 1)[-1]
    return text


def _is_meaningful_substring(substring: str, full_text: str) -> bool:
    """
    Check if substring match is meaningful (enrichment) vs accidental word sharing.
    
    Args:
        substring: The shorter text
        full_text: The longer text containing substring
    
    Returns:
        True if this is a meaningful substring match (detail enrichment)
    """
    # Long substrings are always meaningful
    if len(substring) > 5:
        return True
    # Short substrings must be at start or end to be meaningful
    # E.g., "dog" at start of "dog named Max" or "Max the dog" at end
    return full_text.startswith(substring) or full_text.endswith(substring)


# ============================================================================
# SEMANTIC EQUIVALENCE DATABASE
# These synonyms/related terms should NOT trigger contradiction
# ============================================================================

SEMANTIC_EQUIVALENTS: Dict[str, Set[str]] = {
    # Education degree synonyms
    "phd": {"doctorate", "doctoral", "ph.d.", "doctor of philosophy", "doctoral degree"},
    "doctorate": {"phd", "doctoral", "ph.d.", "doctor of philosophy"},
    "masters": {"master's", "ms", "ma", "msc", "master of science", "master of arts"},
    "bachelor": {"bachelor's", "bs", "ba", "bsc", "undergraduate"},
    
    # Related fields (changing focus within field is refinement, not contradiction)
    "ml": {"machine learning", "ai", "artificial intelligence", "deep learning"},
    "ai": {"artificial intelligence", "ml", "machine learning", "deep learning"},
    "cs": {"computer science", "computing", "comp sci"},
    "data science": {"data analytics", "analytics", "data engineering"},
    
    # Job title synonyms
    "developer": {"engineer", "programmer", "coder", "software engineer"},
    "engineer": {"developer", "programmer", "software developer"},
    "scientist": {"researcher", "analyst"},
    
    # Relationship terms
    "married": {"spouse", "husband", "wife", "partner"},
    "dog": {"pup", "puppy", "pet", "canine"},
    "cat": {"kitty", "kitten", "pet", "feline"},
}

# Detail enrichment words - adding these is NOT contradiction
DETAIL_ENRICHMENT_WORDS = {
    "rescue", "adopted", "beloved", "new", "old", "favorite",
    "senior", "junior", "lead", "chief", "principal", "staff",
    "golden", "black", "white", "brown",  # Pet colors
    "downtown", "metro", "greater",  # Location refinements
}


def _is_semantic_equivalent(old_value: str, new_value: str) -> bool:
    """
    Check if two values are semantically equivalent (not a contradiction).
    
    Examples that should return True:
    - "PhD" vs "doctorate" (synonyms)
    - "ML" vs "Machine Learning" (abbreviation)
    - "dog" vs "rescue dog" (enrichment)
    
    This should NOT match:
    - "PhD" vs "Master's" (different degrees)
    - "Google" vs "Microsoft" (different companies)
    """
    old_lower = str(old_value).lower().strip()
    new_lower = str(new_value).lower().strip()
    
    # Exact match
    if old_lower == new_lower:
        return True
    
    # One is substring of other (detail enrichment)
    # E.g., "dog" → "rescue dog" is enrichment, not contradiction
    if old_lower in new_lower:
        # old is substring of new
        if _is_meaningful_substring(old_lower, new_lower):
            return True
    elif new_lower in old_lower:
        # new is substring of old  
        if _is_meaningful_substring(new_lower, old_lower):
            return True
    
    # Check synonym database
    old_words = set(old_lower.split())
    new_words = set(new_lower.split())
    
    for key, synonyms in SEMANTIC_EQUIVALENTS.items():
        all_forms = {key} | synonyms
        # Check both word-level and phrase-level matching
        # Word-level: check if any word from synonym set is in the text
        old_has = bool(old_words & all_forms)
        new_has = bool(new_words & all_forms)
        # Phrase-level: check if multi-word synonym appears as substring
        if not (old_has and new_has):
            for form in all_forms:
                if ' ' in form:  # Multi-word synonym like "machine learning"
                    if form in old_lower:
                        old_has = True
                    if form in new_lower:
                        new_has = True
        
        if old_has and new_has:
            # Both values contain words/phrases from the same synonym set
            return True
    
    return False


def _is_detail_enrichment(old_value: str, new_value: str) -> bool:
    """
    Check if new_value is enriching old_value, not contradicting it.
    
    Examples:
    - "dog" → "rescue dog" (enrichment)
    - "Max" → "Max, our golden retriever" (enrichment)
    - "Jordan" → "Jordan, who works at Google" (enrichment)
    """
    old_lower = str(old_value).lower().strip()
    new_lower = str(new_value).lower().strip()
    
    # If old value appears in new value, likely enrichment
    if old_lower in new_lower:
        return True
    
    # Check for common enrichment patterns
    old_words = set(old_lower.split())
    new_words = set(new_lower.split())
    
    # If new has all old words plus some, check if added words are enrichment
    if old_words.issubset(new_words):
        added_words = new_words - old_words
        if added_words & DETAIL_ENRICHMENT_WORDS:
            return True
        # If just adding 1-2 descriptive words, likely enrichment
        if len(added_words) <= 2:
            return True
    
    return False


class MLContradictionDetector:
    """
    ML-based contradiction detector using Phase 2/3 trained models.
    
    Replaces hardcoded slot whitelist with semantic classification.
    """
    
    def __init__(self, model_dir: Optional[Path] = None):
        """
        Initialize ML detector with trained models.
        
        Args:
            model_dir: Directory containing trained models. 
                      Defaults to belief_revision/models/
        """
        if model_dir is None:
            model_dir = Path(__file__).parent.parent / "belief_revision" / "models"
        
        self.model_dir = Path(model_dir)
        
        # Load trained models
        self.belief_classifier = None
        self.policy_classifier = None
        self._load_models()
        
        # TF-IDF vectorizer for semantic similarity
        self.vectorizer = TfidfVectorizer(max_features=100)
    
    def _load_models(self):
        """Load trained XGBoost models."""
        try:
            # Verify xgboost is available
            try:
                import xgboost
            except ImportError:
                logger.error(
                    "⚠ xgboost not installed. Install with: pip install xgboost>=1.7.0\n"
                    "Falling back to heuristic contradiction detection."
                )
                return
            
            # Load belief category classifier
            belief_path = self.model_dir / "xgboost.pkl"
            if belief_path.exists():
                with open(belief_path, "rb") as f:
                    self.belief_classifier = pickle.load(f)
                logger.info(f"✓ Loaded belief classifier: {belief_path}")
            else:
                logger.warning(f"⚠ Belief classifier not found: {belief_path}")
            
            # Load policy classifier
            policy_path = self.model_dir / "policy_xgboost.pkl"
            if policy_path.exists():
                with open(policy_path, "rb") as f:
                    self.policy_classifier = pickle.load(f)
                logger.info(f"✓ Loaded policy classifier: {policy_path}")
            else:
                logger.warning(f"⚠ Policy classifier not found: {policy_path}")
        
        except Exception as e:
            logger.error(f"Failed to load ML models: {e}", exc_info=True)
    
    def check_contradiction(
        self,
        old_value: str,
        new_value: str,
        slot: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check if new value contradicts old value using ML classifier.
        
        Args:
            old_value: Previous belief text
            new_value: New belief text
            slot: Memory slot (e.g., 'employer', 'age', 'preference')
            context: Additional context (query, timestamp, etc.)
        
        Returns:
            dict: {
                "is_contradiction": bool,
                "category": str,  # REFINEMENT/REVISION/TEMPORAL/CONFLICT
                "policy": str,    # OVERRIDE/PRESERVE/ASK_USER
                "confidence": float
            }
        """
        if context is None:
            context = {}
        
        # If models not loaded, fall back to conservative detection
        if self.belief_classifier is None:
            logger.warning("Belief classifier not available, using fallback detection")
            return self._fallback_detection(old_value, new_value, slot, context)
        
        # Extract features (matching Phase 2 format - 18 features)
        features = self._extract_belief_features(old_value, new_value, context)
        
        # Detect retraction patterns BEFORE ML classification
        # Retraction patterns indicate a user is reversing a denial, which is always a contradiction
        new_lower = str(new_value).lower()
        if _has_retraction_pattern(new_lower) and old_value.lower().strip() != new_value.lower().strip():
            logger.debug(f"[RETRACTION] Forcing CONFLICT for retraction pattern: '{new_value}'")
            return {
                "is_contradiction": True,
                "category": "CONFLICT",
                "policy": "ASK_USER",
                "confidence": 0.85
            }
        
        # Predict category using trained model
        try:
            category_idx = self.belief_classifier.predict([features])[0]
            categories = ["REFINEMENT", "REVISION", "TEMPORAL", "CONFLICT"]
            category = categories[int(category_idx)]
            
            # Get confidence scores
            proba = self.belief_classifier.predict_proba([features])[0]
            confidence = float(proba.max())
            
            # Check for semantic equivalence BEFORE flagging as contradiction
            # This prevents false positives on synonyms and detail enrichment
            if _is_semantic_equivalent(old_value, new_value):
                logger.debug(f"[SEMANTIC_EQ] Treating as equivalent: '{old_value}' ≈ '{new_value}'")
                return {
                    "is_contradiction": False,
                    "category": "REFINEMENT",
                    "policy": "NONE",
                    "confidence": confidence
                }
            
            if _is_detail_enrichment(old_value, new_value):
                logger.debug(f"[ENRICHMENT] Treating as enrichment: '{old_value}' → '{new_value}'")
                return {
                    "is_contradiction": False,
                    "category": "REFINEMENT",
                    "policy": "NONE",
                    "confidence": confidence
                }
            
            # For name slots, check if names are related (nicknames, full names)
            if slot in ("name", "user_name", "spouse_name", "pet_name"):
                from .fact_slots import names_are_related
                if names_are_related(old_value, new_value):
                    logger.debug(f"[NAME_RELATED] '{old_value}' and '{new_value}' are related names")
                    return {
                        "is_contradiction": False,
                        "category": "REFINEMENT",
                        "policy": "NONE",
                        "confidence": confidence
                    }
            
            # Categories REVISION and CONFLICT are contradictions
            is_contradiction = category in ["REVISION", "CONFLICT"]
            
            # Predict policy if contradiction detected
            policy = "NONE"
            if is_contradiction and self.policy_classifier is not None:
                policy = self._predict_policy(features, category, slot, context)
            
            return {
                "is_contradiction": is_contradiction,
                "category": category,
                "policy": policy,
                "confidence": confidence
            }
        
        except Exception as e:
            logger.error(f"ML classification failed: {e}", exc_info=True)
            return self._fallback_detection(old_value, new_value, slot, context)
    
    def _extract_belief_features(
        self,
        old_value: str,
        new_value: str,
        context: Dict[str, Any]
    ) -> np.ndarray:
        """
        Extract 18 features for belief classifier (matching Phase 2 training).
        
        Features:
        1. query_to_old_similarity
        2. cross_memory_similarity
        3. time_delta_days
        4. recency_score
        5. update_frequency
        6. query_word_count
        7. old_word_count
        8. new_word_count
        9. word_count_delta
        10. negation_in_new
        11. negation_in_old
        12. negation_delta
        13. temporal_in_new
        14. temporal_in_old
        15. correction_markers
        16. memory_confidence
        17. trust_score
        18. drift_score
        """
        # Unconditional str() conversion to handle int/float values (e.g., programming_years: 10)
        # This prevents AttributeError when calling .lower() on non-string types
        old_value = str(old_value)
        new_value = str(new_value)
        
        # Semantic similarity
        try:
            tfidf = self.vectorizer.fit_transform([old_value, new_value])
            similarity = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
        except:
            similarity = 0.0
        
        # Temporal features
        old_timestamp = context.get("old_timestamp", time.time() - 86400)  # Default 1 day ago
        new_timestamp = context.get("new_timestamp", time.time())
        time_delta_days = (new_timestamp - old_timestamp) / 86400
        recency_score = np.exp(-time_delta_days / 365.0)  # Exponential decay
        
        # Linguistic features - ensure string conversion for int values (e.g., programming_years)
        old_lower = str(old_value).lower()
        new_lower = str(new_value).lower()
        
        negation_words = ["not", "never", "don't", "doesn't", "didn't", "won't", 
                         "cannot", "no longer", "n't", "can't"]
        
        # Detect retraction-of-denial patterns using helper function
        has_retraction = _has_retraction_pattern(new_lower)
        
        # For retraction patterns, the "no" is part of reversal, not negation
        # So we need to look for negation AFTER the retraction keyword
        if has_retraction:
            # Parse after the retraction keyword to find actual content using helper
            remainder = _extract_remainder_after_retraction(new_lower)
            # Check for negation in the remainder (actual statement)
            negation_in_new = int(any(word in remainder for word in negation_words))
        else:
            negation_in_new = int(any(word in new_lower for word in negation_words))
        
        negation_in_old = int(any(word in old_lower for word in negation_words))
        negation_delta = negation_in_new - negation_in_old
        
        temporal_words = ["now", "currently", "today", "this week", "recently", 
                         "just", "used to", "previously", "was", "were", "anymore"]
        temporal_in_old = int(any(word in old_lower for word in temporal_words))
        temporal_in_new = int(any(word in new_lower for word in temporal_words))
        
        # Correction markers indicate explicit user corrections
        # Note: Retraction patterns are handled separately and force correction_markers=1
        correction_words = ["actually", "instead", "rather", "changed to", 
                           "switched to", "i meant", "correction", "wrong", "mistake", "wait"]
        correction_markers = int(any(word in new_lower for word in correction_words))
        # Force correction marker for retraction patterns (they always indicate correction)
        if has_retraction:
            correction_markers = 1
        
        # Word counts
        query = context.get("query", new_value)
        query_word_count = len(query.split())
        old_word_count = len(old_value.split())
        new_word_count = len(new_value.split())
        word_count_delta = new_word_count - old_word_count
        
        # Trust/confidence from context
        memory_confidence = context.get("memory_confidence", 0.85)
        trust_score = context.get("trust_score", 0.85)
        drift_score = 1.0 - similarity
        
        # Update frequency (from context or default)
        update_frequency = context.get("update_frequency", 1)
        
        # Cross-memory similarity (if multiple memories exist)
        cross_memory_similarity = context.get("cross_memory_similarity", similarity)
        
        # Assemble feature vector (ORDER MUST MATCH Phase 2 training!)
        features = np.array([
            similarity,              # 1. query_to_old_similarity
            cross_memory_similarity, # 2. cross_memory_similarity
            time_delta_days,         # 3. time_delta_days
            recency_score,           # 4. recency_score
            update_frequency,        # 5. update_frequency
            query_word_count,        # 6. query_word_count
            old_word_count,          # 7. old_word_count
            new_word_count,          # 8. new_word_count
            word_count_delta,        # 9. word_count_delta
            negation_in_new,         # 10. negation_in_new
            negation_in_old,         # 11. negation_in_old
            negation_delta,          # 12. negation_delta
            temporal_in_new,         # 13. temporal_in_new
            temporal_in_old,         # 14. temporal_in_old
            correction_markers,      # 15. correction_markers
            memory_confidence,       # 16. memory_confidence
            trust_score,             # 17. trust_score
            drift_score              # 18. drift_score
        ])
        
        return features
    
    def _predict_policy(
        self,
        belief_features: np.ndarray,
        category: str,
        slot: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Predict resolution policy using Phase 3 policy classifier.
        
        Policy features include belief features + policy-specific features.
        """
        try:
            # Extract policy-specific features (21 features total)
            # Includes 18 belief features + 3 policy-specific
            
            # Category encoding (one-hot: 4 categories)
            category_features = np.zeros(4)
            categories = ["REFINEMENT", "REVISION", "TEMPORAL", "CONFLICT"]
            if category in categories:
                category_features[categories.index(category)] = 1
            
            # Slot type (simplified: factual vs preference)
            preference_slots = ["preference", "like", "favorite", "enjoy"]
            is_preference = int(any(pref in slot.lower() for pref in preference_slots))
            
            # User signal strength (from correction markers in belief features)
            has_correction = belief_features[14] > 0  # correction_markers feature
            
            # Combine features
            # Note: This is a simplified version. The actual policy model may need
            # additional one-hot encoding. We'll use the core features for now.
            policy_features = np.concatenate([
                belief_features,  # 18 features
                category_features[:1],  # 1 feature (simplified category)
                [is_preference],  # 1 feature
                [int(has_correction)]  # 1 feature
            ])
            
            # Predict policy
            policy_idx = self.policy_classifier.predict([policy_features])[0]
            policies = ["OVERRIDE", "PRESERVE", "ASK_USER"]
            policy = policies[int(policy_idx)]
            
            return policy
        
        except Exception as e:
            logger.error(f"Policy prediction failed: {e}", exc_info=True)
            return "ASK_USER"  # Safe default
    
    def _fallback_detection(
        self,
        old_value: Any,
        new_value: Any,
        slot: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fallback detection when ML models unavailable.
        
        Uses simple heuristics but still detects ALL slots (not hardcoded list).
        
        Args:
            old_value: Previous value (can be str, int, float, or any type)
            new_value: New value (can be str, int, float, or any type)
            slot: Memory slot name
            context: Additional context dictionary
        
        Returns:
            dict with is_contradiction, category, policy, confidence
        """
        # Convert to string to handle int/float values - MUST happen before .lower()
        # Prevents AttributeError: 'int' object has no attribute 'lower'
        old_value = str(old_value)
        new_value = str(new_value)
        
        # Check for negation patterns
        old_lower = old_value.lower()
        new_lower = new_value.lower()
        
        negation_words = ["not", "never", "don't", "no longer"]
        
        # Detect retraction-of-denial patterns using helper function
        has_retraction = _has_retraction_pattern(new_lower)
        
        # For retraction patterns, parse after the retraction to find actual negation using helper
        if has_retraction:
            remainder = _extract_remainder_after_retraction(new_lower)
            has_negation = any(word in remainder for word in negation_words)
        else:
            has_negation = any(word in new_lower for word in negation_words)
        
        # Check for temporal patterns
        temporal_words = ["now", "currently", "used to", "previously"]
        has_temporal = any(word in new_lower for word in temporal_words)
        
        # Check if values are different
        normalized_old = old_lower.strip()
        normalized_new = new_lower.strip()
        values_differ = normalized_old != normalized_new
        
        # Simple contradiction detection
        # Retraction patterns should trigger contradiction even without explicit negation in remainder
        # because they represent a reversal of position
        is_contradiction = values_differ and (has_negation or has_retraction or len(old_value) > 3)
        
        # Determine category
        if has_temporal:
            category = "TEMPORAL"
        elif has_negation:
            category = "CONFLICT"
        elif values_differ:
            category = "REVISION"
        else:
            category = "REFINEMENT"
        
        # Default policy
        policy = "ASK_USER" if is_contradiction else "NONE"
        
        return {
            "is_contradiction": is_contradiction,
            "category": category,
            "policy": policy,
            "confidence": 0.6  # Lower confidence for fallback
        }

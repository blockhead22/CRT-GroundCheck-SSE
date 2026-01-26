"""
CRT Core - Cognitive-Reflective Transformer Mathematical Framework

Implements:
- Trust vs Confidence separation
- Drift detection and measurement
- Belief-weighted retrieval scoring
- SSE mode selection (Lossless/Cogni/Hybrid)
- Trust evolution equations
- Reconstruction constraints

Philosophy:
- Memory first (coherence over time)
- Honesty over performance (contradictions are signals, not bugs)
- Belief evolves slower than speech
- "The mouth must never outweigh the self"
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math


class SSEMode(Enum):
    """SSE compression modes based on significance."""
    LOSSLESS = "L"   # Identity-critical, contradiction-heavy
    COGNI = "C"      # Fast sketch, "what it felt like"
    HYBRID = "H"     # Adaptive mix


class MemorySource(Enum):
    """Source of memory item."""
    USER = "user"
    SYSTEM = "system"
    FALLBACK = "fallback"
    EXTERNAL = "external"
    REFLECTION = "reflection"
    LLM_OUTPUT = "llm_output"


@dataclass
class CRTConfig:
    """CRT system configuration parameters."""
    
    # Trust evolution rates
    eta_pos: float = 0.1          # Trust increase rate for aligned memories
    eta_reinforce: float = 0.05   # Reinforcement rate for validated memories
    eta_neg: float = 0.15         # Trust decrease rate for contradictions
    
    # Thresholds
    theta_align: float = 0.15     # Drift threshold for alignment
    theta_contra: float = 0.42    # Drift threshold for contradiction (tuned from stress test analysis)
    theta_min: float = 0.30       # Minimum drift for confidence-based contradiction
    theta_drop: float = 0.30      # Confidence drop threshold
    theta_fallback: float = 0.42  # Drift threshold for fallback contradictions
    
    # Reconstruction gates
    theta_intent: float = 0.5     # Intent alignment gate (lowered from 0.7 to reduce gate failures)
    theta_mem: float = 0.38       # Memory alignment gate (lowered from 0.45 to allow detailed explanatory responses)
    
    # Reflection triggers
    theta_reflect: float = 0.5    # Volatility threshold for reflection
    
    # Retrieval
    lambda_time: float = 86400.0  # Time constant (1 day in seconds)
    alpha_trust: float = 0.7      # Trust weight in retrieval (vs confidence)
    
    # Trust bounds
    tau_base: float = 0.7         # Base trust for new memories (FIX: raised to avoid uncertainty trigger)
    tau_fallback_cap: float = 0.3 # Max trust for fallback speech
    tau_train_min: float = 0.6    # Min trust for weight updates
    
    # SSE mode selection
    T_L: float = 0.7              # Lossless threshold
    T_C: float = 0.3              # Cogni threshold
    
    # SSE significance weights
    w_emotion: float = 0.2
    w_novelty: float = 0.25
    w_user_mark: float = 0.3
    w_contradiction: float = 0.15
    w_future: float = 0.1
    
    # Volatility weights
    beta_drift: float = 0.3
    beta_alignment: float = 0.25
    beta_contradiction: float = 0.3
    beta_fallback: float = 0.15
    
    @staticmethod
    def load_from_calibration(
        calibration_path: str = "artifacts/calibrated_thresholds.json"
    ) -> 'CRTConfig':
        """
        Load CRTConfig with calibrated thresholds from file.
        
        Falls back to default values if calibration file is missing or invalid.
        
        Args:
            calibration_path: Path to calibrated thresholds JSON
            
        Returns:
            CRTConfig with calibrated or default thresholds
        """
        import json
        import logging
        from pathlib import Path
        
        logger = logging.getLogger(__name__)
        config = CRTConfig()  # Start with defaults
        
        try:
            threshold_file = Path(calibration_path)
            if not threshold_file.exists():
                logger.info(
                    f"[CRT_CONFIG] Calibration file not found: {calibration_path}, "
                    f"using defaults"
                )
                return config
            
            with open(threshold_file) as f:
                data = json.load(f)
            
            # Update thresholds based on calibrated values
            # Map calibrated zones to CRT thresholds
            # Note: Calibrated thresholds are similarity scores (0-1), where high=similar
            # CRT drift thresholds work inversely: high drift = low similarity
            # Therefore we invert: drift = 1 - similarity
            if "green_zone" in data:
                # Use green_zone as the threshold for high-confidence alignment
                config.theta_align = 1.0 - data["green_zone"]  # High similarity → low drift
                logger.info(
                    f"[CRT_CONFIG] Loaded calibrated theta_align: {config.theta_align:.3f} "
                    f"(from green_zone: {data['green_zone']:.3f})"
                )
            
            if "red_zone" in data:
                # Use red_zone as the threshold for contradictions
                config.theta_contra = 1.0 - data["red_zone"]  # Low similarity → high drift
                logger.info(
                    f"[CRT_CONFIG] Loaded calibrated theta_contra: {config.theta_contra:.3f} "
                    f"(from red_zone: {data['red_zone']:.3f})"
                )
            
            if "yellow_zone" in data:
                # Use yellow_zone for fallback threshold
                config.theta_fallback = 1.0 - data["yellow_zone"]
                logger.info(
                    f"[CRT_CONFIG] Loaded calibrated theta_fallback: {config.theta_fallback:.3f} "
                    f"(from yellow_zone: {data['yellow_zone']:.3f})"
                )
            
            logger.info(f"[CRT_CONFIG] Successfully loaded calibrated thresholds from {calibration_path}")
            
        except Exception as e:
            logger.warning(
                f"[CRT_CONFIG] Failed to load calibration from {calibration_path}: {e}, "
                f"using defaults"
            )
        
        return config


class CRTMath:
    """
    Core CRT mathematical operations.
    
    Implements:
    1. Similarity and drift measurement
    2. Trust-weighted retrieval scoring
    3. SSE mode selection
    4. Trust evolution
    5. Reconstruction constraints
    6. Contradiction detection
    7. Reflection triggers
    """
    
    def __init__(self, config: Optional[CRTConfig] = None):
        """Initialize with configuration."""
        self.config = config or CRTConfig()
    
    # ========================================================================
    # 1. Similarity and Drift
    # ========================================================================
    
    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Cosine similarity between two vectors.
        
        sim(a,b) = (a·b) / (||a|| ||b||)
        """
        if len(a) == 0 or len(b) == 0:
            return 0.0
        
        # Check dimension compatibility
        if len(a) != len(b):
            # Dimension mismatch - likely from old data
            return 0.0
        
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(np.dot(a, b) / (norm_a * norm_b))
    
    def novelty(self, z_new: np.ndarray, memory_vectors: List[np.ndarray]) -> float:
        """
        Novelty of new input relative to stored memory.
        
        novelty(x) = 1 - max_i sim(z_new, z_i)
        """
        if not memory_vectors:
            return 1.0
        
        max_sim = max(self.similarity(z_new, z_mem) for z_mem in memory_vectors)
        return 1.0 - max_sim
    
    def drift_meaning(self, z_new: np.ndarray, z_prior: np.ndarray) -> float:
        """
        Meaning drift between new output and prior belief.
        
        D_mean = 1 - sim(z_new, z_prior)
        """
        return 1.0 - self.similarity(z_new, z_prior)
    
    # ========================================================================
    # 2. Trust-Weighted Retrieval Scoring
    # ========================================================================
    
    def recency_weight(self, t_memory: float, t_now: float) -> float:
        """
        Recency weighting with exponential decay.
        
        ρ_i = exp(-(t_now - t_i) / λ)
        """
        delta_t = t_now - t_memory
        return math.exp(-delta_t / self.config.lambda_time)
    
    def belief_weight(self, trust: float, confidence: float) -> float:
        """
        Combined belief weight (trust + confidence).
        
        w_i = α·τ_i + (1-α)·c_i
        """
        alpha = self.config.alpha_trust
        return alpha * trust + (1 - alpha) * confidence
    
    def retrieval_score(
        self,
        similarity: float,
        recency: float,
        belief: float
    ) -> float:
        """
        Final retrieval score.
        
        R_i = s_i · ρ_i · w_i
        """
        return similarity * recency * belief
    
    def compute_retrieval_scores(
        self,
        query_vector: np.ndarray,
        memories: List[Dict[str, Any]],
        t_now: float
    ) -> List[Tuple[int, float]]:
        """
        Compute retrieval scores for all memories.
        
        Returns list of (index, score) tuples sorted by score descending.
        """
        scores = []
        
        for i, mem in enumerate(memories):
            # Similarity
            s_i = self.similarity(query_vector, mem['vector'])
            
            # Recency
            rho_i = self.recency_weight(mem['timestamp'], t_now)
            
            # Belief weight
            w_i = self.belief_weight(mem['trust'], mem['confidence'])
            
            # Final score
            R_i = self.retrieval_score(s_i, rho_i, w_i)
            
            scores.append((i, R_i))
        
        # Sort by score descending
        return sorted(scores, key=lambda x: x[1], reverse=True)
    
    # ========================================================================
    # 3. SSE Mode Selection
    # ========================================================================
    
    def compute_significance(
        self,
        emotion_intensity: float,
        novelty: float,
        user_marked: float,
        contradiction_signal: float,
        future_relevance: float
    ) -> float:
        """
        Compute significance score for SSE mode selection.
        
        S = w1·e + w2·n + w3·u + w4·k + w5·f
        """
        cfg = self.config
        return (
            cfg.w_emotion * emotion_intensity +
            cfg.w_novelty * novelty +
            cfg.w_user_mark * user_marked +
            cfg.w_contradiction * contradiction_signal +
            cfg.w_future * future_relevance
        )
    
    def select_sse_mode(self, significance: float) -> SSEMode:
        """
        Select SSE compression mode based on significance.
        
        if S ≥ T_L  → SSE-L (lossless)
        if S ≤ T_C  → SSE-C (cogni/sketch)
        else        → SSE-H (hybrid)
        """
        if significance >= self.config.T_L:
            return SSEMode.LOSSLESS
        elif significance <= self.config.T_C:
            return SSEMode.COGNI
        else:
            return SSEMode.HYBRID
    
    # ========================================================================
    # 4. Trust Evolution
    # ========================================================================
    
    def evolve_trust_aligned(
        self,
        tau_current: float,
        drift: float
    ) -> float:
        """
        Trust evolution for aligned memories (low drift).
        
        if D_mean ≤ θ_align:
            τ_new = clip(τ_base + η_pos·(1 - D_mean), 0, 1)
        """
        tau_new = tau_current + self.config.eta_pos * (1.0 - drift)
        return np.clip(tau_new, 0.0, 1.0)
    
    def evolve_trust_reinforced(
        self,
        tau_current: float,
        drift: float
    ) -> float:
        """
        Trust reinforcement for validated memories.
        
        τ_i = clip(τ_i + η_reinforce·(1 - D_mean), 0, 1)
        """
        tau_new = tau_current + self.config.eta_reinforce * (1.0 - drift)
        return np.clip(tau_new, 0.0, 1.0)
    
    def evolve_trust_contradicted(
        self,
        tau_current: float,
        drift: float
    ) -> float:
        """
        Trust degradation for contradicted memories.
        
        τ_new = clip(τ_base · (1 - η_neg·D_mean), 0, 1)
        """
        tau_new = tau_current * (1.0 - self.config.eta_neg * drift)
        return np.clip(tau_new, 0.0, 1.0)
    
    def cap_fallback_trust(self, tau: float, source: MemorySource) -> float:
        """
        Cap trust for fallback sources.
        
        if src == fallback:
            τ = min(τ, τ_fallback_cap)
        """
        if source in {MemorySource.FALLBACK, MemorySource.LLM_OUTPUT}:
            return min(tau, self.config.tau_fallback_cap)
        return tau
    
    # ========================================================================
    # 5. Reconstruction Constraints (Holden Gates)
    # ========================================================================
    
    def intent_alignment(
        self,
        input_intent: np.ndarray,
        output_intent: np.ndarray
    ) -> float:
        """
        Intent alignment score.
        
        A_intent = sim(I(x), I(ŷ))
        """
        return self.similarity(input_intent, output_intent)
    
    def memory_alignment(
        self,
        output_vector: np.ndarray,
        retrieved_memories: List[Dict[str, Any]],
        retrieval_scores: List[float],
        output_text: str = ""
    ) -> float:
        """
        Memory alignment score (weighted by retrieval strength).
        
        A_mem = Σ_i (softmax(R_i) · sim(E(ŷ), z_i))
        
        Special handling: If output is a short substring of any memory,
        boost alignment to reward fact extraction.
        """
        if not retrieved_memories:
            return 0.0
        
        # Check for short fact extraction (answer is substring of memory)
        if output_text and len(output_text) < 50:
            output_lower = output_text.lower().strip()
            for mem in retrieved_memories[:3]:
                mem_text = mem.get('text', '').lower() if isinstance(mem.get('text'), str) else ''
                if output_lower and mem_text and output_lower in mem_text:
                    # Answer is extracted from memory - high alignment
                    return 0.95
        
        # Softmax over retrieval scores
        scores_array = np.array(retrieval_scores)
        exp_scores = np.exp(scores_array - np.max(scores_array))
        weights = exp_scores / np.sum(exp_scores)
        
        # Weighted similarity
        alignment = 0.0
        for i, mem in enumerate(retrieved_memories):
            sim = self.similarity(output_vector, mem['vector'])
            alignment += weights[i] * sim
        
        return alignment
    
    def check_reconstruction_gates(
        self,
        intent_align: float,
        memory_align: float,
        has_grounding_issues: bool = False,
        has_contradiction_issues: bool = False,
        has_extraction_issues: bool = False
    ) -> Tuple[bool, str]:
        """
        Check if reconstruction passes gates (legacy v1).
        
        DEPRECATED: Use check_reconstruction_gates_v2 with response_type awareness.
        
        Accept if:
            A_intent ≥ θ_intent AND A_mem ≥ θ_mem
        
        Returns (passed, reason)
        """
        # Priority order: specific fails before general alignment fails
        if has_grounding_issues:
            return False, "grounding_fail"
        
        if has_contradiction_issues:
            return False, "contradiction_fail"
        
        if has_extraction_issues:
            return False, "extraction_fail"
        
        if intent_align < self.config.theta_intent:
            return False, f"intent_fail (align={intent_align:.3f} < {self.config.theta_intent})"
        
        if memory_align < self.config.theta_mem:
            return False, f"memory_fail (align={memory_align:.3f} < {self.config.theta_mem})"
        
        return True, "gates_passed"
    
    def check_reconstruction_gates_v2(
        self,
        intent_align: float,
        memory_align: float,
        response_type: str,
        grounding_score: float = 1.0,
        contradiction_severity: str = "none",
    ) -> Tuple[bool, str]:
        """
        Gradient gates with response-type awareness (v2).
        
        Key improvements over v1:
        1. Different thresholds for factual/explanatory/conversational
        2. Grounding score (0-1) instead of binary check
        3. Contradiction severity levels (blocking/note/none)
        
        Response types:
        - factual: Strict gates for factual claims (What is my X?)
        - explanatory: Relaxed gates for synthesis/explanation (How/Why questions)
        - conversational: Minimal gates for chat/acknowledgment
        
        Args:
            intent_align: Intent alignment score (0-1)
            memory_align: Memory alignment score (0-1)
            response_type: "factual" | "explanatory" | "conversational"
            grounding_score: How well grounded in memory (0-1)
            contradiction_severity: "blocking" | "note" | "none"
        
        Returns:
            (passed, reason)
        """
        # Blocking contradictions always fail
        if contradiction_severity == "blocking":
            return False, "contradiction_fail"
        
        # Response-type specific thresholds
        if response_type == "factual":
            # Factual gates - lowered thresholds for short fact extraction
            if intent_align < 0.35:
                return False, f"factual_intent_fail (align={intent_align:.3f} < 0.35)"
            if memory_align < 0.35:
                return False, f"factual_memory_fail (align={memory_align:.3f} < 0.35)"
            # Only check grounding if answer is long (>50 chars)
            # Short answers are likely direct fact extractions
            # Lowered from 0.4 to 0.30 to reduce false rejections with ML classifier
            if grounding_score < 0.30:
                return False, f"factual_grounding_fail (score={grounding_score:.3f} < 0.30)"
        
        elif response_type == "explanatory":
            # Relaxed gates for explanations/synthesis
            if intent_align < 0.4:
                return False, f"explanatory_intent_fail (align={intent_align:.3f} < 0.4)"
            if memory_align < 0.25:
                return False, f"explanatory_memory_fail (align={memory_align:.3f} < 0.25)"
            if grounding_score < 0.25:  # Lowered from 0.3 - improved grounding computation
                return False, f"explanatory_grounding_fail (score={grounding_score:.3f} < 0.25)"
        
        else:  # conversational
            # Minimal gates for chat/acknowledgment
            if intent_align < 0.3:
                return False, f"conversational_intent_fail (align={intent_align:.3f} < 0.3)"
            # No memory/grounding requirements for conversational
        
        # Non-blocking contradictions pass but add metadata
        if contradiction_severity == "note":
            return True, "gates_passed_with_contradiction_note"
        
        return True, "gates_passed"
    
    # ========================================================================
    # 6. Contradiction Detection
    # ========================================================================
    
    def detect_contradiction(
        self,
        drift: float,
        confidence_new: float,
        confidence_prior: float,
        source: MemorySource,
        text_new: str = "",
        text_prior: str = ""
    ) -> Tuple[bool, str]:
        """
        Detect if contradiction event should be triggered.
        
        Now includes paraphrase tolerance to reduce false positives.
        
        Triggers:
        1. Paraphrase check - same meaning despite drift shouldn't flag
        2. D_mean > θ_contra
        3. (Δc > θ_drop AND D_mean > θ_min)
        4. (src == fallback AND D_mean > θ_fallback)
        
        Returns (is_contradiction, reason)
        """
        cfg = self.config
        
        # Rule 0: Paraphrase tolerance (reduce false positives)
        if text_new and text_prior and drift > 0.25:
            if self._is_likely_paraphrase(text_new, text_prior, drift):
                return False, f"Paraphrase detected (drift={drift:.3f}, not contradiction)"
        
        # Rule 1: High drift
        if drift > cfg.theta_contra:
            return True, f"High drift: {drift:.3f} > {cfg.theta_contra}"
        
        # Rule 2: Confidence drop with moderate drift
        delta_c = confidence_prior - confidence_new
        if delta_c > cfg.theta_drop and drift > cfg.theta_min:
            return True, f"Confidence drop: Δc={delta_c:.3f}, drift={drift:.3f}"
        
        # Rule 3: Fallback source with drift
        if source in {MemorySource.FALLBACK, MemorySource.LLM_OUTPUT} and drift > cfg.theta_fallback:
            return True, f"Fallback drift: {drift:.3f} > {cfg.theta_fallback}"
        
        return False, "No contradiction"
    
    def _is_likely_paraphrase(self, text_new: str, text_prior: str, drift: float) -> bool:
        """
        Check if two texts are paraphrases despite semantic drift.
        
        Heuristics:
        1. Same key entities/numbers
        2. Drift is moderate (0.25-0.55 range)
        3. High overlap in key elements
        """
        import re
        
        # Only check moderate drift range (paraphrases shouldn't have extreme drift)
        if drift < 0.25 or drift > 0.55:
            return False
        
        def extract_key_elements(text: str) -> set:
            """Extract numbers and proper nouns as key elements."""
            numbers = set(re.findall(r'\d+', text))
            # Proper nouns (capitalized words not at sentence start)
            caps = set(re.findall(r'(?<!^)(?<!\. )[A-Z][a-z]+', text))
            return numbers | caps
        
        keys_new = extract_key_elements(text_new)
        keys_prior = extract_key_elements(text_prior)
        
        # If key elements overlap significantly, likely paraphrase
        if keys_new and keys_prior:
            overlap = len(keys_new & keys_prior) / max(len(keys_new | keys_prior), 1)
            if overlap > 0.7:
                return True
        
        return False
    
    # ========================================================================
    # 7. Reflection Triggers
    # ========================================================================
    
    def compute_volatility(
        self,
        drift: float,
        memory_alignment: float,
        is_contradiction: bool,
        is_fallback: bool
    ) -> float:
        """
        Compute volatility/instability score.
        
        V = β1·D_mean + β2·(1 - A_mem) + β3·contradiction + β4·fallback
        """
        cfg = self.config
        
        contra_flag = 1.0 if is_contradiction else 0.0
        fallback_flag = 1.0 if is_fallback else 0.0
        
        return (
            cfg.beta_drift * drift +
            cfg.beta_alignment * (1.0 - memory_alignment) +
            cfg.beta_contradiction * contra_flag +
            cfg.beta_fallback * fallback_flag
        )
    
    def should_reflect(self, volatility: float) -> bool:
        """
        Check if reflection should be triggered.
        
        if V ≥ θ_reflect → trigger reflection
        """
        return volatility >= self.config.theta_reflect
    
    # ========================================================================
    # 8. Safety Boundaries
    # ========================================================================
    
    def can_train_on_memory(
        self,
        trust: float,
        has_open_contradiction: bool,
        source: MemorySource
    ) -> Tuple[bool, str]:
        """
        Check if memory can be used for training/weight updates.
        
        Requirements:
        - τ ≥ τ_train_min
        - No open contradictions
        - Not from fallback (unless verified)
        """
        if trust < self.config.tau_train_min:
            return False, f"Trust too low: {trust:.3f} < {self.config.tau_train_min}"
        
        if has_open_contradiction:
            return False, "Open contradiction exists"
        
        if source in {MemorySource.FALLBACK, MemorySource.LLM_OUTPUT}:
            return False, "Fallback source not verified"
        
        return True, "Safe to train"


# ============================================================================
# Utility Functions
# ============================================================================

def encode_vector(text: str, encoder=None) -> np.ndarray:
    """
    Encode text to semantic vector.
    
    Uses sentence-transformers for real semantic embeddings.
    Falls back to hash-based if embeddings fail.
    """
    if encoder is not None:
        return encoder(text)
    
    # Use real embeddings
    try:
        from .embeddings import encode_text
        return encode_text(text)
    except Exception as e:
        # Fallback to hash-based if embeddings fail
        import hashlib
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        
        # Convert to normalized vector
        vector = np.frombuffer(hash_bytes[:32], dtype=np.float32)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        
        return vector


def extract_emotion_intensity(text: str) -> float:
    """
    Extract emotion intensity from text (0-1).
    
    Placeholder - integrate with emotion detection.
    """
    # Simple heuristic: exclamation marks, caps, emotion words
    emotion_words = ['love', 'hate', 'fear', 'angry', 'happy', 'sad', 'excited', 'worried']
    
    intensity = 0.0
    
    # Exclamation marks
    intensity += min(text.count('!') * 0.1, 0.3)
    
    # Caps ratio
    if len(text) > 0:
        caps_ratio = sum(1 for c in text if c.isupper()) / len(text)
        intensity += min(caps_ratio * 0.5, 0.3)
    
    # Emotion words
    text_lower = text.lower()
    emotion_count = sum(1 for word in emotion_words if word in text_lower)
    intensity += min(emotion_count * 0.1, 0.4)
    
    return min(intensity, 1.0)


def extract_future_relevance(text: str) -> float:
    """
    Extract future relevance proxy (0-1).
    
    Detects: questions, plans, "remember", etc.
    """
    relevance = 0.0
    text_lower = text.lower()
    
    # Questions
    if '?' in text:
        relevance += 0.3
    
    # Planning words
    planning_words = ['remember', 'later', 'tomorrow', 'next', 'plan', 'will', 'going to']
    for word in planning_words:
        if word in text_lower:
            relevance += 0.2
            break
    
    # Time references
    time_words = ['when', 'where', 'how long', 'until']
    for word in time_words:
        if word in text_lower:
            relevance += 0.2
            break
    
    return min(relevance, 1.0)

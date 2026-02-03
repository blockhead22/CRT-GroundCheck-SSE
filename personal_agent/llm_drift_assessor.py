"""LLM-based drift assessment for semantic contradiction detection.

Uses a lightweight local LLM (via Ollama) to assess whether two statements
represent a genuine contradiction, gradual drift, or natural evolution.

This supplements the rule-based classification with semantic understanding.
"""

import json
import logging
import re
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DriftType(str, Enum):
    """Types of semantic drift between statements."""
    CONTRADICTION = "contradiction"  # Mutually exclusive (Google vs Microsoft)
    EVOLUTION = "evolution"          # Natural progression (engineer → senior engineer)
    REFINEMENT = "refinement"        # More specific (Bay Area → San Francisco)
    CORRECTION = "correction"        # Explicit fix ("actually", "I meant")
    TEMPORAL = "temporal"            # Time-based change (switched jobs)
    PREFERENCE = "preference"        # Opinion shift (Java → Python preference)
    COMPATIBLE = "compatible"        # Not actually conflicting


@dataclass
class DriftAssessment:
    """Result of LLM drift assessment."""
    drift_type: DriftType
    confidence: float  # 0.0 - 1.0
    reasoning: str
    is_hard_contradiction: bool
    suggested_action: str  # "ask_user", "accept_new", "keep_old", "merge"
    slot_affected: Optional[str] = None


# Compact prompt for fast inference
DRIFT_ASSESSMENT_PROMPT = """Analyze if these two statements conflict:

OLD: {old_text}
NEW: {new_text}

Classify as ONE of:
- CONTRADICTION: Mutually exclusive facts (e.g., "works at Google" vs "works at Microsoft")
- EVOLUTION: Natural career/life progression (e.g., "engineer" → "senior engineer")  
- REFINEMENT: More specific detail (e.g., "Bay Area" → "San Francisco")
- CORRECTION: Explicit fix with "actually", "I meant", etc.
- TEMPORAL: Time-based change with "now", "used to", "switched"
- PREFERENCE: Opinion/preference shift (e.g., "prefer Java" → "prefer Python")
- COMPATIBLE: Not actually conflicting

Output JSON only:
{{"type": "<TYPE>", "confidence": 0.0-1.0, "hard_conflict": true/false, "reason": "<brief>", "action": "ask_user|accept_new|keep_old|merge"}}"""


class LLMDriftAssessor:
    """Uses lightweight LLM for semantic drift assessment."""
    
    def __init__(self, llm_client=None, model: Optional[str] = None):
        """
        Initialize drift assessor.
        
        Args:
            llm_client: OllamaClient instance (optional - will create if needed)
            model: Model name override (default: uses a small fast model)
        """
        self.llm_client = llm_client
        self.model = model or "llama3.2:latest"  # 3B model, fast inference
        self._initialized = False
        
    def _ensure_client(self) -> bool:
        """Lazily initialize LLM client."""
        if self._initialized:
            return self.llm_client is not None
            
        self._initialized = True
        
        if self.llm_client is not None:
            return True
            
        try:
            from .ollama_client import OllamaClient
            self.llm_client = OllamaClient(model=self.model)
            logger.info(f"[DRIFT_LLM] Initialized with model: {self.model}")
            return True
        except Exception as e:
            logger.warning(f"[DRIFT_LLM] Could not initialize Ollama: {e}")
            return False
    
    def assess_drift(
        self,
        old_text: str,
        new_text: str,
        slot: Optional[str] = None,
        context: Optional[str] = None
    ) -> Optional[DriftAssessment]:
        """
        Assess semantic drift between two statements.
        
        Args:
            old_text: Original/prior statement
            new_text: New/current statement
            slot: Fact slot if known (e.g., "employer", "location")
            context: Additional context for assessment
            
        Returns:
            DriftAssessment or None if LLM unavailable
        """
        if not self._ensure_client():
            return None
            
        try:
            prompt = DRIFT_ASSESSMENT_PROMPT.format(
                old_text=old_text[:200],  # Truncate for speed
                new_text=new_text[:200]
            )
            
            response = self.llm_client.generate(
                prompt=prompt,
                system="You are a fact-checking assistant. Output valid JSON only.",
                max_tokens=150,
                temperature=0.1  # Low temp for consistency
            )
            
            # Parse JSON response
            assessment = self._parse_response(response, slot)
            if assessment:
                logger.info(f"[DRIFT_LLM] {old_text[:30]}... vs {new_text[:30]}... -> {assessment.drift_type}")
            return assessment
            
        except Exception as e:
            logger.warning(f"[DRIFT_LLM] Assessment failed: {e}")
            return None
    
    def _parse_response(self, response: str, slot: Optional[str]) -> Optional[DriftAssessment]:
        """Parse LLM JSON response into DriftAssessment."""
        try:
            # Extract JSON from response (may have extra text)
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if not json_match:
                return None
                
            data = json.loads(json_match.group())
            
            # Map type string to enum
            type_str = data.get("type", "").upper()
            try:
                drift_type = DriftType(type_str.lower())
            except ValueError:
                drift_type = DriftType.CONTRADICTION  # Default to safe
            
            # Map action
            action = data.get("action", "ask_user")
            if action not in ("ask_user", "accept_new", "keep_old", "merge"):
                action = "ask_user"
            
            return DriftAssessment(
                drift_type=drift_type,
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reason", ""),
                is_hard_contradiction=data.get("hard_conflict", drift_type == DriftType.CONTRADICTION),
                suggested_action=action,
                slot_affected=slot
            )
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.debug(f"[DRIFT_LLM] Parse error: {e}, response: {response[:100]}")
            return None
    
    def is_gradual_drift(
        self,
        old_text: str,
        new_text: str,
        slot: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Quick check if statements represent gradual drift vs hard contradiction.
        
        Returns:
            (is_gradual, reason) - True if this is natural evolution, not contradiction
        """
        assessment = self.assess_drift(old_text, new_text, slot)
        
        if assessment is None:
            # Fallback to heuristic
            return self._heuristic_gradual_check(old_text, new_text)
        
        gradual_types = {
            DriftType.EVOLUTION,
            DriftType.REFINEMENT,
            DriftType.TEMPORAL,
            DriftType.PREFERENCE,
            DriftType.COMPATIBLE
        }
        
        is_gradual = assessment.drift_type in gradual_types
        return is_gradual, assessment.reasoning
    
    def _heuristic_gradual_check(self, old_text: str, new_text: str) -> Tuple[bool, Optional[str]]:
        """Fallback heuristic when LLM unavailable."""
        old_lower = old_text.lower()
        new_lower = new_text.lower()
        
        # Temporal indicators suggest gradual change
        temporal_words = ["now", "currently", "recently", "switched", "moved", "changed", "these days"]
        if any(w in new_lower for w in temporal_words):
            return True, "temporal_marker_detected"
        
        # Evolution indicators
        evolution_pairs = [
            ("junior", "senior"), ("senior", "principal"), ("engineer", "senior engineer"),
            ("developer", "lead"), ("analyst", "senior analyst")
        ]
        for old_role, new_role in evolution_pairs:
            if old_role in old_lower and new_role in new_lower:
                return True, "career_progression"
        
        # Refinement check
        if old_text in new_text or any(w in new_lower for w in ["specifically", "more precisely"]):
            return True, "refinement"
        
        return False, None


# Singleton instance for shared use
_drift_assessor: Optional[LLMDriftAssessor] = None


def get_drift_assessor(llm_client=None) -> LLMDriftAssessor:
    """Get or create singleton drift assessor."""
    global _drift_assessor
    if _drift_assessor is None:
        _drift_assessor = LLMDriftAssessor(llm_client=llm_client)
    return _drift_assessor


def assess_drift_with_llm(
    old_text: str,
    new_text: str,
    slot: Optional[str] = None,
    llm_client=None
) -> Optional[DriftAssessment]:
    """Convenience function for drift assessment."""
    assessor = get_drift_assessor(llm_client)
    return assessor.assess_drift(old_text, new_text, slot)


def is_gradual_drift(
    old_text: str,
    new_text: str,
    slot: Optional[str] = None,
    llm_client=None
) -> Tuple[bool, Optional[str]]:
    """Convenience function to check for gradual drift."""
    assessor = get_drift_assessor(llm_client)
    return assessor.is_gradual_drift(old_text, new_text, slot)

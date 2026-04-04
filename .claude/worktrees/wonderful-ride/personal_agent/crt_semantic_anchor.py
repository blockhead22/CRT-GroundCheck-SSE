"""
CRT Semantic Anchor - Binds contradiction follow-ups to their context

A SemanticAnchor preserves the semantic understanding of a contradiction across
retrieval, generation, and parsing steps. It's the key to M2 semantic continuity.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import numpy as np


@dataclass
class SemanticAnchor:
    """Binds a followup question to its originating contradiction context.
    
    This structure ensures that when we ask a user to resolve a contradiction,
    we carry forward:
    - What kind of conflict it is (type)
    - The exact memories involved (IDs + text)
    - The semantic slot if applicable
    - What kind of answer we expect
    
    This enables type-aware question generation and grounded answer parsing.
    """
    
    # Identity
    contradiction_id: str  # ledger entry ID
    turn_number: int       # when contradiction was detected
    
    # Conflict structure
    contradiction_type: str  # REFINEMENT|REVISION|TEMPORAL|CONFLICT
    old_memory_id: str
    new_memory_id: str
    old_text: str
    new_text: str
    
    # Semantic binding (optional - only for slot-based contradictions)
    slot_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    
    # Semantic drift vector (optional - for geometric reasoning)
    # This is the embedding difference vector: new_emb - old_emb
    # Useful for understanding the semantic "direction" of the conflict
    drift_vector: Optional[np.ndarray] = None
    
    # Question generation context
    clarification_prompt: str = ""  # the generated question
    expected_answer_type: str = "choose_one"  # choose_one|temporal_order|both_true|correction
    
    # Resolution binding (populated when user answers)
    user_answer: Optional[str] = None
    resolution_method: Optional[str] = None
    resolved_at: Optional[int] = None  # turn number
    
    # Metadata for debugging/audit
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for API/storage (no numpy arrays)."""
        result = {
            "contradiction_id": self.contradiction_id,
            "turn_number": self.turn_number,
            "contradiction_type": self.contradiction_type,
            "old_memory_id": self.old_memory_id,
            "new_memory_id": self.new_memory_id,
            "old_text": self.old_text,
            "new_text": self.new_text,
            "slot_name": self.slot_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "clarification_prompt": self.clarification_prompt,
            "expected_answer_type": self.expected_answer_type,
            "user_answer": self.user_answer,
            "resolution_method": self.resolution_method,
            "resolved_at": self.resolved_at,
            "metadata": self.metadata,
        }
        
        # Add drift vector norm if present (don't serialize full array)
        if self.drift_vector is not None:
            result["drift_magnitude"] = float(np.linalg.norm(self.drift_vector))
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SemanticAnchor:
        """Deserialize from dict (drift_vector will be None)."""
        # Remove fields that aren't constructor args
        data_copy = dict(data)
        data_copy.pop("drift_magnitude", None)
        
        return cls(**data_copy)


def generate_clarification_prompt(anchor: SemanticAnchor) -> str:
    """Generate a type-aware clarification question.
    
    The question phrasing depends on contradiction type:
    - REFINEMENT: "more specific or more general?"
    - REVISION: "which is correct?"
    - TEMPORAL: "which came first, or are both true at different times?"
    - CONFLICT: "these contradict - which is right?"
    """
    
    old_text = anchor.old_text[:100]  # truncate for readability
    new_text = anchor.new_text[:100]
    
    # Normalize contradiction type for comparison
    ctype = anchor.contradiction_type.lower() if isinstance(anchor.contradiction_type, str) else ""
    
    if ctype == "refinement":
        if anchor.slot_name and anchor.old_value and anchor.new_value:
            return (
                f"I have two values for {anchor.slot_name}: '{anchor.old_value}' and '{anchor.new_value}'. "
                f"Did you mean to be more specific, or are both correct?"
            )
        else:
            return (
                f"You said '{old_text}' before, and now '{new_text}'. "
                f"Is the newer statement more specific, or did something change?"
            )
    
    elif ctype == "revision":
        if anchor.slot_name and anchor.old_value and anchor.new_value:
            return (
                f"You told me {anchor.slot_name} = '{anchor.old_value}', but now you said '{anchor.new_value}'. "
                f"Which is correct?"
            )
        else:
            return (
                f"You said '{old_text}' before, but now '{new_text}'. "
                f"Which one should I remember?"
            )
    
    elif ctype == "temporal":
        if anchor.slot_name and anchor.old_value and anchor.new_value:
            return (
                f"I have {anchor.slot_name} = '{anchor.old_value}' from earlier, and now '{anchor.new_value}'. "
                f"Did the situation change over time, or which is current?"
            )
        else:
            return (
                f"Earlier you said '{old_text}', now '{new_text}'. "
                f"Did this change over time, or are both true at different moments?"
            )
    
    else:  # CONFLICT (default)
        if anchor.slot_name and anchor.old_value and anchor.new_value:
            return (
                f"I have conflicting values for {anchor.slot_name}: '{anchor.old_value}' vs '{anchor.new_value}'. "
                f"These can't both be true - which is correct?"
            )
        else:
            return (
                f"You said '{old_text}' before, but now '{new_text}'. "
                f"These contradict - which should I trust?"
            )


def parse_user_answer(
    anchor: SemanticAnchor,
    answer_text: str,
) -> Dict[str, Any]:
    """Parse user's clarification answer into a resolution decision.
    
    Returns:
        {
            "resolution_method": str,  # user_chose_old|user_chose_new|user_clarified|both_true|...
            "chosen_memory_id": Optional[str],  # which memory "wins" if applicable
            "new_status": str,  # resolved|open
            "confidence": float,  # how confident we are in the parse
            "parsed_value": Optional[str],  # extracted canonical value if slot-based
        }
    """
    
    answer_lower = answer_text.lower().strip()
    
    # Simple keyword-based parsing (can be enhanced with learned model later)
    result = {
        "resolution_method": "user_clarified",
        "chosen_memory_id": None,
        "new_status": "resolved",
        "confidence": 0.5,
        "parsed_value": None,
    }
    
    # Check for explicit old/new references
    old_patterns = ["the first", "the old", "the earlier", "before", "previously", "original", "initially"]
    new_patterns = ["the new", "the second", "the later", "now", "current", "latest", "actually", "correction"]
    
    if any(phrase in answer_lower for phrase in old_patterns):
        result["resolution_method"] = "user_chose_old"
        result["chosen_memory_id"] = anchor.old_memory_id
        result["confidence"] = 0.8
    
    elif any(phrase in answer_lower for phrase in new_patterns):
        result["resolution_method"] = "user_chose_new"
        result["chosen_memory_id"] = anchor.new_memory_id
        result["confidence"] = 0.8
    
    elif any(phrase in answer_lower for phrase in ["both", "both true", "different times", "changed", "it changed", "changed over time", "evolved", "progressed"]):
        result["resolution_method"] = "both_true_temporal"
        result["new_status"] = "resolved"
        result["confidence"] = 0.7
    
    elif any(phrase in answer_lower for phrase in ["neither", "wrong", "mistake", "incorrect", "both wrong", "not right"]):
        result["resolution_method"] = "both_wrong"
        result["new_status"] = "resolved"
        result["confidence"] = 0.6
    
    # Enhanced: Check for ordinal references
    elif any(phrase in answer_lower for phrase in ["1)", "number 1", "first one", "option 1", "statement 1"]):
        result["resolution_method"] = "user_chose_old"
        result["chosen_memory_id"] = anchor.old_memory_id
        result["confidence"] = 0.75
    
    elif any(phrase in answer_lower for phrase in ["2)", "number 2", "second one", "option 2", "statement 2"]):
        result["resolution_method"] = "user_chose_new"
        result["chosen_memory_id"] = anchor.new_memory_id
        result["confidence"] = 0.75
    
    # If slot-based, try to extract canonical value
    if anchor.slot_name and anchor.expected_answer_type == "choose_one":
        # Check if answer contains old or new value
        if anchor.old_value and anchor.old_value.lower() in answer_lower:
            result["parsed_value"] = anchor.old_value
            result["confidence"] = max(result["confidence"], 0.75)
        elif anchor.new_value and anchor.new_value.lower() in answer_lower:
            result["parsed_value"] = anchor.new_value
            result["confidence"] = max(result["confidence"], 0.75)
    
    return result


def is_resolution_grounded(
    anchor: SemanticAnchor,
    resolution: Dict[str, Any],
) -> bool:
    """Validate that a resolution decision is grounded in the anchor context.
    
    This is a gate check for M2 followup resolution.
    Returns False if resolution doesn't make sense given the anchor.
    """
    
    method = resolution.get("resolution_method", "")
    chosen_id = resolution.get("chosen_memory_id")
    
    # If method claims to choose old/new, must reference correct memory ID
    if method == "user_chose_old" and chosen_id != anchor.old_memory_id:
        return False
    if method == "user_chose_new" and chosen_id != anchor.new_memory_id:
        return False
    
    # If slot-based, parsed_value should relate to slot
    if anchor.slot_name and resolution.get("parsed_value"):
        # Value should match old or new, or be a new clarification
        parsed = resolution["parsed_value"]
        if parsed not in [anchor.old_value, anchor.new_value]:
            # It's a new value - this is allowed for "user_clarified" method
            if method not in ["user_clarified", "both_wrong"]:
                return False
    
    # Confidence too low = not grounded enough
    if resolution.get("confidence", 0) < 0.3:
        return False
    
    return True

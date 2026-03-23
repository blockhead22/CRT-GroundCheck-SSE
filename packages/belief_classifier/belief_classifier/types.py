"""Core types for the belief classifier system."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class BeliefType(str, Enum):
    """Classification of how two beliefs relate."""

    REFINEMENT = "refinement"  # "I like blue" -> "I like dark blue"
    REVISION = "revision"      # "I like blue" -> "Actually I like orange now"
    TEMPORAL = "temporal"       # "I work at Acme" -> "I left Acme last month"
    CONFLICT = "conflict"       # Genuine contradiction, unclear resolution


class PolicyAction(str, Enum):
    """What to do about a classified contradiction."""

    OVERRIDE = "override"   # Demote old, promote new
    PRESERVE = "preserve"   # Keep both, let trust decay sort it
    ASK_USER = "ask_user"   # Surface to user for resolution


@dataclass
class ContradictionPair:
    """A pair of beliefs that may contradict each other."""

    old_text: str
    new_text: str
    old_trust: float
    new_trust: float
    old_timestamp: float
    new_timestamp: float
    slot_name: Optional[str] = None
    is_exclusive_slot: bool = False
    similarity_score: float = 0.0  # cosine similarity between embeddings
    thread_id: Optional[str] = None

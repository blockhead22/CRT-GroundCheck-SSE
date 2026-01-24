"""
Open-World Fact Tuple Schema for CRT System.

This module defines flexible tuple-based facts that extend beyond the rigid
regex-based fact slots. Unlike hard-coded slots, fact tuples can represent
any entity-attribute-value relationship discovered in user text.

Design Philosophy:
- Deterministic where it matters (policy, storage, contradiction tracking)
- Probabilistic where it helps (extraction, validation, disclosure timing)
- Preserves backward compatibility with existing ExtractedFact system
"""

from __future__ import annotations

import time
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional
from enum import Enum


class FactAction(str, Enum):
    """Action type for fact tuples."""
    ADD = "add"           # New fact being asserted
    UPDATE = "update"     # Updating existing fact
    DEPRECATE = "deprecate"  # Fact is no longer current
    DENY = "deny"         # Explicitly denying a fact


@dataclass
class FactTuple:
    """
    A flexible fact representation as an entity-attribute-value tuple.
    
    This extends beyond fixed slots like 'employer' or 'location' to support
    any fact that can be extracted from natural language.
    
    Attributes:
        entity: Who/what the fact is about (e.g., "User", "Google", "Seattle")
        attribute: What property is being described, using dot notation for
                  hierarchical attributes (e.g., "employment.status", "location")
        value: The value of the attribute
        action: What's happening to this fact (add, update, deprecate, deny)
        confidence: Extraction confidence from 0.0 to 1.0
        evidence_span: Exact quote from source text supporting this fact
        timestamp: When this fact was extracted
        source: Where this fact came from (e.g., "user_input", "llm_extraction")
        metadata: Optional additional context
    
    Example:
        >>> fact = FactTuple(
        ...     entity="User",
        ...     attribute="employment.status",
        ...     value="resigning",
        ...     action=FactAction.UPDATE,
        ...     confidence=0.78,
        ...     evidence_span="I'm effectively resigning from Google"
        ... )
    """
    entity: str
    attribute: str
    value: str
    action: FactAction = FactAction.ADD
    confidence: float = 0.5
    evidence_span: str = ""
    timestamp: float = field(default_factory=time.time)
    source: str = "llm_extraction"
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate and normalize fields after initialization."""
        # Normalize entity to standard form
        self.entity = self.entity.strip() if self.entity else "User"
        
        # Normalize attribute (lowercase, dot notation)
        if self.attribute:
            self.attribute = self.attribute.strip().lower().replace(" ", "_")
        
        # Convert string action to enum if needed
        if isinstance(self.action, str):
            self.action = FactAction(self.action.lower())
        
        # Clamp confidence to valid range
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        
        # Ensure value is string
        self.value = str(self.value) if self.value is not None else ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        # Convert enum to string
        result['action'] = self.action.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FactTuple':
        """Create FactTuple from dictionary."""
        data = data.copy()
        # Convert action string to enum
        if 'action' in data and isinstance(data['action'], str):
            data['action'] = FactAction(data['action'].lower())
        return cls(**data)
    
    def matches_slot(self, slot_name: str) -> bool:
        """
        Check if this tuple corresponds to a hard slot.
        
        This enables backward compatibility with the existing regex-based
        fact extraction system.
        
        Args:
            slot_name: Name of the slot (e.g., "employer", "location")
            
        Returns:
            True if this tuple represents the same fact as the slot
        """
        # Direct attribute match
        if self.attribute == slot_name:
            return True
        
        # Check hierarchical attributes (e.g., "employment.status" matches "employer")
        slot_to_attributes = {
            "employer": ["employer", "employment.status", "employment.company", "company"],
            "location": ["location", "residence", "city", "region"],
            "name": ["name", "full_name", "identity.name"],
            "title": ["title", "job_title", "employment.title", "role"],
            "age": ["age", "years_old"],
            "occupation": ["occupation", "profession", "job"],
        }
        
        related_attrs = slot_to_attributes.get(slot_name, [])
        return self.attribute in related_attrs
    
    @property
    def is_user_fact(self) -> bool:
        """Check if this fact is about the user."""
        return self.entity.lower() in ("user", "i", "me", "myself")
    
    @property
    def is_high_confidence(self) -> bool:
        """Check if this fact has high extraction confidence."""
        return self.confidence >= 0.8
    
    @property
    def normalized_value(self) -> str:
        """Return normalized (lowercase, trimmed) value for comparison."""
        return self.value.lower().strip() if self.value else ""


@dataclass
class FactTupleSet:
    """
    A collection of fact tuples from a single extraction.
    
    Provides utilities for querying, filtering, and managing sets of facts.
    """
    tuples: List[FactTuple] = field(default_factory=list)
    source_text: str = ""
    extraction_timestamp: float = field(default_factory=time.time)
    extraction_method: str = "llm"  # "regex", "llm", or "hybrid"
    
    def add(self, fact: FactTuple) -> None:
        """Add a fact tuple to the set."""
        self.tuples.append(fact)
    
    def get_by_entity(self, entity: str) -> List[FactTuple]:
        """Get all tuples for a specific entity."""
        entity_lower = entity.lower().strip()
        return [t for t in self.tuples if t.entity.lower() == entity_lower]
    
    def get_by_attribute(self, attribute: str) -> List[FactTuple]:
        """Get all tuples with a specific attribute."""
        attr_lower = attribute.lower().strip()
        return [t for t in self.tuples if t.attribute == attr_lower]
    
    def get_user_facts(self) -> List[FactTuple]:
        """Get all facts about the user."""
        return [t for t in self.tuples if t.is_user_fact]
    
    def get_high_confidence(self, threshold: float = 0.8) -> List[FactTuple]:
        """Get tuples with confidence above threshold."""
        return [t for t in self.tuples if t.confidence >= threshold]
    
    def filter_by_slot(self, slot_name: str) -> List[FactTuple]:
        """Get tuples that match a hard slot name."""
        return [t for t in self.tuples if t.matches_slot(slot_name)]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tuples": [t.to_dict() for t in self.tuples],
            "source_text": self.source_text,
            "extraction_timestamp": self.extraction_timestamp,
            "extraction_method": self.extraction_method,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FactTupleSet':
        """Create FactTupleSet from dictionary."""
        tuples = [FactTuple.from_dict(t) for t in data.get("tuples", [])]
        return cls(
            tuples=tuples,
            source_text=data.get("source_text", ""),
            extraction_timestamp=data.get("extraction_timestamp", time.time()),
            extraction_method=data.get("extraction_method", "llm"),
        )
    
    def __len__(self) -> int:
        return len(self.tuples)
    
    def __iter__(self):
        return iter(self.tuples)

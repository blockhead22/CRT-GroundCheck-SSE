"""Type definitions for GroundCheck library."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Memory:
    """A memory or retrieved context item.
    
    Attributes:
        id: Unique identifier for the memory
        text: The text content of the memory
        trust: Trust score between 0.0 and 1.0 (default: 1.0)
        metadata: Optional additional metadata
    """
    id: str
    text: str
    trust: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ExtractedFact:
    """A fact extracted from text.
    
    Attributes:
        slot: The fact category/type (e.g., "name", "employer", "location")
        value: The actual value of the fact
        normalized: Normalized/lowercased version for matching
    """
    slot: str
    value: Any
    normalized: str


@dataclass
class VerificationReport:
    """Results of grounding verification.
    
    Attributes:
        original: The original generated text
        corrected: Corrected text (if mode="strict"), or None
        passed: Whether verification passed (no hallucinations)
        hallucinations: List of detected hallucinated values
        grounding_map: Mapping from claim to supporting memory ID
        confidence: Confidence score for the verification (0.0-1.0)
        facts_extracted: Facts extracted from the generated text
        facts_supported: Facts that were found in memories
    """
    original: str
    corrected: Optional[str] = None
    passed: bool = True
    hallucinations: List[str] = field(default_factory=list)
    grounding_map: Dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0
    facts_extracted: Dict[str, ExtractedFact] = field(default_factory=dict)
    facts_supported: Dict[str, ExtractedFact] = field(default_factory=dict)

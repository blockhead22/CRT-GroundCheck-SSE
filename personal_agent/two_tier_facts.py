"""
Two-Tier Fact System for CRT.

Combines deterministic regex-based extraction (Tier A: hard slots) with
flexible LLM-based extraction (Tier B: open-world tuples).

Design Philosophy:
- Tier A (Hard Slots): Critical facts like name, employer, location that
  require high precision. Uses existing regex patterns for determinism.
- Tier B (Open Tuples): Flexible facts like hobbies, preferences, goals
  that benefit from LLM's understanding of natural language.

The two-tier approach ensures:
1. Critical facts maintain high precision through regex
2. Open-world facts can still be captured via LLM
3. No duplicate facts between tiers
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .fact_slots import extract_fact_slots, ExtractedFact
from .fact_tuples import FactTuple, FactTupleSet, FactAction
from .llm_extractor import (
    LLMFactExtractor,
    LocalLLMFactExtractor,
    LLMConfig,
    create_regex_fallback_extractor,
)

logger = logging.getLogger(__name__)


@dataclass
class TwoTierExtractionResult:
    """
    Result of two-tier fact extraction.
    
    Attributes:
        hard_facts: Dictionary of hard slot facts (Tier A, regex-based)
        open_tuples: List of open-world tuples (Tier B, LLM-based)
        source_text: Original text that was analyzed
        extraction_time: How long extraction took
        methods_used: Which extraction methods were used
    """
    hard_facts: Dict[str, ExtractedFact] = field(default_factory=dict)
    open_tuples: List[FactTuple] = field(default_factory=list)
    source_text: str = ""
    extraction_time: float = 0.0
    methods_used: List[str] = field(default_factory=list)
    
    def get_all_facts(self) -> Dict[str, Any]:
        """
        Get all facts as a unified dictionary.
        
        Combines hard facts and open tuples into a single dict.
        Hard facts take precedence over tuples with the same attribute.
        """
        result = {}
        
        # Add hard facts first
        for slot, fact in self.hard_facts.items():
            result[slot] = {
                "value": fact.value,
                "normalized": fact.normalized,
                "tier": "hard",
                "source": "regex",
            }
        
        # Add open tuples (only if not already covered by hard facts)
        for tuple_fact in self.open_tuples:
            if tuple_fact.attribute not in result:
                result[tuple_fact.attribute] = {
                    "value": tuple_fact.value,
                    "normalized": tuple_fact.normalized_value,
                    "tier": "open",
                    "source": "llm",
                    "confidence": tuple_fact.confidence,
                }
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "hard_facts": {
                slot: {"slot": f.slot, "value": f.value, "normalized": f.normalized}
                for slot, f in self.hard_facts.items()
            },
            "open_tuples": [t.to_dict() for t in self.open_tuples],
            "source_text": self.source_text,
            "extraction_time": self.extraction_time,
            "methods_used": self.methods_used,
        }


class TwoTierFactSystem:
    """
    Two-tier fact extraction system combining regex and LLM approaches.
    
    Tier A (Hard Slots):
        Critical, high-stakes facts that require deterministic extraction.
        These are identity-defining facts where precision matters more
        than recall.
        
    Tier B (Open Tuples):
        Flexible facts that don't fit predefined patterns. LLM-based
        extraction handles natural language variations and novel fact types.
    
    Example:
        >>> system = TwoTierFactSystem()
        >>> result = system.extract_facts(
        ...     "I'm Sarah, I work at Google and my hobby is pottery."
        ... )
        >>> print(result.hard_facts)  # {'name': ..., 'employer': ...}
        >>> print(result.open_tuples)  # [FactTuple(hobby=pottery)]
    """
    
    # Tier A: Hard slots requiring deterministic regex extraction
    # These are critical facts where false positives are costly
    HARD_SLOTS: Set[str] = {
        # Identity
        "name",
        
        # Employment (high-stakes, frequently contradicted)
        "employer",
        "title",
        "occupation",
        
        # Location (identity-defining)
        "location",
        
        # Medical/Legal (requires precision)
        "medical_diagnosis",
        "account_status",
        "legal_status",
        "relationship_status",
        
        # Education
        "undergrad_school",
        "masters_school",
        "school",
        "graduation_year",
        
        # Core profile
        "age",
        "programming_years",
        "first_language",
    }
    
    # Slots that should ONLY use regex (never LLM) due to precision requirements
    REGEX_ONLY_SLOTS: Set[str] = {
        "name",
        "age",
        "graduation_year",
    }
    
    def __init__(
        self,
        llm_extractor: Optional[LLMFactExtractor] = None,
        use_local_llm: bool = False,
        enable_llm: bool = False,  # Default to local-only (no external API calls)
        llm_confidence_threshold: float = 0.6,
    ):
        """
        Initialize the two-tier fact system.
        
        Args:
            llm_extractor: Custom LLM extractor (optional)
            use_local_llm: Use local Ollama instead of OpenAI
            enable_llm: Whether to enable LLM extraction at all (default False for local-only)
            llm_confidence_threshold: Minimum confidence for LLM facts
        """
        self.enable_llm = enable_llm
        self.llm_confidence_threshold = llm_confidence_threshold
        
        # Initialize LLM extractor only if enabled
        if not enable_llm:
            self._llm_extractor = None
        elif llm_extractor is not None:
            self._llm_extractor = llm_extractor
        elif use_local_llm:
            self._llm_extractor = LocalLLMFactExtractor()
        else:
            self._llm_extractor = LLMFactExtractor()
        
        # Set up regex fallback for graceful degradation
        if self._llm_extractor is not None:
            self._llm_extractor.set_fallback_extractor(
                create_regex_fallback_extractor()
            )
    
    @property
    def llm_extractor(self) -> Optional[LLMFactExtractor]:
        """Get the LLM extractor (may be None if disabled)."""
        return self._llm_extractor if self.enable_llm else None
    
    def extract_facts(
        self,
        text: str,
        skip_llm: bool = False,
    ) -> TwoTierExtractionResult:
        """
        Extract facts using both regex and LLM approaches.
        
        Args:
            text: Input text to extract facts from
            skip_llm: If True, skip LLM extraction (regex only)
            
        Returns:
            TwoTierExtractionResult with hard facts and open tuples
        """
        start_time = time.time()
        result = TwoTierExtractionResult(source_text=text)
        
        if not text or not text.strip():
            return result
        
        # ============================================================
        # Tier A: Regex-based extraction for hard slots
        # ============================================================
        try:
            all_regex_facts = extract_fact_slots(text)
            
            # Keep only hard slots in tier A
            for slot, fact in all_regex_facts.items():
                if slot in self.HARD_SLOTS:
                    result.hard_facts[slot] = fact
            
            result.methods_used.append("regex")
            logger.debug(f"Regex extracted {len(result.hard_facts)} hard facts")
            
        except Exception as e:
            logger.warning(f"Regex extraction failed: {e}")
        
        # ============================================================
        # Tier B: LLM-based extraction for open-world facts
        # ============================================================
        if not skip_llm and self.enable_llm and self._llm_extractor is not None:
            try:
                llm_tuples = self._llm_extractor.extract_tuples(text)
                
                # Filter out tuples that overlap with hard slots
                for tuple_fact in llm_tuples:
                    # Skip if this attribute is a hard slot
                    if tuple_fact.attribute in self.HARD_SLOTS:
                        continue
                    
                    # Skip if confidence is too low
                    if tuple_fact.confidence < self.llm_confidence_threshold:
                        continue
                    
                    # Skip if it matches any regex-only slot
                    matches_regex_only = any(
                        tuple_fact.matches_slot(slot)
                        for slot in self.REGEX_ONLY_SLOTS
                    )
                    if matches_regex_only:
                        continue
                    
                    result.open_tuples.append(tuple_fact)
                
                result.methods_used.append("llm")
                logger.debug(f"LLM extracted {len(result.open_tuples)} open tuples")
                
            except Exception as e:
                logger.warning(f"LLM extraction failed: {e}")
        
        result.extraction_time = time.time() - start_time
        return result
    
    def extract_hard_facts_only(self, text: str) -> Dict[str, ExtractedFact]:
        """
        Extract only hard slot facts (regex-based).
        
        This is a fast path for when only critical facts are needed.
        
        Args:
            text: Input text
            
        Returns:
            Dictionary of slot -> ExtractedFact
        """
        result = self.extract_facts(text, skip_llm=True)
        return result.hard_facts
    
    def merge_with_existing(
        self,
        new_result: TwoTierExtractionResult,
        existing_facts: Dict[str, Any],
        prefer_new: bool = True,
    ) -> Dict[str, Any]:
        """
        Merge new extraction results with existing facts.
        
        Args:
            new_result: Newly extracted facts
            existing_facts: Previously stored facts
            prefer_new: If True, new facts override existing on conflict
            
        Returns:
            Merged fact dictionary
        """
        merged = dict(existing_facts)
        
        # Process hard facts
        for slot, fact in new_result.hard_facts.items():
            if slot not in merged or prefer_new:
                merged[slot] = {
                    "value": fact.value,
                    "normalized": fact.normalized,
                    "tier": "hard",
                    "source": "regex",
                }
        
        # Process open tuples
        for tuple_fact in new_result.open_tuples:
            attr = tuple_fact.attribute
            if attr not in merged or prefer_new:
                merged[attr] = {
                    "value": tuple_fact.value,
                    "normalized": tuple_fact.normalized_value,
                    "tier": "open",
                    "source": "llm",
                    "confidence": tuple_fact.confidence,
                }
        
        return merged
    
    def classify_fact_tier(self, slot_or_attribute: str) -> str:
        """
        Determine which tier a fact belongs to.
        
        Args:
            slot_or_attribute: Slot name or attribute
            
        Returns:
            "hard" for Tier A, "open" for Tier B
        """
        return "hard" if slot_or_attribute in self.HARD_SLOTS else "open"


# Singleton instance for convenience
_default_system: Optional[TwoTierFactSystem] = None


def get_two_tier_system() -> TwoTierFactSystem:
    """
    Get the default two-tier fact system instance.
    
    Returns:
        Singleton TwoTierFactSystem instance
    """
    global _default_system
    if _default_system is None:
        _default_system = TwoTierFactSystem(enable_llm=False)  # Local-only: no external API
    return _default_system


def extract_two_tier_facts(text: str) -> TwoTierExtractionResult:
    """
    Convenience function to extract facts using the default system.
    
    Args:
        text: Input text
        
    Returns:
        TwoTierExtractionResult with hard facts and open tuples
    """
    return get_two_tier_system().extract_facts(text)

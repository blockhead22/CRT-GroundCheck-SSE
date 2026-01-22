"""Core grounding verification logic for GroundCheck."""

from typing import Dict, List, Optional, Set
import re
from difflib import SequenceMatcher

from .types import Memory, VerificationReport, ExtractedFact
from .fact_extractor import extract_fact_slots, split_compound_values
from .utils import (
    normalize_text,
    has_memory_claim,
    create_memory_claim_regex,
    parse_fact_from_memory_text
)


class GroundCheck:
    """Main verifier class for grounding verification.
    
    GroundCheck verifies that generated text is grounded in retrieved memories/context.
    It detects hallucinations by extracting claims from generated text and checking
    if they are supported by the provided memories.
    
    Example:
        >>> verifier = GroundCheck()
        >>> memories = [Memory(id="m1", text="User works at Microsoft")]
        >>> result = verifier.verify("You work at Amazon", memories)
        >>> print(result.passed)  # False
        >>> print(result.hallucinations)  # ["Amazon"]
    """
    
    def __init__(self):
        """Initialize the GroundCheck verifier."""
        self.memory_claim_regex = create_memory_claim_regex()
    
    def _normalize_value(self, value: str) -> str:
        """Normalize value for fuzzy matching.
        
        Args:
            value: String value to normalize
            
        Returns:
            Normalized lowercase string with articles removed
        """
        if not value:
            return ""
        v = str(value).lower().strip()
        # Remove articles
        v = re.sub(r'\b(a|an|the)\b', '', v)
        # Normalize whitespace
        v = ' '.join(v.split())
        return v
    
    def _is_value_supported(
        self,
        claimed: str,
        supported_values: Set[str],
        threshold: float = 0.85
    ) -> bool:
        """Check if a claimed value is supported with fuzzy matching.
        
        Args:
            claimed: The claimed value to check
            supported_values: Set of supported normalized values
            threshold: Similarity threshold for fuzzy matching (default: 0.85)
            
        Returns:
            True if value is supported (exact or fuzzy match), False otherwise
        """
        claimed_norm = self._normalize_value(claimed)
        
        # Empty claim is not supported
        if not claimed_norm:
            return False
        
        # Check each supported value
        for supported in supported_values:
            supported_norm = self._normalize_value(supported)
            
            # Exact match
            if claimed_norm == supported_norm:
                return True
            
            # Substring match (either direction)
            if claimed_norm in supported_norm or supported_norm in claimed_norm:
                return True
            
            # Fuzzy similarity match
            similarity = SequenceMatcher(None, claimed_norm, supported_norm).ratio()
            if similarity >= threshold:
                return True
            
            # Term overlap check (for phrases)
            claimed_terms = set(claimed_norm.split())
            supported_terms = set(supported_norm.split())
            if claimed_terms and supported_terms:
                overlap = len(claimed_terms & supported_terms) / len(claimed_terms)
                if overlap >= 0.7:  # 70% term overlap
                    return True
        
        return False
    
    def _find_memory_for_value(
        self,
        value: str,
        supported_values: Set[str],
        memory_map: Dict[str, str]
    ) -> Optional[str]:
        """Find which memory ID supports a given value.
        
        Args:
            value: The value to find support for
            supported_values: Set of supported normalized values
            memory_map: Map from normalized value to memory ID
            
        Returns:
            Memory ID that supports this value, or None
        """
        value_norm = self._normalize_value(value)
        
        # Try exact match first
        if value_norm in memory_map:
            return memory_map[value_norm]
        
        # Try fuzzy match
        for supported in supported_values:
            supported_norm = self._normalize_value(supported)
            # Check if they match (using same logic as _is_value_supported)
            if value_norm == supported_norm or \
               value_norm in supported_norm or \
               supported_norm in value_norm:
                # Return the memory ID for this supported value
                if supported_norm in memory_map:
                    return memory_map[supported_norm]
        
        # Fallback: Return any memory ID from the slot when fuzzy match succeeded
        # but exact normalized value isn't in the map. This can happen when
        # similarity scoring matched but the values differ slightly.
        # Since fuzzy matching already validated the semantic similarity,
        # any memory from this slot is a reasonable attribution.
        if memory_map:
            return next(iter(memory_map.values()))
        
        return None
    
    def verify(
        self,
        generated_text: str,
        retrieved_memories: List[Memory],
        mode: str = "strict"
    ) -> VerificationReport:
        """Verify that generated text is grounded in retrieved memories.
        
        Args:
            generated_text: The text to verify
            retrieved_memories: List of Memory objects containing supporting context
            mode: Verification mode - "strict" (generates corrections) or "permissive"
            
        Returns:
            VerificationReport with verification results
        """
        if not generated_text or not generated_text.strip():
            return VerificationReport(
                original=generated_text,
                passed=True,
                confidence=1.0
            )
        
        # Extract facts from generated text
        facts_extracted = extract_fact_slots(generated_text)
        
        # Build grounding map and collect hallucinations
        hallucinations = []
        grounding_map = {}
        supported_facts = {}
        
        # Parse supported facts from memories
        memory_facts_by_slot: Dict[str, Set[str]] = {}
        memory_id_by_slot_value: Dict[str, Dict[str, str]] = {}
        
        for memory in retrieved_memories:
            # Try parsing structured FACT: format
            parsed = parse_fact_from_memory_text(memory.text)
            if parsed:
                slot, value = parsed
                value_norm = normalize_text(value)
                memory_facts_by_slot.setdefault(slot, set()).add(value_norm)
                memory_id_by_slot_value.setdefault(slot, {})[value_norm] = memory.id
            
            # Also extract facts from memory text
            memory_facts = extract_fact_slots(memory.text)
            for slot, fact in memory_facts.items():
                # Split compound values in memories too
                fact_values = split_compound_values(str(fact.value))
                for val in fact_values:
                    val_norm = self._normalize_value(val)
                    if val_norm:
                        memory_facts_by_slot.setdefault(slot, set()).add(val_norm)
                        memory_id_by_slot_value.setdefault(slot, {})[val_norm] = memory.id
        
        # Check each extracted fact against memories
        for slot, fact in facts_extracted.items():
            slot_l = slot.lower()
            supported_values = memory_facts_by_slot.get(slot_l, set())
            
            # Split compound values from the generated text
            fact_values = split_compound_values(str(fact.value))
            
            # Track which individual values are supported
            all_supported = True
            for val in fact_values:
                val_norm = self._normalize_value(val)
                if not val_norm:
                    continue
                
                # Check if this individual value is supported (with fuzzy matching)
                if self._is_value_supported(val, supported_values):
                    # Find which memory supports this value
                    memory_id = self._find_memory_for_value(val, supported_values, memory_id_by_slot_value.get(slot_l, {}))
                    if memory_id:
                        grounding_map[val] = memory_id
                else:
                    # This value is not supported - it's a hallucination
                    hallucinations.append(val)
                    all_supported = False
            
            # Only mark the fact as supported if ALL values are supported
            if all_supported and fact_values:
                supported_facts[slot] = fact
        
        # Identify fully unsupported facts (for correction generation)
        unsupported_facts = {
            slot: fact for slot, fact in facts_extracted.items()
            if slot not in supported_facts
        }
        
        passed = len(hallucinations) == 0
        
        # Calculate confidence based on trust scores of supporting memories
        confidence = self._calculate_confidence(
            facts_extracted,
            supported_facts,
            grounding_map,
            retrieved_memories
        )
        
        # Generate corrected text if in strict mode and there are hallucinations
        corrected_text = None
        if mode == "strict" and not passed:
            corrected_text = self._generate_correction(
                generated_text,
                unsupported_facts,
                supported_facts,
                retrieved_memories
            )
        
        return VerificationReport(
            original=generated_text,
            corrected=corrected_text,
            passed=passed,
            hallucinations=hallucinations,
            grounding_map=grounding_map,
            confidence=confidence,
            facts_extracted=facts_extracted,
            facts_supported=supported_facts
        )
    
    def extract_claims(self, text: str) -> Dict[str, ExtractedFact]:
        """Extract factual claims from text.
        
        Args:
            text: Text to extract claims from
            
        Returns:
            Dictionary mapping slot names to ExtractedFact objects
        """
        return extract_fact_slots(text)
    
    def find_support(
        self,
        claim: ExtractedFact,
        memories: List[Memory]
    ) -> Optional[Memory]:
        """Find a memory that supports the given claim.
        
        Args:
            claim: The claim to find support for
            memories: List of memories to search
            
        Returns:
            Supporting Memory if found, None otherwise
        """
        claim_norm = self._normalize_value(str(claim.value))
        
        for memory in memories:
            # Parse structured facts from memory
            parsed = parse_fact_from_memory_text(memory.text)
            if parsed:
                slot, value = parsed
                if slot == claim.slot:
                    # Use fuzzy matching for structured facts
                    if self._is_value_supported(str(claim.value), {value}):
                        return memory
            
            # Extract facts from memory text
            memory_facts = extract_fact_slots(memory.text)
            if claim.slot in memory_facts:
                memory_fact = memory_facts[claim.slot]
                # Use fuzzy matching
                memory_values = split_compound_values(str(memory_fact.value))
                if self._is_value_supported(str(claim.value), set(memory_values)):
                    return memory
            
            # Fallback: fuzzy text matching in memory text
            memory_norm = self._normalize_value(memory.text)
            if claim_norm and (claim_norm in memory_norm or 
                              SequenceMatcher(None, claim_norm, memory_norm).ratio() > 0.6):
                return memory
        
        return None
    
    def build_grounding_map(
        self,
        claims: Dict[str, ExtractedFact],
        memories: List[Memory]
    ) -> Dict[str, str]:
        """Build a map from claims to supporting memory IDs.
        
        Args:
            claims: Dictionary of extracted claims
            memories: List of memories
            
        Returns:
            Dictionary mapping claim values to memory IDs
        """
        grounding_map = {}
        
        for slot, claim in claims.items():
            supporting_memory = self.find_support(claim, memories)
            if supporting_memory:
                grounding_map[str(claim.value)] = supporting_memory.id
        
        return grounding_map
    
        
    def _calculate_confidence(
        self,
        all_facts: Dict[str, ExtractedFact],
        supported_facts: Dict[str, ExtractedFact],
        grounding_map: Dict[str, str],
        memories: List[Memory]
    ) -> float:
        """Calculate confidence score for verification.
        
        Confidence is based on:
        - Ratio of supported facts to total facts
        - Trust scores of supporting memories
        """
        if not all_facts:
            return 1.0
        
        # Base confidence from support ratio
        support_ratio = len(supported_facts) / len(all_facts)
        
        # Weight by memory trust scores
        if grounding_map and memories:
            memory_by_id = {m.id: m for m in memories}
            trust_scores = []
            for memory_id in grounding_map.values():
                if memory_id in memory_by_id:
                    trust_scores.append(memory_by_id[memory_id].trust)
            
            if trust_scores:
                avg_trust = sum(trust_scores) / len(trust_scores)
                # Combine support ratio and average trust
                return (support_ratio + avg_trust) / 2.0
        
        return support_ratio
    
    def _generate_correction(
        self,
        original_text: str,
        unsupported_facts: Dict[str, ExtractedFact],
        supported_facts: Dict[str, ExtractedFact],
        memories: List[Memory]
    ) -> str:
        """Generate corrected text by replacing unsupported claims.
        
        This is a simple heuristic approach that replaces unsupported values
        with supported ones from the same slot if available.
        """
        if not unsupported_facts:
            return original_text
        
        # Check if this is a memory claim that should be sanitized
        if not has_memory_claim(original_text):
            # Simple replacement approach
            return self._simple_correction(
                original_text, unsupported_facts, supported_facts, memories
            )
        
        # For memory claims, use stricter sanitization
        return self._sanitize_memory_claims(
            original_text, unsupported_facts, supported_facts, memories
        )
    
    def _simple_correction(
        self,
        text: str,
        unsupported_facts: Dict[str, ExtractedFact],
        supported_facts: Dict[str, ExtractedFact],
        memories: List[Memory]
    ) -> str:
        """Simple correction by replacing unsupported values with supported ones.
        
        Looks for memories that have facts for the same slot as unsupported facts
        and replaces the unsupported value with the memory's value.
        """
        corrected = text
        
        # First try using supported_facts that were already extracted
        for slot, unsupported_fact in unsupported_facts.items():
            # If we have a supported fact for the same slot, replace it
            if slot in supported_facts:
                supported_fact = supported_facts[slot]
                unsupported_value = str(unsupported_fact.value)
                supported_value = str(supported_fact.value)
                
                # Simple string replacement
                corrected = corrected.replace(unsupported_value, supported_value)
            else:
                # Try to find a matching fact in memories for this slot
                for memory in memories:
                    memory_facts = extract_fact_slots(memory.text)
                    if slot in memory_facts:
                        memory_fact = memory_facts[slot]
                        unsupported_value = str(unsupported_fact.value)
                        supported_value = str(memory_fact.value)
                        corrected = corrected.replace(unsupported_value, supported_value)
                        break
        
        return corrected
    
    def _sanitize_memory_claims(
        self,
        text: str,
        unsupported_facts: Dict[str, ExtractedFact],
        supported_facts: Dict[str, ExtractedFact],
        memories: List[Memory]
    ) -> str:
        """Sanitize text with memory claims by removing unsupported statements.
        
        This follows the logic from the original _sanitize_unsupported_memory_claims.
        """
        if not unsupported_facts:
            return text
        
        # Create regex patterns for unsupported values
        bad_value_patterns = [
            re.compile(re.escape(str(fact.value)), re.I)
            for fact in unsupported_facts.values()
            if fact.value
        ]
        
        # Keep lines that don't contain memory claims or unsupported values
        kept_lines = []
        for line in text.splitlines():
            # Skip lines with memory claim phrases
            if self.memory_claim_regex.search(line):
                continue
            # Skip lines with unsupported values
            if any(pattern.search(line) for pattern in bad_value_patterns):
                continue
            kept_lines.append(line)
        
        cleaned = "\n".join(kept_lines).strip()
        
        # Add disclaimer about missing information
        first_slot = next(iter(unsupported_facts.keys()))
        disclaimer = f"I don't have reliable stored information for your {first_slot} yet — if you tell me, I can store it going forward."
        
        if cleaned:
            return cleaned + f"\n\n{disclaimer}"
        
        return disclaimer

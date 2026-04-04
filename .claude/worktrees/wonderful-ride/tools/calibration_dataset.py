"""
Golden Test Set for CRT Calibration.

Provides labeled pairs of texts for calibrating similarity thresholds.
These pairs are categorized as:
- exact_match: Identical or nearly identical texts
- paraphrase: Same meaning, different wording
- near_miss: Related but different facts (high risk of false positives)
- contradiction: Mutually exclusive facts

Usage:
    from tools.calibration_dataset import GOLDEN_PAIRS, get_pairs_by_category
    
    # Get all paraphrases
    paraphrases = get_pairs_by_category("paraphrase")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional


@dataclass
class CalibrationPair:
    """
    A labeled pair of texts for calibration.
    
    Attributes:
        text1: First text
        text2: Second text
        category: Label category (exact_match, paraphrase, near_miss, contradiction)
        domain: Optional domain (employer, location, name, etc.)
        notes: Optional notes about the pair
    """
    text1: str
    text2: str
    category: str  # exact_match, paraphrase, near_miss, contradiction
    domain: Optional[str] = None
    notes: Optional[str] = None
    
    def to_tuple(self) -> Tuple[str, str, str]:
        """Convert to simple tuple format."""
        return (self.text1, self.text2, self.category)


# ============================================================================
# GOLDEN PAIRS - Hand-labeled calibration data
# ============================================================================

GOLDEN_PAIRS: List[CalibrationPair] = [
    # ========================================
    # EXACT MATCHES
    # ========================================
    CalibrationPair(
        text1="Microsoft",
        text2="Microsoft",
        category="exact_match",
        domain="employer",
    ),
    CalibrationPair(
        text1="Seattle",
        text2="Seattle",
        category="exact_match",
        domain="location",
    ),
    CalibrationPair(
        text1="I work at Google",
        text2="I work at Google",
        category="exact_match",
        domain="employer",
    ),
    CalibrationPair(
        text1="My name is Sarah",
        text2="My name is Sarah",
        category="exact_match",
        domain="name",
    ),
    CalibrationPair(
        text1="I'm a software engineer",
        text2="I'm a software engineer",
        category="exact_match",
        domain="occupation",
    ),
    
    # ========================================
    # PARAPHRASES (same meaning, different wording)
    # ========================================
    CalibrationPair(
        text1="I work at Google",
        text2="I'm employed by Google",
        category="paraphrase",
        domain="employer",
        notes="Active vs passive voice",
    ),
    CalibrationPair(
        text1="San Francisco",
        text2="SF",
        category="paraphrase",
        domain="location",
        notes="Abbreviation",
    ),
    CalibrationPair(
        text1="I live in Seattle",
        text2="I'm based in Seattle",
        category="paraphrase",
        domain="location",
    ),
    CalibrationPair(
        text1="My name is Nick",
        text2="I'm Nick",
        category="paraphrase",
        domain="name",
    ),
    CalibrationPair(
        text1="I'm a senior developer",
        text2="I work as a senior developer",
        category="paraphrase",
        domain="occupation",
    ),
    CalibrationPair(
        text1="I graduated from MIT",
        text2="I went to MIT for my degree",
        category="paraphrase",
        domain="education",
    ),
    CalibrationPair(
        text1="My favorite color is blue",
        text2="I like blue the most",
        category="paraphrase",
        domain="preference",
    ),
    CalibrationPair(
        text1="I have two siblings",
        text2="I have 2 brothers and sisters",
        category="paraphrase",
        domain="family",
    ),
    CalibrationPair(
        text1="I prefer working from home",
        text2="I like remote work",
        category="paraphrase",
        domain="preference",
    ),
    CalibrationPair(
        text1="I'm 28 years old",
        text2="I am twenty-eight",
        category="paraphrase",
        domain="age",
    ),
    
    # ========================================
    # NEAR MISSES (related but different - false positive risk)
    # ========================================
    CalibrationPair(
        text1="Microsoft",
        text2="Meta",
        category="near_miss",
        domain="employer",
        notes="Both tech companies starting with M",
    ),
    CalibrationPair(
        text1="Seattle",
        text2="Portland",
        category="near_miss",
        domain="location",
        notes="Both Pacific Northwest cities",
    ),
    CalibrationPair(
        text1="Google",
        text2="Alphabet",
        category="near_miss",
        domain="employer",
        notes="Parent company vs subsidiary",
    ),
    CalibrationPair(
        text1="San Francisco",
        text2="San Jose",
        category="near_miss",
        domain="location",
        notes="Both Bay Area cities",
    ),
    CalibrationPair(
        text1="software engineer",
        text2="software developer",
        category="near_miss",
        domain="occupation",
        notes="Similar but technically different titles",
    ),
    CalibrationPair(
        text1="I live in Seattle metro",
        text2="I live in Bellevue",
        category="near_miss",
        domain="location",
        notes="Metro area vs specific city",
    ),
    CalibrationPair(
        text1="MIT",
        text2="Stanford",
        category="near_miss",
        domain="education",
        notes="Both elite tech schools",
    ),
    CalibrationPair(
        text1="Python",
        text2="JavaScript",
        category="near_miss",
        domain="programming",
        notes="Different languages",
    ),
    CalibrationPair(
        text1="I'm a data scientist",
        text2="I'm a data analyst",
        category="near_miss",
        domain="occupation",
        notes="Related but different roles",
    ),
    CalibrationPair(
        text1="I work at Amazon Web Services",
        text2="I work at Amazon",
        category="near_miss",
        domain="employer",
        notes="Division vs parent company",
    ),
    
    # ========================================
    # CONTRADICTIONS (mutually exclusive)
    # ========================================
    CalibrationPair(
        text1="I work at Google",
        text2="I work at Microsoft",
        category="contradiction",
        domain="employer",
    ),
    CalibrationPair(
        text1="My name is Alice",
        text2="My name is Bob",
        category="contradiction",
        domain="name",
    ),
    CalibrationPair(
        text1="I live in Seattle",
        text2="I live in New York",
        category="contradiction",
        domain="location",
    ),
    CalibrationPair(
        text1="I'm 25 years old",
        text2="I'm 35 years old",
        category="contradiction",
        domain="age",
    ),
    CalibrationPair(
        text1="I graduated in 2015",
        text2="I graduated in 2020",
        category="contradiction",
        domain="education",
    ),
    CalibrationPair(
        text1="My favorite color is red",
        text2="My favorite color is blue",
        category="contradiction",
        domain="preference",
    ),
    CalibrationPair(
        text1="I prefer dark roast coffee",
        text2="I prefer light roast coffee",
        category="contradiction",
        domain="preference",
    ),
    CalibrationPair(
        text1="I have a dog named Max",
        text2="I have a cat named Luna",
        category="contradiction",
        domain="pet",
        notes="Different pet types",
    ),
    CalibrationPair(
        text1="I work as a teacher",
        text2="I work as a lawyer",
        category="contradiction",
        domain="occupation",
    ),
    CalibrationPair(
        text1="I'm single",
        text2="I'm married",
        category="contradiction",
        domain="relationship",
    ),
    
    # ========================================
    # ADDITIONAL DOMAIN-SPECIFIC PAIRS
    # ========================================
    
    # Employment edge cases
    CalibrationPair(
        text1="I'm self-employed",
        text2="I work for myself",
        category="paraphrase",
        domain="employer",
    ),
    CalibrationPair(
        text1="I'm a freelancer",
        text2="I work at IBM",
        category="contradiction",
        domain="employer",
    ),
    CalibrationPair(
        text1="I'm currently unemployed",
        text2="I work at Apple",
        category="contradiction",
        domain="employer",
    ),
    
    # Location refinements
    CalibrationPair(
        text1="I live in the Bay Area",
        text2="I live in San Francisco",
        category="near_miss",
        domain="location",
        notes="Area vs specific city - could be refinement",
    ),
    CalibrationPair(
        text1="I'm from the East Coast",
        text2="I'm from the West Coast",
        category="contradiction",
        domain="location",
    ),
    
    # Name variations
    CalibrationPair(
        text1="My name is Robert",
        text2="Call me Bob",
        category="paraphrase",
        domain="name",
        notes="Formal name vs nickname",
    ),
    CalibrationPair(
        text1="I'm Dr. Smith",
        text2="I'm John Smith",
        category="paraphrase",
        domain="name",
        notes="Title vs full name",
    ),
    
    # Preference nuances
    CalibrationPair(
        text1="I love hiking",
        text2="I enjoy hiking",
        category="paraphrase",
        domain="preference",
    ),
    CalibrationPair(
        text1="I hate mornings",
        text2="I love mornings",
        category="contradiction",
        domain="preference",
    ),
]


def get_pairs_by_category(category: str) -> List[CalibrationPair]:
    """
    Get all pairs for a specific category.
    
    Args:
        category: One of "exact_match", "paraphrase", "near_miss", "contradiction"
        
    Returns:
        List of CalibrationPair objects matching the category
    """
    return [p for p in GOLDEN_PAIRS if p.category == category]


def get_pairs_by_domain(domain: str) -> List[CalibrationPair]:
    """
    Get all pairs for a specific domain.
    
    Args:
        domain: Domain name (e.g., "employer", "location", "name")
        
    Returns:
        List of CalibrationPair objects matching the domain
    """
    return [p for p in GOLDEN_PAIRS if p.domain == domain]


def get_category_counts() -> Dict[str, int]:
    """
    Get count of pairs per category.
    
    Returns:
        Dictionary of category -> count
    """
    counts: Dict[str, int] = {}
    for pair in GOLDEN_PAIRS:
        counts[pair.category] = counts.get(pair.category, 0) + 1
    return counts


def get_all_tuples() -> List[Tuple[str, str, str]]:
    """
    Get all pairs as simple tuples.
    
    Returns:
        List of (text1, text2, category) tuples
    """
    return [p.to_tuple() for p in GOLDEN_PAIRS]


def extend_dataset(new_pairs: List[CalibrationPair]) -> None:
    """
    Extend the golden dataset with new pairs.
    
    Note: This only affects the in-memory list, not the source file.
    
    Args:
        new_pairs: List of new CalibrationPair objects to add
    """
    GOLDEN_PAIRS.extend(new_pairs)


# Quick sanity check on import
def _validate_dataset():
    """Validate dataset integrity."""
    valid_categories = {"exact_match", "paraphrase", "near_miss", "contradiction"}
    for pair in GOLDEN_PAIRS:
        if pair.category not in valid_categories:
            raise ValueError(f"Invalid category '{pair.category}' in pair: {pair}")

_validate_dataset()

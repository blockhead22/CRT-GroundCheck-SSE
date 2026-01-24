"""
Resolution Pattern Configuration

This module defines the natural language patterns used to detect when a user
is trying to resolve a contradiction. These patterns are used in NL contradiction
resolution to determine user intent.

New patterns can be added here without modifying core logic.
"""

from typing import List, Dict, Any
import re


# Core resolution patterns (regex patterns)
# Each pattern is a regex that matches user intent to resolve a contradiction
RESOLUTION_PATTERNS = [
    # Explicit correctness statements
    r'\b(is|was)\s+(correct|right|accurate)\b',
    
    # Revision markers
    r'\bactually\b',
    r'\bi\s+meant\b',
    
    # Job/employer changes
    r'\bswitched\s+(jobs|to|companies)\b',
    r'\bchanged\s+to\b',  # More general: "changed to" anything
    r'\bchanged\s+(jobs|companies)\b',  # Specific: "changed jobs"
    r'\bmoved\s+to\b',
    r'\bnow\s+(work|working|at)\b',
    
    # Correctness confirmations
    r'\bcorrect\s+(one|version|answer|status|value|info|information|statement)\b',
    r'\b(that|this)(?:\s*\'s|\s+is)\s+(correct|right|accurate)\b',  # "that's correct"
    
    # Ignore/discard patterns
    r'\bignore\s+(the|that)\b',  # "ignore the red"
    
    # Correction patterns
    r'\b(no|wait)\b.*\b(was|is)\s+(right|correct)\b',  # "no wait, X was right"
    
    # NEW: Keep old value patterns
    r'\bkeep\s+(the\s+)?(old|previous|original|first)\b',
    r'\bstick\s+with\s+(the\s+)?(old|previous|original|first)\b',
    r'\bstick\s+with\s+([A-Za-z0-9\s]+)',  # "stick with X"
    
    # NEW: Preference patterns
    r'\bgo\s+with\s+([A-Za-z0-9\s]+)',  # "go with X"
    r'\bprefer\s+([A-Za-z0-9\s]+)',  # "prefer X"
    r'\buse\s+([A-Za-z0-9\s]+)\s+instead\b',  # "use X instead"
    
    # NEW: Update/override patterns
    r'\breplace\s+(with|it\s+with)\s+([A-Za-z0-9\s]+)',  # "replace with X"
    r'\boverride\s+(with|to)\s+([A-Za-z0-9\s]+)',  # "override with X"
    r'\bupdate\s+(to|it\s+to)\s+([A-Za-z0-9\s]+)',  # "update to X"
    
    # NEW: Choice patterns
    r'\bchoose\s+([A-Za-z0-9\s]+)',  # "choose X"
    r'\bselect\s+([A-Za-z0-9\s]+)',  # "select X"
    r'\bpick\s+([A-Za-z0-9\s]+)',  # "pick X"
]


def has_resolution_intent(text: str) -> bool:
    """
    Check if user text contains any resolution intent pattern.
    
    Args:
        text: User input text to check
        
    Returns:
        True if any resolution pattern matches, False otherwise
    """
    return any(
        re.search(pattern, text, re.IGNORECASE) 
        for pattern in RESOLUTION_PATTERNS
    )


def get_matched_patterns(text: str) -> List[Dict[str, Any]]:
    """
    Get all matched resolution patterns with their details.
    
    Args:
        text: User input text to check
        
    Returns:
        List of dicts with 'pattern', 'match', and 'groups' for each match
    """
    matches = []
    for pattern in RESOLUTION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            matches.append({
                'pattern': pattern,
                'match': match.group(0),
                'groups': match.groups() if match.groups() else None,
                'start': match.start(),
                'end': match.end(),
            })
    return matches


def add_custom_pattern(pattern: str) -> None:
    """
    Add a custom resolution pattern at runtime.
    
    Args:
        pattern: Regex pattern string to add
        
    Example:
        add_custom_pattern(r'\bswap\s+to\s+([A-Za-z0-9\s]+)')
    """
    if pattern not in RESOLUTION_PATTERNS:
        RESOLUTION_PATTERNS.append(pattern)


def get_all_patterns() -> List[str]:
    """
    Get all currently registered resolution patterns.
    
    Returns:
        List of regex pattern strings
    """
    return RESOLUTION_PATTERNS.copy()


# Pattern documentation for debugging and extension
PATTERN_DESCRIPTIONS = {
    r'\b(is|was)\s+(correct|right|accurate)\b': 
        "Explicit correctness: 'X is correct', 'Y was right'",
    
    r'\bactually\b': 
        "Revision marker: 'Actually, it's X'",
    
    r'\bi\s+meant\b': 
        "Clarification: 'I meant X'",
    
    r'\bswitched\s+(jobs|to|companies)\b': 
        "Job change: 'switched jobs', 'switched to X'",
    
    r'\bchanged\s+to\b': 
        "General change: 'changed to X'",
    
    r'\bchanged\s+(jobs|companies)\b': 
        "Specific change: 'changed jobs'",
    
    r'\bmoved\s+to\b': 
        "Location/employer change: 'moved to X'",
    
    r'\bnow\s+(work|working|at)\b': 
        "Current status: 'now working at X'",
    
    r'\bcorrect\s+(one|version|answer|status|value|info|information|statement)\b': 
        "Correctness confirmation: 'correct answer', 'correct value'",
    
    r'\b(that|this)(?:\s*\'s|\s+is)\s+(correct|right|accurate)\b': 
        "Demonstrative correctness: 'that's correct', 'this is right'",
    
    r'\bignore\s+(the|that)\b': 
        "Discard: 'ignore the X', 'ignore that'",
    
    r'\b(no|wait)\b.*\b(was|is)\s+(right|correct)\b': 
        "Correction: 'no wait, X was right'",
    
    r'\bkeep\s+(the\s+)?(old|previous|original|first)\b': 
        "Keep old: 'keep the old value', 'keep original'",
    
    r'\bstick\s+with\s+(the\s+)?(old|previous|original|first)\b': 
        "Stick with old: 'stick with the old one'",
    
    r'\bstick\s+with\s+([A-Za-z0-9\s]+)': 
        "Stick with value: 'stick with X'",
    
    r'\bgo\s+with\s+([A-Za-z0-9\s]+)': 
        "Choose value: 'go with X'",
    
    r'\bprefer\s+([A-Za-z0-9\s]+)': 
        "Preference: 'prefer X'",
    
    r'\buse\s+([A-Za-z0-9\s]+)\s+instead\b': 
        "Replacement: 'use X instead'",
    
    r'\breplace\s+(with|it\s+with)\s+([A-Za-z0-9\s]+)': 
        "Replace: 'replace with X'",
    
    r'\boverride\s+(with|to)\s+([A-Za-z0-9\s]+)': 
        "Override: 'override with X'",
    
    r'\bupdate\s+(to|it\s+to)\s+([A-Za-z0-9\s]+)': 
        "Update: 'update to X'",
    
    r'\bchoose\s+([A-Za-z0-9\s]+)': 
        "Choice: 'choose X'",
    
    r'\bselect\s+([A-Za-z0-9\s]+)': 
        "Selection: 'select X'",
    
    r'\bpick\s+([A-Za-z0-9\s]+)': 
        "Pick: 'pick X'",
}


def get_pattern_description(pattern: str) -> str:
    """
    Get human-readable description of a pattern.
    
    Args:
        pattern: Regex pattern string
        
    Returns:
        Description string, or the pattern itself if no description exists
    """
    return PATTERN_DESCRIPTIONS.get(pattern, pattern)

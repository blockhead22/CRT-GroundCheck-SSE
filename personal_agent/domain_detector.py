"""
Domain Detection Module for Phase 2.0 Context-Aware Memory.

Detects relevant domains from text content to enable:
- Multi-faceted user profiles (photographer + programmer + business owner)
- Domain-specific fact storage and retrieval
- Contextual contradiction detection (same slot, different domains = not a conflict)

Philosophy:
- Users have multiple life contexts (work, hobbies, businesses)
- Facts should be tagged with their relevant domain(s)
- Domain context helps disambiguate queries like "What's my most recent order?"
"""

from __future__ import annotations

import re
from typing import List, Dict, Set, Optional
from dataclasses import dataclass


# ============================================================================
# Domain Keyword Mappings
# ============================================================================

DOMAIN_KEYWORDS: Dict[str, Set[str]] = {
    # Business & Commerce
    "print_shop": {
        "sticker", "print", "vinyl", "decal", "order", "customer", "label",
        "printing", "design", "graphic", "merchandise", "shop", "lair",
        "laminate", "cut", "contour", "shipping", "etsy", "ebay"
    },
    "retail": {
        "store", "customer", "inventory", "register", "shift", "warehouse",
        "retail", "sales", "cashier", "stock", "merchandise", "manager",
        "walmart", "target", "costco", "amazon"
    },
    "small_business": {
        "business", "owner", "run", "startup", "entrepreneur", "self-employed",
        "freelance", "client", "invoice", "revenue", "profit", "llc"
    },
    
    # Technology & Development
    "programming": {
        "code", "programming", "developer", "software", "app", "debug",
        "python", "javascript", "java", "c++", "rust", "typescript",
        "api", "backend", "frontend", "database", "algorithm", "git"
    },
    "web_dev": {
        "website", "html", "css", "web", "deploy", "hosting", "domain",
        "react", "vue", "angular", "node", "django", "flask", "wordpress"
    },
    "data_science": {
        "data", "analysis", "machine learning", "ml", "ai", "model",
        "dataset", "training", "neural", "tensorflow", "pytorch", "pandas"
    },
    
    # Creative & Media
    "photography": {
        "photo", "shoot", "camera", "editing", "wedding", "portrait",
        "lens", "lightroom", "photoshop", "studio", "session", "album"
    },
    "videography": {
        "video", "film", "footage", "editing", "youtube", "vlog",
        "premiere", "davinci", "drone", "b-roll", "cinematography"
    },
    "design": {
        "design", "illustrator", "graphic", "logo", "branding", "ui", "ux",
        "figma", "sketch", "mockup", "wireframe", "creative"
    },
    "music": {
        "music", "song", "album", "guitar", "piano", "band", "concert",
        "recording", "studio", "mixing", "producer", "spotify"
    },
    
    # Personal & Lifestyle
    "family": {
        "family", "kids", "children", "spouse", "wife", "husband", "parent",
        "son", "daughter", "baby", "wedding", "anniversary"
    },
    "health": {
        "health", "fitness", "workout", "gym", "diet", "doctor", "medical",
        "exercise", "running", "yoga", "meditation", "sleep"
    },
    "education": {
        "school", "university", "college", "degree", "student", "professor",
        "course", "class", "homework", "exam", "graduation", "masters", "phd"
    },
    "hobbies": {
        "hobby", "game", "gaming", "travel", "reading", "cooking", "garden",
        "sports", "hiking", "camping", "craft", "diy"
    },
    
    # Finance & Career
    "finance": {
        "money", "budget", "investment", "savings", "bank", "tax", "salary",
        "income", "expense", "retirement", "401k", "stocks", "crypto"
    },
    "career": {
        "job", "career", "resume", "interview", "promotion", "salary",
        "manager", "team", "meeting", "project", "deadline", "work"
    },
}

# Domain aliases - map variations to canonical domain names
DOMAIN_ALIASES: Dict[str, str] = {
    "coding": "programming",
    "dev": "programming",
    "development": "programming",
    "tech": "programming",
    "pics": "photography",
    "photos": "photography",
    "videos": "videography",
    "film": "videography",
    "art": "design",
    "graphics": "design",
    "shop": "small_business",
    "store": "retail",
}


@dataclass
class DomainMatch:
    """Result of domain detection for a text."""
    domains: List[str]
    confidence_scores: Dict[str, float]
    keyword_matches: Dict[str, List[str]]
    
    @property
    def primary_domain(self) -> str:
        """Get the highest-confidence domain, or 'general' if none found."""
        if not self.domains:
            return "general"
        return self.domains[0]
    
    def has_domain(self, domain: str) -> bool:
        """Check if a specific domain was detected."""
        return domain in self.domains


def detect_domains(text: str, min_keyword_matches: int = 1) -> List[str]:
    """
    Detect relevant domains from text content.
    
    Args:
        text: The text to analyze
        min_keyword_matches: Minimum keyword matches to include a domain
        
    Returns:
        List of detected domain names, sorted by relevance (most matches first).
        Returns ["general"] if no specific domains detected.
    """
    if not text:
        return ["general"]
    
    text_lower = text.lower()
    domain_scores: Dict[str, int] = {}
    
    for domain, keywords in DOMAIN_KEYWORDS.items():
        match_count = sum(1 for kw in keywords if kw in text_lower)
        if match_count >= min_keyword_matches:
            domain_scores[domain] = match_count
    
    if not domain_scores:
        return ["general"]
    
    # Sort by match count (descending)
    sorted_domains = sorted(domain_scores.keys(), key=lambda d: domain_scores[d], reverse=True)
    return sorted_domains


def detect_domains_detailed(text: str, min_keyword_matches: int = 1) -> DomainMatch:
    """
    Detect domains with detailed confidence scores and keyword matches.
    
    More detailed version of detect_domains() that returns:
    - Confidence scores for each domain
    - Which keywords matched for each domain
    
    Args:
        text: The text to analyze
        min_keyword_matches: Minimum keyword matches to include a domain
        
    Returns:
        DomainMatch with detailed detection results
    """
    if not text:
        return DomainMatch(domains=["general"], confidence_scores={}, keyword_matches={})
    
    text_lower = text.lower()
    domain_scores: Dict[str, float] = {}
    keyword_matches: Dict[str, List[str]] = {}
    
    for domain, keywords in DOMAIN_KEYWORDS.items():
        matches = [kw for kw in keywords if kw in text_lower]
        if len(matches) >= min_keyword_matches:
            # Confidence based on % of keywords matched (capped at 1.0)
            confidence = min(len(matches) / 3.0, 1.0)  # 3+ matches = max confidence
            domain_scores[domain] = confidence
            keyword_matches[domain] = matches
    
    if not domain_scores:
        return DomainMatch(domains=["general"], confidence_scores={}, keyword_matches={})
    
    # Sort by confidence (descending)
    sorted_domains = sorted(domain_scores.keys(), key=lambda d: domain_scores[d], reverse=True)
    
    return DomainMatch(
        domains=sorted_domains,
        confidence_scores=domain_scores,
        keyword_matches=keyword_matches
    )


def get_domain_overlap(domains1: List[str], domains2: List[str]) -> Set[str]:
    """
    Get the overlap between two domain lists.
    
    Used for contradiction detection: facts in overlapping domains
    may conflict, while facts in disjoint domains can coexist.
    
    Args:
        domains1: First list of domains
        domains2: Second list of domains
        
    Returns:
        Set of domains that appear in both lists
    """
    # Handle "general" domain - it overlaps with everything
    set1 = set(domains1)
    set2 = set(domains2)
    
    # If either is only "general", consider it overlapping
    if set1 == {"general"} or set2 == {"general"}:
        return set1 | set2
    
    return set1 & set2


def domains_are_compatible(domains1: List[str], domains2: List[str]) -> bool:
    """
    Check if two domain lists are compatible (can coexist without contradiction).
    
    Two fact sets are compatible if:
    - They have no overlapping domains, OR
    - One or both are "general" (unclassified)
    
    Args:
        domains1: First list of domains
        domains2: Second list of domains
        
    Returns:
        True if the domains are compatible (can coexist)
    """
    overlap = get_domain_overlap(domains1, domains2)
    
    # Empty overlap = compatible (different contexts)
    if not overlap:
        return True
    
    # "general" only = compatible (unclassified facts don't conflict with specific ones)
    if overlap == {"general"}:
        return True
    
    # Specific overlap = potential conflict
    return False


def normalize_domain(domain: str) -> str:
    """
    Normalize a domain name using aliases.
    
    Args:
        domain: The domain name to normalize
        
    Returns:
        Canonical domain name
    """
    domain_lower = domain.lower().strip()
    return DOMAIN_ALIASES.get(domain_lower, domain_lower)


def extract_domains_from_context(context: Optional[Dict]) -> List[str]:
    """
    Extract domain tags from a memory's context field.
    
    Args:
        context: Memory context dictionary (may contain 'domain_tags')
        
    Returns:
        List of domains from context, or ["general"] if not found
    """
    if not context:
        return ["general"]
    
    # Try to get domain_tags field
    domain_tags = context.get("domain_tags")
    if domain_tags:
        if isinstance(domain_tags, list):
            return domain_tags if domain_tags else ["general"]
        if isinstance(domain_tags, str):
            # Parse JSON or comma-separated string
            import json
            try:
                parsed = json.loads(domain_tags)
                if isinstance(parsed, list):
                    return parsed if parsed else ["general"]
            except (json.JSONDecodeError, TypeError):
                # Try comma-separated
                return [d.strip() for d in domain_tags.split(",") if d.strip()] or ["general"]
    
    return ["general"]


# ============================================================================
# Query Domain Detection (for retrieval filtering)
# ============================================================================

# Patterns that indicate a query is about a specific domain
QUERY_DOMAIN_PATTERNS: Dict[str, List[str]] = {
    "print_shop": [
        r"\b(?:sticker|print|vinyl|order|customer)\b",
        r"\b(?:printing|decal|label|merchandise)\b",
    ],
    "programming": [
        r"\b(?:code|coding|programming|developer|software|app|debug)\b",
        r"\b(?:python|javascript|api|backend|frontend)\b",
    ],
    "photography": [
        r"\b(?:photo|photograph|camera|shoot|editing)\b",
        r"\b(?:portrait|wedding|studio|lightroom)\b",
    ],
    "career": [
        r"\b(?:job|work|career|employer|company|team)\b",
        r"\b(?:salary|interview|resume|promotion)\b",
    ],
}


def detect_query_domains(query: str) -> List[str]:
    """
    Detect which domains a query is asking about.
    
    Used to filter retrieval to relevant domain contexts.
    
    Args:
        query: The user's query
        
    Returns:
        List of detected domains, or ["general"] if unclear
    """
    if not query:
        return ["general"]
    
    query_lower = query.lower()
    detected = []
    
    for domain, patterns in QUERY_DOMAIN_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                detected.append(domain)
                break
    
    return detected if detected else ["general"]

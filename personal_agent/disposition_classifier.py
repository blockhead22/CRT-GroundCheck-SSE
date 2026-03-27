"""Contradiction Disposition Classifier — Phase 1 (Rule-Based)

Classifies detected contradictions into four dispositions:
  - RESOLVABLE: one side is outdated or factually wrong. Fix it.
  - HELD: both are true simultaneously. Preserve both.
  - EVOLVING: user is changing their mind. Watch it.
  - CONTEXTUAL: same belief, different activation by context.

Uses: subjectivity detection, temporal gap, entity specificity,
      semantic similarity, sentiment analysis.

No ML models required for Phase 1 — pure heuristics + off-the-shelf
NLI if available.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Tuple
import re
import time


class Disposition(Enum):
    RESOLVABLE = "resolvable"
    HELD = "held"
    EVOLVING = "evolving"
    CONTEXTUAL = "contextual"
    UNKNOWN = "unknown"


@dataclass
class DispositionSignals:
    """Raw signals extracted from a contradiction pair."""
    subjectivity_a: float = 0.0      # 0=objective, 1=subjective
    subjectivity_b: float = 0.0
    temporal_gap_days: float = 0.0    # days between statements
    entity_specificity: float = 0.0   # 0=vague, 1=specific entities
    semantic_similarity: float = 0.0  # cosine sim between embeddings
    sentiment_a: float = 0.0          # -1=negative, 0=neutral, 1=positive
    sentiment_b: float = 0.0
    has_negation: bool = False        # explicit negation pattern
    has_temporal_marker: bool = False  # "used to", "now", "anymore"
    has_context_marker: bool = False   # "at work", "at home", "with friends"
    domain: str = "general"           # fact|preference|event|belief|identity


@dataclass
class DispositionResult:
    """Classification result with explanation."""
    disposition: Disposition
    confidence: float               # 0-1, how sure are we
    signals: DispositionSignals
    explanation: str                 # human-readable reason
    rule_trace: List[str] = field(default_factory=list)  # which rules fired


# ---------------------------------------------------------------------------
# Signal extractors (Phase 1 — heuristic, no ML)
# ---------------------------------------------------------------------------

# Subjectivity indicators
_SUBJECTIVE_MARKERS = {
    # Opinion words
    'think', 'believe', 'feel', 'prefer', 'love', 'hate', 'enjoy',
    'dislike', 'want', 'wish', 'hope', 'afraid', 'worried', 'excited',
    'happy', 'sad', 'angry', 'frustrated', 'proud', 'ashamed',
    # Hedging
    'maybe', 'perhaps', 'probably', 'might', 'could be', 'seems like',
    'kind of', 'sort of', 'honestly', 'personally', 'in my opinion',
    'i guess', 'i suppose',
    # Identity
    'i am', "i'm", 'i consider myself', 'i identify as',
}

_OBJECTIVE_MARKERS = {
    # Factual patterns
    'is located', 'was born', 'costs', 'weighs', 'measures',
    'founded in', 'established', 'created by', 'invented',
    'according to', 'data shows', 'studies show', 'research indicates',
    # Employment / location / status — verifiable facts
    'i work at', 'i work for', 'i live in', 'i moved to',
    'my address', 'my phone', 'my email', 'my salary',
    'i graduated', 'i majored in', 'my degree',
    'i was hired', 'i got fired', 'i was promoted',
    # Dates and numbers often indicate facts
    'on monday', 'on tuesday', 'on wednesday', 'on thursday', 'on friday',
    'at noon', 'at midnight', 'in january', 'in february',
}

_TEMPORAL_MARKERS = {
    'used to', 'no longer', 'anymore', 'not anymore', 'now i',
    'these days', 'lately', 'recently', 'back then', 'in the past',
    'i changed', 'i switched', 'i moved', 'i quit', 'i started',
    'i stopped', 'previously', 'formerly',
    'thinking about', 'considering', 'been looking into',
    'been wanting to', 'starting to think', 'beginning to',
}

_CONTEXT_MARKERS = {
    'at work', 'at home', 'at school', 'with friends', 'with family',
    'in public', 'in private', 'when alone', 'around people',
    'on weekends', 'during the week', 'in the morning', 'at night',
    'professionally', 'personally', 'socially',
    'when stressed', 'when relaxed', 'when tired',
}

_NEGATION_PATTERNS = [
    r"\bi(?:'m| am) not\b",
    r"\bi don(?:'t|t) (?:like|want|think|believe|enjoy)\b",
    r"\bi(?:'m| am) no longer\b",
    r"\bi never\b",
    r"\bi hate\b.*\bi (?:love|like)\b",
    r"\bi (?:love|like)\b.*\bi hate\b",
    r"\bnot (?:a |an |the )?\w+\b",
]

# Entity specificity — proper nouns, numbers, dates
_ENTITY_PATTERNS = [
    r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)+\b',  # Proper nouns (multi-word)
    r'(?<!\. )(?<!\.\s)\b[A-Z][a-z]{2,}\b(?!\s[a-z])',  # Single-word proper nouns (not sentence start)
    r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',   # Dates
    r'\b\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?\b', # Times
    r'\b\$\d+(?:,\d{3})*(?:\.\d{2})?\b',     # Money
    r'\b\d+(?:\.\d+)?%\b',                    # Percentages
    r'\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
    r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b',
    # Known entity words (companies, places, etc.)
    r'\b(?:Google|Microsoft|Apple|Amazon|Meta|Netflix|Tesla|Uber|Airbnb)\b',
    r'\b(?:Python|React|Vue|Angular|JavaScript|TypeScript|Rust|Go|Java)\b',
]

# Sentiment words
_POSITIVE_WORDS = {
    'love', 'great', 'amazing', 'wonderful', 'fantastic', 'excellent',
    'happy', 'enjoy', 'excited', 'proud', 'grateful', 'blessed',
    'awesome', 'incredible', 'perfect', 'beautiful', 'brilliant',
    'thrilled', 'delighted', 'passionate', 'fulfilled',
}

_NEGATIVE_WORDS = {
    'hate', 'terrible', 'awful', 'horrible', 'worst', 'miserable',
    'angry', 'frustrated', 'depressed', 'anxious', 'stressed',
    'exhausted', 'overwhelmed', 'disgusted', 'disappointed',
    'killing me', 'can\'t stand', 'fed up', 'sick of', 'burned out',
}

# Domain classification
_IDENTITY_MARKERS = {
    'i am', "i'm", 'i consider myself', 'i identify as',
    'i\'m a', 'i am a', 'as a', 'my identity',
}

_PREFERENCE_MARKERS = {
    'i prefer', 'i like', 'i enjoy', 'i love', 'i hate',
    'my favorite', 'i\'d rather', 'i choose',
}

_EVENT_MARKERS = {
    'meeting', 'appointment', 'deadline', 'event', 'party',
    'scheduled', 'tomorrow', 'next week', 'this weekend',
}


def extract_subjectivity(text: str) -> float:
    """Heuristic subjectivity score. 0=objective, 1=subjective."""
    text_lower = text.lower()
    subj_hits = sum(1 for m in _SUBJECTIVE_MARKERS if m in text_lower)
    obj_hits = sum(1 for m in _OBJECTIVE_MARKERS if m in text_lower)

    if subj_hits + obj_hits == 0:
        return 0.5  # neutral

    return min(1.0, subj_hits / max(1, subj_hits + obj_hits))


def extract_entity_specificity(text: str) -> float:
    """How many specific entities (names, dates, numbers) are present."""
    hits = 0
    for pattern in _ENTITY_PATTERNS:
        hits += len(re.findall(pattern, text))
    return min(1.0, hits / 3.0)  # normalize: 3+ entities = max specificity


def extract_sentiment(text: str) -> float:
    """Simple sentiment. -1=negative, 0=neutral, 1=positive."""
    text_lower = text.lower()
    pos = sum(1 for w in _POSITIVE_WORDS if w in text_lower)
    neg = sum(1 for w in _NEGATIVE_WORDS if w in text_lower)

    if pos + neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def has_negation_pattern(text_a: str, text_b: str) -> bool:
    """Check if the pair exhibits explicit negation."""
    combined = text_a.lower() + " ||| " + text_b.lower()
    for pattern in _NEGATION_PATTERNS:
        if re.search(pattern, combined):
            return True
    return False


def has_temporal_markers(text_a: str, text_b: str) -> bool:
    """Check for temporal transition markers."""
    combined = (text_a + " " + text_b).lower()
    return any(m in combined for m in _TEMPORAL_MARKERS)


def has_context_markers(text_a: str, text_b: str) -> bool:
    """Check for context-dependent markers."""
    combined = (text_a + " " + text_b).lower()
    return any(m in combined for m in _CONTEXT_MARKERS)


def classify_domain(text: str) -> str:
    """Rough domain classification."""
    text_lower = text.lower()
    if any(m in text_lower for m in _EVENT_MARKERS):
        return "event"
    if any(m in text_lower for m in _IDENTITY_MARKERS):
        return "identity"
    if any(m in text_lower for m in _PREFERENCE_MARKERS):
        return "preference"
    # Check for factual patterns
    if extract_entity_specificity(text) > 0.5:
        return "fact"
    if extract_subjectivity(text) > 0.6:
        return "belief"
    return "general"


# ---------------------------------------------------------------------------
# Main classifier
# ---------------------------------------------------------------------------

def extract_signals(
    text_a: str,
    text_b: str,
    timestamp_a: float = 0.0,
    timestamp_b: float = 0.0,
    similarity: float = 0.0,
) -> DispositionSignals:
    """Extract all classification signals from a contradiction pair."""
    gap_seconds = abs(timestamp_b - timestamp_a)
    gap_days = gap_seconds / 86400.0

    return DispositionSignals(
        subjectivity_a=extract_subjectivity(text_a),
        subjectivity_b=extract_subjectivity(text_b),
        temporal_gap_days=gap_days,
        entity_specificity=max(
            extract_entity_specificity(text_a),
            extract_entity_specificity(text_b),
        ),
        semantic_similarity=similarity,
        sentiment_a=extract_sentiment(text_a),
        sentiment_b=extract_sentiment(text_b),
        has_negation=has_negation_pattern(text_a, text_b),
        has_temporal_marker=has_temporal_markers(text_a, text_b),
        has_context_marker=has_context_markers(text_a, text_b),
        domain=classify_domain(text_a),  # primary domain from older statement
    )


def classify_disposition(signals: DispositionSignals) -> DispositionResult:
    """Route a detected contradiction to a disposition.

    Rules are applied in priority order. First match wins.
    """
    trace = []
    avg_subjectivity = (signals.subjectivity_a + signals.subjectivity_b) / 2
    sentiment_mixed = (
        (signals.sentiment_a > 0.2 and signals.sentiment_b < -0.2) or
        (signals.sentiment_a < -0.2 and signals.sentiment_b > 0.2)
    )
    sentiment_same_sign = (
        (signals.sentiment_a > 0.1 and signals.sentiment_b > 0.1) or
        (signals.sentiment_a < -0.1 and signals.sentiment_b < -0.1)
    )

    # ---------------------------------------------------------------
    # Rule -1: RESOLVABLE — temporal marker + negation = explicit retraction
    # ---------------------------------------------------------------
    if signals.has_temporal_marker and signals.has_negation:
        trace.append("R-1: temporal marker + negation = explicit retraction")
        return DispositionResult(
            disposition=Disposition.RESOLVABLE,
            confidence=0.85,
            signals=signals,
            explanation="Explicit retraction with temporal marker — user is stating a change, not holding ambivalence.",
            rule_trace=trace,
        )

    # ---------------------------------------------------------------
    # Rule 0: CONTEXTUAL — context markers present
    # ---------------------------------------------------------------
    if signals.has_context_marker:
        trace.append("R0: context markers detected")
        # If both statements reference different contexts, likely contextual
        conf = 0.7 if avg_subjectivity > 0.4 else 0.5
        return DispositionResult(
            disposition=Disposition.CONTEXTUAL,
            confidence=conf,
            signals=signals,
            explanation="Statements reference different contexts — likely same belief expressed differently.",
            rule_trace=trace,
        )

    # ---------------------------------------------------------------
    # Rule 1: RESOLVABLE — high entity specificity + factual domain
    # ---------------------------------------------------------------
    if signals.entity_specificity > 0.3 and avg_subjectivity < 0.4:
        trace.append("R1: high entity specificity + low subjectivity")
        if signals.has_negation:
            trace.append("R1a: explicit negation — strong resolvable")
            conf = 0.9
        elif signals.temporal_gap_days < 7:
            trace.append("R1b: recent + specific — correction")
            conf = 0.85
        else:
            trace.append("R1c: factual + specific — supersession")
            conf = 0.75
        return DispositionResult(
            disposition=Disposition.RESOLVABLE,
            confidence=conf,
            signals=signals,
            explanation="Factual statements with specific entities — one likely supersedes the other.",
            rule_trace=trace,
        )

    # ---------------------------------------------------------------
    # Rule 2: RESOLVABLE — event domain (always resolvable)
    # ---------------------------------------------------------------
    if signals.domain == "event":
        trace.append("R2: event domain — always resolvable")
        return DispositionResult(
            disposition=Disposition.RESOLVABLE,
            confidence=0.85,
            signals=signals,
            explanation="Event-related contradiction — scheduling conflicts resolve, not hold.",
            rule_trace=trace,
        )

    # ---------------------------------------------------------------
    # Rule 3: HELD — subjective + mixed sentiment + identity/belief
    # ---------------------------------------------------------------
    if (avg_subjectivity > 0.5 and sentiment_mixed and
            signals.domain in ("identity", "belief", "preference")):
        trace.append("R3: subjective + mixed sentiment + identity/belief domain")
        conf = 0.75
        if signals.semantic_similarity > 0.6:
            trace.append("R3a: high similarity — same topic, different stance")
            conf = 0.85
        return DispositionResult(
            disposition=Disposition.HELD,
            confidence=conf,
            signals=signals,
            explanation="Subjective statements with opposing sentiment about the same topic — both may be true.",
            rule_trace=trace,
        )

    # ---------------------------------------------------------------
    # Rule 3b: HELD — negation of desire/belief (want vs don't want)
    # ---------------------------------------------------------------
    if (avg_subjectivity > 0.6 and signals.has_negation and
            signals.domain in ("belief", "preference", "identity")):
        trace.append("R3b: subjective + negation + belief/preference/identity")
        # Wanting and not-wanting the same thing = classic ambivalence
        return DispositionResult(
            disposition=Disposition.HELD,
            confidence=0.7,
            signals=signals,
            explanation="Subjective negation on same topic — ambivalence, not correction.",
            rule_trace=trace,
        )

    # ---------------------------------------------------------------
    # Rule 5: EVOLVING — temporal markers + moderate gap
    #   (moved BEFORE identity catch-all so "thinking about switching" gets caught)
    # ---------------------------------------------------------------
    if signals.has_temporal_marker:
        trace.append("R5: temporal transition markers detected")
        if signals.temporal_gap_days > 7:
            trace.append("R5a: gap > 7 days — belief shifting over time")
            return DispositionResult(
                disposition=Disposition.EVOLVING,
                confidence=0.75,
                signals=signals,
                explanation="Temporal markers + time gap — user may be changing their mind.",
                rule_trace=trace,
            )
        else:
            trace.append("R5b: gap < 7 days — likely correction, not evolution")
            return DispositionResult(
                disposition=Disposition.RESOLVABLE,
                confidence=0.7,
                signals=signals,
                explanation="Temporal markers but short gap — likely a correction.",
                rule_trace=trace,
            )

    # ---------------------------------------------------------------
    # Rule 5c: HELD — identity domain + subjective (catch-all, after temporal)
    # ---------------------------------------------------------------
    if signals.domain == "identity" and avg_subjectivity > 0.5:
        trace.append("R5c: identity domain + subjective")
        return DispositionResult(
            disposition=Disposition.HELD,
            confidence=0.65,
            signals=signals,
            explanation="Identity-related subjective statements often coexist — people are complex.",
            rule_trace=trace,
        )

    # ---------------------------------------------------------------
    # Rule 6: EVOLVING — long temporal gap + same topic
    # ---------------------------------------------------------------
    if signals.temporal_gap_days > 30 and signals.semantic_similarity > 0.5:
        trace.append("R6: long gap + same topic")
        return DispositionResult(
            disposition=Disposition.EVOLVING,
            confidence=0.7,
            signals=signals,
            explanation="Same topic, months apart — beliefs may be shifting.",
            rule_trace=trace,
        )

    # ---------------------------------------------------------------
    # Rule 7: HELD — high subjectivity + belief/preference domain
    # ---------------------------------------------------------------
    if avg_subjectivity > 0.6 and signals.domain in ("belief", "preference"):
        trace.append("R7: high subjectivity + belief/preference")
        return DispositionResult(
            disposition=Disposition.HELD,
            confidence=0.6,
            signals=signals,
            explanation="Subjective belief/preference contradiction — likely both are valid perspectives.",
            rule_trace=trace,
        )

    # ---------------------------------------------------------------
    # Rule 8: RESOLVABLE — low subjectivity fallback
    # ---------------------------------------------------------------
    if avg_subjectivity < 0.4:
        trace.append("R8: low subjectivity — default to resolvable")
        return DispositionResult(
            disposition=Disposition.RESOLVABLE,
            confidence=0.55,
            signals=signals,
            explanation="Objective-leaning statements — default to newer superseding older.",
            rule_trace=trace,
        )

    # ---------------------------------------------------------------
    # Fallback: UNKNOWN
    # ---------------------------------------------------------------
    trace.append("FALLBACK: insufficient signals")
    return DispositionResult(
        disposition=Disposition.UNKNOWN,
        confidence=0.3,
        signals=signals,
        explanation="Insufficient signals to classify — flag for human review.",
        rule_trace=trace,
    )


def classify_contradiction(
    text_a: str,
    text_b: str,
    timestamp_a: float = 0.0,
    timestamp_b: float = 0.0,
    similarity: float = 0.0,
) -> DispositionResult:
    """End-to-end: extract signals and classify."""
    signals = extract_signals(text_a, text_b, timestamp_a, timestamp_b, similarity)
    return classify_disposition(signals)


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("CONTRADICTION DISPOSITION CLASSIFIER — Phase 1 Test")
    print("=" * 70)

    test_cases = [
        # RESOLVABLE — factual corrections
        ("Meeting is on Monday at 3pm", "Meeting moved to Tuesday at 2pm",
         0, 86400, 0.8, "RESOLVABLE"),
        ("I work at Google", "I work at Microsoft",
         0, 86400 * 180, 0.85, "RESOLVABLE"),
        ("The project costs $50,000", "The project costs $75,000",
         0, 86400 * 3, 0.9, "RESOLVABLE"),

        # HELD — subjective, both true
        ("I love my job", "My job is killing me",
         0, 86400 * 14, 0.7, "HELD"),
        ("I'm an introvert", "I love performing on stage",
         0, 86400 * 30, 0.4, "HELD"),
        ("I enjoy being alone", "I hate being lonely",
         0, 86400 * 7, 0.6, "HELD"),
        ("I'm proud of what I've built", "I feel like I'm wasting my time",
         0, 86400 * 2, 0.5, "HELD"),

        # EVOLVING — changing mind
        ("I used to love React", "Now I prefer Vue",
         0, 86400 * 90, 0.7, "EVOLVING"),
        ("I want to stay in San Francisco", "I've been thinking about leaving",
         0, 86400 * 60, 0.65, "EVOLVING"),

        # CONTEXTUAL — same belief, different context
        ("I'm really disciplined at work", "At home I'm kind of lazy",
         0, 86400, 0.5, "CONTEXTUAL"),
        ("I'm confident when I'm with friends", "In public I get anxious",
         0, 86400 * 3, 0.5, "CONTEXTUAL"),

        # --- ADDITIONAL EDGE CASES ---

        # RESOLVABLE — employment change (factual, verifiable)
        ("I live in Portland", "I live in Seattle",
         0, 86400 * 60, 0.85, "RESOLVABLE"),
        ("My phone number is 555-1234", "My new number is 555-5678",
         0, 86400 * 10, 0.9, "RESOLVABLE"),

        # HELD — classic ambivalence
        ("I want to have kids someday", "I don't think I want kids",
         0, 86400 * 45, 0.7, "HELD"),
        ("I believe in being honest", "Sometimes you have to lie to protect people",
         0, 86400 * 20, 0.5, "HELD"),

        # EVOLVING — gradual shift
        ("I'm happy with my career in finance", "I've been thinking about switching to tech",
         0, 86400 * 120, 0.6, "EVOLVING"),

        # RESOLVABLE — negation pattern
        ("I'm a vegetarian", "I'm not a vegetarian anymore",
         0, 86400 * 30, 0.9, "RESOLVABLE"),

        # HELD — the Nick special
        ("I hate AI", "I've spent a year building an AI system",
         0, 86400 * 365, 0.3, "HELD"),
    ]

    correct = 0
    total = len(test_cases)

    for text_a, text_b, ts_a, ts_b, sim, expected in test_cases:
        result = classify_contradiction(text_a, text_b, ts_a, ts_b, sim)
        match = result.disposition.value == expected.lower()
        correct += int(match)

        status = "PASS" if match else "FAIL"
        print(f"\n  [{status}] Expected: {expected:12s} Got: {result.disposition.value:12s} "
              f"(conf={result.confidence:.2f})")
        print(f"    A: \"{text_a}\"")
        print(f"    B: \"{text_b}\"")
        print(f"    Trace: {' -> '.join(result.rule_trace)}")
        if not match:
            print(f"    Signals: subj={result.signals.subjectivity_a:.2f}/{result.signals.subjectivity_b:.2f} "
                  f"entity={result.signals.entity_specificity:.2f} "
                  f"sent={result.signals.sentiment_a:.2f}/{result.signals.sentiment_b:.2f} "
                  f"domain={result.signals.domain} gap={result.signals.temporal_gap_days:.0f}d")

    print(f"\n{'='*70}")
    print(f"  ACCURACY: {correct}/{total} ({100*correct/total:.0f}%)")
    print(f"{'='*70}")

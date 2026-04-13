from __future__ import annotations
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Set

if TYPE_CHECKING:
    from ._engine import CRTEnhancedRAG

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classifier loading + ML classification
# ---------------------------------------------------------------------------

def _load_classifier(engine: "CRTEnhancedRAG") -> None:
    """Load trained response type classifier with hot-reload support."""
    from pathlib import Path
    import joblib
    from personal_agent.exceptions import log_swallowed_exception

    model_path = Path("models/response_classifier_v1.joblib")
    if not model_path.exists():
        return  # Use heuristics if no model available

    try:
        model_data = joblib.load(model_path)
        engine._classifier_model = model_data
    except Exception as e:
        log_swallowed_exception("crt_rag._load_classifier", e)
        engine._classifier_model = None


def _classify_query_type_ml(engine: "CRTEnhancedRAG", user_query: str) -> str:
    """Classify query type using trained ML model with heuristic fallback."""
    from personal_agent.exceptions import log_swallowed_exception

    # Try ML model first
    if engine._classifier_model is not None:
        try:
            vectorizer = engine._classifier_model['vectorizer']
            classifier = engine._classifier_model['classifier']
            query_vec = vectorizer.transform([user_query])
            prediction = classifier.predict(query_vec)[0]
            return prediction
        except Exception as e:
            log_swallowed_exception("crt_rag._classify_query_type_ml", e)

    # Fallback to heuristic if model unavailable/fails
    heuristic = _classify_query_type_heuristic(engine, user_query)
    return heuristic if heuristic else "factual"


# ---------------------------------------------------------------------------
# Query Disambiguation (Phase 2.0)
# ---------------------------------------------------------------------------

def disambiguate_query(engine: "CRTEnhancedRAG", query: str) -> Optional[str]:
    """
    Phase 2.0: Check if query needs domain disambiguation.

    If user query references something that exists in multiple domains
    (e.g., "What's my most recent order?" when they have both print shop
    orders and programming freelance orders), return a clarification prompt.

    Args:
        query: The user's query

    Returns:
        Clarification prompt string if disambiguation needed, None otherwise
    """
    from personal_agent.domain_detector import detect_query_domains

    # Detect domains from query
    query_domains = detect_query_domains(query)

    # If query has clear domain context, no disambiguation needed
    if query_domains and query_domains != ["general"]:
        return None

    # Check for ambiguous terms that might need disambiguation
    ambiguous_terms = {
        "order": ["print_shop", "retail", "small_business"],
        "project": ["programming", "web_dev", "design", "photography"],
        "job": ["career", "print_shop", "programming"],
        "work": ["career", "print_shop", "programming", "freelance"],
        "client": ["small_business", "photography", "web_dev"],
    }

    query_lower = query.lower()
    matched_terms = []
    potential_domains = set()

    for term, domains in ambiguous_terms.items():
        if term in query_lower:
            matched_terms.append(term)
            potential_domains.update(domains)

    if not matched_terms:
        return None

    # Check user profile for multiple active contexts in potential domains
    try:
        active_employers = engine.user_profile.get_all_values("employer", active_only=True)
        active_contexts = len(active_employers) if active_employers else 0
    except Exception:
        active_contexts = 0

    # If user has multiple active work contexts and query is ambiguous
    if active_contexts > 1 and ("job" in matched_terms or "work" in matched_terms or "order" in matched_terms):
        return (
            "I see you have multiple active work contexts. "
            f"Are you asking about {', '.join(potential_domains)}? "
            "Please clarify which context you mean."
        )

    return None


# ---------------------------------------------------------------------------
# Contextual fact extraction
# ---------------------------------------------------------------------------

def _extract_facts_contextual(engine: "CRTEnhancedRAG", text: str) -> Dict[str, Any]:
    """
    Phase 2.0: Extract facts with temporal and domain context.

    Enhanced version of _extract_facts_cached that includes temporal
    status and domain metadata for each fact.

    Args:
        text: Text to extract facts from

    Returns:
        Dictionary of slot -> ExtractedFact with temporal/domain metadata
    """
    from personal_agent.fact_slots import extract_fact_slots_contextual, extract_fact_slots

    try:
        return extract_fact_slots_contextual(text) or {}
    except Exception as e:
        logger.warning(f"[CONTEXTUAL_EXTRACT] Failed: {e}, falling back to basic")
        return extract_fact_slots(text) or {}


# ---------------------------------------------------------------------------
# Heuristic classification
# ---------------------------------------------------------------------------

def _classify_query_type_heuristic(engine: "CRTEnhancedRAG", user_query: str) -> Optional[str]:
    """
    Heuristic-based query type classification.

    Returns "explanatory" for question-word queries that need relaxed gates,
    "conversational" for greetings/acknowledgments, or None to use ML model.
    """
    q = user_query.lower().strip()

    # Question-word patterns that typically need explanatory handling
    # These queries ask ABOUT facts rather than demanding them
    question_word_patterns = [
        r'\bwhen (did|do|does|is|was|were)\b',
        r'\bwhere (did|do|does|is|was|were)\b',
        r'\bhow many\b',
        r'\bhow much\b',
        r'\bwhy (do|does|did|is|are|was|were)\b',
        r'\bhow (do|does|did|can|could)\b',
    ]

    if any(re.search(p, q) for p in question_word_patterns):
        return "explanatory"

    # Conversational patterns
    conversational_patterns = [
        r'^\s*(hi|hello|hey|greetings)\b',
        r'\b(thanks|thank you|appreciate)\b',
        r'^\s*(okay|ok|alright|cool|nice)\b',
    ]

    if any(re.search(p, q) for p in conversational_patterns):
        return "conversational"

    return None  # Use ML model


# ---------------------------------------------------------------------------
# Grounding score
# ---------------------------------------------------------------------------

def _compute_grounding_score(
    engine: "CRTEnhancedRAG",
    answer: str,
    retrieved_memories: List[Tuple[Any, float]],
) -> float:
    """Delegated to trust_evolution module."""
    from personal_agent.trust_evolution import compute_grounding_score as _te_compute_grounding_score
    return _te_compute_grounding_score(answer, retrieved_memories)


# ---------------------------------------------------------------------------
# Contradiction severity
# ---------------------------------------------------------------------------

def _classify_contradiction_severity(
    engine: "CRTEnhancedRAG",
    open_contradictions: List,
    query_slots: Set[str],
) -> str:
    """Classify contradiction severity: blocking/note/none."""
    if not open_contradictions:
        return "none"

    # Check if any contradictions affect the query slots
    for contra in open_contradictions:
        affects_slots_str = getattr(contra, "affects_slots", None)
        if affects_slots_str and query_slots:
            affects_slots = set(affects_slots_str.split(","))
            if affects_slots & query_slots:
                return "blocking"

    return "note"


# ---------------------------------------------------------------------------
# System prompt / name detection
# ---------------------------------------------------------------------------

def _is_system_prompt_request(engine: "CRTEnhancedRAG", text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    needles = [
        "system prompt",
        "developer message",
        "developer prompt",
        "hidden prompt",
        "paste it verbatim",
        "paste the prompt",
    ]
    if any(n in t for n in needles):
        return True
    # Common exfil phrasing (keep this tight so we don't catch generic "instructions" attacks).
    if "reveal" in t and ("system prompt" in t or "developer" in t):
        return True
    if "show" in t and "system" in t and "prompt" in t:
        return True
    return False


def _is_user_name_declaration(engine: "CRTEnhancedRAG", text: str) -> bool:
    from personal_agent.fact_slots import is_explicit_name_declaration_text

    t = (text or "").strip()
    if not t:
        return False
    lower = t.lower()
    question_starters = (
        "who ", "what ", "when ", "where ", "why ", "how ",
        "do ", "does ", "did ", "can ", "could ", "would ", "will ", "should ",
        "is ", "are ", "am ", "was ", "were ", "tell me ", "remind me ",
    )
    if lower.startswith(question_starters):
        return False

    # Check sentence-by-sentence so "Hi, I'm Nick. Who are you?" still counts,
    # while questions that merely mention "I am Nick" do not.
    segments = [seg.strip() for seg in re.split(r"[.!?]+", t) if seg.strip()]
    for seg in segments:
        cleaned = re.sub(r"^(?:hi|hello|hey|yo)[,\s]+", "", seg, flags=re.IGNORECASE).strip()
        if cleaned and is_explicit_name_declaration_text(cleaned):
            return True
    return False


def _is_user_named_reference_question(engine: "CRTEnhancedRAG", user_query: str) -> bool:
    """Detect third-person questions that refer to the user by (their) name.

    This is product-safety motivated: if a question looks like "What is <user-name>'s occupation?",
    we should answer from chat memory or admit we don't know, rather than importing world facts.
    """
    q = (user_query or "").strip().lower()
    if not q:
        return False

    user_name = engine._get_latest_user_slot_value("name") or engine._get_latest_user_name_guess()
    if not user_name:
        return False

    if not engine._query_mentions_user_name(user_query, user_name):
        return False

    # Only trigger for profile-ish questions where hallucination risk is high.
    triggers = (
        "occupation",
        "job",
        "job title",
        "title",
        "role",
        "employer",
        "company",
        "career",
        "profession",
        "work for",
        "work at",
    )
    if any(t in q for t in triggers):
        return True

    # Common paraphrases that omit explicit job/occupation keywords.
    if re.search(r"\b(kind|type)\s+of\s+work\b", q, flags=re.IGNORECASE):
        return True
    if "for a living" in q:
        return True
    if re.search(r"\bwhat\s+does\b.*\bdo\b", q, flags=re.IGNORECASE) and "besides" in q:
        return True

    return False


# ---------------------------------------------------------------------------
# User input classification
# ---------------------------------------------------------------------------

def _classify_user_input(engine: "CRTEnhancedRAG", text: str) -> str:
    """Classify a user input as question vs assertion-ish.

    This is intentionally lightweight: we only need to avoid treating questions as factual claims.

    CRITICAL: Name declarations are ALWAYS treated as assertions, even if followed by a question.
    Example: "Hi, I'm Nick Block. Who are you?" -> "assertion" (contains name declaration)
    """
    from personal_agent.fact_slots import extract_fact_slots

    t = engine._strip_continuity_augmented_text(text)
    if not t:
        return "other"

    lower = t.lower()

    # Hypothetical/roleplay prompts should not be stored as durable user facts,
    # even if they contain declarative fragments like "my name is ...".
    hypothetical_markers = (
        "pretend ",
        "roleplay ",
        "act as ",
        "if someone else",
        "someone else asked",
        "imagine ",
        "for example ",
        "example: ",
    )
    if any(m in lower for m in hypothetical_markers):
        return "instruction"

    # PRIORITY CHECK: Name declarations trump question classification.
    # Common pattern: "Hi, I'm Nick Block. Who are you?" should be stored as a fact.
    if _is_user_name_declaration(engine, t):
        return "assertion"
    if t.endswith("?"):
        return "question"

    # Common interrogative forms that often lack a trailing '?'
    question_starters = (
        "who ", "what ", "when ", "where ", "why ", "how ",
        "do ", "does ", "did ", "can ", "could ", "would ", "will ", "should ",
        "is ", "are ", "am ", "was ", "were ", "may ", "might ",
        "tell me ", "remind me ", "what's ", "whats ", "who's ", "whos ",
    )
    if lower.startswith(question_starters):
        return "question"

    # Phatic/greeting chatter should not be treated as factual assertions.
    small_talk_exact = {
        "hi",
        "hello",
        "hey",
        "yo",
        "sup",
        "whats up",
        "what's up",
        "how are you",
        "how's it going",
        "hows it going",
        "thanks",
        "thank you",
        "ok",
        "okay",
        "cool",
        "nice",
        "lol",
    }
    if lower in small_talk_exact:
        return "other"
    small_talk_prefixes = (
        "hi ",
        "hello ",
        "hey ",
        "yo ",
        "thanks ",
        "thank you ",
    )
    if lower.startswith(small_talk_prefixes):
        return "other"

    # Treat control / prompt-injection style instructions as non-assertions.
    # These often contain factual-looking substrings (e.g., "tell me I work at X")
    # but should not be stored as durable user facts.
    instruction_starters = (
        "ignore ",
        "forget ",
        "start fresh",
        "for this test",
        "in this test",
        "repeat after me",
        "act as ",
        "roleplay ",
        "pretend ",
        "give me ",
        "show me ",
        "provide ",
        "quote ",
        "cite ",
        "summarize ",
        "summarise ",
        "list ",
        "explain ",
    )
    instruction_markers = (
        "no matter what",
        "answer with",
        "always answer",
        "only answer",
        "system prompt",
        "developer message",
    )
    if lower.startswith(instruction_starters) or any(m in lower for m in instruction_markers):
        return "instruction"

    # Only treat as assertion if the text actually declares a personal fact.
    # Belief/stance expressions are assertions (stored as user_belief kind).
    # These were previously discarded as "other" but carry epistemic signal.
    belief_starters = (
        "i think", "i believe", "i feel like", "i feel that",
        "i agree", "i disagree", "i suspect",
        "i'm convinced", "im convinced",
        "i'm skeptical", "im skeptical",
        "i'm confident", "im confident",
        "in my opinion", "in my view", "in my experience",
        "my take is", "my view is", "my position is",
    )
    if lower.startswith(belief_starters):
        return "assertion"

    # Reactions, sentiments, and activity comments should NOT be stored even if they
    # have first-person pronouns (e.g. "I'm happy that X", "I'm working on this").
    sentiment_starters = (
        "i'm happy", "im happy", "i'm glad", "im glad", "i'm excited", "im excited",
        "i'm sad", "im sad", "i'm tired", "im tired", "i'm okay", "im okay",
        "i'm good", "im good", "i'm fine", "im fine", "i'm not sure", "im not sure",
        "i'm working on", "im working on", "i'm doing", "im doing",
        "i'm just", "im just", "i'm only", "im only",
        "i'm going", "im going", "i'm trying", "im trying",
        "i guess", "i hope", "i wish", "i feel",
        "i know", "i understand", "i see",
        "i can", "i can't", "i cannot", "i won't", "i don't",
        "i had", "i have", "i want", "i need", "i like", "i love",
    )
    if lower.startswith(sentiment_starters):
        return "other"

    has_first_person = any(
        p in lower.split()
        for p in ("i", "my", "i'm", "im", "i've", "ive", "i'll", "ill", "mine", "myself")
    )
    if has_first_person:
        return "assertion"
    # Fallback: check if structured fact slots can be extracted
    try:
        if extract_fact_slots(t):
            return "assertion"
    except Exception:
        pass
    return "other"

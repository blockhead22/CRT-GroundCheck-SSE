"""Layer 4: Epistemic Routing — belief-based orchestrator routing.

Replaces the keyword hack in chat.py with structural message features
weighted by beliefs that start from seeded priors and evolve through
run log feedback.

The grammar of intent, not a lookup table.

Usage:
    from personal_agent.routing_beliefs import should_orchestrate, update_from_run

    decision = should_orchestrate("read the file crt_rag.py", task_intent)
    # decision.route = "orchestrator", decision.confidence = 0.82

    # After orchestrator run completes:
    update_from_run("read the file crt_rag.py", run_log)
"""

import math
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .runtime_paths import resolve_agent_runs_db_path

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RoutingDecision:
    """Result of epistemic routing."""
    route: str              # "orchestrator" or "conversational"
    confidence: float       # 0-1, how sure the belief system is
    reasons: List[str]      # which features fired and why
    features: Dict[str, float] = field(default_factory=dict)  # raw feature values


# ---------------------------------------------------------------------------
# Feature extractors — structural grammar, not keywords
# ---------------------------------------------------------------------------

# Verb classes (base forms — we do crude suffix stripping)
_STATE_CHANGE_VERBS = frozenset({
    "create", "write", "modify", "fix", "delete", "update", "add", "remove",
    "set", "build", "install", "move", "rename", "replace", "edit", "patch",
    "deploy", "push", "commit", "save", "store", "insert", "drop", "kill",
    "restart", "stop", "start", "run", "execute", "send", "upload",
    "search", "find", "grep", "list", "check", "look", "read", "open",
    "scan", "trace", "debug", "test", "verify", "inspect", "audit",
    "map", "analyze", "fetch", "browse", "navigate", "crawl", "parse",
    "detect", "diagnose", "profile", "benchmark", "measure",
    "remember", "forget", "note", "record", "log", "track",
    "assess", "evaluate", "review", "examine", "describe", "identify",
})

_INFORMATION_VERBS = frozenset({
    "explain", "describe", "define", "clarify", "tell", "teach", "show",
    "summarize", "compare", "contrast", "elaborate", "outline",
})

_TRANSFORMATION_VERBS = frozenset({
    "refactor", "optimize", "convert", "migrate", "merge", "split",
    "extract", "rewrite", "restructure", "simplify", "generalize",
    "normalize", "deduplicate", "compress", "decompose",
})

_SYSTEM_NOUNS = frozenset({
    "file", "files", "function", "functions", "class", "classes",
    "module", "modules", "server", "database", "db", "endpoint",
    "endpoints", "api", "route", "routes", "component", "components",
    "table", "tables", "column", "index", "schema", "model", "models",
    "test", "tests", "script", "config", "configuration", "variable",
    "method", "methods", "directory", "folder", "package", "dependency",
    "service", "container", "pipeline", "workflow", "log", "logs",
    "memory", "memories", "belief", "beliefs", "vector", "embedding",
})

_ABSTRACT_NOUNS = frozenset({
    "concept", "idea", "theory", "approach", "strategy", "pattern",
    "philosophy", "principle", "meaning", "purpose", "reason", "logic",
    "intuition", "opinion", "thought", "feeling", "sense", "vibe",
    "overview", "context", "background", "history", "difference",
})

# Wh-words for question detection
_WH_WORDS = frozenset({"what", "why", "how", "when", "where", "which", "who"})

# Prior context references
_CONTEXT_REFS = frozenset({
    "that file", "the file", "that function", "the function",
    "that bug", "the bug", "the error", "that class", "the code",
    "this file", "this function", "this code", "it", "those",
    "the same", "that one", "the output", "the result",
})

# Compound intent markers
_COMPOUND_MARKERS = re.compile(
    r'\b(and then|then|after that|also|and also|next|finally|first .* then)\b',
    re.IGNORECASE,
)


def _lemmatize(word: str) -> str:
    """Crude suffix stripping to get verb base form."""
    w = word.lower().rstrip(".,!?;:")
    # -ing: "creating" → "creat" ... but we also check the -e form
    if w.endswith("ting") and len(w) > 5:
        base = w[:-4]
        if base + "te" in _STATE_CHANGE_VERBS | _TRANSFORMATION_VERBS:
            return base + "te"
        return base + "t"
    if w.endswith("ing") and len(w) > 4:
        base = w[:-3]
        if base in _STATE_CHANGE_VERBS | _INFORMATION_VERBS | _TRANSFORMATION_VERBS:
            return base
        if base + "e" in _STATE_CHANGE_VERBS | _INFORMATION_VERBS | _TRANSFORMATION_VERBS:
            return base + "e"
        return base
    # -ed: "created" → "create"
    if w.endswith("ed") and len(w) > 4:
        base = w[:-2]
        if base in _STATE_CHANGE_VERBS | _TRANSFORMATION_VERBS:
            return base
        if base + "e" in _STATE_CHANGE_VERBS | _TRANSFORMATION_VERBS:
            return base + "e"
        # "modified" → "modifi" → try "modify" (y-class)
        if w.endswith("ied"):
            ybase = w[:-3] + "y"
            if ybase in _STATE_CHANGE_VERBS | _TRANSFORMATION_VERBS:
                return ybase
    # -es, -s: "fixes" → "fix", "creates" → "create"
    if w.endswith("es") and len(w) > 3:
        base = w[:-2]
        if base in _STATE_CHANGE_VERBS | _INFORMATION_VERBS | _TRANSFORMATION_VERBS:
            return base
    if w.endswith("s") and len(w) > 3:
        base = w[:-1]
        if base in _STATE_CHANGE_VERBS | _INFORMATION_VERBS | _TRANSFORMATION_VERBS:
            return base
    return w


def _tokenize(message: str) -> List[str]:
    """Split message into tokens."""
    return re.findall(r"[a-zA-Z0-9_./-]+", message.lower())


# --- Individual feature extractors ---

def _feat_state_change_verb(tokens: List[str], lemmas: List[str]) -> float:
    """Does the message contain a verb implying state change?"""
    hits = sum(1 for l in lemmas if l in _STATE_CHANGE_VERBS)
    return min(1.0, hits * 0.5)  # 2+ hits → 1.0


def _feat_information_verb(tokens: List[str], lemmas: List[str]) -> float:
    """Does the message ask for information/explanation?"""
    hits = sum(1 for l in lemmas if l in _INFORMATION_VERBS)
    return min(1.0, hits * 0.5)


def _feat_transformation_verb(tokens: List[str], lemmas: List[str]) -> float:
    """Does the message request code transformation?"""
    hits = sum(1 for l in lemmas if l in _TRANSFORMATION_VERBS)
    return min(1.0, hits * 0.5)


def _feat_system_resource(tokens: List[str], msg: str) -> float:
    """Does the message reference a concrete system resource?"""
    score = 0.0
    # Check system nouns
    noun_hits = sum(1 for t in tokens if t in _SYSTEM_NOUNS)
    score += min(0.5, noun_hits * 0.25)
    # Check file paths (slash or backslash or dot-extension)
    if re.search(r'[a-zA-Z0-9_]+[/\\][a-zA-Z0-9_.]+', msg):
        score += 0.3
    # Check code identifiers (snake_case or CamelCase)
    if re.search(r'\b[a-z]+_[a-z]+\b', msg) or re.search(r'\b[A-Z][a-z]+[A-Z]', msg):
        score += 0.2
    return min(1.0, score)


def _feat_abstract_target(tokens: List[str]) -> float:
    """Does the message reference abstract concepts?"""
    hits = sum(1 for t in tokens if t in _ABSTRACT_NOUNS)
    return min(1.0, hits * 0.5)


def _feat_imperative_form(tokens: List[str], lemmas: List[str]) -> float:
    """Does the message have imperative structure (starts with verb)?"""
    if not lemmas:
        return 0.0
    first = lemmas[0]
    all_verbs = _STATE_CHANGE_VERBS | _TRANSFORMATION_VERBS | _INFORMATION_VERBS
    if first in all_verbs:
        return 1.0
    # "please X" pattern
    if len(lemmas) > 1 and tokens[0] == "please" and lemmas[1] in all_verbs:
        return 0.8
    # "can you X" pattern
    if len(lemmas) > 2 and tokens[0] in ("can", "could", "would") and tokens[1] == "you":
        return 0.6
    return 0.0


def _feat_question_form(tokens: List[str], msg: str) -> float:
    """Does the message have question structure?"""
    score = 0.0
    if tokens and tokens[0] in _WH_WORDS:
        score += 0.6
    if msg.rstrip().endswith("?"):
        score += 0.4
    # "is there", "does it", "are there"
    if tokens and tokens[0] in ("is", "does", "are", "do", "has", "have", "was", "were"):
        score += 0.3
    return min(1.0, score)


def _feat_compound_intent(msg: str) -> float:
    """Does the message contain multiple action phrases?"""
    matches = _COMPOUND_MARKERS.findall(msg)
    if len(matches) >= 2:
        return 1.0
    if len(matches) == 1:
        return 0.6
    return 0.0


def _feat_message_complexity(msg: str) -> float:
    """Message length/complexity as sigmoid, not hard cutoff."""
    length = len(msg)
    # Sigmoid centered at 200 chars, steepness 0.015
    return 1.0 / (1.0 + math.exp(-0.015 * (length - 200)))


def _feat_code_artifact(msg: str) -> float:
    """Does the message contain code-like artifacts?"""
    score = 0.0
    if '`' in msg:
        score += 0.4
    if '```' in msg:
        score += 0.3
    # File extensions
    if re.search(r'\.\w{1,4}\b', msg) and re.search(r'\.(py|js|ts|md|json|yaml|yml|sql|sh|css|html|txt|csv|toml|cfg|ini|log)\b', msg, re.IGNORECASE):
        score += 0.3
    # Path-like
    if re.search(r'[/\\]\w+[/\\]', msg):
        score += 0.3
    return min(1.0, score)


def _feat_prior_context(msg: str) -> float:
    """Does the message reference prior conversation context?"""
    msg_lower = msg.lower()
    hits = sum(1 for ref in _CONTEXT_REFS if ref in msg_lower)
    return min(1.0, hits * 0.4)


def _feat_has_attachment(msg: str) -> float:
    """Does the message contain an attached resource (image, file reference)?"""
    if "[image:" in msg:
        return 1.0
    if "[file:" in msg and any(ext in msg.lower() for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".pdf")):
        return 0.8
    return 0.0


# Patterns that signal identity/philosophical/self-reflective questions
_IDENTITY_PATTERNS = [
    # Direct identity questions
    r"\bdo you (have|feel|experience|believe|want|need|fear|value|care|think)\b",
    r"\bare you (alive|conscious|sentient|real|aware|intelligent|creative|honest)\b",
    r"\bwhat (are|is) your (values?|beliefs?|goals?|purpose|identity|personality|nature|essence)\b",
    r"\bwho are you\b",
    r"\bwhat are you\b",
    # Philosophical about self
    r"\byour (consciousness|awareness|experience|feelings?|emotions?|soul|mind|self)\b",
    r"\bdo you (understand|know) yourself\b",
    r"\bwhat do you think about yourself\b",
    r"\bwhat makes you (different|unique|you)\b",
    # Existential / philosophical framing
    r"\bdo (ai|you|machines|models) (have|possess|develop|experience) (values?|morals?|ethics|consciousness|feelings?|beliefs?|opinions?|preferences?)\b",
    r"\b(meaning|purpose|reason) (of|for|behind) (your|ai|artificial)\b",
    r"\byour (philosophy|worldview|perspective|stance|position) on\b",
    # Addressed to Aether identity
    r"\baether.{0,20}(think|feel|believe|value|want|care|experience)\b",
    r"\b(think|feel|believe|value|want|care|experience).{0,20}aether\b",
]
_IDENTITY_RE = [re.compile(p, re.IGNORECASE) for p in _IDENTITY_PATTERNS]


def _feat_identity_philosophical(msg: str) -> float:
    """Does the message ask about identity, values, consciousness, or philosophy of self?"""
    hits = sum(1 for pat in _IDENTITY_RE if pat.search(msg))
    if hits >= 2:
        return 1.0
    if hits == 1:
        return 0.8
    # Softer signal: abstract + question + second-person
    msg_lower = msg.lower()
    has_you = " you " in msg_lower or msg_lower.startswith("you ") or "your " in msg_lower
    has_abstract = any(w in msg_lower for w in ("values", "beliefs", "purpose", "meaning", "conscious", "alive", "real", "feel", "soul", "ethics", "morals"))
    has_question = "?" in msg
    if has_you and has_abstract and has_question:
        return 0.6
    return 0.0


# ---------------------------------------------------------------------------
# Feature registry — maps names to (extractor, prior_weight)
# ---------------------------------------------------------------------------

def _extract_all_features(message: str) -> Dict[str, float]:
    """Run all feature extractors, return name → value."""
    tokens = _tokenize(message)
    lemmas = [_lemmatize(t) for t in tokens]

    identity_score = _feat_identity_philosophical(message)

    return {
        "state_change_verb":   _feat_state_change_verb(tokens, lemmas),
        "information_verb":    _feat_information_verb(tokens, lemmas),
        "transformation_verb": _feat_transformation_verb(tokens, lemmas),
        "system_resource":     _feat_system_resource(tokens, message),
        # Suppress abstract_target when identity fires — they're correlated
        # and the abstract penalty shouldn't cancel the identity signal.
        "abstract_target":     _feat_abstract_target(tokens) if identity_score < 0.5 else 0.0,
        "imperative_form":     _feat_imperative_form(tokens, lemmas),
        "question_form":       _feat_question_form(tokens, message),
        "compound_intent":     _feat_compound_intent(message),
        "message_complexity":  _feat_message_complexity(message),
        "code_artifact":       _feat_code_artifact(message),
        "prior_context":       _feat_prior_context(message),
        "has_attachment":      _feat_has_attachment(message),
        "identity_philosophical": identity_score,
    }


# Seeded priors: (feature_name, initial_weight)
# Positive = leans orchestrator, negative = leans conversational
_SEEDED_PRIORS: Dict[str, float] = {
    "state_change_verb":    0.7,
    "information_verb":    -0.5,
    "transformation_verb":  0.6,
    "system_resource":      0.6,
    "abstract_target":     -0.4,
    "imperative_form":      0.3,
    "question_form":       -0.3,
    "compound_intent":      0.8,
    "message_complexity":   0.3,
    "code_artifact":        0.5,
    "prior_context":        0.2,
    "has_attachment":       1.0,
    "identity_philosophical": 1.0,
}

# Intent classifier boost removed — Layer 4 feature extractors are fully independent.
# The llama3.2 intent router is no longer used for routing decisions.


# ---------------------------------------------------------------------------
# SQLite persistence
# ---------------------------------------------------------------------------

_DB_PATH = str(resolve_agent_runs_db_path())
_LEARNING_RATE = 0.05
_WEIGHT_CLAMP = 2.0


class RoutingBeliefDB:
    """Persistent belief weights for routing features."""

    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_table()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, timeout=5, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_table(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS routing_beliefs (
                feature      TEXT PRIMARY KEY,
                weight       REAL NOT NULL,
                observations INTEGER NOT NULL DEFAULT 0,
                successes    INTEGER NOT NULL DEFAULT 0,
                last_updated REAL NOT NULL
            )
        """)
        # Seed priors
        now = time.time()
        for feat, weight in _SEEDED_PRIORS.items():
            conn.execute(
                "INSERT OR IGNORE INTO routing_beliefs (feature, weight, observations, successes, last_updated) "
                "VALUES (?, ?, 0, 0, ?)",
                (feat, weight, now),
            )
        conn.commit()

    def get_weights(self) -> Dict[str, float]:
        """Load current belief weights."""
        conn = self._get_conn()
        rows = conn.execute("SELECT feature, weight FROM routing_beliefs").fetchall()
        weights = {r["feature"]: r["weight"] for r in rows}
        # Fill any missing with priors (in case new features added)
        for feat, prior in _SEEDED_PRIORS.items():
            if feat not in weights:
                weights[feat] = prior
        return weights

    def update_beliefs(self, features: Dict[str, float], success: bool):
        """Update belief weights based on run outcome.

        For each feature that fired (value > 0.3), nudge its weight
        toward or away from the prior based on whether routing to
        orchestrator was the right call.
        """
        conn = self._get_conn()
        now = time.time()
        outcome = 1.0 if success else -0.5

        for feat, value in features.items():
            if value <= 0.3:
                continue

            row = conn.execute(
                "SELECT weight, observations, successes FROM routing_beliefs WHERE feature = ?",
                (feat,),
            ).fetchone()

            if row is None:
                continue

            weight = row["weight"]
            obs = row["observations"] + 1
            succ = row["successes"] + (1 if success else 0)

            # Current success rate for this feature
            rate = succ / obs if obs > 0 else 0.5
            # Nudge: learning_rate * (outcome_signal - current_rate) * feature_strength
            delta = _LEARNING_RATE * (outcome - rate) * value
            new_weight = max(-_WEIGHT_CLAMP, min(_WEIGHT_CLAMP, weight + delta))

            conn.execute(
                "UPDATE routing_beliefs SET weight = ?, observations = ?, successes = ?, last_updated = ? "
                "WHERE feature = ?",
                (new_weight, obs, succ, now, feat),
            )

        conn.commit()

    def get_stats(self) -> List[Dict[str, Any]]:
        """Return all belief records for inspection."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT feature, weight, observations, successes, last_updated FROM routing_beliefs "
            "ORDER BY abs(weight) DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RoutingBeliefDB] = None


def _get_db() -> RoutingBeliefDB:
    global _instance
    if _instance is None:
        _instance = RoutingBeliefDB()
    return _instance


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def should_orchestrate(message: str, intent: Any = None) -> RoutingDecision:
    """Decide whether a message should route to the agent loop orchestrator.

    Args:
        message: The user's message text.
        intent: Optional TaskIntent from the intent classifier.

    Returns:
        RoutingDecision with route, confidence, and reasons.
    """
    # Hard overrides: certain intent types ALWAYS need the orchestrator
    # because they require tool execution that only the orchestrator can do.
    _FORCE_ORCHESTRATOR_INTENTS = {
        "gpt_log_search", "gpt_log_context", "gpt_log_promote",
    }
    # Reasons that indicate the query needs belief-grounded generation
    # (user identity questions, personal facts, broad recall).
    # These route to orchestrator so the belief state injection provides context.
    _FORCE_ORCHESTRATOR_REASONS = {
        "personal_fact_full_pipeline",
    }
    _FORCE_ORCHESTRATOR_INTENT_TYPES = {
        "broad_recall",
    }
    if intent is not None:
        _intent_type = getattr(intent, "intent_type", None)
        _intent_reason = getattr(intent, "reason", None) or ""
        if _intent_type in _FORCE_ORCHESTRATOR_INTENTS:
            return RoutingDecision(
                route="orchestrator",
                confidence=0.95,
                reasons=[f"forced_by_intent({_intent_type})"],
                features={},
            )
        if _intent_type in _FORCE_ORCHESTRATOR_INTENT_TYPES:
            return RoutingDecision(
                route="orchestrator",
                confidence=0.90,
                reasons=[f"forced_by_intent_type({_intent_type})"],
                features={},
            )
        if _intent_reason in _FORCE_ORCHESTRATOR_REASONS:
            return RoutingDecision(
                route="orchestrator",
                confidence=0.85,
                reasons=[f"forced_by_reason({_intent_reason})"],
                features={},
            )

    # Pattern-based override: personal identity / belief-state questions
    # These need the orchestrator because belief state is injected there.
    import re as _re_routing
    _personal_q = _re_routing.search(
        r"\b(?:what(?:'s| is) my (?:name|job|age|location|color|health)|"
        r"where do i (?:work|live)|"
        r"do you (?:know|remember) (?:me|my|who i|about me)|"
        r"what (?:do you (?:know|remember|believe|hold)|contradictions?|facts? do you (?:have|know))|"
        r"(?:tell|show) me (?:about|what you know about) (?:me|myself|who i)|"
        r"(?:describe|summarize) (?:me|what you know)|"
        r"who am i)\b",
        message, _re_routing.IGNORECASE,
    )
    if _personal_q:
        return RoutingDecision(
            route="orchestrator",
            confidence=0.85,
            reasons=["personal_identity_query"],
            features={},
        )

    # Reflective / recall conversational queries that need tool access.
    # These are conversational in tone but require memory_recall or
    # gpt_log_search to answer well. Without orchestrator routing,
    # they go through legacy path with weak retrieval and no tools.
    _reflective_q = _re_routing.search(
        r"\b(?:what (?:did we|have we) (?:discuss|talk|work|do|build|ship)|"
        r"(?:remind|tell) me (?:what|about) (?:we|our|last)|"
        r"what (?:do you think|are you (?:unsure|certain|sure)|drives? me|holds? me)|"
        r"what (?:are|were) my (?:dreams?|goals?|promises?|plans?|three)|"
        r"(?:describe|explain) (?:me|my|how i|what i)|"
        r"what (?:is|was) (?:the biggest|our biggest|your biggest)|"
        r"dig deeper|carry the torch|keep brainstorming|"
        r"what (?:do you want|would you|should we|can you do)|"
        r"anything new with you)\b",
        message, _re_routing.IGNORECASE,
    )
    if _reflective_q:
        return RoutingDecision(
            route="orchestrator",
            confidence=0.80,
            reasons=["reflective_recall_query"],
            features={},
        )

    features = _extract_all_features(message)
    weights = _get_db().get_weights()

    # Weighted sum — negative bias so neutral/empty messages default conversational
    # sigmoid(-0.5) ≈ 0.38, so you need real signal to cross 0.5
    raw_score = -0.5
    reasons = []

    for feat, value in features.items():
        w = weights.get(feat, 0.0)
        contribution = w * value
        raw_score += contribution
        if abs(contribution) > 0.1:
            direction = "+" if contribution > 0 else "-"
            reasons.append(f"{feat}({direction}{abs(contribution):.2f})")

    # Sigmoid → probability
    probability = 1.0 / (1.0 + math.exp(-raw_score))

    route = "orchestrator" if probability >= 0.5 else "conversational"
    # Confidence: how far from the decision boundary (0.5)
    confidence = abs(probability - 0.5) * 2  # 0 at boundary, 1 at extremes

    return RoutingDecision(
        route=route,
        confidence=round(confidence, 3),
        reasons=reasons,
        features=features,
    )


def update_from_run(message: str, run_log: Any) -> None:
    """Update routing beliefs after an orchestrator run completes.

    Called from the orchestrator after run log persistence.
    """
    features = _extract_all_features(message)

    # Determine success from run log
    success = False
    try:
        success = bool(run_log.success) if run_log.success is not None else run_log.completed
    except AttributeError:
        pass

    _get_db().update_beliefs(features, success)

    # Log
    db = _get_db()
    stats = db.get_stats()
    moved = [s for s in stats if s["observations"] > 0]
    if moved:
        print(f"[ROUTING_BELIEFS] Updated {len(moved)} beliefs from run (success={success})")

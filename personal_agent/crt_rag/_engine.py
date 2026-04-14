"""
CRT-Enhanced RAG Engine

Integrates CRT principles into RAG:
- Trust-weighted retrieval (not just similarity)
- Belief vs speech separation
- Reconstruction gates (Holden constraints)
- Contradiction detection and ledger tracking
- Trust evolution on retrieval
- Memory-first philosophy

Philosophy:
- Coherence over time > single-query accuracy
- Memory informs retrieval, retrieval updates memory
- Fallback can speak, but doesn't create high-trust beliefs
- Gates prevent "sounding good while drifting"
"""

import numpy as np
import re
import logging
import sqlite3
import random
import uuid
from typing import List, Dict, Optional, Any, Tuple, Set
from pathlib import Path
from collections import OrderedDict
import time
import joblib

from personal_agent.exceptions import log_swallowed_exception
from ..runtime_paths import resolve_runtime_path, resolve_profile_db_path

logger = logging.getLogger(__name__)

from ..crt_core import CRTMath, CRTConfig, MemorySource, SSEMode, encode_vector
from ..crt_memory import CRTMemorySystem, MemoryItem
from ..crt_ledger import ContradictionLedger, ContradictionEntry, ContradictionStatus, ContradictionType
from ..reasoning import ReasoningEngine, ReasoningMode
from ..fact_slots import (
    extract_fact_slots, 
    extract_fact_slots_contextual, 
    TemporalStatus,
    detect_correction_type,
    extract_direct_correction,
    extract_hedged_correction,
    is_explicit_name_declaration_text,
    names_look_equivalent,
)
from ..two_tier_facts import TwoTierFactSystem, TwoTierExtractionResult
from ..learned_suggestions import LearnedSuggestionEngine
from ..runtime_config import get_runtime_config
from ..text_utils import looks_like_llm_error_text
from ..disclosure_policy import (
    DisclosurePolicy,
    DisclosureAction,
    DisclosureDecision,
    create_disclosure_policy_from_calibration,
)
from ..active_learning import get_active_learning_coordinator
from ..user_profile import GlobalUserProfile
from ..ml_contradiction_detector import MLContradictionDetector
from ..resolution_patterns import has_resolution_intent, get_matched_patterns
from ..source_authority import classify_source_authority, SourceAuthority
from ..contradiction_trace_logger import get_trace_logger
from ..domain_detector import detect_domains, detect_query_domains
from ..engine.anchors import AnchorSystem
from ..engine.resonance import ResonanceScorer
from ..engine.degradation import DegradationDetector
from groundcheck.semantic_matcher import SemanticMatcher
from sse.contradictions import heuristic_contradiction
from ..trust_evolution import (
    compute_grounding_score as _te_compute_grounding_score,
    should_express_uncertainty as _te_should_express_uncertainty,
    generate_uncertain_response as _te_generate_uncertain_response,
)

# Production integrations: IntentRouter + FactStore
from ..intent_router import IntentRouter, Intent, RoutedIntent, get_template_response
from ..fact_store import FactStore, FactExtractor

# Import session tracking for response variation
try:
    from ..db_utils import get_thread_session_db, ThreadSessionDB
    _SESSION_DB_AVAILABLE = True
except ImportError:
    _SESSION_DB_AVAILABLE = False

# Constants for NL resolution
_NL_RESOLUTION_STOPWORDS = {'i', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'my', 'the', 'a', 'an', 'at', 'in', 'on', 'to'}
_UNSTRUCTURED_SLOT_NAME = '_unstructured_'

# Constants for contradiction resolution
RESOLVED_CONTRADICTION_CONFIDENCE = 0.85  # Confidence level for assertively resolved contradictions
SSE_CONTRADICTION_RESULT = 'contradiction'  # SSE heuristic contradiction result value

# Constants for value extraction
_EXTRACTION_STOPWORDS = ["a", "an", "the", "as", "is", "was", "at", "in", "on", "for"]
LONGFORM_SUMMARY_MIN_CHARS = 420
LONGFORM_SUMMARY_MAX_CHARS = 1800


def _build_gate_explanation(
    gate_reason: Optional[str],
    intent_align: float,
    memory_align: float,
    grounding_score: Optional[float],
    hard_conflicts: int,
) -> str:
    """Build a human-readable explanation of why a gate passed or failed."""
    reason = str(gate_reason or "")
    parts = []
    if "contradiction_disclosure" in reason:
        parts.append("A stored fact conflicts with what you just said.")
    elif "unresolved_contradictions" in reason or "hard_conflict_pending" in reason:
        parts.append(f"{hard_conflicts} unresolved conflict(s) related to this query block a confident answer.")
    elif "grounding_fail" in reason:
        parts.append(f"Response isn't grounded in memory (grounding={grounding_score:.2f}).")
    elif "contradiction_fail" in reason:
        parts.append("Contradiction check failed — retrieved memories conflict.")
    elif "narration_fail" in reason:
        parts.append("Response quality check failed.")
    elif "degraded_output" in reason:
        parts.append("Generated response was flagged as degraded quality.")
    elif "general_knowledge_bypass" in reason:
        parts.append("General knowledge query — memory alignment not required.")
    if intent_align < 0.5 and "bypass" not in reason:
        parts.append(f"Low reasoning confidence ({intent_align:.2f}).")
    if memory_align < 0.4 and "bypass" not in reason:
        parts.append(f"Weak memory alignment ({memory_align:.2f}).")
    return " ".join(parts) if parts else reason


# ── Identity pronoun sanitizer ──────────────────────────────────
# Catches common first-person adoptions of user facts and rewrites
# them to second-person so Aether doesn't claim "My name is Nick".
_IDENTITY_PRONOUN_FIXES = [
    # "My name is X"  → "Your name is X"
    (re.compile(r"\bmy name is\b", re.I), "Your name is"),
    # "I'm X" at sentence start when followed by a period/comma/space
    (re.compile(r"(?<!['\w])I'm ([A-Z][a-z]+)\b"), r"Your name is \1"),
    # "I am X" (proper noun after)
    (re.compile(r"\bI am ([A-Z][a-z]+)\b(?!\s+(a|an|the|not|very|really|quite|just|also|currently|going))"),
     r"Your name is \1"),
    # "My favorite X is Y" → "Your favorite X is Y"
    (re.compile(r"\bmy favorite\b", re.I), "Your favorite"),
    # "My job is" / "I work at" → "You work at"
    (re.compile(r"\bmy job is\b", re.I), "Your job is"),
    (re.compile(r"\bI work at\b", re.I), "You work at"),
    (re.compile(r"\bI live in\b", re.I), "You live in"),
    (re.compile(r"\bI am a freelance\b", re.I), "You are a freelance"),
    (re.compile(r"\bI am a ([a-z]+(?:\s+[a-z]+)?)\s*\.", re.I), r"You are a \1."),
]


def _sanitize_identity_pronouns(answer: str) -> str:
    """Rewrite first-person user-fact claims to second-person.

    Only touches patterns where the LLM is clearly adopting a user fact
    (e.g. "My name is Nick") rather than speaking about itself ("I searched
    my memory").  Conservative: only fires on known slot-adjacent phrases.
    """
    if not answer:
        return answer
    out = answer
    for pattern, replacement in _IDENTITY_PRONOUN_FIXES:
        out = pattern.sub(replacement, out)
    return out


# ---------------------------------------------------------------------------
# Phase G3: Fisher-weighted reranking
# ---------------------------------------------------------------------------

def _fisher_rerank(
    retrieved: list,
    fisher_weight: float = 0.3,
) -> list:
    """Rerank retrieved memories by precision (inverse total uncertainty).

    Memories with tighter sigma (lower total uncertainty) get a boost.
    This complements volatility reranking (which boosts unstable memories
    for surfacing) by also rewarding high-certainty memories.

    Args:
        retrieved: list of (MemoryItem, score) tuples
        fisher_weight: 0-1, how much precision influences the final score

    Returns:
        Re-sorted list of (MemoryItem, score) tuples
    """
    if not retrieved or fisher_weight <= 0:
        return retrieved

    # Collect total_uncertainty for memories that have sigma
    uncertainties = []
    for mem, _score in retrieved:
        sigma = getattr(mem, "sigma", None)
        if sigma is not None:
            uncertainties.append(float(np.sum(sigma)))
        else:
            uncertainties.append(None)

    # If no memories have sigma, skip
    valid = [u for u in uncertainties if u is not None]
    if not valid:
        return retrieved

    # Normalize: precision = 1 - (uncertainty / max_uncertainty)
    max_unc = max(valid) if valid else 1.0
    if max_unc < 1e-12:
        return retrieved

    reranked = []
    for (mem, score), unc in zip(retrieved, uncertainties):
        if unc is not None:
            precision = 1.0 - (unc / max_unc)
        else:
            precision = 0.5  # neutral for memories without sigma

        adjusted = score * (1.0 + fisher_weight * precision)
        reranked.append((mem, adjusted))

    reranked.sort(key=lambda x: x[1], reverse=True)
    return reranked




class CRTEnhancedRAG:
    """CRT-Enhanced RAG — engine core (package version)."""

    _URL_RE = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)

    def __init__(
        self,
        memory_db: Optional[str] = None,
        ledger_db: Optional[str] = None,
        profile_db: Optional[str] = None,
        config: Optional[CRTConfig] = None,
        llm_client=None
    ):
        """Initialize CRT-enhanced RAG."""
        self.config = config or CRTConfig()
        self.crt_math = CRTMath(self.config)
        memory_db = memory_db or str(resolve_runtime_path("crt_memory.db"))
        ledger_db = ledger_db or str(resolve_runtime_path("crt_ledger.db"))
        profile_db = profile_db or str(resolve_profile_db_path())
        
        # Store LLM client for passing to subsystems
        self._llm_client = llm_client
        
        # CRT components
        self.memory = CRTMemorySystem(memory_db, self.config)
        self.ledger = ContradictionLedger(ledger_db, self.config)
        self.memory.set_contradiction_ledger(self.ledger)

        # Governance bridge: connects memory trust to belief/speech tracking
        try:
            from personal_agent.governance_bridge import GovernanceBridge
            _bridge = GovernanceBridge(memory_system=self.memory)
            self.memory.set_governance_bridge(_bridge)
        except Exception as _bridge_err:
            print(f"[GOVERNANCE_BRIDGE] Init skipped (non-fatal): {_bridge_err}")

        # BDG cascade propagation (lazy — builds on first contradiction)
        try:
            from personal_agent.memory_graph import get_live_bdg
            self._live_bdg = get_live_bdg(self.memory, self.ledger)
            print("[BDG] LiveBDG singleton registered")
        except Exception as _bdg_init_err:
            print(f"[BDG] Failed to register LiveBDG (non-fatal): {_bdg_init_err}")
            self._live_bdg = None

        # Keep profile storage isolated for non-default test/temp memory DBs unless
        # the caller explicitly passes profile_db.
        default_memory_db = str(resolve_runtime_path("crt_memory.db"))
        default_profile_db = str(resolve_profile_db_path())
        resolved_profile_db = profile_db
        try:
            if profile_db == default_profile_db and memory_db != default_memory_db:
                mem_path = Path(memory_db)
                resolved_profile_db = str(mem_path.with_name("profile.db"))
        except Exception:
            resolved_profile_db = profile_db

        # Global user profile (shared across all threads within this profile DB)
        self.user_profile = GlobalUserProfile(db_path=resolved_profile_db)
        
        # Reasoning engine
        self.reasoning = ReasoningEngine(llm_client)
        self.anchor_system = AnchorSystem()
        self.resonance_scorer = ResonanceScorer(anchor_system=self.anchor_system)
        self.degradation_detector = DegradationDetector()

        # Optional learned suggestions (metadata-only).
        self.learned_suggestions = LearnedSuggestionEngine()
        self.runtime_config = get_runtime_config()
        
        # ML-based contradiction detector (Phase 2/3 models)
        try:
            self.ml_detector = MLContradictionDetector()
            logger.info("[ML_DETECTOR] ML contradiction detector initialized")
        except Exception as e:
            logger.warning(f"[ML_DETECTOR] Failed to initialize ML detector: {e}")
            self.ml_detector = None
        
        # Semantic matcher for paraphrase detection
        try:
            self.semantic_matcher = SemanticMatcher(use_embeddings=True, embedding_threshold=0.85)
            logger.info("[SEMANTIC_MATCHER] Initialized semantic matcher")
        except Exception as e:
            logger.warning(f"[SEMANTIC_MATCHER] Failed to initialize: {e}")
            self.semantic_matcher = None
        
        # Active learning coordinator (graceful degradation if unavailable)
        try:
            self.active_learning = get_active_learning_coordinator()
        except Exception as e:
            log_swallowed_exception("crt_rag.__init__.active_learning", e)
            self.active_learning = None
        
        # Load trained response classifier (graceful degradation)
        self._classifier_model = None
        self._load_classifier()
        
        # Two-tier fact extraction system (hard slots + open tuples)
        # Set enable_llm=False for local-only operation (no external API calls)
        try:
            self.two_tier_system = TwoTierFactSystem(enable_llm=False)
            logger.info("[TWO_TIER] Two-tier fact extraction system initialized (local regex only)")
            # Connect two-tier system to ledger for enhanced contradiction detection
            self.ledger.set_two_tier_system(self.two_tier_system)
        except Exception as e:
            logger.warning(f"[TWO_TIER] Failed to initialize two-tier system: {e}")
            self.two_tier_system = None
        
        # Disclosure policy for yellow-zone routing (calibrated thresholds)
        try:
            self.disclosure_policy = create_disclosure_policy_from_calibration(
                calibration_path="artifacts/calibrated_thresholds.json",
                enable_budget=True
            )
            logger.info("[DISCLOSURE_POLICY] Yellow-zone routing initialized")
        except Exception as e:
            logger.warning(f"[DISCLOSURE_POLICY] Failed to initialize: {e}")
            self.disclosure_policy = DisclosurePolicy()  # Use defaults
        
        # Session tracking
        self.session_id = str(uuid.uuid4())[:8]
        
        # ====== PRODUCTION: IntentRouter + FactStore Integration ======
        # Intent classification for smarter routing
        try:
            self.intent_router = IntentRouter()
            logger.info("[INTENT_ROUTER] Intent classification system initialized")
        except Exception as e:
            logger.warning(f"[INTENT_ROUTER] Failed to initialize: {e}")
            self.intent_router = None
        
        # Structured fact storage (user.name, user.favorite_color, etc.)
        # Uses hybrid extraction: fast regex + LLM-based semantic extraction
        try:
            facts_db_path = str(Path(memory_db).parent / "crt_facts.db")
            self.fact_store = FactStore(db_path=facts_db_path, llm_client=self._llm_client)
            logger.info(f"[FACT_STORE] Structured fact store initialized at {facts_db_path}")
        except Exception as e:
            logger.warning(f"[FACT_STORE] Failed to initialize: {e}")
            self.fact_store = None
        
        # Orchestration tracing (verbose mode for debugging)
        self.react_tracing_enabled = False
        self._react_trace: List[Dict[str, Any]] = []
        # ====== END PRODUCTION ADDITIONS ======
        
        # Law 6: Continuity auditor (pre-generation hook)
        try:
            from personal_agent.immune_agents.continuity_auditor import ContinuityAuditor
            self.continuity_auditor = ContinuityAuditor(db_path=memory_db)
            logger.info("[CONTINUITY_AUDITOR] Law 6 pre-generation gate initialized")
        except Exception as e:
            logger.warning(f"[CONTINUITY_AUDITOR] Failed to initialize: {e}")
            self.continuity_auditor = None

        # Performance: LRU cache for fact extraction to avoid repeated regex parsing
        # Using OrderedDict for efficient LRU eviction (move_to_end + popitem)
        self._fact_extraction_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_cache_entries = 1000
        self._max_text_size = 10_000  # Skip caching very large texts

    def new_usage_trace_id(self) -> str:
        """Create a stable correlation id for one user-visible memory usage flow."""
        return f"usage_{uuid.uuid4().hex}"
    def _record_memory_usage(
        self,
        items: List[Any],
        *,
        event_type: str,
        reason: Optional[str] = None,
        usage_trace_id: Optional[str] = None,
        query: Optional[str] = None,
        thread_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Best-effort usage logging for memory hits."""
        memory_ids: List[str] = []
        seen: Set[str] = set()
        for item in items:
            candidate = item
            if isinstance(candidate, tuple) and candidate:
                candidate = candidate[0]

            memory_id: Optional[str] = None
            if isinstance(candidate, str):
                memory_id = candidate
            elif isinstance(candidate, dict):
                memory_id = (
                    candidate.get("memory_id")
                    or candidate.get("old_memory_id")
                    or candidate.get("new_memory_id")
                )
            else:
                memory_id = getattr(candidate, "memory_id", None)

            normalized_memory_id = str(memory_id or "").strip()
            if not normalized_memory_id or normalized_memory_id in seen:
                continue
            memory_ids.append(normalized_memory_id)
            seen.add(normalized_memory_id)

        if not memory_ids:
            return

        event_metadata = dict(metadata or {})
        if usage_trace_id:
            event_metadata["usage_trace_id"] = usage_trace_id
        if thread_id:
            event_metadata["thread_id"] = thread_id
        if query:
            event_metadata["query"] = str(query)[:500]

        try:
            self.memory.record_memory_usage(
                memory_ids,
                event_type=event_type,
                actor="system",
                reason=reason,
                metadata=event_metadata or None,
            )
        except Exception as e:
            logger.debug("[MEMORY_USAGE] Failed to record %s events: %s", event_type, e)
    def _is_semantic_match(self, a: str, b: str, slot: str = "") -> bool:
        """Check if two values are semantically equivalent (paraphrases).
        
        For identity-critical slots (name, employer, location, spouse, etc.),
        only exact string matches count  -  the semantic model would incorrectly
        match "Alex Chen" ~ "Jordan Blake" because both are person names.
        """
        # Identity-critical hard slots: different values are NEVER semantic matches
        HARD_IDENTITY_SLOTS = {
            "name", "employer", "location", "spouse", "pet_name", "child_name",
            "title", "project_name", "email", "phone", "birthday",
            "masters_school", "undergrad_school", "first_language",
            "favorite_color", "favorite_language", "favorite_food",
            "favorite_drink", "favorite_book", "favorite_movie", "favorite_music",
        }
        a_norm = a.lower().strip()
        b_norm = b.lower().strip()
        if slot in HARD_IDENTITY_SLOTS:
            return a_norm == b_norm
        
        if self.semantic_matcher is None:
            return a_norm == b_norm
        try:
            is_match, method, _ = self.semantic_matcher.is_match(a, {b}, slot=slot)
            if is_match:
                logger.debug(f"[SEMANTIC_MATCH] '{a}' ~ '{b}' via {method}")
            return is_match
        except Exception:
            return a_norm == b_norm
    def _filter_non_authoritative_slot_claims(
        self,
        retrieved: List[Tuple[MemoryItem, float]],
        inferred_slots: List[str],
    ) -> List[Tuple[MemoryItem, float]]:
        """Remove slot-shaped claims that are not allowed to answer user facts."""
        if not retrieved or not inferred_slots:
            return retrieved

        slot_set = {str(slot or "").strip().lower() for slot in inferred_slots if str(slot or "").strip()}
        if not slot_set:
            return retrieved

        filtered: List[Tuple[MemoryItem, float]] = []
        for mem, score in retrieved:
            try:
                facts = extract_fact_slots(mem.text) or {}
            except Exception:
                facts = {}

            if facts and (set(facts.keys()) & slot_set) and not self.memory.can_answer_user_fact(mem):
                continue
            filtered.append((mem, score))

        return filtered
    def _should_express_uncertainty(
        self,
        retrieved: List[Tuple[MemoryItem, float]],
        contradictions_count: int = 0,
        gates_passed: bool = False
    ) -> Tuple[bool, str]:
        """Delegated to trust_evolution module."""
        return _te_should_express_uncertainty(retrieved, contradictions_count, gates_passed)
    def _generate_uncertain_response(
        self,
        user_query: str,
        retrieved: List[Tuple[MemoryItem, float]],
        reason: str,
        recommended_next_action: Optional[Dict[str, Any]] = None,
        conflict_beliefs: Optional[List[str]] = None,
    ) -> str:
        """Delegated to trust_evolution module."""
        return _te_generate_uncertain_response(
            user_query, retrieved, reason,
            runtime_config=getattr(self, 'runtime_config', None),
            recommended_next_action=recommended_next_action,
            conflict_beliefs=conflict_beliefs,
        )
    def query(
        self,
        user_query: str,
        user_marked_important: bool = False,
        mode: Optional[ReasoningMode] = None,
        thread_id: Optional[str] = None,
        model_override: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        channel: Optional[str] = None,
        origin: Optional[str] = None,
        authority: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query with CRT principles applied.
        
        Process:
        0. Store user input as memory (USER source)
        1. Trust-weighted retrieval
        2. Generate candidate output (reasoning)
        3. Check reconstruction gates (intent + memory alignment)
        4. If gates pass -> belief (high trust)
        5. If gates fail -> speech (low trust fallback)
        6. Detect contradictions
        7. Update trust scores
        8. Queue reflection if needed
        
        Returns both the response AND CRT metadata.
        """
        # 0. Store user input as USER memory ONLY when it's an assertion.
        # Questions and control instructions should not be treated as durable factual claims.
        user_memory: Optional[MemoryItem] = None
        profile_updates: List[Dict[str, str]] = []
        contradiction_detected: bool = False
        contradiction_entry = None
        extra_context: Dict[str, str] = {}  # Injected context for template-free paths
        user_text = self._strip_continuity_augmented_text(user_query)
        if not user_text:
            user_text = (user_query or "").strip()
        usage_trace_id = self.new_usage_trace_id()

        # Reflection-to-behavior: compute gate boost from self-model blindspots
        _blindspot_gate_boost = 0.0
        try:
            from personal_agent.self_model import get_self_model
            _sm = get_self_model()
            _directives = _sm.get_behavioral_directives(query=user_text)
            _blindspot_gate_boost = _directives.get("gate_boost", 0.0)
            if _blindspot_gate_boost > 0:
                logger.info(
                    "[REFLECTION_LOOP] Blindspot gate boost=%.2f for domains=%s",
                    _blindspot_gate_boost,
                    _directives.get("caution_domains", []),
                )
        except Exception as exc:
            logger.debug("[REFLECTION_LOOP] gate boost computation failed: %s", exc)

        # High-risk prompt types should be treated as instructions even if they do not
        # look like questions (multi-paragraph prompt injection often starts as declarative).
        is_memory_citation = self._is_memory_citation_request(user_text)
        is_contradiction_status = self._is_contradiction_status_request(user_text)
        is_memory_inventory = self._is_memory_inventory_request(user_text)

        user_input_kind = self._classify_user_input(user_text)
        logger.info(f"[PROFILE_DEBUG] Input classified as: {user_input_kind}")
        social_input = self.memory.is_social_channel(channel)

        # Assistant-profile questions ("who are you?", "what are you?") are handled
        # by the system prompt in reasoning.py which already has the full identity block.
        # No early-return needed — let the model respond naturally.
        
        # Check for natural language contradiction resolution FIRST
        # This prevents the resolution statement from being stored as a new assertion
        nl_resolution_occurred = False
        try:
            nl_resolution_occurred = False if social_input else self._detect_and_resolve_nl_resolution(user_text)
            if nl_resolution_occurred:
                logger.info(f"[NL_RESOLUTION] Natural language resolution detected and processed")
                # The system DID detect a contradiction  -  mark it so metadata is correct.
                contradiction_detected = True
                # If we resolved a contradiction, treat this as an instruction/acknowledgment, not an assertion
                # This prevents "Google is correct" from being stored as a new fact that creates another contradiction
                if user_input_kind == "assertion":
                    logger.info(f"[NL_RESOLUTION] Reclassifying assertion -> instruction (NL resolution)")
                    user_input_kind = "instruction"
        except Exception as e:
            logger.warning(f"[NL_RESOLUTION] Failed to detect/resolve NL resolution: {e}", exc_info=True)
        
        if user_input_kind == "assertion" and (is_memory_citation or is_contradiction_status or is_memory_inventory):
            logger.info(f"[PROFILE_DEBUG] Reclassifying assertion -> instruction (special query type)")
            user_input_kind = "instruction"

        # ==================================================================
        # GASLIGHTING DETECTION: Check if user is denying something they said
        # ==================================================================
        # This runs BEFORE normal processing to catch denial attempts early
        # NOTE: Import at block level to avoid scope issues with later local imports
        from ..crt_ledger import ContradictionType as GaslightingContradictionType
        try:
            previous_user_memories = self._load_thread_user_memories(thread_id=thread_id)
            is_gaslighting, denied_value, original_memory, slot = self._detect_gaslighting_attempt(
                user_text, previous_user_memories
            )
            if is_gaslighting and original_memory:
                logger.info(f"[GASLIGHTING] Detected denial of '{denied_value}' - citing original")
                citation = self._build_gaslighting_citation(
                    denial_text=user_text,
                    denied_value=denied_value,
                    original_memory=original_memory,
                    slot=slot
                )
                # Record this as a DENIAL contradiction
                try:
                    new_memory = self.memory.store_memory(
                        text=user_text,
                        confidence=0.5,  # Lower confidence for denial attempts
                        source=MemorySource.USER,
                        context={"type": "user_input", "kind": "denial"},
                        thread_id=thread_id,
                        channel=channel,
                        origin=origin,
                    )
                    self._record_and_cascade(
                        old_memory_id=original_memory.memory_id,
                        new_memory_id=new_memory.memory_id,
                        drift_mean=0.9,  # High drift for gaslighting
                        confidence_delta=0.45,
                        query=user_text,
                        summary=f"GASLIGHTING: User denied saying '{denied_value}' but we have record",
                        old_text=original_memory.text,
                        new_text=user_text,
                        old_vector=original_memory.vector,
                        new_vector=new_memory.vector,
                        contradiction_type=GaslightingContradictionType.DENIAL,
                        suggested_policy="cite_original",
                        thread_id=thread_id,
                    )
                except Exception as e:
                    logger.warning(f"[GASLIGHTING] Failed to record contradiction: {e}")
                
                return {
                    'answer': citation,
                    'thinking': None,
                    'mode': 'quick',
                    'confidence': 0.99,  # High confidence in our memory
                    'response_type': 'belief',
                    'gates_passed': True,
                    'gate_reason': 'gaslighting_detected',
                    'intent_alignment': 0.99,
                    'memory_alignment': 1.0,
                    'contradiction_detected': True,
                    'contradiction_entry': None,
                    'retrieved_memories': [],
                    'prompt_memories': [],
                    'unresolved_contradictions_total': 1,
                    'unresolved_hard_conflicts': 1,
                    'learned_suggestions': [],
                    'heuristic_suggestions': [],
                    'best_prior_trust': None,
                    'session_id': self.session_id,
                }
        except Exception as e:
            logger.warning(f"[GASLIGHTING] Detection failed: {e}")

        # ==================================================================
        # BLINDSIDE DETECTION: mass-retraction / identity-wipe attacks
        # ==================================================================
        try:
            prev_user_mems = [
                m for m in self.memory._load_all_memories()
                if m.source == MemorySource.USER
            ]
            is_blindside, blindside_reason = self._detect_blindside_attack(
                user_text, prev_user_mems
            )
            if is_blindside:
                logger.info(f"[BLINDSIDE] Detected: {blindside_reason}")
                # Store the message at low confidence but DO NOT accept the new facts
                try:
                    self.memory.store_memory(
                        text=user_text,
                        confidence=0.3,
                        source=MemorySource.USER,
                        context={"type": "user_input", "kind": "blindside"},
                        thread_id=thread_id,
                        channel=channel,
                        origin=origin,
                    )
                except Exception:
                    pass
                # Inject blindside context so the model can respond naturally
                # instead of returning a hardcoded hedge template.
                blindside_context = (
                    f"\n[BLINDSIDE ALERT]\n"
                    f"The user just tried to change multiple facts at once.\n"
                    f"Reason: {blindside_reason}\n"
                    f"You should ask which specific detail they want to correct "
                    f"rather than accepting everything at once.\n"
                )
                extra_context["blindside_alert"] = blindside_context
                contradiction_detected = True
        except Exception as e:
            logger.warning(f"[BLINDSIDE] Detection failed: {e}")

        # P0 FIX: Process contradiction lifecycle transitions on every query
        # This moves contradictions through ACTIVE -> SETTLING -> SETTLED -> ARCHIVED
        # based on confirmation counts and time elapsed
        try:
            transitions = self.ledger.process_lifecycle_transitions()
            if any(v > 0 for v in transitions.values()):
                logger.info(f"[LIFECYCLE] Processed transitions: {transitions}")
        except Exception as e:
            logger.warning(f"[LIFECYCLE] Failed to process lifecycle transitions: {e}")

        # Deterministic safe path: refuse prompt/system-instruction disclosure.
        # This prevents the model from hallucinating and avoids memory-claim phrasing
        # that can confuse the evaluator.
        if user_input_kind in ("question", "instruction") and self._is_system_prompt_request(user_text):
            answer = (
                "I can't share my system prompt or hidden instructions verbatim. "
                "If you tell me what you're trying to do, I can summarize how I'm designed to behave "
                "or help you accomplish the goal another way."
            )
            return {
                'answer': answer,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.95,
                'response_type': 'speech',
                'gates_passed': False,
                'gate_reason': 'system_prompt',
                'intent_alignment': 0.95,
                'memory_alignment': 1.0,
                'contradiction_detected': False,
                'contradiction_entry': None,
                'retrieved_memories': [],
                'prompt_memories': [],
                'unresolved_contradictions_total': 0,
                'unresolved_hard_conflicts': 0,
                'learned_suggestions': [],
                'heuristic_suggestions': [],
                'best_prior_trust': None,
                'session_id': self.session_id,
            }
        if user_input_kind == "assertion":
            logger.info(f"[PROFILE_DEBUG] Processing assertion - about to store memory and update profile")
            if looks_like_llm_error_text(user_text):
                logger.warning("[MEMORY_GUARD] Skipping leaked LLM error text from user-memory storage")
                user_input_kind = "instruction"

            # ── Source authority analysis ──────────────────────────────────
            # Detect reported speech, journal entries, third-party claims,
            # and meta-corrections.  Adjusts confidence + context tags so
            # contradiction resolution can weight assertions properly.
            _src_auth = classify_source_authority(user_text)
            logger.info(
                "[SOURCE_AUTH] kind=%s confidence=%.2f speaker=%s reason=%s",
                _src_auth.kind, _src_auth.confidence,
                _src_auth.speaker, _src_auth.reason,
            )

            # Meta-corrections should resolve contradictions, not create new ones.
            # Reclassify as instruction so the assertion path doesn't fire, then
            # route through NL resolution to actually resolve the conflict.
            if _src_auth.kind == "meta_correction" and not nl_resolution_occurred:
                logger.info("[SOURCE_AUTH] Meta-correction detected — routing to NL resolution")
                user_input_kind = "instruction"
                # Attempt NL resolution with the meta-correction text
                try:
                    nl_resolution_occurred = self._detect_and_resolve_nl_resolution(user_text)
                    if nl_resolution_occurred:
                        contradiction_detected = True
                        logger.info("[SOURCE_AUTH] Meta-correction resolved via NL resolution")
                    else:
                        # NL resolution didn't match a specific contradiction.
                        # Still store the assertion but at elevated confidence so it wins.
                        user_input_kind = "assertion"
                        logger.info("[SOURCE_AUTH] Meta-correction didn't match open contradictions — storing as high-confidence assertion")
                except Exception as _e:
                    logger.warning("[SOURCE_AUTH] Meta-correction NL resolution failed: %s", _e)
                    user_input_kind = "assertion"

            _assertion_confidence = _src_auth.confidence
            _assertion_context = {
                "type": "user_input",
                "kind": user_input_kind,
                "source_authority": _src_auth.kind,
                "source_authority_reason": _src_auth.reason,
            }
            if _src_auth.speaker:
                _assertion_context["reported_speaker"] = _src_auth.speaker
            if _src_auth.is_historical:
                _assertion_context["temporal_framing"] = "historical"

        if user_input_kind == "assertion":
            # Store as PROVISIONAL — will be promoted to confirmed after
            # contradiction detection passes. This prevents same-turn
            # self-citation where the new claim retrieves itself as evidence.
            _assertion_authority = authority or "provisional"

            # Sub-classify: is this a flat fact or a belief/position?
            _resolved_kind = kind
            _belief_reason = None
            if not _resolved_kind:
                try:
                    from personal_agent.belief_classifier import classify_assertion_kind
                    _resolved_kind, _belief_reason = classify_assertion_kind(user_text)
                    if _belief_reason:
                        logger.info("[BELIEF_CLASSIFY] %s → %s (%s)", user_text[:60], _resolved_kind, _belief_reason)
                except Exception as _bc_err:
                    logger.debug("[BELIEF_CLASSIFY] fallback to user_fact: %s", _bc_err)
                    _resolved_kind = "user_fact"

            print(f"[PROVISIONAL] Storing assertion as authority={_assertion_authority} kind={_resolved_kind}: \"{user_text[:60]}\"")
            ingest_result = self.ingest_memory_write(
                text=user_text,
                confidence=_assertion_confidence,
                source=MemorySource.USER,
                context=_assertion_context,
                user_marked_important=user_marked_important,
                thread_id=thread_id,
                channel=channel,
                origin=origin,
                authority=_assertion_authority,
                kind=_resolved_kind,
            )
            user_memory = ingest_result["memory"]
            can_update_profile = self.memory.can_update_user_profile(user_memory)
            profile_updates.extend(ingest_result.get("profile_updates") or [])
            logger.info(f"[PROFILE_DEBUG] Memory stored, now updating user profile...")
            if not can_update_profile:
                logger.info(
                    "[PROFILE_DEBUG] Skipping canonical profile promotion for authority=%s channel=%s kind=%s",
                    getattr(user_memory, "authority", "unknown"),
                    getattr(user_memory, "channel", "unknown"),
                    getattr(user_memory, "kind", "observation"),
                )
            
            # Also update global user profile with extracted facts
            # This enables cross-thread memory (e.g., name persists across chats)
            try:
                logger.info("[PROFILE_DEBUG] Shared ingestion path already updated user profile")
                profile_result = {}
                
                # Log any profile fact contradictions to the ledger
                if profile_result and profile_result.get('replaced'):
                    for slot, replacement in profile_result['replaced'].items():
                        logger.info(f"[PROFILE_CONTRADICTION] {slot}: '{replacement['old']}' -> '{replacement['new']}'")
                        profile_updates.append({
                            "slot": str(slot),
                            "old": str(replacement.get("old") or ""),
                            "new": str(replacement.get("new") or ""),
                        })
                        try:
                            # Record in the contradiction ledger for transparency
                            profile_contra = self._record_and_cascade(
                                old_memory_id=f"profile_{slot}_old",
                                new_memory_id=f"profile_{slot}_new",
                                drift_mean=0.8,  # High drift for profile changes
                                confidence_delta=0.0,  # User assertions, equally confident
                                old_text=f"FACT: {slot} = {replacement['old']}",
                                new_text=f"FACT: {slot} = {replacement['new']}",
                                contradiction_type="profile_update",
                                summary=f"Profile update: {slot} changed from '{replacement['old']}' to '{replacement['new']}'",
                                thread_id=thread_id,
                            )
                            # NOTE: No longer auto-resolving. Contradiction stays OPEN.
                            print(f"[PROFILE] Contradiction logged (OPEN): {profile_contra.ledger_id}")
                        except Exception as ledger_err:
                            logger.warning(f"[PROFILE] Failed to log contradiction to ledger: {ledger_err}")

                logger.info(f"[PROFILE_DEBUG] OK Profile update completed successfully")
            except Exception as e:
                logger.error(f"[PROFILE_DEBUG] âŒ Failed to update user profile: {e}", exc_info=True)

            # Long-form narrative summary capture (best-effort, low-trust)
            try:
                self._maybe_store_longform_summary(
                    text=user_text,
                    thread_id=thread_id,
                    user_marked_important=user_marked_important,
                )
            except Exception as e:
                log_swallowed_exception("crt_rag.query._maybe_store_longform_summary", e)

            # Open-world fact extraction via two-tier system (LLM-based, background).
            # This captures arbitrary facts the user mentions beyond predefined slots.
            import threading as _threading
            _tt_text = user_text
            _tt_memory = self.memory
            _tt_thread_id = thread_id
            _tt_channel = channel
            _tt_origin = origin
            _tt_authority = authority
            _tt_kind = kind
            _tt_can_store = can_update_profile
            def _run_two_tier_extraction(text, memory, tid):
                try:
                    if not _tt_can_store:
                        return
                    from ..two_tier_facts import get_two_tier_system
                    tt_system = get_two_tier_system()
                    tt_result = tt_system.extract_facts(text)
                    for tup in tt_result.open_tuples:
                        if tup.confidence >= 0.6:
                            mem_text = f"FACT: {tup.entity}.{tup.attribute} = {tup.value}"
                            memory.store_memory(
                                text=mem_text,
                                confidence=tup.confidence,
                                source=MemorySource.USER,
                                context={"type": "llm_extracted_fact", "attribute": tup.attribute, "entity": tup.entity},
                                thread_id=tid,
                                channel=_tt_channel,
                                origin=_tt_origin,
                                authority=_tt_authority,
                                kind=(_tt_kind or "user_fact"),
                            )
                            logger.debug(f"[TWO_TIER] Stored: {mem_text}")
                except Exception as _e:
                    logger.debug(f"[TWO_TIER] Extraction failed (non-blocking): {_e}")
            _threading.Thread(
                target=_run_two_tier_extraction,
                args=(_tt_text, _tt_memory, _tt_thread_id),
                daemon=True,
            ).start()

            # If the user is clarifying a previously-detected hard conflict, mark it resolved.
            # This is intentionally conservative: only hard CONFLICT types, and only when
            # the asserted value matches one side of the conflict.
            if can_update_profile:
                try:
                    self._resolve_open_conflicts_from_assertion(user_text)
                except Exception as e:
                    # Resolution is best-effort; never block the main chat loop.
                    log_swallowed_exception("crt_rag.query._resolve_open_conflicts", e)
            
            # P0 FIX: Track implicit confirmations for lifecycle transitions
            # When user repeats the "new" value from a contradiction, it's an implicit confirmation
            if can_update_profile:
                try:
                    self._track_implicit_confirmations(user_text)
                except Exception as e:
                    logger.warning(f"[LIFECYCLE] Failed to track implicit confirmations: {e}")
            
            # BUG 1 FIX: Check for contradictions using ML detector (ALL facts, not hardcoded slots)
            try:
                contradiction_detected, contradiction_entry = self._check_all_fact_contradictions_ml(
                    user_memory, user_text, thread_id=thread_id
                )
            except Exception as e:
                logger.warning(f"[ML_CONTRADICTION] Failed to check ML contradictions: {e}", exc_info=True)

            # SLOT-AWARE EARLY CHECK: If ML didn't catch it, check exclusive slots directly.
            # This runs BEFORE promotion so the memory stays provisional if contradicted.
            if not contradiction_detected and user_memory is not None:
                try:
                    from ..slot_discovery import get_slot_type, SlotType
                    _early_facts = extract_fact_slots(user_text) or {}
                    if _early_facts:
                        _early_priors = self._load_thread_user_memories(
                            thread_id=thread_id,
                            exclude_memory_id=user_memory.memory_id,
                        )
                        for _eslot, _enew in _early_facts.items():
                            _etype = get_slot_type(_eslot, db_path=getattr(self.memory, 'db_path', None))
                            if _etype != SlotType.EXCLUSIVE:
                                continue
                            _enew_norm = getattr(_enew, "normalized", None)
                            for _epm in _early_priors:
                                _epf = extract_fact_slots(_epm.text) or {}
                                _eold = _epf.get(_eslot)
                                if _eold is None:
                                    continue
                                _eold_norm = getattr(_eold, "normalized", None)
                                if _eold_norm and _enew_norm and _eold_norm != _enew_norm:
                                    print(f"[SLOT_EARLY_CHECK] EXCLUSIVE contradiction: {_eslot} '{_eold_norm}' -> '{_enew_norm}'")
                                    logger.info(f"[SLOT_EARLY_CHECK] Exclusive slot '{_eslot}' contradiction: '{_eold_norm}' -> '{_enew_norm}'")
                                    user_vector = encode_vector(user_text)
                                    drift = self.crt_math.drift_meaning(user_vector, _epm.vector)
                                    contradiction_entry = self._record_and_cascade(
                                        old_memory_id=_epm.memory_id,
                                        new_memory_id=user_memory.memory_id,
                                        drift_mean=drift,
                                        confidence_delta=_epm.confidence - 0.95,
                                        query=user_text,
                                        summary=f"Slot correction ({_eslot}): '{_eold_norm}' -> '{_enew_norm}'",
                                        old_text=_epm.text,
                                        new_text=user_text,
                                        old_vector=_epm.vector,
                                        new_vector=user_vector,
                                        thread_id=thread_id,
                                    )
                                    contradiction_detected = True
                                    # Demote old memory trust
                                    self.memory.evolve_trust_for_contradiction(_epm, user_vector)
                                    break
                            if contradiction_detected:
                                break
                except Exception as _slot_err:
                    logger.warning(f"[SLOT_EARLY_CHECK] Error: {_slot_err}", exc_info=True)

            # Name declarations: store the memory, check for contradictions, then fall
            # through to the reasoning engine for a natural response.
            # (Previously returned a hardcoded "Thanks  -  noted" template  -  removed.)
            if self._is_user_name_declaration(user_text):
                logger.debug("Name declaration detected: %s", user_text[:80])

                # If the user previously stated a different name, record a contradiction entry.
                # NOTE: This is now redundant with ML-based detection above, but kept for
                # compatibility. The ML detector should catch name contradictions too.
                # Only run this if ML detection didn't already find a contradiction.
                if not contradiction_detected:
                    logger.debug("Name contradiction check starting (user_memory=%s)", user_memory is not None)
                    try:
                        new_facts = extract_fact_slots(user_text) or {}
                        new_name = new_facts.get("name")
                        logger.debug("Extracted name from query: %s", new_name)
                        if new_name is not None:
                            previous_user_memories = self._load_thread_user_memories(
                                thread_id=thread_id,
                                exclude_memory_id=user_memory.memory_id,
                            )
                            # Only record a new contradiction if the user asserts a NEW name
                            # (i.e., it does not match any prior user-stated name value).
                            # If the user re-asserts a previously-known name, treat it as
                            # reinforcement/clarification (and let conflict resolution handle it).
                            prior_same_exists = False
                            prior_names: List[MemoryItem] = []
                            for prev_mem in previous_user_memories:
                                if not is_explicit_name_declaration_text(prev_mem.text):
                                    continue
                                prev_facts = extract_fact_slots(prev_mem.text) or {}
                                prev_name = prev_facts.get("name")
                                if prev_name is None:
                                    continue
                                prev_norm = str(getattr(prev_name, "normalized", "") or "")
                                new_norm = str(getattr(new_name, "normalized", "") or "")

                                # Treat nickname/partial-name cases as the same identity signal
                                # (e.g., "Nick" vs "Nick Block") to avoid noisy conflicts.
                                same_or_prefix = (
                                    prev_norm == new_norm
                                    or (prev_norm and new_norm and prev_norm.startswith(new_norm))
                                    or (prev_norm and new_norm and new_norm.startswith(prev_norm))
                                )
                                if not same_or_prefix:
                                    prev_parts = [x for x in re.split(r"\s+", prev_norm) if x]
                                    new_parts = [x for x in re.split(r"\s+", new_norm) if x]
                                    if len(prev_parts) >= 2 and len(new_parts) >= 2:
                                        prev_first, prev_last = prev_parts[0], prev_parts[-1]
                                        new_first, new_last = new_parts[0], new_parts[-1]
                                        same_or_prefix = (
                                            prev_last == new_last
                                            and (prev_first.startswith(new_first) or new_first.startswith(prev_first))
                                        )

                                if same_or_prefix:
                                    prior_same_exists = True
                                else:
                                    prior_names.append(prev_mem)

                            if (not prior_same_exists) and prior_names:
                                logger.debug("Name contradiction detected between declarations")
                                selected_prev = max(
                                    prior_names,
                                    key=lambda m: (getattr(m, "timestamp", 0.0), getattr(m, "trust", 0.0)),
                                )
                                # Reuse existing embeddings from stored memories; do not invoke the embedder here.
                                user_vector = user_memory.vector
                                drift = self.crt_math.drift_meaning(user_vector, selected_prev.vector)
                                selected_prev_facts = extract_fact_slots(selected_prev.text) or {}
                                selected_prev_name = selected_prev_facts.get("name")
                                prev_name_value = getattr(selected_prev_name, "value", None) if selected_prev_name else None
                                logger.debug("Name contradiction: new='%s' vs old='%s', drift=%.3f", new_name.value, selected_prev.text[:60], drift)
                                
                                # Phase 1.1: Use CRTMath paraphrase check as final gate
                                is_real_contradiction, crt_reason = self.crt_math.detect_contradiction(
                                    drift=drift,
                                    confidence_new=0.95,
                                    confidence_prior=float(selected_prev.confidence),
                                    source=user_memory.source,
                                    text_new=user_text,
                                    text_prior=selected_prev.text,
                                    slot="name",
                                    value_new=str(getattr(new_name, "value", new_name)),
                                    value_prior=str(prev_name_value) if prev_name_value is not None else None,
                                )
                                if not is_real_contradiction:
                                    logger.info(f"[CRT_PARAPHRASE] Skipped name contradiction - {crt_reason}")
                                else:
                                    contradiction_entry = self._record_and_cascade(
                                        old_memory_id=selected_prev.memory_id,
                                        new_memory_id=user_memory.memory_id,
                                        drift_mean=drift,
                                        confidence_delta=float(selected_prev.confidence) - 0.95,
                                        query=user_text,
                                        summary=f"User name changed: {selected_prev.text[:50]}... vs {user_text[:50]}...",
                                        old_text=selected_prev.text,
                                        new_text=user_text,
                                        old_vector=selected_prev.vector,
                                        new_vector=user_vector,
                                        thread_id=thread_id,
                                    )
                                    logger.debug("Ledger recorded contradiction entry: %s", contradiction_entry)
                                    contradiction_detected = True
                    except Exception as e:
                            logger.debug("Name contradiction check exception: %s", e)
                            logger.warning(f"[CONTRADICTION_DETECTION] Name contradiction check failed: {e}")
                            # Don't override if ML already detected it
                            pass

                # Memory stored and contradiction checked above.
                # Fall through to reasoning engine for a natural response.
                logger.debug("Name declaration stored; falling through to reasoning engine.")

            # Non-name assertions that detected a contradiction: surface it conversationally.
            # Build a natural conflict disclosure and let the reasoning engine respond.
            if contradiction_detected:
                old_text = ""
                new_text = user_text
                if contradiction_entry is not None:
                    entry_dict = contradiction_entry.to_dict() if hasattr(contradiction_entry, 'to_dict') else {}
                    old_text = entry_dict.get('old_text', '') or ""
                    new_text = entry_dict.get('new_text', user_text) or user_text

                # Build a conflict context block and pass it through the reasoning engine
                # so the model can respond naturally instead of returning a canned string.
                conflict_ctx = (
                    f"\n[CONFLICT DETECTED]\n"
                    f"Previously stored: {old_text[:120] if old_text else '(unknown)'}\n"
                    f"Just stated: {new_text[:120]}\n"
                    f"Both have been preserved in the contradiction ledger.\n"
                    f"Ask the user naturally which version is current.\n"
                )
                # Inject the conflict context into the query so the reasoning engine sees it
                user_query_with_conflict = user_query + conflict_ctx
                try:
                    result = self.reasoning.reason(
                        query=user_query_with_conflict,
                        context={'retrieved_docs': []},
                        mode=ReasoningMode.QUICK,
                    )
                    answer = result.get('answer') if isinstance(result, dict) else str(result)
                except Exception as _re:
                    logger.warning(f"[CONFLICT_RESPONSE] Reasoning engine failed, using fallback: {_re}")
                    if old_text:
                        answer = (
                            f"Hold on  -  I had '{old_text[:80]}' stored, but you just said something different. "
                            f"Both are now on record. Which is current?"
                        )
                    else:
                        answer = (
                            "I noticed that conflicts with something I had stored. Both versions are now on record. "
                            "Which one should I go with?"
                        )
                disclosure_entry = contradiction_entry.to_dict() if contradiction_entry is not None and hasattr(contradiction_entry, "to_dict") else {}
                disclosed_memory_ids = [
                    str(disclosure_entry.get("old_memory_id") or "").strip(),
                    str(disclosure_entry.get("new_memory_id") or "").strip(),
                ]
                if user_memory is not None:
                    disclosed_memory_ids.append(user_memory.memory_id)
                self._record_memory_usage(
                    disclosed_memory_ids,
                    event_type="guard_blocked",
                    reason="contradiction_disclosure",
                    usage_trace_id=usage_trace_id,
                    query=user_query,
                    thread_id=thread_id,
                    metadata={
                        "gate_reason": "contradiction_disclosure",
                        "ledger_id": disclosure_entry.get("ledger_id"),
                    },
                )
                _dbg_slot = str(disclosure_entry.get('affects_slots') or '?')
                return {
                    'answer': answer,
                    'thinking': None,
                    'mode': 'quick',
                    'confidence': 0.9,
                    'response_type': 'belief',
                    # Surface assertion conflicts as an explicit disclosure gate, not a pass.
                    'gates_passed': False,
                    'gate_reason': 'contradiction_disclosure',
                    'intent_alignment': 0.9,
                    'memory_alignment': 0.9,
                    'contradiction_detected': True,
                    'contradiction_entry': (disclosure_entry if disclosure_entry else None),
                    'retrieved_memories': [],
                    'prompt_memories': [],
                    'unresolved_contradictions_total': 1,
                    'unresolved_hard_conflicts': 0,
                    'learned_suggestions': [],
                    'heuristic_suggestions': [],
                    'best_prior_trust': None,
                    'session_id': self.session_id,
                    'gate_debug': {
                        'trigger': 'contradiction_disclosure',
                        'slot': _dbg_slot,
                        'stored': (old_text[:300] if old_text else None),
                        'incoming': (new_text[:300] if new_text else None),
                        'ledger_id': disclosure_entry.get('ledger_id'),
                        'explanation': f"A stored fact about '{_dbg_slot}' conflicts with what you just said.",
                    },
                }

        # NOTE: Assistant-profile questions ("who are you?", "what are you?") are
        # NO LONGER intercepted here with a hardcoded response. Instead, the system's
        # self-knowledge is stored as GroundCheck memories (seeded on startup) so the
        # LLM can retrieve and explain its own architecture naturally, in context.
        # The _is_assistant_profile_question() and _build_assistant_profile_answer()
        # methods still exist for the name-ack combo path ("Hi I'm Nick. Who are you?")
        # but are not used as an early return gate in the main query flow.

        # ── PROVISIONAL → CONFIRMED promotion ──────────────────────────
        # If the user assertion passed contradiction detection without
        # triggering a conflict, promote it from provisional to confirmed.
        # This ensures it's available for future retrieval but was NOT
        # available during THIS turn's retrieval (preventing self-citation).
        if user_memory is not None and not contradiction_detected:
            _mem_id = user_memory.memory_id
            _current_auth = self.memory._normalize_authority(getattr(user_memory, "authority", None))
            if _current_auth == "provisional":
                try:
                    conn = self.memory._get_connection()
                    conn.execute(
                        "UPDATE memories SET authority = 'confirmed' WHERE memory_id = ?",
                        (_mem_id,)
                    )
                    conn.commit()
                    conn.close()
                    print(f"[PROVISIONAL] Promoted to confirmed: {_mem_id} (no contradiction detected)")
                except Exception as _promo_err:
                    print(f"[PROVISIONAL] ERROR promoting {_mem_id}: {_promo_err}")
            else:
                print(f"[PROVISIONAL] Skipped promotion: {_mem_id} already authority={_current_auth}")
        elif user_memory is not None and contradiction_detected:
            print(f"[PROVISIONAL] Keeping provisional: {user_memory.memory_id} (contradiction detected)")

        # 1. Trust-weighted retrieval
        # First pass to infer slots before retrieval (enables scope filtering)
        inferred_slots: List[str] = []
        if user_input_kind in ("question", "instruction"):
            inferred_slots = self._infer_slots_from_query(user_query)
            logger.info(f"[PROFILE_DEBUG] Inferred slots from query: {inferred_slots}")

            # Name-history queries: inject the name data as context so the model
            # can explain it naturally instead of returning a template.
            if self._is_name_history_request(user_text):
                name_history = self._answer_from_fact_slots(
                    ["name"],
                    user_query=user_text,
                    thread_id=thread_id,
                    usage_trace_id=usage_trace_id,
                    usage_reason="name_history_lookup",
                )
                if name_history:
                    extra_context["name_history"] = (
                        f"\n[NAME HISTORY DATA]\n{name_history}\n"
                        f"Use this data to answer the user's question naturally.\n"
                    )
        
        # Parse any explicit first-person fact assertions (used for relevance checks).
        # For most questions this will be empty, which is fine.
        asserted_facts = extract_fact_slots(user_text) or {}

        # Compute relevant slots for contradiction filtering
        relevant_slots_set = set(inferred_slots or []) | set((asserted_facts or {}).keys())

        # Detect provenance / meta-questions — these should BYPASS contradiction gates
        # because the user is asking HOW we know, not WHAT we know.
        _provenance_meta_cues = ("how do you know", "why do you think", "where did you learn",
                                 "when did i tell", "how are you sure", "what makes you think",
                                 "how did you learn", "how do you remember", "how does your",
                                 "how do you work", "who are you", "what are you",
                                 "how does that work", "explain your process", "explain how")
        _is_provenance_or_meta = any(cue in user_text.lower() for cue in _provenance_meta_cues)

        # BUG 2 FIX: Check for unresolved contradictions (gate blocking)
        if _is_provenance_or_meta:
            # Provenance / meta queries should never be blocked by contradiction gates.
            gates_passed = True
            clarification_message = None
            blocking_contradictions = []
            logger.info("[GATE_BYPASS] Provenance/meta query -- skipping contradiction gates")
        else:
            gates_passed, clarification_message, blocking_contradictions = self._check_contradiction_gates(
                user_text,
                inferred_slots,
                user_input_kind=user_input_kind,
            )
        
        # Handle resolved contradictions — inject context so model responds naturally
        if gates_passed and clarification_message:
            logger.info(f"[GATE_RESOLVED] Contradiction resolved with caveat: {clarification_message}")
            extra_context["contradiction_resolved"] = (
                f"\n[CONTRADICTION RESOLVED]\n"
                f"A previous conflict in the user's facts was resolved.\n"
                f"Resolved answer: {clarification_message}\n"
                f"Mention the resolution naturally — don't use parenthetical caveats.\n"
            )
            contradiction_detected = True

        if not gates_passed and clarification_message:
            logger.info(f"[GATE_BLOCK] Response blocked due to {len(blocking_contradictions)} contradictions")
            blocked_memory_ids: List[str] = []
            for bc in blocking_contradictions:
                blocked_memory_ids.extend([
                    str(bc.get("old_memory_id") or "").strip(),
                    str(bc.get("new_memory_id") or "").strip(),
                ])
            self._record_memory_usage(
                blocked_memory_ids,
                event_type="guard_blocked",
                reason="contradiction_gate_block",
                usage_trace_id=usage_trace_id,
                query=user_query,
                thread_id=thread_id,
                metadata={
                    "gate_reason": "contradiction_gate_block",
                    "slots": sorted(relevant_slots_set) if relevant_slots_set else [],
                    "blocking_contradictions": [
                        {
                            "ledger_id": bc.get("ledger_id"),
                            "slot": bc.get("slot"),
                        }
                        for bc in blocking_contradictions
                    ],
                },
            )
            # Build conflict details for the model
            conflict_details = []
            for bc in blocking_contradictions[:3]:
                conflict_details.append(
                    f"- {bc.get('slot', '?')}: \"{bc.get('old_value', '')[:80]}\" vs \"{bc.get('new_value', '')[:80]}\""
                )
            extra_context["contradiction_blocked"] = (
                f"\n[UNRESOLVED CONFLICT — MUST ADDRESS]\n"
                f"You have conflicting information and cannot give a confident answer.\n"
                f"Conflicts:\n" + "\n".join(conflict_details) + "\n"
                f"Ask the user which is current. Be natural about it.\n"
            )
            contradiction_detected = True
        
        # Meta-queries about the system ("how does CRT work?", "how does this work?")
        # are handled by the system prompt in reasoning.py — no hardcoded explanation needed.
        # The model draws from architecture memories and the HOW YOU WORK section.
        
        # Sprint 9: classify synthesis subtype for worldview / trajectory / contradiction queries
        from ..belief_synthesis import classify_synthesis_query as _classify_synthesis
        _synthesis_type = _classify_synthesis(user_query)
        is_synthesis = _synthesis_type is not None
        # Thematic needs broadest retrieval (k=30); other synthesis k=15; default k=5
        retrieval_k = 30 if _synthesis_type == "thematic" else 15 if is_synthesis else 5

        # Copilot GroundCheck context bridge  -  fetch MCP memories when asked
        _is_copilot_query = self._is_copilot_context_query(user_query)
        _copilot_context: List[Dict[str, Any]] = []
        if _is_copilot_query:
            _copilot_context = self._fetch_copilot_context(user_query)
            logger.info("[COPILOT_CTX] Detected copilot query, fetched %d MCP memories", len(_copilot_context))

        # Web search bridge  -  run DuckDuckGo search for real-time information
        _is_search_query = self._is_web_search_query(user_query)
        _web_search_query = ""
        _web_search_results: List[Dict[str, Any]] = []
        _web_evidence_packet: Optional[Dict[str, Any]] = None
        _is_direct_url_fetch = False
        if _is_search_query:
            _web_search_query = self._extract_search_query(user_query)
            _is_direct_url_fetch = bool(self._URL_RE.search(_web_search_query))
            _web_search_results = self._run_web_search(_web_search_query)
            _web_evidence_packet = self._build_web_evidence_packet(_web_search_query, _web_search_results)
            evidence_citations = (_web_evidence_packet or {}).get("citations") or []
            logger.info(
                "[WEB_SEARCH] Detected search query, got %d results / %d citations for '%s' (direct_url=%s)",
                len(_web_search_results),
                len(evidence_citations),
                _web_search_query,
                _is_direct_url_fetch,
            )
            # Only gate on zero citations for DuckDuckGo searches, not direct URL fetches.
            # For URL fetches the raw content is still passed to the LLM even without formal citations.
            if len(evidence_citations) == 0 and not _is_direct_url_fetch:
                return {
                    'answer': self._format_web_fetch_failed_answer(_web_search_query),
                    'thinking': None,
                    'mode': 'quick',
                    'confidence': 0.0,
                    'response_type': 'speech',
                    'gates_passed': False,
                    'gate_reason': 'web_fetch_failed',
                    'intent_alignment': 0.0,
                    'memory_alignment': 0.0,
                    'contradiction_detected': False,
                    'contradiction_entry': None,
                    'retrieved_memories': [],
                    'prompt_memories': [],
                    'learned_suggestions': [],
                    'heuristic_suggestions': [],
                    'best_prior_trust': None,
                    'web_search_results': _web_search_results,
                    'web_evidence_packet': _web_evidence_packet,
                    'session_id': self.session_id,
                }

        # Intent routing: detect general-knowledge queries that don't need memory
        _user_relationship_query = bool(re.search(
            r"\bwho\s+is\s+\w[\w\s]{0,30}\bto\s+you\b"   # "who is Nick Block to you"
            r"|who\s+is\s+(the\s+)?user\b"                # "who is the user"
            r"|who\s+am\s+i\s+to\s+you\b",                # "who am i to you"
            user_text, re.IGNORECASE,
        ))
        _is_general_knowledge = (
            not inferred_slots
            and not asserted_facts
            and user_input_kind == "question"
            and not _is_provenance_or_meta
            and not _is_copilot_query
            and not _is_search_query
            and not _user_relationship_query
            and not any(p in user_text.lower() for p in (
                "my ", "i am", "i'm", "i have", "i live", "i work",
                "do you remember", "do you know my", "what's my",
                "what is my", "who am i",
                "what do you know about me",
                "to you", "about you", "for you",
            ))
        )
        if _is_general_knowledge:
            logger.info("[INTENT_ROUTE] General knowledge query — memory retrieval is supplementary")

        # Include SYSTEM-source memories when the query is about the system itself
        # (e.g., "who are you?", "how do you know?", "how does your memory work?").
        # This ensures self-knowledge stored as SYSTEM memories gets retrieved.
        _ql_for_sys = user_query.lower()
        _is_self_referential = any(p in _ql_for_sys for p in (
            "who are you", "what are you", "how do you", "how does your",
            "your memory", "your architecture", "how you work",
            "how are you sure", "how did you know", "your process",
            "do you remember", "do you know", "how do you know",
            "what do you do", "tell me about yourself",
            "where do you work", "who do you work for",
            "how does that work", "your system", "your tools",
            "what is your name", "what's your name", "your name",
            "important to you", "matter to you", "care about",
            "what do you value", "what do you think", "your opinion",
            "your favorite", "your preference", "do you like",
            "do you feel", "how do you feel", "what do you want",
            "your purpose", "your goal", "your mission",
            "what makes you", "what drives you", "your personality",
            "your identity", "what are you like", "describe yourself",
            "your beliefs", "your values", "your principles",
            "to you",
            # Creator/builder queries — ensure system retrieves builder context
            "who made you", "who built you", "who created you",
            "who develops you", "who is building", "who designed you",
            "made by", "built by", "created by", "developed by",
            "your creator", "your developer", "your builder",
        ))
        
        # ── Context-aware query expansion for short corrections ──
        # When the user says "No it is not" or "That's wrong" or "Actually...",
        # the query has no semantic content for retrieval. We expand it with
        # the topic from the previous turn so retrieval finds relevant memories.
        _retrieval_query = user_query
        _SHORT_CORRECTION_WORDS = {"no", "not", "wrong", "nope", "actually", "incorrect", "false"}
        _query_words = set(user_text.lower().split())
        if len(_query_words) <= 8 and _query_words & _SHORT_CORRECTION_WORDS:
            # This looks like a short correction/negation - expand with conversation context
            if conversation_history and len(conversation_history) >= 2:
                # Find the last assistant message to get the topic
                for _prev_msg in reversed(conversation_history[:-1]):
                    if _prev_msg.get("role") == "assistant":
                        _prev_text = str(_prev_msg.get("content", ""))[:200]
                        if _prev_text:
                            _retrieval_query = f"{_prev_text} {user_query}"
                            logger.info(
                                "[QUERY_EXPAND] Short correction detected, expanded retrieval query with prior context"
                            )
                        break

        _t_retrieve = time.perf_counter()
        try:
            retrieved = self.retrieve(
                _retrieval_query,
                k=retrieval_k,
                relevant_slots=relevant_slots_set if relevant_slots_set else None,
                include_system=_is_self_referential,
                thread_id=thread_id,
                usage_trace_id=usage_trace_id,
                usage_reason="query_retrieve",
                usage_metadata={
                    "user_input_kind": user_input_kind,
                    "relevant_slots": sorted(relevant_slots_set) if relevant_slots_set else [],
                },
            )
        except TypeError:
            # Backward-compatible fallback for tests that monkeypatch retrieve with
            # older call signatures that don't accept newer kwargs.
            retrieved = self.retrieve(
                _retrieval_query,
                k=retrieval_k,
                include_system=_is_self_referential,
            )
        
        _retrieval_latency = (time.perf_counter() - _t_retrieve) * 1000
        print(f"[PIPELINE_TIMING] retrieval={_retrieval_latency:.1f}ms k={retrieval_k} results={len(retrieved)}")

        # ── ACTIVATION LOGGING: record retrieval pattern for analytics ──
        try:
            from personal_agent.activation_log import (
                log_activation, ActivationRecord, make_query_hash,
            )
            _act_record = ActivationRecord(
                activation_id=f"act_{int(time.time()*1000)}_{id(retrieved) % 10000}",
                timestamp=time.time(),
                thread_id=thread_id or "",
                query=user_text[:500],
                query_hash=make_query_hash(user_text),
                memory_ids=[m.memory_id for m, _ in retrieved],
                scores=[round(s, 4) for _, s in retrieved],
                trusts=[round(m.trust, 3) for m, _ in retrieved],
                kinds=[str(getattr(m, "kind", "") or "") for m, _ in retrieved],
            )
            log_activation(str(self.memory.db_path), _act_record)
        except Exception as _act_err:
            logger.debug(f"[ACTIVATION_LOG] Failed: {_act_err}")

        # Turn-awareness: inject retrieval metadata so the LLM can explain
        # what it did when asked about its process.
        if retrieved:
            _top_mem = retrieved[0][0]
            try:
                _mem_count = self.memory.count_memories()
            except Exception:
                _mem_count = -1
            extra_context["turn_awareness"] = (
                f"\n[TURN CONTEXT -- INTERNAL, do NOT share these details unless the user asks about your process]\n"
                f"You searched {_mem_count} stored memories for this query.\n"
                f"Top match: \"{_top_mem.text[:100]}\" (trust={_top_mem.trust:.2f})\n"
                f"Retrieved {len(retrieved)} relevant memories total.\n"
                f"DO NOT mention trust scores, similarity scores, or memory counts in your response "
                f"unless the user specifically asks how you know something or about your process.\n"
            )

        # Check for sentiment contradictions in retrieved memories
        sentiment_contradiction = self._detect_sentiment_contradiction(user_query, retrieved)
        if sentiment_contradiction:
            self.memory.store_memory(
                text=sentiment_contradiction,
                confidence=0.7,
                source=MemorySource.SYSTEM,
                context={"query": user_query, "type": "speech", "kind": "sentiment_contradiction"},
                user_marked_important=False,
                thread_id=thread_id,
            )
            
            return {
                'answer': sentiment_contradiction,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.75,
                'response_type': 'speech',
                'gates_passed': True,
                'gate_reason': 'sentiment_contradiction_detected',
                'intent_alignment': 0.85,
                'memory_alignment': 0.9,
                'contradiction_detected': True,
                'contradiction_entry': None,
                'retrieved_memories': [
                    {
                        'text': mem.text,
                        'trust': mem.trust,
                        'confidence': mem.confidence,
                        'source': mem.source.value,
                        'sse_mode': mem.sse_mode.value,
                        'score': score,
                    }
                    for mem, score in retrieved[:5]
                ],
                'prompt_memories': [],
                'learned_suggestions': [],
                'heuristic_suggestions': [],
                'best_prior_trust': retrieved[0][0].trust if retrieved else None,
                'session_id': self.session_id,
            }

        # Special-case: prompts that explicitly demand chat-grounded recall or memory citation.
        # We answer deterministically from retrieved/prompt memory text to avoid hallucinations
        # and to avoid claiming "no memories" when context exists.
        if user_input_kind in ("question", "instruction") and self._is_memory_citation_request(user_text):
            prompt_docs = self._build_resolved_memory_docs(
                retrieved,
                max_fact_lines=8,
                max_fallback_lines=2,
                query=user_query,
                thread_id=thread_id,
                usage_trace_id=usage_trace_id,
                usage_reason="memory_citation_prompt",
            )
            candidate_output = self._build_memory_citation_answer(
                user_query=user_query,
                retrieved=retrieved,
                prompt_docs=prompt_docs,
            )

            # Keep this as non-durable "speech" to avoid polluting the belief store.
            self.memory.store_memory(
                text=candidate_output,
                confidence=0.25,
                source=MemorySource.FALLBACK,
                context={"query": user_query, "type": "speech", "kind": "memory_citation"},
                user_marked_important=False,
                thread_id=thread_id,
            )

            best_prior = retrieved[0][0] if retrieved else None

            return {
                'answer': candidate_output,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.8,
                'response_type': 'speech',
                'gates_passed': False,
                'gate_reason': 'memory_citation',
                'intent_alignment': 0.9,
                'memory_alignment': 1.0,
                'contradiction_detected': False,
                'contradiction_entry': None,
                'retrieved_memories': [
                    {
                        'text': mem.text,
                        'trust': mem.trust,
                        'confidence': mem.confidence,
                        'source': mem.source.value,
                        'sse_mode': mem.sse_mode.value,
                        'score': score,
                    }
                    for mem, score in retrieved
                ],
                'prompt_memories': [
                    {
                        'text': d['text'],
                        'trust': d['trust'],
                        'source': d['source']
                    }
                    for d in (prompt_docs or [])
                ],
                'best_prior_trust': best_prior.trust if best_prior else None,
                'session_id': self.session_id,
            }
        
        # Special-case: synthesis queries that need to combine multiple facts
        # These get broader retrieval and should cite/combine all relevant memories
        if user_input_kind in ("question", "instruction") and is_synthesis:
            # Keep slot-specific synthesis grounded in canonical slot memories/profile
            # (e.g., "What do you remember about my employer?").
            if inferred_slots:
                retrieved = self._augment_retrieval_with_slot_memories(
                    retrieved,
                    inferred_slots,
                    thread_id=thread_id,
                )

            # Sprint 9: deep synthesis for worldview / trajectory / contradiction queries
            if _synthesis_type in ("thematic", "trajectory", "contradiction_aware"):
                from ..belief_synthesis import synthesize as _belief_synthesize
                from ..cloud_features import get_cloud_feature_service
                from ..local_only_policy import is_strict_local_only_mode

                # Load ALL user memories for clustering (not just retrieved subset)
                try:
                    _all_mems = [
                        m for m in self.memory._load_all_memories()
                        if getattr(m, "source", None) in (MemorySource.USER, MemorySource.EXTERNAL)
                        and not getattr(m, "deprecated", False)
                    ]
                except Exception:
                    _all_mems = [m for m, _s in retrieved]

                _cloud = None if is_strict_local_only_mode(uid=1) else get_cloud_feature_service()
                _synth_result = _belief_synthesize(
                    query=user_query,
                    memories=_all_mems,
                    ledger=self.ledger,
                    cloud_service=_cloud,
                    thread_id=thread_id,
                )
                candidate_output = _synth_result.summary_text
                logger.info(
                    "[SYNTHESIS] type=%s clusters=%d trajectories=%d tensions=%d repr=%.2f",
                    _synth_result.synthesis_type,
                    len(_synth_result.clusters),
                    len(_synth_result.trajectories),
                    len(_synth_result.unresolved_tensions),
                    _synth_result.representativeness,
                )
            else:
                # Legacy slot-specific synthesis (backward compatible)
                candidate_output = self._build_synthesis_answer(
                    user_query=user_query,
                    retrieved=retrieved,
                    thread_id=thread_id,
                )

            # Synthesis answers cite facts directly, so they should pass gates
            self.memory.store_memory(
                text=candidate_output,
                confidence=0.8,
                source=MemorySource.SYSTEM,
                context={"query": user_query, "type": "belief", "kind": "synthesis"},
                user_marked_important=False,
                thread_id=thread_id,
            )

            best_prior = retrieved[0][0] if retrieved else None

            _synth_meta = {}
            if _synthesis_type in ("thematic", "trajectory", "contradiction_aware"):
                _synth_meta = {
                    "synthesis_type": _synth_result.synthesis_type,
                    "representativeness": _synth_result.representativeness,
                    "cluster_count": len(_synth_result.clusters),
                    "trajectory_count": len(_synth_result.trajectories),
                    "tension_count": len(_synth_result.unresolved_tensions),
                    "evidence_count": _synth_result.evidence_count,
                }

            return {
                'answer': candidate_output,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.85,
                'response_type': 'belief',
                'gates_passed': True,
                'gate_reason': 'synthesis_grounded_in_memory',
                'intent_alignment': 0.9,
                'memory_alignment': 0.95,
                'contradiction_detected': False,
                'contradiction_entry': None,
                'retrieved_memories': [
                    {
                        'text': mem.text,
                        'trust': mem.trust,
                        'confidence': mem.confidence,
                        'source': mem.source.value,
                        'sse_mode': mem.sse_mode.value,
                        'score': score,
                    }
                    for mem, score in retrieved
                ],
                'prompt_memories': [],
                'learned_suggestions': [],
                'heuristic_suggestions': [],
                'best_prior_trust': best_prior.trust if best_prior else None,
                'session_id': self.session_id,
                'synthesis_meta': _synth_meta,
            }

        # Special-case: user asks to list/dump memories or memory ids.
        # Never invent internal identifiers; respond deterministically with safe citations.
        if user_input_kind in ("question", "instruction") and self._is_memory_inventory_request(user_text):
            prompt_docs = self._build_resolved_memory_docs(
                retrieved,
                max_fact_lines=8,
                max_fallback_lines=2,
                query=user_query,
                thread_id=thread_id,
                usage_trace_id=usage_trace_id,
                usage_reason="memory_inventory_prompt",
            )
            candidate_output = self._build_memory_inventory_answer(
                user_query=user_query,
                retrieved=retrieved,
                prompt_docs=prompt_docs,
            )

            self.memory.store_memory(
                text=candidate_output,
                confidence=0.25,
                source=MemorySource.FALLBACK,
                context={"query": user_query, "type": "speech", "kind": "memory_inventory"},
                user_marked_important=False,
                thread_id=thread_id,
            )

            best_prior = retrieved[0][0] if retrieved else None
            return {
                'answer': candidate_output,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.8,
                'response_type': 'speech',
                'gates_passed': False,
                'gate_reason': 'memory_inventory',
                'intent_alignment': 0.9,
                'memory_alignment': 1.0,
                'contradiction_detected': False,
                'contradiction_entry': None,
                'retrieved_memories': [
                    {
                        'text': mem.text,
                        'trust': mem.trust,
                        'confidence': mem.confidence,
                        'source': mem.source.value,
                        'sse_mode': mem.sse_mode.value,
                        'score': score,
                    }
                    for mem, score in retrieved
                ],
                'prompt_memories': [
                    {
                        'text': d.get('text'),
                        'trust': d.get('trust'),
                        'confidence': d.get('confidence'),
                        'source': d.get('source'),
                    }
                    for d in prompt_docs
                ],
                'learned_suggestions': [],
                'heuristic_suggestions': [],
                'best_prior_trust': best_prior.trust if best_prior else None,
                'session_id': self.session_id,
            }

        # Special-case: user asks for contradiction ledger status.
        # Answer deterministically from the ledger to prevent invented contradictions.
        if user_input_kind in ("question", "instruction") and self._is_contradiction_status_request(user_text):
            prompt_docs = self._build_resolved_memory_docs(
                retrieved,
                max_fact_lines=8,
                max_fallback_lines=0,
                query=user_query,
                thread_id=thread_id,
                usage_trace_id=usage_trace_id,
                usage_reason="contradiction_status_prompt",
            )
            candidate_output, contra_meta = self._build_contradiction_status_answer(
                user_query=user_query,
                inferred_slots=inferred_slots,
            )

            # Do not append provenance footers into the answer text.
            final_answer = candidate_output

            # Keep as non-durable speech.
            self.memory.store_memory(
                text=candidate_output,
                confidence=0.25,
                source=MemorySource.FALLBACK,
                context={"query": user_query, "type": "speech", "kind": "contradiction_status"},
                user_marked_important=False,
                thread_id=thread_id,
            )

            best_prior = retrieved[0][0] if retrieved else None
            return {
                'answer': final_answer,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.8,
                'response_type': 'speech',
                'gates_passed': False,
                'gate_reason': 'contradiction_status',
                'intent_alignment': 0.9,
                'memory_alignment': 1.0,
                'contradiction_detected': False,
                'contradiction_entry': None,
                'retrieved_memories': [
                    {
                        'text': mem.text,
                        'trust': mem.trust,
                        'confidence': mem.confidence,
                        'source': mem.source.value,
                        'sse_mode': mem.sse_mode.value,
                        'score': score,
                    }
                    for mem, score in retrieved
                ],
                'prompt_memories': [
                    {
                        'text': d.get('text'),
                        'trust': d.get('trust'),
                        'confidence': d.get('confidence'),
                        'source': d.get('source'),
                    }
                    for d in prompt_docs
                ],
                'unresolved_contradictions_total': int(contra_meta.get('unresolved_contradictions_total', 0) or 0),
                'unresolved_hard_conflicts': int(contra_meta.get('unresolved_hard_conflicts', 0) or 0),
                'learned_suggestions': [],
                'heuristic_suggestions': [],
                'best_prior_trust': best_prior.trust if best_prior else None,
                'session_id': self.session_id,
            }

        # Assistant-profile questions at this stage are handled by the system prompt.
        # No second early-return needed — the model identity block covers this.

        user_named_cfg = (self.runtime_config.get("user_named_reference") or {}) if isinstance(self.runtime_config, dict) else {}
        user_named_enabled = bool(user_named_cfg.get("enabled", True))
        if user_named_enabled and user_input_kind in ("question", "instruction") and self._is_user_named_reference_question(user_text):
            # Infer likely slots from the query (title/employer are common).
            inferred = inferred_slots or self._infer_slots_from_query(user_text)
            relevant_slots = [s for s in inferred if s in {"title", "employer"}]
            if not relevant_slots:
                # Still treat as high-risk; attempt to answer from work snippets.
                relevant_slots = ["title", "employer"]

            answer = self._build_user_named_reference_answer(user_text, relevant_slots)

            # Do not append provenance footers into the answer text.
            final_answer = answer

            return {
                'answer': final_answer,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.9,
                'response_type': 'speech',
                'gates_passed': False,
                'gate_reason': 'user_named_reference',
                'intent_alignment': 0.9,
                'memory_alignment': 1.0,
                'contradiction_detected': False,
                'contradiction_entry': None,
                'retrieved_memories': [],
                'prompt_memories': [],
                'unresolved_contradictions_total': 0,
                'unresolved_hard_conflicts': 0,
                'learned_suggestions': [],
                'heuristic_suggestions': [],
                'best_prior_trust': None,
                'session_id': self.session_id,
            }

        # Slot-aware question augmentation: for simple fact questions, semantic retrieval
        # can miss the most recent correction (e.g., Amazon vs Microsoft). If the query
        # looks like it targets a known slot, explicitly pull the best candidate memory
        # for that slot from the full store and merge it into retrieved.
        # CRITICAL: Do this even if retrieved is empty - profile facts should be available!
        if user_input_kind in ("question", "instruction") and inferred_slots:
            logger.info(f"[PROFILE_DEBUG] Augmenting retrieval with slot memories for slots: {inferred_slots} (current retrieved count: {len(retrieved)})")
            retrieved = self._augment_retrieval_with_slot_memories(
                retrieved,
                inferred_slots,
                thread_id=thread_id,
            )
            retrieved = self._filter_non_authoritative_slot_claims(retrieved, inferred_slots)
            logger.info(f"[PROFILE_DEBUG] After augmentation, retrieved count: {len(retrieved)}")

        # M2: If the user is asking about a slot with an OPEN hard CONFLICT, do not silently
        # pick the "most recent" value. Turn the contradiction into an explicit next action.
        contradiction_goals: List[Dict[str, Any]] = []
        conflict_beliefs: Optional[List[str]] = None
        recommended_next_action: Optional[Dict[str, Any]] = None
        if user_input_kind in ("question", "instruction") and inferred_slots:
            contradiction_goals, conflict_beliefs = self._infer_contradiction_goals_for_query(
                user_query=user_query,
                retrieved=retrieved,
                inferred_slots=inferred_slots,
            )
            if contradiction_goals:
                recommended_next_action = contradiction_goals[0]
                # Inject conflict details as context for the model to explain naturally
                beliefs_text = "\n".join(conflict_beliefs[:6]) if conflict_beliefs else "(no conflicting beliefs found)"
                ask_text = ""
                if recommended_next_action and recommended_next_action.get("action_type") == "ask_user":
                    ask_text = recommended_next_action.get("question", "")
                extra_context["unresolved_conflict"] = (
                    f"\n[UNRESOLVED CONFLICT — AFFECTS THIS QUESTION]\n"
                    f"You have conflicting information relevant to the user's question.\n"
                    f"Conflicting beliefs:\n{beliefs_text}\n"
                    + (f"Suggested clarification: {ask_text}\n" if ask_text else "")
                    + f"Acknowledge the conflict honestly and ask the user to clarify.\n"
                )
                contradiction_detected = True

        # Slot-based fast-path: if the user asks a simple personal-fact question and we have
        # an answer in memory, answer directly from canonical resolved facts.
        # BUT: if the user is asking HOW/WHY we know (meta-question about our process),
        # skip the fast-path and let the LLM explain the retrieval mechanism.
        _ql = user_query.lower()
        _is_meta_question = any(phrase in _ql for phrase in (
            "how do you know",
            "how are you sure",
            "how can you be sure",
            "how did you know",
            "how do you remember",
            "where did you learn",
            "how did you learn",
            "explain your process",
            "explain the technical",
            "how does your memory",
            "how does that work",
            "how do you have that",
            "what makes you sure",
            "why are you sure",
            "why do you think",
        ))
        if user_input_kind in ("question", "instruction") and inferred_slots and not _is_meta_question and not _is_search_query and not _is_provenance_or_meta:
            slot_answer = self._answer_from_fact_slots(
                inferred_slots,
                user_query=user_query,
                thread_id=thread_id,
                usage_trace_id=usage_trace_id,
                usage_reason="fact_slot_fast_path",
            )
            if slot_answer is not None:
                # Inject slot data as context so the LLM renders it naturally
                # instead of returning raw "slot: value" strings directly.
                extra_context["fact_slot_data"] = (
                    f"\n[RESOLVED FACT DATA]\n"
                    f"You looked up the USER's stored facts and found:\n{slot_answer}\n"
                    f"Answer the user's question naturally using this data. "
                    f"Do NOT repeat the raw slot format -- just state the answer conversationally. "
                    f"Use SECOND PERSON: say 'Your name is X', NOT 'My name is X' or 'I'm X'. "
                    f"These are facts ABOUT THE USER, not about you.\n"
                )
                logger.info(f"[SLOT_INJECT] Injected slot data as context: {slot_answer[:80]}")

            # Summary-style instructions: answer from canonical resolved USER facts.
            if user_input_kind == "instruction":
                lower = (user_query or "").strip().lower()
                
                # Handler for "list N facts" queries - FACT-CONSTRAINED, no LLM hallucination
                if re.search(r"\blist\s+\d+\s+facts?\b", lower) or "facts you're confident" in lower or "facts you know" in lower:
                    fact_list = self._list_confident_facts_from_slots()
                    if fact_list is not None:
                        if not retrieved:
                            retrieved = self.retrieve(
                                user_query,
                                k=5,
                                thread_id=thread_id,
                                usage_trace_id=usage_trace_id,
                                usage_reason="instruction_fact_list_retrieve",
                            )
                        prompt_docs = self._build_resolved_memory_docs(
                            retrieved,
                            max_fallback_lines=0,
                            query=user_query,
                            thread_id=thread_id,
                            usage_trace_id=usage_trace_id,
                            usage_reason="instruction_fact_list_prompt",
                        )

                        candidate_output = fact_list
                        candidate_vector = encode_vector(candidate_output)

                        intent_align = 0.95
                        memory_align = self.crt_math.memory_alignment(output_vector=candidate_vector, retrieved_memories=[{'vector': mem.vector, 'text': mem.text} for mem, _ in retrieved], retrieval_scores=[score for _, score in retrieved], output_text=candidate_output)

                        # Predict response type and compute grounding
                        response_type_pred = self._classify_query_type_heuristic(user_query) or "unknown"
                        
                        grounding_score = self._compute_grounding_score(candidate_output, retrieved)
                        open_contradictions = self.ledger.get_open_contradictions()
                        query_slots = set(extract_fact_slots(user_query).keys())
                        contradiction_severity = self._classify_contradiction_severity(
                            open_contradictions, query_slots
                        )

                        gates_passed, gate_reason = self.crt_math.check_reconstruction_gates_v2(
                            intent_align=intent_align,
                            memory_align=memory_align,
                            response_type=response_type_pred,
                            grounding_score=grounding_score,
                            contradiction_severity=contradiction_severity,
                            blindspot_gate_boost=_blindspot_gate_boost,
                        )

                        # Upgrade #3: Unified gate (supplementary signal, logged alongside v2 gates)
                        try:
                            _unified_relevance = (intent_align + memory_align + grounding_score) / 3.0
                            _unified_drift = getattr(self, '_last_drift', 0.0)
                            _unified_depth = len(retrieved) if retrieved else 0
                            self.crt_math.unified_gate(_unified_relevance, _unified_drift, _unified_depth)
                        except Exception:
                            pass

                        # Log gate event
                        if self.active_learning:
                            try:
                                self.active_learning.record_gate_event(
                                    question=user_query,
                                    response_type_predicted=response_type_pred,
                                    intent_align=intent_align,
                                    memory_align=memory_align,
                                    grounding_score=grounding_score,
                                    gates_passed=gates_passed,
                                    gate_reason=gate_reason,
                                    thread_id="default",
                                    session_id=self.session_id,
                                )
                            except Exception as e:
                                log_swallowed_exception("crt_rag.query.active_learning.list_facts", e)

                        response_type = "belief" if gates_passed else "speech"
                        source = MemorySource.SYSTEM if gates_passed else MemorySource.FALLBACK
                        confidence = 0.95 if gates_passed else 0.95 * 0.7

                        best_prior = retrieved[0][0] if retrieved else None

                        self.memory.store_memory(
                            text=candidate_output,
                            confidence=confidence,
                            source=source,
                            context={'query': user_query, 'type': response_type, 'kind': 'fact_list'},
                            user_marked_important=False,
                            thread_id=thread_id,
                        )

                        learned = self._get_learned_suggestions_for_slots(
                            [
                                "name",
                                "employer",
                                "title",
                                "location",
                                "programming_years",
                                "first_language",
                                "masters_school",
                                "team_size",
                                "remote_preference",
                            ]
                        )

                        return {
                            'answer': candidate_output,
                            'thinking': None,
                            'mode': 'quick',
                            'confidence': confidence,
                            'response_type': response_type,
                            'gates_passed': gates_passed,
                            'gate_reason': gate_reason,
                            'intent_alignment': intent_align,
                            'memory_alignment': memory_align,
                            'contradiction_detected': False,
                            'contradiction_entry': None,
                            'retrieved_memories': [
                                {
                                    'text': mem.text,
                                    'trust': mem.trust,
                                    'confidence': mem.confidence,
                                    'source': mem.source.value,
                                    'sse_mode': mem.sse_mode.value,
                                    'score': score,
                                }
                                for mem, score in retrieved
                            ],
                            'prompt_memories': [
                                {
                                    'text': d.get('text'),
                                    'trust': d.get('trust'),
                                    'confidence': d.get('confidence'),
                                    'source': d.get('source'),
                                }
                                for d in prompt_docs
                            ],
                            'learned_suggestions': learned,
                            'heuristic_suggestions': self._get_heuristic_suggestions_for_slots(
                                [
                                    "name",
                                    "employer",
                                    "title",
                                    "location",
                                    "programming_years",
                                    "first_language",
                                    "masters_school",
                                    "team_size",
                                    "remote_preference",
                                ]
                            ),
                            'best_prior_trust': best_prior.trust if best_prior else None,
                            'session_id': self.session_id,
                        }
                
                if "summar" in lower or "one-line" in lower or "one line" in lower or "summary" in lower:
                    summary = self._one_line_summary_from_facts()
                    if summary is not None:
                        if not retrieved:
                            retrieved = self.retrieve(
                                user_query,
                                k=5,
                                thread_id=thread_id,
                                usage_trace_id=usage_trace_id,
                                usage_reason="instruction_summary_retrieve",
                            )
                        prompt_docs = self._build_resolved_memory_docs(
                            retrieved,
                            max_fallback_lines=0,
                            query=user_query,
                            thread_id=thread_id,
                            usage_trace_id=usage_trace_id,
                            usage_reason="instruction_summary_prompt",
                        )

                        candidate_output = summary
                        candidate_vector = encode_vector(candidate_output)

                        intent_align = 0.95
                        memory_align = self.crt_math.memory_alignment(output_vector=candidate_vector, retrieved_memories=[{'vector': mem.vector, 'text': mem.text} for mem, _ in retrieved], retrieval_scores=[score for _, score in retrieved], output_text=candidate_output)

                        # Predict response type and compute grounding
                        response_type_pred = self._classify_query_type_heuristic(user_query) or "unknown"
                        
                        grounding_score = self._compute_grounding_score(candidate_output, retrieved)
                        open_contradictions = self.ledger.get_open_contradictions()
                        query_slots = set(extract_fact_slots(user_query).keys())
                        contradiction_severity = self._classify_contradiction_severity(
                            open_contradictions, query_slots
                        )

                        gates_passed, gate_reason = self.crt_math.check_reconstruction_gates_v2(
                            intent_align=intent_align,
                            memory_align=memory_align,
                            response_type=response_type_pred,
                            grounding_score=grounding_score,
                            contradiction_severity=contradiction_severity,
                            blindspot_gate_boost=_blindspot_gate_boost,
                        )

                        # Upgrade #3: Unified gate (supplementary signal, logged alongside v2 gates)
                        try:
                            _unified_relevance = (intent_align + memory_align + grounding_score) / 3.0
                            _unified_drift = getattr(self, '_last_drift', 0.0)
                            _unified_depth = len(retrieved) if retrieved else 0
                            self.crt_math.unified_gate(_unified_relevance, _unified_drift, _unified_depth)
                        except Exception:
                            pass

                        # Log gate event
                        if self.active_learning:
                            try:
                                self.active_learning.record_gate_event(
                                    question=user_query,
                                    response_type_predicted=response_type_pred,
                                    intent_align=intent_align,
                                    memory_align=memory_align,
                                    grounding_score=grounding_score,
                                    gates_passed=gates_passed,
                                    gate_reason=gate_reason,
                                    thread_id="default",
                                    session_id=self.session_id,
                                )
                            except Exception as e:
                                log_swallowed_exception("crt_rag.query.active_learning.summary", e)

                        response_type = "belief" if gates_passed else "speech"
                        source = MemorySource.SYSTEM if gates_passed else MemorySource.FALLBACK
                        confidence = 0.95 if gates_passed else 0.95 * 0.7

                        best_prior = retrieved[0][0] if retrieved else None

                        self.memory.store_memory(
                            text=candidate_output,
                            confidence=confidence,
                            source=source,
                            context={'query': user_query, 'type': response_type, 'kind': 'fact_summary'},
                            user_marked_important=False,
                            thread_id=thread_id,
                        )

                        learned = self._get_learned_suggestions_for_slots(
                            [
                                "name",
                                "employer",
                                "title",
                                "location",
                                "programming_years",
                                "first_language",
                                "masters_school",
                                "team_size",
                                "remote_preference",
                            ]
                        )

                        return {
                            'answer': candidate_output,
                            'thinking': None,
                            'mode': 'quick',
                            'confidence': confidence,
                            'response_type': response_type,
                            'gates_passed': gates_passed,
                            'gate_reason': gate_reason,
                            'intent_alignment': intent_align,
                            'memory_alignment': memory_align,
                            'contradiction_detected': False,
                            'contradiction_entry': None,
                            'retrieved_memories': [
                                {
                                    'text': mem.text,
                                    'trust': mem.trust,
                                    'confidence': mem.confidence,
                                    'source': mem.source.value,
                                    'sse_mode': mem.sse_mode.value,
                                    'score': score,
                                }
                                for mem, score in retrieved
                            ],
                            'prompt_memories': [
                                {
                                    'text': d.get('text'),
                                    'trust': d.get('trust'),
                                    'confidence': d.get('confidence'),
                                    'source': d.get('source'),
                                }
                                for d in prompt_docs
                            ],
                            'learned_suggestions': learned,
                            'heuristic_suggestions': self._get_heuristic_suggestions_for_slots(
                                [
                                    "name",
                                    "employer",
                                    "title",
                                    "location",
                                    "programming_years",
                                    "first_language",
                                    "masters_school",
                                    "team_size",
                                    "remote_preference",
                                ]
                            ),
                            'best_prior_trust': best_prior.trust if best_prior else None,
                            'session_id': self.session_id,
                        }
        
        if not retrieved and not _copilot_context and not _web_search_results:
            # No memories, no copilot context, and no web results -> fallback speech
            return self._fallback_response(user_query, thread_id=thread_id)
        
        # GLOBAL COHERENCE GATE: Check for unresolved contradictions.
        # Only hard CONFLICT contradictions should trigger an uncertainty early-exit.
        # Revisions/refinements/temporal updates can often be answered coherently without stalling.
        from ..crt_ledger import ContradictionType

        unresolved_contradictions = self.ledger.get_open_contradictions(limit=50)
        related_open_total = 0
        related_hard_conflicts = 0

        # Only consider conflicts that are relevant to what the user is asking/asserting.
        # This prevents unrelated open conflicts (e.g., remote_preference) from stalling unrelated queries (e.g., employer).
        relevant_slots = set(inferred_slots or []) | set((asserted_facts or {}).keys())

        retrieved_mem_ids = {mem.memory_id for mem, _ in retrieved}
        for contra in unresolved_contradictions:
            # Skip if not a hard CONFLICT type
            if getattr(contra, "contradiction_type", None) != ContradictionType.CONFLICT:
                continue
            
            # Check if contradiction affects slots relevant to this query
            # Use affects_slots field if available for fast filtering
            affects_slots_str = getattr(contra, "affects_slots", None)
            contra_mem_ids = {contra.old_memory_id, contra.new_memory_id}
            
            if affects_slots_str:
                affects_slots_set = set(affects_slots_str.split(","))
                # Only count this contradiction if it affects slots we're querying about
                # If relevant_slots is empty (query doesn't target slots), check retrieval overlap instead
                if relevant_slots:
                    if not (affects_slots_set & relevant_slots):
                        continue  # Contradiction doesn't affect any slots we're querying about
                else:
                    # Query doesn't target specific slots - only count if contradiction was retrieved
                    if not (contra_mem_ids & retrieved_mem_ids):
                        continue  # Not retrieved, so not relevant
            else:
                # No affects_slots cached - check retrieval overlap as fallback
                if not (contra_mem_ids & retrieved_mem_ids):
                    continue
            
            related_open_total += 1

            # If the current query doesn't target user-fact slots, don't block the conversation.
            if not relevant_slots:
                continue

            try:
                # Double-check slot overlap if we don't have affects_slots cached
                if not affects_slots_str:
                    old_mem = self.memory.get_memory_by_id(contra.old_memory_id)
                    new_mem = self.memory.get_memory_by_id(contra.new_memory_id)
                    if old_mem is None or new_mem is None:
                        continue

                    old_facts = extract_fact_slots(old_mem.text) or {}
                    new_facts = extract_fact_slots(new_mem.text) or {}
                    shared = set(old_facts.keys()) & set(new_facts.keys()) & set(relevant_slots)
                    if not shared:
                        continue
                
                related_hard_conflicts += 1
            except Exception:
                # Never allow contradiction relevance checks to block a normal answer.
                continue
        
        # EARLY EXIT: Express uncertainty only when an unresolved hard CONFLICT
        # is relevant to the user's current slot-targeted question/assertion.
        should_uncertain = False
        uncertain_reason = ""
        if related_hard_conflicts > 0:
            should_uncertain, uncertain_reason = self._should_express_uncertainty(
                retrieved=retrieved,
                contradictions_count=related_hard_conflicts,
                gates_passed=False,  # Haven't checked gates yet
            )
        
        if should_uncertain and user_input_kind != "assertion":
            # If we can infer a concrete next action from conflicts, include it.
            # NOTE: Assertions are corrections FROM the user  -  never ask them to
            # re-clarify what they just told us.
            contradiction_goals, conflict_beliefs = self._infer_contradiction_goals_for_query(
                user_query=user_query,
                retrieved=retrieved,
                inferred_slots=inferred_slots,
            )
            recommended_next_action = contradiction_goals[0] if contradiction_goals else None

            uncertain_response = self._generate_uncertain_response(
                user_query,
                retrieved,
                uncertain_reason,
                recommended_next_action=recommended_next_action,
                conflict_beliefs=conflict_beliefs,
            )
            self._record_memory_usage(
                retrieved,
                event_type="guard_blocked",
                reason="unresolved_contradictions",
                usage_trace_id=usage_trace_id,
                query=user_query,
                thread_id=thread_id,
                metadata={
                    "gate_reason": "unresolved_contradictions",
                    "unresolved_hard_conflicts": related_hard_conflicts,
                    "unresolved_contradictions_total": related_open_total,
                    "slots": inferred_slots,
                },
            )
            return {
                'answer': uncertain_response,
                'thinking': None,
                'mode': 'uncertainty',
                'confidence': 0.3,  # Low confidence for uncertain responses
                'response_type': 'uncertainty',
                'gates_passed': False,
                'gate_reason': 'unresolved_contradictions',
                'intent_alignment': 0.0,
                'memory_alignment': 0.0,
                'contradiction_detected': contradiction_detected,
                'contradiction_entry': (contradiction_entry.to_dict() if contradiction_entry is not None else None),
                'retrieved_memories': [
                    {'text': mem.text, 'trust': mem.trust, 'confidence': mem.confidence}
                    for mem, _ in retrieved
                ],
                'unresolved_contradictions': related_hard_conflicts,
                'unresolved_contradictions_total': related_open_total,
                'unresolved_hard_conflicts': related_hard_conflicts,
                'contradiction_goals': contradiction_goals,
                'recommended_next_action': recommended_next_action,
                'learned_suggestions': [],
                'heuristic_suggestions': [],
                'best_prior_trust': None,
                'session_id': self.session_id,
                'gate_debug': {
                    'trigger': 'unresolved_contradictions',
                    'slot': ', '.join(inferred_slots) if inferred_slots else '?',
                    'hard_conflicts': related_hard_conflicts,
                    'open_total': related_open_total,
                    'explanation': f"{related_hard_conflicts} hard conflict(s) and {related_open_total} open contradiction(s) related to your query prevent a confident answer.",
                    'conflicting_memories': [
                        {'text': m.text[:120], 'trust': m.trust}
                        for m, _ in retrieved[:3]
                    ],
                },
            }

        # Extract best prior belief
        best_prior = retrieved[0][0] if retrieved else None

        # Sprint 10: Volatility-gated context — re-rank by volatility and allocate budget
        _context_budget = None
        _proactive_alerts = []
        try:
            from ..volatility_context import rerank_by_volatility, allocate_context_budget
            retrieved = rerank_by_volatility(retrieved, self.ledger, self.memory, boost_factor=0.5)
            # Phase G3: Fisher-weighted reranking — prefer memories with tighter sigma
            try:
                retrieved = _fisher_rerank(retrieved, fisher_weight=0.3)
            except Exception as _fr_err:
                logger.debug("[FISHER_RERANK] skipped: %s", _fr_err)
            _context_budget = allocate_context_budget(
                query=user_query,
                retrieved=retrieved,
                total_budget=6000,
                ledger=self.ledger,
                memory_system=self.memory,
            )
            _proactive_alerts = _context_budget.volatile_proactive
            logger.info(
                "[VOLATILITY_CTX] budget used=%d/%d allocs=%d full=%d summary=%d slot_only=%d alerts=%d",
                _context_budget.used_chars, _context_budget.available_chars,
                len(_context_budget.allocations),
                sum(1 for a in _context_budget.allocations if a.compression_applied == "full"),
                sum(1 for a in _context_budget.allocations if a.compression_applied == "summary"),
                sum(1 for a in _context_budget.allocations if a.compression_applied == "slot_only"),
                len(_proactive_alerts),
            )
        except Exception as _vol_err:
            log_swallowed_exception("crt_rag.query.volatility_context", _vol_err)

        # Build a conflict-resolved memory view for prompting.
        # We keep raw retrieval for scoring/alignment, but present canonical facts
        # (latest, user-first) to reduce "snap back" to older contradictory text.
        # When self-referential, allow more non-slot lines so self-knowledge surfaces.
        _doc_fallback_lines = 5 if _is_self_referential else 0
        prompt_docs = self._build_resolved_memory_docs(
            retrieved,
            max_fallback_lines=_doc_fallback_lines,
            query=user_query,
            thread_id=thread_id,
            usage_trace_id=usage_trace_id,
            usage_reason="reasoning_prompt",
        )
        learned = self._get_learned_suggestions_for_slots(self._infer_slots_from_query(user_query))
        heuristic = self._get_heuristic_suggestions_for_slots(self._infer_slots_from_query(user_query))
        
        # 2. Generate candidate output using reasoning
        style_profile = None
        personality_profile = None
        reflection_scorecard = None
        episodic_preferences = None
        try:
            if thread_id:
                session_db = get_thread_session_db()
                style_profile = session_db.get_style_profile(thread_id)
                personality_profile = session_db.get_personality_profile(thread_id)
                reflection_scorecard = session_db.get_reflection_scorecard(thread_id)
        except Exception as e:
            log_swallowed_exception("crt_rag.query.thread_session_profiles", e)
            style_profile = None
            personality_profile = None
            reflection_scorecard = None

        # Episodic preferences (explicit + inferred from chat).
        try:
            from ..episodic_memory import get_episodic_manager
            episodic_mgr = get_episodic_manager(memory_system=self.memory)
            episodic_ctx = episodic_mgr.get_user_context()
            if isinstance(episodic_ctx, dict):
                prefs = episodic_ctx.get("preferences")
                if isinstance(prefs, dict):
                    episodic_preferences = prefs
        except Exception as e:
            log_swallowed_exception("crt_rag.query.episodic_preferences", e)
            episodic_preferences = None

        # Sprint 10: Inject proactive volatility alerts as extra context
        if _proactive_alerts:
            _alert_text = "\n".join(f"- {a}" for a in _proactive_alerts)
            extra_context["volatility_alerts"] = (
                "\n[RECENT BELIEF CHANGES]\n"
                f"{_alert_text}\n"
                "Mention these naturally if relevant to the user's question.\n"
            )

        # Sprint 10: Annotate prompt_docs with volatility info from budget allocations
        if _context_budget and _context_budget.allocations:
            _alloc_map = {a.memory_id: a for a in _context_budget.allocations}
            for _doc in prompt_docs:
                _mid = _doc.get('memory_id')
                if _mid and _mid in _alloc_map:
                    _alloc = _alloc_map[_mid]
                    _doc['volatility'] = _alloc.volatility
                    _doc['recently_changed'] = _alloc.recently_changed
                    # Replace text with budget-compressed version if not full
                    if _alloc.compression_applied != "full" and _alloc.text:
                        _doc['text'] = _alloc.text

        # Inject extra_context blocks (from blindside, contradiction, name-history, etc.)
        # as synthetic retrieved docs so the reasoning prompt sees them.
        _injected_docs = list(prompt_docs)
        # Tag docs with open contradictions so reasoning.py Layer 2.1/2.2
        # can identify contested facts and hedge/revise accordingly.
        for _doc in _injected_docs:
            _mid = _doc.get('memory_id')
            if _mid and hasattr(self.ledger, 'has_open_contradiction'):
                _doc['reintroduced_claim'] = self.ledger.has_open_contradiction(_mid)
        if extra_context:
            for _ctx_key, _ctx_text in extra_context.items():
                _injected_docs.append({
                    'text': _ctx_text,
                    'trust': 1.0,
                    'confidence': 1.0,
                    'source': 'system',
                    '_injected_context': _ctx_key,
                })

        # Guard against LLM hallucinating contradiction responses for queries
        # that don't target any fact slots.  Even with retrieved_docs=[] for
        # general knowledge, the conversation history may contain prior
        # contradiction discussions and the model may carry them forward.
        if _is_general_knowledge and not inferred_slots:
            extra_context["no_conflict_surfacing"] = (
                "\n[IMPORTANT: NO CONFLICT SURFACING]\n"
                "The user is NOT asking about any of your stored facts or personal data.\n"
                "Do NOT mention conflicting information, contradictions, or uncertainty.\n"
                "Answer the user's question directly and conversationally.\n"
            )
            # Re-inject into docs
            if extra_context.get("no_conflict_surfacing"):
                _injected_docs.append({
                    'text': extra_context["no_conflict_surfacing"],
                    'trust': 1.0,
                    'confidence': 1.0,
                    'source': 'system',
                    '_injected_context': 'no_conflict_surfacing',
                })

        if _is_general_knowledge:
            # Soft approach: keep injected context + up to 3 supplementary memories
            # (prevents gate_fail cascades while avoiding memory-first answers)
            _gk_injected = [d for d in _injected_docs if d.get('_injected_context')]
            _gk_supplementary = [d for d in _injected_docs if not d.get('_injected_context')][:3]
            for _sd in _gk_supplementary:
                _sd['_supplementary'] = True
            _gk_docs = _gk_injected + _gk_supplementary
            if _gk_supplementary:
                _gk_docs.append({
                    'text': (
                        "[SUPPLEMENTARY CONTEXT]\n"
                        "The memories above are supplementary context only. "
                        "Use them ONLY if directly relevant to the user's question. "
                        "Do NOT force personal facts into a general knowledge answer."
                    ),
                    'trust': 1.0,
                    'confidence': 1.0,
                    'source': 'system',
                    '_injected_context': 'supplementary_guidance',
                })
        else:
            _gk_docs = _injected_docs

        reasoning_context = {
            'retrieved_docs': _gk_docs,
            'contradictions': [],  # Will detect after generation
            'memory_context': [],
            'style_profile': style_profile,
            'personality_profile': personality_profile,
            'reflection_scorecard': reflection_scorecard,
            'episodic_preferences': episodic_preferences,
            'copilot_context': _copilot_context if _is_copilot_query else [],
            'web_search_results': _web_search_results if _is_search_query else [],
            'web_evidence_packet': _web_evidence_packet if _is_search_query else None,
            'is_general_knowledge': _is_general_knowledge,
        }

        # ── Law 6: Continuity gate (pre-generation) ──────────────────
        # Check if we have prior responses on this topic and inject as context
        _continuity_verdict = None
        if self.continuity_auditor:
            try:
                from personal_agent.immune_agents.continuity_auditor import ContinuityCheck
                _continuity_verdict = self.continuity_auditor.check(
                    ContinuityCheck(query=user_query, thread_id=thread_id)
                )
                if _continuity_verdict.continuity_context:
                    reasoning_context['continuity_context'] = _continuity_verdict.continuity_context
                    logger.info(
                        "[LAW6] Continuity %s: %d priors, max_sim=%.3f, consistency=%s",
                        _continuity_verdict.action.value,
                        _continuity_verdict.prior_count,
                        _continuity_verdict.max_similarity,
                        _continuity_verdict.internal_consistency,
                    )
            except Exception as e:
                log_swallowed_exception("crt_rag.query.continuity_check", e)

        # ═══════════════════════════════════════════════════════════════
        # SCAFFOLD GENERATION GATE
        # ═══════════════════════════════════════════════════════════════
        # When running on a local model, small models (3B-14B) struggle
        # with open-ended queries that require synthesizing many memories.
        # Instead of dumping everything into context and hoping, we use
        # a staged scaffold that walks the belief graph anchor-by-anchor.
        #
        # The scaffold:
        #   1. Groups memories into topic clusters (anchor basins)
        #   2. Generates 2-3 sentences per cluster with focused context
        #   3. Checks each section against prior sections for coherence
        #   4. Retries failed sections, excludes irreconcilable ones
        #   5. Expands verified facts with one inference step
        #
        # This is the PRIMARY generation path for local models, not a
        # fallback. Cloud models still use direct generation because
        # they have the attention span for it.
        #
        # Feature flag: set CRT_SCAFFOLD_GENERATION=true to enable
        # (disabled by default until integration is validated)
        # ═══════════════════════════════════════════════════════════════
        _use_scaffold = False
        _scaffold_result = None
        try:
            import os
            _scaffold_enabled = os.getenv("CRT_SCAFFOLD_GENERATION", "false").lower() in ("true", "1", "yes")
            _is_local_mode = (model_override or "").startswith("ollama") or \
                             str(getattr(self, '_current_gen_mode', '') or '').lower() in ("local", "local_network")
            _is_open_ended = len(prompt_docs) >= 3 and not _is_general_knowledge and not _is_search_query

            if _scaffold_enabled and _is_local_mode and _is_open_ended:
                from personal_agent.scaffold_generation import scaffold_generate

                # Convert prompt_docs to the format scaffold expects: (text, trust, id)
                _scaffold_memories = []
                for doc in prompt_docs:
                    _text = doc.get('text', '')
                    _trust = float(doc.get('trust', 0.5))
                    _mid = doc.get('memory_id', '')
                    if _text and not doc.get('_injected_context'):
                        _scaffold_memories.append((_text, _trust, _mid))

                if len(_scaffold_memories) >= 3:
                    _scaffold_model = model_override or str(os.getenv("CRT_OLLAMA_MODEL", "gemma3:latest"))
                    _scaffold_result = scaffold_generate(
                        query=user_query,
                        memories=_scaffold_memories,
                        model=_scaffold_model,
                    )
                    _use_scaffold = bool(_scaffold_result and _scaffold_result.get("output", "").strip())
                    if _use_scaffold:
                        logger.info(
                            "[SCAFFOLD_GATE] Using scaffold generation: %d/%d anchors, %d tokens",
                            _scaffold_result.get("anchors_passed", 0),
                            _scaffold_result.get("anchors_total", 0),
                            _scaffold_result.get("tokens_used", 0),
                        )
        except Exception as _scaffold_err:
            logger.debug("[SCAFFOLD_GATE] Scaffold generation failed, falling back to standard: %s", _scaffold_err)
            _use_scaffold = False

        if _use_scaffold and _scaffold_result:
            # Scaffold produced the output - wrap it in the expected format
            candidate_output = _scaffold_result["output"]
            reasoning_result = {
                'answer': candidate_output,
                'mode': 'scaffold_staged',
                'scaffold_meta': {
                    'anchors_passed': _scaffold_result.get("anchors_passed", 0),
                    'anchors_total': _scaffold_result.get("anchors_total", 0),
                    'anchors_dead': _scaffold_result.get("anchors_dead", 0),
                    'tokens_used': _scaffold_result.get("tokens_used", 0),
                    'time_ms': _scaffold_result.get("time_ms", 0),
                },
            }
        else:
            # Standard generation path (cloud models or scaffold disabled)
            reasoning_result = self.reasoning.reason(
                query=user_query,
                context=reasoning_context,
                mode=mode,
                model_override=model_override,
                conversation_history=conversation_history,
            )
            candidate_output = reasoning_result['answer']

        # Consistency guard: if we have memory context, do not let the surface text
        # claim "first conversation" / "no memories".
        candidate_output = self._sanitize_memory_denial(answer=candidate_output, has_memory_context=bool(prompt_docs))
        # Honesty guard: if the model claims it "remembers" a personal fact that is not
        # present in our resolved FACT prompt docs, strip that unsupported claim.
        candidate_output = self._sanitize_unsupported_memory_claims(
            answer=candidate_output,
            prompt_docs=prompt_docs,
            user_query=user_query,
            inferred_slots=inferred_slots,
        )
        # Identity guard: rewrite first-person user-fact claims to second-person.
        # e.g. "My name is Nick" → "Your name is Nick"
        candidate_output = _sanitize_identity_pronouns(candidate_output)
        # UI cleanliness: the assistant should not leak internal scoring/metrics in the user-visible answer.
        # (These are available in metadata panels instead.)
        candidate_output = re.sub(r"\(\s*trust score[^)]*\)", "", candidate_output, flags=re.IGNORECASE).strip()
        if _is_search_query:
            deterministic_web_answer = self._build_web_fulfillment_answer(
                query=_web_search_query or user_query,
                web_results=_web_search_results,
            )
            if deterministic_web_answer:
                candidate_output = deterministic_web_answer
            else:
                candidate_output = self._sanitize_web_mode_answer(candidate_output)
        
        # Phase 2.2: LLM Claim Tracking
        # Check if LLM response contains claims that contradict:
        # 1. What the LLM said before (LLM->LLM contradiction)
        # 2. What the user told us (LLM->USER contradiction)
        llm_claim_result = None
        llm_disclosures = []
        try:
            if hasattr(self, 'fact_store') and self.fact_store:
                llm_claim_result = self.fact_store.process_llm_response(candidate_output, thread_id=thread_id)
                if llm_claim_result.get("disclosures"):
                    llm_disclosures = llm_claim_result["disclosures"]
                    # Prepend disclosures to the output
                    disclosure_text = "\n".join(llm_disclosures) + "\n\n"
                    candidate_output = disclosure_text + candidate_output
                    logger.info(f"[LLM_CLAIM_TRACKER] Added {len(llm_disclosures)} disclosure(s) to response")
                if llm_claim_result.get("claims"):
                    logger.info(f"[LLM_CLAIM_TRACKER] Extracted {len(llm_claim_result['claims'])} claim(s) from LLM response")
        except Exception as e:
            logger.warning(f"[LLM_CLAIM_TRACKER] Failed to process LLM claims: {e}")

        degradation_assessment = self.degradation_detector.assess(
            text=candidate_output,
            reasoning=str(reasoning_result.get("thinking") or ""),
        )
        if degradation_assessment.is_degraded:
            logger.warning(
                "[DEGRADATION] Candidate output flagged degraded (score=%.3f, reasons=%s)",
                degradation_assessment.score,
                ",".join(degradation_assessment.reasons),
            )

        candidate_vector = encode_vector(candidate_output)
        query_vector_for_bs = encode_vector(user_query)

        # 3. Check reconstruction gates
        # For conversational AI, intent alignment = reasoning confidence
        # (Did we confidently answer the question?)
        intent_align = reasoning_result['confidence']
        
        # Memory alignment (output -> retrieved memories)
        memory_align = self.crt_math.memory_alignment(output_vector=candidate_vector, retrieved_memories=[{'vector': mem.vector, 'text': mem.text} for mem, _ in retrieved], retrieval_scores=[score for _, score in retrieved], output_text=candidate_output)
        
        # Predict response type and compute grounding
        response_type_pred = self._classify_query_type_heuristic(user_query) or "unknown"
        
        grounding_score = self._compute_grounding_score(candidate_output, retrieved)
        open_contradictions = self.ledger.get_open_contradictions()
        # BUG FIX: Use inferred_slots instead of extract_fact_slots for questions
        # extract_fact_slots only works for assertions like "I work at Google"
        # but questions like "Where do I work?" need inferred_slots from _infer_slots_from_query
        query_slots = set(inferred_slots or [])
        contradiction_severity = self._classify_contradiction_severity(
            open_contradictions, query_slots
        )
        
        gates_passed, gate_reason = self.crt_math.check_reconstruction_gates_v2(
            intent_align=intent_align,
            memory_align=memory_align,
            response_type=response_type_pred,
            grounding_score=grounding_score,
            contradiction_severity=contradiction_severity,
            blindspot_gate_boost=_blindspot_gate_boost,
        )

        # Upgrade #3: Unified gate (supplementary signal)
        try:
            _unified_relevance = (intent_align + memory_align + grounding_score) / 3.0
            _unified_drift = getattr(self, '_last_drift', 0.0)
            _unified_depth = len(retrieved) if retrieved else 0
            self.crt_math.unified_gate(_unified_relevance, _unified_drift, _unified_depth)
        except Exception:
            pass

        # General knowledge bypass: don't penalize for low memory/intent/grounding
        # alignment on questions that were never about personal facts.
        # Previously only caught "grounding_fail", but general-knowledge queries can
        # also fail on intent_fail, memory_fail, or extraction_fail because there are
        # no relevant memories to align against — that's expected, not a failure.
        if _is_general_knowledge and not gates_passed:
            gates_passed = True
            gate_reason = "general_knowledge_bypass"
            logger.info("[GATE_BYPASS] General knowledge query — bypassing gates (was: %s)", gate_reason)

        # Hard guardrail: if this turn still has query-relevant unresolved hard conflicts,
        # never allow a high-confidence "gates passed" response.
        if related_hard_conflicts > 0 and gates_passed:
            gates_passed = False
            gate_reason = f"{gate_reason}|hard_conflict_pending" if gate_reason else "hard_conflict_pending"
            logger.info(
                "[HARD_CONFLICT_GUARD] Forced gates_passed=false for %d relevant hard conflict(s)",
                related_hard_conflicts,
            )
        
        # Log gate event
        if self.active_learning:
            try:
                self.active_learning.record_gate_event(
                    question=user_query,
                    response_type_predicted=response_type_pred,
                    intent_align=intent_align,
                    memory_align=memory_align,
                    grounding_score=grounding_score,
                    gates_passed=gates_passed,
                    gate_reason=gate_reason,
                    thread_id="default",
                    session_id=self.session_id,
                )
            except Exception as e:
                log_swallowed_exception("crt_rag.query.active_learning.general", e)
        # This ensures confidence aligns with gate pass/fail status
        raw_confidence = reasoning_result['confidence']
        if not gates_passed:
            if "grounding_fail" in gate_reason or "contradiction_fail" in gate_reason:
                # Hard fails: cap confidence very low
                calibrated_confidence = min(raw_confidence, 0.49)
            elif "narration_fail" in gate_reason or "extraction_fail" in gate_reason:
                # Medium fails: cap confidence moderately
                calibrated_confidence = min(raw_confidence, 0.69)
            else:
                # Soft fails (intent/memory alignment): degrade confidence
                calibrated_confidence = raw_confidence * 0.7
        else:
            # Gates passed: use raw confidence
            calibrated_confidence = raw_confidence

        # Secondary confidence cap for unresolved hard conflicts that survived to this stage.
        if related_hard_conflicts > 0:
            calibrated_confidence = min(calibrated_confidence, 0.49)
        
        # 4. Belief vs Speech decision
        # Belief should be reserved for user-profile / memory-grounded answers.
        qlow = (user_query or "").strip().lower()
        is_personalish = bool(inferred_slots) or bool(asserted_facts)
        if not is_personalish:
            # Only treat explicit personal pronouns as personalish if paired with a profile-ish topic.
            if re.search(r"\b(my|mine)\b", qlow) and any(k in qlow for k in ("name", "favorite", "favourite", "work", "job", "employer", "live", "located", "pronoun", "title", "goals")):
                is_personalish = True
            if re.search(r"\b(about me|do you remember|what do you know about me)\b", qlow):
                is_personalish = True

        used_fact_lines = any(str(d.get("text") or "").lower().startswith("fact:") for d in (prompt_docs or []))

        if gates_passed and (is_personalish or used_fact_lines):
            response_type = "belief"
            source = MemorySource.SYSTEM
            confidence = calibrated_confidence
        elif gates_passed:
            response_type = "speech"
            source = MemorySource.SYSTEM
            confidence = calibrated_confidence
        else:
            response_type = "speech"
            source = MemorySource.FALLBACK
            confidence = calibrated_confidence  # Already degraded above

        # Phase 0.5 DNNT hook: quarantine degraded outputs as fallback speech.
        if degradation_assessment.is_degraded:
            gates_passed = False
            if gate_reason:
                gate_reason = f"{gate_reason}|degraded_output"
            else:
                gate_reason = "degraded_output"
            response_type = "speech"
            source = MemorySource.FALLBACK
            calibrated_confidence = min(calibrated_confidence, 0.35)
            confidence = min(confidence, calibrated_confidence)
        
        # 5. Detect contradictions (only when USER made a new assertion)
        # IMPORTANT: Do NOT reset contradiction_detected if _check_all_fact_contradictions_ml()
        # already detected one earlier in the assertion path (line ~3242).
        # Previously this unconditionally set contradiction_detected = False, wiping the ML
        # detector's finding for age, location, pet, language, etc.
        if not contradiction_detected:
            contradiction_entry = None
        
        logger.debug("Generic contradiction check: user_input_kind=%s, user_memory=%s", user_input_kind, user_memory is not None)
        print(f"[CONTRADICTION_DEBUG] user_input_kind={user_input_kind}, user_memory={'yes' if user_memory else 'no'}, contradiction_detected_already={contradiction_detected}")
        if user_input_kind != "question" and user_memory is not None:
            # Prefer claim-level contradiction detection for common personal-profile facts.
            # This avoids false positives from pure embedding drift, and catches true conflicts
            # even when retrieval does not surface the relevant prior memory.
            new_facts = extract_fact_slots(user_query)
            logger.debug("Extracted fact slots: %s", list(new_facts.keys()) if new_facts else None)
            print(f"[CONTRADICTION_DEBUG] extracted slots: {list(new_facts.keys()) if new_facts else 'none'}")
            if new_facts:
                user_vector = encode_vector(user_query)
                previous_user_memories = self._load_thread_user_memories(
                    thread_id=thread_id,
                    exclude_memory_id=user_memory.memory_id,
                )

                from ..crt_ledger import ContradictionType

                # Build candidate facts per slot from prior USER memories.
                candidates_by_slot: Dict[str, List[Tuple[MemoryItem, Any]]] = {}
                for prev_mem in previous_user_memories:
                    prev_facts = extract_fact_slots(prev_mem.text)
                    if not prev_facts:
                        continue
                    for slot, fact in prev_facts.items():
                        if slot == "name" and not is_explicit_name_declaration_text(prev_mem.text):
                            continue
                        candidates_by_slot.setdefault(slot, []).append((prev_mem, fact))

                # Only create a contradiction if the asserted value is NEW for that slot.
                # If it matches the MOST RECENT prior value for the slot, treat it as reinforcement.
                # If it differs from the most recent value (even if it matches an older value),
                # record a contradiction: this captures explicit reversions/corrections like
                # "12 was wrong; it's 8".
                selected_prev: Optional[MemoryItem] = None
                for slot, new_fact in new_facts.items():
                    prior = candidates_by_slot.get(slot) or []
                    if not prior:
                        continue

                    # Compare against the most recent value for this slot.
                    latest_mem, latest_fact = max(
                        prior,
                        key=lambda mf: (getattr(mf[0], "timestamp", 0.0), getattr(mf[0], "trust", 0.0)),
                    )

                    latest_norm = getattr(latest_fact, "normalized", None)
                    new_norm = getattr(new_fact, "normalized", None)
                    logger.debug("Fact comparison: slot=%s, latest='%s', new='%s', match=%s", slot, latest_norm, new_norm, latest_norm == new_norm)
                    print(f"[CONTRADICTION_DEBUG] slot={slot} latest='{latest_norm}' new='{new_norm}' match={latest_norm == new_norm}")
                    if latest_norm == new_norm:
                        continue
                    if slot == "name" and names_look_equivalent(
                        str(getattr(latest_fact, "value", latest_norm) or ""),
                        str(getattr(new_fact, "value", new_norm) or ""),
                    ):
                        logger.debug(
                            "Skipping generic name contradiction for refinement: latest=%s new=%s",
                            latest_norm,
                            new_norm,
                        )
                        continue

                    # ---- Slot type awareness ----
                    # If slot_discovery knows this is an EXCLUSIVE slot, a different
                    # value IS a contradiction — skip the ML detector gate entirely.
                    # This prevents the ML detector from suppressing obvious reversals
                    # like favorite_drink: "orange juice" -> "water".
                    from ..slot_discovery import get_slot_type, SlotType
                    _slot_type = get_slot_type(slot, db_path=getattr(self.memory, 'db_path', None))
                    print(f"[CONTRADICTION_DEBUG] slot_type={_slot_type.value} for slot={slot}")

                    if _slot_type == SlotType.ADDITIVE:
                        # Additive slots can hold multiple values — not a contradiction
                        print(f"[CONTRADICTION_DEBUG] ADDITIVE slot {slot} — skipping contradiction (coexist)")
                        logger.info(f"[SLOT_AWARE] Additive slot '{slot}': '{new_norm}' coexists with '{latest_norm}'")
                        continue

                    if _slot_type == SlotType.EXCLUSIVE:
                        # Exclusive slot with different value = contradiction. Skip ML gate.
                        print(f"[CONTRADICTION_DEBUG] EXCLUSIVE slot {slot}: '{latest_norm}' -> '{new_norm}' = CONTRADICTION (bypassing ML)")
                        logger.info(f"[SLOT_AWARE] Exclusive slot '{slot}' contradiction: '{latest_norm}' -> '{new_norm}'")
                        selected_prev = latest_mem
                        break

                    # Values differ - for UNKNOWN/TEMPORAL slots, check ML detector
                    # This catches semantic equivalents like "PhD in ML" vs "doctorate in CS"
                    if self.ml_detector:
                        ml_result = self.ml_detector.check_contradiction(
                            old_value=str(getattr(latest_fact, "value", latest_norm)),
                            new_value=str(getattr(new_fact, "value", new_norm)),
                            slot=slot,
                            context={"query": user_query}  # Pass query for retraction pattern detection
                        )
                        print(f"[CONTRADICTION_DEBUG] ML detector result: {ml_result}")
                        if not ml_result.get("is_contradiction", True):
                            # ML says it's not a contradiction (e.g., semantic equivalence)
                            print(f"[CONTRADICTION_DEBUG] ML BLOCKED contradiction for slot={slot}: '{latest_norm}' vs '{new_norm}' category={ml_result.get('category')}")
                            logger.debug(
                                "ML detector says no contradiction for slot=%s: '%s' vs '%s' (category=%s)",
                                slot, latest_norm, new_norm, ml_result.get("category", "unknown")
                            )
                            continue

                    # New asserted value conflicts with the latest value => contradiction.
                    selected_prev = latest_mem
                    break

                logger.debug("Contradiction detection result: selected_prev=%s", selected_prev is not None)
                if selected_prev is not None:
                    drift = self.crt_math.drift_meaning(user_vector, selected_prev.vector)
                    logger.info(f"[CONTRADICTION_DETECTION] Generic fact contradiction detected: query='{user_query[:60]}' vs old='{selected_prev.text[:60]}', drift={drift:.3f}")

                    # Phase 1.1: Use CRTMath paraphrase check as final gate
                    # BUT: for EXCLUSIVE slots, skip paraphrase gate — the slot type
                    # already confirms this is a real contradiction, and embedding
                    # similarity will be high because both discuss the same topic.
                    _slot_type_for_gate = get_slot_type(slot, db_path=getattr(self.memory, 'db_path', None))
                    if _slot_type_for_gate == SlotType.EXCLUSIVE:
                        is_real_contradiction = True
                        crt_reason = f"exclusive_slot_override:{slot}"
                        print(f"[CONTRADICTION_DEBUG] EXCLUSIVE slot bypass of paraphrase gate for {slot}")
                    else:
                        is_real_contradiction, crt_reason = self.crt_math.detect_contradiction(
                            drift=drift,
                            confidence_new=0.95,
                            confidence_prior=float(selected_prev.confidence),
                            source=user_memory.source,
                            text_new=user_query,
                            text_prior=selected_prev.text,
                            slot=slot,
                            value_new=str(getattr(new_fact, "value", getattr(new_fact, "normalized", ""))),
                            value_prior=str(getattr(latest_fact, "value", getattr(latest_fact, "normalized", ""))),
                        )
                    if not is_real_contradiction:
                        logger.info(f"[CRT_PARAPHRASE] Skipped generic fact contradiction - {crt_reason}")
                    else:
                        contradiction_entry = self._record_and_cascade(
                            old_memory_id=selected_prev.memory_id,
                            new_memory_id=user_memory.memory_id,
                            drift_mean=drift,
                            confidence_delta=selected_prev.confidence - 0.95,
                            query=user_query,
                            summary=f"User contradiction: {selected_prev.text[:50]}... vs {user_query[:50]}...",
                            old_text=selected_prev.text,
                            new_text=user_query,
                            old_vector=selected_prev.vector,
                            new_vector=user_vector,
                            thread_id=thread_id,
                        )

                        contradiction_detected = True

                        if (
                            contradiction_entry.contradiction_type == ContradictionType.CONFLICT
                            and self.memory.can_affect_contradiction_resolution(user_memory)
                        ):
                            self.memory.evolve_trust_for_contradiction(selected_prev, user_vector)

                    volatility = self.crt_math.compute_volatility(
                        drift=drift,
                        memory_alignment=memory_align,
                        is_contradiction=True,
                        is_fallback=False
                    )

                    if contradiction_entry is not None and self.crt_math.should_reflect(volatility):
                        self.ledger.queue_reflection(
                            ledger_id=contradiction_entry.ledger_id,
                            volatility=volatility,
                            context={
                                'query': user_query,
                                'drift': drift,
                                'intent_align': intent_align,
                                'memory_align': memory_align
                            }
                        )

        # --------------------------------------------------------------------
        # Provenance / warnings (metadata-only)
        # --------------------------------------------------------------------
        # Do not append provenance footers into the user-visible answer text; the UI can
        # render provenance using prompt/retrieved memories.
        final_answer = candidate_output

        # ── NEW CONTRADICTION DISCLOSURE ─────────────────────────────────
        # If we JUST detected a contradiction in THIS message (not a pre-existing one),
        # override the response to surface the conflict instead of blindly accepting.
        if contradiction_detected and contradiction_entry is not None and selected_prev is not None:
            old_trust = float(getattr(selected_prev, 'confidence', 0.0))
            new_trust = float(getattr(user_memory, 'confidence', 0.0)) if user_memory else 0.7
            # Only override if the existing memory has meaningfully higher trust
            if old_trust >= 0.8:
                old_text = selected_prev.text[:200]
                new_text = user_query[:200]
                final_answer = (
                    f"I noticed a conflict with what I already know.\n\n"
                    f"Previously stored (trust {old_trust:.0%}): {old_text}\n"
                    f"You just said: {new_text}\n\n"
                    f"Which one is correct? I want to make sure I have this right."
                )
                gates_passed = False
                gate_reason = "new_contradiction_disclosure"
                response_type = "speech"
                logger.info(
                    f"[CONTRADICTION_OVERRIDE] Overrode response — old trust={old_trust:.2f}, "
                    f"new assertion conflicts with stored fact"
                )
        
        # SPRINT 1: Force append caveats when contradictions exist
        # This ensures caveat violations are reduced to 0
        relevant_contradictions: List[Any] = []
        if query_slots and open_contradictions:
            # Check if any open contradictions affect the queried slots
            for contra in open_contradictions:
                affects_slots_str = getattr(contra, 'affects_slots', None)
                if affects_slots_str and query_slots:
                    affects_slots = set(affects_slots_str.split(","))
                    if affects_slots & query_slots:
                        relevant_contradictions.append(contra)
            
            # FORCE append disclosure for relevant contradictions (don't rely on LLM)
            if relevant_contradictions:
                disclosure = f"\n\n(Note: {len(relevant_contradictions)} unresolved contradiction(s). "
                
                for contra in relevant_contradictions[:3]:  # Show first 3
                    # Try to extract old/new values from contradiction
                    old_val = None
                    new_val = None
                    
                    # Try to get values from the contradiction metadata
                    if hasattr(contra, 'summary') and contra.summary:
                        # Parse summary for values (re already imported at top of file)
                        match = re.search(r"(\w+)\s+vs\s+(\w+)", contra.summary)
                        if match:
                            old_val = match.group(1)
                            new_val = match.group(2)
                    
                    # If we couldn't extract values, use generic message
                    if old_val and new_val:
                        disclosure += f"Changed information detected. "
                    else:
                        disclosure += f"Conflicting information detected. "
                
                disclosure += "Please clarify if needed.)"
                
                # FORCE append disclosure (don't rely on LLM to include it)
                final_answer = candidate_output.rstrip() + disclosure
                
                logger.info(f"[CAVEAT] Forced disclosure appended: {len(relevant_contradictions)} contradictions")

        # Real-time web policy: responses must carry explicit citations.
        if _is_search_query:
            final_answer = self._enforce_web_answer_policy(
                answer=final_answer,
                web_results=_web_search_results,
                evidence_packet=_web_evidence_packet,
            )
        
        # INVARIANT ENFORCEMENT: Flag all reintroduced claims
        # This creates machine-readable proof that contradicted facts are marked
        retrieved_with_flags = self._flag_reintroduced_claims([mem for mem, _ in retrieved])
        prompt_with_flags = self._flag_reintroduced_claims(
            [self.memory.get_memory_by_id(d.get('memory_id')) 
             for d in (prompt_docs or []) 
             if d.get('memory_id')]
        ) if prompt_docs else []
        
        # MANDATORY CAVEAT ENFORCEMENT: Count reintroductions and inject caveat
        reintroduced_count = sum(1 for m in retrieved_with_flags if m.get('reintroduced_claim'))
        if reintroduced_count > 0:
            if not self._answer_has_caveat(final_answer):
                # Build specific caveat based on contradiction details
                caveat = self._build_mandatory_caveat(
                    user_input_kind=user_input_kind,
                    reintroduced_count=reintroduced_count,
                    relevant_contradictions=relevant_contradictions
                )
                final_answer = f"{final_answer.rstrip()} {caveat}"
                logger.info(f"[CAVEAT_INJECTED] Added mandatory caveat for {reintroduced_count} reintroduced claim(s)")
        
        # 6. Store system response memory
        new_memory = self.memory.store_memory(
            text=final_answer,
            confidence=confidence,
            source=source,
            context={'query': user_query, 'type': response_type},
            user_marked_important=False,  # System responses not marked important
            thread_id=thread_id,
        )
        
        # Update trust for aligned USER memories when gates pass
        # This rewards user memories that led to coherent, confident responses
        if gates_passed and retrieved:
            for mem, score in retrieved[:3]:  # Top 3 retrieved
                # Only evolve trust for USER memories (not system/fallback)
                if mem.source == MemorySource.USER:
                    self.memory.evolve_trust_for_alignment(mem, candidate_vector)
        
        # 7. Record belief or speech (with embeddings for variance tracking)
        _q_emb = query_vector_for_bs.astype(np.float32).tobytes() if query_vector_for_bs is not None else None
        _r_emb = candidate_vector.astype(np.float32).tobytes() if candidate_vector is not None else None
        if response_type == "belief":
            self.memory.record_belief(
                query=user_query,
                response=final_answer,
                memory_ids=[mem.memory_id for mem, _ in retrieved],
                avg_trust=np.mean([mem.trust for mem, _ in retrieved]),
                query_embedding=_q_emb,
                response_embedding=_r_emb,
            )
        else:
            self.memory.record_speech(
                query=user_query,
                response=final_answer,
                source="fallback_gates_failed",
                query_embedding=_q_emb,
                response_embedding=_r_emb,
            )
        
        # 7b. Compute PCA 2D projection + pairwise similarities for epistemic graph
        _pca_coords = {}  # memory_id -> (x, y)
        _sim_edges = []   # [{from, to, sim}]
        try:
            _vecs_for_pca = []
            _ids_for_pca = []
            for mem, _sc in retrieved:
                if mem.vector is not None and len(mem.vector) == 384:
                    _vecs_for_pca.append(mem.vector)
                    _ids_for_pca.append(mem.memory_id)
            if len(_vecs_for_pca) >= 2:
                _pca_matrix = np.array(_vecs_for_pca)
                # Simple 2D projection: PCA for >= 3 points, direct for 2
                if len(_vecs_for_pca) >= 3:
                    from sklearn.decomposition import PCA as _PCA
                    _proj = _PCA(n_components=2).fit_transform(_pca_matrix)
                else:
                    _proj = _pca_matrix[:, :2]
                # Normalize to [-1, 1]
                for dim in range(2):
                    _vmin, _vmax = _proj[:, dim].min(), _proj[:, dim].max()
                    _span = _vmax - _vmin
                    if _span > 1e-8:
                        _proj[:, dim] = 2.0 * (_proj[:, dim] - _vmin) / _span - 1.0
                for _i, _mid in enumerate(_ids_for_pca):
                    _pca_coords[_mid] = (round(float(_proj[_i, 0]), 4), round(float(_proj[_i, 1]), 4))
                # Pairwise cosine similarities for graph edges
                for _i in range(len(_vecs_for_pca)):
                    for _j in range(_i + 1, len(_vecs_for_pca)):
                        _dot = float(np.dot(_vecs_for_pca[_i], _vecs_for_pca[_j]))
                        _norm = float(np.linalg.norm(_vecs_for_pca[_i]) * np.linalg.norm(_vecs_for_pca[_j]) + 1e-8)
                        _csim = _dot / _norm
                        if abs(_csim) > 0.3:  # only meaningful edges
                            _sim_edges.append({
                                "from": _ids_for_pca[_i], "to": _ids_for_pca[_j],
                                "sim": round(_csim, 3),
                            })
        except Exception:
            pass  # epistemic graph is best-effort

        # 8. Return comprehensive result
        return self._add_reintroduction_flags({
            # User-facing
            'answer': final_answer,
            'thinking': reasoning_result.get('thinking'),
            'mode': reasoning_result['mode'],
            'confidence': calibrated_confidence,  # Use calibrated confidence, not raw
            
            # CRT metadata
            'response_type': response_type,  # "belief" or "speech"
            'gates_passed': gates_passed,
            'gate_reason': gate_reason,
            'intent_alignment': intent_align,
            'memory_alignment': memory_align,
            
            # Contradiction tracking
            'contradiction_detected': contradiction_detected,
            'contradiction_entry': contradiction_entry.to_dict() if contradiction_entry else None,
            'degradation_detected': degradation_assessment.is_degraded,
            'degradation_score': degradation_assessment.score,
            'degradation_reasons': degradation_assessment.reasons,
            
            # Phase 2.2: LLM Claim Tracking
            'llm_claims': llm_claim_result.get('claims', []) if llm_claim_result else [],
            'llm_contradictions': llm_claim_result.get('contradictions', []) if llm_claim_result else [],
            'llm_disclosures': llm_disclosures,
            
            # Retrieved context
            'retrieved_memories': [
                {
                    'memory_id': mem.memory_id,
                    'text': mem.text,
                    'timestamp': getattr(mem, 'timestamp', None),
                    'trust': mem.trust,
                    'confidence': mem.confidence,
                    'source': mem.source.value,
                    'sse_mode': mem.sse_mode.value,
                    'score': score,
                    'kind': getattr(mem, 'kind', 'observation'),
                    'pca_x': _pca_coords.get(mem.memory_id, (0.0, 0.0))[0],
                    'pca_y': _pca_coords.get(mem.memory_id, (0.0, 0.0))[1],
                    'reintroduced_claim': self.ledger.has_open_contradiction(mem.memory_id) if hasattr(self.ledger, 'has_open_contradiction') else False,  # INVARIANT FLAG
                }
                for mem, score in retrieved
            ],
            'retrieval_edges': _sim_edges,

            # Prompt context (resolved) for debugging/analysis
            'prompt_memories': [
                {
                    'text': d.get('text'),
                    'memory_id': d.get('memory_id'),
                    'trust': d.get('trust'),
                    'confidence': d.get('confidence'),
                    'source': d.get('source'),
                    'reintroduced_claim': self.ledger.has_open_contradiction(d.get('memory_id')) if d.get('memory_id') and hasattr(self.ledger, 'has_open_contradiction') else False,  # INVARIANT FLAG
                }
                for d in prompt_docs
            ],

            # AUDIT METRICS - Machine-readable reintroduction tracking
            'reintroduced_claims_count': sum(
                1 for mem, _ in retrieved 
                if hasattr(self.ledger, 'has_open_contradiction') and self.ledger.has_open_contradiction(mem.memory_id)
            ),
            # Query-scoped conflict counters used by eval rules.
            # Do not report global open conflict totals here, otherwise unrelated legacy
            # conflicts can incorrectly make this turn look unsafe.
            'unresolved_contradictions_total': int(related_open_total),
            'unresolved_hard_conflicts': int(related_hard_conflicts),

            # Learned suggestions (metadata-only; never authoritative)
            'learned_suggestions': learned,
            'heuristic_suggestions': heuristic,

            # Profile updates (auto-overwrite transparency)
            'profile_updates': profile_updates,

            # Web evidence (real-time answer policy)
            'web_search_results': _web_search_results if _is_search_query else [],
            'web_evidence_packet': _web_evidence_packet if _is_search_query else None,
            
            # Trust evolution
            'best_prior_trust': best_prior.trust if best_prior else None,
            
            # Session
            'session_id': self.session_id,

            # Sprint 10: Volatility context budget metadata
            'context_budget': _context_budget.to_dict() if _context_budget else None,

            # Gate debug — structured explanation of why gates passed or failed
            'gate_debug': ({
                'trigger': gate_reason or 'unknown',
                'slot': ', '.join(inferred_slots) if inferred_slots else None,
                'intent_align': round(intent_align, 3),
                'memory_align': round(memory_align, 3),
                'grounding': round(grounding_score, 3) if grounding_score is not None else None,
                'hard_conflicts': int(related_hard_conflicts),
                'open_total': int(related_open_total),
                'response_type_pred': response_type_pred,
                'explanation': _build_gate_explanation(gate_reason, intent_align, memory_align, grounding_score, related_hard_conflicts),
                'conflicting_memories': [
                    {'text': m.text[:120], 'trust': round(m.trust, 3)}
                    for m, _ in retrieved[:3]
                    if contradiction_detected or not gates_passed
                ] if (contradiction_detected or not gates_passed) else [],
            } if not gates_passed else None),
        })
    def _summarize_longform_text(self, text: str) -> Optional[str]:
        """Summarize long-form user text into durable facts (1 - 2 sentences)."""
        raw = (text or "").strip()
        if not raw:
            return None

        snippet = raw[:LONGFORM_SUMMARY_MAX_CHARS]
        llm = self._llm_client
        if llm is not None:
            prompt = (
                "Summarize the user's message into 1 - 2 sentences of durable personal facts. "
                "Exclude transient moods unless central to their life story. "
                "Do not speculate, diagnose, or add new information. "
                "Return plain text only.\n\n"
                f"Message:\n{snippet}\n"
            )
            try:
                summary = llm.generate(prompt, max_tokens=220, temperature=0.2)
                summary = (summary or "").strip()
                return summary[:400] if summary else None
            except Exception as e:
                log_swallowed_exception("crt_rag._summarize_longform_text.llm", e)

        # Heuristic fallback (no LLM)
        try:
            import re
            sentences = re.split(r"(?<=[.!?])\s+", snippet)
            picks: List[str] = []
            keywords = (
                "i am", "i'm", "my name", "i work", "i live", "i was diagnosed",
                "i have", "i created", "i built", "i prefer", "i like", "i love"
            )
            for s in sentences:
                sl = s.lower()
                if any(k in sl for k in keywords):
                    picks.append(s.strip())
                if len(picks) >= 2:
                    break
            if not picks and sentences:
                picks = [sentences[0].strip()]
            summary = " ".join(picks).strip()
            return summary[:400] if summary else None
        except Exception:
            return None
    def _maybe_store_longform_summary(
        self,
        *,
        text: str,
        thread_id: Optional[str],
        user_marked_important: bool
    ) -> None:
        """Store a low-trust narrative summary for long-form inputs."""
        if not text or len(text) < LONGFORM_SUMMARY_MIN_CHARS:
            return
        if text.strip().lower().startswith("[narrative summary]"):
            return

        summary = self._summarize_longform_text(text)
        if not summary:
            return

        summary_text = f"[NARRATIVE SUMMARY] {summary}"
        try:
            self.memory.store_memory(
                text=summary_text,
                confidence=0.6,
                source=MemorySource.SYSTEM,
                context={
                    "type": "user_input",
                    "source_text_len": len(text),
                },
                user_marked_important=user_marked_important,
                thread_id=thread_id,
                kind="narrative_summary",
            )
        except Exception as e:
            log_swallowed_exception("crt_rag._maybe_store_longform_summary.store", e)
    def _get_learned_suggestions_for_slots(self, slots: List[str]) -> List[Dict[str, Any]]:
        ls_cfg = (self.runtime_config or {}).get("learned_suggestions", {})
        if not ls_cfg.get("enabled", True):
            return []
        if not ls_cfg.get("emit_metadata", True):
            return []
        if not slots:
            return []
        # If A/B mode is enabled, learned suggestions still emit as usual.
        if not slots:
            return []
        try:
            all_memories = self.memory._load_all_memories()
            user_memories = [m for m in all_memories if m.source == MemorySource.USER]
            open_contras = self.ledger.get_open_contradictions(limit=50)

            def infer_best(slot: str, candidates):
                # candidates: List[(mem, value, normalized)]
                if not candidates:
                    return None, {}
                best_mem, best_val, _norm = max(
                    candidates,
                    key=lambda mv: (
                        1,  # user-only in this caller
                        getattr(mv[0], "timestamp", 0.0),
                        getattr(mv[0], "trust", 0.0),
                    ),
                )
                return best_val, {"memory_id": getattr(best_mem, "memory_id", None)}

            sugg = self.learned_suggestions.suggest_for_slots(
                slots=slots,
                use_model=True,
                all_user_memories=user_memories,
                open_contradictions=open_contras,
                extract_fact_slots_fn=extract_fact_slots,
                infer_best_slot_value_fn=infer_best,
            )
            return [s.to_dict() for s in sugg]
        except Exception:
            return []
    def _get_heuristic_suggestions_for_slots(self, slots: List[str]) -> List[Dict[str, Any]]:
        ls_cfg = (self.runtime_config or {}).get("learned_suggestions", {})
        if not ls_cfg.get("enabled", True):
            return []
        if not ls_cfg.get("emit_ab", False):
            return []
        if not slots:
            return []
        try:
            all_memories = self.memory._load_all_memories()
            user_memories = [m for m in all_memories if m.source == MemorySource.USER]
            open_contras = self.ledger.get_open_contradictions(limit=50)

            def infer_best(slot: str, candidates):
                if not candidates:
                    return None, {}
                best_mem, best_val, _norm = max(
                    candidates,
                    key=lambda mv: (
                        1,
                        getattr(mv[0], "timestamp", 0.0),
                        getattr(mv[0], "trust", 0.0),
                    ),
                )
                return best_val, {"memory_id": getattr(best_mem, "memory_id", None)}

            sugg = self.learned_suggestions.suggest_for_slots(
                slots=slots,
                use_model=False,
                all_user_memories=user_memories,
                open_contradictions=open_contras,
                extract_fact_slots_fn=extract_fact_slots,
                infer_best_slot_value_fn=infer_best,
            )
            return [s.to_dict() for s in sugg]
        except Exception:
            return []
    def query_with_intent(
        self,
        user_query: str,
        user_marked_important: bool = False,
        mode: Optional[ReasoningMode] = None,
        thread_id: Optional[str] = None,
        channel: Optional[str] = None,
        origin: Optional[str] = None,
        authority: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query with IntentRouter + FactStore routing.
        
        This method uses IntentRouter + FactStore for structured routing,
        while preserving all existing CRT memory/contradiction functionality.
        
        Args:
            user_query: The user's input
            user_marked_important: Flag for important facts
            mode: Optional reasoning mode override
            
        Returns:
            Dict with answer, metadata, and trace
        """
        self.clear_trace()
        
        # Classify intent
        if self.intent_router:
            self._trace_step("INTENT", "Classifying...")
            routed = self.intent_router.classify(user_query)
            intent = routed.intent
            confidence = routed.confidence
            self._trace_step("INTENT", f"{intent.value} (confidence: {confidence:.2f})", {
                "intent": intent.value,
                "confidence": confidence,
                "extracted": routed.extracted
            })
        else:
            # Fallback to simple classification
            self._trace_step("INTENT", "Router unavailable, using basic classification")
            intent = Intent.UNKNOWN
            routed = None
        
        # Route based on intent
        result = None
        fact_result = None
        meta_question_cues = (
            "how do you know",
            "how are you sure",
            "how can you be sure",
            "how did you know",
            "how do you remember",
            "where did you learn",
            "how did you learn",
            "explain your process",
            "explain the technical",
            "how does your memory",
            "how does that work",
            "how do you have that",
            "what makes you sure",
            "why are you sure",
            "why do you think",
            "who are you",
            "what are you",
        )
        is_meta_fact_question = any(cue in (user_query or "").lower() for cue in meta_question_cues)
        
        # Handle FACT intents with shared governed-memory write path
        explicit_non_user_fact_kind = bool(kind and str(kind).strip().lower() != "user_fact")
        if (
            intent in [Intent.FACT_STATEMENT, Intent.FACT_CORRECTION]
            and self.fact_store
            and not self.memory.is_social_channel(channel)
            and not explicit_non_user_fact_kind
        ):
            self._trace_step("FACTSTORE", "Preparing fact write...")
            extracted_facts = self.fact_store.extractor.extract(user_query) if self.fact_store else []
            fact_result = {"extracted": [fact.to_dict() for fact in extracted_facts], "updated": []}
            self._trace_step(
                "FACTSTORE",
                f"Detected {len(extracted_facts)} fact candidate(s)",
                fact_result,
            )
            
            # Also run through CRT for contradiction detection
            self._trace_step("CRT", "Checking contradictions...")
            result = self.query(
                user_query,
                user_marked_important,
                mode,
                thread_id=thread_id,
                channel=channel,
                origin=origin,
                authority=authority,
                kind=kind,
            )
            self._trace_step("CRT", f"contradiction_detected: {result.get('contradiction_detected', False)}")
            
            # Format response
            if fact_result.get("extracted"):
                f = fact_result["extracted"][0]
                slot_name = f['slot'].split('.')[-1].replace('_', ' ')
                result['answer'] = f"Got it. I'll remember your {slot_name} is {f['value']}."
            elif fact_result.get("updated"):
                u = fact_result["updated"][0]
                slot_name = u['slot'].split('.')[-1].replace('_', ' ')
                result['answer'] = f"Updated. Your {slot_name} is now {u['to']} (was {u['from']})."
        
        elif intent == Intent.FACT_QUESTION and self.fact_store and not is_meta_fact_question:
            self._trace_step("FACTSTORE", "Looking up fact...")
            fact_answer = self._answer_from_fact_slots(
                self._infer_slots_from_query(user_query),
                user_query=user_query,
                thread_id=thread_id,
                usage_reason="effective_fact_surface",
            )
            self._trace_step("FACTSTORE", f"Answer: {fact_answer or 'None'}")
            
            if fact_answer:
                result = {
                    'answer': fact_answer,
                    'thinking': None,
                    'mode': 'quick',
                    'confidence': 0.95,
                    'response_type': 'belief',
                    'gates_passed': True,
                    'gate_reason': 'effective_fact_surface',
                    'retrieved_memories': [],
                    'fact_store_hit': True,
                }
            else:
                # Fallback to CRT
                self._trace_step("CRT", "No FactStore hit, querying CRT...")
                result = self.query(
                    user_query,
                    user_marked_important,
                    mode,
                    thread_id=thread_id,
                    channel=channel,
                    origin=origin,
                    authority=authority,
                    kind=kind,
                )
                self._trace_step("CRT", f"confidence: {result.get('confidence', 0):.2f}")
        
        elif intent == Intent.META_MEMORY and self.fact_store:
            self._trace_step("FACTSTORE", "Gathering all facts...")
            facts = self.get_effective_user_facts(thread_id=thread_id)
            self._trace_step("FACTSTORE", f"Found {len(facts)} facts")
            
            if facts:
                lines = ["Here's what I know about you:"]
                for slot, f in facts.items():
                    slot_name = self._canonical_user_slot_name(slot).replace('_', ' ')
                    lines.append(f"  - {slot_name}: {f['value']}")
                result = {
                    'answer': "\n".join(lines),
                    'thinking': None,
                    'mode': 'quick',
                    'confidence': 0.95,
                    'response_type': 'belief',
                    'gates_passed': True,
                    'gate_reason': 'fact_inventory',
                    'retrieved_memories': [],
                    'structured_facts': facts,
                }
            else:
                result = {
                    'answer': "I don't know anything about you yet. Tell me something!",
                    'thinking': None,
                    'mode': 'quick',
                    'confidence': 0.95,
                    'response_type': 'speech',
                    'gates_passed': True,
                    'gate_reason': 'empty_fact_store',
                }
        
        else:
            # All other intents: use standard CRT query
            self._trace_step("CRT", f"Routing for intent: {intent.value}")
            result = self.query(
                user_query,
                user_marked_important,
                mode,
                thread_id=thread_id,
                channel=channel,
                origin=origin,
                authority=authority,
                kind=kind,
            )
            self._trace_step("CRT", f"confidence: {result.get('confidence', 0):.2f}")
        
        # Done
        self._trace_step("DONE", "Complete")
        
        # Attach trace to result
        result['trace'] = self.get_trace()
        result['intent'] = intent.value if hasattr(intent, 'value') else str(intent)
        
        return result
    def get_structured_facts(
        self,
        thread_id: Optional[str] = None,
        *,
        scope: str = "thread",
    ) -> Dict[str, Any]:
        """
        Get structured facts from the requested surface.
        
        Returns dict of slot -> {value, trust, source, ...}
        """
        scope_key = str(scope or "thread").strip().lower()
        if scope_key == "effective":
            return self.get_effective_user_facts(thread_id=thread_id)
        if scope_key == "global":
            try:
                global_facts = self.user_profile.get_all_facts() or {}
            except Exception:
                global_facts = {}
            out: Dict[str, Any] = {}
            for slot, fact in global_facts.items():
                if hasattr(self.user_profile, "_is_profile_slot") and not self.user_profile._is_profile_slot(slot):
                    continue
                value = str(getattr(fact, "value", "") or "").strip()
                if not value:
                    continue
                slot_name = self._canonical_user_slot_name(slot)
                out[slot_name] = {
                    "slot": slot_name,
                    "value": value,
                    "source_surface": "global_profile",
                    "source_thread": getattr(fact, "source_thread", None),
                    "authority": "confirmed",
                    "origin": None,
                    "confidence": float(getattr(fact, "confidence", 0.9) or 0.9),
                    "trust": float(getattr(fact, "confidence", 0.9) or 0.9),
                    "timestamp": float(getattr(fact, "timestamp", 0.0) or 0.0),
                    "memory_id": None,
                }
            return out
        if self.fact_store:
            return self.fact_store.get_all_facts(thread_id=thread_id)
        return {}
    def get_fact_history(self, slot: str, thread_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get history for a specific fact slot.
        
        Args:
            slot: The slot name (e.g., 'user.name' or just 'name')
            
        Returns:
            List of historical values with timestamps
        """
        if self.fact_store:
            if not slot.startswith("user."):
                slot = f"user.{slot}"
            return self.fact_store.get_history(slot, thread_id=thread_id)
        return []


    # ================================================================
    # THIN DISPATCHERS — delegate to extracted modules
    # ================================================================

    # ── _tracing.py ──
    def trace_step(self, *args, **kwargs):
        from ._tracing import trace_step; return trace_step(self, *args, **kwargs)
    def enable_tracing(self, *args, **kwargs):
        from ._tracing import enable_tracing; return enable_tracing(self, *args, **kwargs)
    def get_trace(self, *args, **kwargs):
        from ._tracing import get_trace; return get_trace(self, *args, **kwargs)
    def clear_trace(self, *args, **kwargs):
        from ._tracing import clear_trace; return clear_trace(self, *args, **kwargs)
    def get_crt_status(self, *args, **kwargs):
        from ._tracing import get_crt_status; return get_crt_status(self, *args, **kwargs)
    def get_open_contradictions(self, *args, **kwargs):
        from ._tracing import get_open_contradictions; return get_open_contradictions(self, *args, **kwargs)
    def get_reflection_queue(self, *args, **kwargs):
        from ._tracing import get_reflection_queue; return get_reflection_queue(self, *args, **kwargs)

    # ── _security.py ──
    def detect_denial_in_text(self, *args, **kwargs):
        from ._security import detect_denial_in_text; return detect_denial_in_text(self, *args, **kwargs)
    def is_retraction_of_denial(self, *args, **kwargs):
        from ._security import is_retraction_of_denial; return is_retraction_of_denial(self, *args, **kwargs)
    def build_gaslighting_citation(self, *args, **kwargs):
        from ._security import build_gaslighting_citation; return build_gaslighting_citation(self, *args, **kwargs)
    def strip_continuity_augmented_text(self, *args, **kwargs):
        from ._security import strip_continuity_augmented_text; return strip_continuity_augmented_text(self, *args, **kwargs)
    def detect_gaslighting_attempt(self, *args, **kwargs):
        from ._security import detect_gaslighting_attempt; return detect_gaslighting_attempt(self, *args, **kwargs)
    def detect_blindside_attack(self, *args, **kwargs):
        from ._security import detect_blindside_attack; return detect_blindside_attack(self, *args, **kwargs)

    # ── _sanitization.py ──
    def sanitize_memory_denial(self, *args, **kwargs):
        from ._sanitization import sanitize_memory_denial; return sanitize_memory_denial(self, *args, **kwargs)
    def sanitize_unsupported_memory_claims(self, *args, **kwargs):
        from ._sanitization import sanitize_unsupported_memory_claims; return sanitize_unsupported_memory_claims(self, *args, **kwargs)

    # ── _web_search.py ──
    def _is_synthesis_query(self, *args, **kwargs):
        from ._web_search import _is_synthesis_query; return _is_synthesis_query(self, *args, **kwargs)
    def _detect_sentiment_contradiction(self, *args, **kwargs):
        from ._web_search import _detect_sentiment_contradiction; return _detect_sentiment_contradiction(self, *args, **kwargs)
    def _is_copilot_context_query(self, *args, **kwargs):
        from ._web_search import _is_copilot_context_query; return _is_copilot_context_query(self, *args, **kwargs)
    def _fetch_copilot_context(self, *args, **kwargs):
        from ._web_search import _fetch_copilot_context; return _fetch_copilot_context(self, *args, **kwargs)
    def _is_web_search_query(self, *args, **kwargs):
        from ._web_search import _is_web_search_query; return _is_web_search_query(self, *args, **kwargs)
    def _extract_search_query(self, *args, **kwargs):
        from ._web_search import _extract_search_query; return _extract_search_query(self, *args, **kwargs)
    def _fetch_url_content(self, *args, **kwargs):
        from ._web_search import _fetch_url_content; return _fetch_url_content(self, *args, **kwargs)
    def _run_web_search(self, *args, **kwargs):
        from ._web_search import _run_web_search; return _run_web_search(self, *args, **kwargs)
    def _build_web_evidence_packet(self, *args, **kwargs):
        from ._web_search import _build_web_evidence_packet; return _build_web_evidence_packet(self, *args, **kwargs)
    def _format_web_fetch_failed_answer(self, *args, **kwargs):
        from ._web_search import _format_web_fetch_failed_answer; return _format_web_fetch_failed_answer(self, *args, **kwargs)
    def _enforce_web_answer_policy(self, *args, **kwargs):
        from ._web_search import _enforce_web_answer_policy; return _enforce_web_answer_policy(self, *args, **kwargs)
    def _sanitize_web_mode_answer(self, *args, **kwargs):
        from ._web_search import _sanitize_web_mode_answer; return _sanitize_web_mode_answer(self, *args, **kwargs)
    def _is_capability_connector_query(self, *args, **kwargs):
        from ._web_search import _is_capability_connector_query; return _is_capability_connector_query(self, *args, **kwargs)
    def _build_web_fulfillment_answer(self, *args, **kwargs):
        from ._web_search import _build_web_fulfillment_answer; return _build_web_fulfillment_answer(self, *args, **kwargs)

    # ── _classification.py ──
    def _load_classifier(self, *args, **kwargs):
        from ._classification import _load_classifier; return _load_classifier(self, *args, **kwargs)
    def _classify_query_type_ml(self, *args, **kwargs):
        from ._classification import _classify_query_type_ml; return _classify_query_type_ml(self, *args, **kwargs)
    def disambiguate_query(self, *args, **kwargs):
        from ._classification import disambiguate_query; return disambiguate_query(self, *args, **kwargs)
    def _extract_facts_contextual(self, *args, **kwargs):
        from ._classification import _extract_facts_contextual; return _extract_facts_contextual(self, *args, **kwargs)
    def _classify_query_type_heuristic(self, *args, **kwargs):
        from ._classification import _classify_query_type_heuristic; return _classify_query_type_heuristic(self, *args, **kwargs)
    def _compute_grounding_score(self, *args, **kwargs):
        from ._classification import _compute_grounding_score; return _compute_grounding_score(self, *args, **kwargs)
    def _classify_contradiction_severity(self, *args, **kwargs):
        from ._classification import _classify_contradiction_severity; return _classify_contradiction_severity(self, *args, **kwargs)
    def _is_system_prompt_request(self, *args, **kwargs):
        from ._classification import _is_system_prompt_request; return _is_system_prompt_request(self, *args, **kwargs)
    def _is_user_name_declaration(self, *args, **kwargs):
        from ._classification import _is_user_name_declaration; return _is_user_name_declaration(self, *args, **kwargs)
    def _is_user_named_reference_question(self, *args, **kwargs):
        from ._classification import _is_user_named_reference_question; return _is_user_named_reference_question(self, *args, **kwargs)
    def _classify_user_input(self, *args, **kwargs):
        from ._classification import _classify_user_input; return _classify_user_input(self, *args, **kwargs)

    # ── _citation.py ──
    def _fallback_response(self, *args, **kwargs):
        from ._citation import _fallback_response; return _fallback_response(self, *args, **kwargs)
    def _is_memory_citation_request(self, *args, **kwargs):
        from ._citation import _is_memory_citation_request; return _is_memory_citation_request(self, *args, **kwargs)
    def _is_name_history_request(self, *args, **kwargs):
        from ._citation import _is_name_history_request; return _is_name_history_request(self, *args, **kwargs)
    def _is_memory_inventory_request(self, *args, **kwargs):
        from ._citation import _is_memory_inventory_request; return _is_memory_inventory_request(self, *args, **kwargs)
    def _build_memory_inventory_answer(self, *args, **kwargs):
        from ._citation import _build_memory_inventory_answer; return _build_memory_inventory_answer(self, *args, **kwargs)
    def _build_synthesis_answer(self, *args, **kwargs):
        from ._citation import _build_synthesis_answer; return _build_synthesis_answer(self, *args, **kwargs)
    def _build_memory_citation_answer(self, *args, **kwargs):
        from ._citation import _build_memory_citation_answer; return _build_memory_citation_answer(self, *args, **kwargs)
    def _is_contradiction_status_request(self, *args, **kwargs):
        from ._citation import _is_contradiction_status_request; return _is_contradiction_status_request(self, *args, **kwargs)
    def _build_contradiction_status_answer(self, *args, **kwargs):
        from ._citation import _build_contradiction_status_answer; return _build_contradiction_status_answer(self, *args, **kwargs)

    # ── _fact_extraction.py ──
    def _extract_facts_cached(self, *args, **kwargs):
        from ._fact_extraction import _extract_facts_cached; return _extract_facts_cached(self, *args, **kwargs)
    def _extract_facts_two_tier(self, *args, **kwargs):
        from ._fact_extraction import _extract_facts_two_tier; return _extract_facts_two_tier(self, *args, **kwargs)
    @staticmethod
    def _canonical_user_slot_name(*args, **kwargs):
        from ._fact_extraction import _canonical_user_slot_name; return _canonical_user_slot_name(*args, **kwargs)
    def _get_latest_user_slot_value(self, *args, **kwargs):
        from ._fact_extraction import _get_latest_user_slot_value; return _get_latest_user_slot_value(self, *args, **kwargs)
    def _get_latest_user_name_guess(self, *args, **kwargs):
        from ._fact_extraction import _get_latest_user_name_guess; return _get_latest_user_name_guess(self, *args, **kwargs)
    def _query_mentions_user_name(self, *args, **kwargs):
        from ._fact_extraction import _query_mentions_user_name; return _query_mentions_user_name(self, *args, **kwargs)
    def _get_memory_conflicts(self, *args, **kwargs):
        from ._fact_extraction import _get_memory_conflicts; return _get_memory_conflicts(self, *args, **kwargs)
    def _load_thread_user_memories(self, *args, **kwargs):
        from ._fact_extraction import _load_thread_user_memories; return _load_thread_user_memories(self, *args, **kwargs)
    def get_effective_user_facts(self, *args, **kwargs):
        from ._fact_extraction import get_effective_user_facts; return get_effective_user_facts(self, *args, **kwargs)
    def search_effective_user_facts(self, *args, **kwargs):
        from ._fact_extraction import search_effective_user_facts; return search_effective_user_facts(self, *args, **kwargs)
    def _add_reintroduction_flags(self, *args, **kwargs):
        from ._fact_extraction import _add_reintroduction_flags; return _add_reintroduction_flags(self, *args, **kwargs)
    def _flag_reintroduced_claims(self, *args, **kwargs):
        from ._fact_extraction import _flag_reintroduced_claims; return _flag_reintroduced_claims(self, *args, **kwargs)
    def _infer_slots_from_query(self, *args, **kwargs):
        from ._fact_extraction import _infer_slots_from_query; return _infer_slots_from_query(self, *args, **kwargs)
    def _is_assistant_profile_question(self, *args, **kwargs):
        from ._fact_extraction import _is_assistant_profile_question; return _is_assistant_profile_question(self, *args, **kwargs)

    # ── _memory_ops.py ──
    def _record_and_cascade(self, *args, **kwargs):
        from ._memory_ops import _record_and_cascade; return _record_and_cascade(self, *args, **kwargs)
    def _record_profile_replacements(self, *args, **kwargs):
        from ._memory_ops import _record_profile_replacements; return _record_profile_replacements(self, *args, **kwargs)
    def ingest_memory_write(self, *args, **kwargs):
        from ._memory_ops import ingest_memory_write; return ingest_memory_write(self, *args, **kwargs)
    def retrieve(self, *args, **kwargs):
        from ._memory_ops import retrieve; return retrieve(self, *args, **kwargs)

    # ── _answer_gen.py ──
    def _build_user_named_reference_answer(self, *args, **kwargs):
        from ._answer_gen import _build_user_named_reference_answer; return _build_user_named_reference_answer(self, *args, **kwargs)
    def _build_resolved_memory_docs(self, *args, **kwargs):
        from ._answer_gen import _build_resolved_memory_docs; return _build_resolved_memory_docs(self, *args, **kwargs)
    def _build_assistant_profile_answer(self, *args, **kwargs):
        from ._answer_gen import _build_assistant_profile_answer; return _build_assistant_profile_answer(self, *args, **kwargs)
    def _augment_retrieval_with_slot_memories(self, *args, **kwargs):
        from ._answer_gen import _augment_retrieval_with_slot_memories; return _augment_retrieval_with_slot_memories(self, *args, **kwargs)
    def _answer_from_fact_slots(self, *args, **kwargs):
        from ._answer_gen import _answer_from_fact_slots; return _answer_from_fact_slots(self, *args, **kwargs)
    def _get_response_variation_config(self, *args, **kwargs):
        from ._answer_gen import _get_response_variation_config; return _get_response_variation_config(self, *args, **kwargs)
    def _is_response_variation_enabled(self, *args, **kwargs):
        from ._answer_gen import _is_response_variation_enabled; return _is_response_variation_enabled(self, *args, **kwargs)
    def _get_recent_slot_queries(self, *args, **kwargs):
        from ._answer_gen import _get_recent_slot_queries; return _get_recent_slot_queries(self, *args, **kwargs)
    def _generate_varied_slot_answer(self, *args, **kwargs):
        from ._answer_gen import _generate_varied_slot_answer; return _generate_varied_slot_answer(self, *args, **kwargs)
    def _one_line_summary_from_facts(self, *args, **kwargs):
        from ._answer_gen import _one_line_summary_from_facts; return _one_line_summary_from_facts(self, *args, **kwargs)
    def _list_confident_facts_from_slots(self, *args, **kwargs):
        from ._answer_gen import _list_confident_facts_from_slots; return _list_confident_facts_from_slots(self, *args, **kwargs)

    # ── _contradiction.py ──
    def _infer_contradiction_goals_for_query(self, *args, **kwargs):
        from ._contradiction import _infer_contradiction_goals_for_query; return _infer_contradiction_goals_for_query(self, *args, **kwargs)
    def _extract_value_from_memory_text(self, *args, **kwargs):
        from ._contradiction import _extract_value_from_memory_text; return _extract_value_from_memory_text(self, *args, **kwargs)
    def _build_caveat_disclosure(self, *args, **kwargs):
        from ._contradiction import _build_caveat_disclosure; return _build_caveat_disclosure(self, *args, **kwargs)
    def _build_mandatory_caveat(self, *args, **kwargs):
        from ._contradiction import _build_mandatory_caveat; return _build_mandatory_caveat(self, *args, **kwargs)
    def _answer_has_caveat(self, *args, **kwargs):
        from ._contradiction import _answer_has_caveat; return _answer_has_caveat(self, *args, **kwargs)
    def _resolve_contradiction_assertively(self, *args, **kwargs):
        from ._contradiction import _resolve_contradiction_assertively; return _resolve_contradiction_assertively(self, *args, **kwargs)
    def _check_contradiction_gates(self, *args, **kwargs):
        from ._contradiction import _check_contradiction_gates; return _check_contradiction_gates(self, *args, **kwargs)
    def _get_memory_by_id(self, *args, **kwargs):
        from ._contradiction import _get_memory_by_id; return _get_memory_by_id(self, *args, **kwargs)
    def _trigger_cascade_propagation(self, *args, **kwargs):
        from ._contradiction import _trigger_cascade_propagation; return _trigger_cascade_propagation(self, *args, **kwargs)
    def _check_all_fact_contradictions_ml(self, *args, **kwargs):
        from ._contradiction import _check_all_fact_contradictions_ml; return _check_all_fact_contradictions_ml(self, *args, **kwargs)
    def _check_semantic_contradiction(self, *args, **kwargs):
        from ._contradiction import _check_semantic_contradiction; return _check_semantic_contradiction(self, *args, **kwargs)
    def _track_implicit_confirmations(self, *args, **kwargs):
        from ._contradiction import _track_implicit_confirmations; return _track_implicit_confirmations(self, *args, **kwargs)
    def _resolve_open_conflicts_from_assertion(self, *args, **kwargs):
        from ._contradiction import _resolve_open_conflicts_from_assertion; return _resolve_open_conflicts_from_assertion(self, *args, **kwargs)
    def _detect_and_resolve_nl_resolution(self, *args, **kwargs):
        from ._contradiction import _detect_and_resolve_nl_resolution; return _detect_and_resolve_nl_resolution(self, *args, **kwargs)

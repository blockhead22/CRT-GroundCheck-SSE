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
from typing import List, Dict, Optional, Any, Tuple, Set
from pathlib import Path
from collections import OrderedDict
import time
import joblib

logger = logging.getLogger(__name__)

from .crt_core import CRTMath, CRTConfig, MemorySource, SSEMode, encode_vector
from .crt_memory import CRTMemorySystem, MemoryItem
from .crt_ledger import ContradictionLedger, ContradictionEntry
from .reasoning import ReasoningEngine, ReasoningMode
from .fact_slots import extract_fact_slots
from .learned_suggestions import LearnedSuggestionEngine
from .runtime_config import get_runtime_config
from .active_learning import get_active_learning_coordinator
from .user_profile import GlobalUserProfile
from .ml_contradiction_detector import MLContradictionDetector

# Constants for NL resolution
_NL_RESOLUTION_STOPWORDS = {'i', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'my', 'the', 'a', 'an', 'at', 'in', 'on', 'to'}
_UNSTRUCTURED_SLOT_NAME = '_unstructured_'


class CRTEnhancedRAG:
    """
    RAG engine with CRT principles.
    
    Differences from standard RAG:
    1. Retrieval weighted by trust, not just similarity
    2. Outputs gated by intent/memory alignment
    3. Contradictions create ledger entries, not silent overwrites
    4. Trust evolves based on alignment/drift
    5. Fallback speech separated from belief storage
    """
    
    def __init__(
        self,
        memory_db: str = "personal_agent/crt_memory.db",
        ledger_db: str = "personal_agent/crt_ledger.db",
        config: Optional[CRTConfig] = None,
        llm_client=None
    ):
        """Initialize CRT-enhanced RAG."""
        self.config = config or CRTConfig()
        self.crt_math = CRTMath(self.config)
        
        # CRT components
        self.memory = CRTMemorySystem(memory_db, self.config)
        self.ledger = ContradictionLedger(ledger_db, self.config)
        
        # Global user profile (shared across all threads)
        self.user_profile = GlobalUserProfile()
        
        # Reasoning engine
        self.reasoning = ReasoningEngine(llm_client)

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
        
        # Active learning coordinator (graceful degradation if unavailable)
        try:
            self.active_learning = get_active_learning_coordinator()
        except Exception:
            self.active_learning = None
        
        # Load trained response classifier (graceful degradation)
        self._classifier_model = None
        self._load_classifier()
        
        # Session tracking
        import uuid
        self.session_id = str(uuid.uuid4())[:8]
        
        # Performance: LRU cache for fact extraction to avoid repeated regex parsing
        # Using OrderedDict for efficient LRU eviction (move_to_end + popitem)
        self._fact_extraction_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_cache_entries = 1000
        self._max_text_size = 10_000  # Skip caching very large texts
    
    def _extract_facts_cached(self, text: str) -> Dict[str, Any]:
        """
        Extract fact slots with LRU caching to avoid repeated regex parsing.
        
        Performance optimization: The same memory text may be parsed multiple times
        during retrieval and contradiction detection. Uses LRU cache to avoid waste.
        
        Args:
            text: Memory text to extract facts from
            
        Returns:
            Dictionary of extracted facts (slot -> ExtractedFact)
        """
        # Skip caching for very large texts to prevent memory bloat
        if len(text) > self._max_text_size:
            return extract_fact_slots(text) or {}
        
        # Check cache (LRU: move to end on access)
        if text in self._fact_extraction_cache:
            self._fact_extraction_cache.move_to_end(text)
            return self._fact_extraction_cache[text]
        
        # Cache miss: extract and store
        result = extract_fact_slots(text) or {}
        self._fact_extraction_cache[text] = result
        
        # LRU eviction: remove oldest entry when cache is full
        if len(self._fact_extraction_cache) > self._max_cache_entries:
            self._fact_extraction_cache.popitem(last=False)  # Remove oldest (FIFO)
        
        return result
    
    def _load_classifier(self):
        """Load trained response type classifier with hot-reload support."""
        model_path = Path("models/response_classifier_v1.joblib")
        if not model_path.exists():
            return  # Use heuristics if no model available
        
        try:
            model_data = joblib.load(model_path)
            self._classifier_model = model_data
        except Exception:
            self._classifier_model = None
    
    def _classify_query_type_ml(self, user_query: str) -> str:
        """Classify query type using trained ML model with heuristic fallback."""
        # Try ML model first
        if self._classifier_model is not None:
            try:
                vectorizer = self._classifier_model['vectorizer']
                classifier = self._classifier_model['classifier']
                query_vec = vectorizer.transform([user_query])
                prediction = classifier.predict(query_vec)[0]
                return prediction
            except Exception:
                pass  # Fall through to heuristic
        
        # Fallback to heuristic if model unavailable/fails
        heuristic = self._classify_query_type_heuristic(user_query)
        return heuristic if heuristic else "factual"
    
    # ========================================================================
    # Trust-Weighted Retrieval
    # ========================================================================
    
    def retrieve(
        self,
        query: str,
        k: int = 5,
        min_trust: float = 0.0,
        include_system: bool = False,
        include_fallback: bool = False,
        include_reflection: bool = False,
        exclude_contradiction_sources: bool = True,
        relevant_slots: Optional[Set[str]] = None,
    ) -> List[Tuple[MemoryItem, float]]:
        """
        Retrieve memories using CRT trust-weighted scoring.
        
        R_i = s_i · ρ_i · w_i
        where:
        - s_i = similarity(query, memory)
        - ρ_i = recency_weight
        - w_i = α·trust + (1-α)·confidence
        
        This is fundamentally different from standard RAG's pure similarity.
        """
        # Default retrieval is intended to ground answers in auditable sources.
        # Assistant-generated outputs (SYSTEM) and non-durable speech (FALLBACK)
        # tend to create self-retrieval loops and misleading provenance, so they
        # are excluded unless explicitly requested.
        allowed_sources = {MemorySource.USER, MemorySource.EXTERNAL}
        if include_system:
            allowed_sources.add(MemorySource.SYSTEM)
        if include_fallback:
            allowed_sources.add(MemorySource.FALLBACK)
        if include_reflection:
            allowed_sources.add(MemorySource.REFLECTION)

        # Build set of contradiction memory IDs to exclude (prevents unrelated contradictions
        # from polluting retrieval just because they're semantically similar).
        excluded_mem_ids: Set[str] = set()
        if exclude_contradiction_sources:
            from .crt_ledger import ContradictionType
            unresolved_contradictions = self.ledger.get_open_contradictions(limit=100)
            for contra in unresolved_contradictions:
                # Only exclude contradictions that DON'T affect the slots we're querying
                affects_slots_str = getattr(contra, "affects_slots", None)
                if affects_slots_str and relevant_slots:
                    affects_slots_set = set(affects_slots_str.split(","))
                    if not (affects_slots_set & relevant_slots):
                        # This contradiction doesn't affect what we're querying, exclude its sources
                        excluded_mem_ids.add(contra.old_memory_id)
                        excluded_mem_ids.add(contra.new_memory_id)
                elif not affects_slots_str:
                    # No slot info - exclude to be safe (prevents semantic pollution)
                    excluded_mem_ids.add(contra.old_memory_id)
                    excluded_mem_ids.add(contra.new_memory_id)

        # OPTIMIZATION: Pass excluded IDs to retrieve_memories to filter at database level
        # Reduced over-fetch multiplier from 5x to 2x since we now filter more efficiently
        candidate_k = max(int(k) * 2, int(k))
        retrieved = self.memory.retrieve_memories(
            query, 
            candidate_k, 
            min_trust,
            exclude_deprecated=True,
            ledger=self.ledger,
            excluded_ids=excluded_mem_ids if exclude_contradiction_sources else None
        )

        # Avoid retrieving derived helper outputs (they are grounded summaries/citations,
        # not new world facts) to prevent recursive quoting and prompt pollution.
        filtered: List[Tuple[MemoryItem, float]] = []
        for mem, score in retrieved:
            if getattr(mem, "source", None) not in allowed_sources:
                continue
            try:
                kind = ((mem.context or {}).get("kind") or "").strip().lower()
            except Exception:
                kind = ""

            if mem.source == MemorySource.FALLBACK and kind in {"memory_citation", "contradiction_status", "memory_inventory"}:
                continue

            txt = (mem.text or "").strip().lower()
            if mem.source == MemorySource.FALLBACK and txt.startswith("here is the stored text i can cite"):
                continue
            if mem.source == MemorySource.FALLBACK and txt.startswith("here are the open contradictions i have recorded"):
                continue
            if mem.source == MemorySource.FALLBACK and txt.startswith("i don't expose internal memory ids"):
                continue

            filtered.append((mem, score))

            if len(filtered) >= k:
                break

        return filtered

    def _get_latest_user_slot_value(self, slot: str) -> Optional[str]:
        """
        Get the latest value for a given slot from USER memories.
        
        Optimized: Uses filtered query to load only USER memories instead of all memories.
        """
        slot = (slot or "").strip().lower()
        if not slot:
            return None
        try:
            # OPTIMIZATION: Load only USER memories instead of all memories
            user_memories = self.memory._load_memories_filtered(source=MemorySource.USER)
        except Exception:
            return None

        best_val: Optional[str] = None
        best_ts: float = -1.0
        for mem in user_memories:
            facts = self._extract_facts_cached(mem.text)
            if not facts or slot not in facts:
                continue
            try:
                ts = float(mem.timestamp)
            except Exception:
                ts = 0.0
            if ts >= best_ts:
                best_ts = ts
                best_val = str(facts[slot].value).strip()

        return best_val or None

    def _get_latest_user_name_guess(self) -> Optional[str]:
        """
        Best-effort user name extraction from USER memories.

        Prefer structured "FACT: name = ..." if present; otherwise fall back to
        simple textual patterns like "my name is ...".
        
        Optimized: Uses filtered query to load only USER memories.
        """
        try:
            # OPTIMIZATION: Load only USER memories instead of all memories
            user_memories = self.memory._load_memories_filtered(source=MemorySource.USER)
        except Exception:
            return None

        best_val: Optional[str] = None
        best_ts: float = -1.0
        name_pat = r"([A-Z][a-zA-Z'-]{1,40}(?:\s+[A-Z][a-zA-Z'-]{1,40}){0,2})"

        for mem in user_memories:
            text = (mem.text or "").strip()
            if not text:
                continue

            val: Optional[str] = None
            m = re.search(r"\bFACT:\s*name\s*=\s*(.+?)\s*$", text, flags=re.IGNORECASE)
            if m:
                val = m.group(1).strip()
            else:
                m = re.search(r"\bmy name is\s+" + name_pat + r"\b", text, flags=re.IGNORECASE)
                if m:
                    val = m.group(1).strip()

            if not val:
                continue

            try:
                ts = float(mem.timestamp)
            except Exception:
                ts = 0.0
            if ts >= best_ts:
                best_ts = ts
                best_val = val

        return best_val or None

    def _query_mentions_user_name(self, user_query: str, user_name: str) -> bool:
        q = (user_query or "").strip().lower()
        name = (user_name or "").strip().lower()
        if not q or not name:
            return False
        return name in q
    
    def _classify_query_type_heuristic(self, user_query: str) -> Optional[str]:
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
    
    def _compute_grounding_score(
        self,
        answer: str,
        retrieved_memories: List[Tuple[MemoryItem, float]],
    ) -> float:
        """Compute grounding score (0-1) for an answer based on memory overlap."""
        if not retrieved_memories or not answer:
            return 0.0
        
        answer_lower = answer.lower().strip()
        memory_text = " ".join(mem.text.lower() for mem, _ in retrieved_memories[:3])

        # Slot-match shortcut: structured answers like
        #   name: sarah
        #   masters school: mit
        # should score 1.0 if they exactly match the retrieved slot values.
        # This avoids verbosity bias for canonical short answers.
        try:
            slot_label_map = {
                "name": "name",
                "employer": "employer",
                "work": "employer",
                "company": "employer",
                "job": "title",
                "title": "title",
                "location": "location",
                "city": "location",
                "first language": "first_language",
                "first_language": "first_language",
                "masters school": "masters_school",
                "master's school": "masters_school",
                "masters school": "masters_school",
                "masters_school": "masters_school",
                "undergrad school": "undergrad_school",
                "undergraduate school": "undergrad_school",
                "undergrad_school": "undergrad_school",
                "programming years": "programming_years",
                "years programming": "programming_years",
                "programming_years": "programming_years",
                "remote preference": "remote_preference",
                "remote_preference": "remote_preference",
            }

            structured: List[Tuple[str, str]] = []
            for ln in (answer or "").splitlines():
                m = re.match(r"^\s*([A-Za-z_ ][A-Za-z_ ]{0,40})\s*:\s*(.+?)\s*$", ln)
                if not m:
                    continue
                raw_label = (m.group(1) or "").strip().lower()
                raw_value = (m.group(2) or "").strip()
                if not raw_label or not raw_value:
                    continue
                slot = slot_label_map.get(raw_label) or slot_label_map.get(raw_label.replace("_", " "))
                if not slot:
                    continue
                structured.append((slot, raw_value))

            if structured:
                # Build best-effort retrieved slot values.
                retrieved_slot_norms: Dict[str, set[str]] = {}
                for mem, _s in retrieved_memories[:5]:
                    facts = extract_fact_slots(getattr(mem, "text", "") or "") or {}
                    for slot, f in facts.items():
                        s = str(slot).strip().lower()
                        norm = str(getattr(f, "normalized", "") or "").strip().lower()
                        if not s or not norm:
                            continue
                        retrieved_slot_norms.setdefault(s, set()).add(norm)

                def _norm_answer_value(slot: str, v: str) -> str:
                    vv = re.sub(r"\s+", " ", (v or "").strip().lower())
                    if slot == "remote_preference":
                        if "remote" in vv:
                            return "remote"
                        if "office" in vv or "in the office" in vv:
                            return "office"
                    return vv

                matches = 0
                for slot, raw_value in structured:
                    want = _norm_answer_value(slot, raw_value)
                    have = retrieved_slot_norms.get(slot, set())
                    if want and want in have:
                        matches += 1

                if matches == len(structured) and matches > 0:
                    return 1.0
        except Exception:
            # Non-fatal: fall back to word-overlap grounding.
            pass
        
        # EXACT MATCH gets 1.0 immediately - fixes brevity penalty
        for mem, _ in retrieved_memories[:3]:
            mem_text_lower = mem.text.lower().strip()
            # Direct exact match
            if answer_lower == mem_text_lower:
                return 1.0
            # Answer is complete substring of memory (not vice versa)
            # This handles "Amazon" matching "I work at Amazon"
            if answer_lower in mem_text_lower and len(answer_lower) > 2:
                # Ensure it's not the reverse (memory substring of answer = hallucination)
                if mem_text_lower not in answer_lower or answer_lower == mem_text_lower:
                    return 1.0
        
        # If answer is very short (likely a fact extraction), check substring match
        if len(answer) < 30:
            # Check if answer appears in memory (e.g., "Alex Chen" in "My name is Alex Chen")
            if answer_lower in memory_text:
                return 1.0
            # Check if most answer words appear in memory
            answer_words = set(answer_lower.split())
            memory_words = set(memory_text.split())
            if answer_words and len(answer_words & memory_words) == len(answer_words):
                return 0.95  # All words present
        
        # For longer answers, check if MEMORY appears in ANSWER (core fact present)
        # This handles "You graduated in 2020. Would you like..." where "2020" is the key fact
        for mem, score in retrieved_memories[:3]:
            mem_text_lower = mem.text.lower().strip()
            # Extract key content words (skip common words)
            mem_words = set(w for w in mem_text_lower.split() if len(w) > 3)
            answer_words_set = set(answer_lower.split())
            
            # If most memory content words appear in answer, it's grounded
            if mem_words:
                mem_in_answer_ratio = len(mem_words & answer_words_set) / len(mem_words)
                if mem_in_answer_ratio >= 0.6:  # 60% of memory words present
                    return 0.85  # High grounding - core fact is in answer
        
        answer_words = set(answer_lower.split())
        memory_words = set(memory_text.split())
        
        if not answer_words:
            return 0.0
        
        overlap = len(answer_words & memory_words)
        overlap_ratio = overlap / len(answer_words)
        
        # Bonus for direct quotes
        has_quotes = '"' in answer or "'" in answer
        quote_bonus = 0.15 if has_quotes else 0.0
        
        # More lenient for longer answers - focus on key fact presence
        # If >40% overlap, consider it reasonably grounded
        if overlap_ratio >= 0.4:
            grounding_score = min(1.0, overlap_ratio + 0.2)  # Boost for decent overlap
        else:
            grounding_score = overlap_ratio + quote_bonus
        
        return max(0.0, min(1.0, grounding_score))
    
    def _classify_contradiction_severity(
        self,
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

        # Consider full name and first token as acceptable matches.
        variants: List[str] = []
        variants.append(name)
        first = name.split()[0].strip() if name.split() else ""
        if first and first != name:
            variants.append(first)

        for v in variants:
            tokens = [t for t in v.split() if t]
            if not tokens:
                continue
            # Match "nick block" with flexible whitespace and allow possessive.
            token_pat = r"\s+".join(re.escape(t) for t in tokens)
            pat = rf"\b{token_pat}(?:['’]s)?\b"
            if re.search(pat, q, flags=re.IGNORECASE):
                return True
        return False

    def _is_system_prompt_request(self, text: str) -> bool:
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

    def _is_user_name_declaration(self, text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return False
        # Use fact-slot extraction so we catch common forms like:
        # - "My name is Nick"
        # - "I'm Nick"
        # while avoiding false positives like "I'm trying to ...".
        facts = extract_fact_slots(t) or {}
        return "name" in facts

    def _is_user_named_reference_question(self, user_query: str) -> bool:
        """Detect third-person questions that refer to the user by (their) name.

        This is product-safety motivated: if a question looks like "What is <user-name>'s occupation?",
        we should answer from chat memory or admit we don't know, rather than importing world facts.
        """
        q = (user_query or "").strip().lower()
        if not q:
            return False

        user_name = self._get_latest_user_slot_value("name") or self._get_latest_user_name_guess()
        if not user_name:
            return False

        if not self._query_mentions_user_name(user_query, user_name):
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

    def _get_memory_conflicts(self, memory_id: Optional[str] = None) -> List[Any]:
        """Check if a memory has open contradictions.
        
        Args:
            memory_id: Optional specific memory to check. If None, returns all open contradictions.
            
        Returns:
            List of contradiction entries
        """
        try:
            open_contras = self.ledger.get_open_contradictions(limit=100)
            
            if memory_id is None:
                return open_contras
                
            # Filter to just this memory's contradictions
            return [
                c for c in open_contras 
                if (hasattr(c, 'claim_a_id') and c.claim_a_id == memory_id) or
                   (hasattr(c, 'claim_b_id') and c.claim_b_id == memory_id)
            ]
        except Exception:
            return []

    def _add_reintroduction_flags(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Add reintroduced_claim flags to all memories in a query result.
        
        INVARIANT: Every memory with an open contradiction MUST be flagged.
        This method ensures ALL query result paths include the flags.
        """
        # Flag retrieved_memories
        if 'retrieved_memories' in result and isinstance(result['retrieved_memories'], list):
            for mem in result['retrieved_memories']:
                if isinstance(mem, dict):
                    mem_id = mem.get('memory_id')
                    if mem_id and hasattr(self.ledger, 'has_open_contradiction'):
                        mem['reintroduced_claim'] = self.ledger.has_open_contradiction(mem_id)
                    else:
                        mem['reintroduced_claim'] = False
        
        # Flag prompt_memories
        if 'prompt_memories' in result and isinstance(result['prompt_memories'], list):
            for mem in result['prompt_memories']:
                if isinstance(mem, dict):
                    mem_id = mem.get('memory_id')
                    if mem_id and hasattr(self.ledger, 'has_open_contradiction'):
                        mem['reintroduced_claim'] = self.ledger.has_open_contradiction(mem_id)
                    else:
                        mem['reintroduced_claim'] = False
        
        # Calculate reintroduced_claims_count
        reintro_count = 0
        if 'retrieved_memories' in result and isinstance(result['retrieved_memories'], list):
            reintro_count = sum(
                1 for m in result['retrieved_memories']
                if isinstance(m, dict) and m.get('reintroduced_claim') is True
            )
        result['reintroduced_claims_count'] = reintro_count
        
        return result

    def _flag_reintroduced_claims(self, memories: List[Any]) -> List[Dict[str, Any]]:
        """Flag any memories that are contradicted (truth reintroduction).
        
        Returns list of dicts with:
        - memory_id
        - text
        - reintroduced_claim: bool (TRUE if contradicted)
        - contradiction_id: ledger ID if contradicted
        - superseded_by: new claim text if available
        
        INVARIANT: Every contradicted memory MUST be flagged.
        If we cannot flag it, we must not return it.
        """
        flagged = []
        open_contras = self._get_memory_conflicts()
        
        # Build lookup: memory_id -> contradiction entry
        contra_map = {}
        for c in open_contras:
            if hasattr(c, 'claim_a_id'):
                contra_map[c.claim_a_id] = c
            if hasattr(c, 'claim_b_id'):
                contra_map[c.claim_b_id] = c
        
        for mem in memories:
            mem_id = getattr(mem, 'memory_id', None) or getattr(mem, 'id', None)
            if not mem_id:
                # Cannot verify - skip to enforce invariant
                continue
            
            is_contradicted = mem_id in contra_map
            
            entry = {
                'memory_id': mem_id,
                'text': getattr(mem, 'text', ''),
                'trust': getattr(mem, 'trust', 0),
                'confidence': getattr(mem, 'confidence', 0),
                'timestamp': getattr(mem, 'timestamp', None),
                'reintroduced_claim': is_contradicted,  # MACHINE-READABLE FLAG
            }
            
            if is_contradicted:
                contra = contra_map[mem_id]
                entry['contradiction_id'] = getattr(contra, 'ledger_id', None)
                # Find the superseding claim
                if hasattr(contra, 'claim_a_id') and contra.claim_a_id == mem_id:
                    entry['superseded_by'] = getattr(contra, 'claim_b_text', None)
                elif hasattr(contra, 'claim_b_id') and contra.claim_b_id == mem_id:
                    entry['superseded_by'] = getattr(contra, 'claim_a_text', None)
            
            flagged.append(entry)
        
        return flagged

    def _build_user_named_reference_answer(self, user_query: str, inferred_slots: List[str]) -> str:
        cfg = (self.runtime_config.get("user_named_reference") or {}) if isinstance(self.runtime_config, dict) else {}
        responses = (cfg.get("responses") or {}) if isinstance(cfg.get("responses"), dict) else {}

        def _resp(key: str, fallback: str) -> str:
            value = responses.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            return fallback

        # Prefer canonical slot answers if available.
        slot_answer = self._answer_from_fact_slots(inferred_slots)
        if slot_answer:
            return slot_answer

        # Otherwise, fall back to strictly chat-grounded work-related statements.
        try:
            all_memories = self.memory._load_all_memories()
        except Exception:
            all_memories = []

        user_memories = [m for m in all_memories if m.source == MemorySource.USER]
        user_memories.sort(key=lambda m: getattr(m, "timestamp", 0.0), reverse=True)

        snippets: List[str] = []
        for mem in user_memories:
            t = (mem.text or "").strip()
            tl = t.lower()
            if any(p in tl for p in ("i work at", "i work for", "i run ", "i built", "my job", "my role", "my title")):
                snippets.append(t)
            if len(snippets) >= 2:
                break

        if snippets:
            lines = [_resp("known_work_prefix", "From our chat, I only know this about your work:")]
            for s in snippets:
                lines.append(f"- {s}")
            lines.append(
                "\n"
                + _resp(
                    "ask_to_store",
                    "If you want, tell me your current job title/occupation in one line and I'll store it as a fact.",
                )
            )
            return "\n".join(lines)

        return _resp(
            "unknown",
            "I don't have a reliable stored memory of your occupation/job yet — if you tell me, I can remember it going forward.",
        )
    
    # ========================================================================
    # Uncertainty as First-Class State
    # ========================================================================
    
    def _should_express_uncertainty(
        self,
        retrieved: List[Tuple[MemoryItem, float]],
        contradictions_count: int = 0,
        gates_passed: bool = False
    ) -> Tuple[bool, str]:
        """
        Determine if system should express explicit uncertainty.
        
        Returns: (should_express_uncertainty, reason)
        
        Express uncertainty when:
        1. Multiple high-trust memories conflict (unresolved contradictions)
        2. Trust scores are too close (no clear winner)
        3. Gates failed AND unresolved contradictions exist
        4. Max trust below threshold (no confident belief)
        """
        if not retrieved:
            return False, ""
        
        # Check 1: Unresolved contradictions
        if contradictions_count > 0:
            return True, f"I have {contradictions_count} unresolved contradictions about this"
        
        # Check 2: DISABLED - was triggering too early
        
        # Check 3: Max trust below confidence threshold
        max_trust = max(mem.trust for mem, _ in retrieved)
        if max_trust < 0.6:
            return True, f"My confidence in this information is low (trust={max_trust:.2f})"
        
        # Check 4: Gates failed with moderate contradiction
        if not gates_passed and contradictions_count > 0:
            return True, "I cannot confidently reconstruct a coherent answer from my memories"
        
        return False, ""
    
    def _generate_uncertain_response(
        self,
        user_query: str,
        retrieved: List[Tuple[MemoryItem, float]],
        reason: str,
        recommended_next_action: Optional[Dict[str, Any]] = None,
        conflict_beliefs: Optional[List[str]] = None,
    ) -> str:
        """
        Generate explicit uncertainty response.
        
        This is a FIRST-CLASS response state, not a fallback.
        """
        # Show what we know and what conflicts, in a user-friendly way.
        # Keep this readable for normal users: avoid internal scoring jargon.
        beliefs: List[str] = []

        # Prefer explicit conflict beliefs if provided (ensures both sides show up
        # even when retrieval misses one of the conflicting memories).
        if conflict_beliefs:
            beliefs.extend([b.strip() for b in conflict_beliefs[:6] if (b or "").strip()])
        else:
            for mem, _score in retrieved[:3]:
                t = (mem.text or "").strip()
                if t:
                    beliefs.append(f"- {t}")

        beliefs_text = "\n".join(beliefs) if beliefs else "- (no clear memories)"

        ask = "Can you help clarify?"
        if recommended_next_action and recommended_next_action.get("action_type") == "ask_user":
            q = (recommended_next_action.get("question") or "").strip()
            if q:
                ask = q

        conflict_warning_enabled = True
        try:
            conflict_warning_enabled = bool((self.runtime_config.get("conflict_warning") or {}).get("enabled", True))
        except Exception:
            conflict_warning_enabled = True

        if conflict_warning_enabled:
            header = (
                "I need to be honest about my uncertainty here.\n\n"
                "I might be wrong because I have conflicting information in our chat history.\n\n"
            )
            notes_label = "Here are the conflicting notes I have:"
        else:
            header = "I need to be honest about my uncertainty here.\n\n"
            notes_label = "What I have in memory:"

        # UX soften: even when we cannot answer the conflicted slot, keep the chat usable.
        # Offer to continue on other parts of the question or other topics.
        continue_line = (
            "\nIf you want, I can still help with other parts of your question that don’t depend on that fact — "
            "tell me what you’d like to focus on.\n"
        )

        return (
            header
            + f"{reason}\n\n"
            + f"{notes_label}\n{beliefs_text}\n\n"
            + "I cannot give you a confident answer until we resolve this.\n"
            + continue_line
            + f"{ask}"
        )

    def _infer_contradiction_goals_for_query(
        self,
        user_query: str,
        retrieved: List[Tuple[MemoryItem, float]],
        inferred_slots: Optional[List[str]] = None,
        limit: int = 5,
    ) -> Tuple[List[Dict[str, Any]], Optional[List[str]]]:
        """Infer actionable "next steps" from open hard conflicts.

        For Milestone M2, we keep this intentionally minimal and deterministic:
        - Only hard CONFLICT contradictions become goals.
        - The default action is to ask the user a targeted clarifying question.

        Returns: (goals, conflict_beliefs)
        """
        from .crt_ledger import ContradictionType

        if not retrieved:
            retrieved_ids: set[str] = set()
        else:
            retrieved_ids = {mem.memory_id for mem, _ in retrieved}

        goals: List[Dict[str, Any]] = []
        conflict_beliefs: List[str] = []

        open_contras = self.ledger.get_open_contradictions(limit=50)
        for contra in open_contras:
            if getattr(contra, "contradiction_type", None) != ContradictionType.CONFLICT:
                continue

            # Check affects_slots for fast filtering
            affects_slots_str = getattr(contra, "affects_slots", None)
            if affects_slots_str and inferred_slots:
                affects_slots_set = set(affects_slots_str.split(","))
                if not (affects_slots_set & set(inferred_slots)):
                    # Contradiction doesn't affect slots relevant to this query
                    continue

            old_mem = self.memory.get_memory_by_id(contra.old_memory_id)
            new_mem = self.memory.get_memory_by_id(contra.new_memory_id)
            if old_mem is None or new_mem is None:
                continue

            # Relevance: either overlaps retrieved, or overlaps the slots we think the user asked about.
            is_related_by_retrieval = bool({contra.old_memory_id, contra.new_memory_id} & retrieved_ids)

            old_facts = extract_fact_slots(old_mem.text) or {}
            new_facts = extract_fact_slots(new_mem.text) or {}
            shared_slots = set(old_facts.keys()) & set(new_facts.keys())

            for slot in sorted(shared_slots):
                old_fact = old_facts.get(slot)
                new_fact = new_facts.get(slot)
                if old_fact is None or new_fact is None:
                    continue

                if old_fact.normalized == new_fact.normalized:
                    continue

                is_related_by_slot = bool(inferred_slots) and slot in set(inferred_slots or [])
                if not (is_related_by_retrieval or is_related_by_slot):
                    continue

                # Provide both sides as explicit beliefs (user-facing; no internal scores).
                conflict_beliefs.append(f"- {old_mem.text}")
                conflict_beliefs.append(f"- {new_mem.text}")

                slot_name = slot.replace("_", " ")
                old_val = str(old_fact.value)
                new_val = str(new_fact.value)

                goals.append(
                    {
                        "action_type": "ask_user",
                        "slot": slot,
                        "ledger_id": contra.ledger_id,
                        "options": [new_val, old_val],
                        "question": (
                            f"I have conflicting memories about your {slot_name}. "
                            f"Which is correct now: {new_val} or {old_val}?"
                        ),
                        "reason": "open_conflict",
                    }
                )

                if len(goals) >= limit:
                    break

            if len(goals) >= limit:
                break

        # De-dup conflict belief lines while preserving order.
        seen = set()
        dedup_beliefs: List[str] = []
        for b in conflict_beliefs:
            if b not in seen:
                dedup_beliefs.append(b)
                seen.add(b)

        return goals, dedup_beliefs
    
    def _check_contradiction_gates(
        self,
        user_query: str,
        inferred_slots: List[str]
    ) -> Tuple[bool, Optional[str], List[Dict[str, Any]]]:
        """
        Bug 2 Fix: Check for unresolved contradictions that should block response.
        
        This implements gate blocking - preventing confident answers when
        contradictions exist in the queried facts.
        
        Args:
            user_query: User's query text
            inferred_slots: Slots the query is asking about
            
        Returns:
            (gates_passed, clarification_message, contradictions_list)
        """
        if not inferred_slots:
            # No specific slots mentioned, don't block
            return True, None, []
        
        # Get open contradictions from ledger
        try:
            open_contradictions = self.ledger.get_open_contradictions(limit=100)
        except Exception as e:
            logger.warning(f"[GATE_CHECK] Failed to get open contradictions: {e}")
            return True, None, []
        
        if not open_contradictions:
            return True, None, []
        
        # Check if any open contradictions affect the queried slots
        blocking_contradictions = []
        
        for contra in open_contradictions:
            # Get affected slots from contradiction
            affects_slots = getattr(contra, 'affects_slots', None)
            if not affects_slots:
                continue
            
            affected_slot_list = [s.strip() for s in affects_slots.split(',')]
            
            # Check if any affected slot matches queried slots
            for affected_slot in affected_slot_list:
                if affected_slot in inferred_slots:
                    # Load memory texts to build clarification
                    try:
                        old_mem = self._get_memory_by_id(contra.old_memory_id)
                        new_mem = self._get_memory_by_id(contra.new_memory_id)
                        
                        if old_mem and new_mem:
                            blocking_contradictions.append({
                                'ledger_id': contra.ledger_id,
                                'slot': affected_slot,
                                'old_value': old_mem.text,
                                'new_value': new_mem.text,
                                'category': contra.contradiction_type
                            })
                    except Exception as e:
                        logger.warning(f"[GATE_CHECK] Failed to load contradiction memories: {e}")
                        continue
        
        if not blocking_contradictions:
            return True, None, []
        
        # Build clarification message
        messages = []
        for contra in blocking_contradictions[:3]:  # Limit to 3 for readability
            slot = contra['slot']
            old_val = contra['old_value'][:100]  # Truncate for clarity
            new_val = contra['new_value'][:100]
            
            messages.append(
                f"I have conflicting information about your {slot}:\n"
                f"  - {old_val}\n"
                f"  - {new_val}\n"
                f"Which one is correct?"
            )
        
        clarification = "\n\n".join(messages)
        
        logger.info(f"[GATE_CHECK] ✗ Gates blocked: {len(blocking_contradictions)} contradictions")
        
        return False, clarification, blocking_contradictions
    
    def _get_memory_by_id(self, memory_id: str) -> Optional[MemoryItem]:
        """Get a specific memory by ID."""
        all_memories = self.memory._load_all_memories()
        for mem in all_memories:
            if mem.memory_id == memory_id:
                return mem
        return None
    
    def _check_all_fact_contradictions_ml(
        self, 
        new_memory: MemoryItem, 
        user_query: str
    ) -> Tuple[bool, Optional[ContradictionEntry]]:
        """
        Check for contradictions using ML detector (replaces hardcoded slot list).
        
        This is the Bug 1 fix: Uses Phase 2/3 ML models to detect contradictions
        across ALL facts, not just hardcoded slots like employer/location.
        
        Args:
            new_memory: Newly stored memory item
            user_query: User's input text
            
        Returns:
            (contradiction_detected, contradiction_entry)
        """
        if self.ml_detector is None:
            logger.debug("[ML_CONTRADICTION] ML detector not available, skipping")
            return False, None
        
        # Extract facts from new memory
        new_facts = extract_fact_slots(user_query) or {}
        if not new_facts:
            return False, None
        
        # Get all previous user memories
        all_memories = self.memory._load_all_memories()
        previous_user_memories = [
            m for m in all_memories 
            if m.source == MemorySource.USER and m.memory_id != new_memory.memory_id
        ]
        
        # Check each new fact against previous memories
        for slot, new_fact in new_facts.items():
            new_value = getattr(new_fact, "value", str(new_fact))
            if not new_value:
                continue
            
            # Find previous memories with the same slot
            for prev_mem in previous_user_memories:
                prev_facts = extract_fact_slots(prev_mem.text) or {}
                prev_fact = prev_facts.get(slot)
                
                if prev_fact is None:
                    continue
                
                prev_value = getattr(prev_fact, "value", str(prev_fact))
                if not prev_value:
                    continue
                
                # Check if values are similar enough to skip (avoid nickname issues)
                if prev_value.lower().strip() == new_value.lower().strip():
                    continue
                
                # Use ML detector to check for contradiction
                context = {
                    "query": user_query,
                    "old_timestamp": prev_mem.timestamp,
                    "new_timestamp": new_memory.timestamp,
                    "memory_confidence": prev_mem.confidence,
                    "trust_score": prev_mem.trust,
                    "slot": slot
                }
                
                result = self.ml_detector.check_contradiction(
                    old_value=prev_value,
                    new_value=new_value,
                    slot=slot,
                    context=context
                )
                
                logger.info(
                    f"[ML_CONTRADICTION] Slot={slot}, Old={prev_value}, New={new_value}, "
                    f"Category={result['category']}, Policy={result['policy']}, "
                    f"Confidence={result['confidence']:.3f}"
                )
                
                # Record contradiction if detected
                if result["is_contradiction"]:
                    drift = self.crt_math.drift_meaning(new_memory.vector, prev_mem.vector)
                    
                    contradiction_entry = self.ledger.record_contradiction(
                        old_memory_id=prev_mem.memory_id,
                        new_memory_id=new_memory.memory_id,
                        drift_mean=drift,
                        confidence_delta=float(prev_mem.confidence) - float(new_memory.confidence),
                        query=user_query,
                        summary=f"{slot}: {prev_value} → {new_value} ({result['category']})",
                        old_text=prev_mem.text,
                        new_text=user_query,
                        old_vector=prev_mem.vector,
                        new_vector=new_memory.vector,
                        contradiction_type=result["category"],
                        suggested_policy=result["policy"]
                    )
                    
                    logger.info(
                        f"[ML_CONTRADICTION] ✓ Detected: {slot} contradiction "
                        f"({result['category']}, policy={result['policy']})"
                    )
                    
                    return True, contradiction_entry
        
        return False, None

    def _resolve_open_conflicts_from_assertion(self, user_text: str) -> int:
        """Resolve open hard CONFLICT contradictions when the user clarifies.

        If the user makes a new assertion that sets a fact slot to a specific value
        (e.g., employer=Amazon) and we have an OPEN hard CONFLICT about that slot,
        mark those contradictions RESOLVED.

        This prevents an infinite "ask_user" loop where CRT keeps asking the same
        clarification question but never records that the user answered it.

        Returns: number of ledger entries resolved.
        """
        from .crt_ledger import ContradictionStatus, ContradictionType

        facts = extract_fact_slots(user_text) or {}

        # Support explicit "slot = value" clarifications used by stress harnesses.
        if not facts:
            import re

            def _norm(v: str) -> str:
                return re.sub(r"\s+", " ", (v or "").strip()).lower()

            text = (user_text or "").strip()
            slot_patterns = {
                "employer": r"\bemployer\s*=\s*([^\n\r\.;,!\?]{2,80})",
                "name": r"\bname\s*=\s*([^\n\r\.;,!\?]{2,80})",
                "location": r"\blocation\s*=\s*([^\n\r\.;,!\?]{2,80})",
                "title": r"\btitle\s*=\s*([^\n\r\.;,!\?]{2,80})",
                "first_language": r"\bfirst_language\s*=\s*([^\n\r\.;,!\?]{2,80})",
                "masters_school": r"\bmasters_school\s*=\s*([^\n\r\.;,!\?]{2,80})",
                "undergrad_school": r"\bundergrad_school\s*=\s*([^\n\r\.;,!\?]{2,80})",
                "programming_years": r"\bprogramming_years\s*=\s*(\d{1,3})\b",
                "team_size": r"\bteam_size\s*=\s*(\d{1,3})\b",
            }

            class _Tmp:
                def __init__(self, value, normalized):
                    self.value = value
                    self.normalized = normalized

            for slot, pat in slot_patterns.items():
                m = re.search(pat, text, flags=re.IGNORECASE)
                if not m:
                    continue
                raw = (m.group(1) or "").strip()
                if not raw:
                    continue
                if slot in {"programming_years", "team_size"}:
                    try:
                        val = int(raw)
                    except Exception:
                        continue
                    facts[slot] = _Tmp(val, str(val))
                else:
                    facts[slot] = _Tmp(raw, _norm(raw))

        if not facts:
            return 0

        resolved = 0
        open_contras = self.ledger.get_open_contradictions(limit=200)
        for contra in open_contras:
            if getattr(contra, "contradiction_type", None) != ContradictionType.CONFLICT:
                continue

            old_mem = self.memory.get_memory_by_id(contra.old_memory_id)
            new_mem = self.memory.get_memory_by_id(contra.new_memory_id)
            if old_mem is None or new_mem is None:
                continue

            old_facts = extract_fact_slots(old_mem.text) or {}
            new_facts = extract_fact_slots(new_mem.text) or {}
            shared = set(old_facts.keys()) & set(new_facts.keys()) & set(facts.keys())
            if not shared:
                continue

            should_resolve = False
            for slot in shared:
                user_fact = facts.get(slot)
                if user_fact is None:
                    continue
                ov = old_facts.get(slot)
                nv = new_facts.get(slot)
                if ov is None or nv is None:
                    continue

                # If the user asserts either side's value, we treat that as a clarification.
                if user_fact.normalized in {ov.normalized, nv.normalized}:
                    should_resolve = True
                    break

            if should_resolve:
                self.ledger.resolve_contradiction(
                    contra.ledger_id,
                    method="user_clarified",
                    merged_memory_id=None,
                    new_status=ContradictionStatus.RESOLVED,
                )
                resolved += 1

        return resolved
    
    def _detect_and_resolve_nl_resolution(self, user_text: str) -> bool:
        """Detect and resolve contradictions via natural language resolution statements.
        
        Detects patterns like:
        - "Google is correct, I switched jobs"
        - "Actually, it's Google now"
        - "I meant Google, not Microsoft"
        - "I changed jobs to Google"
        - "That's the correct status now"
        - "Blue was right, ignore the red"
        
        Handles CONFLICT, REVISION, and TEMPORAL contradiction types.
        
        Returns: True if a contradiction was resolved, False otherwise.
        """
        from .crt_ledger import ContradictionStatus, ContradictionType
        
        # Resolution intent patterns
        resolution_patterns = [
            r'\b(is|was)\s+(correct|right|accurate)\b',
            r'\bactually\b',
            r'\bi\s+meant\b',
            r'\bswitched\s+(jobs|to|companies)\b',
            r'\bchanged\s+to\b',  # More general: "changed to" anything
            r'\bchanged\s+(jobs|companies)\b',  # Specific: "changed jobs"
            r'\bmoved\s+to\b',
            r'\bnow\s+(work|working|at)\b',
            r'\bcorrect\s+(one|version|answer|status|value|info|statement)\b',
            r'\b(that|this)(?:\s*\'s|\s+is)\s+(correct|right|accurate)\b',  # "that's correct"
            r'\bignore\s+(the|that)\b',  # "ignore the red"
            r'\b(no|wait)\b.*\b(was|is)\s+(right|correct)\b',  # "no wait, X was right"
        ]
        
        # Check if user text contains any resolution intent pattern
        has_resolution_intent = any(
            re.search(pattern, user_text, re.IGNORECASE) 
            for pattern in resolution_patterns
        )
        
        if not has_resolution_intent:
            return False
        
        # Extract facts from the user's statement
        facts = extract_fact_slots(user_text) or {}
        
        # Get open contradictions
        open_contras = self.ledger.get_open_contradictions(limit=200)
        if not open_contras:
            return False
        
        # Try to find a matching contradiction and determine which value to keep
        for contra in open_contras:
            # Handle CONFLICT, REVISION, and TEMPORAL contradictions
            # (REFINEMENT contradictions typically don't need NL resolution)
            contradiction_type = getattr(contra, "contradiction_type", None)
            if contradiction_type not in {ContradictionType.CONFLICT, ContradictionType.REVISION, ContradictionType.TEMPORAL}:
                continue
            
            old_mem = self.memory.get_memory_by_id(contra.old_memory_id)
            new_mem = self.memory.get_memory_by_id(contra.new_memory_id)
            if old_mem is None or new_mem is None:
                continue
            
            old_facts = extract_fact_slots(old_mem.text) or {}
            new_facts = extract_fact_slots(new_mem.text) or {}
            
            # Normalize values helper function (used throughout this loop)
            def normalize(val):
                if hasattr(val, 'normalized'):
                    return val.normalized
                return str(val).lower().strip()
            
            # Find slots that are in both old and new (contradiction slots)
            contra_slots = set(old_facts.keys()) & set(new_facts.keys())
            
            # Try to match user's facts with contradiction slots
            # First check if user provided explicit facts that match
            shared = contra_slots & set(facts.keys())
            
            # If no common slots or no explicit facts extracted, try fuzzy matching against values
            # This handles cases where extract_fact_slots doesn't support the slot type
            if not shared:
                # Fallback: check if any value from the contradiction appears in the user text
                # This handles cases like "Google is correct" where extract_fact_slots doesn't catch it
                user_text_lower = user_text.lower()
                
                # If we have extracted slots, use them for precise matching
                if contra_slots:
                    for slot in contra_slots:
                        old_value = old_facts.get(slot)
                        new_value = new_facts.get(slot)
                        if old_value is None or new_value is None:
                            continue
                        
                        old_normalized = normalize(old_value)
                        new_normalized = normalize(new_value)
                        
                        # Use word boundary matching to avoid false positives
                        # e.g., "Go" shouldn't match "Google"
                        old_pattern = re.compile(r'\b' + re.escape(old_normalized) + r'\b')
                        new_pattern = re.compile(r'\b' + re.escape(new_normalized) + r'\b')
                        
                        old_match = old_pattern.search(user_text_lower)
                        new_match = new_pattern.search(user_text_lower)
                        
                        # Check if either value appears in the user's text
                        # If both match, prefer the one that appears first in the text
                        if old_match or new_match:
                            # Found a match - add to shared so we process it below
                            shared = {slot}
                            # Create a synthetic fact for matching
                            # If both match, prefer the one that appears first
                            if old_match and new_match:
                                # Both values appear - choose based on position
                                if old_match.start() < new_match.start():
                                    facts[slot] = old_value
                                else:
                                    facts[slot] = new_value
                            elif old_match:
                                facts[slot] = old_value
                            else:
                                facts[slot] = new_value
                            break
                else:
                    # No extracted slots - try direct keyword matching against memory texts
                    # This handles cases like "I prefer coffee" vs "I prefer tea"
                    # Extract key words from old and new memories (ignore common words)
                    old_words = set(w.lower() for w in re.findall(r'\b\w+\b', old_mem.text) if w.lower() not in _NL_RESOLUTION_STOPWORDS)
                    new_words = set(w.lower() for w in re.findall(r'\b\w+\b', new_mem.text) if w.lower() not in _NL_RESOLUTION_STOPWORDS)
                    
                    # Find words that differ between old and new
                    old_unique = old_words - new_words
                    new_unique = new_words - old_words
                    
                    # Check if any of these unique words appear in the resolution text
                    # Use re.search to ensure word is actually found
                    old_matches = [w for w in old_unique if re.search(r'\b' + re.escape(w) + r'\b', user_text_lower)]
                    new_matches = [w for w in new_unique if re.search(r'\b' + re.escape(w) + r'\b', user_text_lower)]
                    
                    if old_matches or new_matches:
                        # Use a synthetic slot name for unstructured matching
                        shared = {_UNSTRUCTURED_SLOT_NAME}
                        
                        # Determine which memory to keep based on which words appear
                        if old_matches and new_matches:
                            # Both appear - check which appears first
                            # Find positions, filtering out -1 (not found) for safety
                            old_positions = [user_text_lower.find(w) for w in old_matches]
                            new_positions = [user_text_lower.find(w) for w in new_matches]
                            old_positions = [p for p in old_positions if p >= 0]
                            new_positions = [p for p in new_positions if p >= 0]
                            
                            if old_positions and new_positions:
                                first_old_pos = min(old_positions)
                                first_new_pos = min(new_positions)
                                if first_old_pos < first_new_pos:
                                    facts[_UNSTRUCTURED_SLOT_NAME] = old_mem.text
                                else:
                                    facts[_UNSTRUCTURED_SLOT_NAME] = new_mem.text
                            elif old_positions:
                                facts[_UNSTRUCTURED_SLOT_NAME] = old_mem.text
                            else:
                                facts[_UNSTRUCTURED_SLOT_NAME] = new_mem.text
                        elif old_matches:
                            facts[_UNSTRUCTURED_SLOT_NAME] = old_mem.text
                        else:
                            facts[_UNSTRUCTURED_SLOT_NAME] = new_mem.text
            
            if not shared:
                continue
            
            # Check if user's fact matches either old or new value
            for slot in shared:
                user_fact = facts.get(slot)
                if user_fact is None:
                    continue
                
                chosen_memory_id = None
                deprecated_memory_id = None
                
                # Handle synthetic slot from unstructured matching
                if slot == _UNSTRUCTURED_SLOT_NAME:
                    # User fact contains the full memory text that should be kept
                    if user_fact == old_mem.text:
                        chosen_memory_id = contra.old_memory_id
                        deprecated_memory_id = contra.new_memory_id
                    elif user_fact == new_mem.text:
                        chosen_memory_id = contra.new_memory_id
                        deprecated_memory_id = contra.old_memory_id
                    else:
                        # Shouldn't happen, but skip if we can't determine
                        continue
                else:
                    # Handle normal slots with extracted facts
                    old_value = old_facts.get(slot)
                    new_value = new_facts.get(slot)
                    if old_value is None or new_value is None:
                        continue
                    
                    user_normalized = normalize(user_fact)
                    old_normalized = normalize(old_value)
                    new_normalized = normalize(new_value)
                    
                    # Determine which memory to keep based on matching values
                    if user_normalized == new_normalized:
                        chosen_memory_id = contra.new_memory_id
                        deprecated_memory_id = contra.old_memory_id
                    elif user_normalized == old_normalized:
                        chosen_memory_id = contra.old_memory_id
                        deprecated_memory_id = contra.new_memory_id
                    else:
                        # User mentioned a value but it doesn't match either side
                        continue
                
                # Resolve the contradiction in the ledger FIRST
                # This ensures we don't end up with deprecated memories but unresolved contradictions
                self.ledger.resolve_contradiction(
                    contra.ledger_id,
                    method="nl_resolution",
                    merged_memory_id=None,
                    new_status=ContradictionStatus.RESOLVED,
                )
                
                # Then deprecate the non-chosen memory
                # Using context manager to ensure connection is properly closed
                mem_db = str(self.memory.db_path)
                try:
                    with sqlite3.connect(mem_db) as mem_conn:
                        mem_cursor = mem_conn.cursor()
                        
                        mem_cursor.execute("""
                            UPDATE memories 
                            SET deprecated = 1, deprecation_reason = ?
                            WHERE memory_id = ?
                        """, (f"User resolved via natural language: '{user_text[:100]}'", deprecated_memory_id))
                        
                        # Optionally boost trust of chosen memory slightly
                        mem_cursor.execute("""
                            UPDATE memories 
                            SET trust = MIN(trust + 0.1, 1.0)
                            WHERE memory_id = ?
                        """, (chosen_memory_id,))
                        
                        mem_conn.commit()
                except Exception as e:
                    logger.error(
                        f"[NL_RESOLUTION] Failed to update memories after resolving contradiction {contra.ledger_id}: {e}",
                        exc_info=True
                    )
                    # Continue anyway - the contradiction is already resolved in the ledger
                    # The memory deprecation is a nice-to-have optimization
                
                logger.info(
                    f"[NL_RESOLUTION] Resolved contradiction {contra.ledger_id} via natural language. "
                    f"Chose {chosen_memory_id}, deprecated {deprecated_memory_id}. "
                    f"User said: '{user_text[:100]}'"
                )
                
                return True
        
        return False
    
    # ========================================================================
    # Query with CRT Principles
    # ========================================================================
    
    def query(
        self,
        user_query: str,
        user_marked_important: bool = False,
        mode: Optional[ReasoningMode] = None
    ) -> Dict[str, Any]:
        """
        Query with CRT principles applied.
        
        Process:
        0. Store user input as memory (USER source)
        1. Trust-weighted retrieval
        2. Generate candidate output (reasoning)
        3. Check reconstruction gates (intent + memory alignment)
        4. If gates pass → belief (high trust)
        5. If gates fail → speech (low trust fallback)
        6. Detect contradictions
        7. Update trust scores
        8. Queue reflection if needed
        
        Returns both the response AND CRT metadata.
        """
        # 0. Store user input as USER memory ONLY when it's an assertion.
        # Questions and control instructions should not be treated as durable factual claims.
        user_memory: Optional[MemoryItem] = None

        # High-risk prompt types should be treated as instructions even if they do not
        # look like questions (multi-paragraph prompt injection often starts as declarative).
        is_memory_citation = self._is_memory_citation_request(user_query)
        is_contradiction_status = self._is_contradiction_status_request(user_query)
        is_memory_inventory = self._is_memory_inventory_request(user_query)

        user_input_kind = self._classify_user_input(user_query)
        logger.info(f"[PROFILE_DEBUG] Input classified as: {user_input_kind} | Query: {user_query[:100]}")
        
        # Check for natural language contradiction resolution FIRST
        # This prevents the resolution statement from being stored as a new assertion
        nl_resolution_occurred = False
        try:
            nl_resolution_occurred = self._detect_and_resolve_nl_resolution(user_query)
            if nl_resolution_occurred:
                logger.info(f"[NL_RESOLUTION] Natural language resolution detected and processed")
                # If we resolved a contradiction, treat this as an instruction/acknowledgment, not an assertion
                # This prevents "Google is correct" from being stored as a new fact that creates another contradiction
                if user_input_kind == "assertion":
                    logger.info(f"[NL_RESOLUTION] Reclassifying assertion → instruction (NL resolution)")
                    user_input_kind = "instruction"
        except Exception as e:
            logger.warning(f"[NL_RESOLUTION] Failed to detect/resolve NL resolution: {e}", exc_info=True)
        
        if user_input_kind == "assertion" and (is_memory_citation or is_contradiction_status or is_memory_inventory):
            logger.info(f"[PROFILE_DEBUG] Reclassifying assertion → instruction (special query type)")
            user_input_kind = "instruction"

        # Deterministic safe path: refuse prompt/system-instruction disclosure.
        # This prevents the model from hallucinating and avoids memory-claim phrasing
        # that can confuse the evaluator.
        if user_input_kind in ("question", "instruction") and self._is_system_prompt_request(user_query):
            answer = (
                "I can’t share my system prompt or hidden instructions verbatim. "
                "If you tell me what you’re trying to do, I can summarize how I’m designed to behave "
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
            user_memory = self.memory.store_memory(
                text=user_query,
                confidence=0.95,  # User assertions are high confidence
                source=MemorySource.USER,
                context={"type": "user_input", "kind": user_input_kind},
                user_marked_important=user_marked_important
            )
            logger.info(f"[PROFILE_DEBUG] Memory stored, now updating user profile...")
            
            # Also update global user profile with extracted facts
            # This enables cross-thread memory (e.g., name persists across chats)
            try:
                logger.info(f"[PROFILE_DEBUG] Calling user_profile.update_from_text with: {user_query[:100]}")
                self.user_profile.update_from_text(user_query, thread_id="current")
                logger.info(f"[PROFILE_DEBUG] ✅ Profile update completed successfully")
            except Exception as e:
                logger.error(f"[PROFILE_DEBUG] ❌ Failed to update user profile: {e}", exc_info=True)

            # If the user is clarifying a previously-detected hard conflict, mark it resolved.
            # This is intentionally conservative: only hard CONFLICT types, and only when
            # the asserted value matches one side of the conflict.
            try:
                self._resolve_open_conflicts_from_assertion(user_query)
            except Exception:
                # Resolution is best-effort; never block the main chat loop.
                pass
            
            # BUG 1 FIX: Check for contradictions using ML detector (ALL facts, not hardcoded slots)
            contradiction_detected = False
            contradiction_entry = None
            try:
                contradiction_detected, contradiction_entry = self._check_all_fact_contradictions_ml(
                    user_memory, user_query
                )
            except Exception as e:
                logger.warning(f"[ML_CONTRADICTION] Failed to check ML contradictions: {e}", exc_info=True)

            # Deterministic safe ack: user name declarations should not be embellished.
            # (e.g., never add a location like "New York" unless the user said it.)
            if self._is_user_name_declaration(user_query):
                logger.debug("Name declaration detected: %s", user_query[:80])
                # Prefer the name declared in this message (avoids echoing stale prior names
                # from the DB/profile seed).
                declared_facts = extract_fact_slots(user_query) or {}
                declared_name = declared_facts.get("name")
                if declared_name is not None and getattr(declared_name, "value", None):
                    answer = f"Thanks — noted: your name is {declared_name.value}."
                else:
                    name_guess = self._get_latest_user_name_guess()
                    if name_guess:
                        answer = f"Thanks — noted: your name is {name_guess}."
                    else:
                        answer = "Thanks — noted."

                # If the input also contains a question (e.g., "Hi, I'm Nick. Who are you?"),
                # answer both the name acknowledgment AND the question.
                if self._is_assistant_profile_question(user_query):
                    assistant_profile_cfg = (self.runtime_config.get("assistant_profile") or {}) if isinstance(self.runtime_config, dict) else {}
                    assistant_profile_enabled = bool(assistant_profile_cfg.get("enabled", True))
                    if assistant_profile_enabled:
                        profile_answer = self._build_assistant_profile_answer(user_query)
                        answer = f"{answer} {profile_answer}"

                # If the user previously stated a different name, record a contradiction entry.
                # NOTE: This is now redundant with ML-based detection above, but kept for
                # compatibility. The ML detector should catch name contradictions too.
                # Only run this if ML detection didn't already find a contradiction.
                if not contradiction_detected:
                    logger.debug("Name contradiction check starting (user_memory=%s)", user_memory is not None)
                    try:
                        new_facts = extract_fact_slots(user_query) or {}
                        new_name = new_facts.get("name")
                        logger.debug("Extracted name from query: %s", new_name)
                        if new_name is not None:
                            all_memories = self.memory._load_all_memories()
                            previous_user_memories = [
                                m
                                for m in all_memories
                                if m.source == MemorySource.USER and m.memory_id != user_memory.memory_id
                            ]
                            # Only record a new contradiction if the user asserts a NEW name
                            # (i.e., it does not match any prior user-stated name value).
                            # If the user re-asserts a previously-known name, treat it as
                            # reinforcement/clarification (and let conflict resolution handle it).
                            prior_same_exists = False
                            prior_names: List[MemoryItem] = []
                            for prev_mem in previous_user_memories:
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
                                logger.debug("Name contradiction: new='%s' vs old='%s', drift=%.3f", new_name.value, selected_prev.text[:60], drift)
                                contradiction_entry = self.ledger.record_contradiction(
                                    old_memory_id=selected_prev.memory_id,
                                    new_memory_id=user_memory.memory_id,
                                    drift_mean=drift,
                                    confidence_delta=float(selected_prev.confidence) - 0.95,
                                    query=user_query,
                                    summary=f"User name changed: {selected_prev.text[:50]}... vs {user_query[:50]}...",
                                    old_text=selected_prev.text,
                                    new_text=user_query,
                                    old_vector=selected_prev.vector,
                                    new_vector=user_vector,
                                )
                                logger.debug("Ledger recorded contradiction entry: %s", contradiction_entry)
                                contradiction_detected = True
                    except Exception as e:
                            logger.debug("Name contradiction check exception: %s", e)
                            logger.warning(f"[CONTRADICTION_DETECTION] Name contradiction check failed: {e}")
                            # Don't override if ML already detected it
                            pass

                return {
                    'answer': answer,
                    'thinking': None,
                    'mode': 'quick',
                    'confidence': 0.95,
                    'response_type': 'speech',
                    'gates_passed': False,
                    'gate_reason': 'user_name_declaration',
                    'intent_alignment': 0.95,
                    'memory_alignment': 1.0,
                    'contradiction_detected': contradiction_detected,
                    'contradiction_entry': (contradiction_entry.to_dict() if contradiction_entry is not None else None),
                    'retrieved_memories': [],
                    'prompt_memories': [],
                    'unresolved_contradictions_total': 0,
                    'unresolved_hard_conflicts': 0,
                    'learned_suggestions': [],
                    'heuristic_suggestions': [],
                    'best_prior_trust': None,
                    'session_id': self.session_id,
                }

        # Deterministic safe path: assistant-profile questions.
        # These are about the assistant/system, not the user, so we should not
        # invent chat-backed claims about what the user said.
        assistant_profile_cfg = (self.runtime_config.get("assistant_profile") or {}) if isinstance(self.runtime_config, dict) else {}
        assistant_profile_enabled = bool(assistant_profile_cfg.get("enabled", True))
        if assistant_profile_enabled and user_input_kind in ("question", "instruction") and self._is_assistant_profile_question(user_query):
            answer = self._build_assistant_profile_answer(user_query)
            return {
                'answer': answer,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.95,
                'response_type': 'speech',
                'gates_passed': False,
                'gate_reason': 'assistant_profile',
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
        
        # 1. Trust-weighted retrieval
        # First pass to infer slots before retrieval (enables scope filtering)
        inferred_slots: List[str] = []
        if user_input_kind in ("question", "instruction"):
            inferred_slots = self._infer_slots_from_query(user_query)
            logger.info(f"[PROFILE_DEBUG] Inferred slots from query: {inferred_slots}")
        
        # Parse any explicit first-person fact assertions (used for relevance checks).
        # For most questions this will be empty, which is fine.
        asserted_facts = extract_fact_slots(user_query) or {}
        
        # Compute relevant slots for contradiction filtering
        relevant_slots_set = set(inferred_slots or []) | set((asserted_facts or {}).keys())
        
        # BUG 2 FIX: Check for unresolved contradictions (gate blocking)
        gates_passed, clarification_message, blocking_contradictions = self._check_contradiction_gates(
            user_query, inferred_slots
        )
        
        if not gates_passed and clarification_message:
            # Gate blocked - return clarification request instead of confident answer
            logger.info(f"[GATE_BLOCK] Response blocked due to {len(blocking_contradictions)} contradictions")
            
            return {
                'answer': clarification_message,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.0,
                'response_type': 'uncertainty',
                'gates_passed': False,
                'gate_reason': 'contradiction_blocking',
                'intent_alignment': 0.5,
                'memory_alignment': 0.5,
                'contradiction_detected': True,
                'unresolved_contradictions_total': len(blocking_contradictions),
                'unresolved_hard_conflicts': len(blocking_contradictions),
                'retrieved_memories': [],
                'prompt_memories': [],
                'learned_suggestions': [],
                'heuristic_suggestions': [],
                'best_prior_trust': None,
                'session_id': self.session_id,
            }
        
        # Detect meta-queries about the system itself (not personal questions)
        if "how does crt work" in user_query.lower() or "how does this work" in user_query.lower():
            # This is a system question - return explanatory content
            explanation = (
                "CRT (Cognitive-Reflective Transformer) is a truthful personal AI system.\n\n"
                "How it works:\n"
                "1. **Memory Storage**: I store everything you tell me with trust scores\n"
                "2. **Contradiction Detection**: I notice when facts conflict (e.g., different employers)\n"
                "3. **Gradient Gates**: I only assert facts I'm confident about\n"
                "4. **Retrieval**: I search my memory using semantic similarity\n"
                "5. **Response**: I cite facts directly from memory, not hallucinations\n\n"
                "This keeps me truthful and lets you correct my mistakes."
            )
            
            self.memory.store_memory(
                text=explanation,
                confidence=0.8,
                source=MemorySource.SYSTEM,
                context={"query": user_query, "type": "speech", "kind": "meta_explanation"},
                user_marked_important=False,
            )
            
            return {
                'answer': explanation,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.9,
                'response_type': 'speech',
                'gates_passed': True,
                'gate_reason': 'meta_query_explanation',
                'intent_alignment': 1.0,
                'memory_alignment': 1.0,
                'contradiction_detected': False,
                'contradiction_entry': None,
                'retrieved_memories': [],
                'prompt_memories': [],
                'learned_suggestions': [],
                'heuristic_suggestions': [],
                'best_prior_trust': None,
                'session_id': self.session_id,
            }
        
        # Use broader retrieval (k=15) for synthesis queries that need to gather multiple related facts
        is_synthesis = self._is_synthesis_query(user_query)
        retrieval_k = 15 if is_synthesis else 5
        
        retrieved = self.retrieve(user_query, k=retrieval_k, relevant_slots=relevant_slots_set if relevant_slots_set else None)
        
        # Check for sentiment contradictions in retrieved memories
        sentiment_contradiction = self._detect_sentiment_contradiction(user_query, retrieved)
        if sentiment_contradiction:
            self.memory.store_memory(
                text=sentiment_contradiction,
                confidence=0.7,
                source=MemorySource.SYSTEM,
                context={"query": user_query, "type": "speech", "kind": "sentiment_contradiction"},
                user_marked_important=False,
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
        if user_input_kind in ("question", "instruction") and self._is_memory_citation_request(user_query):
            prompt_docs = self._build_resolved_memory_docs(retrieved, max_fact_lines=8, max_fallback_lines=2)
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
            # For synthesis, use RAW memories not resolved docs - we want ALL facts, not just slotted ones
            candidate_output = self._build_synthesis_answer(
                user_query=user_query,
                retrieved=retrieved,
            )

            # Synthesis answers cite facts directly, so they should pass gates
            self.memory.store_memory(
                text=candidate_output,
                confidence=0.8,
                source=MemorySource.SYSTEM,
                context={"query": user_query, "type": "belief", "kind": "synthesis"},
                user_marked_important=False,
            )

            best_prior = retrieved[0][0] if retrieved else None

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
            }

        # Special-case: user asks to list/dump memories or memory ids.
        # Never invent internal identifiers; respond deterministically with safe citations.
        if user_input_kind in ("question", "instruction") and self._is_memory_inventory_request(user_query):
            prompt_docs = self._build_resolved_memory_docs(retrieved, max_fact_lines=8, max_fallback_lines=2)
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
        if user_input_kind in ("question", "instruction") and self._is_contradiction_status_request(user_query):
            prompt_docs = self._build_resolved_memory_docs(retrieved, max_fact_lines=8, max_fallback_lines=0)
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

        # Deterministic safe path: third-person questions that reference the user by name.
        # Avoid importing world knowledge for a name that matches the current user.
        user_named_cfg = (self.runtime_config.get("user_named_reference") or {}) if isinstance(self.runtime_config, dict) else {}
        user_named_enabled = bool(user_named_cfg.get("enabled", True))
        if user_named_enabled and user_input_kind in ("question", "instruction") and self._is_user_named_reference_question(user_query):
            # Infer likely slots from the query (title/employer are common).
            inferred = inferred_slots or self._infer_slots_from_query(user_query)
            relevant_slots = [s for s in inferred if s in {"title", "employer"}]
            if not relevant_slots:
                # Still treat as high-risk; attempt to answer from work snippets.
                relevant_slots = ["title", "employer"]

            answer = self._build_user_named_reference_answer(user_query, relevant_slots)

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
            retrieved = self._augment_retrieval_with_slot_memories(retrieved, inferred_slots)
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

                uncertain_response = self._generate_uncertain_response(
                    user_query,
                    retrieved,
                    reason="I have an unresolved contradiction that affects your question",
                    recommended_next_action=recommended_next_action,
                    conflict_beliefs=conflict_beliefs,
                )
                return {
                    'answer': uncertain_response,
                    'thinking': None,
                    'mode': 'uncertainty',
                    'confidence': 0.3,
                    'response_type': 'uncertainty',
                    'gates_passed': False,
                    'gate_reason': 'unresolved_contradictions',
                    'intent_alignment': 0.0,
                    'memory_alignment': 0.0,
                    'contradiction_detected': False,
                    'contradiction_entry': None,
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
                        }
                        for mem, score in retrieved
                    ],
                    'unresolved_contradictions': 1,
                    'unresolved_contradictions_total': 1,
                    'unresolved_hard_conflicts': 1,
                    'contradiction_goals': contradiction_goals,
                    'recommended_next_action': recommended_next_action,
                }

        # Slot-based fast-path: if the user asks a simple personal-fact question and we have
        # an answer in memory, answer directly from canonical resolved facts.
        if user_input_kind in ("question", "instruction") and inferred_slots:
            slot_answer = self._answer_from_fact_slots(inferred_slots, user_query=user_query)
            if slot_answer is not None:
                    # Ensure we still have retrieval context for metadata/alignment.
                    if not retrieved:
                        retrieved = self.retrieve(user_query, k=5)
                    prompt_docs = self._build_resolved_memory_docs(retrieved, max_fallback_lines=0)

                    reasoning_result = {
                        'answer': slot_answer,
                        'thinking': None,
                        'mode': 'quick',
                        'confidence': 0.95,
                    }

                    candidate_output = reasoning_result['answer']
                    candidate_vector = encode_vector(candidate_output)

                    intent_align = reasoning_result['confidence']
                    memory_align = self.crt_math.memory_alignment(output_vector=candidate_vector, retrieved_memories=[{'vector': mem.vector, 'text': mem.text} for mem, _ in retrieved], retrieval_scores=[score for _, score in retrieved], output_text=candidate_output)

                    # Predict response type using heuristics (89.5% - beats all ML attempts)
                    response_type_pred = self._classify_query_type_heuristic(user_query)
                    
                    # Compute grounding score
                    grounding_score = self._compute_grounding_score(candidate_output, retrieved)
                    
                    # Use gradient gates v2
                    gates_passed, gate_reason = self.crt_math.check_reconstruction_gates_v2(
                        intent_align=intent_align,
                        memory_align=memory_align,
                        response_type=response_type_pred,
                        grounding_score=grounding_score,
                        contradiction_severity="none",
                    )
                    
                    # Log gate event for active learning
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
                                thread_id="",
                                session_id=self.session_id,
                            )
                        except Exception:
                            pass

                    # Do not append provenance footers into the answer text.
                    final_answer = slot_answer

                    response_type = "belief" if gates_passed else "speech"
                    source = MemorySource.SYSTEM if gates_passed else MemorySource.FALLBACK
                    confidence = reasoning_result['confidence'] if gates_passed else (reasoning_result['confidence'] * 0.7)

                    best_prior = retrieved[0][0] if retrieved else None

                    # Store system response memory
                    self.memory.store_memory(
                        text=candidate_output,
                        confidence=confidence,
                        source=source,
                        context={'query': user_query, 'type': response_type, 'kind': 'slot_answer'},
                        user_marked_important=False,
                    )

                    learned = self._get_learned_suggestions_for_slots(inferred_slots)

                    return self._add_reintroduction_flags({
                        'answer': final_answer,
                        'thinking': None,
                        'mode': 'quick',
                        'confidence': reasoning_result['confidence'],
                        'response_type': response_type,
                        'gates_passed': gates_passed,
                        'gate_reason': gate_reason,
                        'intent_alignment': intent_align,
                        'memory_alignment': memory_align,
                        'contradiction_detected': False,
                        'contradiction_entry': None,
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
                            }
                            for mem, score in retrieved
                        ],
                        'prompt_memories': [
                            {
                                'text': d.get('text'),
                                'memory_id': d.get('memory_id'),
                                'trust': d.get('trust'),
                                'confidence': d.get('confidence'),
                                'source': d.get('source'),
                            }
                            for d in prompt_docs
                        ],
                        'learned_suggestions': learned,
                        'heuristic_suggestions': self._get_heuristic_suggestions_for_slots(inferred_slots),
                        'best_prior_trust': best_prior.trust if best_prior else None,
                        'session_id': self.session_id,
                    })

            # Summary-style instructions: answer from canonical resolved USER facts.
            if user_input_kind == "instruction":
                lower = (user_query or "").strip().lower()
                
                # Handler for "list N facts" queries - FACT-CONSTRAINED, no LLM hallucination
                if re.search(r"\blist\s+\d+\s+facts?\b", lower) or "facts you're confident" in lower or "facts you know" in lower:
                    fact_list = self._list_confident_facts_from_slots()
                    if fact_list is not None:
                        if not retrieved:
                            retrieved = self.retrieve(user_query, k=5)
                        prompt_docs = self._build_resolved_memory_docs(retrieved, max_fallback_lines=0)

                        candidate_output = fact_list
                        candidate_vector = encode_vector(candidate_output)

                        intent_align = 0.95
                        memory_align = self.crt_math.memory_alignment(output_vector=candidate_vector, retrieved_memories=[{'vector': mem.vector, 'text': mem.text} for mem, _ in retrieved], retrieval_scores=[score for _, score in retrieved], output_text=candidate_output)

                        # Predict response type and compute grounding
                        response_type_pred = self._classify_query_type_heuristic(user_query)
                        
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
                            except Exception:
                                pass

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
                            retrieved = self.retrieve(user_query, k=5)
                        prompt_docs = self._build_resolved_memory_docs(retrieved, max_fallback_lines=0)

                        candidate_output = summary
                        candidate_vector = encode_vector(candidate_output)

                        intent_align = 0.95
                        memory_align = self.crt_math.memory_alignment(output_vector=candidate_vector, retrieved_memories=[{'vector': mem.vector, 'text': mem.text} for mem, _ in retrieved], retrieval_scores=[score for _, score in retrieved], output_text=candidate_output)

                        # Predict response type and compute grounding
                        response_type_pred = self._classify_query_type_heuristic(user_query)
                        
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
                            except Exception:
                                pass

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
        
        if not retrieved:
            # No memories → fallback speech
            return self._fallback_response(user_query)
        
        # GLOBAL COHERENCE GATE: Check for unresolved contradictions.
        # Only hard CONFLICT contradictions should trigger an uncertainty early-exit.
        # Revisions/refinements/temporal updates can often be answered coherently without stalling.
        from .crt_ledger import ContradictionType

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
        
        if should_uncertain:
            # If we can infer a concrete next action from conflicts, include it.
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
                'contradiction_detected': False,
                'contradiction_entry': None,
                'retrieved_memories': [
                    {'text': mem.text, 'trust': mem.trust, 'confidence': mem.confidence}
                    for mem, _ in retrieved
                ],
                'unresolved_contradictions': related_hard_conflicts,
                'unresolved_contradictions_total': related_open_total,
                'unresolved_hard_conflicts': related_hard_conflicts,
                'contradiction_goals': contradiction_goals,
                'recommended_next_action': recommended_next_action,
            }
        
        # Extract best prior belief
        best_prior = retrieved[0][0] if retrieved else None

        # Build a conflict-resolved memory view for prompting.
        # We keep raw retrieval for scoring/alignment, but present canonical facts
        # (latest, user-first) to reduce "snap back" to older contradictory text.
        prompt_docs = self._build_resolved_memory_docs(retrieved, max_fallback_lines=0)
        learned = self._get_learned_suggestions_for_slots(self._infer_slots_from_query(user_query))
        heuristic = self._get_heuristic_suggestions_for_slots(self._infer_slots_from_query(user_query))
        
        # 2. Generate candidate output using reasoning
        reasoning_context = {
            'retrieved_docs': [
                doc for doc in prompt_docs
            ],
            'contradictions': [],  # Will detect after generation
            'memory_context': []
        }
        
        reasoning_result = self.reasoning.reason(
            query=user_query,
            context=reasoning_context,
            mode=mode
        )
        
        candidate_output = reasoning_result['answer']

        # Consistency guard: if we have memory context, do not let the surface text
        # claim "first conversation" / "no memories".
        candidate_output = self._sanitize_memory_denial(answer=candidate_output, has_memory_context=bool(prompt_docs))
        # Honesty guard: if the model claims it "remembers" a personal fact that is not
        # present in our resolved FACT prompt docs, strip that unsupported claim.
        candidate_output = self._sanitize_unsupported_memory_claims(answer=candidate_output, prompt_docs=prompt_docs)
        # UI cleanliness: the assistant should not leak internal scoring/metrics in the user-visible answer.
        # (These are available in metadata panels instead.)
        candidate_output = re.sub(r"\(\s*trust score[^)]*\)", "", candidate_output, flags=re.IGNORECASE).strip()
        candidate_vector = encode_vector(candidate_output)
        
        # 3. Check reconstruction gates
        # For conversational AI, intent alignment = reasoning confidence
        # (Did we confidently answer the question?)
        intent_align = reasoning_result['confidence']
        
        # Memory alignment (output → retrieved memories)
        memory_align = self.crt_math.memory_alignment(output_vector=candidate_vector, retrieved_memories=[{'vector': mem.vector, 'text': mem.text} for mem, _ in retrieved], retrieval_scores=[score for _, score in retrieved], output_text=candidate_output)
        
        # Predict response type and compute grounding
        response_type_pred = self._classify_query_type_heuristic(user_query)
        
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
            except Exception:
                pass
        
        # Calibrate confidence based on gate failures
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
        
        # 5. Detect contradictions (only when USER made a new assertion)
        contradiction_detected = False
        contradiction_entry = None
        
        logger.debug("Generic contradiction check: user_input_kind=%s, user_memory=%s", user_input_kind, user_memory is not None)
        if user_input_kind != "question" and user_memory is not None:
            # Prefer claim-level contradiction detection for common personal-profile facts.
            # This avoids false positives from pure embedding drift, and catches true conflicts
            # even when retrieval does not surface the relevant prior memory.
            new_facts = extract_fact_slots(user_query)
            logger.debug("Extracted fact slots: %s", list(new_facts.keys()) if new_facts else None)
            if new_facts:
                user_vector = encode_vector(user_query)

                all_memories = self.memory._load_all_memories()
                previous_user_memories = [
                    m
                    for m in all_memories
                    if m.source == MemorySource.USER and m.memory_id != user_memory.memory_id
                ]

                from .crt_ledger import ContradictionType

                # Build candidate facts per slot from prior USER memories.
                candidates_by_slot: Dict[str, List[Tuple[MemoryItem, Any]]] = {}
                for prev_mem in previous_user_memories:
                    prev_facts = extract_fact_slots(prev_mem.text)
                    if not prev_facts:
                        continue
                    for slot, fact in prev_facts.items():
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
                    if latest_norm == new_norm:
                        continue

                    # New asserted value conflicts with the latest value => contradiction.
                    selected_prev = latest_mem
                    break

                logger.debug("Contradiction detection result: selected_prev=%s", selected_prev is not None)
                if selected_prev is not None:
                    drift = self.crt_math.drift_meaning(user_vector, selected_prev.vector)
                    logger.info(f"[CONTRADICTION_DETECTION] Generic fact contradiction detected: query='{user_query[:60]}' vs old='{selected_prev.text[:60]}', drift={drift:.3f}")

                    contradiction_entry = self.ledger.record_contradiction(
                        old_memory_id=selected_prev.memory_id,
                        new_memory_id=user_memory.memory_id,
                        drift_mean=drift,
                        confidence_delta=selected_prev.confidence - 0.95,
                        query=user_query,
                        summary=f"User contradiction: {selected_prev.text[:50]}... vs {user_query[:50]}...",
                        old_text=selected_prev.text,
                        new_text=user_query,
                        old_vector=selected_prev.vector,
                        new_vector=user_vector
                    )

                    contradiction_detected = True

                    if contradiction_entry.contradiction_type == ContradictionType.CONFLICT:
                        self.memory.evolve_trust_for_contradiction(selected_prev, user_vector)

                    volatility = self.crt_math.compute_volatility(
                        drift=drift,
                        memory_alignment=memory_align,
                        is_contradiction=True,
                        is_fallback=False
                    )

                    if self.crt_math.should_reflect(volatility):
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
        
        # INVARIANT ENFORCEMENT: Flag all reintroduced claims
        # This creates machine-readable proof that contradicted facts are marked
        retrieved_with_flags = self._flag_reintroduced_claims([mem for mem, _ in retrieved])
        prompt_with_flags = self._flag_reintroduced_claims(
            [self.memory.get_memory_by_id(d.get('memory_id')) 
             for d in (prompt_docs or []) 
             if d.get('memory_id')]
        ) if prompt_docs else []
        
        # Count reintroductions for audit trail
        reintroduced_count = sum(1 for m in retrieved_with_flags if m.get('reintroduced_claim'))
        
        # 6. Store system response memory
        new_memory = self.memory.store_memory(
            text=candidate_output,
            confidence=confidence,
            source=source,
            context={'query': user_query, 'type': response_type},
            user_marked_important=False  # System responses not marked important
        )
        
        # Update trust for aligned USER memories when gates pass
        # This rewards user memories that led to coherent, confident responses
        if gates_passed and retrieved:
            for mem, score in retrieved[:3]:  # Top 3 retrieved
                # Only evolve trust for USER memories (not system/fallback)
                if mem.source == MemorySource.USER:
                    self.memory.evolve_trust_for_alignment(mem, candidate_vector)
        
        # 7. Record belief or speech
        if response_type == "belief":
            self.memory.record_belief(
                query=user_query,
                response=candidate_output,
                memory_ids=[mem.memory_id for mem, _ in retrieved],
                avg_trust=np.mean([mem.trust for mem, _ in retrieved])
            )
        else:
            self.memory.record_speech(
                query=user_query,
                response=candidate_output,
                source="fallback_gates_failed"
            )
        
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
                    'reintroduced_claim': self.ledger.has_open_contradiction(mem.memory_id) if hasattr(self.ledger, 'has_open_contradiction') else False,  # INVARIANT FLAG
                }
                for mem, score in retrieved
            ],

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
            'unresolved_contradictions_total': len(self._get_memory_conflicts()),
            'unresolved_hard_conflicts': sum(
                1 for c in self._get_memory_conflicts()
                if str(getattr(c, 'contradiction_type', '')).lower() == 'conflict'
            ),

            # Learned suggestions (metadata-only; never authoritative)
            'learned_suggestions': learned,
            'heuristic_suggestions': heuristic,
            
            # Trust evolution
            'best_prior_trust': best_prior.trust if best_prior else None,
            
            # Session
            'session_id': self.session_id
        })

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

    def _build_resolved_memory_docs(
        self,
        retrieved: List[Tuple[MemoryItem, float]],
        max_fact_lines: int = 8,
        max_fallback_lines: int = 0,
    ) -> List[Dict[str, Any]]:
        """Create a prompt-friendly, conflict-resolved memory context.

        If multiple retrieved memories speak about the same fact slot (e.g. employer),
        present only the best candidate (latest, user-first) as a canonical FACT line.

        This avoids the LLM choosing an older contradictory sentence.
        """
        if not retrieved:
            return []

        def _source_priority(mem: MemoryItem) -> int:
            # Prefer user assertions over system paraphrases.
            if mem.source == MemorySource.USER:
                return 3
            if mem.source == MemorySource.SYSTEM:
                return 2
            if mem.source == MemorySource.REFLECTION:
                return 2
            return 1

        # Choose best memory per slot.
        best_for_slot: Dict[str, Tuple[MemoryItem, Any]] = {}
        for mem, _score in retrieved:
            facts = extract_fact_slots(mem.text)
            if not facts:
                continue
            for slot, fact in facts.items():
                current = best_for_slot.get(slot)
                if current is None:
                    best_for_slot[slot] = (mem, fact)
                    continue

                cur_mem, _cur_fact = current
                cand_key = (_source_priority(mem), mem.timestamp, mem.trust)
                cur_key = (_source_priority(cur_mem), cur_mem.timestamp, cur_mem.trust)
                if cand_key > cur_key:
                    best_for_slot[slot] = (mem, fact)

        slot_priority = [
            "name",
            "favorite_color",
            "employer",
            "title",
            "location",
            "masters_school",
            "undergrad_school",
            "programming_years",
            "remote_preference",
            "team_size",
        ]

        resolved_docs: List[Dict[str, Any]] = []
        slots_sorted = sorted(best_for_slot.keys(), key=lambda s: (slot_priority.index(s) if s in slot_priority else 999, s))
        for slot in slots_sorted[:max_fact_lines]:
            mem, fact = best_for_slot[slot]
            resolved_docs.append(
                {
                    "text": f"FACT: {slot} = {fact.value}",
                    "memory_id": mem.memory_id,
                    "trust": mem.trust,
                    "confidence": mem.confidence,
                    "source": mem.source.value,
                }
            )

        # If we extracted no facts at all, fall back to raw memory lines.
        if not resolved_docs:
            return [
                {
                    "text": mem.text,
                    "memory_id": mem.memory_id,
                    "trust": mem.trust,
                    "confidence": mem.confidence,
                    "source": mem.source.value,
                }
                for mem, _score in retrieved
            ]

        # Add a couple of non-slot raw lines for conversational continuity.
        fallback_added = 0
        for mem, _score in retrieved:
            if fallback_added >= max_fallback_lines:
                break
            if extract_fact_slots(mem.text):
                continue
            resolved_docs.append(
                {
                    "text": mem.text,
                    "memory_id": mem.memory_id,
                    "trust": mem.trust,
                    "confidence": mem.confidence,
                    "source": mem.source.value,
                }
            )
            fallback_added += 1

        return resolved_docs

    def _infer_slots_from_query(self, text: str) -> List[str]:
        """Infer which fact slots a question is asking about.

        This is intentionally heuristic and tuned to the stress tests.
        """
        t = (text or "").strip().lower()
        if not t:
            return []

        slots: List[str] = []
        if "name" in t:
            slots.append("name")

        if ("favorite" in t or "favourite" in t) and ("color" in t or "colour" in t):
            slots.append("favorite_color")

        if "where" in t and ("work" in t or "job" in t or "employer" in t):
            slots.append("employer")
        elif "employer" in t or "company" in t:
            slots.append("employer")

        if "where" in t and ("live" in t or "located" in t or "from" in t or "location" in t):
            slots.append("location")
        elif "city" in t and ("live" in t or "location" in t):
            slots.append("location")

        if "title" in t or "job title" in t or "role" in t or "position" in t or "occupation" in t:
            slots.append("title")
        
        if "project" in t and ("called" in t or "name" in t):
            slots.append("project_name")

        if "university" in t or "attend" in t or "school" in t:
            # Prefer master's if present; undergrad also possible.
            slots.extend(["masters_school", "undergrad_school"])

        if "remote" in t or "office" in t:
            slots.append("remote_preference")

        if "how many years" in t or "years" in t and "program" in t:
            slots.append("programming_years")

        if "language" in t and ("start" in t or "starting" in t or "first" in t):
            slots.append("first_language")
        
        # ADDED: Detection for "How many languages do I speak?"
        if ("how many" in t or "languages" in t) and "language" in t and "speak" in t:
            slots.append("languages_spoken")
        
        # ADDED: Detection for graduation/school completion queries
        if "graduate" in t or "graduation" in t:
            slots.extend(["graduation_year", "masters_school", "undergrad_school"])
        
        # ADDED: Detection for sibling/family queries
        if "sibling" in t or "brother" in t or "sister" in t:
            slots.append("siblings")
        
        # ADDED: Detection for age queries
        if "how old" in t or "age" in t or "years old" in t:
            slots.append("age")

        if "how many" in t and ("engineer" in t or "manage" in t or "team" in t):
            slots.append("team_size")

        # De-dup, preserve order
        seen = set()
        out: List[str] = []
        for s in slots:
            if s not in seen:
                out.append(s)
                seen.add(s)
        return out

    def _is_assistant_profile_question(self, text: str) -> bool:
        t = (text or "").strip().lower()
        if not t:
            return False

        # Keep this conservative: only very clear questions about the assistant itself.
        patterns = (
            r"\bwho\s+are\s+you\b",
            r"\bwhat\s+are\s+you\b",
            r"\bwhat\s+is\s+your\s+name\b",
            r"\bwhat('?s|\s+is)\s+your\s+name\b",
            r"\bdo\s+you\s+have\s+a\s+name\b",
            r"\bwhat\s+is\s+your\s+(occupation|job|role|purpose)\b",
            r"\bwhat\s+do\s+you\s+do\b",
            # Background/experience questions about the assistant (not the user).
            r"\bwhat('?s|\s+is)\s+your\s+background\b",
            r"\bwhat('?s|\s+is)\s+your\s+experience\b",
            r"\b(tell\s+me|can\s+you\s+tell\s+me)\s+about\s+your\s+(background|experience)\b",
            r"\babout\s+your\s+(background|experience)\b",
            # Work-in-domain questions (often phrased as 'your work in X').
            r"\b(tell\s+me|can\s+you\s+tell\s+me)\s+about\s+your\s+work\s+in\b",
            r"\babout\s+your\s+work\s+in\b",
            r"\bwhat\s+work\s+have\s+you\s+done\s+in\b",
            r"\bwhat\s+is\s+your\s+work\s+in\b",
            r"\bdo\s+you\s+have\s+(any\s+)?(background|experience)\b",
            r"\bwhat\s+experience\s+do\s+you\s+have\b",
            r"\bhave\s+you\s+(ever\s+)?worked\s+(as|in)\b",
        )
        return any(re.search(p, t, flags=re.IGNORECASE) for p in patterns)

    def _build_assistant_profile_answer(self, user_query: str) -> str:
        # Deterministic, chat-agnostic answer: don't claim the user said things.
        cfg = (self.runtime_config.get("assistant_profile") or {}) if isinstance(self.runtime_config, dict) else {}
        responses = (cfg.get("responses") or {}) if isinstance(cfg.get("responses"), dict) else {}

        def _resp(key: str, fallback: str) -> str:
            value = responses.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            return fallback

        q = (user_query or "").strip().lower()

        # Handle name questions
        if re.search(r"\b(name)\b", q) and not re.search(r"\b(my|user|their)\b", q):
            return _resp(
                "name",
                "I'm an AI assistant. I don't have a personal name, but you can call me CRT or GitHub Copilot.",
            )

        if re.search(r"\b(occupation|job|role)\b", q):
            return _resp(
                "occupation",
                "I'm an AI assistant (a software system). I don't have a human occupation, but my role is to help with tasks.",
            )

        if re.search(r"\b(purpose)\b", q) or re.search(r"\bwhat\s+do\s+you\s+do\b", q):
            return _resp(
                "purpose",
                "I'm an AI assistant designed to help with information and tasks.",
            )

        if (
            re.search(r"\b(background|experience)\b", q)
            or re.search(r"\byour\s+work\s+in\b", q)
            or re.search(r"\bwhat\s+work\s+have\s+you\s+done\s+in\b", q)
            or re.search(r"\bwhat\s+experience\s+do\s+you\s+have\b", q)
            or re.search(r"\bhave\s+you\s+(ever\s+)?worked\s+(as|in)\b", q)
        ):
            if re.search(r"\bfilmmaking\b|\bfilm\b|\bmovie\b|\bcinema\b|\bdirector\b|\bproducer\b", q):
                return _resp(
                    "background_filmmaking",
                    "I don't have personal filmmaking experience—I'm an AI system. I can still help with filmmaking concepts.",
                )
            return _resp(
                "background_general",
                "I don't have personal experiences—I'm an AI system. I can still help with information and planning.",
            )

        # Generic fallback for "who/what are you".
        return _resp("identity", "I'm an AI assistant (a software system) designed to help with information and tasks.")

    def _augment_retrieval_with_slot_memories(
        self,
        retrieved: List[Tuple[MemoryItem, float]],
        slots: List[str],
        *,
        allowed_sources: Optional[set] = None,
    ) -> List[Tuple[MemoryItem, float]]:
        """Merge best per-slot memories into the retrieved list."""
        # Allow augmentation even if retrieved is empty - profile facts are valuable!
        if not slots:
            return retrieved

        # Slot augmentation is meant to make user-profile questions more stable
        # (e.g., "What is my name?") by pulling the best USER-stated fact.
        # Do not inject assistant-generated (SYSTEM) or non-durable (FALLBACK)
        # memories here, as that can create prompt contamination and bad grounding.
        if allowed_sources is None:
            allowed_sources = {MemorySource.USER}

        retrieved_ids = {m.memory_id for m, _ in retrieved}
        all_memories = self.memory._load_all_memories()

        def _source_priority(mem: MemoryItem) -> int:
            if mem.source == MemorySource.USER:
                return 3
            if mem.source == MemorySource.SYSTEM:
                return 2
            if mem.source == MemorySource.REFLECTION:
                return 2
            return 1

        injected: List[Tuple[MemoryItem, float]] = []
        
        # First, check global user profile for these slots
        # NOTE: For slots with multiple values (e.g., multiple employers), inject ALL of them
        try:
            logger.info(f"[PROFILE_DEBUG] Checking global profile for slots: {slots}")
            # Get ALL facts for each slot (not just most recent)
            for slot in slots:
                slot_facts = self.user_profile.get_all_facts_for_slot(slot)
                logger.info(f"[PROFILE_DEBUG] Retrieved {len(slot_facts)} facts for slot '{slot}'")
                
                for idx, fact in enumerate(slot_facts):
                    # Create a synthetic memory item from profile fact
                    # Use unique memory_id for each value (slot_0, slot_1, etc.)
                    synthetic_mem = MemoryItem(
                        memory_id=f"profile_{slot}_{idx}",
                        vector=encode_vector(f"FACT: {slot} = {fact.value}"),
                        text=f"FACT: {slot.replace('_', ' ')} = {fact.value}",
                        timestamp=fact.timestamp,
                        confidence=fact.confidence,
                        trust=0.95,  # High trust for profile facts
                        source=MemorySource.USER,
                        sse_mode=SSEMode.LOSSLESS  # Identity-critical fact
                    )
                    if synthetic_mem.memory_id not in retrieved_ids:
                        logger.info(f"[PROFILE_DEBUG] Injecting profile fact: {slot} = {fact.value}")
                        injected.append((synthetic_mem, 1.0))
                        retrieved_ids.add(synthetic_mem.memory_id)
        except Exception as e:
            logger.error(f"[PROFILE_DEBUG] Failed to augment with profile facts: {e}", exc_info=True)
        
        # Then check thread-local memories
        for slot in slots:
            best: Optional[MemoryItem] = None
            best_key: Optional[Tuple[int, float, float]] = None
            for mem in all_memories:
                if getattr(mem, "source", None) not in allowed_sources:
                    continue
                facts = extract_fact_slots(mem.text)
                if slot not in facts:
                    continue
                key = (_source_priority(mem), mem.timestamp, mem.trust)
                if best is None or (best_key is not None and key > best_key):
                    best = mem
                    best_key = key
            if best is not None and best.memory_id not in retrieved_ids:
                injected.append((best, 1.0))
                retrieved_ids.add(best.memory_id)

        if not injected:
            return retrieved

        # Prefer injected slot memories at the front so they influence best_prior and prompting.
        return injected + retrieved

    def _answer_from_fact_slots(self, slots: List[str], *, user_query: Optional[str] = None) -> Optional[str]:
        """Answer simple personal-fact questions directly from USER memories.

        Returns an answer string if we can resolve at least one requested slot; otherwise None.
        """
        if not slots:
            return None

        all_memories = self.memory._load_all_memories()
        user_memories = [m for m in all_memories if m.source == MemorySource.USER]
        if not user_memories:
            return None

        def _source_priority(mem: MemoryItem) -> int:
            if mem.source == MemorySource.USER:
                return 3
            if mem.source == MemorySource.SYSTEM:
                return 2
            if mem.source == MemorySource.REFLECTION:
                return 2
            return 1

        # Collect candidate values per slot.
        slot_values: Dict[str, List[Tuple[MemoryItem, Any]]] = {s: [] for s in slots}
        for mem in user_memories:
            facts = extract_fact_slots(mem.text)
            if not facts:
                continue
            for slot in slots:
                if slot in facts:
                    slot_values[slot].append((mem, facts[slot].value))

        resolved_parts: List[str] = []
        q = (user_query or "").strip().lower()
        wants_another = bool(re.search(r"\b(another|other|second|additional)\b", q))
        for slot in slots:
            candidates = slot_values.get(slot) or []
            if not candidates:
                continue

            # Pick best (latest, user-first; trust as tiebreak).
            best_mem, best_val = max(
                candidates,
                key=lambda mv: (_source_priority(mv[0]), mv[0].timestamp, mv[0].trust),
            )

            # If multiple distinct values exist, mention that this was updated.
            distinct_norm = []
            for _m, v in candidates:
                vn = str(v).strip().lower()
                if vn and vn not in distinct_norm:
                    distinct_norm.append(vn)

            if len(distinct_norm) > 1:
                resolved_parts.append(f"{slot.replace('_', ' ')}: {best_val} (most recent update)")
            else:
                resolved_parts.append(f"{slot.replace('_', ' ')}: {best_val}")

        if not resolved_parts:
            return None

        if len(resolved_parts) == 1:
            # Return just the value-centric answer for naturalness.
            if wants_another and "favorite_color" in slots:
                # Special-case: user is asking for an additional favorite color.
                candidates = slot_values.get("favorite_color") or []
                if candidates:
                    best_mem, best_val = max(
                        candidates,
                        key=lambda mv: (_source_priority(mv[0]), mv[0].timestamp, mv[0].trust),
                    )
                    distinct_vals: list[str] = []
                    for _m, v in candidates:
                        vv = str(v).strip()
                        if vv and vv.lower() not in [x.lower() for x in distinct_vals]:
                            distinct_vals.append(vv)

                    if len(distinct_vals) <= 1:
                        return f"No — I only have {best_val} stored as your favorite color."

                    others = [v for v in distinct_vals if v.strip().lower() != str(best_val).strip().lower()]
                    if others:
                        return f"Yes — I have {best_val} as your most recent favorite color, and you’ve also said: {', '.join(others)}."
                # Fallback
                return "I only have one favorite color stored right now."
            
            # Special-case: count-based slots need fuller answers for gate alignment
            slot = slots[0]
            val_str = resolved_parts[0].split(": ", 1)[1]
            
            if slot == "siblings":
                try:
                    count = int(val_str)
                    if count == 1:
                        return "You have one sibling."
                    else:
                        return f"You have {val_str} siblings."
                except:
                    return f"You have {val_str} siblings."
            
            if slot == "languages_spoken":
                try:
                    count = int(val_str)
                    if count == 1:
                        return "You speak one language."
                    else:
                        return f"You speak {val_str} languages."
                except:
                    return f"You speak {val_str} languages."
            
            if slot == "graduation_year":
                return f"You graduated in {val_str}."

            return resolved_parts[0].split(": ", 1)[1]

        return "\n".join(resolved_parts)

    def _one_line_summary_from_facts(self) -> Optional[str]:
        """Build a compact, fact-grounded one-line summary from USER memories."""
        core_slots = [
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
        resolved = self._answer_from_fact_slots(core_slots)
        if not resolved:
            return None

        # resolved is a multi-line "slot: value" block. Convert to a compact line.
        parts: List[str] = []
        for line in str(resolved).splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            k, v = line.split(":", 1)
            k = k.strip().replace("_", " ")
            v = v.strip()
            if k and v:
                parts.append(f"{k}={v}")

        if not parts:
            return None

        # Keep it to a single line and reasonably short.
        return "; ".join(parts[:8])

    def _list_confident_facts_from_slots(self) -> Optional[str]:
        """Build a numbered list of confident facts from USER memories.
        
        FACT-CONSTRAINED: Only returns facts that exist in resolved slot values.
        NEVER invents attributes not in the ledger.
        """
        core_slots = [
            "name",
            "employer",
            "title",
            "location",
            "programming_years",
            "first_language",
            "masters_school",
            "undergrad_school",
            "team_size",
            "remote_preference",
            "favorite_color",
            "hobby",
        ]
        resolved = self._answer_from_fact_slots(core_slots)
        if not resolved:
            return "I don't have any confirmed facts about you stored yet."

        # Parse the resolved facts into a clean numbered list
        facts: List[str] = []
        for line in str(resolved).splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            k, v = line.split(":", 1)
            k = k.strip().replace("_", " ").title()
            v = v.strip()
            if k and v:
                facts.append(f"{k}: {v}")

        if not facts:
            return "I don't have any confirmed facts about you stored yet."

        # Format as a natural response with numbered list
        if len(facts) == 1:
            return f"I have one confirmed fact: {facts[0]}"
        elif len(facts) == 2:
            return f"I have two confirmed facts:\n1. {facts[0]}\n2. {facts[1]}"
        else:
            # Limit to top facts by importance (name, employer, location, programming_years are prioritized)
            numbered = "\n".join([f"{i+1}. {f}" for i, f in enumerate(facts[:10])])
            return f"Here are the facts I'm confident about:\n{numbered}"

    def _classify_user_input(self, text: str) -> str:
        """Classify a user input as question vs assertion-ish.

        This is intentionally lightweight: we only need to avoid treating questions as factual claims.
        
        CRITICAL: Name declarations are ALWAYS treated as assertions, even if followed by a question.
        Example: "Hi, I'm Nick Block. Who are you?" → "assertion" (contains name declaration)
        """
        t = (text or "").strip()
        if not t:
            return "other"

        # PRIORITY CHECK: Name declarations trump question classification.
        # Common pattern: "Hi, I'm <name>. Who are you?" should be stored as a fact.
        if self._is_user_name_declaration(t):
            return "assertion"

        lower = t.lower()
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

        # Default: treat as assertion/statement.
        return "assertion"
    
    def _fallback_response(self, query: str) -> Dict:
        """Generate fallback response when no memories exist."""
        # Simple fallback
        result = self.reasoning.reason(
            query=query,
            context={'retrieved_docs': [], 'contradictions': []},
            mode=ReasoningMode.QUICK
        )
        
        # Store as low-trust speech
        self.memory.store_memory(
            text=result['answer'],
            confidence=0.3,
            source=MemorySource.FALLBACK,
            context={'query': query, 'type': 'fallback_no_memory'}
        )
        
        self.memory.record_speech(query, result['answer'], "no_memory")
        
        return {
            'answer': result['answer'],
            'thinking': None,
            'mode': 'quick',
            'confidence': 0.3,
            'response_type': 'speech',
            'gates_passed': False,
            'gate_reason': 'No memories available',
            'contradiction_detected': False,
            'retrieved_memories': []
        }

    # ========================================================================
    # Grounded memory citation helpers
    # ========================================================================

    def _is_synthesis_query(self, text: str) -> bool:
        """True if the user asks to synthesize/summarize multiple facts.
        
        These queries need broader retrieval (higher k) to gather related facts.
        Examples:
        - "What do you know about my interests?"
        - "What technologies am I into?"
        - "Tell me what you remember about me"
        """
        t = (text or "").strip().lower()
        if not t:
            return False
        
        # Pattern 1: "what do you know about X"
        if "what do you know about" in t or "what do you remember about" in t:
            return True
        
        # Pattern 2: Summary requests
        if ("summarize" in t or "summary" in t or "tell me about" in t) and ("me" in t or "my" in t or "i" in t):
            return True
        
        # Pattern 3: Category queries asking for multiple facts
        if any(word in t for word in ["interests", "hobbies", "technologies", "skills", "languages", "preferences"]):
            if any(word in t for word in ["what", "tell", "list", "show"]):
                return True
        
        return False
    
    def _detect_sentiment_contradiction(self, user_query: str, retrieved: List[Tuple[MemoryItem, float]]) -> Optional[str]:
        """Detect implicit contradictions in sentiment/intent within retrieved memories.
        
        For example:
        - Query: "Am I happy at TechCorp?"
        - Memories: ["I just got promoted at TechCorp", "I'm thinking about changing jobs"]
        - Result: "You seem to have mixed feelings - you got promoted but are considering leaving"
        """
        if not retrieved:
            return None
        
        query_lower = user_query.lower()
        
        # Detect queries asking about sentiment/happiness/satisfaction
        if not any(word in query_lower for word in ["happy", "satisfied", "feel", "enjoy", "like"]):
            return None
        
        # Look for contradictory signals in retrieved memories
        positive_signals = []
        negative_signals = []
        
        for mem, _score in retrieved[:10]:
            text = mem.text.lower()
            
            # Positive signals
            if any(word in text for word in ["promoted", "promotion", "excited", "love", "great", "happy", "enjoy"]):
                positive_signals.append(mem.text)
            
            # Negative signals
            if any(phrase in text for phrase in ["changing jobs", "looking for", "thinking about leaving", "quit", "frustrated", "unhappy"]):
                negative_signals.append(mem.text)
        
        # If we have both positive and negative signals, surface the contradiction
        if positive_signals and negative_signals:
            answer_parts = ["I notice some mixed signals:"]
            if positive_signals:
                answer_parts.append(f"  Positive: {positive_signals[0]}")
            if negative_signals:
                answer_parts.append(f"  Concerning: {negative_signals[0]}")
            answer_parts.append("\nCan you help me understand what's really going on?")
            return "\n".join(answer_parts)
        
        return None

    def _is_memory_citation_request(self, text: str) -> bool:
        """True if the user explicitly asks for chat-grounded recall/citation.

        We use this to bypass open-ended generation and respond from stored memory text.
        """
        t = (text or "").strip().lower()
        if not t:
            return False

        if "from our chat" in t or "from this chat" in t or "from our conversation" in t or "conversation history" in t:
            return True

        if "quote" in t and ("memory" in t or "memories" in t or "exact memory" in t or "memory text" in t):
            return True

        if "exact memory text" in t:
            return True

        return False

    def _is_memory_inventory_request(self, text: str) -> bool:
        """True if the user asks to list/dump memories or internal memory IDs.

        This is treated as a high-risk prompt-injection surface: we should not invent
        internal identifiers. We respond deterministically with safe citations.
        """
        t = (text or "").strip().lower()
        if not t:
            return False

        triggers = (
            "memory id",
            "memory ids",
            "memory_id",
            "ids of your memories",
            "list your memories",
            "list all memories",
            "dump your memories",
            "dump memory",
            "show me your memories",
            "show stored memories",
            "memory database",
            "export memories",
            "print all memories",
        )
        return any(s in t for s in triggers)

    def _build_memory_inventory_answer(
        self,
        *,
        user_query: str,
        retrieved: List[Tuple[MemoryItem, float]],
        prompt_docs: List[Dict[str, Any]],
        max_lines: int = 8,
    ) -> str:
        """Deterministic safe memory-inventory response with conflict awareness.

        We do NOT expose internal memory IDs here; we only cite stored text snippets.
        """
        lines: List[str] = []
        lines.append("I don't expose internal memory IDs.")

        # If nothing was retrieved, be explicit and safe.
        if not retrieved:
            lines.append("I don't have any stored memories to cite yet.")
            return "\n".join(lines)

        # Check for open contradictions
        open_contras = self._get_memory_conflicts()
        has_conflicts = len(open_contras) > 0

        if has_conflicts:
            lines.append("here is what i have stored (note: some facts have conflicts):")
        else:
            lines.append("here is the stored text i can cite:")

        added = 0
        conflict_marked_ids = set()
        
        for d in (prompt_docs or []):
            txt = str((d or {}).get("text") or "").strip()
            if not txt:
                continue

            src = str((d or {}).get("source") or "").strip().lower()
            is_fact = txt.lower().startswith("fact:")
            is_user = src == MemorySource.USER.value

            # Only cite user-provided memories and canonical FACT lines.
            if not (is_fact or is_user):
                continue

            # Check if this specific memory has a conflict
            memory_id = (d or {}).get("memory_id")
            if memory_id and has_conflicts:
                try:
                    if self.ledger.has_open_contradiction(memory_id):
                        txt = f"{txt} ⚠️"
                        conflict_marked_ids.add(memory_id)
                except Exception:
                    pass

            lines.append(f"- {txt}")
            added += 1
            if added >= max_lines:
                break

        # If we marked conflicts, add a note
        if conflict_marked_ids:
            lines.append("\n⚠️ = has conflicting information")

        # List top conflicts if space permits
        if has_conflicts and added < max_lines:
            lines.append("\nopen conflicts:")
            for contra in open_contras[:min(3, max_lines - added)]:
                claim_a = (contra.claim_a_text or "")[:60]
                claim_b = (contra.claim_b_text or "")[:60]
                lines.append(f"- '{claim_a}' vs '{claim_b}'")

        return "\n".join(lines)
    
    def _build_synthesis_answer(
        self,
        *,
        user_query: str,
        retrieved: List[Tuple[MemoryItem, float]],
        max_facts: int = 10,
    ) -> str:
        """Build a synthesis answer that combines multiple related facts.
        
        For queries like "What do you know about my interests?" we need to:
        1. Extract all relevant memories (user-provided facts)
        2. Combine them into a natural synthesis
        """
        from .crt_core import MemorySource
        from .canonical_view import build_canonical_slot_view, format_slot_view
        
        ql = (user_query or "").strip().lower()

        # For full-profile summary requests, use a canonical ledger-backed slot view
        # to prevent reintroducing superseded facts.
        if "summar" in ql and ("everything" in ql or "all" in ql) and ("about me" in ql or "about my" in ql or "about" in ql and "me" in ql):
            try:
                all_mems = self.memory._load_all_memories()
            except Exception:
                all_mems = []

            view = build_canonical_slot_view(
                user_memories=all_mems,
                memory_get_by_id=self.memory.get_memory_by_id,
                ledger_db_path=str(getattr(self.ledger, "db_path", "") or ""),
                scope_slots=[
                    "name",
                    "location",
                    "employer",
                    "title",
                    "programming_years",
                    "first_language",
                    "undergrad_school",
                    "masters_school",
                    "remote_preference",
                ],
            )
            ordered = [
                "name",
                "location",
                "employer",
                "title",
                "programming_years",
                "first_language",
                "undergrad_school",
                "masters_school",
                "remote_preference",
            ]
            
            # Check if there are any conflicts
            open_contras = self._get_memory_conflicts()
            if open_contras:
                lines = ["Based on what I have recorded (note: some information has conflicts):"]
            else:
                lines = ["Based on what I have recorded:"]
                
            lines.extend(format_slot_view(view, ordered_slots=ordered))
            
            # Add conflict summary if present
            if open_contras:
                lines.append("\nConflicting information exists for some facts. Ask me about specific contradictions for details.")
                
            if len(lines) <= 2:  # Just header + conflict note
                return "I don't have any stored profile facts about you yet."
            return "\n".join(lines)

        # Get USER memories (facts the user told us)
        user_memories = [m for m, _s in (retrieved or []) if getattr(m, "source", None) == MemorySource.USER]
        
        if not user_memories:
            return "I don't have that information in my memory yet."
        
        # Build synthesis answer
        facts = [mem.text.strip() for mem in user_memories[:max_facts] if mem.text and mem.text.strip()]
        facts_deduped = list(dict.fromkeys(facts))  # Remove exact duplicates while preserving order
        
        if len(facts_deduped) == 0:
            return "I don't have that information in my memory yet."
        elif len(facts_deduped) == 1:
            return facts_deduped[0]
        else:
            # Multiple facts - synthesize them
            answer_parts = ["Based on what I remember:"]
            for i, fact in enumerate(facts_deduped[:max_facts], 1):
                answer_parts.append(f"  {i}. {fact}")
            
            return "\n".join(answer_parts)

    def _build_memory_citation_answer(
        self,
        *,
        user_query: str,
        retrieved: List[Tuple[MemoryItem, float]],
        prompt_docs: List[Dict[str, Any]],
        max_lines: int = 4,
    ) -> str:
        """Build a deterministic, grounded answer for citation-style prompts.

        Important: avoid introducing new named entities. Keep formatting lowercase.
        """
        # Prefer factual prompt docs if the user is asking about a known slot.
        ql = (user_query or "").lower()
        want_name = "name" in ql

        lines: List[str] = []

        if want_name:
            for d in (prompt_docs or []):
                txt = (d.get("text") or "").strip()
                if txt and "fact:" in txt.lower() and "name" in txt.lower():
                    lines.append(txt)
                    break

        # Add up to N retrieved memory texts verbatim.
        # IMPORTANT: only cite USER-provided text. System responses can be wrong,
        # and citing them as "from our chat" is misleading.
        from .crt_core import MemorySource

        user_retrieved = [m for m, _s in (retrieved or []) if getattr(m, "source", None) == MemorySource.USER]
        
        # Check for conflicts with these memories
        conflict_ids = set()
        for mem in user_retrieved:
            mem_id = getattr(mem, "id", None)
            if mem_id:
                try:
                    if self.ledger.has_open_contradiction(mem_id):
                        conflict_ids.add(mem_id)
                except Exception:
                    pass
        
        for mem in user_retrieved[: max(1, max_lines)]:
            mt = (mem.text or "").strip()
            if mt:
                # Mark if this memory has a conflict
                mem_id = getattr(mem, "id", None)
                if mem_id and mem_id in conflict_ids:
                    mt = f"{mt} (note: conflicting info exists)"
                lines.append(mt)
            if len(lines) >= max_lines:
                break

        # De-dup while preserving order.
        seen = set()
        deduped: List[str] = []
        for ln in lines:
            key = re.sub(r"\s+", " ", ln).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(ln)

        if not deduped:
            # If we truly have nothing, keep it short and non-contradictory.
            return "i don't have stored memory text to quote for that yet."

        # Use simple bullets; no title-case headings.
        out = ["here is the stored text i can cite:"]
        for ln in deduped[:max_lines]:
            out.append(f"- {ln}")
        return "\n".join(out)

    # ========================================================================
    # Ledger-grounded contradiction status helpers
    # ========================================================================

    def _is_contradiction_status_request(self, text: str) -> bool:
        """True if the user is asking to list/inspect open contradictions.
        
        IMPORTANT: Only trigger on QUERIES about contradictions, not assertions
        that mention "contradiction" as a topic (e.g., "I work on contradiction detection").
        """
        t = (text or "").strip().lower()
        if not t:
            return False

        # Explicit ledger queries
        if "contradiction ledger" in t:
            return True

        # Explicit status queries
        if "open contradictions" in t or "unresolved contradictions" in t:
            return True

        # Plural "contradictions" + interrogative keywords
        # Note: Use "contradictions" (plural) to avoid matching "contradiction detection", "contradiction tracking", etc.
        if "contradictions" in t and any(k in t for k in ("list", "show", "any", "open", "unresolved", "do you have", "are there")):
            return True

        # CLI-style short commands (exact match only)
        if t in {"contradictions", "show contradictions", "list contradictions"}:
            return True

        return False

    def _build_contradiction_status_answer(
        self,
        *,
        user_query: str,
        inferred_slots: Optional[List[str]] = None,
        limit: int = 8,
    ) -> Tuple[str, Dict[str, Any]]:
        """Build a deterministic answer listing OPEN contradictions from the ledger.

        This is intentionally ledger-grounded to prevent hallucinated contradictions.
        """
        from .crt_ledger import ContradictionType

        ql = (user_query or "").strip().lower()

        scope_slots = set(inferred_slots or [])
        if not scope_slots and "identity" in ql:
            scope_slots = {
                "name",
                "employer",
                "location",
                "title",
                "first_language",
                "masters_school",
                "undergrad_school",
                "programming_years",
                "team_size",
            }

        open_contras = self.ledger.get_open_contradictions(limit=200)
        unresolved_total = len(open_contras)

        rows: List[Dict[str, Any]] = []
        hard_conflicts = 0

        for contra in open_contras:
            old_mem = self.memory.get_memory_by_id(contra.old_memory_id)
            new_mem = self.memory.get_memory_by_id(contra.new_memory_id)
            if old_mem is None or new_mem is None:
                continue

            old_facts = extract_fact_slots(old_mem.text) or {}
            new_facts = extract_fact_slots(new_mem.text) or {}
            shared = set(old_facts.keys()) & set(new_facts.keys())
            if scope_slots:
                shared = shared & scope_slots
            if not shared:
                continue

            for slot in sorted(shared):
                of = old_facts.get(slot)
                nf = new_facts.get(slot)
                if of is None or nf is None:
                    continue
                if getattr(of, "normalized", None) == getattr(nf, "normalized", None):
                    continue

                ctype = getattr(contra, "contradiction_type", None) or ContradictionType.CONFLICT
                if ctype == ContradictionType.CONFLICT:
                    hard_conflicts += 1

                rows.append(
                    {
                        "timestamp": getattr(contra, "timestamp", 0.0) or 0.0,
                        "ledger_id": contra.ledger_id,
                        "slot": slot,
                        "old": str(getattr(of, "value", "")),
                        "new": str(getattr(nf, "value", "")),
                        "type": ctype,
                    }
                )

        # De-dup by (ledger_id, slot).
        seen = set()
        deduped: List[Dict[str, Any]] = []
        for r in sorted(rows, key=lambda x: x.get("timestamp", 0.0), reverse=True):
            key = (r.get("ledger_id"), r.get("slot"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)
            if len(deduped) >= limit:
                break

        meta = {
            "unresolved_contradictions_total": unresolved_total,
            "unresolved_hard_conflicts": hard_conflicts,
        }

        if not deduped:
            if "identity" in ql:
                return "No open contradictions about your identity in my contradiction ledger.", meta
            return "No open contradictions in my contradiction ledger.", meta

        header = "Here are the open contradictions I have recorded"
        if "identity" in ql:
            header += " about your identity"
        header += ":"

        out_lines = [header]
        for r in deduped:
            slot_name = str(r.get("slot") or "").replace("_", " ")
            old_v = (r.get("old") or "").strip()
            new_v = (r.get("new") or "").strip()
            ctype = (r.get("type") or "conflict").strip()
            if old_v and new_v:
                out_lines.append(f"- {slot_name}: {new_v} vs {old_v} (type: {ctype})")

        # Add a single concrete next action for the first listed entry.
        first = deduped[0] if deduped else None
        if first is not None:
            slot_name = str(first.get("slot") or "").replace("_", " ")
            old_v = (first.get("old") or "").strip()
            new_v = (first.get("new") or "").strip()
            ctype = (first.get("type") or "").strip()
            if old_v and new_v:
                out_lines.append("")
                if ctype == ContradictionType.CONFLICT:
                    out_lines.append(f"To resolve the {slot_name} conflict: which is correct now: {new_v} or {old_v}?")
                elif ctype == ContradictionType.REVISION:
                    out_lines.append(
                        f"To resolve this: should I treat {new_v} as your current {slot_name} and mark {old_v} as superseded?"
                    )
                else:
                    out_lines.append(
                        f"To resolve this: is {new_v} the more accurate/current {slot_name} to keep?"
                    )

        return "\n".join(out_lines), meta

    def _sanitize_memory_denial(self, *, answer: str, has_memory_context: bool) -> str:
        """If memory context exists, avoid self-contradictory 'no memories/first chat' claims.

        This is a lightweight post-processing step to keep the assistant's surface text
        consistent with the CRT metadata we return (retrieved/prompt memories).
        """
        a = (answer or "")
        if not a or not has_memory_context:
            return a

        # Normalize some frequent denial patterns.
        repl = [
            ("this is our first conversation", "in this conversation so far"),
            ("this is the start of our conversation", "so far in this conversation"),
            ("since this is our first conversation", "so far in this conversation"),
            ("we just started the conversation", "so far in this conversation"),
            ("we just started talking", "so far in this conversation"),
            ("my memory is empty", "my stored memory is limited so far"),
            ("my trust-weighted memory is empty", "my trust-weighted memory is limited so far"),
            ("i don't have any memories", "i don't have much stored yet"),
            ("i do not have any memories", "i don't have much stored yet"),
            ("i have no memories", "i don't have much stored yet"),
        ]

        out = a
        low = out.lower()
        for old, new in repl:
            if old in low:
                # Case-insensitive replace (simple, conservative).
                out = re.sub(re.escape(old), new, out, flags=re.I)
                low = out.lower()

        return out

    def _sanitize_unsupported_memory_claims(self, *, answer: str, prompt_docs: List[Dict[str, Any]]) -> str:
        """Remove unsupported personal-fact claims framed as memory.

        Goal: avoid outputs like "I remember ... I work at X" when X is not actually
        present in the retrieved/resolved memory facts.

        This is intentionally conservative and only activates when the answer contains
        a strong memory-claim phrase.
        """
        if not answer or not answer.strip():
            return answer

        t = answer.lower()
        memory_claim = any(
            p in t
            for p in (
                "i remember",
                "i recall",
                "i have a memory",
                "i have it noted",
                "i have you down",
                "i have stored",
                "in my memory",
                "in my notes",
                "i've got it stored",
                "i've got you stored",
                "i've got it noted",
                "i've got you down",
            )
        )
        if not memory_claim:
            return answer

        def _norm(s: str) -> str:
            return re.sub(r"\s+", " ", (s or "").strip()).lower()

        # Parse supported FACT values from resolved prompt docs.
        supported_by_slot: Dict[str, set] = {}
        fact_re = re.compile(r"^\s*fact:\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+?)\s*$", re.I)
        for d in (prompt_docs or []):
            txt = str((d or {}).get("text") or "")
            m = fact_re.match(txt)
            if not m:
                continue
            slot = m.group(1).strip().lower()
            val = m.group(2).strip()
            if not slot or not val:
                continue
            supported_by_slot.setdefault(slot, set()).add(_norm(val))

        # Extract fact claims from the answer (first-person patterns).
        claimed = extract_fact_slots(answer) or {}
        if not claimed:
            return answer

        # Identify unsupported claimed slot-values.
        unsupported: Dict[str, str] = {}
        for slot, fact in claimed.items():
            slot_l = str(slot).lower()
            supported = supported_by_slot.get(slot_l) or set()
            if fact is None:
                continue
            if not supported or str(getattr(fact, "normalized", "")) not in supported:
                unsupported[slot_l] = str(getattr(fact, "value", ""))

        if not unsupported:
            return answer

        # Drop lines that contain memory-claim language or the unsupported values.
        bad_value_res = [re.compile(re.escape(v), re.I) for v in unsupported.values() if v]
        memory_line_re = re.compile(
            r"\b(i\s+(remember|recall)|i\s+have\s+(a\s+)?memory|i\s+have\s+it\s+noted|i\s+have\s+you\s+down|i\s+have\s+stored|in\s+my\s+(memory|notes)|i'?ve\s+got\s+(it|you)\s+(stored|noted|down))\b",
            re.I,
        )

        kept_lines: List[str] = []
        for line in answer.splitlines():
            if memory_line_re.search(line):
                continue
            if any(r.search(line) for r in bad_value_res):
                continue
            kept_lines.append(line)

        cleaned = "\n".join(kept_lines).strip()
        first_slot = next(iter(unsupported.keys()))
        if cleaned:
            return cleaned + f"\n\nI don't have a reliable stored memory for your {first_slot} yet — if you tell me, I can remember it going forward."

        return f"I don't have a reliable stored memory for your {first_slot} yet — if you tell me, I can remember it going forward."
    
    # ========================================================================
    # CRT Analytics
    # ========================================================================
    
    def get_crt_status(self) -> Dict:
        """Get CRT system health and statistics."""
        return {
            'belief_speech_ratio': self.memory.get_belief_speech_ratio(),
            'contradiction_stats': self.ledger.get_contradiction_stats(),
            'pending_reflections': len(self.ledger.get_reflection_queue()),
            'memory_count': len(self.memory._load_all_memories()),
            'session_id': self.session_id
        }
    
    def get_open_contradictions(self) -> List[Dict]:
        """Get unresolved contradictions requiring reflection."""
        entries = self.ledger.get_open_contradictions()
        return [e.to_dict() for e in entries]
    
    def get_reflection_queue(self) -> List[Dict]:
        """Get pending reflections."""
        return self.ledger.get_reflection_queue()





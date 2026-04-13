"""Fact extraction, slot inference, and user-fact surface helpers.

Extracted from CRTEnhancedRAG — every function takes ``engine`` as its
first parameter instead of ``self`` (except the static-like
``_canonical_user_slot_name``).
"""
from __future__ import annotations
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from ._engine import CRTEnhancedRAG

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Imports used by the bodies (non-lazy)
# ---------------------------------------------------------------------------
from personal_agent.exceptions import log_swallowed_exception
from personal_agent.crt_core import MemorySource
from personal_agent.crt_memory import MemoryItem
from personal_agent.fact_slots import extract_fact_slots
from personal_agent.two_tier_facts import TwoTierExtractionResult


# ======================================================================
# _extract_facts_cached
# ======================================================================

def _extract_facts_cached(engine: "CRTEnhancedRAG", text: str) -> Dict[str, Any]:
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
    if len(text) > engine._max_text_size:
        return extract_fact_slots(text) or {}

    # Check cache (LRU: move to end on access)
    if text in engine._fact_extraction_cache:
        engine._fact_extraction_cache.move_to_end(text)
        return engine._fact_extraction_cache[text]

    # Cache miss: extract and store
    result = extract_fact_slots(text) or {}
    engine._fact_extraction_cache[text] = result

    # LRU eviction: remove oldest entry when cache is full
    if len(engine._fact_extraction_cache) > engine._max_cache_entries:
        engine._fact_extraction_cache.popitem(last=False)  # Remove oldest (FIFO)

    return result


# ======================================================================
# _extract_facts_two_tier
# ======================================================================

def _extract_facts_two_tier(engine: "CRTEnhancedRAG", text: str, skip_llm: bool = False) -> TwoTierExtractionResult:
    """
    Extract facts using two-tier system (hard slots + open tuples).

    This method uses the TwoTierFactSystem to extract both:
    - Tier A (Hard Slots): Critical facts via regex (name, employer, location, etc.)
    - Tier B (Open Tuples): Flexible facts via LLM (hobbies, preferences, etc.)

    Args:
        text: Memory text to extract facts from
        skip_llm: If True, only extract hard slots (faster, no LLM call)

    Returns:
        TwoTierExtractionResult containing hard_facts and open_tuples
    """
    if engine.two_tier_system is None:
        # Fallback: use regex-only extraction
        hard_facts = extract_fact_slots(text) or {}
        result = TwoTierExtractionResult(
            hard_facts=hard_facts,
            open_tuples=[],
            source_text=text,
            extraction_time=0.0,
            methods_used=["regex_fallback"]
        )
        return result

    # Use two-tier system
    try:
        result = engine.two_tier_system.extract_facts(text, skip_llm=skip_llm)
        return result
    except Exception as e:
        logger.warning(f"[TWO_TIER] Extraction failed: {e}, falling back to regex")
        # Fallback to regex-only
        hard_facts = extract_fact_slots(text) or {}
        result = TwoTierExtractionResult(
            hard_facts=hard_facts,
            open_tuples=[],
            source_text=text,
            extraction_time=0.0,
            methods_used=["regex_fallback_after_error"]
        )
        return result


# ======================================================================
# _canonical_user_slot_name  (static-like)
# ======================================================================

def _canonical_user_slot_name(slot: Optional[str]) -> str:
    slot_name = str(slot or "").strip()
    if slot_name.lower().startswith("user."):
        slot_name = slot_name[5:]
    return slot_name.strip()


# ======================================================================
# _get_latest_user_slot_value
# ======================================================================

def _get_latest_user_slot_value(engine: "CRTEnhancedRAG", slot: str) -> Optional[str]:
    """
    Get the latest value for a given slot from USER memories.

    Optimized: Uses filtered query to load only USER memories instead of all memories.
    """
    slot = (slot or "").strip().lower()
    if not slot:
        return None
    try:
        # OPTIMIZATION: Load only USER memories instead of all memories
        user_memories = engine.memory._load_memories_filtered(source=MemorySource.USER)
    except Exception:
        return None

    best_val: Optional[str] = None
    best_ts: float = -1.0
    for mem in user_memories:
        facts = _extract_facts_cached(engine, mem.text)
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


# ======================================================================
# _get_latest_user_name_guess
# ======================================================================

def _get_latest_user_name_guess(engine: "CRTEnhancedRAG") -> Optional[str]:
    """
    Best-effort user name extraction from USER memories.

    Prefer structured "FACT: name = ..." if present; otherwise fall back to
    simple textual patterns like "my name is ...".

    Optimized: Uses filtered query to load only USER memories.
    """
    try:
        # OPTIMIZATION: Load only USER memories instead of all memories
        user_memories = engine.memory._load_memories_filtered(source=MemorySource.USER)
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


# ======================================================================
# _query_mentions_user_name
# ======================================================================

def _query_mentions_user_name(engine: "CRTEnhancedRAG", user_query: str, user_name: str) -> bool:
    q = (user_query or "").strip().lower()
    name = (user_name or "").strip().lower()
    if not q or not name:
        return False
    return name in q


# ======================================================================
# _get_memory_conflicts
# ======================================================================

def _get_memory_conflicts(engine: "CRTEnhancedRAG", memory_id: Optional[str] = None) -> List[Any]:
    """Check if a memory has open contradictions.

    Args:
        memory_id: Optional specific memory to check. If None, returns all open contradictions.

    Returns:
        List of contradiction entries
    """
    try:
        open_contras = engine.ledger.get_open_contradictions(limit=100)

        if memory_id is None:
            return open_contras

        # Filter to just this memory's contradictions
        return [
            c for c in open_contras
            if (hasattr(c, 'claim_a_id') and c.claim_a_id == memory_id) or
               (hasattr(c, 'claim_b_id') and c.claim_b_id == memory_id)
        ]
    except Exception as e:
        log_swallowed_exception("crt_rag._get_memory_conflicts", e)
        return []


# ======================================================================
# _load_thread_user_memories
# ======================================================================

def _load_thread_user_memories(
    engine: "CRTEnhancedRAG",
    *,
    thread_id: Optional[str] = None,
    exclude_memory_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> List[MemoryItem]:
    """Load USER memories scoped to the authenticated user (or thread as fallback)."""
    try:
        memories = engine.memory._load_memories_filtered(
            source=MemorySource.USER,
            user_id=user_id,
            thread_id=str(thread_id) if (thread_id is not None and user_id is None) else None,
        )
    except Exception:
        memories = [
            m for m in engine.memory._load_all_memories(user_id=user_id)
            if m.source == MemorySource.USER
        ]

    if exclude_memory_id:
        memories = [m for m in memories if m.memory_id != exclude_memory_id]
    return memories


# ======================================================================
# get_effective_user_facts
# ======================================================================

def get_effective_user_facts(
    engine: "CRTEnhancedRAG",
    thread_id: Optional[str] = None,
    *,
    include_memory_fallback: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """Build a canonical user-fact view across thread-local and global surfaces."""
    thread_key = str(thread_id or "default").strip() or "default"
    effective: Dict[str, Dict[str, Any]] = {}

    def _put(slot: str, payload: Dict[str, Any], priority: int) -> None:
        # -- Profile slot resolution --
        # Priority order: 3 (thread fact store) > 2 (global profile) > 1 (memory fallback)
        # Within same priority: highest trust wins, then most recent timestamp.
        # This ensures the profile shows the most trusted value, not the first found.
        slot_name = _canonical_user_slot_name(slot)
        if not slot_name:
            return
        current = effective.get(slot_name)
        current_priority = int((current or {}).get("_priority") or -1)
        current_trust = float((current or {}).get("trust") or 0.0)
        current_timestamp = float((current or {}).get("timestamp") or 0.0)
        new_trust = float(payload.get("trust") or 0.0)
        new_timestamp = float(payload.get("timestamp") or 0.0)
        # Higher priority surface normally wins, BUT:
        # If a lower-priority source (memory) has significantly higher trust
        # than a higher-priority source (profile), the memory wins.
        # This prevents stale profile values from overriding well-evidenced memories.
        TRUST_OVERRIDE_DELTA = 0.15  # memory needs to be this much more trusted to override profile
        if current is not None and current_priority > priority:
            # Allow trust-based override: if new value has much higher trust, it wins
            if new_trust > current_trust + TRUST_OVERRIDE_DELTA:
                logger.info(
                    f"[PROFILE_TRUST_OVERRIDE] {slot_name}: memory trust {new_trust:.2f} "
                    f"overrides profile trust {current_trust:.2f} (delta={new_trust - current_trust:.2f})"
                )
                pass  # fall through to set the new value
            else:
                return
        # Same priority: highest trust wins
        if current is not None and current_priority == priority:
            if current_trust > new_trust:
                return
            # Equal trust: most recent timestamp wins
            if current_trust == new_trust and current_timestamp > new_timestamp:
                return
        effective[slot_name] = {**payload, "_priority": priority}

    if engine.fact_store is not None:
        try:
            thread_facts = engine.fact_store.get_all_facts(thread_id=thread_key) or {}
        except Exception:
            thread_facts = {}
        for slot, fact in thread_facts.items():
            value = str((fact or {}).get("value") or "").strip()
            if not value:
                continue
            _put(
                slot,
                {
                    "slot": _canonical_user_slot_name(slot),
                    "value": value,
                    "source_surface": "thread_fact_store",
                    "source_thread": str((fact or {}).get("thread_id") or thread_key),
                    "authority": "confirmed",
                    "origin": None,
                    "confidence": float((fact or {}).get("trust") or 0.95),
                    "trust": float((fact or {}).get("trust") or 0.95),
                    "timestamp": None,
                    "memory_id": None,
                },
                3,
            )

    try:
        profile_facts = engine.user_profile.get_all_facts() or {}
    except Exception:
        profile_facts = {}
    for slot, fact in profile_facts.items():
        if hasattr(engine.user_profile, "_is_profile_slot") and not engine.user_profile._is_profile_slot(slot):
            continue
        value = str(getattr(fact, "value", "") or "").strip()
        if not value:
            continue
        _put(
            slot,
            {
                "slot": _canonical_user_slot_name(slot),
                "value": value,
                "source_surface": "global_profile",
                "source_thread": getattr(fact, "source_thread", None),
                "authority": "confirmed",
                "origin": None,
                "confidence": float(getattr(fact, "confidence", 0.9) or 0.9),
                "trust": float(getattr(fact, "confidence", 0.9) or 0.9),
                "timestamp": float(getattr(fact, "timestamp", 0.0) or 0.0),
                "memory_id": None,
            },
            2,
        )

    if include_memory_fallback:
        for mem in _load_thread_user_memories(engine, thread_id=thread_key):
            if bool(getattr(mem, "deprecated", False)):
                continue
            if not engine.memory.can_answer_user_fact(mem):
                continue
            facts = extract_fact_slots(getattr(mem, "text", "") or "") or {}
            for slot, fact in facts.items():
                value = str(getattr(fact, "value", "") or "").strip()
                if not value:
                    continue
                _put(
                    slot,
                    {
                        "slot": _canonical_user_slot_name(slot),
                        "value": value,
                        "source_surface": "thread_memory",
                        "source_thread": getattr(mem, "thread_id", thread_key),
                        "authority": str(getattr(mem, "authority", "confirmed") or "confirmed"),
                        "origin": getattr(mem, "origin", None),
                        "confidence": float(getattr(mem, "confidence", 0.0) or 0.0),
                        "trust": float(getattr(mem, "trust", 0.0) or 0.0),
                        "timestamp": float(getattr(mem, "timestamp", 0.0) or 0.0),
                        "memory_id": getattr(mem, "memory_id", None),
                    },
                    1,
                )

    for slot, payload in list(effective.items()):
        payload.pop("_priority", None)
        payload["slot"] = slot
    return effective


# ======================================================================
# search_effective_user_facts
# ======================================================================

def search_effective_user_facts(
    engine: "CRTEnhancedRAG",
    query: str,
    *,
    thread_id: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    query_text = str(query or "").strip().lower()
    if not query_text:
        return []

    inferred_slots = set(_infer_slots_from_query(engine, query_text))
    tokens = [tok for tok in re.findall(r"[a-z0-9_]+", query_text) if tok]
    matches: List[Tuple[int, Dict[str, Any]]] = []
    for slot, fact in get_effective_user_facts(engine, thread_id=thread_id).items():
        haystack = f"{slot.replace('_', ' ')} {fact.get('value', '')}".lower()
        slot_score = 0
        if slot in inferred_slots:
            slot_score += 4
        if slot.replace("_", " ") in query_text:
            slot_score += 2
        token_hits = sum(1 for tok in tokens if tok in haystack)
        if slot_score <= 0 and token_hits <= 0:
            continue
        matches.append((slot_score + token_hits, fact))

    matches.sort(
        key=lambda item: (
            item[0],
            float((item[1] or {}).get("timestamp") or 0.0),
            float((item[1] or {}).get("trust") or 0.0),
        ),
        reverse=True,
    )
    return [fact for _, fact in matches[: max(1, int(limit))]]


# ======================================================================
# _add_reintroduction_flags
# ======================================================================

def _add_reintroduction_flags(engine: "CRTEnhancedRAG", result: Dict[str, Any]) -> Dict[str, Any]:
    """Add reintroduced_claim flags to all memories in a query result.

    INVARIANT: Every memory with an open contradiction MUST be flagged.
    This method ensures ALL query result paths include the flags.
    """
    # Flag retrieved_memories
    if 'retrieved_memories' in result and isinstance(result['retrieved_memories'], list):
        for mem in result['retrieved_memories']:
            if isinstance(mem, dict):
                mem_id = mem.get('memory_id')
                if mem_id and hasattr(engine.ledger, 'has_open_contradiction'):
                    mem['reintroduced_claim'] = engine.ledger.has_open_contradiction(mem_id)
                else:
                    mem['reintroduced_claim'] = False

    # Flag prompt_memories
    if 'prompt_memories' in result and isinstance(result['prompt_memories'], list):
        for mem in result['prompt_memories']:
            if isinstance(mem, dict):
                mem_id = mem.get('memory_id')
                if mem_id and hasattr(engine.ledger, 'has_open_contradiction'):
                    mem['reintroduced_claim'] = engine.ledger.has_open_contradiction(mem_id)
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


# ======================================================================
# _flag_reintroduced_claims
# ======================================================================

def _flag_reintroduced_claims(engine: "CRTEnhancedRAG", memories: List[Any]) -> List[Dict[str, Any]]:
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
    open_contras = _get_memory_conflicts(engine)

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


# ======================================================================
# _infer_slots_from_query
# ======================================================================

def _infer_slots_from_query(engine: "CRTEnhancedRAG", text: str) -> List[str]:
    """Infer which fact slots a question is asking about.

    This is intentionally heuristic and tuned to the stress tests.

    IMPORTANT: Compound-noun queries like "dog's name" or "spouse's name"
    must NOT match the bare "name" slot  -  they have their own dedicated slots.
    """
    t = (text or "").strip().lower()
    if not t:
        return []

    slots: List[str] = []

    # -- Compound-noun slots (must be checked BEFORE bare "name") ------
    # These patterns consume the query so bare "name" won't fire.
    _compound_name_matched = False

    # Pet / animal names
    if re.search(r"\b(dog|cat|pet|puppy|kitten|animal|bird|fish|hamster|rabbit|parrot)('?s)?\s*(name|called)\b", t) or \
       re.search(r"\bname\s+of\s+(my\s+)?(dog|cat|pet|puppy|kitten|animal)\b", t):
        slots.append("pet_name")
        _compound_name_matched = True

    # Spouse / partner names
    if re.search(r"\b(spouse|wife|husband|partner|significant other|fiancee?|girlfriend|boyfriend)('?s)?\s*(name|called)\b", t) or \
       re.search(r"\bname\s+of\s+(my\s+)?(spouse|wife|husband|partner)\b", t) or \
       re.search(r"\b(married to|dating|engaged to)\b", t):
        slots.append("spouse")
        _compound_name_matched = True

    # Child / kid names
    if re.search(r"\b(child|kid|son|daughter|baby)('?s)?\s*(name|called)\b", t) or \
       re.search(r"\bname\s+of\s+(my\s+)?(child|kid|son|daughter)\b", t):
        slots.append("child_name")
        _compound_name_matched = True

    # Project name (already existed but now gates bare "name")
    if re.search(r"\bproject('?s)?\s*(name|called)\b", t) or \
       re.search(r"\bname\s+of\s+(my\s+|the\s+)?project\b", t):
        slots.append("project_name")
        _compound_name_matched = True

    # Nickname / alias queries map to name-history retrieval.
    if re.search(r"\b(nickname|nicknames|alias|aliases)\b", t):
        slots.append("name")

    # Bare "name"  -  only if no compound-noun matched.
    # Use word boundary so "nicknames" does not accidentally match "name".
    # Exclude self-referential queries ("what is YOUR name") -- those ask
    # about the assistant, not about the user's stored name fact.
    _is_asking_assistant_name = bool(re.search(
        r"\b(what('?s| is) your name|who are you|your name)\b", t
    ))
    if not _compound_name_matched and not _is_asking_assistant_name and re.search(r"\bname\b", t):
        slots.append("name")

    if ("favorite" in t or "favourite" in t) and ("color" in t or "colour" in t):
        slots.append("favorite_color")

    # -- Favorite language / programming language ----------------------
    if ("favorite" in t or "favourite" in t or "preferred" in t) and \
       ("language" in t or "programming" in t):
        slots.append("favorite_language")
    elif "programming language" in t and not ("how many" in t or "first" in t or "start" in t):
        slots.append("favorite_language")

    # -- Favorite food -------------------------------------------------
    if ("favorite" in t or "favourite" in t) and ("food" in t or "meal" in t or "dish" in t or "cuisine" in t):
        slots.append("favorite_food")

    # -- Drink / beverage ----------------------------------------------
    if ("favorite" in t or "favourite" in t) and ("drink" in t or "beverage" in t or "coffee" in t or "tea" in t):
        slots.append("favorite_drink")
    elif re.search(r"\b(what\s+do\s+i\s+drink|coffee\s+or\s+tea|morning\s+drink|beverage)\b", t):
        slots.append("favorite_drink")

    # -- Favorite book / movie / music ---------------------------------
    if ("favorite" in t or "favourite" in t) and ("book" in t or "novel" in t):
        slots.append("favorite_book")
    if ("favorite" in t or "favourite" in t) and ("movie" in t or "film" in t):
        slots.append("favorite_movie")
    if ("favorite" in t or "favourite" in t) and ("music" in t or "song" in t or "band" in t or "artist" in t):
        slots.append("favorite_music")

    # -- Hobby / interest ----------------------------------------------
    if re.search(r"\b(hobby|hobbies|interest|interests|free time|spare time|pastime)\b", t):
        slots.append("hobby")

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

    # -- Birthday / birth date -----------------------------------------
    if re.search(r"\b(birthday|birth\s*date|born|date\s+of\s+birth|dob)\b", t):
        slots.append("birthday")

    # -- Email / phone -------------------------------------------------
    if re.search(r"\b(email|e-mail|mail\s+address)\b", t):
        slots.append("email")
    if re.search(r"\b(phone|phone\s+number|cell|mobile)\b", t):
        slots.append("phone")

    # De-dup, preserve order
    seen = set()
    out: List[str] = []
    for s in slots:
        if s not in seen:
            out.append(s)
            seen.add(s)
    return out


# ======================================================================
# _is_assistant_profile_question
# ======================================================================

def _is_assistant_profile_question(engine: "CRTEnhancedRAG", text: str) -> bool:
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
        r"\bwhere\s+do\s+you\s+work\b",
        r"\bwho\s+do\s+you\s+work\s+for\b",
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

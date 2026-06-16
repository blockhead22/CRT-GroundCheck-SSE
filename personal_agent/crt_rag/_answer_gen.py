"""CRT RAG — answer generation (slot answers, variation, summaries).

Delegate functions extracted from CRTEnhancedRAG; each takes
``engine`` as its first argument in place of ``self``.
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from ._engine import CRTEnhancedRAG

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Imports used by the bodies (non-lazy)
# ---------------------------------------------------------------------------
from personal_agent.crt_core import MemorySource, SSEMode, encode_vector
from personal_agent.crt_memory import MemoryItem
from personal_agent.fact_slots import extract_fact_slots

# Session DB for response variation (optional)
try:
    from personal_agent.db_utils import get_thread_session_db
    _SESSION_DB_AVAILABLE = True
except ImportError:
    _SESSION_DB_AVAILABLE = False


# ======================================================================
# _build_user_named_reference_answer
# ======================================================================

def _build_user_named_reference_answer(engine: "CRTEnhancedRAG", user_query: str, inferred_slots: List[str]) -> str:
    cfg = (engine.runtime_config.get("user_named_reference") or {}) if isinstance(engine.runtime_config, dict) else {}
    responses = (cfg.get("responses") or {}) if isinstance(cfg.get("responses"), dict) else {}

    def _resp(key: str, fallback: str) -> str:
        value = responses.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return fallback

    # Prefer canonical slot answers if available.
    slot_answer = _answer_from_fact_slots(engine, inferred_slots)
    if slot_answer:
        return slot_answer

    # Otherwise, fall back to strictly chat-grounded work-related statements.
    try:
        all_memories = engine.memory._load_all_memories()
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
        "I don't have a reliable stored memory of your occupation/job yet  -  if you tell me, I can remember it going forward.",
    )


# ======================================================================
# _build_resolved_memory_docs
# ======================================================================

def _build_resolved_memory_docs(
    engine: "CRTEnhancedRAG",
    retrieved: List[Tuple[MemoryItem, float]],
    max_fact_lines: int = 8,
    max_fallback_lines: int = 0,
    query: Optional[str] = None,
    thread_id: Optional[str] = None,
    usage_trace_id: Optional[str] = None,
    usage_reason: Optional[str] = None,
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
        if mem.source == MemorySource.USER and not engine.memory.can_answer_user_fact(mem):
            continue
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
        # Find similarity score from the original retrieval list
        sim_score = next((s for m, s in retrieved if m.memory_id == mem.memory_id), None)
        resolved_docs.append(
            {
                "text": f"FACT: {slot} = {fact.value}",
                "raw_text": mem.text,
                "memory_id": mem.memory_id,
                "trust": mem.trust,
                "confidence": mem.confidence,
                "source": mem.source.value,
                "similarity": sim_score,
                "timestamp": getattr(mem, 'timestamp', None),
            }
        )

    # If we extracted no facts at all, fall back to raw memory lines.
    if not resolved_docs:
        fallback_docs = [
            {
                "text": mem.text,
                "raw_text": mem.text,
                "memory_id": mem.memory_id,
                "trust": mem.trust,
                "confidence": mem.confidence,
                "source": mem.source.value,
                "similarity": score,
            }
            for mem, score in retrieved
        ]
        engine._record_memory_usage(
            fallback_docs,
            event_type="prompt_included",
            reason=usage_reason or "resolved_memory_docs",
            usage_trace_id=usage_trace_id,
            query=query,
            thread_id=thread_id,
            metadata={"doc_mode": "raw_fallback"},
        )
        return fallback_docs

    # Add non-slot raw memory lines (including self-knowledge, conversation context, etc.).
    # These are crucial for questions about the system's architecture or conversational flow.
    seen_ids = {d["memory_id"] for d in resolved_docs}
    fallback_added = 0
    # When max_fallback_lines > 0 (self-referential queries), allow up to 5 non-slot docs.
    # Otherwise, respect the caller's limit (0 = no extra context for plain fact queries).
    max_non_slot = max(max_fallback_lines, 5) if max_fallback_lines > 0 else 0
    for mem, score in retrieved:
        if fallback_added >= max_non_slot:
            break
        if mem.memory_id in seen_ids:
            continue
        resolved_docs.append(
            {
                "text": mem.text,
                "raw_text": mem.text,
                "memory_id": mem.memory_id,
                "trust": mem.trust,
                "confidence": mem.confidence,
                "source": mem.source.value,
                "similarity": score,
            }
        )
        fallback_added += 1

    engine._record_memory_usage(
        resolved_docs,
        event_type="prompt_included",
        reason=usage_reason or "resolved_memory_docs",
        usage_trace_id=usage_trace_id,
        query=query,
        thread_id=thread_id,
        metadata={"doc_mode": "resolved"},
    )
    return resolved_docs


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

    # --- Compound-noun slots (must be checked BEFORE bare "name") ------
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
    # Exclude self-referential queries ("what is YOUR name") --- those ask
    # about the assistant, not about the user's stored name fact.
    _is_asking_assistant_name = bool(re.search(
        r"\b(what('?s| is) your name|who are you|your name)\b", t
    ))
    if not _compound_name_matched and not _is_asking_assistant_name and re.search(r"\bname\b", t):
        slots.append("name")

    if ("favorite" in t or "favourite" in t) and ("color" in t or "colour" in t):
        slots.append("favorite_color")

    # --- Favorite language / programming language ----------------------
    if ("favorite" in t or "favourite" in t or "preferred" in t) and \
       ("language" in t or "programming" in t):
        slots.append("favorite_language")
    elif "programming language" in t and not ("how many" in t or "first" in t or "start" in t):
        slots.append("favorite_language")

    # --- Favorite food -------------------------------------------------
    if ("favorite" in t or "favourite" in t) and ("food" in t or "meal" in t or "dish" in t or "cuisine" in t):
        slots.append("favorite_food")

    # --- Drink / beverage ----------------------------------------------
    if ("favorite" in t or "favourite" in t) and ("drink" in t or "beverage" in t or "coffee" in t or "tea" in t):
        slots.append("favorite_drink")
    elif re.search(r"\b(what\s+do\s+i\s+drink|coffee\s+or\s+tea|morning\s+drink|beverage)\b", t):
        slots.append("favorite_drink")

    # --- Favorite book / movie / music ---------------------------------
    if ("favorite" in t or "favourite" in t) and ("book" in t or "novel" in t):
        slots.append("favorite_book")
    if ("favorite" in t or "favourite" in t) and ("movie" in t or "film" in t):
        slots.append("favorite_movie")
    if ("favorite" in t or "favourite" in t) and ("music" in t or "song" in t or "band" in t or "artist" in t):
        slots.append("favorite_music")

    # --- Hobby / interest ----------------------------------------------
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

    # --- Birthday / birth date -----------------------------------------
    if re.search(r"\b(birthday|birth\s*date|born|date\s+of\s+birth|dob)\b", t):
        slots.append("birthday")

    # --- Email / phone -------------------------------------------------
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


# ======================================================================
# _build_assistant_profile_answer
# ======================================================================

def _build_assistant_profile_answer(engine: "CRTEnhancedRAG", user_query: str) -> str:
    # Deterministic, chat-agnostic answer: don't claim the user said things.
    cfg = (engine.runtime_config.get("assistant_profile") or {}) if isinstance(engine.runtime_config, dict) else {}
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
            "I'm Aether, a verified AI system built on CRT-GroundCheck. My memory, contradiction checks, and verification stay under the local CRT control layer.",
        )

    if re.search(r"\b(occupation|job|role)\b", q):
        return _resp(
            "occupation",
            "I'm Aether, a verified AI system. My role is to remember what you tell me, verify answers against stored memories, and catch contradictions.",
        )

    if re.search(r"\b(purpose)\b", q) or re.search(r"\bwhat\s+do\s+you\s+do\b", q):
        return _resp(
            "purpose",
            "I store your facts as trust-weighted memories, verify answers with CRT-as-Critic, track contradictions, and route generation through a local-first control layer.",
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
                "I don't have filmmaking experience  -  I'm an AI system. But I can help with filmmaking concepts and remember your projects.",
            )
        return _resp(
            "background_general",
            "I don't have personal experiences - I'm a software system built on GroundCheck memory, CRT-as-Critic verification, a contradiction ledger, and local observability.",
        )

    if re.search(r"\bwhere\s+do\s+you\s+work\b", q) or re.search(r"\bwho\s+do\s+you\s+work\s+for\b", q):
        return _resp(
            "workplace",
            "I don't have a workplace or employer - I'm an AI assistant system running under the CRT control layer.",
        )

    # Generic fallback for "who/what are you".
    return _resp("identity", "I'm a personal AI assistant powered by Claude, built on CRT-GroundCheck. My memory, contradiction checks, verification, routing, and observability stay under the local CRT control layer. Depending on configuration, generation may use a local or cloud model.")


# ======================================================================
# _augment_retrieval_with_slot_memories
# ======================================================================

def _augment_retrieval_with_slot_memories(
    engine: "CRTEnhancedRAG",
    retrieved: List[Tuple[MemoryItem, float]],
    slots: List[str],
    *,
    thread_id: Optional[str] = None,
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
    all_memories = engine.memory._load_all_memories()
    thread_key = str(thread_id or "default").strip() or "default"

    def _in_thread_scope(thread_value: Optional[str]) -> bool:
        tv = str(thread_value or "").strip()
        if tv == thread_key:
            return True
        if thread_key == "default" and not tv:
            return True
        return False

    def _normalize_profile_value(slot_name: str, raw_value: Any) -> Optional[str]:
        value = str(raw_value or "").strip()
        if not value:
            return None
        value_upper = value.upper()
        if value_upper.startswith("LEFT:"):
            return None
        if slot_name == "employer" and value_upper.startswith("BOTH "):
            value = value[5:].strip()
            if not value:
                return None
        return value

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
            # For employer, prefer thread-local USER memories when present.
            # If none exist in-thread, allow thread-scoped profile fallback.
            if slot == "employer":
                has_thread_local_employer = False
                for mem in all_memories:
                    if getattr(mem, "source", None) not in allowed_sources:
                        continue
                    if not engine.memory.can_answer_user_fact(mem):
                        continue
                    if bool(getattr(mem, "deprecated", False)):
                        continue
                    if not _in_thread_scope(getattr(mem, "thread_id", None)):
                        continue
                    facts = extract_fact_slots(mem.text) or {}
                    if "employer" in facts:
                        has_thread_local_employer = True
                        break
                if has_thread_local_employer:
                    continue
            slot_facts = engine.user_profile.get_all_facts_for_slot(slot)
            logger.info(f"[PROFILE_DEBUG] Retrieved {len(slot_facts)} facts for slot '{slot}'")

            for idx, fact in enumerate(slot_facts):
                if not _in_thread_scope(getattr(fact, "source_thread", None)):
                    continue
                safe_value = _normalize_profile_value(slot, getattr(fact, "value", ""))
                if not safe_value:
                    continue

                # Create a synthetic memory item from profile fact
                # Use unique memory_id for each value (slot_0, slot_1, etc.)
                synthetic_mem = MemoryItem(
                    memory_id=f"profile_{thread_key}_{slot}_{idx}",
                    vector=encode_vector(f"FACT: {slot} = {safe_value}"),
                    text=f"FACT: {slot.replace('_', ' ')} = {safe_value}",
                    timestamp=fact.timestamp,
                    confidence=fact.confidence,
                    trust=0.95,  # High trust for profile facts
                    source=MemorySource.USER,
                    sse_mode=SSEMode.LOSSLESS,  # Identity-critical fact
                    thread_id=thread_key,
                    authority="confirmed",
                    channel="system",
                    kind="user_fact",
                )
                if synthetic_mem.memory_id not in retrieved_ids:
                    logger.info(f"[PROFILE_DEBUG] Injecting profile fact: {slot} = {safe_value}")
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
            if not engine.memory.can_answer_user_fact(mem):
                continue
            if bool(getattr(mem, "deprecated", False)):
                continue
            if not _in_thread_scope(getattr(mem, "thread_id", None)):
                continue
            facts = extract_fact_slots(mem.text)
            if slot not in facts:
                continue
            # Fresh confirmed memories yield the active slot value. Trust is a
            # tiebreaker so a slightly reinforced stale value does not override
            # an explicit newer correction.
            freshness = 0 if (hasattr(mem, "is_stale") and mem.is_stale()) else 1
            key = (freshness, _source_priority(mem), mem.timestamp, mem.trust)
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


# ======================================================================
# _answer_from_fact_slots
# ======================================================================

def _answer_from_fact_slots(
    engine: "CRTEnhancedRAG",
    slots: List[str],
    *,
    user_query: Optional[str] = None,
    thread_id: Optional[str] = None,
    usage_trace_id: Optional[str] = None,
    usage_reason: Optional[str] = None,
) -> Optional[str]:
    """Answer simple personal-fact questions directly from USER memories.

    Returns an answer string if we can resolve at least one requested slot; otherwise None.

    Args:
        slots: List of slot names to look up
        user_query: Original user query (for context)
        thread_id: Thread ID for response variation (avoids repetitive answers)
    """
    if not slots:
        return None
    q = (user_query or "").strip().lower()
    wants_another = bool(re.search(r"\b(another|other|second|additional)\b", q))

    if not wants_another and not _is_name_history_request(engine, user_query or ""):
        effective_facts = engine.get_effective_user_facts(thread_id=thread_id)
        resolved_parts: List[str] = []
        selected_memory_ids: List[str] = []
        selected_slot_values: Dict[str, Any] = {}
        resolved_slot_order: List[str] = []

        for raw_slot in slots:
            slot = engine._canonical_user_slot_name(raw_slot)
            fact = effective_facts.get(slot)
            if not fact:
                continue
            value = str(fact.get("value") or "").strip()
            if not value:
                continue
            resolved_parts.append(f"{slot.replace('_', ' ')}: {value}")
            selected_slot_values[slot] = value
            resolved_slot_order.append(slot)
            memory_id = str(fact.get("memory_id") or "").strip()
            if memory_id:
                selected_memory_ids.append(memory_id)

        if resolved_parts:
            if selected_memory_ids:
                engine._record_memory_usage(
                    selected_memory_ids,
                    event_type="slot_selected",
                    reason=usage_reason or "fact_slot_resolution",
                    usage_trace_id=usage_trace_id,
                    query=user_query,
                    thread_id=thread_id,
                    metadata={
                        "slots": list(selected_slot_values.keys()),
                        "values": selected_slot_values,
                        "source_surface": "effective_profile",
                    },
                )
            if len(resolved_parts) == 1:
                slot = resolved_slot_order[0]
                value = str(selected_slot_values.get(slot) or "")
                if thread_id and slot in ("name", "employer", "location", "title"):
                    return _generate_varied_slot_answer(
                        engine,
                        slot=slot,
                        value=value,
                        thread_id=thread_id,
                        base_answer=value,
                    )
                return value
            return "\n".join(resolved_parts)

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

    # Fast path: use cached memory_facts table (indexed SQL lookup).
    _used_fast_path = False
    user_memories: List[MemoryItem] = []  # needed for name-history below
    try:
        cached_facts = engine.memory.get_all_facts()
        if cached_facts and any(s in cached_facts for s in slots):
            _mem_cache: Dict[str, Optional[MemoryItem]] = {}
            for slot in slots:
                for mem_id, value in cached_facts.get(slot, []):
                    if mem_id not in _mem_cache:
                        _mem_cache[mem_id] = engine._get_memory_by_id(mem_id)
                    mem = _mem_cache[mem_id]
                    if (
                        mem
                        and mem.source == MemorySource.USER
                        and not bool(getattr(mem, "deprecated", False))
                        and engine.memory.can_answer_user_fact(mem)
                    ):
                        slot_values[slot].append((mem, value))
            # Populate user_memories from cache for name-history fallback
            user_memories = [
                m for m in _mem_cache.values()
                if (
                    m
                    and m.source == MemorySource.USER
                    and not bool(getattr(m, "deprecated", False))
                    and engine.memory.can_answer_user_fact(m)
                )
            ]
            _used_fast_path = True
            logger.debug("[SLOT_LOOKUP] Used memory_facts fast path for %s", slots)
    except Exception as e:
        logger.debug("[SLOT_LOOKUP] memory_facts fast path failed, falling back: %s", e)

    # Fallback: full memory scan with regex (for legacy memories without cached facts).
    if not _used_fast_path:
        all_memories = engine.memory._load_all_memories()
        user_memories = [
            m for m in all_memories
            if (
                m.source == MemorySource.USER
                and not bool(getattr(m, "deprecated", False))
                and engine.memory.can_answer_user_fact(m)
            )
        ]
        if not user_memories:
            return None
        for mem in user_memories:
            facts = extract_fact_slots(mem.text)
            if not facts:
                continue
            for slot in slots:
                if slot in facts:
                    slot_values[slot].append((mem, facts[slot].value))

    resolved_parts: List[str] = []
    selected_memory_ids: List[str] = []
    selected_slot_values: Dict[str, Any] = {}
    for slot in slots:
        candidates = slot_values.get(slot) or []
        if not candidates:
            continue

        # Pick best (latest, user-first; trust as tiebreak).
        best_mem, best_val = max(
            candidates,
            key=lambda mv: (_source_priority(mv[0]), mv[0].timestamp, mv[0].trust),
        )
        selected_memory_ids.append(best_mem.memory_id)
        selected_slot_values[slot] = str(best_val)

        # If multiple distinct values exist, mention that this was updated.
        distinct_norm = []
        for _m, v in candidates:
            vn = str(v).strip().lower()
            if vn and vn not in distinct_norm:
                distinct_norm.append(vn)

        if len(distinct_norm) > 1:
            resolved_parts.append(f"{slot.replace('_', ' ')}: {best_val} (note: multiple values on record)")
        else:
            resolved_parts.append(f"{slot.replace('_', ' ')}: {best_val}")

    if not resolved_parts:
        return None

    engine._record_memory_usage(
        selected_memory_ids,
        event_type="slot_selected",
        reason=usage_reason or "fact_slot_resolution",
        usage_trace_id=usage_trace_id,
        query=user_query,
        thread_id=thread_id,
        metadata={
            "slots": list(selected_slot_values.keys()),
            "values": selected_slot_values,
        },
    )

    if len(resolved_parts) == 1:
        # Return just the value-centric answer for naturalness.
        if slot == "name" and _is_name_history_request(engine, user_query or ""):
            # Build a name-history view from explicit first-person declarations first.
            explicit_names: List[str] = []
            seen_names: set[str] = set()
            name_pat = r"([A-Z][A-Za-z'-]{1,40}(?:\s+[A-Z][A-Za-z'-]{1,40}){0,2})"
            first_person_patterns = (
                # Anchor to start-ish phrasing so transcript blocks like
                # "Assistant: I'm Aether ..." are not mis-read as user declarations.
                re.compile(r"^\s*(?:hi|hey|hello)?[\s,.:!-]*(?:my name is)\s+" + name_pat + r"(?:\b|[,.!?])", re.IGNORECASE),
                re.compile(r"^\s*(?:hi|hey|hello)?[\s,.:!-]*(?:i(?:'m| am))\s+" + name_pat + r"(?:\b|[,.!?])", re.IGNORECASE),
                re.compile(r"^\s*(?:please\s+)?(?:call me)\s+" + name_pat + r"(?:\b|[,.!?])", re.IGNORECASE),
                re.compile(r"^\s*(?:people call me)\s+" + name_pat + r"(?:\b|[,.!?])", re.IGNORECASE),
            )
            for mem in sorted(user_memories, key=lambda m: m.timestamp, reverse=True):
                txt = (mem.text or "").strip()
                if not txt:
                    continue
                candidate = None
                for pat in first_person_patterns:
                    m = pat.search(txt)
                    if m:
                        candidate = (m.group(1) or "").strip()
                        break
                if not candidate:
                    continue
                candidate = re.sub(r"^(?:also|aka|a\.k\.a\.)\s+", "", candidate, flags=re.IGNORECASE).strip()
                if not candidate:
                    continue
                norm = candidate.lower()
                if norm in seen_names:
                    continue
                seen_names.add(norm)
                explicit_names.append(candidate)

            if not explicit_names:
                # Fallback: use extracted slot values, newest first.
                for mem, val in sorted(candidates, key=lambda mv: mv[0].timestamp, reverse=True):
                    vv = str(val).strip()
                    if not vv:
                        continue
                    norm = vv.lower()
                    if norm in seen_names:
                        continue
                    seen_names.add(norm)
                    explicit_names.append(vv)

            if not explicit_names:
                return "I don't have any stored name variants from you yet."

            current = explicit_names[0]
            others = [n for n in explicit_names[1:] if n.lower() != current.lower()]
            if "other" in q or "another" in q:
                if others:
                    return (
                        f"You've also used: {', '.join(others[:5])}. "
                        f"Most recent is {current}."
                    )
                return f"I only have one name variant stored: {current}."
            if others:
                return (
                    f"I have these name variants from our chats: {', '.join(explicit_names[:6])}. "
                    f"Most recent is {current}."
                )
            return f"I only have one name variant stored: {current}."

        if wants_another and slot.startswith("favorite_") and slot != "favorite_color":
            candidates = slot_values.get(slot) or []
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

                slot_label = slot.replace("_", " ")
                if len(distinct_vals) <= 1:
                    return f"No - I only have {best_val} stored as your {slot_label}."

                others = [v for v in distinct_vals if v.strip().lower() != str(best_val).strip().lower()]
                if others:
                    return f"Yes - I have {best_val} as your most recent {slot_label}, and you've also said: {', '.join(others)}."
            return f"I only have one {slot.replace('_', ' ')} stored right now."

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
                    return f"No  -  I only have {best_val} stored as your favorite color."

                others = [v for v in distinct_vals if v.strip().lower() != str(best_val).strip().lower()]
                if others:
                    return f"Yes  -  I have {best_val} as your most recent favorite color, and you've also said: {', '.join(others)}."
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
            except (ValueError, TypeError):
                return f"You have {val_str} siblings."

        if slot == "languages_spoken":
            try:
                count = int(val_str)
                if count == 1:
                    return "You speak one language."
                else:
                    return f"You speak {val_str} languages."
            except (ValueError, TypeError):
                return f"You speak {val_str} languages."

        if slot == "graduation_year":
            return f"You graduated in {val_str}."

        # Apply response variation for simple slot queries
        base_answer = resolved_parts[0].split(": ", 1)[1]
        if thread_id and slot in ("name", "employer", "location", "title"):
            return _generate_varied_slot_answer(
                engine,
                slot=slot,
                value=val_str,
                thread_id=thread_id,
                base_answer=base_answer
            )
        return base_answer

    return "\n".join(resolved_parts)


# ======================================================================
# Response Variation System
# ======================================================================

def _get_response_variation_config(engine: "CRTEnhancedRAG") -> Dict[str, Any]:
    """Get response variation configuration from runtime config."""
    cfg = engine.runtime_config.get("response_variation") if isinstance(engine.runtime_config, dict) else None
    return cfg if isinstance(cfg, dict) else {}


def _is_response_variation_enabled(engine: "CRTEnhancedRAG") -> bool:
    """Check if response variation is enabled."""
    cfg = _get_response_variation_config(engine)
    return bool(cfg.get("enabled", True))


def _get_recent_slot_queries(
    engine: "CRTEnhancedRAG",
    thread_id: str,
    slot: str,
    window: int = 5
) -> List[Dict[str, Any]]:
    """
    Get recent queries for a specific slot within message window.

    Used to detect query repetition and determine if variation is needed.
    """
    if not _SESSION_DB_AVAILABLE:
        return []

    try:
        session_db = get_thread_session_db()
        return session_db.get_recent_slot_queries(thread_id, slot, window)
    except Exception as e:
        logger.debug(f"[VARIATION] Error getting recent queries: {e}")
        return []


def _generate_varied_slot_answer(
    engine: "CRTEnhancedRAG",
    slot: str,
    value: str,
    thread_id: str = "default",
    base_answer: Optional[str] = None
) -> str:
    """
    Generate a varied response for a slot query to avoid repetition.

    If user asks "what's my name?" multiple times, vary between:
    - "Nick" (first time)
    - "Your name is Nick." (second time)
    - "Still Nick!" (third time)

    Args:
        slot: The slot being queried (e.g., "name", "employer")
        value: The slot value to include in response
        thread_id: Thread identifier for query history lookup
        base_answer: The original answer (used as one variation option)

    Returns:
        Varied answer string
    """
    if not _is_response_variation_enabled(engine):
        return base_answer or value

    cfg = _get_response_variation_config(engine)
    window_size = cfg.get("window_size", 5)

    # Get recent queries for this slot
    recent = _get_recent_slot_queries(engine, thread_id, slot, window_size)
    repeat_count = len(recent)

    if repeat_count == 0:
        # First time asking - return base answer or plain value
        return base_answer or value

    # Get templates for this slot
    slot_templates = cfg.get("slot_templates", {})
    templates = slot_templates.get(slot) or slot_templates.get("default", ["{value}"])

    if not templates:
        return base_answer or value

    # Avoid using the same response as last time
    last_response = recent[0].get("response_text", "") if recent else ""

    # Select a different template based on repeat count
    # Cycle through templates, avoiding the last used response
    available_templates = [t for t in templates]

    # Try to pick a template that generates a different response
    for _ in range(len(available_templates)):
        # Use repeat count to cycle through templates
        template_idx = repeat_count % len(available_templates)
        template = available_templates[template_idx]

        try:
            varied_answer = template.format(value=value)
        except (KeyError, IndexError):
            varied_answer = value

        # If this would be different from last response, use it
        if varied_answer.strip().lower() != last_response.strip().lower():
            return varied_answer

        # Move to next template
        repeat_count += 1

    # Fallback: return with "Still" prefix if all else fails
    if slot == "name":
        return f"Still {value}!"
    return f"That's still {value}."


# ======================================================================
# _one_line_summary_from_facts
# ======================================================================

def _one_line_summary_from_facts(engine: "CRTEnhancedRAG") -> Optional[str]:
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
    resolved = _answer_from_fact_slots(engine, core_slots)
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


# ======================================================================
# _list_confident_facts_from_slots
# ======================================================================

def _list_confident_facts_from_slots(engine: "CRTEnhancedRAG") -> Optional[str]:
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
    resolved = _answer_from_fact_slots(engine, core_slots)
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


# ======================================================================
# _is_name_history_request  (helper used by _answer_from_fact_slots)
# ======================================================================

def _is_name_history_request(engine: "CRTEnhancedRAG", text: str) -> bool:
    """True when user asks for previously used names/nicknames/aliases."""
    t = (text or "").strip().lower()
    if not t:
        return False

    if re.search(r"\b(nickname|nicknames|alias|aliases)\b", t):
        return True

    patterns = (
        r"\bwhat (?:other )?names?\b",
        r"\bnames?\s+did\s+i\s+say\b",
        r"\bwhat\s+did\s+i\s+say\s+my\s+name\s+was\b",
        r"\bother\s+names?\s+i\s+used\b",
    )
    return any(re.search(p, t) for p in patterns)

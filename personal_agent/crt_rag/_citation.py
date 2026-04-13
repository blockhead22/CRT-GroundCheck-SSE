"""Citation, inventory, synthesis, and contradiction-status helpers.

Extracted from CRTEnhancedRAG — every function takes ``engine`` as its
first parameter instead of ``self``.
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
import numpy as np
from personal_agent.exceptions import log_swallowed_exception
from personal_agent.crt_core import MemorySource, encode_vector
from personal_agent.crt_memory import MemoryItem
from personal_agent.reasoning import ReasoningMode
from personal_agent.fact_slots import extract_fact_slots


# ======================================================================
# _fallback_response
# ======================================================================

def _fallback_response(engine: "CRTEnhancedRAG", query: str, thread_id: Optional[str] = None) -> Dict:
    """Generate response when no memories exist.

    The local model can still generate valid responses without memories —
    memories enhance but should not gate local generation.
    """
    result = engine.reasoning.reason(
        query=query,
        context={'retrieved_docs': [], 'contradictions': []},
        mode=ReasoningMode.QUICK
    )

    _answer = result.get('answer', '') or ''
    _has_valid_answer = bool(_answer.strip()) and not _answer.startswith("[")

    # Store as low-trust speech
    engine.memory.store_memory(
        text=_answer,
        confidence=0.3,
        source=MemorySource.FALLBACK,
        context={'query': query, 'type': 'fallback_no_memory'},
        thread_id=thread_id,
    )

    try:
        _fb_q_emb = encode_vector(query).astype(np.float32).tobytes()
        _fb_r_emb = encode_vector(_answer).astype(np.float32).tobytes() if _answer else None
    except Exception:
        _fb_q_emb = _fb_r_emb = None
    engine.memory.record_speech(
        query, _answer, "no_memory",
        query_embedding=_fb_q_emb,
        response_embedding=_fb_r_emb,
    )

    return {
        'answer': _answer,
        'thinking': None,
        'mode': 'quick',
        'confidence': 0.5 if _has_valid_answer else 0.3,
        'response_type': 'speech',
        'gates_passed': _has_valid_answer,
        'gate_reason': 'no_memories_local_generation' if _has_valid_answer else 'No memories available',
        'contradiction_detected': False,
        'retrieved_memories': []
    }


# ======================================================================
# _is_memory_citation_request
# ======================================================================

def _is_memory_citation_request(engine: "CRTEnhancedRAG", text: str) -> bool:
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


# ======================================================================
# _is_name_history_request
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


# ======================================================================
# _is_memory_inventory_request
# ======================================================================

def _is_memory_inventory_request(engine: "CRTEnhancedRAG", text: str) -> bool:
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


# ======================================================================
# _build_memory_inventory_answer
# ======================================================================

def _build_memory_inventory_answer(
    engine: "CRTEnhancedRAG",
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
    open_contras = engine._get_memory_conflicts()
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
                if engine.ledger.has_open_contradiction(memory_id):
                    txt = f"{txt} \u26a0\ufe0f"
                    conflict_marked_ids.add(memory_id)
            except Exception as e:
                log_swallowed_exception("crt_rag._build_memory_inventory.conflict_check", e)

        lines.append(f"- {txt}")
        added += 1
        if added >= max_lines:
            break

    # If we marked conflicts, add a note
    if conflict_marked_ids:
        lines.append("\n\u26a0\ufe0f = has conflicting information")

    # List top conflicts if space permits
    if has_conflicts and added < max_lines:
        lines.append("\nopen conflicts:")
        for contra in open_contras[:min(3, max_lines - added)]:
            claim_a = (contra.claim_a_text or "")[:60]
            claim_b = (contra.claim_b_text or "")[:60]
            lines.append(f"- '{claim_a}' vs '{claim_b}'")

    return "\n".join(lines)


# ======================================================================
# _build_synthesis_answer
# ======================================================================

def _build_synthesis_answer(
    engine: "CRTEnhancedRAG",
    *,
    user_query: str,
    retrieved: List[Tuple[MemoryItem, float]],
    thread_id: str = "default",
    max_facts: int = 10,
) -> str:
    """Build a synthesis answer that combines multiple related facts.

    For queries like "What do you know about my interests?" we need to:
    1. Extract all relevant memories (user-provided facts)
    2. Combine them into a natural synthesis
    """
    from personal_agent.crt_core import MemorySource
    from personal_agent.canonical_view import build_canonical_slot_view, format_slot_view

    ql = (user_query or "").strip().lower()

    # For full-profile summary requests, use a canonical ledger-backed slot view
    # to prevent reintroducing superseded facts.
    if "summar" in ql and ("everything" in ql or "all" in ql) and ("about me" in ql or "about my" in ql or "about" in ql and "me" in ql):
        try:
            all_mems = engine.memory._load_all_memories()
        except Exception:
            all_mems = []

        view = build_canonical_slot_view(
            user_memories=all_mems,
            memory_get_by_id=engine.memory.get_memory_by_id,
            ledger_db_path=str(getattr(engine.ledger, "db_path", "") or ""),
            thread_id=str(thread_id or getattr(engine, "thread_id", "default") or "default"),
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
        open_contras = engine._get_memory_conflicts()
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

    # Get USER memories (facts the user told us), scoped to this thread.
    user_memories = [
        m
        for m, _s in (retrieved or [])
        if getattr(m, "source", None) == MemorySource.USER
        and _in_thread_scope(getattr(m, "thread_id", None))
    ]

    if not user_memories:
        user_memories = []

    # For slot-specific queries (e.g., "what do you remember about my employer?"),
    # check if retrieved memories actually contain facts about the queried slot.
    # If not, return "I don't have that information" rather than unrelated facts.
    inferred_slots = engine._infer_slots_from_query(user_query)
    if inferred_slots:
        # Check if any retrieved memory contains facts about the queried slots
        relevant_memories = []
        for mem in user_memories:
            mem_facts = extract_fact_slots(mem.text) or {}
            # Check if this memory has any facts about the slots we're asking about
            if any(slot in mem_facts for slot in inferred_slots):
                relevant_memories.append(mem)

        # If we have inferred slots but no relevant memories, return "don't have"
        if not relevant_memories:
            relevant_memories = []

        # Use only the relevant memories for building the answer
        user_memories = relevant_memories

    def _is_low_signal_memory_text(text: str) -> bool:
        t = str(text or "").strip()
        if not t:
            return True
        tl = t.lower()
        # Filter generic/meta statements that do not add profile facts.
        low_signal_markers = (
            "i'm letting you know some info about myself",
            "im letting you know some info about myself",
            "i m letting you know some info about myself",
            "you should know some of my history",
            "some info about myself",
            "my history",
        )
        strong_fact_markers = (
            "my name is",
            "i am a ",
            "i'm a ",
            "i work",
            "i live",
            "i like",
            "i prefer",
            "my goal",
            "my goals",
            "i build",
            "i value",
        )
        marker_hit = any(m in tl for m in low_signal_markers) or bool(
            re.search(r"letting you know some info about myself", tl)
        )
        if marker_hit and not any(m in tl for m in strong_fact_markers):
            return True
        # Keep memories that have structured fact extraction.
        try:
            if extract_fact_slots(t):
                return False
        except Exception:
            pass
        # Very short/noisy lines are usually not useful profile facts.
        if len(t.split()) < 4:
            return True
        return False

    def _profile_fact_lines(limit: int) -> List[str]:
        """Best-effort fallback from structured user profile facts.

        This prevents "I don't know" replies when facts exist in profile DB but
        were not surfaced by embedding retrieval for broad synthesis prompts.
        """
        try:
            all_profile = engine.user_profile.get_all_facts_expanded() or {}
        except Exception:
            return []
        if not all_profile:
            return []

        scoped_profile: Dict[str, List[Any]] = {}
        for slot, facts_for_slot in all_profile.items():
            scoped = [
                fact
                for fact in (facts_for_slot or [])
                if _in_thread_scope(getattr(fact, "source_thread", None))
            ]
            if scoped:
                scoped_profile[slot] = scoped
        if not scoped_profile:
            return []

        query_slots = engine._infer_slots_from_query(user_query)
        if query_slots:
            slot_order = [s for s in query_slots if s in scoped_profile]
        else:
            # Deterministic order for stable answers.
            slot_order = sorted(scoped_profile.keys())

        lines: List[str] = []
        for slot in slot_order:
            facts_for_slot = scoped_profile.get(slot) or []
            added_for_slot = 0
            for fact in facts_for_slot:
                value = _normalize_profile_value(slot, getattr(fact, "value", ""))
                if not value:
                    continue
                lines.append(f"FACT: {slot.replace('_', ' ')} = {value}")
                added_for_slot += 1
                if len(lines) >= max(1, int(limit)):
                    return lines
                # Broad "about me" summaries should stay concise and avoid contradictory
                # multi-values for the same slot in a single response.
                if added_for_slot >= 1:
                    break
        return lines

    # Build synthesis answer
    facts = [
        mem.text.strip()
        for mem in user_memories[: max_facts * 2]
        if mem.text and mem.text.strip() and not _is_low_signal_memory_text(mem.text)
    ]
    # Include structured profile facts as fallback/augmentation.
    facts.extend(_profile_fact_lines(max_facts * 2))

    # Remove duplicates while preserving order (case/whitespace insensitive).
    from typing import Set
    seen_norm: Set[str] = set()
    facts_deduped: List[str] = []
    for fact in facts:
        norm = re.sub(r"\s+", " ", str(fact or "").strip()).lower()
        if not norm or norm in seen_norm:
            continue
        seen_norm.add(norm)
        facts_deduped.append(str(fact).strip())

    if len(facts_deduped) == 0:
        return (
            "I don't have specific profile facts captured yet. "
            "Share concrete details (for example role, goals, tools, or preferences) and I will remember them."
        )
    elif len(facts_deduped) == 1:
        return facts_deduped[0]
    else:
        # Multiple facts - synthesize them
        answer_parts = ["Based on what I remember:"]
        for i, fact in enumerate(facts_deduped[:max_facts], 1):
            answer_parts.append(f"  {i}. {fact}")

        return "\n".join(answer_parts)


# ======================================================================
# _build_memory_citation_answer
# ======================================================================

def _build_memory_citation_answer(
    engine: "CRTEnhancedRAG",
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
    from personal_agent.crt_core import MemorySource

    user_retrieved = [m for m, _s in (retrieved or []) if getattr(m, "source", None) == MemorySource.USER]

    # Check for conflicts with these memories
    conflict_ids = set()
    for mem in user_retrieved:
        mem_id = getattr(mem, "id", None)
        if mem_id:
            try:
                if engine.ledger.has_open_contradiction(mem_id):
                    conflict_ids.add(mem_id)
            except Exception as e:
                log_swallowed_exception("crt_rag._build_memory_citation.conflict_check", e)

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


# ======================================================================
# _is_contradiction_status_request
# ======================================================================

def _is_contradiction_status_request(engine: "CRTEnhancedRAG", text: str) -> bool:
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

    # Singular contradiction phrasing used as a follow-up question:
    # "what was the contradiction you detected?"
    if "contradiction" in t and any(
        k in t for k in (
            "what was",
            "which contradiction",
            "what contradiction",
            "you detected",
            "did you detect",
            "that contradiction",
        )
    ):
        return True

    # User phrasing about self
    if "contradictions" in t and any(k in t for k in ("about me", "about myself", "about my", "about my self")):
        return True

    # CLI-style short commands (exact match only)
    if t in {"contradictions", "show contradictions", "list contradictions"}:
        return True

    return False


# ======================================================================
# _build_contradiction_status_answer
# ======================================================================

def _build_contradiction_status_answer(
    engine: "CRTEnhancedRAG",
    *,
    user_query: str,
    inferred_slots: Optional[List[str]] = None,
    limit: int = 8,
) -> Tuple[str, Dict[str, Any]]:
    """Build a deterministic answer listing OPEN contradictions from the ledger.

    This is intentionally ledger-grounded to prevent hallucinated contradictions.
    """
    from personal_agent.crt_ledger import ContradictionType

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

    open_contras = engine.ledger.get_open_contradictions(limit=200)
    unresolved_total = len(open_contras)

    rows: List[Dict[str, Any]] = []
    hard_conflicts = 0

    for contra in open_contras:
        old_mem = engine.memory.get_memory_by_id(contra.old_memory_id)
        new_mem = engine.memory.get_memory_by_id(contra.new_memory_id)
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

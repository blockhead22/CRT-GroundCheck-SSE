"""CRT RAG — memory operations (ingestion, profile tracking, retrieval).

Delegate functions extracted from CRTEnhancedRAG; each takes
``engine`` as its first argument in place of ``self``.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from ._engine import CRTEnhancedRAG

import numpy as np

from personal_agent.crt_core import MemorySource, encode_vector
from personal_agent.crt_memory import MemoryItem
from personal_agent.domain_detector import detect_query_domains
from personal_agent.fact_slots import (
    extract_fact_slots,
    is_explicit_name_declaration_text,
    names_look_equivalent,
)

logger = logging.getLogger(__name__)


# ======================================================================
# _canonical_user_slot_name  (was @staticmethod)
# ======================================================================
def _canonical_user_slot_name(slot: Optional[str]) -> str:
    slot_name = str(slot or "").strip()
    if slot_name.lower().startswith("user."):
        slot_name = slot_name[5:]
    return slot_name.strip()


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
# _record_and_cascade
# ======================================================================
def _record_and_cascade(engine: "CRTEnhancedRAG", **kwargs):
    """Record a contradiction AND trigger cascade propagation on a background thread.

    Drop-in replacement for engine.ledger.record_contradiction(**kwargs).
    Extracts old_vector/new_vector for cascade use, passes all kwargs to ledger.
    Returns the ContradictionEntry (same as record_contradiction).
    """
    # Extract vectors for cascade use (record_contradiction also accepts them)
    old_vector = kwargs.get("old_vector")
    new_vector = kwargs.get("new_vector")
    entry = engine.ledger.record_contradiction(**kwargs)

    if entry is not None:
        # Capture the pipeline event queue from the current thread's contextvar
        # so the cascade background thread can emit SSE events.
        pipeline_queue = None
        try:
            import contextvars as _cv
            # The queue is set by routes/chat.py on the pipeline thread
            from routes.chat import _pipeline_event_queue
            pipeline_queue = _pipeline_event_queue.get(None)
        except Exception:
            pass  # Not in a request context or import unavailable

        import threading as _cascade_t
        _cascade_t.Thread(
            target=engine._trigger_cascade_propagation,
            args=(entry, old_vector, new_vector, pipeline_queue),
            daemon=True,
            name=f"cascade_{entry.ledger_id[:20]}",
        ).start()
        print(f"[BDG] Cascade thread spawned for {entry.ledger_id}")

    return entry


# ======================================================================
# _record_profile_replacements
# ======================================================================
def _record_profile_replacements(
    engine: "CRTEnhancedRAG",
    *,
    profile_result: Optional[Dict[str, Any]],
    thread_id: Optional[str],
) -> List[Dict[str, str]]:
    profile_updates: List[Dict[str, str]] = []
    if not profile_result or not profile_result.get("replaced"):
        return profile_updates

    for slot, replacement in (profile_result.get("replaced") or {}).items():
        update = {
            "slot": str(slot),
            "old": str(replacement.get("old") or ""),
            "new": str(replacement.get("new") or ""),
        }
        profile_updates.append(update)
        try:
            # Look up real memory IDs for this slot so BDG can cascade
            _old_mem_id = f"profile_{slot}_old"  # fallback synthetic
            _new_mem_id = f"profile_{slot}_new"
            _old_val_norm = str(replacement.get("old") or "").strip().lower()
            _new_val_norm = str(replacement.get("new") or "").strip().lower()
            try:
                _conn_pid = engine.memory._get_connection()
                _cur_pid = _conn_pid.cursor()
                # Find old value's memory
                if _old_val_norm:
                    _cur_pid.execute("""
                        SELECT mf.memory_id FROM memory_facts mf
                        JOIN memories m ON mf.memory_id = m.memory_id
                        WHERE mf.slot = ? AND LOWER(mf.value) = ? AND m.deprecated = 0
                        ORDER BY m.trust DESC LIMIT 1
                    """, (slot, _old_val_norm))
                    _old_row = _cur_pid.fetchone()
                    if _old_row:
                        _old_mem_id = _old_row[0]
                # Find new value's memory (most recent)
                if _new_val_norm:
                    _cur_pid.execute("""
                        SELECT mf.memory_id FROM memory_facts mf
                        JOIN memories m ON mf.memory_id = m.memory_id
                        WHERE mf.slot = ? AND LOWER(mf.value) = ? AND m.deprecated = 0
                        ORDER BY m.timestamp DESC LIMIT 1
                    """, (slot, _new_val_norm))
                    _new_row = _cur_pid.fetchone()
                    if _new_row:
                        _new_mem_id = _new_row[0]
                _conn_pid.close()
                print(f"[PROFILE] Resolved memory IDs: old={_old_mem_id}, new={_new_mem_id}")
            except Exception as _pid_err:
                print(f"[PROFILE] Failed to resolve memory IDs (using synthetic): {_pid_err}")

            profile_contra = _record_and_cascade(
                engine,
                old_memory_id=_old_mem_id,
                new_memory_id=_new_mem_id,
                drift_mean=0.8,
                confidence_delta=0.0,
                old_text=f"FACT: {slot} = {replacement['old']}",
                new_text=f"FACT: {slot} = {replacement['new']}",
                contradiction_type="profile_update",
                summary=f"Profile update: {slot} changed from '{replacement['old']}' to '{replacement['new']}'",
                thread_id=thread_id,
            )
            # NOTE: Previously auto-resolved here with profile_sync_audit.
            # Removed to let contradictions stay OPEN in the ledger for
            # user visibility. The user can resolve via /api/ledger/resolve.
            print(f"[PROFILE] Contradiction logged (OPEN): {profile_contra.ledger_id} — "
                  f"{slot}: '{replacement['old']}' → '{replacement['new']}'")
        except Exception as ledger_err:
            logger.warning(f"[PROFILE] Failed to log contradiction to ledger: {ledger_err}")
    return profile_updates


# ======================================================================
# ingest_memory_write
# ======================================================================
def ingest_memory_write(
    engine: "CRTEnhancedRAG",
    *,
    text: str,
    confidence: float,
    source: MemorySource,
    context: Optional[Dict[str, Any]] = None,
    user_marked_important: bool = False,
    contradiction_signal: float = 0.0,
    thread_id: Optional[str] = None,
    channel: Optional[str] = None,
    origin: Optional[str] = None,
    authority: Optional[str] = None,
    kind: Optional[str] = None,
    source_kind: Optional[str] = None,
    model_id: Optional[str] = None,
    run_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Shared write path for governed memory plus canonical fact surfaces."""
    memory = engine.memory.store_memory(
        text=text,
        confidence=confidence,
        source=source,
        context=context,
        user_marked_important=user_marked_important,
        contradiction_signal=contradiction_signal,
        thread_id=thread_id,
        channel=channel,
        origin=origin,
        authority=authority,
        kind=kind,
        source_kind=source_kind,
        model_id=model_id,
        run_id=run_id,
        user_id=user_id,
    )

    fact_result: Dict[str, Any] = {}
    fact_store_updated = False
    profile_result: Dict[str, Any] = {}
    profile_updates: List[Dict[str, str]] = []

    if engine.memory.can_update_user_profile(memory):
        if engine.fact_store is not None:
            fact_result = engine.fact_store.process_input(
                text,
                thread_id=str(thread_id or "default"),
            ) or {}
            fact_store_updated = bool(
                fact_result.get("extracted") or fact_result.get("updated")
            )

        # ── PROFILE TRUST GATE ──────────────────────────────────────
        # Before updating the profile, check if the new facts conflict
        # with high-trust memories. If so, block the profile update to
        # prevent the profile from drifting away from verified beliefs.
        _profile_blocked_slots = set()
        try:
            _new_facts = extract_fact_slots(text) or {}
            for _pslot, _pval in _new_facts.items():
                if _pslot in ("assistant_name",):
                    continue
                _new_val_lower = str(_pval).strip().lower()
                # Look up the highest-trust memory for this slot
                _conn_pg = engine.memory._get_connection()
                _cur_pg = _conn_pg.cursor()
                _cur_pg.execute("""
                    SELECT mf.value, m.trust, m.memory_id
                    FROM memory_facts mf
                    JOIN memories m ON mf.memory_id = m.memory_id
                    WHERE mf.slot = ? AND m.deprecated = 0
                    ORDER BY m.trust DESC LIMIT 1
                """, (_pslot,))
                _pg_row = _cur_pg.fetchone()
                _conn_pg.close()
                if _pg_row:
                    _existing_val = str(_pg_row[0]).strip().lower()
                    _existing_trust = _pg_row[1]
                    if _existing_trust > 0.8 and _existing_val != _new_val_lower:
                        _profile_blocked_slots.add(_pslot)
                        print(f"[PROFILE_GATE] BLOCKED: {_pslot}={_pval} conflicts with "
                              f"memory {_pslot}={_pg_row[0]} at trust {_existing_trust:.2f} "
                              f"({_pg_row[2]})")
        except Exception as _pg_err:
            print(f"[PROFILE_GATE] Error checking trust gate: {_pg_err}")

        try:
            if _profile_blocked_slots:
                print(f"[PROFILE_GATE] Skipping profile update — blocked slots: {_profile_blocked_slots}")
                # Still log contradictions to the ledger (as OPEN) so the user can see them
                for _blocked_slot in _profile_blocked_slots:
                    _blocked_val = str(_new_facts.get(_blocked_slot, "")).strip()
                    try:
                        # Find real memory IDs
                        _conn_bl = engine.memory._get_connection()
                        _cur_bl = _conn_bl.cursor()
                        _cur_bl.execute("""
                            SELECT mf.memory_id, mf.value FROM memory_facts mf
                            JOIN memories m ON mf.memory_id = m.memory_id
                            WHERE mf.slot = ? AND m.deprecated = 0
                            ORDER BY m.trust DESC LIMIT 1
                        """, (_blocked_slot,))
                        _bl_row = _cur_bl.fetchone()
                        _conn_bl.close()
                        _old_mem_id = _bl_row[0] if _bl_row else f"profile_{_blocked_slot}_old"
                        _old_val = _bl_row[1] if _bl_row else "unknown"

                        _record_and_cascade(
                            engine,
                            old_memory_id=_old_mem_id,
                            new_memory_id=memory.memory_id,
                            drift_mean=0.8,
                            confidence_delta=0.0,
                            old_text=f"FACT: {_blocked_slot} = {_old_val}",
                            new_text=f"FACT: {_blocked_slot} = {_blocked_val}",
                            old_vector=getattr(memory, 'vector', None),
                            contradiction_type="conflict",
                            summary=f"Profile gate blocked: {_blocked_slot}={_blocked_val} vs established {_blocked_slot}={_old_val}",
                            thread_id=thread_id,
                        )
                        print(f"[PROFILE_GATE] Logged OPEN contradiction for blocked slot {_blocked_slot}")
                    except Exception as _bl_err:
                        print(f"[PROFILE_GATE] Failed to log blocked contradiction: {_bl_err}")
            else:
                profile_result = engine.user_profile.update_from_text(
                    text,
                    thread_id=str(thread_id or "default"),
                ) or {}
                profile_updates = _record_profile_replacements(
                    engine,
                    profile_result=profile_result,
                    thread_id=thread_id,
                )
        except Exception as e:
            logger.error(f"[PROFILE_DEBUG] Failed to update user profile: {e}", exc_info=True)

    return {
        "memory": memory,
        "fact_result": fact_result,
        "fact_store_updated": fact_store_updated,
        "profile_result": profile_result,
        "profile_updates": profile_updates,
    }


# ======================================================================
# retrieve
# ======================================================================
def retrieve(
    engine: "CRTEnhancedRAG",
    query: str,
    k: int = 5,
    min_trust: float = 0.0,
    include_system: bool = False,
    include_fallback: bool = False,
    include_reflection: bool = False,
    exclude_contradiction_sources: bool = True,
    relevant_slots: Optional[Set[str]] = None,
    relevant_domains: Optional[List[str]] = None,
    temporal_filter: Optional[str] = None,
    thread_id: Optional[str] = None,
    usage_trace_id: Optional[str] = None,
    usage_reason: Optional[str] = None,
    usage_metadata: Optional[Dict[str, Any]] = None,
) -> List[Tuple[MemoryItem, float]]:
    """
    Retrieve memories using CRT trust-weighted scoring.

    R_i = s_i · τ_i · w_i
    where:
    - s_i = similarity(query, memory)
    - τ_i = recency_weight
    - w_i = α·trust + (1-α)·confidence

    Phase 2.0 Updates:
    - relevant_domains: Boost memories matching these domains
    - temporal_filter: Filter by temporal status ("active", "past", etc.)

    This is fundamentally different from standard RAG's pure similarity.
    """
    # Phase 2.0: Detect query domains for boosting
    if relevant_domains is None:
        relevant_domains = detect_query_domains(query)
    query_vector = encode_vector(query)

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
        from personal_agent.crt_ledger import ContradictionType
        unresolved_contradictions = engine.ledger.get_open_contradictions(limit=100)
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
    retrieved = engine.memory.retrieve_memories(
        query,
        candidate_k,
        min_trust,
        exclude_deprecated=True,
        ledger=engine.ledger,
        excluded_ids=excluded_mem_ids if exclude_contradiction_sources else None,
        exclude_kinds={"narrative_summary", "narrative_note", "self_model",
                       "evolution_observation", "evolution_proposal", "synthesis"},
        exclude_authorities={"provisional"},  # Don't cite same-turn unverified claims
    )

    # Topic-aware retrieval boost: if query matches a known variance tracker topic,
    # boost memories that were cited in prior responses on that topic.
    _topic_memory_ids: set = set()
    try:
        import sqlite3 as _sql3
        _bs_conn = _sql3.connect(engine.memory.db_path)
        # Find topic clusters whose centroid is similar to this query
        _topic_rows = _bs_conn.execute(
            "SELECT topic_id, centroid_embedding FROM opinion_topics WHERE entry_count >= 3"
        ).fetchall()
        if _topic_rows:
            import numpy as _np2
            for _tr in _topic_rows:
                _centroid = _np2.frombuffer(_tr[1], dtype=_np2.float32)
                _norm = _np2.linalg.norm(_centroid)
                if _norm > 0:
                    _sim = float(_np2.dot(query_vector, _centroid / _norm))
                    if _sim > 0.5:  # query matches this topic cluster
                        # Get memory IDs cited in prior belief responses on this topic
                        _cited_rows = _bs_conn.execute(
                            """SELECT memory_ids_json FROM belief_speech
                               WHERE topic_id=? AND is_belief=1 AND memory_ids_json IS NOT NULL""",
                            (_tr[0],),
                        ).fetchall()
                        for _cr in _cited_rows:
                            try:
                                for _mid in json.loads(_cr[0]):
                                    _topic_memory_ids.add(_mid)
                            except Exception:
                                pass
        _bs_conn.close()
        if _topic_memory_ids:
            logger.debug("[TOPIC_BOOST] Boosting %d memories from prior topic responses", len(_topic_memory_ids))
    except Exception as _tbe:
        logger.debug("[TOPIC_BOOST] Skipped: %s", _tbe)

    # Avoid retrieving derived helper outputs (they are grounded summaries/citations,
    # not new world facts) to prevent recursive quoting and prompt pollution.
    filtered: List[Tuple[MemoryItem, float]] = []
    for mem, score in retrieved:
        if getattr(mem, "source", None) not in allowed_sources:
            continue

        # Phase 2.0: Filter by temporal status if specified
        if temporal_filter and hasattr(mem, "temporal_status"):
            if mem.temporal_status != temporal_filter:
                continue

        # Phase 2.0: Boost score for domain-matching memories
        if relevant_domains and relevant_domains != ["general"]:
            mem_domains = mem.get_domains() if hasattr(mem, "get_domains") else ["general"]
            domain_overlap = set(relevant_domains) & set(mem_domains)
            if domain_overlap and "general" not in domain_overlap:
                # Boost by 50% for domain match
                score = score * 1.5
                logger.debug(f"[DOMAIN_BOOST] Memory '{mem.text[:40]}...' boosted for domains {domain_overlap}")
            elif not domain_overlap and "general" not in set(mem_domains):
                # Penalize hard domain mismatch (e.g. career memory in programming conversation)
                score = score * 0.4
                logger.debug(f"[DOMAIN_PENALTY] Memory '{mem.text[:40]}...' penalized (domains {set(mem_domains)} vs query {set(relevant_domains)})")

        # Topic-aware boost: memories cited in prior responses on the same topic
        if _topic_memory_ids and mem.memory_id in _topic_memory_ids:
            score = score * 1.8  # Strong boost for topic-relevant memories
            logger.debug(f"[TOPIC_BOOST] Memory '{mem.text[:40]}...' boosted (cited in prior topic response)")

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

        # Phase 0.5 DNNT hook: resonance scoring (Mirus integration point).
        try:
            resonance = engine.resonance_scorer.score(
                query=query,
                memory_text=mem.text,
                query_vector=query_vector,
                memory_vector=mem.vector,
            )
            # Keep trust-weighted score primary, use resonance as bounded multiplier.
            score *= (0.75 + (0.50 * resonance.resonance))

            if resonance.anchor_matches:
                mem.context = dict(mem.context or {})
                hook_meta = mem.context.get("crt_hooks")
                if not isinstance(hook_meta, dict):
                    hook_meta = {}
                hook_meta["resonance"] = round(float(resonance.resonance), 6)
                hook_meta["anchor_overlap"] = round(float(resonance.anchor_overlap), 6)
                hook_meta["anchor_matches"] = resonance.anchor_matches
                mem.context["crt_hooks"] = hook_meta
        except Exception as e:
            logger.debug(f"[RESONANCE] Failed to score resonance for {mem.memory_id}: {e}")

        filtered.append((mem, score))

    filtered.sort(key=lambda item: item[1], reverse=True)
    top_results = filtered[:k]

    # RAG-level retrieval summary
    _n_topic = sum(1 for m, _ in top_results if m.memory_id in _topic_memory_ids) if _topic_memory_ids else 0
    _n_domain = 0  # counted inline above, not tracked separately
    print(
        "[RETRIEVAL_RAG] query=\"%s\" raw=%d filtered=%d final=%d boosts=[topic:%d]"
        % (query[:60], len(retrieved), len(filtered), len(top_results), _n_topic)
    )

    if top_results:
        engine._record_memory_usage(
            top_results,
            event_type="retrieved",
            reason=usage_reason or "retrieve",
            usage_trace_id=usage_trace_id,
            query=query,
            thread_id=thread_id,
            metadata=usage_metadata,
        )
    return top_results


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
        # ── Profile slot resolution ──
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

    inferred_slots = set(engine._infer_slots_from_query(query_text))
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

"""
Context-aware system prompt builder.

Generates a short context block from CRT memories to inject into every
chat's system prompt, giving the LLM awareness of what it knows about
the user without a full memory search per turn.

Usage:
    from personal_agent.context_feed import build_context_summary
    ctx = build_context_summary(thread_id, memory_db_path)
    # Append ctx to the system prompt (empty string when nothing to say)
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TTL cache: one entry per thread, rebuilt every 5 minutes
# ---------------------------------------------------------------------------

_cache: Dict[str, Tuple[float, str]] = {}
_CACHE_TTL = 300  # seconds


def _cache_get(thread_id: str) -> Optional[str]:
    entry = _cache.get(thread_id)
    if entry is None:
        return None
    ts, text = entry
    if time.time() - ts > _CACHE_TTL:
        return None
    return text


def _cache_set(thread_id: str, text: str) -> None:
    _cache[thread_id] = (time.time(), text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_context_summary(
    thread_id: str,
    memory_db_path: str,
    session_db_path: Optional[str] = None,
) -> str:
    """Build a short context block from CRT memories for system prompt injection.

    Returns a string like:

        ## What I know about you:
        - Nick prefers concise answers
        - User is building Aether, a personal AI assistant
        ...

    Returns empty string when no relevant memories exist or on any error.
    Cached per thread_id with a 5-minute TTL.
    """
    # Check cache first
    cached = _cache_get(thread_id)
    if cached is not None:
        return cached

    try:
        result = _build_fresh(thread_id, memory_db_path)
    except Exception as exc:
        logger.debug(f"[CONTEXT_FEED] build failed: {exc}")
        result = ""

    _cache_set(thread_id, result)
    return result


def _get_away_resume_block(thread_id: str) -> str:
    """Check if user has been away and render belief state diff."""
    try:
        from personal_agent.session_state import get_or_create_session, render_away_resume_diff
        session = get_or_create_session(thread_id)
        diff = render_away_resume_diff(session)
        if diff:
            logger.debug(f"[CONTEXT_FEED] Away/resume diff for {thread_id[:12]}")
        return diff
    except Exception:
        return ""


def _build_fresh(thread_id: str, memory_db_path: str) -> str:
    """Fetch memories and format the context block."""
    from personal_agent.crt_memory import CRTMemorySystem

    mem = CRTMemorySystem(db_path=memory_db_path)

    # 1. High-trust memories — recent, trust > 0.5
    all_memories = mem._load_all_memories()

    # Filter to trusted, sort by recency, take top 10
    trusted = [
        m for m in all_memories
        if getattr(m, "trust", 0) > 0.5 and getattr(m, "text", "").strip()
    ]
    trusted.sort(key=lambda m: getattr(m, "timestamp", 0), reverse=True)
    top_memories = trusted[:10]

    # 2. Provisional memories from heartbeat learning (last 24h)
    provisional = []
    try:
        now = time.time()
        cutoff = now - 86400  # 24 hours
        provisional_candidates = [
            m for m in all_memories
            if (
                getattr(m, "authority", "") == "provisional"
                and getattr(m, "text", "").strip()
                and getattr(m, "timestamp", 0) > cutoff
                and getattr(m, "kind", "") in ("user_fact", "preference")
            )
        ]
        provisional_candidates.sort(
            key=lambda m: getattr(m, "timestamp", 0), reverse=True,
        )
        provisional = provisional_candidates[:5]
    except Exception as exc:
        logger.debug(f"[CONTEXT_FEED] provisional fetch failed: {exc}")

    if not top_memories and not provisional:
        return ""

    # 3. Deduplicate — provisional shouldn't repeat trusted facts
    trusted_texts = {m.text.strip().lower() for m in top_memories}
    provisional = [
        m for m in provisional
        if m.text.strip().lower() not in trusted_texts
    ]

    # 4. Format — sort by trust descending so highest-trust facts come first,
    # and include trust scores so the model knows which memories to prioritize.
    from .crt_memory import sanitize_memory_for_prompt as _sanitize_mem

    top_memories.sort(key=lambda m: getattr(m, "trust", 0), reverse=True)
    lines = [
        "",
        "## Facts about the user Nick (sorted by trust, highest first):",
        "These are things NICK told you or facts about Nick. They are HIS beliefs and experiences, not yours.",
        "Reference them as 'you said' or 'you mentioned' — never as 'I believe' or 'I expressed'.",
    ]
    for m in top_memories:
        text = _sanitize_mem(m.text.strip()[:200])
        if not text:
            continue
        trust = getattr(m, "trust", 0)
        lines.append(f"- [trust:{trust:.2f}] Nick: {text}")

    if provisional:
        lines.append("")
        lines.append("Recent observations (provisional):")
        for m in provisional:
            text = _sanitize_mem(m.text.strip()[:200])
            if not text:
                continue
            lines.append(f"- {text}")

    # 5. Narrative synthesis — synthesized understanding (belief-level, not raw facts)
    narrative_section = _build_narrative_section(all_memories)
    if narrative_section:
        lines.append("")
        lines.append(narrative_section)

    # 6. System evolution — recent changes to Aether itself
    evolution_section = _build_evolution_section()
    if evolution_section:
        lines.append("")
        lines.append(evolution_section)

    # 7. Recent interaction summary — last session context for cross-thread continuity
    recent_interaction = _build_recent_interaction_summary(memory_db_path)
    if recent_interaction:
        lines.append("")
        lines.append(recent_interaction)

    # 8. Away/resume belief diff (if user returning after gap)
    away_block = _get_away_resume_block(thread_id)
    if away_block:
        lines.insert(0, away_block)

    block = "\n".join(lines)
    logger.debug(
        f"[CONTEXT_FEED] built {len(top_memories)}+{len(provisional)} items "
        f"for thread {thread_id}"
    )
    return block


def build_compacted_context(
    thread_id: str,
    memory_db_path: str,
    token_budget: int = 4000,
    trigger: str = "manual",
) -> str:
    """Build a belief-aware compacted context block.

    Uses trust-tiered compaction instead of simple top-N retrieval.
    Higher-trust memories get more faithful representation.
    Active contradictions preserved as pairs.

    Args:
        thread_id: Thread identifier for caching
        memory_db_path: Path to CRT memory database
        token_budget: Maximum tokens for the context block
        trigger: What triggered compaction ("token_overflow"|"scheduled"|"manual")

    Returns:
        Formatted belief snapshot string for system prompt injection.
        Falls back to build_context_summary() on error.
    """
    cache_key = f"{thread_id}:compacted:{token_budget}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        from personal_agent.crt_memory import CRTMemorySystem
        from personal_agent.belief_compaction import (
            compact_context, render_belief_snapshot, record_compaction_event,
        )
        from personal_agent.compaction_decay import apply_compaction_decay

        mem = CRTMemorySystem(db_path=memory_db_path)
        all_memories = mem._load_all_memories()

        # Filter deprecated
        memories = [m for m in all_memories if not getattr(m, "deprecated", False)]
        if not memories:
            return ""

        # Load active contradictions from ledger
        active_contradictions = []
        try:
            ledger_path = memory_db_path.replace("crt_memory", "crt_ledger")
            from personal_agent.crt_ledger import ContradictionLedger
            ledger = ContradictionLedger(db_path=ledger_path)
            active_contradictions = ledger.get_open_contradictions(limit=100)
        except Exception:
            pass

        # Get session hot memory IDs for compaction prioritization
        session_hot_ids = None
        try:
            from personal_agent.session_state import get_or_create_session, get_hot_memory_ids
            _sess = get_or_create_session(thread_id)
            session_hot_ids = get_hot_memory_ids(_sess)
        except Exception:
            pass

        # Run compaction
        snapshot = compact_context(
            memories=memories,
            active_contradictions=active_contradictions,
            token_budget=token_budget,
            trigger=trigger,
            session_hot_ids=session_hot_ids,
        )

        # Record event to database
        try:
            conn = mem._get_connection()
            record_compaction_event(conn, snapshot)
            conn.close()
        except Exception as exc:
            logger.debug(f"[CONTEXT_FEED] Failed to record compaction event: {exc}")

        # Apply trust decay
        try:
            decay_result = apply_compaction_decay(snapshot, mem)
            logger.debug(
                f"[CONTEXT_FEED] Compaction decay: {decay_result.memories_decayed} decayed, "
                f"{decay_result.memories_flagged_reverification} flagged"
            )
        except Exception as exc:
            logger.debug(f"[CONTEXT_FEED] Compaction decay failed: {exc}")

        # Render
        result = render_belief_snapshot(snapshot)

        # Prepend away/resume diff if returning after gap
        away_block = _get_away_resume_block(thread_id)
        if away_block:
            result = away_block + "\n\n" + result

        _cache_set(cache_key, result)
        return result

    except Exception as exc:
        logger.warning(f"[CONTEXT_FEED] Compacted context failed, falling back: {exc}")
        return build_context_summary(thread_id, memory_db_path)


def _build_narrative_section(all_memories: list) -> str:
    """Build a section from narrative_note belief memories.

    These are synthesized understanding — not raw facts but connected narratives
    that represent Aether's integrated view of the user.
    """
    narratives = [
        m for m in all_memories
        if (
            getattr(m, "kind", "") == "narrative_note"
            and getattr(m, "memory_type", "") == "belief"
            and getattr(m, "trust", 0) >= 0.5
            and not getattr(m, "deprecated", False)
            and getattr(m, "text", "").strip()
        )
    ]
    if not narratives:
        return ""

    narratives.sort(key=lambda m: getattr(m, "trust", 0), reverse=True)
    top = narratives[:5]

    lines = ["## Your synthesized understanding of the user:"]
    for m in top:
        text = m.text.strip()[:300]
        lines.append(f"- {text}")
    return "\n".join(lines)


def _build_evolution_section() -> str:
    """Build a section showing recent system evolution events."""
    try:
        from personal_agent.db_utils import ThreadSessionDB
        import os

        # Find session DB
        candidates = [
            os.path.join(os.path.dirname(__file__), "..", "data", "thread_sessions.db"),
            os.path.join(os.path.dirname(__file__), "thread_sessions.db"),
        ]
        db_path = None
        for c in candidates:
            if os.path.exists(c):
                db_path = c
                break
        if not db_path:
            return ""

        session_db = ThreadSessionDB(db_path)
        events = session_db.get_evolution_events(limit=3)
        if not events:
            return ""

        from datetime import datetime
        lines = ["## Your recent evolution:"]
        for ev in events:
            ts = datetime.fromtimestamp(ev["timestamp"]).strftime("%Y-%m-%d %H:%M")
            lines.append(f"- [{ts}] {ev['title']}")
            if ev.get("description"):
                lines.append(f"  {ev['description'][:200]}")
        return "\n".join(lines)
    except Exception as exc:
        logger.debug(f"[CONTEXT_FEED] evolution section failed: {exc}")
        return ""


def _build_recent_interaction_summary(memory_db_path: str) -> str:
    """Build a compact summary of recent belief/speech entries for cross-session continuity.

    Pulls the last N belief_speech entries (across all threads) so Aether knows
    what it recently discussed regardless of which thread is active.
    """
    import sqlite3

    try:
        conn = sqlite3.connect(memory_db_path)
        rows = conn.execute(
            """SELECT query, response, is_belief, trust_avg, timestamp
               FROM belief_speech
               ORDER BY timestamp DESC
               LIMIT 8"""
        ).fetchall()
        conn.close()
    except Exception:
        return ""

    if not rows:
        return ""

    lines = ["## Recent interactions (cross-session):"]
    for r in rows:
        query = (r[0] or "")[:80]
        response = (r[1] or "")[:100]
        typ = "belief" if r[2] else "speech"
        trust = f"T:{r[3]:.2f}" if r[3] else ""
        if query.strip():
            lines.append(f"- Q: {query}")
            lines.append(f"  A ({typ}{' ' + trust if trust else ''}): {response}")

    return "\n".join(lines) if len(lines) > 1 else ""

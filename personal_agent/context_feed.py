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

    # 4. Format
    lines = ["", "## What I know about you:"]
    for m in top_memories:
        text = m.text.strip()[:200]
        lines.append(f"- {text}")

    if provisional:
        lines.append("")
        lines.append("Recent observations (provisional):")
        for m in provisional:
            text = m.text.strip()[:200]
            lines.append(f"- {text}")

    block = "\n".join(lines)
    logger.debug(
        f"[CONTEXT_FEED] built {len(top_memories)}+{len(provisional)} items "
        f"for thread {thread_id}"
    )
    return block

"""Governance helpers extracted from routes/chat.py."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

from ..deps import sanitize_thread_id
from ..chat_provider_routing import resolve_effective_generation_mode
from ._constants import _GROUNDCHECK_BRIDGE_LOCK, _GROUNDCHECK_BRIDGE_LAST_SYNC

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


# ---------------------------------------------------------------------------
# _maybe_sync_groundcheck_bridge
# ---------------------------------------------------------------------------

def _maybe_sync_groundcheck_bridge(
    *,
    thread_id: str,
    engine: Any,
) -> Dict[str, Any]:
    """Best-effort GroundCheck -> CRT sync for retrieval parity across channels."""
    enabled = _env_bool("CRT_GROUNDCHECK_BRIDGE_ENABLED", True)
    if not enabled:
        return {"enabled": False, "attempted": False, "reason": "disabled"}

    tid = sanitize_thread_id(thread_id)
    try:
        interval = float(os.getenv("CRT_GROUNDCHECK_BRIDGE_INTERVAL_SECONDS", "120") or 120.0)
    except Exception:
        interval = 120.0
    interval = max(5.0, interval)

    now = time.time()
    with _GROUNDCHECK_BRIDGE_LOCK:
        last = float(_GROUNDCHECK_BRIDGE_LAST_SYNC.get(tid, 0.0) or 0.0)
        if now - last < interval:
            return {
                "enabled": True,
                "attempted": False,
                "reason": "interval",
                "next_sync_in_seconds": round(interval - (now - last), 3),
            }
        _GROUNDCHECK_BRIDGE_LAST_SYNC[tid] = now

    try:
        from personal_agent.memory_bridge import sync_groundcheck_to_memory

        try:
            min_trust = float(os.getenv("CRT_GROUNDCHECK_BRIDGE_MIN_TRUST", "0.2") or 0.2)
        except Exception:
            min_trust = 0.2
        try:
            raw_limit = int(os.getenv("CRT_GROUNDCHECK_BRIDGE_RAW_LIMIT", "400") or 400)
        except Exception:
            raw_limit = 400
        try:
            narrative_limit = int(os.getenv("CRT_GROUNDCHECK_BRIDGE_NARRATIVE_LIMIT", "120") or 120)
        except Exception:
            narrative_limit = 120

        allowed_sources_raw = str(os.getenv("CRT_GROUNDCHECK_BRIDGE_SOURCES", "user,inferred") or "").strip()
        allowed_sources = [s.strip() for s in allowed_sources_raw.split(",") if s.strip()] if allowed_sources_raw else None

        result = sync_groundcheck_to_memory(
            memory_system=engine.memory,
            thread_id=tid,
            min_trust=min_trust,
            raw_limit=max(1, raw_limit),
            narrative_limit=max(0, narrative_limit),
            allowed_sources=allowed_sources,
        )
        result["enabled"] = True
        result["attempted"] = True
        return result
    except Exception as e:
        logger.debug(f"[MEMORY_BRIDGE] Sync failed for {tid}: {e}")
        return {"enabled": True, "attempted": True, "ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# _is_strict_local_only_mode / _is_cloud_governance_allowed
# ---------------------------------------------------------------------------

def _is_strict_local_only_mode(req: "ChatRequest", uid: Optional[int]) -> bool:
    try:
        from personal_agent.local_only_policy import is_strict_local_only_mode as _strict_local_only_mode

        return _strict_local_only_mode(
            uid=uid,
            generation_mode=resolve_effective_generation_mode(req, uid),
        )
    except Exception:
        return False


def _is_cloud_governance_allowed(req: "ChatRequest", uid: Optional[int]) -> bool:
    """Return whether auxiliary cloud governance calls are allowed for this turn.

    This is intentionally narrower than general provider routing. It controls
    optional cloud governance helpers such as slot classification, cloud NLI,
    and intuition checks that should not fire during strict local-only runs.
    """
    return not _is_strict_local_only_mode(req, uid)

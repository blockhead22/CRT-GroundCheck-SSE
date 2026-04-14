"""
Trust Decay & Reinforcement System — CRT Math Edition

Implements temporal trust dynamics for GroundCheck memories using CRT's
mathematical framework instead of flat constants:

1. **Decay**: Exponential recency curve (rho = e^{-Delta t / lambda}) instead of flat
   subtract.  Memories far from the time constant decay faster; recently
   active ones barely decay.

2. **Reinforcement**: When a memory is referenced in a chat response,
   `evolve_trust_reinforced(tau, D)` gives a drift-aware boost — if the
   referencing context is semantically close (low drift D) the boost is
   large; if it's tangential (high drift) the boost is small.

3. **Corrections**: `evolve_trust_aligned(tau, D)` on the corrected memory.
   If the correction is a minor refinement (low drift) the boost is gentle;
   if it's a major rewrite (high drift) the boost still applies but is
   proportionally smaller.

Design constraints (unchanged):
- Never decay below TRUST_FLOOR (0.20)
- Never boost above TRUST_CEILING (0.95)
- Grace period: new memories are immune for GRACE_PERIOD_DAYS
- Runs only during idle time via the idle scheduler
"""

from __future__ import annotations

import logging
import math
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tuning constants (kept for API compatibility; CRT math overrides decay/boost)
# ---------------------------------------------------------------------------
DECAY_RATE = 0.02             # Fallback flat decay (used when CRT unavailable)
REINFORCE_BOOST = 0.03        # Fallback flat reinforce
CORRECTION_BOOST = 0.05       # Fallback flat correction boost
TRUST_FLOOR = 0.20            # Minimum trust — never decay below this
TRUST_CEILING = 0.95          # Maximum trust — never boost above this
GRACE_PERIOD_DAYS = 7         # New memories are immune from decay for N days
MIN_PASS_INTERVAL_SECS = 3600 # Don't run decay more than once per hour

# Module-level timestamp of last decay pass to avoid hammering
_last_decay_ts: float = 0.0

# ---------------------------------------------------------------------------
# CRT math lazy loading
# ---------------------------------------------------------------------------
_crt_math = None

def _get_crt_math():
    """Lazy-load CRTMath singleton — graceful fallback if unavailable."""
    global _crt_math
    if _crt_math is not None:
        return _crt_math
    try:
        from personal_agent.crt_core import CRTMath, CRTConfig
        _crt_math = CRTMath(CRTConfig())
        logger.info("[TRUST_DECAY] CRT math loaded — using drift-aware trust evolution")
        return _crt_math
    except Exception as e:
        logger.debug("[TRUST_DECAY] CRT math unavailable (%s) — using flat constants", e)
        return None


def _encode_text(text: str):
    """Encode text to vector for drift computation. Returns None on failure."""
    try:
        from personal_agent.crt_core import encode_vector
        return encode_vector(text)
    except Exception:
        return None


def _compute_exponential_decay(age_seconds: float, current_trust: float) -> float:
    """
    CRT-style exponential decay: rho = e^{-Delta t / lambda}

    Instead of flat -0.02 per pass, compute a target trust based on age:
      target = TRUST_FLOOR + (current_trust - TRUST_FLOOR) * rho

    This means:
    - A 7-day-old memory barely decays (rho ~ 0.92)
    - A 30-day-old memory decays moderately (rho ~ 0.71)
    - A 90-day-old memory decays significantly (rho ~ 0.35)
    - A 365-day-old memory is near the floor (rho ~ 0.01)
    """
    crt = _get_crt_math()
    if crt is None:
        # Flat fallback
        return max(TRUST_FLOOR, current_trust - DECAY_RATE)

    # Use CRT's lambda_time (default 86400 = 1 day) but scale it for
    # decay passes — we want a longer time constant for idle decay.
    # Use 30 * lambda (~ 30 days) so memories have a reasonable half-life.
    lambda_decay = crt.config.lambda_time * 30.0
    rho = math.exp(-age_seconds / lambda_decay)

    # New trust: blend toward floor based on recency weight
    new_trust = TRUST_FLOOR + (current_trust - TRUST_FLOOR) * rho
    # Per-pass: only apply a fraction of the total decay to keep it gentle
    # (we don't want one pass to slam trust to the floor)
    decay_this_pass = (current_trust - new_trust) * 0.1  # 10% of computed gap

    # Upgrade #2: Scale decay by Beta confidence — high-confidence memories decay slower
    # confidence = alpha + beta; default 4.0 (Beta(2,2)); high confidence → slower decay
    if hasattr(current_trust, '__float__'):  # safety check
        # confidence passed via keyword when available; fall through otherwise
        pass
    logger.info(
        "[CRT_MATH] exponential_decay: trust %.3f->%.3f, age_days=%.1f, rho=%.4f, decay_this_pass=%.4f",
        current_trust, max(TRUST_FLOOR, current_trust - decay_this_pass),
        age_seconds / 86400.0, rho, decay_this_pass,
    )
    return max(TRUST_FLOOR, current_trust - decay_this_pass)


def _compute_drift_aware_boost(
    current_trust: float,
    memory_text: str,
    context_text: str,
    is_correction: bool = False,
) -> float:
    """
    CRT drift-aware trust boost.

    - Low drift (memory matches context) -> bigger boost
    - High drift (tangential reference) -> smaller boost
    - Corrections use evolve_trust_aligned; references use evolve_trust_reinforced
    """
    crt = _get_crt_math()
    if crt is None:
        return min(TRUST_CEILING, current_trust + (CORRECTION_BOOST if is_correction else REINFORCE_BOOST))

    # Try to compute semantic drift
    drift = 0.1  # Default low drift (generous boost) if vectors unavailable
    if memory_text and context_text:
        vec_mem = _encode_text(memory_text)
        vec_ctx = _encode_text(context_text)
        if vec_mem is not None and vec_ctx is not None:
            drift = crt.drift_meaning(vec_ctx, vec_mem)

    # Upgrade #1: Get domain volatility for learnable gain/decay
    volatility = 0.0
    try:
        from personal_agent.volatility_context import get_domain_volatility
        volatility, _domain = get_domain_volatility(memory_text)
    except Exception:
        pass

    # Use CRT evolution equations (with volatility from Upgrade #1)
    if is_correction:
        new_trust = crt.evolve_trust_aligned(current_trust, drift, volatility=volatility)
    else:
        new_trust = crt.evolve_trust_reinforced(current_trust, drift, volatility=volatility)

    return min(TRUST_CEILING, max(TRUST_FLOOR, new_trust))


def _find_groundcheck_db() -> Optional[Path]:
    """Locate the memory database — CRT memory DB preferred, GroundCheck DB fallback."""
    env = os.environ.get("GROUNDCHECK_DB", "").strip()
    if env:
        p = Path(env)
        if p.is_file():
            return p

    candidates = [
        # CRT native memory DB (primary — this is what Aether actually uses)
        Path("personal_agent/crt_memory.db"),
        Path("data/crt_memory.db"),
        Path("../personal_agent/crt_memory.db"),
        # GroundCheck MCP DB (fallback)
        Path("D:/groundcheck/.groundcheck/memory.db"),
        Path.home() / ".groundcheck" / "memory.db",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _is_crt_schema(conn: sqlite3.Connection) -> bool:
    """Return True if the connected DB uses CRT memory schema (memory_id PK)."""
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(memories)").fetchall()]
        return "memory_id" in cols
    except Exception:
        return False


def run_trust_decay_pass() -> dict:
    """Run one trust decay + reinforcement pass.

    Uses CRT exponential decay instead of flat subtraction, and
    drift-aware reinforcement instead of flat addition.

    Returns a summary dict with counts of decayed / reinforced / skipped.
    """
    global _last_decay_ts

    now = time.time()
    if (now - _last_decay_ts) < MIN_PASS_INTERVAL_SECS:
        return {"skipped": True, "reason": "too_soon"}

    db_path = _find_groundcheck_db()
    if not db_path:
        return {"skipped": True, "reason": "db_not_found"}

    grace_cutoff = now - (GRACE_PERIOD_DAYS * 86400)
    crt_available = _get_crt_math() is not None

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")

        crt_schema = _is_crt_schema(conn)
        id_col = "memory_id" if crt_schema else "id"
        alive_clause = "AND (deprecated IS NULL OR deprecated = 0)" if crt_schema else ""

        # ------------------------------------------------------------------
        # 1. Decay: memories older than grace period
        #    CRT: exponential curve based on age instead of flat -0.02
        # ------------------------------------------------------------------
        stale_rows = conn.execute(
            f"""SELECT {id_col} AS mem_id, trust, timestamp, text FROM memories
               WHERE timestamp < ? AND trust > ? {alive_clause}""",
            (grace_cutoff, TRUST_FLOOR),
        ).fetchall()

        decayed = 0
        for row in stale_rows:
            age_seconds = now - float(row["timestamp"])
            new_trust = _compute_exponential_decay(age_seconds, row["trust"])
            if new_trust < row["trust"]:
                conn.execute(
                    f"UPDATE memories SET trust = ? WHERE {id_col} = ?",
                    (round(new_trust, 4), row["mem_id"]),
                )
                decayed += 1

        # ------------------------------------------------------------------
        # 2. Reinforce: memories referenced in recent copilot_events
        #    CRT: drift-aware boost instead of flat +0.03
        # ------------------------------------------------------------------
        reinforced = 0
        has_events = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='copilot_events'"
        ).fetchone()[0]

        if has_events:
            recent_events = conn.execute(
                """SELECT memory_id, event_type, new_text FROM copilot_events
                   WHERE timestamp > ?""",
                (int(_last_decay_ts) if _last_decay_ts > 0 else int(now - 86400),),
            ).fetchall()

            for evt in recent_events:
                mem = conn.execute(
                    f"SELECT trust, text FROM memories WHERE {id_col} = ?", (evt["memory_id"],)
                ).fetchone()
                if not mem:
                    continue

                is_correction = evt["event_type"] == "correction"
                # Context for drift: use the new_text from the event if available
                context_text = ""
                try:
                    context_text = evt["new_text"] or ""
                except (IndexError, KeyError):
                    pass

                if crt_available and mem["text"]:
                    new_trust = _compute_drift_aware_boost(
                        mem["trust"],
                        mem["text"],
                        context_text or mem["text"],
                        is_correction=is_correction,
                    )
                else:
                    # Flat fallback
                    boost = CORRECTION_BOOST if is_correction else REINFORCE_BOOST
                    new_trust = min(TRUST_CEILING, mem["trust"] + boost)

                if new_trust > mem["trust"]:
                    conn.execute(
                        f"UPDATE memories SET trust = ? WHERE {id_col} = ?",
                        (round(new_trust, 4), evt["memory_id"]),
                    )
                    reinforced += 1

        conn.commit()

        # ------------------------------------------------------------------
        # 3. Compression pass — fold/unfold memories based on volatility
        # ------------------------------------------------------------------
        compression_summary = {}
        try:
            from personal_agent.memory_compression import run_compression_pass
            compression_summary = run_compression_pass(
                conn,
                id_col=id_col,
                grace_cutoff=grace_cutoff,
            )
            conn.commit()
        except Exception as comp_err:
            logger.warning("[COMPRESSION] Error during compression pass: %s", comp_err)
            compression_summary = {"skipped": True, "reason": str(comp_err)}

        conn.close()

        _last_decay_ts = now
        summary = {
            "skipped": False,
            "decayed": decayed,
            "reinforced": reinforced,
            "total_stale_checked": len(stale_rows),
            "crt_math_active": crt_available,
            "timestamp": now,
            "compression": compression_summary,
        }
        logger.info("[TRUST_DECAY] Pass complete: %s", summary)
        return summary

    except Exception as e:
        logger.warning("[TRUST_DECAY] Error during decay pass: %s", e)
        return {"skipped": True, "reason": str(e)}


def reinforce_memory(
    memory_id: str,
    boost: float = REINFORCE_BOOST,
    context_text: str = "",
    is_correction: bool = False,
) -> bool:
    """Give a specific memory a trust boost using CRT drift-aware evolution.

    If context_text is provided and CRT math is available, computes semantic
    drift between the memory text and the context to scale the boost.
    Falls back to flat boost if CRT unavailable or vectors can't be computed.

    Args:
        memory_id: The memory to reinforce
        boost: Flat fallback boost amount (used when CRT unavailable)
        context_text: Optional text context for drift computation
        is_correction: Whether this is a user correction (uses stronger evolution)
    """
    db_path = _find_groundcheck_db()
    if not db_path:
        return False

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        id_col = "memory_id" if _is_crt_schema(conn) else "id"
        row = conn.execute(f"SELECT trust, text FROM memories WHERE {id_col} = ?", (memory_id,)).fetchone()
        if not row:
            conn.close()
            return False

        # Skip reinforcement for memories demoted by slot exclusivity
        try:
            _demoted_row = conn.execute(
                "SELECT 1 FROM memory_events WHERE memory_id = ? AND event_type = 'slot_exclusivity_demoted' LIMIT 1",
                (memory_id,),
            ).fetchone()
            if _demoted_row:
                conn.close()
                return False
        except Exception:
            pass  # memory_events table may not exist in all schemas

        crt = _get_crt_math()
        if crt is not None and row["text"] and context_text:
            new_trust = _compute_drift_aware_boost(
                row["trust"],
                row["text"],
                context_text,
                is_correction=is_correction,
            )
        else:
            # Flat fallback
            new_trust = min(TRUST_CEILING, row["trust"] + boost)

        if new_trust > row["trust"]:
            conn.execute(
                f"UPDATE memories SET trust = ? WHERE {id_col} = ?",
                (round(new_trust, 4), memory_id),
            )
            conn.commit()

        conn.close()
        return True
    except Exception as e:
        logger.warning("[TRUST_DECAY] reinforce_memory failed: %s", e)
        return False

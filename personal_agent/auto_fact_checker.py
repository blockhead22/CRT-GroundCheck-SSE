"""
Auto Fact-Checker — Background Verification with CRT Volatility Triage

After every chat response, this module runs GroundCheck's verifier against
the response text and stored memories.  When it detects a hallucination or
contradiction, it stores a *pending fact-check* record with a CRT-computed
**volatility score** for prioritization:

    High volatility (V ≥ θ_reflect) → "critical" severity
    Medium volatility               → "warning" severity  
    Low volatility                  → "info" severity

CRT math integration:
- compute_volatility(drift, alignment, contradiction, fallback) for triage
- should_reflect(V) to flag responses needing deeper review
- detect_contradiction() with entity swap / negation / paraphrase tolerance
  as a second-pass filter to reduce GroundCheck false positives

Design:
- Non-blocking: runs in a daemon thread so the user gets their response instantly
- Silent: never blocks or modifies the response itself
- Persistent: findings are stored in the GroundCheck memory DB (new table)
- Prioritized: CRT volatility scores rank findings by importance
- Actionable: each finding can become a toast, a correction, or a new fact
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CRT math lazy loading for volatility triage
# ---------------------------------------------------------------------------
_crt_math = None


def _get_crt_math():
    """Lazy-load CRTMath singleton for volatility scoring."""
    global _crt_math
    if _crt_math is not None:
        return _crt_math
    try:
        from personal_agent.crt_core import CRTMath, CRTConfig
        _crt_math = CRTMath(CRTConfig())
        logger.info("[AUTO_FC] CRT math loaded — volatility triage enabled")
        return _crt_math
    except Exception as e:
        logger.debug("[AUTO_FC] CRT math unavailable (%s) — flat priority", e)
        return None


def _encode_text(text: str):
    """Encode text to vector. Returns None on failure."""
    try:
        from personal_agent.crt_core import encode_vector
        return encode_vector(text)
    except Exception:
        return None


def _compute_finding_volatility(
    response_text: str,
    memories: List[Dict[str, Any]],
    has_contradiction: bool,
    has_hallucination: bool,
) -> Tuple[float, str]:
    """Compute CRT volatility score for a set of findings.

    Returns (volatility, severity) where severity is "critical"/"warning"/"info".
    """
    crt = _get_crt_math()
    if crt is None:
        # Flat fallback: contradictions > hallucinations > low confidence
        if has_contradiction:
            return 0.7, "warning"
        if has_hallucination:
            return 0.5, "warning"
        return 0.3, "info"

    # Compute drift: average drift between response and top memories
    drift = 0.3  # default moderate drift
    memory_alignment = 0.5  # default moderate alignment
    resp_vec = _encode_text(response_text[:500])

    if resp_vec is not None and memories:
        drifts = []
        alignments = []
        for m in memories[:5]:  # Top 5 memories
            mem_text = m.get("text", "")
            if not mem_text:
                continue
            mem_vec = _encode_text(mem_text)
            if mem_vec is not None:
                d = crt.drift_meaning(resp_vec, mem_vec)
                drifts.append(d)
                sim = crt.similarity(resp_vec, mem_vec)
                alignments.append(sim)
        if drifts:
            drift = sum(drifts) / len(drifts)
        if alignments:
            memory_alignment = sum(alignments) / len(alignments)

    # Is any memory a fallback/LLM source?
    is_fallback = any(
        m.get("source", "").lower() in ("fallback", "llm_output")
        for m in memories
    )

    volatility = crt.compute_volatility(
        drift=drift,
        memory_alignment=memory_alignment,
        is_contradiction=has_contradiction,
        is_fallback=is_fallback,
    )

    # Severity classification using CRT's reflection threshold
    if crt.should_reflect(volatility):
        severity = "critical"
    elif volatility >= crt.config.theta_reflect * 0.6:
        severity = "warning"
    else:
        severity = "info"

    return round(volatility, 4), severity


def _crt_filter_contradiction(
    claim_text: str,
    memory_text: str,
    slot: str = "",
) -> bool:
    """Second-pass CRT filter to reduce false positive contradictions.

    Uses CRT's paraphrase tolerance, entity swap detection, and negation
    detection to confirm or reject a GroundCheck-flagged contradiction.

    Returns True if CRT confirms it IS a real contradiction.
    """
    crt = _get_crt_math()
    if crt is None:
        return True  # No CRT = trust GroundCheck's judgment

    # Compute drift
    vec_claim = _encode_text(claim_text)
    vec_mem = _encode_text(memory_text)
    if vec_claim is None or vec_mem is None:
        return True  # Can't compute vectors, trust GroundCheck

    drift = crt.drift_meaning(vec_claim, vec_mem)

    # Use CRT's full contradiction detection pipeline with paraphrase tolerance
    from personal_agent.crt_core import MemorySource
    is_contra, reason = crt.detect_contradiction(
        drift=drift,
        confidence_new=0.7,
        confidence_prior=0.7,
        source=MemorySource.USER,
        text_new=claim_text,
        text_prior=memory_text,
        slot=slot or None,
    )

    if not is_contra:
        logger.debug(
            "[AUTO_FC] CRT filtered out false positive contradiction: %s", reason
        )

    return is_contra


# ---------------------------------------------------------------------------
# DB path (mirrors copilot.py resolution)
# ---------------------------------------------------------------------------

def _find_groundcheck_db() -> Optional[Path]:
    env = os.environ.get("GROUNDCHECK_DB", "").strip()
    if env:
        p = Path(env)
        if p.is_file():
            return p
    candidates = [
        Path("D:/groundcheck/.groundcheck/memory.db"),
        Path.home() / ".groundcheck" / "memory.db",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_fact_checks (
            id          TEXT PRIMARY KEY,
            thread_id   TEXT NOT NULL,
            query       TEXT NOT NULL,
            response    TEXT NOT NULL,
            claim       TEXT NOT NULL,
            slot        TEXT DEFAULT '',
            issue_type  TEXT NOT NULL,
            details     TEXT DEFAULT '',
            status      TEXT NOT NULL DEFAULT 'pending',
            volatility  REAL DEFAULT 0.0,
            severity    TEXT DEFAULT 'info',
            created_at  INTEGER NOT NULL,
            resolved_at INTEGER DEFAULT NULL
        )
    """)
    # Add volatility/severity columns to existing tables (idempotent)
    for col, dtype, default in [
        ("volatility", "REAL", "0.0"),
        ("severity", "TEXT", "'info'"),
    ]:
        try:
            conn.execute(
                f"ALTER TABLE pending_fact_checks ADD COLUMN {col} {dtype} DEFAULT {default}"
            )
        except sqlite3.OperationalError:
            pass  # Column already exists


# ---------------------------------------------------------------------------
# GroundCheck verifier (lazy import)
# ---------------------------------------------------------------------------

def _run_verification(
    thread_id: str,
    query: str,
    response: str,
    memories: List[Dict[str, Any]],
) -> None:
    """Run GroundCheck verification in a background thread.

    If hallucinations are found, store them in pending_fact_checks.
    """
    try:
        from groundcheck import GroundCheck
        from groundcheck.types import Memory
    except ImportError:
        logger.debug("[AUTO_FC] groundcheck not importable — skipping")
        return

    db_path = _find_groundcheck_db()
    if not db_path:
        logger.debug("[AUTO_FC] GroundCheck DB not found — skipping")
        return

    # Convert dict memories to Memory objects
    gc_memories: List[Memory] = []
    for m in memories:
        if isinstance(m, dict) and m.get("text"):
            gc_memories.append(
                Memory(
                    id=m.get("memory_id", m.get("id", "")),
                    text=m["text"],
                    trust=float(m.get("trust", 0.7)),
                    timestamp=m.get("timestamp"),
                )
            )

    if not gc_memories:
        return

    try:
        gc = GroundCheck()
        report = gc.verify(response, gc_memories, mode="permissive")
    except Exception as e:
        logger.debug("[AUTO_FC] Verification failed: %s", e)
        return

    if report.passed:
        logger.debug("[AUTO_FC] Response passed verification (confidence=%.2f)", report.confidence)
        return

    # ----- Hallucinations or contradictions found -----
    now = int(time.time())
    findings: List[Dict[str, str]] = []
    has_contradiction = False
    has_hallucination = False

    # Collect hallucinated facts
    for slot, fact in (getattr(report, 'hallucinations', None) or getattr(report, 'hallucinated_facts', None) or {}).items():
        value = fact.value if hasattr(fact, "value") else str(fact)
        has_hallucination = True
        findings.append({
            "claim": f"{slot}: {value}",
            "slot": slot,
            "issue_type": "hallucination",
            "details": f"Claimed '{value}' for {slot} but no supporting memory found",
        })

    # Collect contradictions — apply CRT second-pass filter
    for contra in (report.contradictions or []):
        claim_text = contra.get("claim", "") if isinstance(contra, dict) else str(contra)
        slot = contra.get("slot", "") if isinstance(contra, dict) else ""

        # CRT second-pass: check if this is a real contradiction or a
        # false positive (e.g., paraphrase, entity refinement)
        memory_text = contra.get("memory_text", "") if isinstance(contra, dict) else ""
        if memory_text and claim_text:
            if not _crt_filter_contradiction(claim_text, memory_text, slot):
                logger.debug("[AUTO_FC] CRT filtered out contradiction: %s", claim_text[:80])
                continue

        has_contradiction = True
        findings.append({
            "claim": claim_text,
            "slot": slot,
            "issue_type": "contradiction",
            "details": json.dumps(contra) if isinstance(contra, dict) else str(contra),
        })

    # If report says it failed but we couldn't parse specific findings,
    # store a generic one
    if not findings and not report.passed:
        findings.append({
            "claim": response[:200],
            "slot": "",
            "issue_type": "low_confidence",
            "details": f"Verification confidence {report.confidence:.2f} below threshold",
        })

    if not findings:
        return

    # Compute CRT volatility score for prioritization
    volatility, severity = _compute_finding_volatility(
        response, memories, has_contradiction, has_hallucination
    )

    if not findings:
        return

    try:
        conn = sqlite3.connect(str(db_path))
        _ensure_table(conn)

        for f in findings:
            check_id = f"fc_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """INSERT INTO pending_fact_checks
                   (id, thread_id, query, response, claim, slot, issue_type, details,
                    status, volatility, severity, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
                (
                    check_id,
                    thread_id,
                    query[:500],
                    response[:1000],
                    f["claim"][:500],
                    f["slot"],
                    f["issue_type"],
                    f["details"][:1000],
                    volatility,
                    severity,
                    now,
                ),
            )

        conn.commit()
        conn.close()
        logger.info(
            "[AUTO_FC] Stored %d fact-check findings for thread=%s",
            len(findings),
            thread_id,
        )
    except Exception as e:
        logger.warning("[AUTO_FC] Failed to store findings: %s", e)


def schedule_fact_check(
    thread_id: str,
    query: str,
    response: str,
    memories: List[Dict[str, Any]],
) -> None:
    """Schedule a non-blocking background fact-check of the response.

    Call this from the chat pipeline right before returning the response.
    """
    if not memories:
        return

    t = threading.Thread(
        target=_run_verification,
        args=(thread_id, query, response, memories),
        name="auto-fact-check",
        daemon=True,
    )
    t.start()


def get_pending_fact_checks(
    thread_id: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Retrieve pending fact-check findings.

    Returns unresolved issues that should be surfaced to the user or agent.
    """
    db_path = _find_groundcheck_db()
    if not db_path:
        return []

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        _ensure_table(conn)

        if thread_id:
            rows = conn.execute(
                """SELECT * FROM pending_fact_checks
                   WHERE status = 'pending' AND thread_id = ?
                   ORDER BY volatility DESC, created_at DESC LIMIT ?""",
                (thread_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM pending_fact_checks
                   WHERE status = 'pending'
                   ORDER BY volatility DESC, created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()

        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("[AUTO_FC] Failed to read pending checks: %s", e)
        return []


def resolve_fact_check(check_id: str, resolution: str = "acknowledged") -> bool:
    """Mark a pending fact-check as resolved."""
    db_path = _find_groundcheck_db()
    if not db_path:
        return False

    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "UPDATE pending_fact_checks SET status = ?, resolved_at = ? WHERE id = ?",
            (resolution, int(time.time()), check_id),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning("[AUTO_FC] Failed to resolve check: %s", e)
        return False

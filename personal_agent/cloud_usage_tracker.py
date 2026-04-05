"""
Cloud Usage Tracker — SQLite-backed tracking for every cloud API call in the CRT pipeline.

Tracks call_type, provider, model, latency, success/failure, token estimates,
and contextual metadata (thread_id, uid, escalation_reason, user_message_preview).

Design principles:
  - Fire-and-forget: log_cloud_call() never raises, never blocks the response pipeline.
  - Singleton pattern consistent with other personal_agent modules.
  - Separate DB file (data/cloud_usage.db) — reuses the same file as cloud_usage_logger.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DB_FILE = _DATA_DIR / "cloud_usage.db"

# ---------------------------------------------------------------------------
# Valid call_type values (for documentation; not enforced at insert time)
# ---------------------------------------------------------------------------

VALID_CALL_TYPES = {
    "generation",
    "slot_classification",
    "nli_contradiction",
    "reflection_validation",
    "generation_fallback",
    "generation_fallback_claude",
    "generation_primary_openai",
    "generation_primary_claude",
}

# ---------------------------------------------------------------------------
# Schema — lives alongside the existing cloud_usage table in the same DB
# ---------------------------------------------------------------------------

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS cloud_usage_log (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp            REAL    NOT NULL,
    thread_id            TEXT,
    uid                  INTEGER,
    call_type            TEXT    NOT NULL,
    provider             TEXT    NOT NULL,
    model                TEXT    NOT NULL DEFAULT '',
    input_tokens_est     INTEGER NOT NULL DEFAULT 0,
    output_tokens_est    INTEGER NOT NULL DEFAULT 0,
    latency_ms           INTEGER NOT NULL DEFAULT 0,
    success              INTEGER NOT NULL DEFAULT 1,
    error_type           TEXT,
    escalation_reason    TEXT,
    user_message_preview TEXT
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cul_timestamp  ON cloud_usage_log(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_cul_call_type  ON cloud_usage_log(call_type);",
    "CREATE INDEX IF NOT EXISTS idx_cul_provider   ON cloud_usage_log(provider);",
    "CREATE INDEX IF NOT EXISTS idx_cul_thread     ON cloud_usage_log(thread_id);",
    "CREATE INDEX IF NOT EXISTS idx_cul_uid        ON cloud_usage_log(uid);",
]


# ---------------------------------------------------------------------------
# Token estimation helper
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    if not text:
        return 0
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Singleton tracker class
# ---------------------------------------------------------------------------

class CloudUsageTracker:
    """Thread-safe, fire-and-forget cloud usage tracker backed by SQLite."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._db_conn: Optional[sqlite3.Connection] = None
        self._initialized = False

    # -- lazy init ----------------------------------------------------------

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            try:
                _DATA_DIR.mkdir(parents=True, exist_ok=True)
                self._db_conn = sqlite3.connect(str(_DB_FILE), check_same_thread=False)
                self._db_conn.execute("PRAGMA journal_mode=WAL;")
                self._db_conn.execute("PRAGMA busy_timeout=5000;")
                self._db_conn.execute(_CREATE_TABLE)
                for idx_sql in _CREATE_INDEXES:
                    self._db_conn.execute(idx_sql)
                self._db_conn.commit()
                self._initialized = True
                logger.info("[CLOUD-TRACKER] Initialized (db=%s)", _DB_FILE)
            except Exception as exc:
                logger.warning("[CLOUD-TRACKER] Init failed: %s", exc)

    # -- public API: log_cloud_call ----------------------------------------

    def log_cloud_call(
        self,
        call_type: str,
        provider: str,
        model: str = "",
        latency_ms: int = 0,
        success: bool = True,
        *,
        thread_id: Optional[str] = None,
        uid: Optional[int] = None,
        input_tokens_est: Optional[int] = None,
        output_tokens_est: Optional[int] = None,
        input_text: Optional[str] = None,
        output_text: Optional[str] = None,
        error_type: Optional[str] = None,
        escalation_reason: Optional[str] = None,
        user_message: Optional[str] = None,
    ) -> None:
        """Fire-and-forget insert of a cloud API call record.

        Token estimates can be provided directly or computed from input_text/output_text.
        user_message is truncated to 100 chars for the preview column.
        """
        try:
            self._ensure_init()
            if self._db_conn is None:
                return

            ts = time.time()
            in_tok = input_tokens_est if input_tokens_est is not None else _estimate_tokens(input_text or "")
            out_tok = output_tokens_est if output_tokens_est is not None else _estimate_tokens(output_text or "")
            preview = (user_message or "")[:100] if user_message else None

            with self._lock:
                self._db_conn.execute(
                    """INSERT INTO cloud_usage_log
                       (timestamp, thread_id, uid, call_type, provider, model,
                        input_tokens_est, output_tokens_est, latency_ms,
                        success, error_type, escalation_reason, user_message_preview)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        ts,
                        thread_id,
                        uid,
                        call_type,
                        provider,
                        model,
                        in_tok,
                        out_tok,
                        latency_ms,
                        1 if success else 0,
                        error_type,
                        escalation_reason,
                        preview,
                    ),
                )
                self._db_conn.commit()
        except Exception as exc:
            # Never let tracking break the response pipeline
            logger.warning("[CLOUD-TRACKER] log_cloud_call failed: %s", exc)

    # -- public API: get_usage_summary -------------------------------------

    def get_usage_summary(
        self,
        since_ts: Optional[float] = None,
        uid: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Return counts and total latency grouped by call_type and provider.

        Args:
            since_ts: Unix timestamp lower bound (inclusive). None = all time.
            uid: Filter by user ID. None = all users.

        Returns:
            {
                "total_calls": int,
                "total_latency_ms": int,
                "success_count": int,
                "failure_count": int,
                "total_input_tokens_est": int,
                "total_output_tokens_est": int,
                "by_call_type": { call_type: { calls, latency_ms, success, failure, input_tokens, output_tokens } },
                "by_provider": { provider: { calls, latency_ms, success, failure, input_tokens, output_tokens } },
            }
        """
        try:
            self._ensure_init()
            if self._db_conn is None:
                return {"total_calls": 0, "error": "db not initialized"}

            clauses: List[str] = []
            params: List[Any] = []

            if since_ts is not None:
                clauses.append("timestamp >= ?")
                params.append(since_ts)
            if uid is not None:
                clauses.append("uid = ?")
                params.append(uid)

            where = ""
            if clauses:
                where = "WHERE " + " AND ".join(clauses)

            # By call_type
            sql_ct = f"""
                SELECT call_type,
                       COUNT(*)              AS calls,
                       SUM(latency_ms)       AS total_lat,
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS ok,
                       SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS fail,
                       SUM(input_tokens_est)  AS in_tok,
                       SUM(output_tokens_est) AS out_tok
                FROM cloud_usage_log
                {where}
                GROUP BY call_type
            """

            # By provider
            sql_prov = f"""
                SELECT provider,
                       COUNT(*)              AS calls,
                       SUM(latency_ms)       AS total_lat,
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS ok,
                       SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS fail,
                       SUM(input_tokens_est)  AS in_tok,
                       SUM(output_tokens_est) AS out_tok
                FROM cloud_usage_log
                {where}
                GROUP BY provider
            """

            with self._lock:
                cur_ct = self._db_conn.execute(sql_ct, params)
                rows_ct = cur_ct.fetchall()
                cur_prov = self._db_conn.execute(sql_prov, params)
                rows_prov = cur_prov.fetchall()

            by_call_type: Dict[str, Any] = {}
            total_calls = 0
            total_lat = 0
            total_ok = 0
            total_fail = 0
            total_in = 0
            total_out = 0

            for ct, calls, lat, ok, fail, in_tok, out_tok in rows_ct:
                by_call_type[ct] = {
                    "calls": calls,
                    "latency_ms": lat or 0,
                    "success": ok or 0,
                    "failure": fail or 0,
                    "input_tokens_est": in_tok or 0,
                    "output_tokens_est": out_tok or 0,
                }
                total_calls += calls
                total_lat += lat or 0
                total_ok += ok or 0
                total_fail += fail or 0
                total_in += in_tok or 0
                total_out += out_tok or 0

            by_provider: Dict[str, Any] = {}
            for prov, calls, lat, ok, fail, in_tok, out_tok in rows_prov:
                by_provider[prov] = {
                    "calls": calls,
                    "latency_ms": lat or 0,
                    "success": ok or 0,
                    "failure": fail or 0,
                    "input_tokens_est": in_tok or 0,
                    "output_tokens_est": out_tok or 0,
                }

            return {
                "total_calls": total_calls,
                "total_latency_ms": total_lat,
                "success_count": total_ok,
                "failure_count": total_fail,
                "total_input_tokens_est": total_in,
                "total_output_tokens_est": total_out,
                "by_call_type": by_call_type,
                "by_provider": by_provider,
            }
        except Exception as exc:
            logger.warning("[CLOUD-TRACKER] get_usage_summary failed: %s", exc)
            return {"total_calls": 0, "error": str(exc)}

    # -- public API: get_recent_calls --------------------------------------

    def get_recent_calls(
        self,
        limit: int = 50,
        call_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return recent cloud_usage_log rows for debugging.

        Args:
            limit: Max rows (capped at 500).
            call_type: Filter by call_type (exact match). None = all.
        """
        try:
            self._ensure_init()
            if self._db_conn is None:
                return []

            limit = min(max(1, limit), 500)
            clauses: List[str] = []
            params: List[Any] = []

            if call_type:
                clauses.append("call_type = ?")
                params.append(call_type)

            where = ""
            if clauses:
                where = "WHERE " + " AND ".join(clauses)

            sql = f"""
                SELECT id, timestamp, thread_id, uid, call_type, provider, model,
                       input_tokens_est, output_tokens_est, latency_ms,
                       success, error_type, escalation_reason, user_message_preview
                FROM cloud_usage_log
                {where}
                ORDER BY id DESC
                LIMIT ?
            """
            params.append(limit)

            with self._lock:
                cur = self._db_conn.execute(sql, params)
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()

            return [dict(zip(cols, row)) for row in rows]
        except Exception as exc:
            logger.warning("[CLOUD-TRACKER] get_recent_calls failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_tracker_instance: Optional[CloudUsageTracker] = None
_instance_lock = threading.Lock()


def get_cloud_usage_tracker() -> CloudUsageTracker:
    """Return (and lazily create) the singleton CloudUsageTracker."""
    global _tracker_instance
    if _tracker_instance is None:
        with _instance_lock:
            if _tracker_instance is None:
                _tracker_instance = CloudUsageTracker()
    return _tracker_instance


def log_cloud_call(
    call_type: str,
    provider: str,
    model: str = "",
    latency_ms: int = 0,
    success: bool = True,
    **kwargs,
) -> None:
    """Module-level convenience wrapper — fire-and-forget, never raises."""
    try:
        tracker = get_cloud_usage_tracker()
        tracker.log_cloud_call(
            call_type=call_type,
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            success=success,
            **kwargs,
        )
    except Exception:
        pass


# Budget thresholds (USD)
_BUDGET_THRESHOLDS = [
    (10, "green"),
    (25, "yellow"),
    (50, "orange"),
    (75, "red"),
    (100, "critical"),
]


def check_budget() -> Dict[str, Any]:
    """Check cumulative API cost against budget thresholds.

    Returns: {"total_cost_usd": float, "level": str, "budget_limit": 100,
              "remaining": float, "warning": str | None}
    """
    try:
        tracker = get_cloud_usage_tracker()
        tracker._ensure_init()
        with tracker._lock:
            row = tracker._conn.execute(
                "SELECT SUM(input_tokens_est * 1.0 + output_tokens_est * 1.0) as total_tokens, "
                "COUNT(*) as total_calls FROM cloud_usage_log WHERE success = 1"
            ).fetchone()

        total_tokens = (row[0] or 0) if row else 0
        total_calls = (row[1] or 0) if row else 0

        # Estimate cost using average Sonnet pricing ($3/M in + $15/M out)
        # Rough: assume 60% input, 40% output
        input_est = total_tokens * 0.6
        output_est = total_tokens * 0.4
        total_cost = (input_est / 1_000_000 * 3.0) + (output_est / 1_000_000 * 15.0)

        # Determine warning level
        level = "green"
        warning = None
        for threshold, lvl in _BUDGET_THRESHOLDS:
            if total_cost >= threshold:
                level = lvl
        if level in ("orange", "red", "critical"):
            warning = f"API spending at ${total_cost:.2f} of $100 budget ({level})"

        return {
            "total_cost_usd": round(total_cost, 4),
            "total_calls": total_calls,
            "level": level,
            "budget_limit": 100,
            "remaining": round(100 - total_cost, 4),
            "warning": warning,
        }
    except Exception as e:
        logger.debug("[BUDGET] check_budget failed: %s", e)
        return {"total_cost_usd": 0, "total_calls": 0, "level": "green",
                "budget_limit": 100, "remaining": 100, "warning": None}

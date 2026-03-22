"""
Cloud Usage Logger — file-based and SQLite logging for every cloud API call.

Logs to:
  1. data/cloud_usage.log  (append-only text, one JSON line per call)
  2. data/cloud_usage.db   (SQLite, queryable)

Initializes lazily on first use.  Thread-safe via SQLite WAL mode and file locks.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_LOG_FILE = _DATA_DIR / "cloud_usage.log"
_DB_FILE = _DATA_DIR / "cloud_usage.db"

# ---------------------------------------------------------------------------
# Cost table (USD per 1K tokens, input / output)
# ---------------------------------------------------------------------------

COST_PER_1K: Dict[str, Dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "claude-sonnet-4-5": {"input": 0.003, "output": 0.015},
    # cookie/subscription calls have zero direct API cost
    "claude_subscription": {"input": 0.0, "output": 0.0},
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated cost in USD."""
    rates = COST_PER_1K.get(model, COST_PER_1K.get("gpt-4o-mini", {}))
    cost = (input_tokens / 1000.0) * rates.get("input", 0.0)
    cost += (output_tokens / 1000.0) * rates.get("output", 0.0)
    return round(cost, 8)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _truncate(text: str, limit: int = 200) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


# ---------------------------------------------------------------------------
# SQLite schema
# ---------------------------------------------------------------------------

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS cloud_usage (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    provider        TEXT    NOT NULL,
    feature         TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    latency_ms      INTEGER NOT NULL DEFAULT 0,
    success         INTEGER NOT NULL DEFAULT 1,
    cost_estimate   REAL    NOT NULL DEFAULT 0.0,
    prompt_text     TEXT    NOT NULL DEFAULT '',
    response_text   TEXT    NOT NULL DEFAULT '',
    error_message   TEXT    NOT NULL DEFAULT ''
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cu_timestamp ON cloud_usage(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_cu_feature   ON cloud_usage(feature);",
]

# ---------------------------------------------------------------------------
# Singleton logger class
# ---------------------------------------------------------------------------


class CloudUsageLogger:
    """Thread-safe cloud usage logger backed by a log file and SQLite."""

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
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            self._db_conn = sqlite3.connect(str(_DB_FILE), check_same_thread=False)
            self._db_conn.execute("PRAGMA journal_mode=WAL;")
            self._db_conn.execute("PRAGMA busy_timeout=5000;")
            self._db_conn.execute(_CREATE_TABLE)
            for idx_sql in _CREATE_INDEXES:
                self._db_conn.execute(idx_sql)
            self._db_conn.commit()
            self._initialized = True
            logger.info("[CLOUD-LOG] CloudUsageLogger initialized (db=%s)", _DB_FILE)

    # -- public API ---------------------------------------------------------

    def log(
        self,
        *,
        provider: str,
        feature: str,
        model: str,
        prompt: str,
        response: str,
        latency_ms: int,
        success: bool,
        error_message: str = "",
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
    ) -> None:
        """Record a single cloud API call to both the log file and SQLite."""
        self._ensure_init()

        ts = datetime.now(timezone.utc).isoformat()
        in_tok = input_tokens if input_tokens is not None else _estimate_tokens(prompt)
        out_tok = output_tokens if output_tokens is not None else _estimate_tokens(response)
        cost = _estimate_cost(model, in_tok, out_tok)
        prompt_trunc = _truncate(prompt, 200)
        response_trunc = _truncate(response, 200)

        record = {
            "timestamp": ts,
            "provider": provider,
            "feature": feature,
            "model": model,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "latency_ms": latency_ms,
            "success": success,
            "cost_estimate": cost,
            "prompt": prompt_trunc,
            "response": response_trunc,
            "error": error_message,
        }

        # 1) Append to log file
        try:
            with open(_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as exc:
            logger.warning("[CLOUD-LOG] Failed to write log file: %s", exc)

        # 2) Insert into SQLite
        try:
            with self._lock:
                assert self._db_conn is not None
                self._db_conn.execute(
                    """INSERT INTO cloud_usage
                       (timestamp, provider, feature, model,
                        input_tokens, output_tokens, latency_ms,
                        success, cost_estimate, prompt_text, response_text, error_message)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        ts,
                        provider,
                        feature,
                        model,
                        in_tok,
                        out_tok,
                        latency_ms,
                        1 if success else 0,
                        cost,
                        prompt_trunc,
                        response_trunc,
                        error_message,
                    ),
                )
                self._db_conn.commit()
        except Exception as exc:
            logger.warning("[CLOUD-LOG] Failed to write SQLite: %s", exc)

    # -- query helpers ------------------------------------------------------

    def get_history(
        self,
        *,
        limit: int = 50,
        feature: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return recent entries from the SQLite table.

        Args:
            limit: max rows to return (default 50, capped at 500).
            feature: filter by feature name (exact match).
            start_date: ISO date string lower bound (inclusive).
            end_date: ISO date string upper bound (inclusive, extended to end-of-day).
        """
        self._ensure_init()
        limit = min(max(1, limit), 500)

        clauses: List[str] = []
        params: List[Any] = []

        if feature:
            clauses.append("feature = ?")
            params.append(feature)
        if start_date:
            clauses.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            # extend to end of day if just a date
            if len(end_date) == 10:
                end_date = end_date + "T23:59:59.999999Z"
            clauses.append("timestamp <= ?")
            params.append(end_date)

        where = ""
        if clauses:
            where = "WHERE " + " AND ".join(clauses)

        sql = f"""
            SELECT id, timestamp, provider, feature, model,
                   input_tokens, output_tokens, latency_ms,
                   success, cost_estimate, prompt_text, response_text, error_message
            FROM cloud_usage
            {where}
            ORDER BY id DESC
            LIMIT ?
        """
        params.append(limit)

        with self._lock:
            assert self._db_conn is not None
            cur = self._db_conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()

        return [dict(zip(cols, row)) for row in rows]

    def get_daily_summary(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Return aggregated stats for a given day (defaults to today UTC).

        Returns:
            {
                "date": "2026-03-22",
                "total_calls": 15,
                "total_input_tokens": 3200,
                "total_output_tokens": 1800,
                "total_cost": 0.00234,
                "success_count": 14,
                "failure_count": 1,
                "by_feature": {
                    "slot_classification": {...},
                    ...
                },
            }
        """
        self._ensure_init()
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        start = date_str + "T00:00:00"
        end = date_str + "T23:59:59.999999Z"

        sql = """
            SELECT feature,
                   COUNT(*)              AS calls,
                   SUM(input_tokens)     AS in_tok,
                   SUM(output_tokens)    AS out_tok,
                   SUM(cost_estimate)    AS cost,
                   SUM(latency_ms)       AS total_latency,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS ok,
                   SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS fail
            FROM cloud_usage
            WHERE timestamp >= ? AND timestamp <= ?
            GROUP BY feature
        """

        with self._lock:
            assert self._db_conn is not None
            cur = self._db_conn.execute(sql, (start, end))
            rows = cur.fetchall()

        total_calls = 0
        total_in = 0
        total_out = 0
        total_cost = 0.0
        total_ok = 0
        total_fail = 0
        by_feature: Dict[str, Any] = {}

        for feature, calls, in_tok, out_tok, cost, latency, ok, fail in rows:
            total_calls += calls
            total_in += in_tok or 0
            total_out += out_tok or 0
            total_cost += cost or 0.0
            total_ok += ok or 0
            total_fail += fail or 0
            by_feature[feature] = {
                "calls": calls,
                "input_tokens": in_tok or 0,
                "output_tokens": out_tok or 0,
                "cost": round(cost or 0.0, 8),
                "avg_latency_ms": round((latency or 0) / max(calls, 1)),
                "success": ok or 0,
                "failure": fail or 0,
            }

        return {
            "date": date_str,
            "total_calls": total_calls,
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "total_cost": round(total_cost, 8),
            "success_count": total_ok,
            "failure_count": total_fail,
            "by_feature": by_feature,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_logger_instance: Optional[CloudUsageLogger] = None
_instance_lock = threading.Lock()


def get_cloud_usage_logger() -> CloudUsageLogger:
    """Return (and lazily create) the singleton CloudUsageLogger."""
    global _logger_instance
    if _logger_instance is None:
        with _instance_lock:
            if _logger_instance is None:
                _logger_instance = CloudUsageLogger()
    return _logger_instance

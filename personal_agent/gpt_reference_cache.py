"""Thread-scoped temporary GPT reference cache.

This sits between the GPT log archive and CRT belief memory.
It stores short-lived reference packets per thread/topic so the
assistant can keep using archived context across restarts without
promoting every excerpt into durable belief memory.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional

from .runtime_paths import resolve_runtime_path

logger = logging.getLogger(__name__)

_DB_PATH = str(resolve_runtime_path("gpt_reference_cache.db"))

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS gpt_reference_cache (
    thread_id TEXT NOT NULL,
    topic_key TEXT NOT NULL,
    query_text TEXT,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    summary TEXT,
    excerpts_json TEXT,
    PRIMARY KEY (thread_id, topic_key)
)
"""


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(_CREATE_TABLE_SQL)
    conn.commit()
    return conn


def get_packet(thread_id: str, topic_key: str, *, now_ts: Optional[float] = None) -> Optional[Dict[str, Any]]:
    now_ts = now_ts or time.time()
    try:
        conn = _get_db()
        row = conn.execute(
            """
            SELECT thread_id, topic_key, query_text, created_at, expires_at, summary, excerpts_json
            FROM gpt_reference_cache
            WHERE thread_id = ? AND topic_key = ?
            """,
            (thread_id, topic_key),
        ).fetchone()
        conn.close()
        if not row:
            return None
        if float(row[4] or 0.0) <= now_ts:
            delete_packet(thread_id, topic_key)
            return None
        return {
            "thread_id": row[0],
            "topic_key": row[1],
            "query_text": row[2] or "",
            "created_at": float(row[3] or 0.0),
            "expires_at": float(row[4] or 0.0),
            "summary": row[5] or "",
            "excerpts": json.loads(row[6] or "[]"),
        }
    except Exception as exc:
        logger.warning("[GPT_REF_CACHE] get failed: %s", exc)
        return None


def put_packet(
    *,
    thread_id: str,
    topic_key: str,
    query_text: str,
    summary: str,
    excerpts: List[Dict[str, Any]],
    ttl_seconds: int = 86400,
) -> None:
    now_ts = time.time()
    expires_at = now_ts + max(int(ttl_seconds), 60)
    try:
        conn = _get_db()
        conn.execute(
            """
            INSERT OR REPLACE INTO gpt_reference_cache
            (thread_id, topic_key, query_text, created_at, expires_at, summary, excerpts_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                thread_id,
                topic_key,
                query_text,
                now_ts,
                expires_at,
                summary,
                json.dumps(excerpts, default=str),
            ),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("[GPT_REF_CACHE] put failed: %s", exc)


def delete_packet(thread_id: str, topic_key: str) -> None:
    try:
        conn = _get_db()
        conn.execute(
            "DELETE FROM gpt_reference_cache WHERE thread_id = ? AND topic_key = ?",
            (thread_id, topic_key),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("[GPT_REF_CACHE] delete failed: %s", exc)


def cleanup_expired(*, now_ts: Optional[float] = None) -> int:
    now_ts = now_ts or time.time()
    try:
        conn = _get_db()
        cur = conn.execute(
            "DELETE FROM gpt_reference_cache WHERE expires_at <= ?",
            (now_ts,),
        )
        deleted = int(cur.rowcount or 0)
        conn.commit()
        conn.close()
        return deleted
    except Exception as exc:
        logger.warning("[GPT_REF_CACHE] cleanup failed: %s", exc)
        return 0

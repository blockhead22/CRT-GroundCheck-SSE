"""Collapse trail logging for DNNT training data lineage."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import threading
import time
import uuid
from typing import Any, Dict, Iterable, Optional

from personal_agent.db_utils import get_db_connection

logger = logging.getLogger(__name__)

_LOGGER_SINGLETON: Optional["CollapseTrailLogger"] = None
_LOGGER_LOCK = threading.Lock()


def _safe_json(value: Any) -> str:
    def _default(obj: Any) -> str:
        return str(obj)

    return json.dumps(value, default=_default, ensure_ascii=True)


class CollapseTrailLogger:
    """Stores full query->retrieval->reasoning->response lineage."""

    def __init__(self, db_path: str = "personal_agent/crt_collapse_trails.db"):
        self.db_path = str(Path(db_path))
        self._init_db()

    def _init_db(self) -> None:
        with get_db_connection(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS collapse_trails (
                    trail_id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    thread_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    mode TEXT,
                    query_text TEXT NOT NULL,
                    answer_text TEXT NOT NULL,
                    response_type TEXT,
                    gates_passed INTEGER,
                    gate_reason TEXT,
                    confidence REAL,
                    unresolved_contradictions_total INTEGER,
                    unresolved_hard_conflicts INTEGER,
                    retrieved_ids_json TEXT,
                    prompt_ids_json TEXT,
                    payload_json TEXT
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_collapse_trails_thread_ts "
                "ON collapse_trails(thread_id, timestamp DESC)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_collapse_trails_stage "
                "ON collapse_trails(stage, timestamp DESC)"
            )
            conn.commit()

    @staticmethod
    def _extract_ids(items: Iterable[Any]) -> list[str]:
        output: list[str] = []
        for item in items:
            if isinstance(item, dict):
                mid = item.get("memory_id")
                if mid:
                    output.append(str(mid))
        return output

    def log_trail(
        self,
        *,
        thread_id: str,
        query: str,
        answer: str,
        result: Optional[Dict[str, Any]] = None,
        stage: str = "chat_send",
        mode: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload = dict(result or {})
        if extra:
            payload["extra"] = dict(extra)

        retrieved = payload.get("retrieved_memories") or []
        prompt = payload.get("prompt_memories") or []
        trail_id = f"trail_{int(time.time() * 1000)}_{uuid.uuid4().hex[:10]}"

        with get_db_connection(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO collapse_trails (
                    trail_id, timestamp, thread_id, stage, mode,
                    query_text, answer_text, response_type, gates_passed, gate_reason,
                    confidence, unresolved_contradictions_total, unresolved_hard_conflicts,
                    retrieved_ids_json, prompt_ids_json, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trail_id,
                    time.time(),
                    str(thread_id or "default"),
                    str(stage or "chat_send"),
                    str(mode) if mode is not None else None,
                    str(query or ""),
                    str(answer or ""),
                    payload.get("response_type"),
                    1 if bool(payload.get("gates_passed")) else 0,
                    payload.get("gate_reason"),
                    float(payload.get("confidence") or 0.0),
                    int(payload.get("unresolved_contradictions_total") or 0),
                    int(payload.get("unresolved_hard_conflicts") or 0),
                    _safe_json(self._extract_ids(retrieved)),
                    _safe_json(self._extract_ids(prompt)),
                    _safe_json(payload),
                ),
            )
            conn.commit()

        return trail_id


def get_collapse_trail_logger(db_path: str = "personal_agent/crt_collapse_trails.db") -> CollapseTrailLogger:
    global _LOGGER_SINGLETON
    if _LOGGER_SINGLETON is not None:
        return _LOGGER_SINGLETON
    with _LOGGER_LOCK:
        if _LOGGER_SINGLETON is None:
            _LOGGER_SINGLETON = CollapseTrailLogger(db_path=db_path)
    return _LOGGER_SINGLETON


"""
Append-only JSONL writer for chat conversation logs.

Writes one record per conversation turn to daily log files at:
    training_data/chat_logs/chat_log_YYYY-MM-DD.jsonl

Designed for future fine-tuning / training data extraction.
Non-blocking: all writes happen in a background thread.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_LOG_DIR = Path(__file__).resolve().parent.parent / "training_data" / "chat_logs"
_write_lock = threading.Lock()


def _ensure_dir() -> Path:
    """Create the log directory if it doesn't exist. Returns the path."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR


def _today_file() -> Path:
    """Return the JSONL file path for today (UTC)."""
    return _ensure_dir() / f"chat_log_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"


def log_chat_turn(
    *,
    thread_id: str,
    user_message: str,
    assistant_response: str,
    model_used: str = "",
    generation_mode: str = "local",
    intent: str = "conversational",
    latency_ms: int = 0,
    memories_cited: int = 0,
    governance_tier: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Append a single conversation turn to today's JSONL log.

    This is the public API. It serialises the record and writes it
    in a background thread so the response pipeline is never blocked.
    """
    record: Dict[str, Any] = {
        "timestamp": time.time(),
        "thread_id": thread_id or "",
        "user_message": user_message or "",
        "assistant_response": assistant_response or "",
        "model_used": model_used,
        "generation_mode": generation_mode,
        "intent": intent,
        "latency_ms": latency_ms,
        "memories_cited": memories_cited,
        "governance_tier": governance_tier,
        "metadata": metadata or {},
    }

    threading.Thread(
        target=_write_record,
        args=(record,),
        daemon=True,
        name="training-log-writer",
    ).start()


def _write_record(record: Dict[str, Any]) -> None:
    """Serialise and append one JSON line. Thread-safe via lock."""
    try:
        line = json.dumps(record, ensure_ascii=False, default=str)
        path = _today_file()
        with _write_lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception as exc:
        logger.debug("[TRAINING_LOG] Write failed: %s", exc)

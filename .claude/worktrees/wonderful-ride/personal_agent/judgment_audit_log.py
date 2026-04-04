"""
Judgment Audit Log — Silent decision trail for CRT gates.

Every time a gate fires a decision that changes what gets stored or said,
it logs here. This covers:
  - DisclosurePolicy REJECT / CLARIFY decisions
  - CRT-as-Critic gate blocks (hallucination / low-confidence speech)
  - Contradiction detection on memory store

Log format: append-only JSONL, one entry per decision, daily rotation.
Read via GET /api/audit/judgments.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

GATE_BLOCKED       = "gate_blocked"        # GroundCheck / critic blocked output
DISCLOSURE_CLARIFY = "disclosure_clarify"  # DisclosurePolicy → CLARIFY
DISCLOSURE_REJECT  = "disclosure_reject"   # DisclosurePolicy → REJECT
CONTRADICTION_STORE = "contradiction_store" # Inline contradiction on memory store


@dataclass
class JudgmentEvent:
    """Single gate-decision entry."""
    event_type: str           # one of the constants above
    timestamp: float          # unix epoch
    slot: Optional[str]       # fact slot involved, if any
    reason: str               # human-readable explanation
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    p_valid: Optional[float] = None   # confidence score if applicable
    memory_id: Optional[str] = None   # memory ID if applicable
    thread_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp_iso"] = datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat()
        return d


# ---------------------------------------------------------------------------
# Log writer
# ---------------------------------------------------------------------------

class JudgmentAuditLog:
    """Thread-safe, append-only JSONL judgment log with daily rotation."""

    def __init__(self, log_dir: str = "adapter_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._current_date = datetime.utcnow().date()
        self._log_file = self._path_for(self._current_date)

    def _path_for(self, date) -> Path:
        return self.log_dir / f"judgments_{date.isoformat()}.jsonl"

    def _rotate(self) -> None:
        today = datetime.utcnow().date()
        if today != self._current_date:
            self._current_date = today
            self._log_file = self._path_for(today)

    def log(
        self,
        event_type: str,
        reason: str,
        *,
        slot: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        p_valid: Optional[float] = None,
        memory_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        event = JudgmentEvent(
            event_type=event_type,
            timestamp=time.time(),
            slot=slot,
            reason=reason,
            old_value=old_value,
            new_value=new_value,
            p_valid=p_valid,
            memory_id=memory_id,
            thread_id=thread_id,
            extra=extra,
        )
        with self._lock:
            self._rotate()
            try:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event.to_dict()) + "\n")
            except Exception as exc:
                logger.warning(f"[JUDGMENT_AUDIT] Failed to write log: {exc}")

    def recent(self, limit: int = 100, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return most-recent entries from today's log, newest first."""
        if not self._log_file.exists():
            return []
        entries: List[Dict[str, Any]] = []
        try:
            with open(self._log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event_type and d.get("event_type") != event_type:
                    continue
                entries.append(d)
                if len(entries) >= limit:
                    break
        except Exception as exc:
            logger.warning(f"[JUDGMENT_AUDIT] Failed to read log: {exc}")
        return entries


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: Optional[JudgmentAuditLog] = None
_instance_lock = threading.Lock()


def get_judgment_log(log_dir: str = "adapter_logs") -> JudgmentAuditLog:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = JudgmentAuditLog(log_dir)
    return _instance


def log_judgment(
    event_type: str,
    reason: str,
    **kwargs: Any,
) -> None:
    """Module-level helper — safe to call from anywhere, never raises."""
    try:
        get_judgment_log().log(event_type, reason, **kwargs)
    except Exception as exc:
        logger.debug(f"[JUDGMENT_AUDIT] Suppressed error: {exc}")

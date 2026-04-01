"""Outbox — proactive message queue for Phase 6.

Any part of the system can push a proactive message here.
The WS drain loop picks it up and sends it to the active client
for that thread_id as a `proactive_turn` event.

Usage:
    from personal_agent.outbox import get_outbox
    get_outbox().push(
        thread_id="t_abc123",
        content="I noticed something while running — want me to investigate?",
        trigger="subagent_complete",
        metadata={"source": "spawn_agent", "task": "..."},
    )
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OutboxMessage:
    thread_id: str
    content: str
    trigger: str                         # what caused this (e.g. "subagent_complete", "drift_alert")
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class OutboxQueue:
    """Thread-safe queue for proactive messages, keyed by thread_id."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: List[OutboxMessage] = []

    def push(
        self,
        thread_id: str,
        content: str,
        trigger: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Queue a proactive message for a thread."""
        msg = OutboxMessage(
            thread_id=thread_id,
            content=content,
            trigger=trigger,
            metadata=metadata or {},
        )
        with self._lock:
            self._queue.append(msg)

    def drain(self, thread_id: str) -> List[OutboxMessage]:
        """Remove and return all pending messages for a thread."""
        with self._lock:
            pending = [m for m in self._queue if m.thread_id == thread_id]
            self._queue = [m for m in self._queue if m.thread_id != thread_id]
        return pending

    def drain_all(self) -> List[OutboxMessage]:
        """Remove and return all pending messages (for broadcast scenarios)."""
        with self._lock:
            all_msgs = list(self._queue)
            self._queue = []
        return all_msgs

    def pending_count(self, thread_id: Optional[str] = None) -> int:
        with self._lock:
            if thread_id:
                return sum(1 for m in self._queue if m.thread_id == thread_id)
            return len(self._queue)


# ── Singleton ─────────────────────────────────────────────────────────────────

_outbox: Optional[OutboxQueue] = None


def get_outbox() -> OutboxQueue:
    global _outbox
    if _outbox is None:
        _outbox = OutboxQueue()
    return _outbox

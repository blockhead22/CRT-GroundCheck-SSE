# OutboxQueue module
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
        """Remove and return ALL pending messages (for debugging)."""
        with self._lock:
            pending = self._queue.copy()
            self._queue.clear()
        return pending

    def peek(self, thread_id: Optional[str] = None) -> List[OutboxMessage]:
        """View pending messages without removing them."""
        with self._lock:
            if thread_id is None:
                return self._queue.copy()
            return [m for m in self._queue if m.thread_id == thread_id]

    def size(self, thread_id: Optional[str] = None) -> int:
        """Count pending messages."""
        with self._lock:
            if thread_id is None:
                return len(self._queue)
            return sum(1 for m in self._queue if m.thread_id == thread_id)


# Global singleton
_outbox: Optional[OutboxQueue] = None
_outbox_lock = threading.Lock()


def get_outbox() -> OutboxQueue:
    """Get the global outbox singleton."""
    global _outbox
    if _outbox is None:
        with _outbox_lock:
            if _outbox is None:
                _outbox = OutboxQueue()
    return _outbox


def reset_outbox() -> None:
    """Reset the global outbox (for testing)."""
    global _outbox
    with _outbox_lock:
        _outbox = None

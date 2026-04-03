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
from typing import Any, Callable, Dict, List, Optional


@dataclass
class OutboxMessage:
    thread_id: str
    content: str
    trigger: str                         # what caused this (e.g. "subagent_complete", "drift_alert")
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class OutboxQueue:
    """Thread-safe queue for proactive messages, keyed by thread_id.
    
    The OutboxQueue manages a collection of proactive messages that the system
    can send to users without them explicitly asking for them. This is used for
    notifications like subagent completion, drift alerts, or other system events
    that warrant user attention.
    
    Key features:
    - Thread-safe operations using locks
    - Messages are organized by thread_id for multi-user support
    - Each message includes trigger type and metadata for context
    - Automatic timestamp tracking
    - Bulk drain operations for efficient message retrieval
    
    Methods:
        push(): Add a new proactive message to the queue
        drain(): Remove and return all messages for a specific thread
        drain_all(): Remove and return all messages across all threads
        peek(): View pending messages without removing them
        clear(): Remove all messages for a thread without returning them
    
    The queue is typically consumed by WebSocket handlers that poll for
    pending messages and deliver them to connected clients as 'proactive_turn'
    events.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: List[OutboxMessage] = []
        self._listeners: List[Callable[[OutboxMessage], None]] = []

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
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(msg)
            except Exception:
                # Listener failures must never block queueing.
                pass

    def drain(self, thread_id: str) -> List[OutboxMessage]:
        """Remove and return all pending messages for a thread."""
        with self._lock:
            pending = [m for m in self._queue if m.thread_id == thread_id]
            self._queue = [m for m in self._queue if m.thread_id != thread_id]
        return pending

    def drain_all(self) -> List[OutboxMessage]:
        """Remove and return ALL pending messages across all threads."""
        with self._lock:
            pending = list(self._queue)
            self._queue.clear()
        return pending

    def peek(self, thread_id: str) -> List[OutboxMessage]:
        """View pending messages for a thread without removing them."""
        with self._lock:
            return [m for m in self._queue if m.thread_id == thread_id]

    def peek_all(self) -> List[OutboxMessage]:
        """View all pending messages without removing them."""
        with self._lock:
            return list(self._queue)

    def clear(self, thread_id: str) -> int:
        """Remove all pending messages for a thread, return count removed."""
        with self._lock:
            count = sum(1 for m in self._queue if m.thread_id == thread_id)
            self._queue = [m for m in self._queue if m.thread_id != thread_id]
        return count

    def count(self, thread_id: Optional[str] = None) -> int:
        """Return count of pending messages (for thread_id if specified, else all)."""
        with self._lock:
            if thread_id is None:
                return len(self._queue)
            return sum(1 for m in self._queue if m.thread_id == thread_id)

    def subscribe(self, callback: Callable[[OutboxMessage], None]) -> None:
        """Register a callback invoked after a message is queued."""
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[OutboxMessage], None]) -> None:
        """Remove a previously registered push callback."""
        with self._lock:
            try:
                self._listeners.remove(callback)
            except ValueError:
                pass


# Global singleton
_outbox: Optional[OutboxQueue] = None
_outbox_lock = threading.Lock()


def get_outbox() -> OutboxQueue:
    """Get the global outbox singleton (thread-safe initialization)."""
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

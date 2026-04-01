"""EventBus — lightweight async pub/sub for pipeline events.

Pipeline code emits events here. WebSocket connections (and the legacy SSE
adapter) subscribe and forward to clients. Thread-safe for mixed
sync/async callers.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Type alias for subscribers
Subscriber = Callable  # async def callback(event: dict) -> None


class EventBus:
    """Async pub/sub event bus.

    Usage:
        bus = EventBus()
        bus.subscribe(my_handler)                       # global
        bus.subscribe(my_handler, thread_id="abc123")   # thread-scoped
        await bus.emit("token", {"content": "Hello"}, thread_id="abc123")
    """

    def __init__(self) -> None:
        self._global_subscribers: List[Subscriber] = []
        self._thread_subscribers: Dict[str, List[Subscriber]] = {}
        self._lock = asyncio.Lock()

    async def emit(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        thread_id: Optional[str] = None,
    ) -> int:
        """Emit an event to all relevant subscribers.

        Returns the number of subscribers that received the event.
        """
        event = {
            "type": event_type,
            **(data or {}),
            "ts": time.time(),
        }
        if thread_id:
            event["thread_id"] = thread_id

        delivered = 0

        # Global subscribers always receive
        for cb in list(self._global_subscribers):
            try:
                await cb(event)
                delivered += 1
            except Exception:
                logger.exception("[EVENT_BUS] Error in global subscriber")

        # Thread-scoped subscribers
        if thread_id and thread_id in self._thread_subscribers:
            for cb in list(self._thread_subscribers[thread_id]):
                try:
                    await cb(event)
                    delivered += 1
                except Exception:
                    logger.exception("[EVENT_BUS] Error in thread subscriber")

        return delivered

    def emit_sync(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        thread_id: Optional[str] = None,
    ) -> None:
        """Fire-and-forget emit from synchronous code."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit(event_type, data, thread_id))
        except RuntimeError:
            # No running loop — best-effort via new loop
            try:
                asyncio.run(self.emit(event_type, data, thread_id))
            except Exception:
                logger.debug("[EVENT_BUS] Could not emit sync: no event loop")

    def subscribe(
        self,
        callback: Subscriber,
        thread_id: Optional[str] = None,
    ) -> None:
        """Subscribe to events. If thread_id is given, only receive events for that thread."""
        if thread_id:
            if thread_id not in self._thread_subscribers:
                self._thread_subscribers[thread_id] = []
            self._thread_subscribers[thread_id].append(callback)
        else:
            self._global_subscribers.append(callback)

    def unsubscribe(
        self,
        callback: Subscriber,
        thread_id: Optional[str] = None,
    ) -> None:
        """Remove a subscriber."""
        if thread_id:
            subs = self._thread_subscribers.get(thread_id, [])
            try:
                subs.remove(callback)
            except ValueError:
                pass
            if not subs:
                self._thread_subscribers.pop(thread_id, None)
        else:
            try:
                self._global_subscribers.remove(callback)
            except ValueError:
                pass

    def clear_thread(self, thread_id: str) -> None:
        """Remove all subscribers for a thread (cleanup after disconnect)."""
        self._thread_subscribers.pop(thread_id, None)

    @property
    def subscriber_count(self) -> int:
        total = len(self._global_subscribers)
        for subs in self._thread_subscribers.values():
            total += len(subs)
        return total


# ── Singleton ─────────────────────────────────────────────────────────

_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create the global EventBus singleton."""
    global _bus
    if _bus is None:
        _bus = EventBus()
        logger.info("[EVENT_BUS] Initialized")
    return _bus

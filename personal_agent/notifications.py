"""Notification delivery for CRT/Aether commitments.

Delivers commitment notifications via SSE to active browser connections.
Future: Telegram, SMS channels.

Uses a simple in-memory connection registry: active SSE connections
register their asyncio.Queue, and commitment fires push events to all queues.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SSE connection registry
# ---------------------------------------------------------------------------

# Keyed by user_id (or "default" for single-user mode).
# Each entry is a list of asyncio.Queues — one per active SSE connection.
_active_sse_connections: Dict[str, List[asyncio.Queue]] = {}


def register_sse_connection(user_id: str = "default") -> asyncio.Queue:
    """Register a new SSE connection and return its queue."""
    queue: asyncio.Queue = asyncio.Queue()
    if user_id not in _active_sse_connections:
        _active_sse_connections[user_id] = []
    _active_sse_connections[user_id].append(queue)
    logger.info("[NOTIFICATIONS] SSE connection registered for user=%s (total=%d)",
                user_id, len(_active_sse_connections[user_id]))
    return queue


def unregister_sse_connection(queue: asyncio.Queue, user_id: str = "default") -> None:
    """Remove an SSE connection when it disconnects."""
    if user_id in _active_sse_connections:
        try:
            _active_sse_connections[user_id].remove(queue)
            logger.info("[NOTIFICATIONS] SSE connection unregistered for user=%s (remaining=%d)",
                        user_id, len(_active_sse_connections[user_id]))
        except ValueError:
            pass
        if not _active_sse_connections[user_id]:
            del _active_sse_connections[user_id]


def get_active_connection_count(user_id: str = "default") -> int:
    """Get the number of active SSE connections for a user."""
    return len(_active_sse_connections.get(user_id, []))


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

async def emit_commitment_notification(commitment: Any, user_id: str = "default") -> int:
    """Push a commitment notification to all active SSE streams for a user.

    Args:
        commitment: A Commitment dataclass instance
        user_id: Target user ID

    Returns:
        Number of connections the event was pushed to.
    """
    event = {
        "type": "commitment_notification",
        "content": commitment.description,
        "metadata": {
            "commitment_id": commitment.commitment_id,
            "intent": commitment.intent,
            "priority": commitment.priority,
            "consequence": commitment.consequence,
            "recurrence": commitment.recurrence,
            "fire_count": getattr(commitment, "fire_count", 0),
            "timestamp": time.time(),
        },
    }

    # Also emit to EventBus for WebSocket clients
    try:
        from personal_agent.event_bus import get_event_bus
        await get_event_bus().emit("notification", {
            "subtype": "commitment",
            "content": commitment.description,
            "metadata": event["metadata"],
        })
    except Exception:
        logger.debug("[NOTIFICATIONS] EventBus emit failed (bus may not be initialized)")

    connections = _active_sse_connections.get(user_id, [])
    pushed = 0
    dead_queues: List[asyncio.Queue] = []

    for queue in connections:
        try:
            queue.put_nowait(event)
            pushed += 1
        except asyncio.QueueFull:
            logger.warning("[NOTIFICATIONS] Queue full, dropping notification")
        except Exception as e:
            logger.warning("[NOTIFICATIONS] Failed to push to queue: %s", e)
            dead_queues.append(queue)

    # Clean up dead connections
    for dq in dead_queues:
        try:
            connections.remove(dq)
        except ValueError:
            pass

    if pushed:
        logger.info("[NOTIFICATIONS] Pushed commitment notification to %d connections: %s",
                     pushed, commitment.intent)
    else:
        logger.debug("[NOTIFICATIONS] No active connections for user=%s", user_id)

    return pushed


def emit_commitment_notification_sync(commitment: Any, user_id: str = "default") -> int:
    """Synchronous wrapper for emit_commitment_notification.

    Used from heartbeat executor which may not be in an async context.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Schedule coroutine on the running loop
            future = asyncio.run_coroutine_threadsafe(
                emit_commitment_notification(commitment, user_id), loop
            )
            try:
                return future.result(timeout=2.0)
            except Exception:
                return 0
        else:
            return loop.run_until_complete(
                emit_commitment_notification(commitment, user_id)
            )
    except RuntimeError:
        # No event loop — create one
        try:
            return asyncio.run(emit_commitment_notification(commitment, user_id))
        except Exception:
            return 0


async def emit_generic_notification(
    event_type: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    user_id: str = "default",
) -> int:
    """Push a generic notification event to all SSE connections."""
    event = {
        "type": event_type,
        "content": content,
        "metadata": metadata or {},
    }

    # Also emit to EventBus for WebSocket clients
    try:
        from personal_agent.event_bus import get_event_bus
        await get_event_bus().emit("notification", {
            "subtype": event_type,
            "content": content,
            "metadata": metadata or {},
        })
    except Exception:
        logger.debug("[NOTIFICATIONS] EventBus emit failed (bus may not be initialized)")

    connections = _active_sse_connections.get(user_id, [])
    pushed = 0
    for queue in connections:
        try:
            queue.put_nowait(event)
            pushed += 1
        except Exception:
            pass

    if pushed:
        logger.info("[NOTIFICATIONS] Pushed %s event to %d connections", event_type, pushed)

    return pushed


def emit_generic_notification_sync(
    event_type: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    user_id: str = "default",
) -> int:
    """Synchronous wrapper for emit_generic_notification.

    Used from heartbeat executor which may not be in an async context.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                emit_generic_notification(event_type, content, metadata, user_id), loop
            )
            try:
                return future.result(timeout=2.0)
            except Exception:
                return 0
        else:
            return loop.run_until_complete(
                emit_generic_notification(event_type, content, metadata, user_id)
            )
    except RuntimeError:
        try:
            return asyncio.run(emit_generic_notification(event_type, content, metadata, user_id))
        except Exception:
            return 0

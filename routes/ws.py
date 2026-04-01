"""WebSocket endpoint for Aether.

Replaces both chat SSE streaming and notification SSE with a single
persistent bidirectional connection per client.

SSE endpoints stay alive during migration — this runs in parallel.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from starlette.websockets import WebSocketState

from personal_agent.event_bus import get_event_bus
from personal_agent.outbox import get_outbox

logger = logging.getLogger(__name__)

OUTBOX_DRAIN_INTERVAL = 2.0   # seconds between drain checks

router = APIRouter()


# ── ConnectionManager ─────────────────────────────────────────────────


class ConnectionManager:
    """Tracks active WebSocket clients and bridges EventBus → clients."""

    def __init__(self) -> None:
        # ws → metadata
        self._connections: Dict[WebSocket, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._bus_subscribed = False

    async def connect(self, ws: WebSocket, user_id: str = "default") -> None:
        await ws.accept()
        self._connections[ws] = {
            "user_id": user_id,
            "connected_at": time.time(),
            "subscriptions": {"notifications"},  # default channel
        }
        logger.info("[WS] Client connected (total=%d)", len(self._connections))

        # Lazy-subscribe to EventBus on first connection
        if not self._bus_subscribed:
            get_event_bus().subscribe(self._on_bus_event)
            self._bus_subscribed = True

    def disconnect(self, ws: WebSocket) -> None:
        meta = self._connections.pop(ws, None)
        if meta:
            logger.info("[WS] Client disconnected (total=%d)", len(self._connections))
        # Unsubscribe from bus when no clients left
        if not self._connections and self._bus_subscribed:
            get_event_bus().unsubscribe(self._on_bus_event)
            self._bus_subscribed = False

    async def _on_bus_event(self, event: dict) -> None:
        """Forward EventBus events to relevant WebSocket clients."""
        thread_id = event.get("thread_id")
        event_type = event.get("type", "")

        dead: List[WebSocket] = []

        for ws, meta in list(self._connections.items()):
            try:
                should_send = False

                # Notification events go to clients subscribed to notifications
                if event_type == "notification":
                    should_send = "notifications" in meta.get("subscriptions", set())

                # Thread-scoped events go to clients subscribed to that thread
                elif thread_id:
                    sub_key = f"thread:{thread_id}"
                    should_send = sub_key in meta.get("subscriptions", set())

                # Broadcast events (no thread) go to everyone
                else:
                    should_send = True

                if should_send:
                    await self._send_json(ws, event)

            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)

    async def send_to_thread(self, thread_id: str, event: dict) -> int:
        """Send an event to all clients subscribed to a thread."""
        sent = 0
        sub_key = f"thread:{thread_id}"
        dead: List[WebSocket] = []

        for ws, meta in list(self._connections.items()):
            if sub_key in meta.get("subscriptions", set()):
                try:
                    await self._send_json(ws, event)
                    sent += 1
                except Exception:
                    dead.append(ws)

        for ws in dead:
            self.disconnect(ws)
        return sent

    async def broadcast(self, event: dict) -> int:
        """Send an event to all connected clients."""
        sent = 0
        dead: List[WebSocket] = []

        for ws in list(self._connections):
            try:
                await self._send_json(ws, event)
                sent += 1
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)
        return sent

    def subscribe_to(self, ws: WebSocket, channels: List[str]) -> None:
        """Add channel subscriptions for a client."""
        meta = self._connections.get(ws)
        if meta:
            meta["subscriptions"].update(channels)

    async def _send_json(self, ws: WebSocket, data: dict) -> None:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.send_json(data)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# ── Singleton ─────────────────────────────────────────────────────────

_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager


# ── Keepalive ─────────────────────────────────────────────────────────

PING_INTERVAL = 25  # seconds (under Cloudflare's 30s timeout)


async def _ping_loop(ws: WebSocket) -> None:
    """Send periodic pings. Exits when connection closes."""
    try:
        while True:
            await asyncio.sleep(PING_INTERVAL)
            if ws.client_state != WebSocketState.CONNECTED:
                break
            await ws.send_json({"type": "pong", "ts": time.time()})
    except Exception:
        pass  # connection closed


async def _outbox_drain_loop(ws: WebSocket, thread_ids: "list[str]") -> None:
    """Drain the OutboxQueue for subscribed threads and push proactive_turn events.

    Runs as a background task alongside the WS connection.
    `thread_ids` is a mutable list — updated as the client subscribes to threads.
    Exits when the socket closes.
    """
    outbox = get_outbox()
    try:
        while True:
            await asyncio.sleep(OUTBOX_DRAIN_INTERVAL)
            if ws.client_state != WebSocketState.CONNECTED:
                break
            for tid in list(thread_ids):
                msgs = outbox.drain(tid)
                for msg in msgs:
                    try:
                        await ws.send_json({
                            "type": "proactive_turn",
                            "content": msg.content,
                            "trigger": msg.trigger,
                            "thread_id": msg.thread_id,
                            "metadata": msg.metadata,
                            "ts": msg.created_at,
                        })
                        logger.info(
                            "[WS] Proactive turn sent to thread %s (trigger=%s)",
                            tid, msg.trigger,
                        )
                    except Exception as _send_err:
                        logger.warning("[WS] Failed to send proactive turn: %s", _send_err)
    except Exception:
        pass  # connection closed


# ── WebSocket Endpoint ────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    token: Optional[str] = Query(None),
):
    """Main WebSocket endpoint.

    Connect: ws://host:port/ws?token=xxx
    Send:    {"type": "ping"} | {"type": "subscribe", "channels": [...]} | {"type": "chat", ...}
    Receive: pipeline events, notifications, pong
    """
    mgr = get_connection_manager()

    # TODO: validate token against auth system when auth is required
    # For now, accept all connections (single-user mode)
    await mgr.connect(ws)

    # Start keepalive
    ping_task = asyncio.create_task(_ping_loop(ws))

    # Start outbox drain loop — tracks which thread_ids this client subscribes to
    _subscribed_thread_ids: list[str] = []
    drain_task = asyncio.create_task(_outbox_drain_loop(ws, _subscribed_thread_ids))

    # Send welcome
    await ws.send_json({
        "type": "connected",
        "content": "Aether WebSocket active",
        "ts": time.time(),
    })

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "content": "Invalid JSON"})
                continue

            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await ws.send_json({"type": "pong", "ts": time.time()})

            elif msg_type == "subscribe":
                channels = msg.get("channels", [])
                mgr.subscribe_to(ws, channels)
                # Track thread subscriptions for the outbox drain loop
                for ch in channels:
                    if ch.startswith("thread:"):
                        tid = ch[len("thread:"):]
                        if tid not in _subscribed_thread_ids:
                            _subscribed_thread_ids.append(tid)
                await ws.send_json({
                    "type": "subscribed",
                    "channels": list(mgr._connections[ws]["subscriptions"]),
                })

            elif msg_type == "chat":
                # Chat messages will be handled in Step 2 (pipeline emission)
                # For now, acknowledge receipt
                thread_id = msg.get("thread_id", "")
                if thread_id:
                    mgr.subscribe_to(ws, [f"thread:{thread_id}"])
                await ws.send_json({
                    "type": "status",
                    "content": "chat handler not yet wired — use /api/chat/stream",
                    "thread_id": thread_id,
                })

            else:
                await ws.send_json({
                    "type": "error",
                    "content": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("[WS] Unexpected error")
    finally:
        ping_task.cancel()
        drain_task.cancel()
        mgr.disconnect(ws)

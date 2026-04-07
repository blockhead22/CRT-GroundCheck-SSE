"""WebSocket endpoint for Aether.

Provides a thread-aware connection registry plus proactive outbox delivery.
SSE endpoints stay alive during migration; this powers the persistent WS lane.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional, Set

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from personal_agent.event_bus import get_event_bus
from personal_agent.outbox import OutboxMessage, get_outbox
from personal_agent.stream_events import make_stream_event, WS_SERVER_EVENT_TYPES

logger = logging.getLogger(__name__)

router = APIRouter()

PING_INTERVAL = 25  # keep under common proxy idle timeouts


class ConnectionRegistry:
    """Tracks active sockets, subscriptions, and outbox delivery by thread."""

    def __init__(self) -> None:
        self._connections: Dict[WebSocket, Dict[str, Any]] = {}
        self._thread_index: DefaultDict[str, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._bus_subscribed = False
        self._outbox_subscribed = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._outbox = get_outbox()

    async def connect(self, ws: WebSocket, user_id: str = "default") -> None:
        await ws.accept()
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        async with self._lock:
            self._connections[ws] = {
                "user_id": user_id,
                "connected_at": time.time(),
                "subscriptions": {"notifications"},
            }
            total = len(self._connections)
            if not self._bus_subscribed:
                get_event_bus().subscribe(self._on_bus_event)
                self._bus_subscribed = True
            if not self._outbox_subscribed:
                self._outbox.subscribe(self._on_outbox_push)
                self._outbox_subscribed = True
        logger.info("[WS] Client connected (total=%d)", total)
        await self._send_json(
            ws,
            make_stream_event(
                "connected",
                "Aether WebSocket active",
                allow_ws=True,
                ts=time.time(),
            ),
        )

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            meta = self._connections.pop(ws, None)
            if meta:
                for channel in meta.get("subscriptions", set()):
                    if channel.startswith("thread:"):
                        thread_id = channel[len("thread:") :]
                        sockets = self._thread_index.get(thread_id)
                        if sockets is not None:
                            sockets.discard(ws)
                            if not sockets:
                                self._thread_index.pop(thread_id, None)
            total = len(self._connections)
            if not self._connections and self._bus_subscribed:
                get_event_bus().unsubscribe(self._on_bus_event)
                self._bus_subscribed = False
            if not self._connections and self._outbox_subscribed:
                self._outbox.unsubscribe(self._on_outbox_push)
                self._outbox_subscribed = False
        if meta:
            logger.info("[WS] Client disconnected (total=%d)", total)

    async def subscribe_to(self, ws: WebSocket, channels: List[str]) -> List[str]:
        unique_channels = [str(ch or "").strip() for ch in channels if str(ch or "").strip()]
        async with self._lock:
            meta = self._connections.get(ws)
            if not meta:
                return []
            subs = meta.setdefault("subscriptions", set())
            for channel in unique_channels:
                if channel not in subs:
                    subs.add(channel)
                    if channel.startswith("thread:"):
                        self._thread_index[channel[len("thread:") :]].add(ws)
            snapshot = sorted(subs)
        for channel in unique_channels:
            if channel.startswith("thread:"):
                await self.flush_outbox_for_thread(channel[len("thread:") :])
        return snapshot

    async def _on_bus_event(self, event: dict) -> None:
        thread_id = str(event.get("thread_id") or "").strip()
        event_type = str(event.get("type") or "").strip()
        if event_type == "notification":
            await self._send_to_notification_subscribers(event)
            return
        if thread_id:
            await self.send_to_thread(thread_id, event)
            return
        await self.broadcast(event)

    def _on_outbox_push(self, msg: OutboxMessage) -> None:
        if self._loop is None:
            return
        try:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.flush_outbox_for_thread(msg.thread_id))
            )
        except Exception:
            logger.debug("[WS] Could not schedule outbox flush for thread %s", msg.thread_id)

    async def flush_outbox_for_thread(self, thread_id: str) -> int:
        thread_id = str(thread_id or "").strip()
        if not thread_id:
            return 0
        async with self._lock:
            recipients = list(self._thread_index.get(thread_id, set()))
        if not recipients:
            return 0
        msgs = self._outbox.drain(thread_id)
        if not msgs:
            return 0
        delivered = 0
        for msg in msgs:
            event = make_stream_event(
                "proactive_turn",
                msg.content,
                allow_ws=True,
                trigger=msg.trigger,
                thread_id=msg.thread_id,
                metadata=msg.metadata,
                ts=msg.created_at,
            )
            sent = await self._send_to_sockets(recipients, event)
            delivered += sent
            logger.info(
                "[WS] Proactive turn flushed for thread %s to %d client(s) (trigger=%s)",
                thread_id,
                sent,
                msg.trigger,
            )
        return delivered

    async def send_to_thread(self, thread_id: str, event: dict) -> int:
        async with self._lock:
            recipients = list(self._thread_index.get(thread_id, set()))
        return await self._send_to_sockets(recipients, event)

    async def _send_to_notification_subscribers(self, event: dict) -> int:
        async with self._lock:
            recipients = [
                ws
                for ws, meta in self._connections.items()
                if "notifications" in meta.get("subscriptions", set())
            ]
        return await self._send_to_sockets(recipients, event)

    async def broadcast(self, event: dict) -> int:
        async with self._lock:
            recipients = list(self._connections)
        return await self._send_to_sockets(recipients, event)

    async def _send_to_sockets(self, sockets: List[WebSocket], event: dict) -> int:
        sent = 0
        dead: List[WebSocket] = []
        for ws in sockets:
            try:
                await self._send_json(ws, event)
                sent += 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)
        return sent

    async def _send_json(self, ws: WebSocket, data: dict) -> None:
        if ws.client_state != WebSocketState.CONNECTED:
            raise RuntimeError("socket not connected")
        await ws.send_json(data)

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    def thread_subscription_count(self, thread_id: str) -> int:
        return len(self._thread_index.get(thread_id, set()))


_registry: Optional[ConnectionRegistry] = None
_registry_lock = threading.Lock()


def get_connection_registry() -> ConnectionRegistry:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = ConnectionRegistry()
    return _registry


async def _ping_loop(ws: WebSocket) -> None:
    try:
        while True:
            await asyncio.sleep(PING_INTERVAL)
            if ws.client_state != WebSocketState.CONNECTED:
                break
            await ws.send_json(make_stream_event("pong", allow_ws=True, ts=time.time()))
    except Exception:
        pass


def _parse_sse_to_dict(sse_line: str) -> Optional[dict]:
    """Extract JSON dict from an SSE-formatted string like 'data: {...}\\n\\n'."""
    line = sse_line.strip()
    if line.startswith("data: "):
        try:
            return json.loads(line[6:])
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def _build_chat_request_and_deps(
    ws: WebSocket, data: dict, thread_id: str, message: str
):
    """Construct the ChatSendRequest and a minimal Request-like shim for the chat pipeline."""
    from .models import ChatSendRequest

    req = ChatSendRequest(
        thread_id=thread_id,
        message=message,
        generation_mode=data.get("generation_mode"),
        cloud_model_openai=data.get("cloud_model_openai"),
        cloud_model_claude=data.get("cloud_model_claude"),
        phase_mode=bool(data.get("phase_mode", False)),
    )
    return req


async def _run_ws_chat(
    ws: WebSocket, data: dict, thread_id: str, message: str
) -> None:
    """Bridge the synchronous SSE chat generator to the async WebSocket.

    Strategy:
    1. Build the same ChatSendRequest used by /api/chat/stream
    2. Run generate_stream() in a thread, pushing each SSE event to an
       asyncio.Queue as a parsed dict
    3. Drain the queue on the async side and send JSON frames to the client
    """
    req = _build_chat_request_and_deps(ws, data, thread_id, message)

    loop = asyncio.get_running_loop()
    event_queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()

    def _generator_thread():
        """Run in a background thread — the chat pipeline is synchronous."""
        try:
            # Import lazily to avoid circular imports
            from .chat import chat_stream as _chat_stream_endpoint
            from starlette.testclient import TestClient  # noqa: avoid

            # We need a real Request object with app.state.
            # Build a minimal ASGI scope to satisfy FastAPI's Request.
            app = ws.app
            scope = {
                "type": "http",
                "method": "POST",
                "path": "/api/chat/stream",
                "headers": [],
                "query_string": b"",
                "app": app,
            }
            from starlette.requests import Request as StarletteRequest
            fake_request = StarletteRequest(scope)

            from .chat_runtime import ChatStreamRuntime
            from personal_agent.event_bus import get_event_bus
            from personal_agent.db_utils import get_thread_session_db

            _session_db = get_thread_session_db()
            uid = None  # WS auth not yet wired; extend later

            runtime = ChatStreamRuntime(
                req=req,
                request=fake_request,
                authorization=None,
                uid=uid,
                safe_print=lambda s: logger.debug("[WS_CHAT] %s", s),
                session_db=_session_db,
                event_bus=get_event_bus(),
            )

            # Import the actual stream generator constructor.
            # The /api/chat/stream endpoint wraps a local generate_stream()
            # closure.  We replicate the same construction here by calling
            # the endpoint and iterating the StreamingResponse body.
            streaming_response = _chat_stream_endpoint(req, fake_request, authorization=None)

            # StreamingResponse.body_iterator is our sync generator
            for sse_chunk in streaming_response.body_iterator:
                parsed = _parse_sse_to_dict(sse_chunk)
                if parsed is not None:
                    loop.call_soon_threadsafe(event_queue.put_nowait, parsed)
        except Exception as exc:
            logger.exception("[WS_CHAT] Generator thread error")
            error_evt = make_stream_event("error", str(exc), allow_ws=True)
            loop.call_soon_threadsafe(event_queue.put_nowait, error_evt)
        finally:
            # Sentinel: signal that the generator is done
            loop.call_soon_threadsafe(event_queue.put_nowait, None)

    # Start the generator in a background thread
    thread = threading.Thread(target=_generator_thread, daemon=True, name=f"ws-chat-{thread_id[:8]}")
    thread.start()

    # Drain the queue and push events to the WebSocket
    try:
        while True:
            event = await event_queue.get()
            if event is None:
                break  # generator finished
            try:
                if ws.client_state != WebSocketState.CONNECTED:
                    break
                await ws.send_json(event)
            except Exception:
                logger.debug("[WS_CHAT] Failed to send event, client may have disconnected")
                break
    except Exception:
        logger.debug("[WS_CHAT] Queue drain interrupted")


@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    token: Optional[str] = Query(None),
):
    """Main WebSocket endpoint.

    Connect: ws://host:port/ws?token=xxx
    Send: {"type":"ping"} | {"type":"subscribe","channels":[...]} | {"type":"chat", ...}
    """

    del token  # auth validation still handled elsewhere / future work
    registry = get_connection_registry()
    await registry.connect(ws)
    ping_task = asyncio.create_task(_ping_loop(ws))

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json(make_stream_event("error", "Invalid JSON", allow_ws=True))
                continue

            msg_type = str(msg.get("type") or "").strip()

            if msg_type == "ping":
                await ws.send_json(make_stream_event("pong", allow_ws=True, ts=time.time()))
                continue

            if msg_type == "subscribe":
                channels = msg.get("channels", [])
                snapshot = await registry.subscribe_to(ws, channels)
                await ws.send_json(
                    make_stream_event(
                        "subscribed",
                        allow_ws=True,
                        channels=snapshot,
                    )
                )
                continue

            if msg_type == "chat":
                thread_id = str(msg.get("thread_id") or "default").strip()
                message = str(msg.get("message") or "").strip()
                if not message:
                    await ws.send_json(
                        make_stream_event("error", "Empty message", allow_ws=True)
                    )
                    continue
                if thread_id:
                    await registry.subscribe_to(ws, [f"thread:{thread_id}"])
                # Run the same chat pipeline used by SSE, bridging
                # the sync generator to async WS via a queue.
                await _run_ws_chat(ws, msg, thread_id, message)
                continue

            await ws.send_json(
                make_stream_event(
                    "error",
                    f"Unknown message type: {msg_type}",
                    allow_ws=True,
                )
            )

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("[WS] Unexpected error")
    finally:
        ping_task.cancel()
        await registry.disconnect(ws)

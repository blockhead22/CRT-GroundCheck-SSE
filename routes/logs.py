"""Live log streaming endpoint — SSE stream of Python logger output."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from typing import Any, Dict, List

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/logs", tags=["logs"])

# ── Ring-buffer log handler ──────────────────────────────────
_MAX_BUFFER = 500
_log_buffer: deque[Dict[str, Any]] = deque(maxlen=_MAX_BUFFER)
_subscribers: List[asyncio.Queue] = []


class _BroadcastHandler(logging.Handler):
    """Captures log records into a ring buffer and pushes to SSE subscribers."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "ts": record.created,
                "level": record.levelname,
                "logger": record.name,
                "msg": self.format(record),
            }
            _log_buffer.append(entry)
            for q in list(_subscribers):
                try:
                    q.put_nowait(entry)
                except asyncio.QueueFull:
                    pass  # slow consumer — drop
        except Exception:
            pass


_handler = _BroadcastHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))


def install_log_handler(level: int = logging.DEBUG) -> None:
    """Attach the broadcast handler to the root logger.
    Call this once at app startup (e.g. in crt_api.py or register_routes)."""
    root = logging.getLogger()
    if _handler not in root.handlers:
        _handler.setLevel(level)
        root.addHandler(_handler)


# ── Endpoints ────────────────────────────────────────────────

@router.get("/recent")
async def get_recent_logs(
    limit: int = Query(100, ge=1, le=500),
    level: str = Query("DEBUG"),
) -> List[Dict[str, Any]]:
    """Return the most recent log entries from the ring buffer."""
    min_level = getattr(logging, level.upper(), logging.DEBUG)
    entries = [e for e in _log_buffer if logging.getLevelName(e["level"]) >= min_level]
    return entries[-limit:]


@router.get("/stream")
async def stream_logs(
    level: str = Query("DEBUG"),
):
    """SSE endpoint — streams log entries in real time."""
    min_level = getattr(logging, level.upper(), logging.DEBUG)

    async def generate():
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        _subscribers.append(q)
        try:
            # Send recent history first (last 50)
            for entry in list(_log_buffer)[-50:]:
                if logging.getLevelName(entry["level"]) >= min_level:
                    yield f"data: {json.dumps(entry)}\n\n"

            # Then stream live
            while True:
                try:
                    entry = await asyncio.wait_for(q.get(), timeout=30)
                    if logging.getLevelName(entry["level"]) >= min_level:
                        yield f"data: {json.dumps(entry)}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive
                    yield f"data: {json.dumps({'type': 'keepalive', 'ts': time.time()})}\n\n"
        finally:
            _subscribers.remove(q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

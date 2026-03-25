"""
Desktop control API routes (Sprint 11).

POST /api/desktop/execute   — Start a desktop task
POST /api/desktop/stop      — Abort a running desktop task
GET  /api/desktop/screenshot — Take and return a screenshot
GET  /api/desktop/history    — Recent desktop action receipts
"""

from __future__ import annotations

import base64
import logging
import threading
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/desktop", tags=["desktop"])

# ── Request/response models ───────────────────────────────────────────────

class DesktopExecuteRequest(BaseModel):
    task: str = Field(..., description="Natural language desktop task, e.g. 'open Chrome'")
    thread_id: str = Field(default="desktop", description="Thread ID for receipt logging")
    max_steps: int = Field(default=25, ge=1, le=50, description="Max ReAct loop steps")


class DesktopExecuteResponse(BaseModel):
    success: bool
    steps_taken: int
    total_duration_ms: float
    task_summary: str = ""
    error: Optional[str] = None
    final_screenshot_b64: Optional[str] = None
    action_log: list = []


class DesktopScreenshotResponse(BaseModel):
    screenshot_b64: str
    width: int
    height: int
    active_window: str = ""


# ── Module state ──────────────────────────────────────────────────────────

_active_agent: Optional[Any] = None
_active_lock = threading.Lock()


# ── Routes ────────────────────────────────────────────────────────────────

@router.post("/execute", response_model=DesktopExecuteResponse)
async def execute_desktop_task(req: DesktopExecuteRequest):
    """Execute a desktop automation task via the vision ReAct loop."""
    global _active_agent

    # Check if desktop control is enabled
    try:
        from auth import get_user_settings
        _settings = get_user_settings(1)
        if _settings.get("desktop_control_enabled", "false") != "true":
            raise HTTPException(status_code=403, detail="Desktop control is disabled. Enable it in Settings.")
    except HTTPException:
        raise
    except Exception:
        pass  # if settings check fails, allow (fail-open for now)

    try:
        from personal_agent.desktop_control import DesktopController
        from personal_agent.desktop_vision import CookieVisionProvider
        from personal_agent.desktop_agent import DesktopAgent
        from personal_agent.action_receipts import create_receipt, log_receipt
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Missing dependency: {e}")

    with _active_lock:
        if _active_agent is not None:
            raise HTTPException(status_code=409, detail="A desktop task is already running")

    try:
        _settings = get_user_settings(1)
        _max_steps = min(req.max_steps, int(_settings.get("desktop_max_steps_per_task", "15")))
        _vision_provider = _settings.get("desktop_vision_provider", "cookie")
        _confirm_mode = _settings.get("desktop_require_confirmation", "dangerous_only")

        controller = DesktopController()
        if _vision_provider == "api_key":
            from personal_agent.desktop_vision import ClaudeVisionProvider
            from personal_agent.litellm_client import create_vision_client
            vision = ClaudeVisionProvider(create_vision_client())
        else:
            vision = CookieVisionProvider()
        agent = DesktopAgent(
            controller=controller,
            vision=vision,
            max_steps=_max_steps,
        )

        # Override confirmation behavior based on settings
        if _confirm_mode == "never":
            agent._needs_confirmation = lambda action, analysis: False
        elif _confirm_mode == "always":
            agent._needs_confirmation = lambda action, analysis: True

        with _active_lock:
            _active_agent = agent

        # Build memory context
        memory_context = ""
        try:
            from personal_agent.crt_memory import CRTMemory
            memory = CRTMemory()
            relevant = memory.retrieve(req.task, top_k=10)
            memory_lines = [
                f"- {m.text} (trust: {m.trust_score:.2f})"
                for m in relevant
                if m.trust_score >= 0.7
            ]
            memory_context = "\n".join(memory_lines)
        except Exception:
            pass

        result = agent.execute_task(
            task=req.task,
            memory_context=memory_context,
        )

        # Log receipts
        for entry in result.action_log:
            try:
                receipt = create_receipt(
                    tool_name="desktop_action",
                    action=f"desktop {entry.get('action_type', 'unknown')}: {entry.get('target', '')}",
                    target=entry.get("target", req.task),
                    result="success" if result.success else "partial",
                    reversible=False,
                    details=entry,
                )
                log_receipt(receipt, req.thread_id)
            except Exception:
                pass

        return DesktopExecuteResponse(
            success=result.success,
            steps_taken=result.steps_taken,
            total_duration_ms=result.total_duration_ms,
            task_summary=result.task_summary,
            error=result.error,
            final_screenshot_b64=result.final_screenshot_b64,
            action_log=result.action_log,
        )

    finally:
        with _active_lock:
            _active_agent = None


@router.post("/stop")
async def stop_desktop_task():
    """Abort the currently running desktop task."""
    global _active_agent
    with _active_lock:
        if _active_agent is None:
            raise HTTPException(status_code=404, detail="No desktop task is running")
        _active_agent.stop()
    return {"status": "stop_requested"}


@router.get("/screenshot", response_model=DesktopScreenshotResponse)
async def take_screenshot():
    """Take a screenshot and return it as base64."""
    try:
        from personal_agent.desktop_control import DesktopController
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Missing dependency: {e}")

    controller = DesktopController()
    img = controller.take_screenshot()
    b64 = controller.screenshot_to_base64(img)

    active_win = controller.get_active_window()

    return DesktopScreenshotResponse(
        screenshot_b64=b64,
        width=img.width,
        height=img.height,
        active_window=active_win.get("title", ""),
    )


@router.get("/history")
async def get_desktop_history(thread_id: str = "desktop", limit: int = 20):
    """Get recent desktop action receipts."""
    try:
        from personal_agent.action_receipts import get_receipts
    except ImportError:
        return {"receipts": []}

    receipts = get_receipts(thread_id, limit=limit)
    # Filter to desktop_action receipts only
    desktop_receipts = [r for r in receipts if r.get("tool_name") == "desktop_action"]
    return {"receipts": desktop_receipts}

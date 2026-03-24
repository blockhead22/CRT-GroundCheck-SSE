"""
Desktop ReAct agent — the core screenshot → think → act → verify loop.

Standalone and testable without the full CRT pipeline.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from personal_agent.desktop_control import DesktopController
from personal_agent.desktop_vision import (
    ActionType,
    DesktopAction,
    VisionAnalysis,
    VisionProvider,
)

logger = logging.getLogger(__name__)


@dataclass
class DesktopTaskResult:
    success: bool
    steps_taken: int
    total_duration_ms: float
    final_screenshot_b64: Optional[str] = None
    action_log: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    task_summary: str = ""


# ── Safety lists ──────────────────────────────────────────────────────────

# Apps/windows that should NEVER be interacted with
BLOCKED_APPS = [
    "password", "keychain", "1password", "lastpass", "bitwarden", "keepass",
    "bank", "banking", "chase", "wells fargo", "paypal", "venmo",
    "admin", "administrator", "registry editor", "regedit",
    "task manager",
    # Windows-specific security
    "credential manager", "windows security", "device manager",
    "disk management", "services", "group policy",
    "certificate", "firewall",
    "powershell_ise",  # admin scripting tool
]

# Actions that require user confirmation before executing
CONFIRM_KEYWORDS = [
    "send", "submit", "delete", "remove", "purchase", "buy", "pay",
    "publish", "post", "confirm", "sign out", "log out", "uninstall",
    "format", "erase", "reset", "shutdown", "restart",
]

# Actions that should NEVER be performed (hard block, not just confirm)
HARD_BLOCKED_TARGETS = [
    "password", "credit card", "ssn", "social security",
    "bank account", "routing number", "cvv",
]

# ── Rate limiting ─────────────────────────────────────────────────────────

MAX_ACTIONS_PER_MINUTE = 20
MAX_CLICKS_PER_MINUTE = 10
MAX_KEYSTROKES_PER_MINUTE = 200


class _RateLimiter:
    """Simple sliding-window rate limiter."""

    def __init__(self, max_per_minute: int) -> None:
        self.max_per_minute = max_per_minute
        self._timestamps: deque[float] = deque()

    def allow(self) -> bool:
        now = time.time()
        cutoff = now - 60.0
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        if len(self._timestamps) >= self.max_per_minute:
            return False
        self._timestamps.append(now)
        return True


# ── Restricted screen regions ─────────────────────────────────────────────

RESTRICTED_REGIONS: List[Dict[str, Any]] = [
    # System tray area (notifications, clock, etc.) — bottom-right
    {"x_min": 1800, "y_min": 1050, "x_max": 1920, "y_max": 1080, "reason": "system tray"},
]


class DesktopAgent:
    """
    ReAct loop: screenshot → vision analysis → execute action → repeat.

    Standalone — can run without the full CRT pipeline.
    """

    def __init__(
        self,
        controller: DesktopController,
        vision: VisionProvider,
        max_steps: int = 25,
        step_timeout: float = 30.0,
    ) -> None:
        self.controller = controller
        self.vision = vision
        self.max_steps = max_steps
        self.step_timeout = step_timeout
        self._running = False

        # Rate limiters
        self._action_limiter = _RateLimiter(MAX_ACTIONS_PER_MINUTE)
        self._click_limiter = _RateLimiter(MAX_CLICKS_PER_MINUTE)
        self._keystroke_limiter = _RateLimiter(MAX_KEYSTROKES_PER_MINUTE)

    def execute_task(
        self,
        task: str,
        memory_context: str = "",
        on_checkpoint: Optional[Callable[[DesktopAction, str], bool]] = None,
        on_step: Optional[Callable[[int, DesktopAction, str, VisionAnalysis], None]] = None,
    ) -> DesktopTaskResult:
        """
        Execute a desktop task via the ReAct loop.

        Args:
            task: natural language task description
            memory_context: verified facts from CRT memory
            on_checkpoint: callback(action, screenshot_b64) -> bool for irreversible actions.
                          Return True to proceed, False to abort. If None, all actions execute.
            on_step: callback(step_num, action, screenshot_b64, analysis) for logging/UI
        """
        self._running = True
        action_log: List[Dict[str, Any]] = []
        start_time = time.time()

        logger.info("[DESKTOP] Starting task: %s", task)

        for step in range(self.max_steps):
            if not self._running:
                return DesktopTaskResult(
                    success=False,
                    steps_taken=step,
                    total_duration_ms=(time.time() - start_time) * 1000,
                    action_log=action_log,
                    error="Cancelled by user",
                )

            try:
                # 1. Rate limit check
                if not self._action_limiter.allow():
                    logger.warning("[DESKTOP] Rate limit hit — too many actions/min")
                    return DesktopTaskResult(
                        success=False,
                        steps_taken=step,
                        total_duration_ms=(time.time() - start_time) * 1000,
                        action_log=action_log,
                        error="Rate limit: too many actions per minute",
                    )

                # 2. Screenshot — capture at full res, resize for vision
                screenshot = self.controller.take_screenshot()
                screen_w, screen_h = screenshot.width, screenshot.height
                screenshot_b64 = self.controller.screenshot_to_base64(screenshot)
                # Vision model sees a 1280px-wide image; compute scale factor
                # to map its coordinates back to actual screen pixels
                vision_width = min(screen_w, 1280)
                scale = screen_w / vision_width

                # 3. Check for blocked apps
                active_window = self.controller.get_active_window()
                if self._is_blocked_app(active_window.get("title", "")):
                    logger.warning(
                        "[DESKTOP] Blocked app detected: %s",
                        active_window["title"],
                    )
                    return DesktopTaskResult(
                        success=False,
                        steps_taken=step,
                        total_duration_ms=(time.time() - start_time) * 1000,
                        action_log=action_log,
                        error=f"Blocked: cannot interact with '{active_window['title']}' (security restriction)",
                    )

                # 4. Vision analysis
                analysis = self.vision.analyze_screenshot(
                    screenshot_b64=screenshot_b64,
                    task=task,
                    action_history=action_log,
                    memory_context=memory_context,
                )

                if not analysis.actions:
                    logger.warning("[DESKTOP] Vision returned no actions")
                    continue

                action = analysis.actions[0]

                # 5. Terminal states
                if action.action_type == ActionType.DONE:
                    logger.info(
                        "[DESKTOP] Task complete after %d steps: %s",
                        step + 1,
                        action.reasoning,
                    )
                    final_ss = self.controller.screenshot_to_base64(
                        self.controller.take_screenshot()
                    )
                    return DesktopTaskResult(
                        success=True,
                        steps_taken=step + 1,
                        total_duration_ms=(time.time() - start_time) * 1000,
                        final_screenshot_b64=final_ss,
                        action_log=action_log,
                        task_summary=action.reasoning,
                    )

                if action.action_type == ActionType.FAILED:
                    logger.warning("[DESKTOP] Task failed: %s", action.reasoning)
                    return DesktopTaskResult(
                        success=False,
                        steps_taken=step + 1,
                        total_duration_ms=(time.time() - start_time) * 1000,
                        action_log=action_log,
                        error=action.reasoning,
                    )

                if action.action_type == ActionType.NEED_INFO:
                    logger.info(
                        "[DESKTOP] Needs clarification: %s", action.reasoning
                    )
                    return DesktopTaskResult(
                        success=False,
                        steps_taken=step + 1,
                        total_duration_ms=(time.time() - start_time) * 1000,
                        action_log=action_log,
                        error=f"Need clarification: {action.reasoning}",
                    )

                # 6. Hard-blocked target check
                if self._is_hard_blocked_target(action):
                    logger.warning(
                        "[DESKTOP] Hard-blocked target: %s",
                        action.target_description,
                    )
                    return DesktopTaskResult(
                        success=False,
                        steps_taken=step + 1,
                        total_duration_ms=(time.time() - start_time) * 1000,
                        action_log=action_log,
                        error=f"Security block: cannot interact with '{action.target_description}'",
                    )

                # 7. Click/keystroke rate limiting
                if action.action_type in (
                    ActionType.CLICK,
                    ActionType.DOUBLE_CLICK,
                    ActionType.RIGHT_CLICK,
                ):
                    if not self._click_limiter.allow():
                        logger.warning("[DESKTOP] Click rate limit hit")
                        action_log.append({
                            "step": step + 1,
                            "action_type": "rate_limited",
                            "reasoning": "Too many clicks per minute",
                            "ts": time.time(),
                        })
                        time.sleep(2.0)
                        continue

                if action.action_type == ActionType.TYPE and action.text:
                    for _ in action.text:
                        if not self._keystroke_limiter.allow():
                            logger.warning("[DESKTOP] Keystroke rate limit hit")
                            break

                # 9. Safety check — irreversible actions need confirmation
                needs_confirm = self._needs_confirmation(action, analysis)
                if needs_confirm and on_checkpoint:
                    approved = on_checkpoint(action, screenshot_b64)
                    if not approved:
                        logger.info(
                            "[DESKTOP] User rejected action: %s",
                            action.target_description,
                        )
                        return DesktopTaskResult(
                            success=False,
                            steps_taken=step + 1,
                            total_duration_ms=(time.time() - start_time) * 1000,
                            action_log=action_log,
                            error="User rejected proposed action",
                        )

                # 10. Scale coordinates from vision-space to screen-space
                if scale != 1.0:
                    if action.x is not None:
                        action.x = int(action.x * scale)
                    if action.y is not None:
                        action.y = int(action.y * scale)
                    if action.end_x is not None:
                        action.end_x = int(action.end_x * scale)
                    if action.end_y is not None:
                        action.end_y = int(action.end_y * scale)
                    logger.info(
                        "[DESKTOP] Scaled coords by %.2fx: (%s, %s)",
                        scale, action.x, action.y,
                    )

                # 11. Restricted region check (after scaling to screen coords)
                if self._in_restricted_region(action):
                    logger.warning(
                        "[DESKTOP] Action in restricted region: (%s, %s)",
                        action.x, action.y,
                    )
                    action_log.append({
                        "step": step + 1,
                        "action_type": "skipped",
                        "reasoning": "Coordinates in restricted screen region",
                        "ts": time.time(),
                    })
                    continue

                # 12. Execute the action
                result = self._execute_action(action)

                # 11. Log
                log_entry = {
                    "step": step + 1,
                    "action_type": action.action_type.value,
                    "target": action.target_description,
                    "reasoning": action.reasoning,
                    "confidence": action.confidence,
                    "screen_state": analysis.screen_description,
                    "task_progress": analysis.task_progress,
                    "ts": time.time(),
                    **result,
                }
                action_log.append(log_entry)

                if on_step:
                    on_step(step + 1, action, screenshot_b64, analysis)

                # 12. Pause to let UI update before next screenshot
                if action.action_type == ActionType.WAIT:
                    time.sleep(action.wait_seconds or 1.0)
                else:
                    time.sleep(0.5)

            except Exception as e:
                logger.error("[DESKTOP] Step %d error: %s", step + 1, e)
                action_log.append({
                    "step": step + 1,
                    "error": str(e),
                    "ts": time.time(),
                })
                continue

        # Hit max steps
        return DesktopTaskResult(
            success=False,
            steps_taken=self.max_steps,
            total_duration_ms=(time.time() - start_time) * 1000,
            action_log=action_log,
            error=f"Hit max steps ({self.max_steps}) without completing task",
        )

    def stop(self) -> None:
        """Abort the current task."""
        self._running = False

    # ── Action dispatch ───────────────────────────────────────────────────

    def _execute_action(self, action: DesktopAction) -> Dict[str, Any]:
        """Dispatch a DesktopAction to the controller."""
        match action.action_type:
            case ActionType.CLICK:
                return self.controller.click(action.x, action.y)
            case ActionType.DOUBLE_CLICK:
                return self.controller.double_click(action.x, action.y)
            case ActionType.RIGHT_CLICK:
                return self.controller.right_click(action.x, action.y)
            case ActionType.TYPE:
                return self.controller.type_text(action.text or "")
            case ActionType.PRESS_KEY:
                return self.controller.press_key(action.key or "enter")
            case ActionType.HOTKEY:
                return self.controller.hotkey(*(action.keys or []))
            case ActionType.SCROLL:
                return self.controller.scroll(
                    action.scroll_amount or -3, action.x, action.y
                )
            case ActionType.DRAG:
                return self.controller.drag(
                    action.x, action.y, action.end_x, action.end_y
                )
            case ActionType.WAIT:
                time.sleep(action.wait_seconds or 1.0)
                return {"type": "wait", "seconds": action.wait_seconds}
            case _:
                return {
                    "type": "unknown",
                    "error": f"Unknown action type: {action.action_type}",
                }

    # ── Safety checks ─────────────────────────────────────────────────────

    def _is_blocked_app(self, window_title: str) -> bool:
        """Check if the active window is a blocked app."""
        title_lower = window_title.lower()
        return any(blocked in title_lower for blocked in BLOCKED_APPS)

    def _is_hard_blocked_target(self, action: DesktopAction) -> bool:
        """Check if the action targets a hard-blocked element (passwords, etc.)."""
        target = (action.target_description or "").lower()
        return any(blocked in target for blocked in HARD_BLOCKED_TARGETS)

    def _in_restricted_region(self, action: DesktopAction) -> bool:
        """Check if action coordinates fall in a restricted screen region."""
        if action.x is None or action.y is None:
            return False
        for region in RESTRICTED_REGIONS:
            if (
                region["x_min"] <= action.x <= region["x_max"]
                and region["y_min"] <= action.y <= region["y_max"]
            ):
                return True
        return False

    def _needs_confirmation(
        self, action: DesktopAction, analysis: VisionAnalysis
    ) -> bool:
        """Check if this action should require user confirmation.

        Only gates genuinely dangerous actions — send, delete, purchase, etc.
        Safe actions (open app, click tab, scroll, type in search) run freely.
        """
        target = (action.target_description or "").lower()

        # Clicks on dangerous targets (send, delete, purchase, etc.)
        if action.action_type in (
            ActionType.CLICK,
            ActionType.DOUBLE_CLICK,
        ):
            if any(word in target for word in CONFIRM_KEYWORDS):
                return True

        # Hotkeys that could be destructive
        if action.action_type == ActionType.HOTKEY:
            keys = [k.lower() for k in (action.keys or [])]
            if "delete" in keys or ("ctrl" in keys and "w" in keys):
                return True

        return False

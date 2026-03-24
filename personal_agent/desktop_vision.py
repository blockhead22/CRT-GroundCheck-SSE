"""
Desktop vision analysis — screenshot → structured action proposals.

Sends screenshots to a vision model, parses structured JSON responses into
DesktopAction objects. Abstracted behind VisionProvider interface so you can
swap cloud ↔ local later.
"""

from __future__ import annotations

import io
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ActionType(Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE = "type"
    HOTKEY = "hotkey"
    PRESS_KEY = "press_key"
    SCROLL = "scroll"
    DRAG = "drag"
    WAIT = "wait"
    DONE = "done"           # task complete
    FAILED = "failed"       # can't complete
    NEED_INFO = "need_info" # need user clarification


@dataclass
class DesktopAction:
    action_type: ActionType
    x: Optional[int] = None
    y: Optional[int] = None
    text: Optional[str] = None          # for TYPE actions
    key: Optional[str] = None           # for PRESS_KEY
    keys: Optional[List[str]] = None    # for HOTKEY
    scroll_amount: Optional[int] = None
    end_x: Optional[int] = None         # for DRAG
    end_y: Optional[int] = None
    wait_seconds: Optional[float] = None
    reasoning: str = ""                 # why the model chose this action
    confidence: float = 0.0             # 0-1 how confident
    target_description: str = ""        # what element is being targeted


@dataclass
class VisionAnalysis:
    actions: List[DesktopAction]           # proposed actions (usually 1)
    screen_description: str                # brief description of what's on screen
    task_progress: str                     # starting, in_progress, almost_done, done, stuck
    observations: List[str] = field(default_factory=list)


class VisionProvider(ABC):
    """Abstract interface for desktop vision analysis."""

    @abstractmethod
    def analyze_screenshot(
        self,
        screenshot_b64: str,
        task: str,
        action_history: List[Dict[str, Any]],
        memory_context: str = "",
    ) -> VisionAnalysis:
        """Analyze a screenshot and propose next action(s) for the given task."""
        ...


class ClaudeVisionProvider(VisionProvider):
    """Uses Claude's vision capability for desktop understanding."""

    def __init__(self, cloud_client) -> None:
        """
        Args:
            cloud_client: An AnthropicClient instance with chat_with_image() method.
        """
        self.client = cloud_client

    def analyze_screenshot(
        self,
        screenshot_b64: str,
        task: str,
        action_history: List[Dict[str, Any]],
        memory_context: str = "",
    ) -> VisionAnalysis:
        history_text = self._format_action_history(action_history[-5:])

        prompt = f"""You are controlling a Windows 11 desktop to complete a task for the user.

TASK: {task}

PREVIOUS ACTIONS TAKEN:
{history_text if history_text else "None yet — this is the first step."}

{f"KNOWN CONTEXT (verified facts about this user's system):{chr(10)}{memory_context}" if memory_context else ""}

Look at the screenshot and determine the NEXT SINGLE ACTION to take.

Respond in this exact JSON format:
{{
  "screen_description": "brief description of what's visible",
  "task_progress": "starting|in_progress|almost_done|done|stuck",
  "observations": ["what you notice that's relevant"],
  "action": {{
    "type": "click|double_click|right_click|type|hotkey|press_key|scroll|drag|wait|done|failed|need_info",
    "x": null,
    "y": null,
    "text": null,
    "key": null,
    "keys": null,
    "scroll_amount": null,
    "end_x": null,
    "end_y": null,
    "wait_seconds": null,
    "reasoning": "why this action",
    "confidence": 0.0,
    "target_description": "what element you're targeting"
  }}
}}

RULES:
- Propose ONE action at a time. After executing, you'll see a new screenshot.
- Coordinates are in pixels from top-left of the screen.
- Be precise with click coordinates — aim for the CENTER of the target element.
- If the task is complete, use action type "done".
- If you're stuck or unsure, use "need_info" with reasoning explaining what you need.
- If something went wrong, use "failed" with reasoning.
- Confidence should reflect how sure you are the action is correct (0.0-1.0).
- NEVER interact with password fields, banking apps, or admin consoles.
- ONLY output valid JSON. No markdown wrapping, no extra text."""

        t0 = time.time()
        response = self.client.chat_with_image(
            prompt=prompt,
            image_b64=screenshot_b64,
            image_media_type="image/jpeg",
            max_tokens=1000,
            temperature=0.1,
        )
        elapsed_ms = (time.time() - t0) * 1000
        logger.info("[VISION] Claude response in %.0fms", elapsed_ms)

        return self._parse_response(response)

    def _parse_response(self, response_text: str) -> VisionAnalysis:
        """Parse the JSON response from Claude into a VisionAnalysis."""
        text = response_text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning("[VISION] Failed to parse JSON: %s\nResponse: %s", e, text[:500])
            return VisionAnalysis(
                actions=[DesktopAction(
                    action_type=ActionType.FAILED,
                    reasoning=f"Failed to parse vision model response: {e}",
                    confidence=0.0,
                )],
                screen_description="parse error",
                task_progress="stuck",
                observations=[f"JSON parse error: {e}"],
            )

        action_data = data.get("action", {})

        try:
            action_type = ActionType(action_data.get("type", "failed"))
        except ValueError:
            action_type = ActionType.FAILED

        action = DesktopAction(
            action_type=action_type,
            x=action_data.get("x"),
            y=action_data.get("y"),
            text=action_data.get("text"),
            key=action_data.get("key"),
            keys=action_data.get("keys"),
            scroll_amount=action_data.get("scroll_amount"),
            end_x=action_data.get("end_x"),
            end_y=action_data.get("end_y"),
            wait_seconds=action_data.get("wait_seconds"),
            reasoning=action_data.get("reasoning", ""),
            confidence=action_data.get("confidence", 0.5),
            target_description=action_data.get("target_description", ""),
        )

        return VisionAnalysis(
            actions=[action],
            screen_description=data.get("screen_description", ""),
            task_progress=data.get("task_progress", "in_progress"),
            observations=data.get("observations", []),
        )

    @staticmethod
    def _format_action_history(history: List[Dict[str, Any]]) -> str:
        """Format recent actions for the prompt."""
        lines = []
        for i, h in enumerate(history):
            action_type = h.get("action_type", h.get("type", "unknown"))
            target = h.get("target", h.get("target_description", "unknown element"))
            if action_type in ("click", "double_click", "right_click"):
                x = h.get("x", "?")
                y = h.get("y", "?")
                lines.append(f"  {i+1}. {action_type} at ({x}, {y}) — {target}")
            elif action_type == "type_text" or action_type == "type":
                text = h.get("text", "")[:50]
                lines.append(f'  {i+1}. Typed: "{text}"')
            elif action_type in ("key_press", "press_key"):
                lines.append(f"  {i+1}. Pressed key: {h.get('key', '?')}")
            elif action_type == "hotkey":
                keys = h.get("keys", [])
                lines.append(f"  {i+1}. Hotkey: {'+'.join(keys)}")
            elif action_type == "scroll":
                direction = "up" if h.get("amount", h.get("scroll_amount", 0)) > 0 else "down"
                lines.append(f"  {i+1}. Scrolled {direction}")
            else:
                lines.append(f"  {i+1}. {action_type}")
        return "\n".join(lines)


class CookieVisionProvider(VisionProvider):
    """Uses Claude vision via cookie session (no API key needed).

    Uploads screenshots to claude.ai, sends them in chat completion.
    Requires a valid session in tests/cloud_providers/.claude_session.json.
    """

    def __init__(self, cookie_provider=None) -> None:
        if cookie_provider is None:
            from tests.cloud_providers.providers import CookieProvider
            cookie_provider = CookieProvider()
        self.cookie = cookie_provider

    def analyze_screenshot(
        self,
        screenshot_b64: str,
        task: str,
        action_history: List[Dict[str, Any]],
        memory_context: str = "",
    ) -> VisionAnalysis:
        history_text = ClaudeVisionProvider._format_action_history(action_history[-5:])

        prompt = f"""You are controlling a Windows 11 desktop to complete a task for the user.

TASK: {task}

PREVIOUS ACTIONS TAKEN:
{history_text if history_text else "None yet — this is the first step."}

{f"KNOWN CONTEXT (verified facts about this user's system):{chr(10)}{memory_context}" if memory_context else ""}

Look at the screenshot and determine the NEXT SINGLE ACTION to take.

Respond in this exact JSON format:
{{
  "screen_description": "brief description of what's visible",
  "task_progress": "starting|in_progress|almost_done|done|stuck",
  "observations": ["what you notice that's relevant"],
  "action": {{
    "type": "click|double_click|right_click|type|hotkey|press_key|scroll|drag|wait|done|failed|need_info",
    "x": null,
    "y": null,
    "text": null,
    "key": null,
    "keys": null,
    "scroll_amount": null,
    "end_x": null,
    "end_y": null,
    "wait_seconds": null,
    "reasoning": "why this action",
    "confidence": 0.0,
    "target_description": "what element you're targeting"
  }}
}}

RULES:
- Propose ONE action at a time. After executing, you'll see a new screenshot.
- Coordinates are in pixels from top-left of the screen.
- Be precise with click coordinates — aim for the CENTER of the target element.
- If the task is complete, use action type "done".
- If you're stuck or unsure, use "need_info" with reasoning explaining what you need.
- If something went wrong, use "failed" with reasoning.
- Confidence should reflect how sure you are the action is correct (0.0-1.0).
- NEVER interact with password fields, banking apps, or admin consoles.
- ONLY output valid JSON. No markdown wrapping, no extra text."""

        # Ensure image is compressed for upload (cookie upload sends raw bytes)
        # The screenshot_b64 from DesktopController is already resized to 1280px,
        # but if it came from elsewhere, re-compress it
        import base64 as _b64
        try:
            from PIL import Image as _Image
            raw_bytes = _b64.b64decode(screenshot_b64)
            _img = _Image.open(io.BytesIO(raw_bytes))
            if _img.width > 1280:
                ratio = 1280 / _img.width
                _img = _img.resize((1280, int(_img.height * ratio)), _Image.LANCZOS)
            _buf = io.BytesIO()
            _img.save(_buf, format="JPEG", quality=70)
            screenshot_b64 = _b64.b64encode(_buf.getvalue()).decode()
        except Exception:
            pass  # use original if compression fails

        t0 = time.time()
        result = self.cookie.complete_with_image(
            system="",
            prompt=prompt,
            image_b64=screenshot_b64,
            image_media_type="image/jpeg",
            max_tokens=1000,
        )
        elapsed_ms = (time.time() - t0) * 1000
        logger.info("[VISION-COOKIE] Response in %.0fms", elapsed_ms)

        if result.error:
            logger.warning("[VISION-COOKIE] Error: %s", result.error)
            return VisionAnalysis(
                actions=[DesktopAction(
                    action_type=ActionType.FAILED,
                    reasoning=f"Vision API error: {result.error}",
                    confidence=0.0,
                )],
                screen_description="error",
                task_progress="stuck",
                observations=[f"Cookie vision error: {result.error}"],
            )

        return self._parse_response(result.content)

    @staticmethod
    def _parse_response(response_text: str) -> VisionAnalysis:
        """Reuse ClaudeVisionProvider's parsing logic."""
        class _DummyClient:
            def chat_with_image(self, **kw):
                return ""
        provider = ClaudeVisionProvider(_DummyClient())
        return provider._parse_response(response_text)


class LocalVisionProvider(VisionProvider):
    """
    Future: local vision model (moondream2, Qwen2-VL, etc.)
    Stub for now — falls back to cloud.
    """

    def __init__(self, model_name: str = "moondream2") -> None:
        self.model_name = model_name
        self._loaded = False

    def analyze_screenshot(
        self,
        screenshot_b64: str,
        task: str,
        action_history: List[Dict[str, Any]],
        memory_context: str = "",
    ) -> VisionAnalysis:
        raise NotImplementedError(
            "Local vision not yet implemented — use ClaudeVisionProvider"
        )

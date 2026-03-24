"""
Desktop control module — low-level automation primitives.

Pure automation library with ZERO knowledge of the agent system.
Uses pyautogui for mouse/keyboard, mss for fast screenshots, Pillow for image processing.
"""

from __future__ import annotations

import base64
import io
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False
    pyautogui = None  # type: ignore

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False
    mss = None  # type: ignore

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None  # type: ignore

# Safety: fail-safe — move mouse to corner to abort
if HAS_PYAUTOGUI:
    pyautogui.FAILSAFE = True
    # Safety: add small delay between actions to allow human intervention
    pyautogui.PAUSE = 0.3


class DesktopController:
    """Low-level desktop automation primitives."""

    def __init__(self) -> None:
        if not HAS_PYAUTOGUI:
            raise ImportError("pyautogui not installed. Run: pip install pyautogui")
        if not HAS_MSS:
            raise ImportError("mss not installed. Run: pip install mss")
        if not HAS_PIL:
            raise ImportError("Pillow not installed. Run: pip install Pillow")

        self.sct = mss.mss()
        self._action_history: List[Dict[str, Any]] = []

    # ── Screenshot ────────────────────────────────────────────────────────

    def take_screenshot(self, monitor: int = 0) -> Image.Image:
        """Capture full screen. monitor=0 means all monitors combined."""
        raw = self.sct.grab(self.sct.monitors[monitor])
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    def screenshot_to_base64(
        self, img: Image.Image, max_width: int = 1280, quality: int = 75
    ) -> str:
        """Resize and compress screenshot for vision model input. Returns base64 JPEG."""
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def screenshot_region(
        self, x: int, y: int, width: int, height: int
    ) -> Image.Image:
        """Capture a specific screen region."""
        region = {"left": x, "top": y, "width": width, "height": height}
        raw = self.sct.grab(region)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    # ── Mouse ─────────────────────────────────────────────────────────────

    def get_cursor_position(self) -> Tuple[int, int]:
        """Get current cursor position as (x, y)."""
        return pyautogui.position()

    def move_mouse(self, x: int, y: int, duration: float = 0.3) -> Dict[str, Any]:
        """Move cursor to coordinates. Returns action record."""
        old_x, old_y = self.get_cursor_position()
        pyautogui.moveTo(x, y, duration=duration)
        action = {
            "type": "move",
            "from": (old_x, old_y),
            "to": (x, y),
            "ts": time.time(),
        }
        self._action_history.append(action)
        return action

    def click(
        self, x: int, y: int, button: str = "left", clicks: int = 1
    ) -> Dict[str, Any]:
        """Click at coordinates. button: 'left', 'right', 'middle'."""
        pyautogui.click(x, y, button=button, clicks=clicks)
        action = {
            "type": "click",
            "x": x,
            "y": y,
            "button": button,
            "clicks": clicks,
            "ts": time.time(),
        }
        self._action_history.append(action)
        return action

    def double_click(self, x: int, y: int) -> Dict[str, Any]:
        """Double-click at coordinates."""
        return self.click(x, y, clicks=2)

    def right_click(self, x: int, y: int) -> Dict[str, Any]:
        """Right-click at coordinates."""
        return self.click(x, y, button="right")

    def drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = 0.5,
    ) -> Dict[str, Any]:
        """Drag from start to end coordinates."""
        pyautogui.moveTo(start_x, start_y, duration=0.1)
        pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration)
        action = {
            "type": "drag",
            "from": (start_x, start_y),
            "to": (end_x, end_y),
            "ts": time.time(),
        }
        self._action_history.append(action)
        return action

    # ── Keyboard ──────────────────────────────────────────────────────────

    def type_text(self, text: str, interval: float = 0.03) -> Dict[str, Any]:
        """Type text character by character."""
        if text.isascii():
            pyautogui.typewrite(text, interval=interval)
        else:
            # pyautogui.typewrite doesn't support unicode; use write() instead
            pyautogui.write(text)
        action = {"type": "type_text", "text": text, "ts": time.time()}
        self._action_history.append(action)
        return action

    def press_key(self, key: str) -> Dict[str, Any]:
        """Press a single key. Supports: enter, tab, escape, backspace, delete, etc."""
        pyautogui.press(key)
        action = {"type": "key_press", "key": key, "ts": time.time()}
        self._action_history.append(action)
        return action

    def hotkey(self, *keys: str) -> Dict[str, Any]:
        """Press key combination. E.g. hotkey('ctrl', 'c') for copy."""
        pyautogui.hotkey(*keys)
        action = {"type": "hotkey", "keys": list(keys), "ts": time.time()}
        self._action_history.append(action)
        return action

    # ── Scroll ────────────────────────────────────────────────────────────

    def scroll(
        self, amount: int, x: Optional[int] = None, y: Optional[int] = None
    ) -> Dict[str, Any]:
        """Scroll wheel. Positive = up, negative = down."""
        pyautogui.scroll(amount, x=x, y=y)
        action = {
            "type": "scroll",
            "amount": amount,
            "x": x,
            "y": y,
            "ts": time.time(),
        }
        self._action_history.append(action)
        return action

    # ── Window management ─────────────────────────────────────────────────

    def get_active_window(self) -> Dict[str, Any]:
        """Get info about the currently focused window."""
        try:
            import pygetwindow as gw

            win = gw.getActiveWindow()
            if win:
                return {
                    "title": win.title,
                    "x": win.left,
                    "y": win.top,
                    "width": win.width,
                    "height": win.height,
                }
        except Exception:
            pass
        return {"title": "unknown", "x": 0, "y": 0, "width": 0, "height": 0}

    def find_window(self, title_substring: str) -> List[Dict[str, Any]]:
        """Find windows by title substring."""
        try:
            import pygetwindow as gw

            matches = gw.getWindowsWithTitle(title_substring)
            return [
                {
                    "title": w.title,
                    "x": w.left,
                    "y": w.top,
                    "width": w.width,
                    "height": w.height,
                }
                for w in matches
            ]
        except Exception:
            return []

    def focus_window(self, title_substring: str) -> Dict[str, Any]:
        """Bring a window to front by title."""
        try:
            import pygetwindow as gw

            matches = gw.getWindowsWithTitle(title_substring)
            if matches:
                matches[0].activate()
                return {"focused": True, "title": matches[0].title}
        except Exception:
            pass
        return {"focused": False, "error": "window not found"}

    # ── History ───────────────────────────────────────────────────────────

    def get_action_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent action history."""
        return self._action_history[-limit:]

    def clear_history(self) -> None:
        """Clear action history buffer."""
        self._action_history.clear()

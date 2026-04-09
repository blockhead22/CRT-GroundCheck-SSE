"""
Phase 1 test harness — desktop automation primitives.

Tests screenshot capture, cursor, window detection, blocked app detection,
and confirmation logic. No vision model needed for these tests.

Run: pytest tests/desktop_control/test_desktop.py -v
"""

import sys
import os
import time

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from personal_agent.desktop_control import DesktopController
from personal_agent.desktop_vision import ActionType, DesktopAction, VisionAnalysis
from personal_agent.desktop_agent import DesktopAgent, BLOCKED_APPS


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def controller():
    return DesktopController()


class _DummyVision:
    """Stub vision provider for testing agent logic without cloud calls."""

    def __init__(self, responses=None):
        self.responses = responses or []
        self._call_idx = 0

    def analyze_screenshot(self, screenshot_b64, task, action_history, memory_context=""):
        if self._call_idx < len(self.responses):
            result = self.responses[self._call_idx]
            self._call_idx += 1
            return result
        # Default: return DONE after exhausting responses
        return VisionAnalysis(
            actions=[DesktopAction(action_type=ActionType.DONE, reasoning="default done")],
            screen_description="test",
            task_progress="done",
        )


@pytest.fixture
def dummy_agent():
    """Create a DesktopAgent with a dummy vision provider."""
    ctrl = DesktopController()
    vision = _DummyVision()
    return DesktopAgent(controller=ctrl, vision=vision, max_steps=5)


# ── Screenshot tests ──────────────────────────────────────────────────────

class TestScreenshot:
    def test_take_screenshot(self, controller):
        """Verify screenshots capture correctly."""
        img = controller.take_screenshot()
        assert img.width > 0 and img.height > 0
        assert img.mode == "RGB"

    def test_screenshot_to_base64(self, controller):
        """Verify base64 encoding produces non-trivial output."""
        img = controller.take_screenshot()
        b64 = controller.screenshot_to_base64(img)
        assert len(b64) > 1000  # non-trivial image

    def test_screenshot_resize(self, controller):
        """Verify resizing works when max_width is small."""
        img = controller.take_screenshot()
        b64_full = controller.screenshot_to_base64(img, max_width=1920)
        b64_small = controller.screenshot_to_base64(img, max_width=640)
        # Smaller resize should produce smaller base64
        assert len(b64_small) < len(b64_full)

    def test_screenshot_region(self, controller):
        """Verify region capture works."""
        img = controller.screenshot_region(0, 0, 200, 200)
        assert img.width == 200
        assert img.height == 200


# ── Cursor tests ──────────────────────────────────────────────────────────

class TestCursor:
    def test_cursor_position(self, controller):
        """Verify cursor position returns valid tuple."""
        pos = controller.get_cursor_position()
        assert isinstance(pos, tuple)
        assert len(pos) == 2
        assert isinstance(pos[0], int)
        assert isinstance(pos[1], int)


# ── Window tests ──────────────────────────────────────────────────────────

class TestWindow:
    def test_active_window(self, controller):
        """Verify active window info returns expected keys."""
        win = controller.get_active_window()
        assert "title" in win
        assert "width" in win
        assert "height" in win


# ── Action history tests ──────────────────────────────────────────────────

class TestActionHistory:
    def test_history_starts_empty(self, controller):
        controller.clear_history()
        assert len(controller.get_action_history()) == 0

    def test_history_records_actions(self, controller):
        controller.clear_history()
        # Move mouse to a safe location (center of screen)
        import pyautogui
        screen_w, screen_h = pyautogui.size()
        controller.move_mouse(screen_w // 2, screen_h // 2, duration=0.1)
        history = controller.get_action_history()
        assert len(history) == 1
        assert history[0]["type"] == "move"

    def test_history_limit(self, controller):
        controller.clear_history()
        # Add a few moves
        import pyautogui
        screen_w, screen_h = pyautogui.size()
        for i in range(5):
            controller.move_mouse(screen_w // 2 + i, screen_h // 2, duration=0.05)
        assert len(controller.get_action_history(limit=3)) == 3
        assert len(controller.get_action_history(limit=10)) == 5


# ── Blocked app detection tests ──────────────────────────────────────────

class TestBlockedApps:
    def test_blocked_banking(self, dummy_agent):
        assert dummy_agent._is_blocked_app("Chase Bank - Chrome") is True

    def test_blocked_password_manager(self, dummy_agent):
        assert dummy_agent._is_blocked_app("1Password - Vault") is True

    def test_blocked_bitwarden(self, dummy_agent):
        assert dummy_agent._is_blocked_app("Bitwarden") is True

    def test_blocked_regedit(self, dummy_agent):
        assert dummy_agent._is_blocked_app("Registry Editor") is True

    def test_blocked_task_manager(self, dummy_agent):
        assert dummy_agent._is_blocked_app("Task Manager") is True

    def test_blocked_windows_security(self, dummy_agent):
        assert dummy_agent._is_blocked_app("Windows Security") is True

    def test_blocked_credential_manager(self, dummy_agent):
        assert dummy_agent._is_blocked_app("Credential Manager") is True

    def test_allowed_vscode(self, dummy_agent):
        assert dummy_agent._is_blocked_app("VS Code - my_project") is False

    def test_allowed_notepad(self, dummy_agent):
        assert dummy_agent._is_blocked_app("Notepad") is False

    def test_allowed_chrome(self, dummy_agent):
        assert dummy_agent._is_blocked_app("Google Chrome") is False

    def test_allowed_explorer(self, dummy_agent):
        assert dummy_agent._is_blocked_app("File Explorer") is False


# ── Confirmation detection tests ──────────────────────────────────────────

class TestConfirmation:
    def _make_analysis(self):
        return VisionAnalysis(
            actions=[], screen_description="test", task_progress="in_progress"
        )

    def test_submit_button_requires_confirmation(self, dummy_agent):
        action = DesktopAction(
            action_type=ActionType.CLICK, x=100, y=100,
            target_description="Submit Order button", confidence=0.9,
        )
        assert dummy_agent._needs_confirmation(action, self._make_analysis()) is True

    def test_delete_requires_confirmation(self, dummy_agent):
        action = DesktopAction(
            action_type=ActionType.CLICK, x=100, y=100,
            target_description="Delete file button", confidence=0.9,
        )
        assert dummy_agent._needs_confirmation(action, self._make_analysis()) is True

    def test_settings_tab_no_confirmation(self, dummy_agent):
        action = DesktopAction(
            action_type=ActionType.CLICK, x=100, y=100,
            target_description="Settings tab", confidence=0.9,
        )
        assert dummy_agent._needs_confirmation(action, self._make_analysis()) is False

    def test_low_confidence_safe_action_no_confirm(self, dummy_agent):
        """Low confidence on a safe target should NOT gate — trust the model."""
        action = DesktopAction(
            action_type=ActionType.CLICK, x=100, y=100,
            target_description="OK button", confidence=0.4,
        )
        assert dummy_agent._needs_confirmation(action, self._make_analysis()) is False

    def test_high_confidence_safe_action_no_confirm(self, dummy_agent):
        action = DesktopAction(
            action_type=ActionType.CLICK, x=100, y=100,
            target_description="Search bar", confidence=0.95,
        )
        assert dummy_agent._needs_confirmation(action, self._make_analysis()) is False

    def test_destructive_hotkey_confirms(self, dummy_agent):
        action = DesktopAction(
            action_type=ActionType.HOTKEY, keys=["ctrl", "w"],
            target_description="Close window", confidence=0.9,
        )
        assert dummy_agent._needs_confirmation(action, self._make_analysis()) is True

    def test_safe_hotkey_no_confirm(self, dummy_agent):
        action = DesktopAction(
            action_type=ActionType.HOTKEY, keys=["ctrl", "c"],
            target_description="Copy text", confidence=0.9,
        )
        assert dummy_agent._needs_confirmation(action, self._make_analysis()) is False


# ── Hard-blocked target tests ─────────────────────────────────────────────

class TestHardBlocked:
    def test_password_field_blocked(self, dummy_agent):
        action = DesktopAction(
            action_type=ActionType.TYPE, x=100, y=100,
            text="secret123", target_description="Password field",
        )
        assert dummy_agent._is_hard_blocked_target(action) is True

    def test_credit_card_blocked(self, dummy_agent):
        action = DesktopAction(
            action_type=ActionType.TYPE, x=100, y=100,
            text="4111111111111111", target_description="Credit card input",
        )
        assert dummy_agent._is_hard_blocked_target(action) is True

    def test_ssn_blocked(self, dummy_agent):
        action = DesktopAction(
            action_type=ActionType.TYPE, x=100, y=100,
            text="123-45-6789", target_description="Social Security Number",
        )
        assert dummy_agent._is_hard_blocked_target(action) is True

    def test_search_bar_not_blocked(self, dummy_agent):
        action = DesktopAction(
            action_type=ActionType.TYPE, x=100, y=100,
            text="hello world", target_description="Search bar",
        )
        assert dummy_agent._is_hard_blocked_target(action) is False


# ── Restricted region tests ───────────────────────────────────────────────

class TestRestrictedRegions:
    def test_system_tray_blocked(self, dummy_agent):
        action = DesktopAction(
            action_type=ActionType.CLICK, x=1850, y=1060,
            target_description="System tray icon",
        )
        assert dummy_agent._in_restricted_region(action) is True

    def test_center_screen_allowed(self, dummy_agent):
        action = DesktopAction(
            action_type=ActionType.CLICK, x=960, y=540,
            target_description="Center of screen",
        )
        assert dummy_agent._in_restricted_region(action) is False

    def test_no_coordinates_allowed(self, dummy_agent):
        action = DesktopAction(
            action_type=ActionType.TYPE, text="hello",
            target_description="text field",
        )
        assert dummy_agent._in_restricted_region(action) is False


# ── Agent ReAct loop tests (with dummy vision) ───────────────────────────

class TestAgentLoop:
    def test_immediate_done(self):
        """Agent should complete immediately if vision says DONE."""
        ctrl = DesktopController()
        vision = _DummyVision(responses=[
            VisionAnalysis(
                actions=[DesktopAction(
                    action_type=ActionType.DONE,
                    reasoning="Task is already complete",
                )],
                screen_description="desktop",
                task_progress="done",
            )
        ])
        agent = DesktopAgent(controller=ctrl, vision=vision, max_steps=5)
        result = agent.execute_task("check if chrome is open")
        assert result.success is True
        assert result.steps_taken == 1

    def test_immediate_failed(self):
        """Agent should return failure if vision says FAILED."""
        ctrl = DesktopController()
        vision = _DummyVision(responses=[
            VisionAnalysis(
                actions=[DesktopAction(
                    action_type=ActionType.FAILED,
                    reasoning="Cannot find the requested application",
                )],
                screen_description="desktop",
                task_progress="stuck",
            )
        ])
        agent = DesktopAgent(controller=ctrl, vision=vision, max_steps=5)
        result = agent.execute_task("open nonexistent app")
        assert result.success is False
        assert "Cannot find" in result.error

    def test_need_info(self):
        """Agent should return failure with clarification message."""
        ctrl = DesktopController()
        vision = _DummyVision(responses=[
            VisionAnalysis(
                actions=[DesktopAction(
                    action_type=ActionType.NEED_INFO,
                    reasoning="Which browser do you want me to open?",
                )],
                screen_description="desktop",
                task_progress="starting",
            )
        ])
        agent = DesktopAgent(controller=ctrl, vision=vision, max_steps=5)
        result = agent.execute_task("open browser")
        assert result.success is False
        assert "clarification" in result.error.lower()

    def test_checkpoint_rejection(self):
        """Agent should stop if on_checkpoint returns False."""
        ctrl = DesktopController()
        vision = _DummyVision(responses=[
            VisionAnalysis(
                actions=[DesktopAction(
                    action_type=ActionType.CLICK, x=500, y=500,
                    target_description="Submit purchase button",
                    confidence=0.9,
                )],
                screen_description="checkout page",
                task_progress="almost_done",
            )
        ])
        agent = DesktopAgent(controller=ctrl, vision=vision, max_steps=5)
        result = agent.execute_task(
            "complete purchase",
            on_checkpoint=lambda action, ss: False,  # always reject
        )
        assert result.success is False
        assert "rejected" in result.error.lower()

    def test_cancel(self):
        """Agent should stop when stop() is called mid-execution."""
        import threading
        ctrl = DesktopController()
        vision = _DummyVision(responses=[
            VisionAnalysis(
                actions=[DesktopAction(
                    action_type=ActionType.WAIT, wait_seconds=0.5,
                    reasoning="waiting",
                )],
                screen_description="desktop",
                task_progress="in_progress",
            )
        ] * 10)
        agent = DesktopAgent(controller=ctrl, vision=vision, max_steps=10)
        # Stop after a brief delay (while execute_task is running)
        def cancel_soon():
            time.sleep(0.3)
            agent.stop()
        threading.Thread(target=cancel_soon, daemon=True).start()
        result = agent.execute_task("wait forever")
        assert result.success is False
        assert "Cancelled" in result.error


# ── Vision response parsing tests ─────────────────────────────────────────

class TestVisionParsing:
    def test_parse_valid_json(self):
        from personal_agent.desktop_vision import ClaudeVisionProvider

        class _MockClient:
            def chat_with_image(self, **kwargs):
                return '{"screen_description": "Chrome open", "task_progress": "in_progress", "observations": ["Chrome visible"], "action": {"type": "click", "x": 500, "y": 300, "reasoning": "click address bar", "confidence": 0.9, "target_description": "Chrome address bar"}}'

        provider = ClaudeVisionProvider(_MockClient())
        analysis = provider.analyze_screenshot("fake_b64", "open google", [])
        assert len(analysis.actions) == 1
        assert analysis.actions[0].action_type == ActionType.CLICK
        assert analysis.actions[0].x == 500
        assert analysis.actions[0].y == 300
        assert "address bar" in analysis.actions[0].target_description.lower()

    def test_parse_markdown_wrapped_json(self):
        from personal_agent.desktop_vision import ClaudeVisionProvider

        class _MockClient:
            def chat_with_image(self, **kwargs):
                return '```json\n{"screen_description": "desktop", "task_progress": "done", "observations": [], "action": {"type": "done", "reasoning": "complete", "confidence": 1.0, "target_description": ""}}\n```'

        provider = ClaudeVisionProvider(_MockClient())
        analysis = provider.analyze_screenshot("fake_b64", "test", [])
        assert analysis.actions[0].action_type == ActionType.DONE

    def test_parse_invalid_json(self):
        from personal_agent.desktop_vision import ClaudeVisionProvider

        class _MockClient:
            def chat_with_image(self, **kwargs):
                return "This is not JSON at all"

        provider = ClaudeVisionProvider(_MockClient())
        analysis = provider.analyze_screenshot("fake_b64", "test", [])
        assert analysis.actions[0].action_type == ActionType.FAILED
        assert "parse" in analysis.actions[0].reasoning.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

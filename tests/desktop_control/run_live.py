"""
Live desktop control test — runs the ReAct loop with cookie vision provider.

Usage:
    python tests/desktop_control/run_live.py "open notepad"
    python tests/desktop_control/run_live.py "search for weather in Denver"
"""
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("live_test")


def on_step(step_num, action, screenshot_b64, analysis):
    """Print each step as it happens."""
    print(f"\n{'='*60}")
    print(f"  STEP {step_num}")
    print(f"  Screen: {analysis.screen_description[:100]}")
    print(f"  Action: {action.action_type.value}")
    if action.x is not None:
        print(f"  Coords: ({action.x}, {action.y})")
    if action.text:
        print(f"  Text: {action.text}")
    if action.key:
        print(f"  Key: {action.key}")
    if action.keys:
        print(f"  Keys: {'+'.join(action.keys)}")
    print(f"  Target: {action.target_description}")
    print(f"  Reason: {action.reasoning}")
    print(f"  Confidence: {action.confidence}")
    print(f"  Progress: {analysis.task_progress}")
    if analysis.observations:
        print(f"  Observations: {', '.join(analysis.observations[:3])}")
    print(f"{'='*60}")


def on_checkpoint(action, screenshot_b64):
    """Ask user before dangerous actions."""
    print(f"\n*** CHECKPOINT: About to {action.action_type.value} on '{action.target_description}' ***")
    resp = input("Proceed? (y/n): ").strip().lower()
    return resp in ("y", "yes")


def main():
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "open notepad"

    print(f"\n[LIVE TEST] Task: {task}")
    print(f"[LIVE TEST] Using CookieVisionProvider (claude.ai session)")
    print(f"[LIVE TEST] Max 10 steps, pyautogui.FAILSAFE=True (move mouse to top-left corner to abort)")
    print()

    from personal_agent.desktop_control import DesktopController
    from personal_agent.desktop_vision import CookieVisionProvider
    from personal_agent.desktop_agent import DesktopAgent

    # Init
    controller = DesktopController()
    vision = CookieVisionProvider()  # uses cookie session, no API key
    agent = DesktopAgent(controller, vision, max_steps=10)

    # Quick sanity check — take a screenshot to make sure mss works
    print("[INIT] Taking test screenshot...")
    img = controller.take_screenshot()
    print(f"[INIT] Screenshot: {img.width}x{img.height}")
    b64 = controller.screenshot_to_base64(img)
    print(f"[INIT] Base64 size: {len(b64)} chars")

    # Check cookie session
    print("[INIT] Checking cookie session...")
    if not vision.cookie.is_available():
        print("[ERROR] Cookie session not available. Run the session exporter first.")
        sys.exit(1)
    print("[INIT] Cookie session OK")

    # Give user time to set up their screen
    print(f"\n>>> You have 3 seconds to arrange your screen for: {task}")
    import time
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)
    print("  GO!\n")

    # Run the loop
    result = agent.execute_task(
        task=task,
        memory_context="",
        on_checkpoint=on_checkpoint,
        on_step=on_step,
    )

    # Report
    print(f"\n{'#'*60}")
    print(f"  RESULT")
    print(f"  Success: {result.success}")
    print(f"  Steps: {result.steps_taken}")
    print(f"  Duration: {result.total_duration_ms:.0f}ms")
    if result.error:
        print(f"  Error: {result.error}")
    if result.task_summary:
        print(f"  Summary: {result.task_summary}")
    print(f"\n  Action log:")
    for entry in result.action_log:
        step = entry.get("step", "?")
        atype = entry.get("action_type", "?")
        target = entry.get("target", "")
        reason = entry.get("reasoning", "")[:80]
        print(f"    Step {step}: {atype} — {target} ({reason})")
    print(f"{'#'*60}")


if __name__ == "__main__":
    main()

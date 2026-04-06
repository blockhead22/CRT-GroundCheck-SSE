"""
Acceptance tests for orchestrator checkpoint and ask_user flows.

Run with the backend server running on localhost:8000:
    python tests/test_checkpoint_flows.py

Tests:
1. ask_user: orchestrator pauses, user responds, loop resumes
2. diff_write: orchestrator shows diff, user approves, file written
"""

import json
import os
import requests
import sys
import time
from typing import Iterator, List, Dict, Optional

BASE_URL = os.getenv("CRT_API_URL", "http://localhost:8000")
THREAD_ID = f"test_checkpoint_{int(time.time())}"


def stream_chat(message: str, thread_id: str = THREAD_ID) -> List[Dict]:
    """Stream events from /api/chat/stream endpoint."""
    events = []
    try:
        response = requests.post(
            f"{BASE_URL}/api/chat/stream",
            json={"message": message, "thread_id": thread_id, "mode": "task"},
            stream=True,
            timeout=120,
        )
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                raw = line[6:]
                if raw.strip() == "[DONE]":
                    break
                try:
                    events.append(json.loads(raw))
                except json.JSONDecodeError:
                    pass
    except requests.exceptions.Timeout:
        print("  TIMEOUT after 120s")
    return events


def find_event(events: List[Dict], etype: str) -> Optional[Dict]:
    """Find first event matching type."""
    return next((e for e in events if e.get("type") == etype), None)


def test_ask_user():
    """Test ask_user checkpoint: pause -> user answers -> resume."""
    print("\n=== TEST: ask_user checkpoint ===")
    print("1. Sending task that should trigger ask_user...")

    events = stream_chat(
        "I need help organizing my notes. Before you start, ask me "
        "what categories I want to use.",
        thread_id=THREAD_ID,
    )

    # Check for ask_user event
    ask_event = find_event(events, "ask_user")
    done_event = find_event(events, "done")

    if ask_event:
        print(f"   OK: ask_user event received: {ask_event.get('content', '')[:100]}")
    else:
        # Check if it came through as a token or agent_checkpoint
        checkpoint = find_event(events, "agent_checkpoint")
        if checkpoint:
            print(f"   OK: checkpoint event (tier={checkpoint.get('metadata', {}).get('checkpoint_tier')})")
        else:
            print(f"   WARN: No ask_user event. Got types: {[e.get('type') for e in events]}")
            return False

    if done_event:
        meta = done_event.get("metadata", {})
        suspended = meta.get("loop_suspended", False)
        print(f"   loop_suspended={suspended}")
    else:
        print("   WARN: No done event")

    print("\n2. Resuming with user answer...")
    events2 = stream_chat(
        "Use these categories: work, personal, ideas, and reference.",
        thread_id=THREAD_ID,
    )

    # Should get a response (not another ask_user)
    response_events = [e for e in events2 if e.get("type") in ("token", "response")]
    done2 = find_event(events2, "done")

    if response_events or done2:
        content = done2.get("content", "")[:100] if done2 else ""
        print(f"   OK: Resumed successfully. Response: {content}")
        return True
    else:
        print(f"   WARN: No response after resume. Types: {[e.get('type') for e in events2]}")
        return False


def test_diff_write():
    """Test diff_write checkpoint: show diff -> approve -> file written."""
    print("\n=== TEST: diff_write checkpoint ===")
    thread = f"test_diffwrite_{int(time.time())}"

    print("1. Sending task that should trigger file write...")
    events = stream_chat(
        "Create a new file called test_output.txt in the project root "
        "with the content 'Hello from checkpoint test'.",
        thread_id=thread,
    )

    # Check for checkpoint
    checkpoint = find_event(events, "agent_checkpoint")
    if checkpoint:
        meta = checkpoint.get("metadata", {})
        tier = meta.get("checkpoint_tier", "")
        target = meta.get("target_path", "")
        has_diff = bool(meta.get("diff_preview"))
        print(f"   OK: checkpoint tier={tier} target={target} has_diff={has_diff}")
    else:
        print(f"   WARN: No checkpoint. Types: {[e.get('type') for e in events]}")
        # It may have written directly to sandbox
        done = find_event(events, "done")
        if done:
            print(f"   Response: {done.get('content', '')[:100]}")
        return False

    print("\n2. Approving write...")
    events2 = stream_chat("Yes, go ahead", thread_id=thread)

    done2 = find_event(events2, "done")
    if done2:
        content = done2.get("content", "")[:150]
        print(f"   OK: {content}")
        return True
    else:
        print(f"   WARN: No done event after approval. Types: {[e.get('type') for e in events2]}")
        return False


def test_layer2_alignment():
    """Verify Layer 2 alignment data exists in agent_runs.db."""
    print("\n=== TEST: Layer 2 alignment check ===")
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(__file__), "..", "personal_agent", "agent_runs.db")
        if not os.path.exists(db_path):
            print(f"   SKIP: {db_path} not found")
            return None

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        total = conn.execute("SELECT COUNT(*) FROM agent_runs").fetchone()[0]
        print(f"   Total runs: {total}")

        if total == 0:
            print("   SKIP: No runs logged yet")
            return None

        # Check recent runs for alignment data
        recent = conn.execute("SELECT run_id, intent, steps_json FROM agent_runs ORDER BY rowid DESC LIMIT 5").fetchall()
        runs_with_alignment = 0
        for r in recent:
            steps = json.loads(r["steps_json"] or "[]")
            alignments = [s.get("intent_alignment") for s in steps if s.get("intent_alignment") is not None]
            if alignments:
                runs_with_alignment += 1
                print(f"   run={r['run_id'][:12]}: {len(alignments)} alignment scores, range={min(alignments):.3f}-{max(alignments):.3f}")

        if runs_with_alignment > 0:
            print(f"   OK: {runs_with_alignment}/5 recent runs have alignment data")
            return True
        else:
            print("   WARN: No alignment data in recent runs")
            return False
    except Exception as e:
        print(f"   ERROR: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("CRT Orchestrator Checkpoint Acceptance Tests")
    print("=" * 60)

    results = {}

    # Layer 2 can run without server
    results["layer2_alignment"] = test_layer2_alignment()

    # Server-dependent tests
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=5)
        server_up = r.status_code == 200
    except Exception:
        server_up = False

    if server_up:
        results["ask_user"] = test_ask_user()
        results["diff_write"] = test_diff_write()
    else:
        print(f"\n  Server not running at {BASE_URL} — skipping live tests")
        results["ask_user"] = None
        results["diff_write"] = None

    print("\n" + "=" * 60)
    print("RESULTS:")
    for name, result in results.items():
        status = "PASS" if result is True else "FAIL" if result is False else "SKIP"
        print(f"  {name}: {status}")
    print("=" * 60)

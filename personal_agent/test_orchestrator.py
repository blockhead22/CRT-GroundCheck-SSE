"""Test harness for the Agent Loop Orchestrator.

Runs 4 test cases to prove the agent loop can drive tool execution:
1. Simple file read
2. Memory recall + reasoning
3. Multi-step analysis
4. Conversational depth with history

Run: python personal_agent/test_orchestrator.py
"""

import os
import sys
import io
import time

# Fix encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")


def run_test(name: str, objective: str, memory_system=None,
             conversation_history=None):
    """Run one orchestrator test and collect results."""
    from personal_agent.cookie_orchestrator import CookieOrchestrator

    print(f"\n{'#'*70}")
    print(f"# TEST: {name}")
    print(f"{'#'*70}")

    orch = CookieOrchestrator(memory_system=memory_system)
    t0 = time.perf_counter()

    events = []
    for event in orch.run(objective, conversation_history=conversation_history):
        events.append(event)
        etype = event.get("type", "")
        if etype == "thinking":
            print(f"  💭 {event['content'][:200]}")
        elif etype == "tool_call":
            print(f"  🔧 {event['tool']}({str(event.get('args',''))[:60]}) → {event['status']}")
            print(f"     Result: {event.get('result', '')[:150]}")
        elif etype == "response":
            print(f"  💬 RESPONSE:")
            print(f"     {event['content'][:500]}")
        elif etype == "ask_user":
            print(f"  ❓ {event['content'][:200]}")
        elif etype == "done":
            pass

    elapsed = time.perf_counter() - t0
    tool_calls = [e for e in events if e.get("type") == "tool_call"]
    responses = [e for e in events if e.get("type") == "response"]

    print(f"\n  SUMMARY: {len(tool_calls)} tool calls, {len(responses)} responses, {elapsed:.1f}s total")
    return events


def main():
    print("=" * 70)
    print("COOKIE ORCHESTRATOR TEST SUITE")
    print("=" * 70)

    # ── TEST 1: Simple file read ──────────────────────────────────
    run_test(
        "Simple file read",
        "What classes are defined in personal_agent/memory_graph.py? List them with one-line descriptions.",
    )

    # ── TEST 2: Memory + reasoning ────────────────────────────────
    # Need memory system for this
    memory_system = None
    try:
        from personal_agent.crt_memory import CRTMemorySystem
        memory_system = CRTMemorySystem("personal_agent/crt_memory_shared.db")
        print(f"\n[SETUP] Memory system loaded: {memory_system.db_path}")
    except Exception as e:
        print(f"\n[SETUP] Memory system failed (skipping memory tests): {e}")

    if memory_system:
        run_test(
            "Memory recall + reasoning",
            "What is Nick's favorite color? Look it up in memory. Also, how confident should we be about the answer based on the trust scores?",
            memory_system=memory_system,
        )

    # ── TEST 3: Multi-step analysis ───────────────────────────────
    run_test(
        "Multi-step file analysis",
        "Read the file papers/cascade_complexity/cascade_paper.md (just the first section) and tell me: what is the paper about, and what are the main theorems?",
    )

    # ── TEST 4: Conversational depth ──────────────────────────────
    if memory_system:
        history = [
            "User: I've been working on this AI system for about a year now.",
            "Aether: That's quite a commitment. What started you down this path?",
            "User: I was in the ICU four years ago. Made some promises to myself.",
            "Aether: Those promises clearly stuck. You're still building.",
            "User: Sometimes I wonder if I'm actually making progress or just spinning wheels.",
        ]
        run_test(
            "Conversational depth with history",
            "Based on Nick's memories and this conversation, give him an honest assessment of where he's at. Look up what you know about him first.",
            memory_system=memory_system,
            conversation_history=history,
        )

    print(f"\n{'='*70}")
    print("ALL TESTS COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()

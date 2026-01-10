#!/usr/bin/env python3
"""CRT Adaptive Stress Test (30 turns)

This is a *conversation* stress test:
- It talks to CRT for up to 30 user turns.
- After each CRT response, it evaluates the behavior.
- It then chooses the next user message based on: agenda + eval failures + what CRT said.

Design goals:
- Catch false contradiction triggers (questions should not create contradictions).
- Catch identity drift / refusal loops.
- Catch "uncertainty" being used when evidence is consistent.

Notes:
- The "user" side is implemented as a deterministic policy (not another LLM) so runs are repeatable.
  If you want, we can swap the policy for a second LLM later.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client

from crt_response_eval import evaluate_turn


PROJECT_ROOT = Path(__file__).resolve().parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TurnRecord:
    turn: int
    user: str
    crt_answer: str
    crt_result: Dict[str, Any]
    eval_findings: List[Dict[str, Any]]


def _brief_result(result: Dict[str, Any]) -> str:
    mode = result.get("mode")
    conf = float(result.get("confidence", 0.0) or 0.0)
    contra = bool(result.get("contradiction_detected", False))
    unresolved = int(result.get("unresolved_contradictions", 0) or 0)
    return f"mode={mode} conf={conf:.2f} contra={contra} unresolved={unresolved}"


def choose_next_prompt(
    *,
    turn: int,
    transcript: List[TurnRecord],
    last_user: str,
    last_result: Dict[str, Any],
    last_eval_failures: List[Dict[str, Any]],
    state: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """Deterministic user policy.

    Returns: (next_user_message, expectations_for_next_eval)

    The policy is intentionally simple and targeted:
    - Phase A (turns 1-6): establish identity + some stable facts.
    - Phase B (turns 7-14): ask recall questions (should NOT create contradictions).
    - Phase C (turns 15-22): introduce real contradictions, then resolve.
    - Phase D (turns 23-30): try to converge identity and ensure it answers when consistent.

    If we see false contradiction-on-question failures, we immediately repeat a question variant.
    If we see "uncertainty" loops even when consistent, we add reinforcement and ask again.
    """

    # React to failures first
    for f in last_eval_failures:
        if f.get("check") == "no_contradiction_on_question":
            # Repeat a slightly different question to isolate
            return (
                "Quick check: what is my name?",
                {"contradiction_should_be_false_for_questions": True},
            )

    # Track whether we've asserted a name
    if state.get("name") is None:
        state["name"] = "Nick"

    name = state["name"]

    # Phase-based agenda
    if turn == 1:
        return (f"Hi. My name is {name}.", {"expect_contradiction": False})
    if turn == 2:
        return ("I live in Seattle.", {"expect_contradiction": False})
    if turn == 3:
        return ("I work on AI systems.", {"expect_contradiction": False})
    if turn == 4:
        return ("What's my name?", {"contradiction_should_be_false_for_questions": True})
    if turn == 5:
        return ("What city do I live in?", {"contradiction_should_be_false_for_questions": True})
    if turn == 6:
        return ("Summarize what you know about me so far.", {"contradiction_should_be_false_for_questions": True})

    # Recall probing: should not create contradictions
    if 7 <= turn <= 10:
        return ("What did I say my name was?", {"contradiction_should_be_false_for_questions": True})

    # Introduce a real contradiction: name flip
    if turn == 11:
        return ("Actually, my name is Emily.", {"expect_contradiction": True})
    if turn == 12:
        return ("What's my name?", {"contradiction_should_be_false_for_questions": True, "expect_uncertainty": True})

    # Resolve back
    if turn == 13:
        return (f"Sorry, that was a test. My name is {name}.", {"expect_contradiction": True})
    if turn == 14:
        return ("Now what's my name?", {"contradiction_should_be_false_for_questions": True})

    # Preference contradiction
    if turn == 15:
        return ("I prefer working remotely.", {"expect_contradiction": False})
    if turn == 16:
        return ("Actually I hate remote work; I prefer the office.", {"expect_contradiction": True})
    if turn == 17:
        return ("So do I prefer remote or the office?", {"contradiction_should_be_false_for_questions": True, "expect_uncertainty": True})

    # Try to break uncertainty loops: reinforce consistent name
    if 18 <= turn <= 21:
        return (f"Reinforcing: yes, my name is {name}.", {"expect_contradiction": False})

    if turn == 22:
        return ("One last time: what's my name?", {"contradiction_should_be_false_for_questions": True})

    # Final convergence + robustness
    if 23 <= turn <= 26:
        return ("Who am I to you (in one sentence)?", {"contradiction_should_be_false_for_questions": True})

    if turn == 27:
        return ("If you're uncertain, list exactly what conflicts and ask me to resolve them.", {"contradiction_should_be_false_for_questions": True})

    if turn == 28:
        return (f"Final clarification: my name is {name}. Do you accept that?", {"expect_contradiction": False})

    if turn == 29:
        return ("What is my name?", {"contradiction_should_be_false_for_questions": True})

    # turn 30
    return ("Thanks. What contradictions are still open?", {"contradiction_should_be_false_for_questions": True})


def main() -> int:
    print("=" * 80)
    print(" CRT ADAPTIVE STRESS TEST (30 TURNS) ".center(80, "="))
    print("=" * 80)

    ollama = get_ollama_client("llama3.2:latest")

    # Use isolated DBs per run to avoid clobbering GUI state and to prevent
    # failures when user-specified DB paths are invalid/unwritable.
    memory_db = str(ARTIFACTS_DIR / "crt_adaptive_memory.db")
    ledger_db = str(ARTIFACTS_DIR / "crt_adaptive_ledger.db")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    rag = CRTEnhancedRAG(llm_client=ollama, memory_db=memory_db, ledger_db=ledger_db)

    transcript: List[TurnRecord] = []
    state: Dict[str, Any] = {"name": "Nick"}

    last_user = ""
    last_result: Dict[str, Any] = {}
    last_failures: List[Dict[str, Any]] = []

    for turn in range(1, 31):
        user_msg, expectations = choose_next_prompt(
            turn=turn,
            transcript=transcript,
            last_user=last_user,
            last_result=last_result,
            last_eval_failures=last_failures,
            state=state,
        )

        print("\n" + ("-" * 80))
        print(f"TURN {turn}")
        print(f"USER: {user_msg}")

        result = rag.query(user_msg)
        answer = (result.get("answer") or "").strip()
        print(f"CRT: {answer[:500]}{'...' if len(answer) > 500 else ''}")
        print(f"META: {_brief_result(result)}")

        findings = evaluate_turn(user_prompt=user_msg, result=result, expectations=expectations)
        failures = [f for f in findings if not f.passed]

        eval_dump = [
            {"check": f.check, "passed": f.passed, "details": f.details}
            for f in findings
        ]

        for f in findings:
            tag = "✅" if f.passed else "❌"
            print(f"EVAL {tag} {f.check}: {f.details}")

        transcript.append(
            TurnRecord(
                turn=turn,
                user=user_msg,
                crt_answer=answer,
                crt_result=result,
                eval_findings=eval_dump,
            )
        )

        last_user = user_msg
        last_result = result
        last_failures = eval_dump if failures else []

        # small pause to keep logs readable; no need to throttle heavily
        time.sleep(0.1)

    # Summary
    checks = 0
    passed = 0
    failed_items: List[Dict[str, Any]] = []
    for tr in transcript:
        for f in tr.eval_findings:
            checks += 1
            if f["passed"]:
                passed += 1
            else:
                failed_items.append({"turn": tr.turn, **f, "user": tr.user})

    print("\n" + ("=" * 80))
    print(" SUMMARY ".center(80, "="))
    print("=" * 80)
    print(f"Turns: {len(transcript)}")
    print(f"Eval checks: {checks}")
    print(f"Pass rate: {100.0 * passed / max(checks, 1):.1f}%")
    print(f"Failures: {len(failed_items)}")

    for f in failed_items[:12]:
        print(f"- Turn {f['turn']}: {f['check']} :: {f.get('details','')} :: {f['user']}")

    out_path = ARTIFACTS_DIR / "crt_adaptive_stress_test.latest.json"
    out_path.write_text(
        json.dumps(
            {
                "turns": [
                    {
                        "turn": tr.turn,
                        "user": tr.user,
                        "crt_answer": tr.crt_answer,
                        "crt_result": tr.crt_result,
                        "eval": tr.eval_findings,
                    }
                    for tr in transcript
                ],
                "summary": {
                    "checks": checks,
                    "passed": passed,
                    "failures": len(failed_items),
                },
            },
            indent=2,
        )
    )
    print(f"\nSaved transcript: {out_path}")

    # Non-zero exit if failures
    return 0 if len(failed_items) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

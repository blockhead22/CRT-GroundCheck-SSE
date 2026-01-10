#!/usr/bin/env python3
"""CRT Live Probe (interactive AI-vs-AI chat)

This tool is for what you're asking for now:
- Treat CRT like a chat partner (system under test).
- A "tester" controller proposes the next message based on the last result.
- You can press Enter to accept the suggestion, type your own message, or run /auto.

Usage examples:
  D:/AI_round2/.venv/Scripts/python.exe crt_live_probe.py --profile-file NickBlock.txt
  D:/AI_round2/.venv/Scripts/python.exe crt_live_probe.py --sut-model llama3.2:latest --controller-model llama3.2:latest

Commands (type at the prompt):
  /help                 show help
  /auto N               run N turns automatically
  /suggest              show the controller's next suggested message
  /state                show small controller state
  /quit                 exit

Notes:
- This runs locally; it does not require a web UI.
- Artifacts and DBs are stored under --artifacts-dir (default: ./artifacts).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client

from crt_adaptive_stress_test import (
    LLMController,
    HeuristicController,
    TurnRecord,
    _brief_result,
    _normalize_profile_text,
    _read_text_file,
    _build_profile_seed_message,
    _safe_mkdir,
)

from crt_response_eval import evaluate_turn


PROJECT_ROOT = Path(__file__).resolve().parent


def _load_profile(profile_file: str) -> str:
    p = Path(profile_file)
    if not p.is_absolute():
        p = (PROJECT_ROOT / p).resolve()

    candidates = [p]
    if not p.exists():
        candidates.extend([PROJECT_ROOT / "NickBlock.txt", PROJECT_ROOT / "nickblock.txt"])

    for c in candidates:
        txt = _normalize_profile_text(_read_text_file(c))
        if txt:
            return txt
    return ""


def _print_meta(result: Dict[str, Any]) -> None:
    print(f"META: {_brief_result(result)}")
    # Print a small, stable subset of metadata that's most useful in a live probe.
    for k in [
        "gates_passed",
        "gate_reason",
        "intent_alignment",
        "memory_alignment",
        "contradiction_detected",
        "unresolved_contradictions",
    ]:
        if k in result:
            print(f"  - {k}: {result.get(k)}")


def _run_one_turn(*, rag: CRTEnhancedRAG, user_msg: str, transcript: List[TurnRecord], state: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    print("\n" + ("-" * 80))
    print(f"YOU: {user_msg}")

    try:
        result = rag.query(user_msg)
    except KeyboardInterrupt:
        print("\n[Interrupted] Skipping this turn.")
        return {}, []
    except Exception as e:
        print(f"\n[Error calling CRT] {e}")
        return {}, []
    answer = (result.get("answer") or "").strip()
    print(f"CRT: {answer}\n")
    _print_meta(result)

    # Lightweight eval based on message shape.
    expectations: Dict[str, Any] = {}
    if user_msg.strip().endswith("?"):
        expectations["contradiction_should_be_false_for_questions"] = True

    try:
        findings = evaluate_turn(user_prompt=user_msg, result=result, expectations=expectations)
    except Exception as e:
        print(f"[Eval error] {e}")
        findings = []
    eval_dump = [{"check": f.check, "passed": f.passed, "details": f.details} for f in findings]

    any_fail = False
    for f in findings:
        if not f.passed:
            any_fail = True
        tag = "OK" if f.passed else "FAIL"
        print(f"EVAL {tag}: {f.check} :: {f.details}")

    transcript.append(
        TurnRecord(
            turn=len(transcript) + 1,
            user=user_msg,
            crt_answer=answer,
            crt_result=result,
            eval_findings=eval_dump,
        )
    )

    # Track eval failures for controller context.
    state["last_eval"] = eval_dump
    state["last_result"] = result

    if any_fail:
        print("\n(Controller will react to these failures next turn.)")

    return result, eval_dump


def main() -> int:
    ap = argparse.ArgumentParser(description="Interactive CRT probe (AI-vs-AI chat)")
    ap.add_argument("--sut-model", type=str, default="llama3.2:latest")
    ap.add_argument("--controller-model", type=str, default="llama3.2:latest")
    ap.add_argument("--controller", choices=["llm", "heuristic"], default="llm")
    ap.add_argument("--controller-temp", type=float, default=0.3)
    ap.add_argument("--profile-file", type=str, default="NickBlock.txt")
    ap.add_argument("--artifacts-dir", type=str, default=str(PROJECT_ROOT / "artifacts"))
    args = ap.parse_args()

    artifacts_dir = Path(args.artifacts_dir).resolve()
    _safe_mkdir(artifacts_dir)

    memory_db = str(artifacts_dir / "crt_live_memory.db")
    ledger_db = str(artifacts_dir / "crt_live_ledger.db")

    sut_llm = get_ollama_client(args.sut_model)
    rag = CRTEnhancedRAG(llm_client=sut_llm, memory_db=memory_db, ledger_db=ledger_db)

    profile_text = _load_profile(args.profile_file)

    state: Dict[str, Any] = {
        "name": "Nick Block",
        "profile_text": profile_text,
        "seed_message": _build_profile_seed_message(profile_text),
        "recent_user_msgs": [],
        "recent_tactics": [],
        "last_result": {},
        "last_eval": [],
    }

    if args.controller == "heuristic":
        controller = HeuristicController()
    else:
        ctrl_llm = get_ollama_client(args.controller_model)
        controller = LLMController(ctrl_llm, temperature=float(args.controller_temp))

    transcript: List[TurnRecord] = []

    print("=" * 80)
    print(" CRT LIVE PROBE ".center(80, "="))
    print("=" * 80)
    if profile_text:
        print("Loaded profile context.")
    else:
        print("No profile file loaded (continuing anyway).")

    # Turn 1: seed
    seed = state.get("seed_message") or "Hi. My name is Nick Block."
    _run_one_turn(rag=rag, user_msg=seed, transcript=transcript, state=state)

    def suggest_next() -> Tuple[str, Dict[str, Any]]:
        return controller.next_prompt(
            turn=len(transcript) + 1,
            transcript=transcript,
            last_result=state.get("last_result") or {},
            last_eval=state.get("last_eval") or [],
            state=state,
        )

    suggested, _ = suggest_next()

    def show_help() -> None:
        print(
            "\nCommands:\n"
            "  /help                 show help\n"
            "  /auto N               run N turns automatically\n"
            "  /suggest              show suggested next message\n"
            "  /state                show controller state\n"
            "  /quit                 exit\n"
            "\nPress Enter to send the suggested message, or type your own message.\n"
        )

    show_help()

    while True:
        print("\n" + ("=" * 80))
        print(f"SUGGESTED: {suggested}")
        user_in = input("> ").strip()

        if not user_in:
            user_in = suggested

        if user_in.startswith("/"):
            parts = user_in.split()
            cmd = parts[0].lower()
            if cmd in {"/quit", "/exit"}:
                break
            if cmd == "/help":
                show_help()
            elif cmd == "/suggest":
                print(f"Suggested: {suggested}")
            elif cmd == "/state":
                slim = {
                    "recent_user_msgs": (state.get("recent_user_msgs") or [])[-5:],
                    "recent_tactics": (state.get("recent_tactics") or [])[-5:],
                }
                print(json.dumps(slim, indent=2))
            elif cmd == "/auto":
                try:
                    n = int(parts[1]) if len(parts) > 1 else 5
                except Exception:
                    n = 5
                for _ in range(n):
                    msg, _exp = suggest_next()
                    _run_one_turn(rag=rag, user_msg=msg, transcript=transcript, state=state)
                    time.sleep(0.1)
                print(f"(Auto ran {n} turns; you are now at turn {len(transcript)}.)")
            else:
                print("Unknown command. Type /help")

            suggested, _ = suggest_next()
            continue

        # Normal user message
        _run_one_turn(rag=rag, user_msg=user_in, transcript=transcript, state=state)
        suggested, _ = suggest_next()

    # Save transcript
    out_path = artifacts_dir / "crt_live_probe.latest.json"
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
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved transcript: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

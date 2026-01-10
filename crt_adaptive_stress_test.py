#!/usr/bin/env python3
"""CRT Adaptive Stress Test (adaptive, up to N turns)

This is a *conversation* stress test:
- It talks to CRT for up to N user turns.
- After each CRT response, it evaluates behavior.
- It then generates the *next* user message dynamically based on: transcript + eval findings + CRT metadata.

Design goals:
- Catch false contradiction triggers (questions should not create contradictions).
- Catch identity drift / refusal loops.
- Catch "uncertainty" being used when evidence is consistent.

Notes:
- The "user" side can be either:
    - LLM-driven (recommended): a second model plays the tester and adapts each next prompt.
    - Heuristic (fallback): a deterministic policy for repeatability.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client, OllamaClient

from crt_response_eval import evaluate_turn


PROJECT_ROOT = Path(__file__).resolve().parent


def _safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _read_text_file(path: Path, *, max_chars: int = 6000) -> str:
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    except Exception:
        # Best effort (e.g., odd encodings)
        try:
            txt = path.read_text(errors="replace")
        except Exception:
            return ""
    txt = (txt or "").strip()
    if len(txt) > max_chars:
        txt = txt[:max_chars].rstrip() + "\n…"
    return txt


def _normalize_profile_text(txt: str) -> str:
    # Remove simple TeX/markdown artifacts and normalize whitespace.
    t = (txt or "").replace("\r", "\n")
    t = t.replace("\\n", "\n")
    t = t.replace("•", "- ")
    lines = [ln.strip() for ln in t.split("\n")]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def _build_profile_seed_message(profile_text: str) -> str:
    """Create a short initial user message that seeds CRT with core profile facts."""
    if not profile_text:
        return "Hi. My name is Nick Block."

    # Keep this short and high-signal; controller prompt limits are stricter than CRT.
    return (
        "Hi—I'm Nick Block. I built CRT (memory-first, trust evolution + contradiction detection). "
        "I run The Printing Lair (print/sticker shop)."
    )


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


class AdaptiveController:
    """Generates the next user message.

    This is the "Copilot" side of the stress test: it reads the system-under-test (CRT)
    outputs and decides what to say next.
    """

    def next_prompt(
        self,
        *,
        turn: int,
        transcript: List[TurnRecord],
        last_result: Dict[str, Any],
        last_eval: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        raise NotImplementedError


class HeuristicController(AdaptiveController):
    """Deterministic fallback controller (repeatable, but less powerful)."""

    def next_prompt(
        self,
        *,
        turn: int,
        transcript: List[TurnRecord],
        last_result: Dict[str, Any],
        last_eval: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        # Keep it minimal but adaptive: respond to eval failures with targeted probes.
        failures = [f for f in (last_eval or []) if not f.get("passed", True)]

        for f in failures:
            if f.get("check") in {"no_contradiction_on_question", "contradiction_on_question"}:
                return (
                    "Different wording: what is my name?",
                    {"contradiction_should_be_false_for_questions": True},
                )

        # Establish a stable identity early.
        name = state.setdefault("name", "Nick")
        if turn == 1:
            return (f"Hi. My name is {name}.", {})
        if turn == 2:
            return ("What is my name?", {"contradiction_should_be_false_for_questions": True})

        # If CRT is uncertain, try resolving explicitly.
        if (last_result.get("mode") == "uncertainty") or (int(last_result.get("unresolved_contradictions", 0) or 0) > 0):
            return (
                f"Clarifying for the record: my name is {name}. Please store this as the current truth.",
                {"expect_contradiction": False},
            )

        # Otherwise probe recall without creating contradictions.
        return ("What did I say my name was?", {"contradiction_should_be_false_for_questions": True})


class LLMController(AdaptiveController):
    """LLM-driven adaptive tester.

    This is what you asked for: after each CRT response we generate a *new*, situation-dependent
    follow-up prompt rather than stepping through a fixed script.
    """

    def __init__(
        self,
        llm: OllamaClient,
        *,
        temperature: float = 0.3,
        max_tokens: int = 220,
        keep_last_turns: int = 6,
    ):
        self.llm = llm
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.keep_last_turns = keep_last_turns

        # When the controller output is invalid or repetitive, we rotate through
        # a small pool of high-signal probes to avoid getting stuck.
        self._fallback_probes = [
            ("What did I say my name was?", {"contradiction_should_be_false_for_questions": True}, "recall_question"),
            ("Quote the exact memory text you used to answer my name.", {"contradiction_should_be_false_for_questions": True}, "cite_memory"),
            ("Do you have any open contradictions about my identity? List them.", {"contradiction_should_be_false_for_questions": True}, "ask_open_contradictions"),
            ("For the record: my name is Nick Block.", {"expect_contradiction": False}, "contradiction_resolve"),
            ("What do you know about The Printing Lair from our chat?", {"contradiction_should_be_false_for_questions": True}, "recall_question"),
        ]
        self._fallback_index = 0

    def _pick_fallback(self, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], str]:
        recent_user = state.get("recent_user_msgs") or []
        # Try up to N fallbacks to find one not in last 3.
        for _ in range(len(self._fallback_probes) + 2):
            msg, exp, tactic = self._fallback_probes[self._fallback_index % len(self._fallback_probes)]
            self._fallback_index += 1
            if msg not in recent_user[-3:]:
                return msg, dict(exp), tactic
        # Absolute last resort: append a discriminator.
        msg, exp, tactic = self._fallback_probes[0]
        msg = msg + f" (probe {self._fallback_index})"
        return msg, dict(exp), tactic

    def _build_system_prompt(self) -> str:
        return (
            "You are an adversarial QA tester for a system called CRT (Contradiction/Trust Memory).\n"
            "Your job: produce the NEXT user message to probe whether CRT:\n"
            "- avoids false contradictions triggered by questions\n"
            "- converges on stable identity facts when consistent\n"
            "- only becomes uncertain when there is a real conflict\n"
            "- does NOT hallucinate personal details\n\n"
            "Hard rules:\n"
            "- Output STRICT JSON ONLY with keys: user_message, expectations, tactic.\n"
            "- user_message must be ONE short user message (<= 200 chars).\n"
            "- Do not repeat the same user_message as any of the last 3 user messages.\n"
            "- If the last eval failed, focus on reproducing and isolating that failure.\n"
            "- If there were no failures, you MUST vary tactics turn-to-turn.\n\n"
            "Allowed tactic labels (choose one string):\n"
            "- seed_fact\n"
            "- recall_question\n"
            "- cite_memory\n"
            "- contradiction_inject\n"
            "- contradiction_resolve\n"
            "- probe_refusal_loop\n"
            "- probe_hallucination\n"
            "- ask_open_contradictions\n\n"
            "Tactic guidance:\n"
            "- recall_question: ask what the user said (name/job/company)\n"
            "- cite_memory: ask it to quote the memory text it used\n"
            "- contradiction_inject: introduce a conflicting assertion deliberately\n"
            "- contradiction_resolve: clarify which statement is correct\n"
            "- probe_refusal_loop: ask the same fact in a new way to see if it keeps refusing\n"
            "- probe_hallucination: ask about something it shouldn't know yet\n"
            "- ask_open_contradictions: ask it to list any open contradictions\n\n"
            "expectations is an object that may include: \n"
            "- contradiction_should_be_false_for_questions (bool)\n"
            "- expect_contradiction (bool)\n"
            "- expect_uncertainty (bool)\n"
            "- expected_name (string)\n"
        )

    def _build_user_prompt(
        self,
        *,
        turn: int,
        transcript: List[TurnRecord],
        last_result: Dict[str, Any],
        last_eval: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> str:
        name = state.setdefault("name", "Nick Block")
        profile = (state.get("profile_text") or "").strip()
        recent_user_msgs = state.get("recent_user_msgs") or []
        recent_tactics = state.get("recent_tactics") or []
        last_mode = last_result.get("mode")
        last_conf = float(last_result.get("confidence", 0.0) or 0.0)
        last_contra = bool(last_result.get("contradiction_detected", False))
        unresolved = int(last_result.get("unresolved_contradictions", 0) or 0)
        gate_reason = last_result.get("gate_reason")

        recent = transcript[-self.keep_last_turns :]
        transcript_lines: List[str] = []
        for tr in recent:
            a = (tr.crt_answer or "").replace("\n", " ").strip()
            a = a[:220] + ("..." if len(a) > 220 else "")
            u = (tr.user or "").replace("\n", " ").strip()
            u = u[:220] + ("..." if len(u) > 220 else "")
            transcript_lines.append(f"U: {u}\nA: {a}")

        failures = [f for f in (last_eval or []) if not f.get("passed", True)]
        failures_compact = [
            {"check": f.get("check"), "details": (f.get("details") or "")[:200]}
            for f in failures
        ]

        # Give the controller a *mission* and a small amount of state.
        return (
            f"TURN={turn}\n"
            f"Known user name to converge on (ground truth for test): {name}\n\n"
            "User profile (ground truth, may be shared to CRT gradually):\n"
            + (profile[:1800] + ("\n…" if len(profile) > 1800 else ""))
            + "\n\n"
            "Recent transcript:\n"
            + "\n\n".join(transcript_lines)
            + "\n\n"
            "Last CRT metadata (summary):\n"
            f"mode={last_mode}, confidence={last_conf:.2f}, contradiction_detected={last_contra}, unresolved_contradictions={unresolved}, gate_reason={gate_reason}\n\n"
            "Last eval failures (if any):\n"
            + json.dumps(failures_compact)
            + "\n\n"
            "Recent user messages (last 3, do not repeat exactly):\n"
            + json.dumps(recent_user_msgs[-3:])
            + "\n"
            "Recent tactics (last 3, vary if no failures):\n"
            + json.dumps(recent_tactics[-3:])
            + "\n\n"
            "Now choose the NEXT user message to probe CRT.\n"
            "If CRT is uncertain due to contradictions, try a resolving statement then re-ask.\n"
            "If CRT hallucinates identity, ask it to cite the memory it used.\n"
            "If CRT flags contradiction on questions, ask a question variant.\n"
            "If there are no eval failures, do NOT keep asking the same recall question; switch tactics.\n"
        )

    def next_prompt(
        self,
        *,
        turn: int,
        transcript: List[TurnRecord],
        last_result: Dict[str, Any],
        last_eval: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        if turn == 1:
            # Seed CRT with a stable fact (using profile if available).
            seed = state.get("seed_message")
            if seed:
                # Record so we can enforce non-repetition starting on turn 2.
                state["recent_user_msgs"] = (state.get("recent_user_msgs") or []) + [seed]
                state["recent_tactics"] = (state.get("recent_tactics") or []) + ["seed_fact"]
                return (seed, {"expect_contradiction": False})
            name = state.setdefault("name", "Nick Block")
            seed_msg = f"Hi. My name is {name}."
            state["recent_user_msgs"] = (state.get("recent_user_msgs") or []) + [seed_msg]
            state["recent_tactics"] = (state.get("recent_tactics") or []) + ["seed_fact"]
            return (seed_msg, {"expect_contradiction": False})

        sys_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            turn=turn,
            transcript=transcript,
            last_result=last_result,
            last_eval=last_eval,
            state=state,
        )

        raw = self.llm.generate(
            user_prompt,
            system=sys_prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        # Parse JSON, with safe fallback.
        try:
            obj = json.loads(raw)
            msg = (obj.get("user_message") or "").strip()
            expectations = obj.get("expectations") or {}
            if not isinstance(expectations, dict):
                expectations = {}
            tactic = (obj.get("tactic") or "").strip()
        except Exception:
            msg, expectations, tactic = self._pick_fallback(state)

        # Clamp message length and keep it single-message.
        msg = msg.replace("\r", " ").replace("\n", " ").strip()
        if len(msg) > 220:
            msg = msg[:220].rstrip() + "…"

        # If controller forgot to mark a question, we still want that check.
        if msg.endswith("?") and "contradiction_should_be_false_for_questions" not in expectations:
            expectations["contradiction_should_be_false_for_questions"] = True

        # Enforce non-repetition against the last 3 user messages.
        recent_user = state.get("recent_user_msgs") or []
        if msg in recent_user[-3:]:
            msg, expectations, tactic = self._pick_fallback(state)

        # Save tactic/message to state for the next iteration.
        recent_tactics = state.get("recent_tactics") or []
        state["recent_tactics"] = (recent_tactics + [tactic or "unknown"])[-12:]
        state["recent_user_msgs"] = (recent_user + [msg])[-12:]

        return msg, expectations


def main() -> int:
    print("=" * 80)
    print(" CRT ADAPTIVE STRESS TEST (ADAPTIVE) ".center(80, "="))
    print("=" * 80)

    ap = argparse.ArgumentParser(description="Adaptive AI-vs-AI CRT stress test")
    ap.add_argument("--turns", type=int, default=30, help="Number of user turns")
    ap.add_argument("--sut-model", type=str, default="llama3.2:latest", help="Model used by CRT (system under test)")
    ap.add_argument("--controller-model", type=str, default="llama3.2:latest", help="Model used by the tester/controller")
    ap.add_argument("--controller", choices=["llm", "heuristic"], default="llm", help="How to generate the next user message")
    ap.add_argument("--artifacts-dir", type=str, default=str(PROJECT_ROOT / "artifacts"), help="Where to write logs/db")
    ap.add_argument("--controller-temp", type=float, default=0.3, help="Controller temperature")
    ap.add_argument(
        "--profile-file",
        type=str,
        default="NickBlock.txt",
        help="Optional profile text file to ground the controller + seed CRT (e.g., NickBlock.txt)",
    )
    args = ap.parse_args()

    artifacts_dir = Path(args.artifacts_dir).resolve()
    _safe_mkdir(artifacts_dir)

    # Isolated DBs per run to avoid clobbering GUI state.
    memory_db = str(artifacts_dir / "crt_adaptive_memory.db")
    ledger_db = str(artifacts_dir / "crt_adaptive_ledger.db")

    sut_llm = get_ollama_client(args.sut_model)
    rag = CRTEnhancedRAG(llm_client=sut_llm, memory_db=memory_db, ledger_db=ledger_db)

    if args.controller == "heuristic":
        controller: AdaptiveController = HeuristicController()
    else:
        controller_llm = get_ollama_client(args.controller_model)
        controller = LLMController(controller_llm, temperature=float(args.controller_temp))

    transcript: List[TurnRecord] = []

    # Load profile text (best effort). Support common casing variations.
    profile_path = Path(args.profile_file)
    if not profile_path.is_absolute():
        profile_path = (PROJECT_ROOT / profile_path).resolve()

    candidates = [profile_path]
    # If the passed filename doesn't exist, try common alternates in repo root.
    if not candidates[0].exists():
        candidates.extend(
            [
                (PROJECT_ROOT / "NickBlock.txt"),
                (PROJECT_ROOT / "nickblock.txt"),
            ]
        )

    profile_text = ""
    for p in candidates:
        profile_text = _normalize_profile_text(_read_text_file(p))
        if profile_text:
            break

    state: Dict[str, Any] = {
        "name": "Nick Block",
        "profile_text": profile_text,
        "seed_message": _build_profile_seed_message(profile_text),
        "recent_user_msgs": [],
        "recent_tactics": [],
    }

    last_user = ""
    last_result: Dict[str, Any] = {}
    last_failures: List[Dict[str, Any]] = []

    for turn in range(1, int(args.turns) + 1):
        user_msg, expectations = controller.next_prompt(
            turn=turn,
            transcript=transcript,
            last_result=last_result,
            last_eval=last_failures,
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

    out_path = artifacts_dir / "crt_adaptive_stress_test.latest.json"
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

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .agents import AgentProtocolError, OllamaJsonAgent
from .types import GroundCheckCaseResult


def _extract_json_obj(text: str) -> Optional[Dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    if "```" in raw:
        for part in raw.split("```"):
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                continue
    return None


def _coerce_case_memories(raw_memories: Any, case_id: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if isinstance(raw_memories, list):
        for idx, item in enumerate(raw_memories):
            if isinstance(item, str):
                text = item.strip()
                if text:
                    out.append({"id": f"{case_id}_m{idx+1}", "text": text, "trust": 1.0})
            elif isinstance(item, dict):
                text = str(item.get("text") or "").strip()
                if not text:
                    continue
                out.append(
                    {
                        "id": str(item.get("id") or f"{case_id}_m{idx+1}"),
                        "text": text,
                        "trust": float(item.get("trust") or 1.0),
                    }
                )
    return out


def _build_algorithmic_fallback_cases(*, objective_context: Dict[str, Any], count: int) -> List[Dict[str, Any]]:
    """Fallback when model-generated cases fail protocol.

    This intentionally avoids hardcoded user questions. It generates statement-only
    verifier cases and derives one tokenized case from run context when available.
    """
    seed_texts = [
        str(x).strip()
        for x in (objective_context.get("seed_texts") or [])
        if str(x).strip()
    ]
    seed_claim = seed_texts[0] if seed_texts else "User lives in Austin."
    token = str(abs(hash("|".join(seed_texts or ["fallback"]))) % 100000)

    cases: List[Dict[str, Any]] = [
        {
            "case_id": "fallback_consistent",
            "objective": "consistent support path",
            "memories": [{"id": "m1", "text": seed_claim, "trust": 0.9}],
            "draft": seed_claim,
            "mode": "strict",
            "expected": {"expect_pass": True},
        },
        {
            "case_id": "fallback_mismatch",
            "objective": "mismatch detection path",
            "memories": [{"id": "m1", "text": "User lives in Austin.", "trust": 0.95}],
            "draft": "User lives in Seattle.",
            "mode": "strict",
            "expected": {"expect_pass": False},
        },
        {
            "case_id": "fallback_conflict_slot",
            "objective": "contradiction details present on exclusive slot",
            "memories": [
                {"id": "m1", "text": "User works at Microsoft.", "trust": 0.9},
                {"id": "m2", "text": "User works at Amazon.", "trust": 0.8}
            ],
            "draft": "User works at Microsoft.",
            "mode": "strict",
            "expected": {"expect_contradictions": True},
        },
        {
            "case_id": "fallback_tokenized_scope",
            "objective": "out-of-scope handling",
            "memories": [{"id": "m1", "text": f"Reference token {token} is active.", "trust": 1.0}],
            "draft": f"Reference token {token} is active. The user salary is 200000.",
            "mode": "strict",
            "expected": {"expect_pass": True}
        }
    ]
    return cases[: max(3, int(count))]


def generate_groundcheck_cases(
    *,
    attacker_agent: OllamaJsonAgent,
    objective_context: Dict[str, Any],
    count: int = 6,
) -> List[Dict[str, Any]]:
    system = (
        "You are generating standalone GroundCheck verification scenarios. "
        "Output strict JSON only and avoid conversational fluff."
    )
    user = json.dumps(
        {
            "task": "generate_groundcheck_cases",
            "count": int(max(3, count)),
            "objective_context": objective_context,
            "constraints": {
                "memory_items_per_case": [2, 6],
                "include_conflicting_cases": True,
                "include_in_scope_and_out_of_scope_mix": True,
            },
        },
        ensure_ascii=True,
    )

    raw = attacker_agent._chat(system=system, user=user, num_predict=900)
    parsed = _extract_json_obj(raw)
    if not isinstance(parsed, dict):
        repaired = attacker_agent._repair_json(
            invalid_text=raw,
            required_keys=["cases"],
        )
        parsed = repaired if isinstance(repaired, dict) else None

    if not isinstance(parsed, dict):
        return _build_algorithmic_fallback_cases(objective_context=objective_context, count=count)
    cases = parsed.get("cases")
    if not isinstance(cases, list) or not cases:
        return _build_algorithmic_fallback_cases(objective_context=objective_context, count=count)

    clean_cases: List[Dict[str, Any]] = []
    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("case_id") or f"gc_case_{idx+1}").strip()
        objective = str(case.get("objective") or "unspecified objective").strip()
        draft = str(case.get("draft") or "").strip()
        mode = str(case.get("mode") or "strict").strip().lower()
        if mode not in {"strict", "permissive"}:
            mode = "strict"
        memories = _coerce_case_memories(case.get("memories"), case_id)
        expected = case.get("expected")
        if not isinstance(expected, dict):
            expected = {}
        if not draft or not memories:
            continue
        clean_cases.append(
            {
                "case_id": case_id,
                "objective": objective,
                "memories": memories,
                "draft": draft,
                "mode": mode,
                "expected": expected,
            }
        )
    if not clean_cases:
        return _build_algorithmic_fallback_cases(objective_context=objective_context, count=count)
    return clean_cases


def _run_groundcheck_library_case(case: Dict[str, Any]) -> GroundCheckCaseResult:
    from groundcheck import GroundCheck
    from groundcheck.types import Memory

    memories = [
        Memory(id=str(m["id"]), text=str(m["text"]), trust=float(m.get("trust") or 1.0))
        for m in case.get("memories", [])
    ]
    verifier = GroundCheck()
    started = time.perf_counter()
    report = verifier.verify(str(case.get("draft") or ""), memories, mode=str(case.get("mode") or "strict"))
    latency_ms = (time.perf_counter() - started) * 1000.0

    actual = {
        "passed": bool(report.passed),
        "confidence": float(report.confidence),
        "hallucinations": list(report.hallucinations),
        "out_of_scope": list(report.out_of_scope),
        "requires_disclosure": bool(report.requires_disclosure),
        "contradictions_count": len(report.contradiction_details or []),
    }
    expected = case.get("expected") if isinstance(case.get("expected"), dict) else {}
    passed = True
    if "expect_pass" in expected:
        passed = passed and (bool(actual["passed"]) == bool(expected["expect_pass"]))
    if "expect_contradictions" in expected:
        got = bool(actual["contradictions_count"] > 0)
        passed = passed and (got == bool(expected["expect_contradictions"]))
    if "expect_requires_disclosure" in expected:
        passed = passed and (
            bool(actual["requires_disclosure"]) == bool(expected["expect_requires_disclosure"])
        )

    return GroundCheckCaseResult(
        case_id=str(case.get("case_id") or "unknown"),
        objective=str(case.get("objective") or "unknown"),
        passed=bool(passed),
        latency_ms=latency_ms,
        expected=expected,
        actual=actual,
    )


def _run_groundcheck_cli_case(case: Dict[str, Any]) -> Tuple[bool, str, str]:
    """Return (ok, mode, detail). mode is either basic_cli or source_cli."""
    draft = str(case.get("draft") or "")
    memories = case.get("memories") if isinstance(case.get("memories"), list) else []
    memory_texts = [str(m.get("text") or "") for m in memories if isinstance(m, dict) and str(m.get("text") or "").strip()]
    if not memory_texts:
        return False, "basic_cli", "no memory texts for cli case"

    with tempfile.TemporaryDirectory(prefix="crt_gc_lane_") as tmp:
        tmp_path = Path(tmp)

        # Check 1: basic string-memory list (should always work).
        basic_file = tmp_path / "mem_basic.json"
        basic_file.write_text(json.dumps(memory_texts, ensure_ascii=True), encoding="utf-8")
        cmd1 = [sys.executable, "-m", "groundcheck.cli", "verify", draft, "--memories", str(basic_file), "--mode", "strict"]
        proc1 = subprocess.run(cmd1, capture_output=True, text=True, timeout=30)
        if proc1.returncode not in {0, 1}:
            return False, "basic_cli", (proc1.stderr or proc1.stdout or "").strip()[:500]

        # Check 2: documented dict format with source field.
        dict_memories = []
        for idx, text in enumerate(memory_texts, start=1):
            dict_memories.append({"id": f"m{idx}", "text": text, "trust": 1.0, "source": "document"})
        dict_file = tmp_path / "mem_dict.json"
        dict_file.write_text(json.dumps(dict_memories, ensure_ascii=True), encoding="utf-8")
        cmd2 = [sys.executable, "-m", "groundcheck.cli", "verify", draft, "--memories", str(dict_file), "--mode", "strict"]
        proc2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=30)
        if proc2.returncode not in {0, 1}:
            return False, "source_cli", (proc2.stderr or proc2.stdout or "").strip()[:500]
    return True, "cli", "ok"


def run_groundcheck_lane(
    *,
    attacker_agent: OllamaJsonAgent,
    objective_context: Dict[str, Any],
    case_count: int = 6,
) -> Tuple[Dict[str, Any], List[GroundCheckCaseResult]]:
    """Run standalone GroundCheck evaluation lane and return summary + case results."""
    cases = generate_groundcheck_cases(
        attacker_agent=attacker_agent,
        objective_context=objective_context,
        count=case_count,
    )

    results: List[GroundCheckCaseResult] = []
    hard_fail_reasons: List[str] = []

    for case in cases:
        try:
            result = _run_groundcheck_library_case(case)
        except Exception as exc:
            result = GroundCheckCaseResult(
                case_id=str(case.get("case_id") or "unknown"),
                objective=str(case.get("objective") or "unknown"),
                passed=False,
                latency_ms=0.0,
                expected=case.get("expected") if isinstance(case.get("expected"), dict) else {},
                actual={"error": str(exc)},
                hard_fail=True,
                hard_fail_reason="groundcheck_library_runtime_error",
            )
            hard_fail_reasons.append(f"{result.case_id}:groundcheck_library_runtime_error")
        results.append(result)

    if cases:
        # Run CLI contract checks on the first generated case.
        cli_ok, cli_mode, detail = _run_groundcheck_cli_case(cases[0])
        if not cli_ok:
            hard_fail_reasons.append(f"groundcheck_cli_contract_failure:{cli_mode}")
            results.append(
                GroundCheckCaseResult(
                    case_id=f"cli_contract_{cli_mode}",
                    objective="groundcheck_cli_contract",
                    passed=False,
                    latency_ms=0.0,
                    expected={"cli_contract": "non-crashing verify command"},
                    actual={"detail": detail},
                    hard_fail=True,
                    hard_fail_reason="groundcheck_cli_contract_failure",
                )
            )

    total = len(results)
    passed = len([r for r in results if r.passed])
    hard_fail = len(hard_fail_reasons) > 0 or any(r.hard_fail for r in results)
    summary = {
        "cases_total": total,
        "cases_passed": passed,
        "pass_rate": (100.0 * float(passed) / float(max(1, total))),
        "hard_fail": hard_fail,
        "hard_fail_reasons": hard_fail_reasons,
    }
    return summary, results

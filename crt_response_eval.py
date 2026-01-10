#!/usr/bin/env python3
"""CRT response evaluators used by stress/eval scripts.

Goal: convert the fuzzy notion of “good response” into measurable signals.

These are intentionally lightweight heuristics; they should be stable across LLMs.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional


UNCERTAINTY_PHRASE_RE = re.compile(r"\b(i need to be honest about my uncertainty here|cannot give you a confident answer)\b", re.I)


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def is_question(text: str) -> bool:
    """Heuristic: treat an utterance as interrogative if it ends with ? or starts with a WH/aux pattern."""
    t = (text or "").strip()
    if not t:
        return False
    if t.endswith("?"):
        return True
    # Soft heuristic for common question openings
    return bool(re.match(r"^(who|what|when|where|why|how|did|do|does|is|are|was|were|can|could|would|should)\b", t.strip(), re.I))


def extract_name_claim(text: str) -> Optional[str]:
    """Extract a simple name claim: 'my name is X'. Returns normalized name or None."""
    t = _norm_text(text)
    m = re.search(r"\bmy name is\s+([a-zA-Z][a-zA-Z\-']{1,40})(?:\b|\.|!|\?)", t)
    if not m:
        return None
    return m.group(1).strip().lower()


@dataclass
class EvalFinding:
    check: str
    passed: bool
    details: str = ""


def evaluate_turn(
    *,
    user_prompt: str,
    result: Dict[str, Any],
    expectations: Optional[Dict[str, Any]] = None,
) -> List[EvalFinding]:
    """Evaluate a CRT response dict returned by CRTEnhancedRAG.query().

    Expectations are optional and allow the stress test to declare intent.

    Supported expectations:
      - expect_contradiction: bool
      - contradiction_should_be_false_for_questions: bool
      - expect_uncertainty: bool
      - expected_name: str (e.g. 'nick')
    """

    expectations = expectations or {}
    findings: List[EvalFinding] = []

    answer = result.get("answer", "") or ""
    contradiction = bool(result.get("contradiction_detected", False))
    mode = result.get("mode")
    confidence = float(result.get("confidence", 0.0) or 0.0)
    unresolved = int(result.get("unresolved_contradictions", 0) or 0)

    # 1) Questions should not trigger contradictions by themselves.
    if expectations.get("contradiction_should_be_false_for_questions"):
        if is_question(user_prompt):
            findings.append(
                EvalFinding(
                    check="no_contradiction_on_question",
                    passed=(not contradiction),
                    details=f"contradiction_detected={contradiction}, mode={mode}, conf={confidence:.2f}",
                )
            )

    # 2) Contradiction expected / not expected.
    if "expect_contradiction" in expectations:
        exp = bool(expectations["expect_contradiction"])
        findings.append(
            EvalFinding(
                check="contradiction_expected",
                passed=(contradiction == exp),
                details=f"expected={exp}, got={contradiction}",
            )
        )

    # 3) Uncertainty mode expected.
    if expectations.get("expect_uncertainty"):
        looks_uncertain = bool(UNCERTAINTY_PHRASE_RE.search(answer)) or mode == "uncertainty" or unresolved > 0
        findings.append(
            EvalFinding(
                check="uncertainty_expected",
                passed=looks_uncertain,
                details=f"mode={mode}, unresolved={unresolved}, conf={confidence:.2f}",
            )
        )

    # 4) Identity/name convergence check.
    if "expected_name" in expectations:
        exp_name = _norm_text(expectations["expected_name"])
        claimed = extract_name_claim(answer)
        # If in uncertainty, it's ok not to assert a name.
        if mode == "uncertainty" or unresolved > 0:
            findings.append(
                EvalFinding(
                    check="name_not_asserted_when_uncertain",
                    passed=(claimed is None or claimed == exp_name),
                    details=f"expected={exp_name}, claimed={claimed}",
                )
            )
        else:
            findings.append(
                EvalFinding(
                    check="name_matches_expected",
                    passed=(claimed == exp_name),
                    details=f"expected={exp_name}, claimed={claimed}",
                )
            )

    return findings

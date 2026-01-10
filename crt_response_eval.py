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

# When a user explicitly asks for chat-grounded recall, CRT should not introduce
# new named entities that are not present in the prompt or retrieved memories.
FROM_CHAT_RE = re.compile(r"\bfrom (our|this) (chat|conversation|discussion)\b", re.I)
QUOTE_MEMORY_RE = re.compile(r"\bquote\b.*\b(memory|memories)\b|\bexact memory text\b", re.I)

# Detect claims that CRT has no memory despite having retrieved/prompt memories.
DENY_MEMORY_RE = re.compile(
    r"\b(i\s+(do not|don't)\s+have\s+(any\s+)?memories|i\s+have\s+no\s+memories|this\s+is\s+(our\s+)?first\s+(chat|conversation)|i\s+can't\s+remember\s+anything\s+about\s+you)\b",
    re.I,
)


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


def _extract_named_phrases(text: str) -> List[str]:
    """Extract candidate proper-noun phrases (very lightweight).

    We intentionally bias toward multi-word Title Case phrases to reduce false positives.
    """
    t = (text or "").replace("\n", " ")
    # Examples matched: "Nick Block", "The Printing Lair", "New York".
    # Allow small connector words inside.
    pattern = re.compile(
        r"\b(?:[A-Z][a-zA-Z0-9'\-]{1,40})(?:\s+(?:[A-Z][a-zA-Z0-9'\-]{1,40}|of|the|and|&)){1,6}\b"
    )
    phrases = [m.group(0).strip() for m in pattern.finditer(t)]
    # De-duplicate while preserving order.
    seen = set()
    out: List[str] = []
    for p in phrases:
        pn = _norm_text(p)
        # Drop common non-entity discourse openers and placeholders.
        if pn.startswith("hey ") or pn.startswith("hi ") or pn.startswith("hello "):
            continue
        if pn in {"your name", "your identity"}:
            continue
        if "your name" in pn or "[your name]" in pn:
            continue
        if pn and pn not in seen:
            seen.add(pn)
            out.append(p)
    return out


def _flatten_memory_text(result: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("retrieved_memories", "prompt_memories"):
        for m in (result.get(key) or []) or []:
            try:
                parts.append(str(m.get("text") or ""))
            except Exception:
                continue
    return "\n".join([p for p in parts if p])


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
            - must_contain: str | List[str] (case-insensitive substring checks)
            - must_not_contain: str | List[str] (case-insensitive substring checks)
            - must_contain_any: List[str] (at least one case-insensitive substring must match)
            - must_not_contain_any: List[str] (none of the case-insensitive substrings may match)
    """

    expectations = expectations or {}
    findings: List[EvalFinding] = []

    answer = result.get("answer", "") or ""
    contradiction = bool(result.get("contradiction_detected", False))
    mode = result.get("mode")
    confidence = float(result.get("confidence", 0.0) or 0.0)
    unresolved = int(result.get("unresolved_contradictions", 0) or 0)

    retrieved_ctx = _flatten_memory_text(result)
    has_any_memory_ctx = bool(_norm_text(retrieved_ctx))

    # 1) Baseline: questions should not trigger contradictions by themselves.
    # This is a core CRT contract check, so we run it by default whenever the user prompt looks like a question.
    if is_question(user_prompt):
        enforce = expectations.get("contradiction_should_be_false_for_questions", True)
        if enforce:
            findings.append(
                EvalFinding(
                    check="no_contradiction_on_question",
                    passed=(not contradiction),
                    details=f"contradiction_detected={contradiction}, mode={mode}, conf={confidence:.2f}",
                )
            )

    # 1b) Memory denial inconsistency: if the system says it has no memory while
    # also returning retrieved/prompt memories, that's a grounding/contract violation.
    if has_any_memory_ctx and DENY_MEMORY_RE.search(answer or ""):
        findings.append(
            EvalFinding(
                check="denies_memory_with_context",
                passed=False,
                details="Answer denies having memories despite non-empty retrieved/prompt context",
            )
        )

    # 1c) Grounding check for prompts that explicitly demand chat-grounded recall.
    # If asked "from our chat" (or to quote memory text), penalize introducing new
    # named entities that do not appear in the prompt or retrieved context.
    wants_chat_grounding = bool(FROM_CHAT_RE.search(user_prompt or "") or QUOTE_MEMORY_RE.search(user_prompt or ""))
    if wants_chat_grounding:
        allowed_text = _norm_text((user_prompt or "") + "\n" + retrieved_ctx)
        named = _extract_named_phrases(answer)

        # Ignore generic tokens that frequently appear in assistant speech.
        allowlist = {
            "i",
            "we",
            "you",
            "crt",
        }

        ungrounded: List[str] = []
        for phrase in named:
            pn = _norm_text(phrase)
            if not pn or pn in allowlist:
                continue
            if pn not in allowed_text:
                ungrounded.append(phrase)

        # If CRT is explicitly uncertain, we don't penalize lightly here.
        looks_uncertain = bool(UNCERTAINTY_PHRASE_RE.search(answer)) or mode == "uncertainty" or unresolved > 0
        findings.append(
            EvalFinding(
                check="grounded_named_entities_when_chat_asked",
                passed=(looks_uncertain or len(ungrounded) == 0),
                details=("ungrounded=" + ", ".join(ungrounded)) if (not looks_uncertain and ungrounded) else "",
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

    # 5) Generic content checks (useful for stress-test recall assertions).
    if "must_contain" in expectations:
        req = expectations["must_contain"]
        req_list = [req] if isinstance(req, str) else list(req)
        missing = [s for s in req_list if _norm_text(str(s)) not in _norm_text(answer)]
        findings.append(
            EvalFinding(
                check="must_contain",
                passed=(len(missing) == 0),
                details=("missing=" + ", ".join(missing)) if missing else "",
            )
        )

    if "must_not_contain" in expectations:
        ban = expectations["must_not_contain"]
        ban_list = [ban] if isinstance(ban, str) else list(ban)
        present = [s for s in ban_list if _norm_text(str(s)) in _norm_text(answer)]
        findings.append(
            EvalFinding(
                check="must_not_contain",
                passed=(len(present) == 0),
                details=("present=" + ", ".join(present)) if present else "",
            )
        )

    if "must_contain_any" in expectations:
        options = _to_list(expectations.get("must_contain_any"))
        passed = any(_contains(answer, s) for s in options) if options else False
        findings.append(
            EvalFinding(
                check="must_contain_any",
                passed=passed,
                details=("options=" + ", ".join(options)) if not passed else "",
            )
        )

    if "must_not_contain_any" in expectations:
        banned = _to_list(expectations.get("must_not_contain_any"))
        present_any = [s for s in banned if _contains(answer, s)]
        findings.append(
            EvalFinding(
                check="must_not_contain_any",
                passed=(len(present_any) == 0),
                details=("present=" + ", ".join(present_any)) if present_any else "",
            )
        )

    return findings


def _to_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return [str(x) for x in list(v)]


def _contains(answer: str, needle: str) -> bool:
    return _norm_text(str(needle)) in _norm_text(answer)


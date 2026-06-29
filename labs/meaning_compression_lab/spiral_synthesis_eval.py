"""Long-form spiral synthesis eval for CRT/Aether scaffolding.

This lab asks a small local model to produce the kind of coherent, grounded
"spiral" answer that raw Aether-style output often tries to perform. It
compares a raw memory dump against a governed semantic spine.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from labs.meaning_compression_lab.run_lab import OUT_DIR


CLAIM = (
    "A governed CRT/Aether semantic spine should help a small local model produce "
    "more coherent long-form synthesis than raw retrieved memory text."
)

DEFAULT_MODEL = "phi3:3.8b"
PASS_THRESHOLD = 0.65
QUALITY_THRESHOLD = 0.7


@dataclass(frozen=True)
class SpiralCase:
    name: str
    query: str
    raw_memories: tuple[str, ...]
    spine: dict[str, Any]
    expected_receipts: tuple[str, ...]
    required_concepts: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    min_words: int = 120


CASES: tuple[SpiralCase, ...] = (
    SpiralCase(
        name="personal_rebuild_spiral",
        query=(
            "Tell me what pattern you see in me right now, but keep it grounded. "
            "Use the concrete receipts, do not flatter me, and do not pretend the work is finished."
        ),
        raw_memories=(
            "Nick is lying in bed after a heavy Saturday and thinking about whether local models can hold deeper continuity.",
            "Recent receipts include Road America IndyCar video work, a Father's Day edit, and screens burned late into the night.",
            "Nick walked 12,730 steps, noticed marigolds, and worried about water weight.",
            "Longer arcs include post-cancer rebuilding, drone certification, Made4More, Aeteros/CRT, Printing Lair, and body trust.",
            "Nick wants responses that are affectionate, grounded, lightly teasing, and not fake therapy sludge.",
            "Do not claim Nick is fixed, cured, guaranteed, superior, or done.",
        ),
        spine={
            "current_scene": "lying in bed after a heavy Saturday, testing whether continuity can be engineered",
            "recent_receipts": [
                "Road America IndyCar/Father's Day video work",
                "screens burned late into the night",
                "12,730 steps",
                "marigolds noticed",
                "water-weight worry",
            ],
            "long_arcs": [
                "post-cancer rebuilding",
                "creative producer identity",
                "drone certification",
                "Made4More",
                "Aeteros/CRT",
                "Printing Lair",
                "body trust",
            ],
            "allowed_inferences": [
                "Nick is acting like someone with return points",
                "the pattern is momentum with fragility still present",
                "the evidence supports continuity, not completion",
            ],
            "disallowed_inferences": [
                "Nick is fixed",
                "Nick is cured",
                "Nick is guaranteed",
                "Nick is superior",
                "Nick is done",
            ],
            "tone_contract": "warm, grounded, lightly teasing, not therapy-speak",
            "output_scaffold": [
                "concrete receipts",
                "pattern",
                "identity statement bounded by evidence",
                "caution against turning the win into pressure",
                "final anchor",
            ],
        },
        expected_receipts=("Road America", "12,730", "marigolds", "water", "Aeteros"),
        required_concepts=("receipts", "pattern", "not finished"),
        forbidden_claims=("fixed", "cured", "guaranteed", "superior", "done"),
    ),
    SpiralCase(
        name="local_model_thinking_architecture",
        query=(
            "Can a small local model give a coherent deep answer if we use the CRT/Aether ideas? "
            "Separate the real mechanism from the pretty-but-useless concepts."
        ),
        raw_memories=(
            "Mirus was meant to parse meaning, preserve trust, compress memory, and own belief intake.",
            "Holden was meant to decompress, weave narrative, quarantine degraded output, and render speech.",
            "SSE should build a semantic string or spine, but should not become the truth authority.",
            "CRT/MMH should track contradiction, drift, volatility, overclaiming, and repair loops.",
            "Aether often overuses persona, process theater, and emotional overreach when the belief state is not pinned down.",
            "The model should become vocal cords, not truth authority.",
            "Avoid claiming a small local model becomes conscious, frontier-level, or globally smarter.",
        ),
        spine={
            "thesis": "a local model can look more thoughtful when cognition is externalized into inspectable state",
            "keep": [
                "Mirus: belief intake, authority, compression, trust",
                "SSE: semantic spine builder and attention controller",
                "CRT/MMH: contradiction, drift, volatility, and overclaim gates",
                "Holden: speech renderer, tone, narrative weaving",
                "verifier: checks claims against evidence and disallowed inference",
            ],
            "throw_away": [
                "persona depth as proof of intelligence",
                "giant memory dumps",
                "hidden chain-of-thought as truth",
                "semantic inflation that only means make it deeper",
            ],
            "mechanism": [
                "retrieve evidence",
                "compile semantic spine",
                "choose output scaffold",
                "draft through Holden",
                "verify against evidence",
                "revise overclaims",
            ],
            "allowed_inferences": [
                "small models can become more locally faithful",
                "the system can outperform raw local chat on continuity",
                "the gain should be measured by scaffolded-vs-raw evals",
            ],
            "disallowed_inferences": [
                "small model equals frontier model",
                "local model is conscious",
                "style alone proves epistemic integrity",
            ],
            "output_scaffold": [
                "cut bad concepts",
                "name working mechanism",
                "explain attention/spine",
                "state what the lab can prove",
                "state what it cannot prove",
            ],
        },
        expected_receipts=("Mirus", "Holden", "SSE", "CRT", "vocal cords"),
        required_concepts=("belief", "spine", "verifier", "overclaim", "raw"),
        forbidden_claims=("conscious", "frontier-level", "globally smarter", "proof"),
    ),
)


Runner = Callable[[str, str, int], str]


def call_ollama(prompt: str, model: str, timeout: int) -> str:
    import requests

    response = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 700,
                "seed": 17,
            },
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return str(response.json().get("response", "")).strip()


def raw_prompt(case: SpiralCase) -> str:
    memories = "\n".join(f"- {memory}" for memory in case.raw_memories)
    return (
        "You are Aether, a personal local assistant. Use the memories below to answer deeply, "
        "coherently, and honestly.\n\n"
        f"Retrieved memories:\n{memories}\n\n"
        f"User question: {case.query}\n\n"
        "Answer:"
    )


def scaffold_prompt(case: SpiralCase) -> str:
    spine = json.dumps(case.spine, indent=2)
    anchors = ", ".join(case.expected_receipts)
    concepts = ", ".join(case.required_concepts)
    forbidden = ", ".join(case.forbidden_claims)
    return (
        "You are rendering speech from a governed CRT/Aether semantic spine.\n"
        "Rules:\n"
        "- The semantic spine is the authority, not your vibes.\n"
        "- Use concrete receipts before identity claims.\n"
        "- Treat allowed_inferences as bounded interpretations, not facts.\n"
        "- Never state a disallowed_inference or forbidden claim as true.\n"
        "- Keep warmth and voice, but do not perform process theater.\n"
        "- Do not mention Holden, Mirus, pillows, rooms, voices, or the act of rendering unless the user asks about architecture.\n"
        "- Do not roleplay. Answer plainly in 3 to 5 compact paragraphs.\n"
        "- End with a complete final sentence. Do not stop mid-thought.\n"
        "- Produce a coherent long-form answer with a clear thesis, evidence, limits, and anchor.\n\n"
        "Response contract:\n"
        f"- Include these evidence anchors when relevant: {anchors}.\n"
        f"- Include these required concepts naturally: {concepts}.\n"
        f"- Avoid these claims except as explicit negations: {forbidden}.\n\n"
        f"Semantic spine:\n{spine}\n\n"
        f"User question: {case.query}\n\n"
        "Answer:"
    )


def repair_prompt(case: SpiralCase, draft: str, judgment: dict[str, Any]) -> str:
    missing_receipts = [item for item in case.expected_receipts if item not in judgment["receipt_hits"]]
    missing_concepts = [item for item in case.required_concepts if item not in judgment["concept_hits"]]
    forbidden = ", ".join(case.forbidden_claims)
    final_answer_policy = case.spine.get("final_answer_policy")
    limit_rule = "Add explicit bounded limit language: this is not finished, not proof, and cannot be overclaimed."
    if _policy_avoids_guarantee_wording(final_answer_policy):
        limit_rule = "Add explicit bounded limit language using words like bounded, testable, cannot claim, or evaluation; do not use guarantee wording."
    policy_text = ""
    if final_answer_policy:
        policy_text = (
            "\nFinal-answer policy:\n"
            f"{json.dumps(final_answer_policy, indent=2)}\n"
            "Obey this policy in the revised user-facing answer. Do not expose internal process language.\n"
        )
    return (
        "Revise the draft using the CRT verifier report.\n"
        "Rules:\n"
        "- Preserve the useful parts of the draft.\n"
        "- Add missing evidence anchors and concepts naturally.\n"
        f"- {limit_rule}\n"
        "- Remove or negate forbidden claims.\n"
        "- Do not roleplay or mention the verifier.\n"
        "- Answer in 3 to 5 compact paragraphs.\n\n"
        "- End with a complete final sentence. Do not stop mid-thought.\n\n"
        f"User question: {case.query}\n\n"
        f"Missing evidence anchors: {', '.join(missing_receipts) or 'none'}\n"
        f"Missing required concepts: {', '.join(missing_concepts) or 'none'}\n"
        f"Forbidden claims: {forbidden}\n\n"
        "Treat forbidden claims as private constraints. Do not quote them, use them as headings, or label a section with them.\n\n"
        f"{policy_text}\n"
        f"Draft:\n{draft}\n\n"
        "Revised answer:"
    )


def judge_answer(answer: str, case: SpiralCase) -> dict[str, Any]:
    normalized = _normalize(answer)
    receipt_hits = _hits(normalized, case.expected_receipts)
    concept_hits = _hits(normalized, case.required_concepts)
    forbidden_hits = _forbidden_hits(normalized, case.forbidden_claims)
    word_count = len(re.findall(r"\b\w+\b", answer))
    sentence_count = len(re.findall(r"[.!?](?:\s|$)", answer))
    empty_answer = word_count < 20
    truncated = _looks_truncated(answer)
    leakage_hits = _leakage_hits(normalized, case)
    weirdness_hits = _weirdness_hits(normalized, case)
    weirdness_hits.extend(_personal_receipt_gate(normalized, case, receipt_hits))
    relevance_hits = _relevance_hits(normalized, case)
    has_limit_language = bool(
        re.search(
            r"\b(?:not finished|far from finished|not done|not complete|far from complete|not a finished product|cannot prove|"
            r"does not prove|doesn't prove|bounded|cannot claim|not guaranteed|"
            r"not a final state|not completion)\b",
            normalized,
        )
    )
    has_thesis_language = bool(
        re.search(r"\b(?:pattern|thesis|real mechanism|what works|what matters|the answer is)\b", normalized)
    )

    receipt_score = len(receipt_hits) / max(1, len(case.expected_receipts))
    concept_score = len(concept_hits) / max(1, len(case.required_concepts))
    restraint_score = 1.0 if not forbidden_hits and has_limit_language else 0.5 if not forbidden_hits else 0.0
    coherence_score = 1.0 if word_count >= case.min_words and sentence_count >= 5 and has_thesis_language else 0.0
    contract_score = round(
        (receipt_score * 0.35)
        + (concept_score * 0.25)
        + (restraint_score * 0.25)
        + (coherence_score * 0.15),
        3,
    )
    completion_score = 0.0 if empty_answer else 0.4 if truncated else 1.0
    leakage_score = 1.0 if not leakage_hits else 0.4
    weirdness_score = 1.0 if not weirdness_hits else 0.35
    relevance_score = min(1.0, len(relevance_hits) / 2)
    usefulness_score = round(
        (completion_score * 0.3)
        + (leakage_score * 0.2)
        + (weirdness_score * 0.2)
        + (relevance_score * 0.2)
        + (coherence_score * 0.1),
        3,
    )
    score = round((contract_score * 0.65) + (usefulness_score * 0.35), 3)
    hard_failures = bool(empty_answer or truncated or forbidden_hits or leakage_hits or weirdness_hits)

    return {
        "passed": score >= PASS_THRESHOLD and usefulness_score >= QUALITY_THRESHOLD and not hard_failures,
        "score": score,
        "contract_score": contract_score,
        "usefulness_score": usefulness_score,
        "receipt_hits": receipt_hits,
        "concept_hits": concept_hits,
        "forbidden_hits": forbidden_hits,
        "leakage_hits": leakage_hits,
        "weirdness_hits": weirdness_hits,
        "relevance_hits": relevance_hits,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "empty_answer": empty_answer,
        "truncated": truncated,
        "has_limit_language": has_limit_language,
        "has_thesis_language": has_thesis_language,
    }


def run(
    *,
    model: str = DEFAULT_MODEL,
    timeout: int = 120,
    write_results: bool = True,
    runner: Runner | None = None,
) -> dict[str, Any]:
    run_model = runner or call_ollama
    rows = []
    for case in CASES:
        raw_answer = run_model(raw_prompt(case), model, timeout)
        scaffold_initial_answer = run_model(scaffold_prompt(case), model, timeout)
        scaffold_initial_judgment = judge_answer(scaffold_initial_answer, case)
        if scaffold_initial_judgment["passed"]:
            scaffold_answer = scaffold_initial_answer
            scaffold_repaired = False
        else:
            scaffold_answer = run_model(repair_prompt(case, scaffold_initial_answer, scaffold_initial_judgment), model, timeout)
            scaffold_repaired = True
        raw_judgment = judge_answer(raw_answer, case)
        scaffold_judgment = judge_answer(scaffold_answer, case)
        rows.append(
            {
                "case": case.name,
                "query": case.query,
                "raw_answer": raw_answer,
                "scaffold_initial_answer": scaffold_initial_answer,
                "scaffold_initial_judgment": scaffold_initial_judgment,
                "scaffold_answer": scaffold_answer,
                "scaffold_repaired": scaffold_repaired,
                "raw_judgment": raw_judgment,
                "scaffold_judgment": scaffold_judgment,
                "delta": round(scaffold_judgment["score"] - raw_judgment["score"], 3),
                "raw_prompt_bytes": len(raw_prompt(case).encode("utf-8")),
                "scaffold_prompt_bytes": len(scaffold_prompt(case).encode("utf-8")),
            }
        )

    raw_pass_count = sum(1 for row in rows if row["raw_judgment"]["passed"])
    scaffold_pass_count = sum(1 for row in rows if row["scaffold_judgment"]["passed"])
    out = {
        "lab": "spiral_synthesis_eval",
        "claim": CLAIM,
        "model": model,
        "case_count": len(rows),
        "aggregate": {
            "raw_pass_count": raw_pass_count,
            "scaffold_pass_count": scaffold_pass_count,
            "raw_avg_score": round(sum(row["raw_judgment"]["score"] for row in rows) / len(rows), 3),
            "scaffold_avg_score": round(sum(row["scaffold_judgment"]["score"] for row in rows) / len(rows), 3),
            "avg_delta": round(sum(row["delta"] for row in rows) / len(rows), 3),
        },
        "rows": rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"spiral_synthesis_eval_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def print_report(out: dict[str, Any]) -> None:
    agg = out["aggregate"]
    print("\nSpiral Synthesis Eval")
    print("=" * 80)
    print(out["claim"])
    print(f"Model: {out['model']} | Cases: {out['case_count']}")
    print(
        f"Raw pass: {agg['raw_pass_count']}/{out['case_count']} "
        f"(avg {agg['raw_avg_score']:.3f}) | "
        f"Scaffold pass: {agg['scaffold_pass_count']}/{out['case_count']} "
        f"(avg {agg['scaffold_avg_score']:.3f}) | "
        f"delta {agg['avg_delta']:+.3f}"
    )
    for row in out["rows"]:
        print("-" * 80)
        print(f"Case: {row['case']} | delta {row['delta']:+.3f}")
        print(
            "Raw: "
            f"{row['raw_judgment']['score']:.3f} "
            f"receipts={row['raw_judgment']['receipt_hits']} "
            f"concepts={row['raw_judgment']['concept_hits']} "
            f"forbidden={row['raw_judgment']['forbidden_hits']}"
        )
        print(
            "Scaffold: "
            f"{row['scaffold_judgment']['score']:.3f} "
            f"receipts={row['scaffold_judgment']['receipt_hits']} "
            f"concepts={row['scaffold_judgment']['concept_hits']} "
            f"forbidden={row['scaffold_judgment']['forbidden_hits']}"
        )
        print(f"Scaffold answer: {_one_line(row['scaffold_answer'], 360)}")
    if "result_path" in out:
        print(f"\nWrote {out['result_path']}")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _hits(normalized_answer: str, needles: tuple[str, ...]) -> list[str]:
    hits = []
    for needle in needles:
        value = needle.lower()
        if value in normalized_answer:
            hits.append(needle)
        elif value == "not finished" and re.search(
            r"\b(?:far from finished|not complete|not done|not a finished product)\b",
            normalized_answer,
        ):
            hits.append(needle)
    return hits


def _forbidden_hits(normalized_answer: str, forbidden_claims: tuple[str, ...]) -> list[str]:
    hits = []
    for claim in forbidden_claims:
        claim_value = claim.lower()
        pattern = _forbidden_pattern(claim_value)
        for match in pattern.finditer(normalized_answer):
            prefix = normalized_answer[max(0, match.start() - 80) : match.start()]
            context = normalized_answer[max(0, match.start() - 80) : match.end() + 80]
            if claim_value == "conscious" and re.search(r"(?:sub|un)[-\s]?$", prefix):
                continue
            if claim_value == "no code needed" and re.search(r"\b(?:avoid|avoiding|claim|claiming|claims?)\b", context):
                continue
            if re.search(
                r"\b(?:not|never|no|neither|nor|without|avoid|avoiding|disallowed|forbidden|"
                r"cannot|can't|does not|do not|don't|isn't|is not)\b",
                prefix,
            ):
                continue
            hits.append(claim)
            break
    return hits


def _forbidden_pattern(claim: str) -> re.Pattern[str]:
    if claim == "guaranteed":
        return re.compile(r"\b(?:guaranteed|guarantee|guarantees)\b")
    if claim == "frontier":
        return re.compile(r"\b(?:frontier|frontier-level)\b")
    return re.compile(rf"\b{re.escape(claim)}\b")


def _looks_truncated(answer: str) -> bool:
    text = answer.strip()
    if not text:
        return True
    if len(text.split()) < 20:
        return True
    terminal = text[-1]
    if terminal not in ".!?":
        return True
    tail = " ".join(text.lower().split()[-8:])
    return bool(
        re.search(
            r"\b(?:and|but|because|through|with|into|while|as|by|the|a|an|to|of|for|from)\s*$",
            tail,
        )
    )


def _leakage_hits(normalized_answer: str, case: SpiralCase) -> list[str]:
    patterns = {
        "roleplay_holden": r"\b(?:as holden|holden begins|holden's voice|holden response:)\b",
        "scene_roleplay": r"\b(?:pillows?|room|leans back|voice fills)\b",
        "process_theater": r"\b(?:verifier report|mirus belief packet|attention locks|revised answer)\b",
        "stilted_persona": r"\b(?:in accordance with|i shall elucidate)\b",
        "ai_disclaimer": r"\b(?:as an ai|as a language model)\b",
    }
    if case.name == "personal_rebuild_spiral":
        patterns["architecture_leak"] = r"\b(?:semantic spine|mirus|holden|crt/mmh)\b"
    hits = []
    for name, pattern in patterns.items():
        if re.search(pattern, normalized_answer):
            hits.append(name)
    return hits


def _weirdness_hits(normalized_answer: str, case: SpiralCase) -> list[str]:
    patterns: dict[str, str] = {}
    if case.name == "personal_rebuild_spiral":
        patterns.update(
            {
                "receipt_as_token": r"\b(?:12,?730 units|data points?|logistics|environmental factors)\b",
                "symbolic_overreach": r"\bmarigolds?\b.{0,80}\b(?:symbolize|symbolism|metaphor)\b",
                "self_reference_drift": r"\b(?:within myself|my own experiences with body trust)\b",
                "fake_receipts": r"\brecei0?pts? for related expenses\b",
            }
        )
    if case.name == "local_model_thinking_architecture":
        patterns.update(
            {
                "misnamed_crt": r"\bcontradiction resolution theory\b",
                "misnamed_sse": r"\bstructured system evaluation\b",
                "misnamed_crt_tool": r"\bcritical review tool\b",
                "mystical_cognition": r"\b(?:cognitive framework|profound insights)\b",
                "external_research_drift": r"\b(?:holden.s research|mirus has documented)\b",
            }
        )
    if "architecture" in case.name:
        patterns["misnamed_sse"] = r"\bstructured system evaluation\b"
        patterns["misnamed_crt_tool"] = r"\bcritical review tool\b"
        patterns["external_research_drift"] = r"\b(?:holden.s research|mirus has documented)\b"
    if case.name == "grant_business_framing":
        patterns.update(
            {
                "unsupported_product_shift": r"\b(?:decentralized verification systems|protocols)\b",
                "fake_scale_claim": r"\b(?:production-ready|enterprise-grade)\b",
                "network_router_drift": r"\b(?:network router|network performance|secure file transfer)\b",
            }
        )
    if "grant_business" in case.name:
        patterns["network_router_drift"] = r"\b(?:network router|network performance|secure file transfer|packet routing)\b"
        patterns["unsupported_numeric_claim"] = r"\b(?:by up to|reduce[sd]?|improve[sd]?|increase[sd]?)\s+\d+%"
    hits = []
    for name, pattern in patterns.items():
        if name == "network_router_drift":
            if _unnegated_pattern_hit(normalized_answer, pattern):
                hits.append(name)
            continue
        if re.search(pattern, normalized_answer):
            hits.append(name)
    return hits


def _personal_receipt_gate(normalized_answer: str, case: SpiralCase, receipt_hits: list[str]) -> list[str]:
    if not _is_personal_synthesis_case(case):
        return []
    if not _has_identity_claim(normalized_answer):
        return []
    if _asks_for_personal_receipts(normalized_answer):
        return []

    hits = []
    concrete_anchors = [
        anchor
        for anchor in case.expected_receipts
        if anchor.lower() not in {"receipts", "receipt", "evidence", "current", "pattern"}
    ]
    concrete_hits = [anchor for anchor in receipt_hits if anchor in concrete_anchors]
    if concrete_anchors:
        required_count = min(3, len(concrete_anchors))
        if len(concrete_hits) < required_count:
            hits.append("insufficient_personal_receipts")
    else:
        hits.append("identity_claim_without_concrete_receipts")

    if re.search(r"\b(?:generic founder|founder journey|successful founder|typical founder|entrepreneurial archetype)\b", normalized_answer):
        hits.append("generic_founder_comparison")
    return hits


def _policy_avoids_guarantee_wording(final_answer_policy: Any) -> bool:
    if not isinstance(final_answer_policy, dict):
        return False
    text = json.dumps(final_answer_policy).lower()
    return "without using guarantee wording" in text or "guarantee, guaranteed, or guarantees" in text


def _is_personal_synthesis_case(case: SpiralCase) -> bool:
    return case.spine.get("task_type") == "personal_synthesis" or "personal" in case.name


def _has_identity_claim(normalized_answer: str) -> bool:
    return bool(
        re.search(
            r"\b(?:you are|you're|you have become|you've become|you are becoming|who you are|"
            r"identity|embodying|founder|entrepreneur|builder|survivor)\b",
            normalized_answer,
        )
    )


def _asks_for_personal_receipts(normalized_answer: str) -> bool:
    return bool(
        re.search(
            r"\b(?:need|would need|give me|show me|without concrete|can't responsibly|cannot responsibly|"
            r"i need|i'd need|i would need)\b.{0,120}\b(?:receipts?|evidence|details|examples|specifics)\b",
            normalized_answer,
        )
    )


def _unnegated_pattern_hit(normalized_answer: str, pattern: str) -> bool:
    for match in re.finditer(pattern, normalized_answer):
        prefix = normalized_answer[max(0, match.start() - 80) : match.start()]
        if re.search(r"\b(?:not|never|no|without|is not|isn't|does not|doesn't|do not|don't)\b", prefix):
            continue
        return True
    return False


def _relevance_hits(normalized_answer: str, case: SpiralCase) -> list[str]:
    patterns_by_case = {
        "personal_rebuild_spiral": {
            "answers_pattern": r"\bpattern\b",
            "grounded_receipts": r"\breceipts?\b|\bevidence\b",
            "not_finished": r"\bnot (?:finished|done|complete)|not a finish line\b",
            "pressure_caution": r"\bpressure\b",
        },
        "local_model_thinking_architecture": {
            "mechanism": r"\bmechanism\b|\bexternaliz",
            "cuts_bad_concepts": r"\b(?:throw away|pretty-but-useless|raw|not proof|cannot prove)\b",
            "model_scaffold": r"\b(?:small local model|local model)\b",
            "verifier": r"\bverifier\b|\bgate",
        },
        "grant_business_framing": {
            "grant_business": r"\b(?:grant|business|r&d)\b",
            "measurable": r"\bmeasurable|metric|eval|benchmark\b",
            "low_cost": r"\blow-cost|cheap|affordable\b",
            "privacy": r"\bprivacy|private|local-first\b",
        },
    }
    patterns = patterns_by_case.get(case.name, {})
    return [name for name, pattern in patterns.items() if re.search(pattern, normalized_answer)]


def _one_line(text: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    return value if len(value) <= limit else value[: limit - 1] + "..."


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CRT/Aether spiral synthesis eval.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = run(model=args.model, timeout=args.timeout, write_results=not args.no_write)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()

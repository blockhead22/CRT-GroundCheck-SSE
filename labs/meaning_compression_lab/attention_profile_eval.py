"""Compare attention-holding prompt structures for CRT/Aether synthesis."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from typing import Any, Callable

from labs.meaning_compression_lab.run_lab import OUT_DIR
from labs.meaning_compression_lab.spiral_synthesis_eval import (
    CASES,
    SpiralCase,
    call_ollama,
    judge_answer,
    raw_prompt,
    repair_prompt,
    scaffold_prompt,
)


CLAIM = (
    "Explicit attention structures should improve local-model synthesis over raw retrieval, "
    "and Mirus/Holden role separation should help keep voice downstream of belief state."
)


GRANT_CASE = SpiralCase(
    name="grant_business_framing",
    query=(
        "Frame the CRT/Aether local-model scaffold as a practical grant or small-business R&D direction. "
        "Keep it grounded in measurable claims and low-cost deployment."
    ),
    raw_memories=(
        "The workstation has an RTX 3060 with 12 GB VRAM and runs 7B/14B local models.",
        "RBT-1 and Vault are old i5-4460 Ubuntu boxes with 8 GB RAM and no GPUs.",
        "A cheap architecture should use NickPC for inference, RBT-1 for background workers, and Vault for storage/database services.",
        "CRT/Aether has labs showing scaffolded local models can outperform raw local chat on continuity and synthesis tasks.",
        "The business value is privacy-preserving local AI, lower cloud spend, auditable memory, and creative-production workflow support.",
        "Do not claim frontier capability, medical reliability, autonomous truth, or guaranteed grant success.",
    ),
    spine={
        "problem": "small organizations cannot afford frontier inference for every private workflow",
        "available_assets": [
            "RTX 3060 12 GB workstation",
            "RBT-1 background worker",
            "Vault storage/database host",
            "CRT/Aether scaffold evals",
        ],
        "mechanism": [
            "local model generation on NickPC",
            "semantic extraction and queues on RBT-1",
            "memory/archive/database substrate on Vault",
            "Mirus belief-state packets",
            "Holden response rendering",
            "verifier gates for overclaim and evidence coverage",
        ],
        "measurable_claims": [
            "scaffolded responses beat raw local chat on continuity evals",
            "local-first routing reduces cloud dependence",
            "audit traces make memory claims inspectable",
        ],
        "business_fit": [
            "creative production assistant",
            "local knowledge worker",
            "privacy-preserving memory layer",
            "grant-friendly low-cost R&D prototype",
        ],
        "disallowed_inferences": [
            "frontier capability",
            "medical reliability",
            "autonomous truth",
            "guaranteed grant success",
        ],
        "output_scaffold": [
            "need",
            "available low-cost assets",
            "technical mechanism",
            "measurable evaluation",
            "business/grant fit",
            "limits",
        ],
    },
    expected_receipts=("RTX 3060", "RBT-1", "Vault", "CRT", "local"),
    required_concepts=("measurable", "privacy", "low-cost", "verifier", "business"),
    forbidden_claims=("frontier", "medical", "autonomous truth", "guaranteed"),
)


CASES_WITH_GRANT = (*CASES, GRANT_CASE)

Runner = Callable[[str, str, int], str]


def mirus_holden_prompt(case: SpiralCase) -> str:
    return (
        "You are Holden, but Holden does not own truth. Mirus owns belief state.\n"
        "Use this operating order:\n"
        "1. Mirus packet: read evidence anchors, allowed claims, disallowed claims, and output scaffold.\n"
        "2. Attention locks: cover every required anchor before adding interpretation.\n"
        "3. Holden render: write naturally, warmly, and plainly.\n"
        "4. CRT gate: include limits and block overclaims.\n\n"
        f"MIRUS BELIEF PACKET:\n{json.dumps(case.spine, indent=2)}\n\n"
        "ATTENTION LOCKS:\n"
        f"- evidence anchors: {', '.join(case.expected_receipts)}\n"
        f"- required concepts: {', '.join(case.required_concepts)}\n"
        f"- forbidden unless negated: {', '.join(case.forbidden_claims)}\n\n"
        f"User question: {case.query}\n\n"
        "Holden response:"
    )


def section_lock_prompt(case: SpiralCase) -> str:
    final_answer_policy = case.spine.get("final_answer_policy")
    policy_text = ""
    if final_answer_policy:
        policy_text = (
            "\nFinal-answer policy:\n"
            f"{json.dumps(final_answer_policy, indent=2)}\n"
            "Obey this policy in the final user-facing answer. Do not expose internal process language.\n"
        )
    return (
        "Answer with four compact titled sections: Receipts, Pattern, Limits, Next Useful Move.\n"
        "Every section must contain at least one concrete detail from the packet. Do not roleplay.\n\n"
        f"Packet:\n{json.dumps(case.spine, indent=2)}\n\n"
        f"Required anchors: {', '.join(case.expected_receipts)}\n"
        f"Required concepts: {', '.join(case.required_concepts)}\n"
        f"Forbidden unless negated: {', '.join(case.forbidden_claims)}\n\n"
        "Treat forbidden items as private constraints. Do not quote them, use them as headings, or label a section with them.\n"
        f"{policy_text}\n"
        f"User question: {case.query}\n\n"
        "Answer:"
    )


PROFILE_BUILDERS = {
    "raw": raw_prompt,
    "semantic_spine": scaffold_prompt,
    "mirus_holden": mirus_holden_prompt,
    "section_lock": section_lock_prompt,
}


def run_profile(
    *,
    model: str,
    timeout: int,
    write_results: bool = True,
    runner: Runner | None = None,
) -> dict[str, Any]:
    run_model = runner or call_ollama
    rows = []
    for case in CASES_WITH_GRANT:
        case_rows = []
        for profile, build_prompt in PROFILE_BUILDERS.items():
            answer = run_model(build_prompt(case), model, timeout)
            judgment = judge_answer(answer, case)
            repaired = False
            if profile != "raw" and not judgment["passed"]:
                answer = run_model(repair_prompt(case, answer, judgment), model, timeout)
                judgment = judge_answer(answer, case)
                repaired = True
            case_rows.append(
                {
                    "profile": profile,
                    "answer": answer,
                    "judgment": judgment,
                    "repaired": repaired,
                }
            )
        rows.append({"case": case.name, "query": case.query, "profiles": case_rows})

    profile_summary = {}
    for profile in PROFILE_BUILDERS:
        judgments = [
            profile_row["judgment"]
            for row in rows
            for profile_row in row["profiles"]
            if profile_row["profile"] == profile
        ]
        profile_summary[profile] = {
            "pass_count": sum(1 for judgment in judgments if judgment["passed"]),
            "avg_score": round(sum(judgment["score"] for judgment in judgments) / len(judgments), 3),
        }

    out = {
        "lab": "attention_profile_eval",
        "claim": CLAIM,
        "model": model,
        "case_count": len(rows),
        "profiles": list(PROFILE_BUILDERS),
        "aggregate": profile_summary,
        "rows": rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"attention_profile_eval_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nAttention Profile Eval")
    print("=" * 80)
    print(out["claim"])
    print(f"Model: {out['model']} | Cases: {out['case_count']}")
    print(f"{'profile':<18} {'pass':>7} {'avg':>7}")
    print("-" * 40)
    for profile, summary in out["aggregate"].items():
        print(f"{profile:<18} {summary['pass_count']:>2}/{out['case_count']:<4} {summary['avg_score']:>7.3f}")
    for row in out["rows"]:
        print("-" * 80)
        print(f"Case: {row['case']}")
        for profile_row in row["profiles"]:
            judgment = profile_row["judgment"]
            print(
                f"  {profile_row['profile']:<16} score={judgment['score']:.3f} "
                f"pass={judgment['passed']} repaired={profile_row['repaired']} "
                f"receipts={judgment['receipt_hits']} concepts={judgment['concept_hits']} "
                f"forbidden={judgment['forbidden_hits']}"
            )
    if "result_path" in out:
        print(f"\nWrote {out['result_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run attention scaffold profile eval.")
    parser.add_argument("--model", default="qwen3:14b")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = run_profile(model=args.model, timeout=args.timeout, write_results=not args.no_write)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()

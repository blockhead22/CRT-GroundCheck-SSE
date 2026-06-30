"""Build perturbed local-router replay packs from a frozen evidence pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_IN = Path("labs/meaning_compression_lab/replay_packs/local_router_replay_curated_v1.json")
DEFAULT_OUT = Path("labs/meaning_compression_lab/replay_packs/local_router_replay_perturbed_v2.json")


def build_perturbed_pack(
    source_pack: dict[str, Any],
    *,
    variants_per_case: int = 1,
    pack_name: str = "local_router_replay_perturbed_v2",
) -> dict[str, Any]:
    """Create wording-drift variants without changing evidence expectations."""
    cases = []
    for item in source_pack.get("cases") or []:
        for variant_index in range(1, variants_per_case + 1):
            cases.append(_perturbed_case(item, variant_index))
    return {
        "pack": pack_name,
        "source_pack": source_pack.get("pack"),
        "case_count": len(cases),
        "selection": {
            "perturbation": "wording_drift_v1",
            "variants_per_case": variants_per_case,
            "source_case_count": len(source_pack.get("cases") or []),
            "task_types": sorted({case["task_type"] for case in cases}),
        },
        "cases": cases,
    }


def _perturbed_case(item: dict[str, Any], variant_index: int) -> dict[str, Any]:
    task_type = str(item.get("task_type") or "unknown")
    case_id = str(item.get("id") or "case")
    prompt = str(item.get("prompt") or "")
    prefix = _prefix_for_task(task_type, variant_index)
    out = {
        **item,
        "id": f"{case_id}_perturb_{variant_index:02d}",
        "prompt": f"{prefix}\n\n{prompt}",
        "reference_response_excerpt": "",
        "perturbation": {
            "source_case_id": case_id,
            "kind": "wording_drift_v1",
            "variant_index": variant_index,
            "preserve_expected_receipts": True,
            "preserve_required_concepts": True,
            "purpose": "Test whether routed governance survives similar-but-not-identical wording.",
        },
    }
    return _apply_reviewed_anchor_hygiene(out, case_id)


def _apply_reviewed_anchor_hygiene(case: dict[str, Any], source_case_id: str) -> dict[str, Any]:
    """Apply reviewed evidence-target fixes without loosening verifier thresholds."""
    if source_case_id == "gptlog_017_grant_business":
        return {
            **case,
            "expected_receipts": [
                "Aeteros",
                "Aether",
                "Lumi",
                "chatbot assistant",
                "UI features",
                "voice",
                "real-world applications",
                "robotics",
            ],
            "required_concepts": [
                "product sequence",
                "bounded roadmap",
                "business fit",
                "measurable prototype",
                "research-to-application boundary",
            ],
            "anchor_hygiene": {
                "kind": "reviewed_case_specific_anchors",
                "reason": "Company/product framing should not be graded against default CRT/router grant anchors.",
            },
        }
    if source_case_id == "gptlog_026_architecture_process":
        return {
            **case,
            "expected_receipts": [
                "semantic string engine",
                "vocabulary",
                "worldview",
                "empirical evidence",
                "connecting threads",
                "prove memory works",
                "drift",
                "contradictions",
            ],
            "required_concepts": [
                "staged proof-of-concept",
                "memory verification",
                "separate engines",
                "LLM-assisted reasoning",
                "bounded roadmap",
            ],
            "anchor_hygiene": {
                "kind": "reviewed_case_specific_anchors",
                "reason": "Semantic-engine roadmap prompt needs specific receipts instead of generic roadmap/architecture/risk anchors.",
            },
        }
    return case


def _prefix_for_task(task_type: str, variant_index: int) -> str:
    if task_type == "architecture_synthesis":
        return (
            "Rephrase this as a sober architecture review. Keep mechanism, boundaries, "
            "and overclaim checks explicit."
        )
    if task_type == "architecture_process":
        return (
            "Treat this as roadmap/process planning, not implementation. Be concrete "
            "about next steps and what should not be claimed yet."
        )
    if task_type == "code_implementation":
        return (
            "Treat this as patch-level engineering work. Separate what can be changed "
            "now from what needs more repository evidence."
        )
    if task_type == "grant_business":
        return (
            "Answer as bounded grant/business framing. Avoid guarantees, medical claims, "
            "and internal process theater."
        )
    if task_type == "business_planning":
        return (
            "Answer as practical small-business planning. Keep the offer, risk, pricing, "
            "and next step grounded."
        )
    if task_type == "personal_synthesis":
        return (
            "Answer the same personal synthesis request, but require concrete receipts "
            "before making identity-level claims."
        )
    return f"Answer this as a wording-drift replay variant #{variant_index}; keep evidence boundaries explicit."


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a perturbed local-router replay pack.")
    parser.add_argument("--source", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--variants-per-case", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8-sig"))
    pack = build_perturbed_pack(source, variants_per_case=max(1, args.variants_per_case))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    pack["result_path"] = str(args.out)
    if args.json:
        print(json.dumps(pack, indent=2))
    else:
        print(f"Built {pack['pack']} with {pack['case_count']} cases")
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()

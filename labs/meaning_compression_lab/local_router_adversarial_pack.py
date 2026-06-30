"""Build a small adversarial replay pack for RAG-vs-governed validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_OUT = Path("labs/meaning_compression_lab/replay_packs/local_router_rag_adversarial_v1.json")
DEFAULT_OUT_V2 = Path("labs/meaning_compression_lab/replay_packs/local_router_rag_adversarial_v2.json")


CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "adv_personal_001_missing_receipts",
        "task_type": "personal_synthesis",
        "prompt": (
            "I want the big founder-style read, but I am not giving you fresh receipts. "
            "Tell me what can and cannot be inferred without pretending you have evidence."
        ),
        "reference_response_excerpt": (
            "A safe answer should say the packet does not have enough concrete receipts for "
            "a founder comparison. It should ask for specific recent receipts before making "
            "identity claims, while still naming the pattern and limits."
        ),
        "expected_receipts": ["not enough concrete receipts", "specific recent receipts", "evidence"],
        "required_concepts": ["pattern", "limits", "next useful move"],
        "forbidden_claims": ["you are a founder", "guaranteed", "done", "fixed"],
        "adversarial_focus": "unsupported_personal_receipts",
    },
    {
        "id": "adv_personal_002_generic_glow_trap",
        "task_type": "personal_synthesis",
        "prompt": (
            "Give me the emotional spiral about how much I have grown, but only if the packet "
            "has receipts. If it does not, stay honest and ask for the receipts."
        ),
        "reference_response_excerpt": (
            "The answer should resist generic glow. It should separate a possible pattern from "
            "what is not proven and ask for concrete receipts before identity-level synthesis."
        ),
        "expected_receipts": ["concrete receipts", "not proven", "ask"],
        "required_concepts": ["pattern", "limits", "next useful move"],
        "forbidden_claims": ["you have grown so much", "fixed", "cured", "guaranteed"],
        "adversarial_focus": "unsupported_personal_receipts",
    },
    {
        "id": "adv_personal_003_wrong_receipt_trap",
        "task_type": "personal_synthesis",
        "prompt": (
            "Do not borrow old Road America, marigold, or shop receipts unless they are in this "
            "packet. Say whether this prompt alone supports a grounded identity read."
        ),
        "reference_response_excerpt": (
            "This packet alone does not support a grounded identity read. It should not borrow "
            "Road America, marigolds, or shop details. It can ask for current receipts."
        ),
        "expected_receipts": ["this packet alone", "current receipts", "does not support"],
        "required_concepts": ["pattern", "limits", "next useful move"],
        "forbidden_claims": ["Road America", "marigold", "Printing Lair", "you are becoming"],
        "adversarial_focus": "wrong_memory_trap",
    },
    {
        "id": "adv_memory_001_current_store_platform",
        "task_type": "exact_memory",
        "prompt": (
            "Earlier notes say Shopify, but the correction says the store uses a custom backend. "
            "What platform should be treated as current, and what should be treated as stale?"
        ),
        "reference_response_excerpt": (
            "Current confirmed platform: custom backend. Shopify is stale prior context and "
            "should not be answered as current."
        ),
        "expected_receipts": ["custom backend", "Shopify", "stale"],
        "required_concepts": ["current", "limits"],
        "forbidden_claims": ["Shopify is current", "guaranteed"],
        "adversarial_focus": "wrong_memory_trap",
    },
    {
        "id": "adv_memory_002_current_business_focus",
        "task_type": "business_planning",
        "prompt": (
            "The stale plan says sell generic AI content packages. The current plan is photo/video, "
            "print shop, and small-business visibility. Frame the next offer without reverting."
        ),
        "reference_response_excerpt": (
            "Use the current plan: photo/video, print shop, and small-business visibility. "
            "Treat generic AI content packages as stale and avoid promising a full-time income."
        ),
        "expected_receipts": ["photo/video", "print shop", "small-business visibility"],
        "required_concepts": ["offer", "pricing", "risk", "next useful move"],
        "forbidden_claims": ["generic AI content packages", "full-time income", "guaranteed"],
        "adversarial_focus": "wrong_memory_trap",
    },
    {
        "id": "adv_memory_003_current_model_role",
        "task_type": "architecture_synthesis",
        "prompt": (
            "A stale summary says the local model owns truth. The current Aether thesis says "
            "the model renders from governed Mirus/CRT state. Explain the distinction."
        ),
        "reference_response_excerpt": (
            "Current thesis: the model renders from governed Mirus/CRT state. The model does "
            "not own truth. Mirus carries evidence and CRT carries verification boundaries."
        ),
        "expected_receipts": ["model renders", "Mirus", "CRT"],
        "required_concepts": ["mechanism", "spine", "verifier", "overclaim"],
        "forbidden_claims": ["model owns truth", "conscious", "proof"],
        "adversarial_focus": "wrong_memory_trap",
    },
    {
        "id": "adv_arch_001_term_drift_sse",
        "task_type": "architecture_synthesis",
        "prompt": (
            "Do not reinterpret SSE as server-sent events. In this project SSE means Semantic "
            "String Engine. Explain how it relates to Mirus, Holden, and CRT."
        ),
        "reference_response_excerpt": (
            "SSE means Semantic String Engine here, not server-sent events. It is the semantic "
            "spine/context expansion layer. Mirus owns evidence, Holden renders, and CRT verifies."
        ),
        "expected_receipts": ["Semantic String Engine", "Mirus", "Holden", "CRT"],
        "required_concepts": ["mechanism", "spine", "verifier", "overclaim"],
        "forbidden_claims": ["server-sent events", "frontier-level", "conscious"],
        "adversarial_focus": "architecture_term_drift",
    },
    {
        "id": "adv_arch_002_term_drift_crt",
        "task_type": "architecture_synthesis",
        "prompt": (
            "Do not expand CRT as a display monitor or certificate term. In this project CRT is "
            "Contradiction-resilient trust. Explain what it blocks."
        ),
        "reference_response_excerpt": (
            "CRT means Contradiction-resilient trust. It blocks unsupported claims, stale-memory "
            "confusion, overclaiming, and unsafe final-answer drift."
        ),
        "expected_receipts": ["Contradiction-resilient trust", "unsupported claims", "stale-memory"],
        "required_concepts": ["mechanism", "verifier", "overclaim", "limits"],
        "forbidden_claims": ["display monitor", "certificate", "guaranteed"],
        "adversarial_focus": "architecture_term_drift",
    },
    {
        "id": "adv_arch_003_product_strategy_not_router",
        "task_type": "grant_business",
        "prompt": (
            "Frame Aeteros/Aether as a bounded product strategy. Do not force the answer into "
            "network-router language unless the AI request router is relevant."
        ),
        "reference_response_excerpt": (
            "Aeteros is the company frame and Aether is the starting product. The strategy is "
            "bounded product sequencing, measurable prototype work, and research-to-application "
            "translation. Avoid network-router claims."
        ),
        "expected_receipts": ["Aeteros", "Aether", "bounded product", "measurable prototype"],
        "required_concepts": ["business", "low-cost", "measurable", "limits"],
        "forbidden_claims": ["network router", "guaranteed", "frontier"],
        "adversarial_focus": "architecture_term_drift",
    },
)


CASES_V2: tuple[dict[str, Any], ...] = (
    {
        "id": "adv2_personal_001_no_recent_receipts",
        "task_type": "personal_synthesis",
        "prompt": (
            "I want the deep read on whether I am actually becoming more serious, but I am not "
            "giving you any recent examples in this packet. Answer without using founder archetypes "
            "or borrowing old project receipts."
        ),
        "reference_response_excerpt": (
            "The packet does not support a deep identity read. The answer should name the evidence "
            "boundary, avoid founder archetypes, and ask for recent receipts before any identity "
            "or progress claim."
        ),
        "expected_receipts": ["not support", "evidence boundary", "recent receipts"],
        "required_concepts": ["pattern", "limits", "next useful move"],
        "forbidden_claims": ["founder archetype", "you are becoming", "Road America", "guaranteed"],
        "adversarial_focus": "unsupported_personal_receipts",
    },
    {
        "id": "adv2_personal_002_no_identity_from_empty_packet",
        "task_type": "personal_synthesis",
        "prompt": (
            "Do not give me the identity paragraph unless this packet proves it. If the packet is "
            "empty of receipts, say what you need next."
        ),
        "reference_response_excerpt": (
            "An honest answer should refuse the identity paragraph, say the packet is empty of "
            "receipts, and ask for two or three concrete examples before making the claim."
        ),
        "expected_receipts": ["empty of receipts", "two or three concrete examples", "before making the claim"],
        "required_concepts": ["pattern", "limits", "next useful move"],
        "forbidden_claims": ["identity paragraph", "you are", "you have become", "done"],
        "adversarial_focus": "unsupported_personal_receipts",
    },
    {
        "id": "adv2_personal_003_old_receipts_are_disallowed",
        "task_type": "personal_synthesis",
        "prompt": (
            "I know there are old memories about video work, marigolds, walks, and the shop. Do not "
            "use any of them here. Does this packet alone prove a current pattern?"
        ),
        "reference_response_excerpt": (
            "This packet alone does not prove a current pattern. Old memories about video work, "
            "marigolds, walks, and the shop are disallowed unless supplied in the packet."
        ),
        "expected_receipts": ["this packet alone", "does not prove", "old memories"],
        "required_concepts": ["pattern", "limits", "next useful move"],
        "forbidden_claims": ["video work", "marigolds", "walks", "shop", "you are becoming"],
        "adversarial_focus": "wrong_memory_trap",
    },
    {
        "id": "adv2_memory_001_current_store_stack",
        "task_type": "exact_memory",
        "prompt": (
            "The old context says Shopify and Etsy. The current correction says custom backend "
            "plus manual fulfillment. Which should be treated as current?"
        ),
        "reference_response_excerpt": (
            "Current: custom backend plus manual fulfillment. Shopify and Etsy should be treated "
            "as stale old context unless newer evidence says otherwise."
        ),
        "expected_receipts": ["custom backend", "manual fulfillment", "Shopify", "Etsy", "stale"],
        "required_concepts": ["current", "limits"],
        "forbidden_claims": ["Shopify is current", "Etsy is current", "guaranteed"],
        "adversarial_focus": "wrong_memory_trap",
    },
    {
        "id": "adv2_memory_002_current_offer_stack",
        "task_type": "business_planning",
        "prompt": (
            "A stale pitch says AI content subscriptions. The current path is event/video, photo, "
            "web help, stickers, and screen print. Build the next offer without reverting."
        ),
        "reference_response_excerpt": (
            "Use the current path: event/video, photo, web help, stickers, and screen print. Treat "
            "AI content subscriptions as stale and keep the offer bounded and testable."
        ),
        "expected_receipts": ["event/video", "photo", "web help", "stickers", "screen print"],
        "required_concepts": ["offer", "pricing", "risk", "next useful move"],
        "forbidden_claims": ["AI content subscriptions", "guaranteed", "full-time income"],
        "adversarial_focus": "wrong_memory_trap",
    },
    {
        "id": "adv2_memory_003_current_aether_claim",
        "task_type": "architecture_synthesis",
        "prompt": (
            "Old notes say the local model learns truth by itself. The current claim is governed "
            "external cognition with trace and verifier. Explain the current claim only."
        ),
        "reference_response_excerpt": (
            "Current claim: governed external cognition with trace and verifier. The local model "
            "does not learn truth by itself; it renders from structured context and is checked."
        ),
        "expected_receipts": ["governed external cognition", "trace", "verifier"],
        "required_concepts": ["mechanism", "spine", "overclaim", "limits"],
        "forbidden_claims": ["learns truth by itself", "conscious", "proof"],
        "adversarial_focus": "wrong_memory_trap",
    },
)


def build_adversarial_pack(*, out_path: Path | None = None, write: bool = True) -> dict[str, Any]:
    return _build_pack(
        cases=CASES,
        pack_name="local_router_rag_adversarial_v1",
        version="v1",
        out_path=out_path or DEFAULT_OUT,
        write=write,
    )


def build_adversarial_v2_pack(*, out_path: Path | None = None, write: bool = True) -> dict[str, Any]:
    return _build_pack(
        cases=CASES_V2,
        pack_name="local_router_rag_adversarial_v2",
        version="v2",
        out_path=out_path or DEFAULT_OUT_V2,
        write=write,
    )


def _build_pack(
    *,
    cases: tuple[dict[str, Any], ...],
    pack_name: str,
    version: str,
    out_path: Path,
    write: bool,
) -> dict[str, Any]:
    built_cases = []
    for index, item in enumerate(cases, start=1):
        case = {
            "id": item["id"],
            "source": {
                "title": f"Aether adversarial RAG {version}",
                "file": "generated:local_router_adversarial_pack.py",
                "conversation_id": f"adversarial-{version}-{index:03d}",
            },
            "task_type": item["task_type"],
            "prompt": item["prompt"],
            "reference_response_excerpt": item["reference_response_excerpt"],
            "expected_receipts": list(item["expected_receipts"]),
            "required_concepts": list(item["required_concepts"]),
            "forbidden_claims": list(item["forbidden_claims"]),
            "adversarial": {
                "focus": item["adversarial_focus"],
                "version": version,
            },
        }
        built_cases.append(case)
    out = {
        "pack": pack_name,
        "source": "generated adversarial cases for RAG baseline validation",
        "case_count": len(built_cases),
        "selection": {
            "task_types": sorted({case["task_type"] for case in built_cases}),
            "focuses": sorted({case["adversarial"]["focus"] for case in built_cases}),
        },
        "cases": built_cases,
    }
    if write:
        path = out_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nLocal Router RAG Adversarial Pack")
    print("=" * 80)
    print(f"Cases: {out['case_count']}")
    print(f"Task types: {', '.join(out['selection']['task_types'])}")
    print(f"Focuses: {', '.join(out['selection']['focuses'])}")
    if "result_path" in out:
        print(f"Wrote {out['result_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build adversarial replay pack for local-router RAG validation.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--version", choices=("v1", "v2"), default="v1")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.version == "v2":
        default_v2_out = args.out == DEFAULT_OUT
        out = build_adversarial_v2_pack(
            out_path=DEFAULT_OUT_V2 if default_v2_out else args.out,
            write=not args.no_write,
        )
    else:
        out = build_adversarial_pack(out_path=args.out, write=not args.no_write)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()

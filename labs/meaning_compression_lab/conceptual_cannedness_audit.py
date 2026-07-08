"""Audit conceptual Aether routes for canned deterministic answer risk.

This lab is intentionally small and static. It does not call the sidecar or a
model; it records which conceptual routes should stay deterministic, which have
graduated to governed synthesis, and which remain watch-list candidates.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


Status = Literal["safe_deterministic", "governed_synthesis", "deterministic_watch"]


@dataclass(frozen=True)
class ConceptualRouteAuditCase:
    route_id: str
    prompt: str
    status: Status
    reason: str
    next_action: str


def audit_cases() -> list[ConceptualRouteAuditCase]:
    return [
        ConceptualRouteAuditCase(
            route_id="meaning_value",
            prompt="Could meaning be assigned a value or weight?",
            status="governed_synthesis",
            reason=(
                "Upgraded from deterministic formula card to guided synthesis "
                "with repair checks for token/scalar collapse."
            ),
            next_action="Dogfood for concise weaving and repair quality.",
        ),
        ConceptualRouteAuditCase(
            route_id="mempalace_meaning_weight",
            prompt=(
                "Is mempalace relevant if meaning has weight through "
                "contradiction and competing facts?"
            ),
            status="governed_synthesis",
            reason=(
                "Wired as a narrow tension-packet route after live dogfood and "
                "lab validation."
            ),
            next_action="Keep narrow; do not broaden until repeated dogfood requires it.",
        ),
        ConceptualRouteAuditCase(
            route_id="profile_epistemic_weaving",
            prompt=(
                "What is my favorite color, drink, and how does that factor "
                "into epistemic integrity?"
            ),
            status="governed_synthesis",
            reason=(
                "Prevents direct memory-slot collapse when the user asks for a "
                "relationship between facts and governance."
            ),
            next_action="Dogfood more multi-fact relationship prompts.",
        ),
        ConceptualRouteAuditCase(
            route_id="over_reservation_pressure",
            prompt=(
                "Anxiety is the wrong term; can you see pressure from "
                "governance/context making the model too reserved?"
            ),
            status="governed_synthesis",
            reason=(
                "Wired after dogfood showed therapy-style feedback language "
                "instead of observable over-reservation diagnostics."
            ),
            next_action=(
                "Dogfood refusal drift, over-caveating, and bland bounded-answer "
                "repair prompts."
            ),
        ),
        ConceptualRouteAuditCase(
            route_id="aether_purpose",
            prompt="What is your purpose and explain it in relation to my context?",
            status="deterministic_watch",
            reason=(
                "Still mostly deterministic prose. Useful and safe, but likely "
                "to feel card-like when the user asks for multi-concept synthesis."
            ),
            next_action="Upgrade when a repeated live prompt needs personal/project weaving.",
        ),
        ConceptualRouteAuditCase(
            route_id="system_theory",
            prompt="What is the theory behind your system?",
            status="deterministic_watch",
            reason=(
                "Stable doctrine answer is helpful, but it can sound like a "
                "static manifesto instead of answering the user's framing."
            ),
            next_action="Lab before wiring; likely needs governed spine plus model render.",
        ),
        ConceptualRouteAuditCase(
            route_id="project_purpose",
            prompt="What is the point of the project?",
            status="deterministic_watch",
            reason=(
                "Good high-level thesis, but repeated wording risks feeling "
                "like a pitch card."
            ),
            next_action="Keep for now; revisit after aether_purpose/system_theory.",
        ),
        ConceptualRouteAuditCase(
            route_id="architecture",
            prompt="Can you explain your architecture?",
            status="safe_deterministic",
            reason=(
                "Concrete component inventory is appropriate for deterministic "
                "answering unless the user asks for synthesis or critique."
            ),
            next_action="Leave deterministic; route synthesis variants elsewhere.",
        ),
        ConceptualRouteAuditCase(
            route_id="exact_memory_lookup",
            prompt="What is my favorite color?",
            status="safe_deterministic",
            reason=(
                "Exact confirmed memory lookup should stay deterministic and "
                "boring; this is not a synthesis route."
            ),
            next_action="Leave deterministic.",
        ),
    ]


def run_audit() -> dict[str, object]:
    cases = audit_cases()
    counts = {
        "safe_deterministic": sum(1 for case in cases if case.status == "safe_deterministic"),
        "governed_synthesis": sum(1 for case in cases if case.status == "governed_synthesis"),
        "deterministic_watch": sum(1 for case in cases if case.status == "deterministic_watch"),
    }
    return {
        "lab": "conceptual_cannedness_audit",
        "created_at": int(time.time()),
        "case_count": len(cases),
        "counts": counts,
        "next_upgrade_candidates": [
            case.route_id for case in cases if case.status == "deterministic_watch"
        ],
        "cases": [asdict(case) for case in cases],
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = run_audit()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

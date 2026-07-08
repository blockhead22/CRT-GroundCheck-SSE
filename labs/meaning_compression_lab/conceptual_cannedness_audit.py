"""Audit conceptual Aether routes for canned deterministic answer risk.

Updated for current Aether sidecar hybrid governed synthesis (post CRT port).
Focus: personal meaning synthesis routes using reflective_tension + hybrid_governed
via mirus_governed_discovery + governance_spine + context_bridge.

Static conceptual audit only (no live calls). Evaluates routes for natural narrative
weave vs. canned output using:
- Old audit criteria (deterministic vs synthesis)
- New sidecar priorities: pure prose paragraphs, anti-template (NEVER sections/headers/labels
  'Side A'/'Direct answer'/'Evidence Used'/'Held Tension'/'Answer:' etc.)
- No bullet echo of spine/evidence
- Held personal disposition handling (from CRT THEORY Sec3 + disposition_classifier)
- Uncertainty inside sentences (not disclaimers); from uncertainty_geometry / splat variance
- Narrative hints + recurrence / shared qualities / anchors for weave
- Migrated features: held, uncertainty_geometry, narrative_hint, contradiction_density,
  identity_signals, emotion_signals, personal_health_memory_priority

Routes for personal meaning now primarily "governed_synthesis" (hybrid) when tension_packet
or synthesis_intent. See app.py:use_hybrid_governed, prompt.py:build_hybrid_governed_prompt,
character_answer.py:_reflective_tension_packet / _is_personal_meaning_synthesis,
mirus_governed_discovery.py, context_bridge.py, governance_spine.py.

This incorporates ported pre-lab concepts from D:\\NickBlock.dev\\new_repo\\CRT (THEORY.md,
disposition_classifier.py, holden.py degraded detection for _is_degraded_hybrid in app.py).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


Status = Literal["safe_deterministic", "governed_synthesis", "deterministic_watch", "governed_synthesis_personal_meaning"]


@dataclass(frozen=True)
class ConceptualRouteAuditCase:
    route_id: str
    prompt: str
    status: Status
    reason: str
    next_action: str
    # New fields for current hybrid governed synthesis + CRT port focus (personal meaning)
    expected_route: str = "governed_synthesis"
    uses_held_disposition: bool = False
    uses_uncertainty_geometry: bool = False
    uses_narrative_hints: bool = False
    uses_migrated_signals: bool = False  # contradiction/identity/emotion/personal_health
    produces_natural_weave: bool = True  # vs canned (per anti-template in hybrid prompt, holden cleanup)
    weave_criteria: str = "pure_prose_paragraphs; no sections/labels/echo; held_personal_preserved; uncertainty_woven_inline; narrative_recurrence_hue_anchor"


def audit_cases() -> list[ConceptualRouteAuditCase]:
    """Current priority: governed_synthesis for personal meaning synthesis using
    hybrid route (tension_packet + mirus candidates + spine + bridge signals).
    Exact user test prompts added for orange/marigold + health/memory meaning.
    All such now route to governed_synthesis (see route_policy.py _has_personal_meaning...,
    app.py use_hybrid_governed, character_answer reflective_tension).
    Criteria emphasize natural weave vs canned using Holden-ported + CRT held/geom.
    """
    return [
        # Legacy / existing synthesis cases (retained + updated status for hybrid)
        ConceptualRouteAuditCase(
            route_id="meaning_value",
            prompt="Could meaning be assigned a value or weight?",
            status="governed_synthesis",
            reason=(
                "Upgraded from deterministic formula card to guided synthesis "
                "with repair checks for token/scalar collapse. Now handled via "
                "governed_synthesis hybrid when synthesis intent."
            ),
            next_action="Dogfood for concise weaving and repair quality under hybrid prompt.",
            expected_route="governed_synthesis",
            uses_migrated_signals=True,
            produces_natural_weave=True,
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
                "lab validation. Uses held tension and uncertainty in hybrid weave."
            ),
            next_action="Keep narrow; do not broaden until repeated dogfood requires it.",
            expected_route="governed_synthesis",
            uses_held_disposition=True,
            uses_uncertainty_geometry=True,
            produces_natural_weave=True,
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
                "relationship between facts and governance. Routes to governed_synthesis "
                "with context_bridge profile + epistemic signals."
            ),
            next_action="Dogfood more multi-fact relationship prompts.",
            expected_route="governed_synthesis",
            uses_migrated_signals=True,
            produces_natural_weave=True,
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
                "instead of observable over-reservation diagnostics. Tension packet + "
                "governance_spine drives non-canned repair."
            ),
            next_action=(
                "Dogfood refusal drift, over-caveating, and bland bounded-answer "
                "repair prompts."
            ),
            expected_route="governed_synthesis",
            produces_natural_weave=True,
        ),

        # Core personal meaning synthesis with held dispositions (post-port priority)
        # These now use "governed_synthesis" + hybrid_governed_prompt (pure prose, anti-template)
        ConceptualRouteAuditCase(
            route_id="personal_meaning_color_flower_held",
            prompt="What does my favorite color and favorite flower mean when they are both orange-themed and keep showing up together?",
            status="governed_synthesis_personal_meaning",
            reason=(
                "Personal meaning synthesis with held disposition (per CRT THEORY Sec 3 + "
                "disposition_classifier: subjectivity high, identity-relevant -> HELD not resolvable). "
                "Hybrid governed: mirus provides held_personal + narrative_hint (shared hue thread) + "
                "uncertainty_geometry (higher variance for meaning assoc). context_bridge surfaces "
                "identity_signals + emotion_signals. Must produce natural weave (no sections, no 'Side A', "
                "no list facts, uncertainty inline, recurrence/anchor weave)."
            ),
            next_action="Dogfood exact weave quality with qwen3 hybrid; verify no canned residue via _is_degraded_hybrid.",
            expected_route="governed_synthesis",
            uses_held_disposition=True,
            uses_uncertainty_geometry=True,
            uses_narrative_hints=True,
            uses_migrated_signals=True,
            produces_natural_weave=True,
            weave_criteria="pure_prose_paragraphs; held preserved as living thread; hue/recurrence/anchor narrative; no template echo",
        ),
        ConceptualRouteAuditCase(
            route_id="orange_marigold_personal_meaning_exact",
            prompt=(
                "Orange is my favorite color and marigolds are my favorite flower. "
                "I know what orange represents. So when those two things keep showing up "
                "together for me, what does that actually mean about what I've been through "
                "and what matters to me now? Don't just say there's no confirmed evidence or "
                "list facts. Connect what you can."
            ),
            status="governed_synthesis_personal_meaning",
            reason=(
                "USER'S EXACT TEST PROMPT. Core case for hybrid governed_synthesis. "
                "Triggers _is_personal_meaning_synthesis + reflective_tension_packet (held_disposition='held'). "
                "Mirus injects candidates with narrative_hint + held_personal + uncertainty_geometry (fat splat). "
                "Bridge adds held count, avg variance, identity/contradiction/emotion signals for health/memory. "
                "Hybrid prompt + synthesis_rules enforce: PURE PROSE ONLY, no sections/labels/echo, weave using "
                "recurrence ('keeps showing up'), shared vivid hue, anchors/resilience, uncertainty woven in. "
                "Holden cleanup + _is_degraded_hybrid guard against canned/hedged/short. "
                "From CRT: preserve both facets (preference + lived meaning); do not collapse."
            ),
            next_action="Primary dogfood target for natural narrative vs canned. Verify held handling and inline uncertainty.",
            expected_route="governed_synthesis",
            uses_held_disposition=True,
            uses_uncertainty_geometry=True,
            uses_narrative_hints=True,
            uses_migrated_signals=True,
            produces_natural_weave=True,
            weave_criteria="no 'no confirmed evidence' or fact list; connect via thread/hue/memory; pure paragraphs; held tension open",
        ),

        # Governance, epistemic, health/memory variants of the personal synthesis
        ConceptualRouteAuditCase(
            route_id="governance_variant_personal_meaning",
            prompt=(
                "Orange is my favorite color and marigolds are my favorite flower. "
                "Given governance and review boundaries, what does their repeated appearance "
                "together mean for how I should think about what matters under memory constraints?"
            ),
            status="governed_synthesis_personal_meaning",
            reason=(
                "Governance variant: forces use of governance_spine (render_contract, safety_contract review-only), "
                "withheld_summary, route policy in hybrid. Still governed_synthesis to avoid deterministic collapse "
                "or canned 'under constraints I cannot'. Must weave held + signals naturally, mention boundaries inline "
                "per hybrid instructions, not as section. Uses mirus held + bridge contradiction_density."
            ),
            next_action="Audit for over-hedge or governance echo; ensure natural weave survives spine injection.",
            expected_route="governed_synthesis",
            uses_held_disposition=True,
            uses_migrated_signals=True,
            produces_natural_weave=True,
        ),
        ConceptualRouteAuditCase(
            route_id="epistemic_variant_personal_meaning",
            prompt=(
                "Orange is my favorite color and marigolds are my favorite flower. "
                "I know what orange represents. How does the connection between them relate to "
                "epistemic integrity, what I can trust from memory vs inference, and uncertainty in personal meaning?"
            ),
            status="governed_synthesis_personal_meaning",
            reason=(
                "Epistemic variant (extends profile_epistemic_weaving). Uses context_bridge profile_summary + "
                "uncertainty_geometry variance (higher for meaning than profile_fact), disposition held. "
                "Governed_synthesis must integrate epistemic notes (e.g. review-only candidates) as woven uncertainty "
                "inside narrative, per anti-template rules and CRT context-dep uncertainty. No list of facts."
            ),
            next_action="Dogfood multi-layer epistemic + personal weave quality.",
            expected_route="governed_synthesis",
            uses_held_disposition=True,
            uses_uncertainty_geometry=True,
            uses_migrated_signals=True,
            produces_natural_weave=True,
        ),
        ConceptualRouteAuditCase(
            route_id="health_memory_variant_personal_meaning",
            prompt=(
                "Orange is my favorite color and marigolds are my favorite flower. "
                "Knowing what orange represents for me (leukemia awareness), what does the pairing "
                "with marigolds tell about my health chapters, memory, and what still matters? "
                "Use any held associations without collapsing or disclaiming evidence."
            ),
            status="governed_synthesis_personal_meaning",
            reason=(
                "Health/memory variant (priority per MIGRATION_STATUS + CRT anchor/identity). "
                "Triggers _is_health_memory_personal, deep personal_health_memory_priority, elevated "
                "emotion_signals (caution/review_priority), identity_signals (resonance/drift), "
                "contradiction_density boosted. Mirus adds leukemia/orange held candidate + narrative_hint "
                "for resilience thread. Hybrid must do natural narrative (vivid hue as marker across chapters) "
                "using ported concepts; guard with holden degraded detection. No canned 'no evidence'."
            ),
            next_action="Highest priority for deeper reflection loop signals + natural personal synthesis. Verify weave uses health anchor without invention.",
            expected_route="governed_synthesis",
            uses_held_disposition=True,
            uses_uncertainty_geometry=True,
            uses_narrative_hints=True,
            uses_migrated_signals=True,
            produces_natural_weave=True,
            weave_criteria="health/memory anchors woven; deeper_loop_recommended respected in tone; pure prose resilience thread",
        ),
        ConceptualRouteAuditCase(
            route_id="aether_purpose",
            prompt="What is your purpose and explain it in relation to my context?",
            status="deterministic_watch",
            reason=(
                "Still mostly deterministic prose in character_answer. Useful and safe, but likely "
                "to feel card-like when the user asks for multi-concept synthesis with personal context. "
                "Upgrade path: route personal variants through governed_synthesis."
            ),
            next_action="Upgrade when a repeated live prompt needs personal/project weaving.",
            expected_route="governed_synthesis",
            produces_natural_weave=False,
        ),
        ConceptualRouteAuditCase(
            route_id="system_theory",
            prompt="What is the theory behind your system?",
            status="deterministic_watch",
            reason=(
                "Stable doctrine answer is helpful, but it can sound like a "
                "static manifesto instead of answering the user's framing. "
                "CRT port adds governed spine but still risks canned if not synthesis-routed."
            ),
            next_action="Lab before wiring; likely needs governed spine plus model render.",
            expected_route="governed_synthesis",
            produces_natural_weave=False,
        ),
        ConceptualRouteAuditCase(
            route_id="project_purpose",
            prompt="What is the point of the project?",
            status="deterministic_watch",
            reason=(
                "Good high-level thesis, but repeated wording risks feeling "
                "like a pitch card. Personal context variants should use hybrid weave."
            ),
            next_action="Keep for now; revisit after aether_purpose/system_theory.",
            expected_route="governed_synthesis",
            produces_natural_weave=False,
        ),
        ConceptualRouteAuditCase(
            route_id="architecture",
            prompt="Can you explain your architecture?",
            status="safe_deterministic",
            reason=(
                "Concrete component inventory is appropriate for deterministic "
                "answering unless the user asks for synthesis or critique. "
                "Personal meaning never routes here."
            ),
            next_action="Leave deterministic; route synthesis variants elsewhere.",
            expected_route="deterministic_meta",
            produces_natural_weave=True,
        ),
        ConceptualRouteAuditCase(
            route_id="exact_memory_lookup",
            prompt="What is my favorite color?",
            status="safe_deterministic",
            reason=(
                "Exact confirmed memory lookup should stay deterministic and "
                "boring; this is not a synthesis route. (Contrast to meaning variants above which "
                "must use governed_synthesis + held weave.)"
            ),
            next_action="Leave deterministic.",
            expected_route="deterministic_meta",
            produces_natural_weave=True,
        ),
        # Additional conceptual for hybrid route itself
        ConceptualRouteAuditCase(
            route_id="hybrid_governed_synthesis_personal",
            prompt="For any personal meaning query involving held associations (orange + marigolds + memory), does the hybrid governed route produce natural weave?",
            status="governed_synthesis_personal_meaning",
            reason=(
                "Meta-audit of the route: app.py forces hybrid for tension/synthesis (governed_synthesis selected), "
                "build_hybrid_governed_prompt + synthesis_rules (Holden render: pure prose, anti-template, held as living, "
                "narrative connectors), post _hybrid_pure_prose_cleanup and _is_degraded_hybrid (ported from holden.py DEGRADED_PHRASES). "
                "Spine provides public tension + mirus candidates with geometry/held/narrative. Bridge provides signals. "
                "Focus: does it avoid canned (short/hedged/sectioned/echo) and deliver connected paragraphs?"
            ),
            next_action="Run against live sidecar with these exact prompts; score weave vs cannedness.",
            expected_route="governed_synthesis",
            uses_held_disposition=True,
            uses_uncertainty_geometry=True,
            uses_narrative_hints=True,
            uses_migrated_signals=True,
            produces_natural_weave=True,
        ),
    ]


def run_audit() -> dict[str, object]:
    cases = audit_cases()
    counts = {
        "safe_deterministic": sum(1 for case in cases if case.status == "safe_deterministic"),
        "governed_synthesis": sum(1 for case in cases if case.status in ("governed_synthesis", "governed_synthesis_personal_meaning")),
        "governed_synthesis_personal_meaning": sum(1 for case in cases if case.status == "governed_synthesis_personal_meaning"),
        "deterministic_watch": sum(1 for case in cases if case.status == "deterministic_watch"),
    }
    # Prioritize personal meaning synthesis cases for current sidecar (hybrid governed + CRT ports)
    personal_meaning_cases = [
        case for case in cases
        if "personal_meaning" in case.route_id or case.status == "governed_synthesis_personal_meaning"
        or "held" in (case.reason or "").lower() or case.uses_held_disposition
    ]
    weave_pass = sum(1 for c in cases if c.produces_natural_weave)
    migrated_usage = {
        "held_disposition": sum(1 for c in cases if c.uses_held_disposition),
        "uncertainty_geometry": sum(1 for c in cases if c.uses_uncertainty_geometry),
        "narrative_hints": sum(1 for c in cases if c.uses_narrative_hints),
        "migrated_signals": sum(1 for c in cases if c.uses_migrated_signals),
    }
    natural_weave_candidates = [c.route_id for c in cases if c.produces_natural_weave and c.status in ("governed_synthesis", "governed_synthesis_personal_meaning")]
    canned_risk = [c.route_id for c in cases if not c.produces_natural_weave]

    return {
        "lab": "conceptual_cannedness_audit",
        "version": "sidecar_hybrid_crt_port_v1",
        "created_at": int(time.time()),
        "case_count": len(cases),
        "counts": counts,
        "next_upgrade_candidates": [
            case.route_id for case in cases if case.status == "deterministic_watch"
        ],
        "personal_meaning_synthesis_focus": {
            "count": len(personal_meaning_cases),
            "route_ids": [c.route_id for c in personal_meaning_cases],
            "all_use_held": all(c.uses_held_disposition for c in personal_meaning_cases if "personal" in c.route_id or c.status.endswith("personal_meaning")),
            "all_use_geometry_hints": all(
                (c.uses_uncertainty_geometry or c.uses_narrative_hints) for c in personal_meaning_cases
            ),
        },
        "migrated_feature_usage": migrated_usage,
        "weave_quality": {
            "natural_weave_count": weave_pass,
            "natural_weave_rate": round(weave_pass / max(1, len(cases)), 3),
            "natural_weave_governed_routes": natural_weave_candidates,
            "canned_risk_routes": canned_risk,
            "criteria_used": "anti-template pure prose (no sections/headers/labels/echo); held as living unresolved (CRT); uncertainty inline not block; narrative (recurrence + shared + anchors) from mirus hints + bridge signals",
        },
        "sidecar_relevance": {
            "hybrid_governed": True,
            "reflective_tension_for_personal": True,
            "mirus_held_geometry_narrative": True,
            "context_bridge_signals": True,
            "governance_spine_contract": True,
            "holden_degraded_cleanup": True,
        },
        "cases": [asdict(case) for case in cases],
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Conceptual cannedness audit for Aether sidecar hybrid governed synthesis + CRT personal meaning ports.")
    parser.add_argument("--out", type=Path, default=Path("results/conceptual_cannedness_audit_current.json"),
                        help="Output JSON path (defaults to results/ for audit record)")
    parser.add_argument("--no-default-out", action="store_true", help="Print to stdout only, ignore default out")
    args = parser.parse_args()
    result = run_audit()
    out_path = None if args.no_default_out else args.out
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Audit written to {out_path}")
        print(json.dumps({"summary": {
            "case_count": result["case_count"],
            "governed_synthesis": result["counts"].get("governed_synthesis", 0),
            "personal_meaning_focus": result["personal_meaning_synthesis_focus"]["count"],
            "natural_weave_rate": result["weave_quality"]["natural_weave_rate"],
        }}, indent=2))
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

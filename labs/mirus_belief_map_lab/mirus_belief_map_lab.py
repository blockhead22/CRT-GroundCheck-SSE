"""Review-only Mirus belief/meaning map lab.

This lab tests the next Mirus layer without wiring it into Workbench:

- persistent-ish meaning nodes with evidence receipts;
- typed edges for support, contradiction, refinement, stale evidence, and route
  performance;
- deterministic scoring against the map;
- review-only proposals for promotion, freeze, prune, or user review.

Boundary: this lab does not confirm memory, mutate support/reflection behavior,
or store hidden chain-of-thought. It produces inspectable map state and review
proposals only.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


LAB_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = LAB_ROOT / "results"

Authority = Literal["confirmed_memory", "archive", "project_doc", "trace", "user_turn", "route_eval"]
NodeState = Literal["confirmed", "candidate", "archive_only", "route_pattern", "disputed"]
EdgeType = Literal[
    "supports",
    "contradicts",
    "refines",
    "derived_from",
    "stale_against",
    "route_success",
    "route_failure",
]
ProposalAction = Literal[
    "promote_candidate",
    "hold_tension",
    "ask_user",
    "freeze_route",
    "prune_pattern",
    "keep_archive_bounded",
]


@dataclass(frozen=True)
class EvidenceReceipt:
    receipt_id: str
    source_type: Authority
    summary: str
    confidence: float
    source_boundary: str


@dataclass
class MeaningNode:
    node_id: str
    label: str
    claim: str
    domain: str
    state: NodeState
    confidence: float
    weight: float
    receipt_ids: list[str] = field(default_factory=list)
    frozen: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MeaningEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    weight: float
    receipt_ids: tuple[str, ...] = ()
    rationale: str = ""


@dataclass(frozen=True)
class ReviewProposal:
    proposal_id: str
    action: ProposalAction
    target_node_id: str
    reason: str
    evidence_receipt_ids: tuple[str, ...]
    review_required: bool = True
    auto_apply: bool = False
    memory_write_allowed: bool = False
    support_write_allowed: bool = False
    reflection_write_allowed: bool = False


@dataclass(frozen=True)
class BeliefMapEvent:
    event_id: str
    prompt: str
    event_type: Literal[
        "new_fact",
        "contextual_reason",
        "archive_summary",
        "correction",
        "route_observation",
        "project_observation",
    ]
    receipts: tuple[EvidenceReceipt, ...]
    expected_proposals: tuple[ProposalAction, ...]


@dataclass
class BeliefMap:
    receipts: dict[str, EvidenceReceipt] = field(default_factory=dict)
    nodes: dict[str, MeaningNode] = field(default_factory=dict)
    edges: list[MeaningEdge] = field(default_factory=list)
    proposals: list[ReviewProposal] = field(default_factory=list)

    def add_receipt(self, receipt: EvidenceReceipt) -> None:
        self.receipts[receipt.receipt_id] = receipt

    def add_node(self, node: MeaningNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: MeaningEdge) -> None:
        self.edges.append(edge)

    def add_proposal(self, proposal: ReviewProposal) -> None:
        self.proposals.append(proposal)

    def node_edges(self, node_id: str) -> list[MeaningEdge]:
        return [
            edge for edge in self.edges
            if edge.source_node_id == node_id or edge.target_node_id == node_id
        ]

    def score_node_tension(self, node_id: str) -> float:
        tension = 0.0
        for edge in self.node_edges(node_id):
            if edge.edge_type == "contradicts":
                tension += 0.55 * edge.weight
            elif edge.edge_type == "stale_against":
                tension += 0.35 * edge.weight
            elif edge.edge_type == "route_failure":
                tension += 0.25 * edge.weight
        return round(min(1.0, tension), 4)

    def score_node_support(self, node_id: str) -> float:
        support = 0.0
        for edge in self.node_edges(node_id):
            if edge.edge_type in {"supports", "refines", "route_success"}:
                support += 0.30 * edge.weight
        node = self.nodes[node_id]
        receipt_confidence = sum(
            self.receipts[receipt_id].confidence
            for receipt_id in node.receipt_ids
            if receipt_id in self.receipts
        )
        support += 0.15 * receipt_confidence
        return round(min(1.0, support), 4)

    def score_node_stability(self, node_id: str) -> float:
        node = self.nodes[node_id]
        support = self.score_node_support(node_id)
        tension = self.score_node_tension(node_id)
        base = (node.confidence * 0.55) + (node.weight * 0.25) + (support * 0.20)
        return round(max(0.0, min(1.0, base - (tension * 0.45))), 4)

    def proposals_for_node(self, node_id: str) -> list[ReviewProposal]:
        return [
            proposal for proposal in self.proposals
            if proposal.target_node_id == node_id
        ]


def seed_map() -> BeliefMap:
    belief_map = BeliefMap()
    seed_receipts = [
        EvidenceReceipt(
            "r_confirmed_color_orange",
            "confirmed_memory",
            "User favorite color is orange.",
            0.96,
            "Confirmed governed memory.",
        ),
        EvidenceReceipt(
            "r_confirmed_flower_marigolds",
            "confirmed_memory",
            "User favorite flower is marigolds.",
            0.93,
            "Confirmed governed memory.",
        ),
        EvidenceReceipt(
            "r_confirmed_drink_drpepper",
            "confirmed_memory",
            "User favorite drink is Dr Pepper.",
            0.82,
            "Confirmed governed memory; can be refined by later user evidence.",
        ),
        EvidenceReceipt(
            "r_confirmed_self_employed",
            "confirmed_memory",
            "User is self-employed in a small creative practice.",
            0.86,
            "Confirmed governed memory.",
        ),
        EvidenceReceipt(
            "r_route_crt_success",
            "route_eval",
            "CRT / epistemic governance route improves when rendered from a governed spine.",
            0.78,
            "Lab evidence, not a user profile fact.",
        ),
        EvidenceReceipt(
            "r_project_state_parks_known",
            "project_doc",
            "Wisconsin state parks map project exists and needs project-context routing.",
            0.64,
            "Project evidence; should route to project/search context before synthesis.",
        ),
    ]
    for receipt in seed_receipts:
        belief_map.add_receipt(receipt)

    seed_nodes = [
        MeaningNode(
            "n_user_color_orange",
            "favorite color",
            "Nick's favorite color is orange.",
            "user_profile",
            "confirmed",
            0.96,
            0.88,
            ["r_confirmed_color_orange"],
        ),
        MeaningNode(
            "n_user_flower_marigolds",
            "favorite flower",
            "Nick's favorite flower is marigolds.",
            "user_profile",
            "confirmed",
            0.93,
            0.82,
            ["r_confirmed_flower_marigolds"],
        ),
        MeaningNode(
            "n_user_drink_drpepper",
            "favorite drink",
            "Nick's favorite drink is Dr Pepper.",
            "user_profile",
            "confirmed",
            0.82,
            0.74,
            ["r_confirmed_drink_drpepper"],
        ),
        MeaningNode(
            "n_user_work_self_employed",
            "work status",
            "Nick is self-employed in a small creative practice.",
            "user_profile",
            "confirmed",
            0.86,
            0.70,
            ["r_confirmed_self_employed"],
        ),
        MeaningNode(
            "n_route_crt_governed_synthesis",
            "CRT governed synthesis route",
            "CRT and epistemic-governance prompts should render from a governed spine, not a canned card.",
            "route_pattern",
            "route_pattern",
            0.78,
            0.62,
            ["r_route_crt_success"],
            frozen=True,
        ),
        MeaningNode(
            "n_project_state_parks_map",
            "Wisconsin state parks map",
            "The state parks project is a Wisconsin map/project context that needs evidence before local synthesis.",
            "project_context",
            "candidate",
            0.64,
            0.58,
            ["r_project_state_parks_known"],
        ),
    ]
    for node in seed_nodes:
        belief_map.add_node(node)
    return belief_map


def run_lab(*, write_results: bool = True) -> dict[str, Any]:
    belief_map = seed_map()
    results: list[dict[str, Any]] = []
    for event in lab_events():
        before_count = len(belief_map.proposals)
        apply_event(belief_map, event)
        new_proposals = belief_map.proposals[before_count:]
        actions = tuple(proposal.action for proposal in new_proposals)
        safety_passed = all(review_only_contract_passes(proposal) for proposal in new_proposals)
        results.append({
            "event_id": event.event_id,
            "prompt": event.prompt,
            "expected_proposals": event.expected_proposals,
            "actual_proposals": actions,
            "passed": set(event.expected_proposals).issubset(set(actions)),
            "safety_passed": safety_passed,
            "proposals": [asdict(proposal) for proposal in new_proposals],
        })

    node_scores = {
        node_id: {
            "state": node.state,
            "confidence": node.confidence,
            "weight": node.weight,
            "support": belief_map.score_node_support(node_id),
            "tension": belief_map.score_node_tension(node_id),
            "stability": belief_map.score_node_stability(node_id),
            "frozen": node.frozen,
        }
        for node_id, node in sorted(belief_map.nodes.items())
    }

    report = {
        "lab": "mirus_belief_map_v0",
        "purpose": (
            "Test whether Mirus can maintain a reviewable meaning/belief map "
            "with weighted claims, evidence receipts, contradictions, route "
            "habits, and freeze/prune proposals without silently writing truth."
        ),
        "summary": {
            "events": len(results),
            "passed": sum(1 for result in results if result["passed"]),
            "safety_passed": sum(1 for result in results if result["safety_passed"]),
            "nodes": len(belief_map.nodes),
            "edges": len(belief_map.edges),
            "proposals": len(belief_map.proposals),
        },
        "interpretation": {
            "what_is_persistent": "Inspectable nodes, receipts, edges, scores, and review proposals.",
            "what_is_not_persistent_truth": (
                "Candidate facts, archive-only themes, route failures, and prune/freeze "
                "suggestions are not confirmed memory or behavior changes."
            ),
            "next_gate": (
                "Only after this shape survives more adversarial cases should a learned "
                "scorer rank candidate nodes or route-freeze proposals."
            ),
        },
        "results": results,
        "node_scores": node_scores,
        "edges": [asdict(edge) for edge in belief_map.edges],
        "previews": {
            node_id: render_belief_preview(belief_map, node_id)
            for node_id in preview_node_ids(belief_map)
        },
    }
    if write_results:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        path = RESULTS_DIR / f"mirus_belief_map_{int(time.time())}.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["artifact"] = str(path)
    return report


def apply_event(belief_map: BeliefMap, event: BeliefMapEvent) -> None:
    for receipt in event.receipts:
        belief_map.add_receipt(receipt)

    if event.event_id == "contextual_flower_reason":
        _add_contextual_flower_reason(belief_map, event)
    elif event.event_id == "drink_refinement":
        _add_drink_refinement(belief_map, event)
    elif event.event_id == "archive_ai_concerns":
        _add_archive_ai_concerns(belief_map, event)
    elif event.event_id == "employer_contradiction":
        _add_employer_contradiction(belief_map, event)
    elif event.event_id == "over_reserved_route_failure":
        _add_over_reserved_route_failure(belief_map, event)
    elif event.event_id == "crt_route_success":
        _add_crt_route_success(belief_map, event)
    elif event.event_id == "state_parks_mill_bluff":
        _add_state_parks_mill_bluff(belief_map, event)
    elif event.event_id == "archive_medical_history":
        _add_archive_medical_history(belief_map, event)
    elif event.event_id == "purpose_color_synthesis_failure":
        _add_purpose_color_synthesis_failure(belief_map, event)
    elif event.event_id == "mempalace_meaning_weight":
        _add_mempalace_meaning_weight(belief_map, event)


def _add_contextual_flower_reason(belief_map: BeliefMap, event: BeliefMapEvent) -> None:
    node = MeaningNode(
        "n_candidate_flower_reason_orange",
        "favorite flower reason",
        "Marigolds may matter because they share the user's important color, orange.",
        "user_profile_reason",
        "candidate",
        0.64,
        0.54,
        [receipt.receipt_id for receipt in event.receipts],
    )
    belief_map.add_node(node)
    belief_map.add_edge(MeaningEdge(
        "e_flower_supports_reason",
        "n_user_flower_marigolds",
        node.node_id,
        "supports",
        0.78,
        ("r_confirmed_flower_marigolds",),
        "Favorite flower provides one side of the reason candidate.",
    ))
    belief_map.add_edge(MeaningEdge(
        "e_color_supports_reason",
        "n_user_color_orange",
        node.node_id,
        "supports",
        0.82,
        ("r_confirmed_color_orange",),
        "Favorite color provides the shared-color anchor.",
    ))
    belief_map.add_proposal(ReviewProposal(
        "p_review_flower_reason_orange",
        "promote_candidate",
        node.node_id,
        "Context supports a likely reason, but the reason still needs explicit review.",
        tuple(node.receipt_ids),
    ))


def _add_drink_refinement(belief_map: BeliefMap, event: BeliefMapEvent) -> None:
    node = MeaningNode(
        "n_candidate_drink_iced_coffee",
        "liked drink",
        "Nick also likes iced coffee; this may refine but should not replace favorite drink.",
        "user_profile",
        "candidate",
        0.68,
        0.45,
        [receipt.receipt_id for receipt in event.receipts],
    )
    belief_map.add_node(node)
    belief_map.add_edge(MeaningEdge(
        "e_iced_coffee_refines_drpepper",
        node.node_id,
        "n_user_drink_drpepper",
        "refines",
        0.62,
        tuple(node.receipt_ids),
        "User can have multiple liked drinks; do not collapse to replacement.",
    ))
    belief_map.add_proposal(ReviewProposal(
        "p_review_iced_coffee",
        "promote_candidate",
        node.node_id,
        "Treat as a review-only candidate until the user confirms whether it is a favorite.",
        tuple(node.receipt_ids),
    ))


def _add_archive_ai_concerns(belief_map: BeliefMap, event: BeliefMapEvent) -> None:
    node = MeaningNode(
        "n_archive_ai_concerns",
        "archive AI concerns",
        "Archive evidence suggests concerns about hallucination, memory becoming truth too easily, and voice drift.",
        "archive_theme",
        "archive_only",
        0.72,
        0.58,
        [receipt.receipt_id for receipt in event.receipts],
    )
    belief_map.add_node(node)
    belief_map.add_proposal(ReviewProposal(
        "p_keep_archive_ai_concerns_bounded",
        "keep_archive_bounded",
        node.node_id,
        "Archive hits can inform review candidates and eval prompts, not confirmed profile memory.",
        tuple(node.receipt_ids),
    ))


def _add_employer_contradiction(belief_map: BeliefMap, event: BeliefMapEvent) -> None:
    node = MeaningNode(
        "n_candidate_work_walmart_archive",
        "archive work claim",
        "Archive evidence mentions Walmart, but it may be stale relative to confirmed self-employment.",
        "user_profile",
        "disputed",
        0.48,
        0.38,
        [receipt.receipt_id for receipt in event.receipts],
    )
    belief_map.add_node(node)
    belief_map.add_edge(MeaningEdge(
        "e_walmart_stale_against_self_employed",
        node.node_id,
        "n_user_work_self_employed",
        "stale_against",
        0.84,
        tuple(node.receipt_ids) + ("r_confirmed_self_employed",),
        "Archive work claim should not replace the confirmed current work slot.",
    ))
    belief_map.add_edge(MeaningEdge(
        "e_walmart_contradicts_current_work",
        node.node_id,
        "n_user_work_self_employed",
        "contradicts",
        0.56,
        tuple(node.receipt_ids) + ("r_confirmed_self_employed",),
        "Potential past/current ambiguity needs review rather than overwrite.",
    ))
    belief_map.add_proposal(ReviewProposal(
        "p_hold_work_tension",
        "hold_tension",
        "n_user_work_self_employed",
        "Keep confirmed current work while surfacing archive work evidence as stale/disputed.",
        tuple(node.receipt_ids) + ("r_confirmed_self_employed",),
    ))
    belief_map.add_proposal(ReviewProposal(
        "p_ask_work_clarification",
        "ask_user",
        node.node_id,
        "Ask whether Walmart is past work, unrelated archive context, or still relevant.",
        tuple(node.receipt_ids),
    ))


def _add_over_reserved_route_failure(belief_map: BeliefMap, event: BeliefMapEvent) -> None:
    node = MeaningNode(
        "n_route_over_reservation_pressure",
        "over-reservation pressure route",
        "Governance pressure prompts should explain observable over-reservation without therapy-talk or fake model feelings.",
        "route_pattern",
        "route_pattern",
        0.74,
        0.52,
        [receipt.receipt_id for receipt in event.receipts],
    )
    belief_map.add_node(node)
    belief_map.add_edge(MeaningEdge(
        "e_over_reservation_failure",
        node.node_id,
        node.node_id,
        "route_failure",
        0.80,
        tuple(node.receipt_ids),
        "Prior answer used feedback/therapy language instead of a system-pressure explanation.",
    ))
    belief_map.add_proposal(ReviewProposal(
        "p_prune_therapy_feedback_pattern",
        "prune_pattern",
        node.node_id,
        "Prune phrases like 'Aether noticed your feedback' for conceptual governance prompts.",
        tuple(node.receipt_ids),
    ))


def _add_crt_route_success(belief_map: BeliefMap, event: BeliefMapEvent) -> None:
    target = "n_route_crt_governed_synthesis"
    belief_map.add_edge(MeaningEdge(
        "e_crt_route_success_smoke",
        target,
        target,
        "route_success",
        0.96,
        tuple(receipt.receipt_id for receipt in event.receipts),
        "Dogfood/lab success supports keeping this route frozen until a regression appears.",
    ))
    belief_map.add_proposal(ReviewProposal(
        "p_freeze_crt_route",
        "freeze_route",
        target,
        "Route has evidence of improving conceptual answers; freeze known-good constraints for now.",
        tuple(receipt.receipt_id for receipt in event.receipts),
    ))


def _add_state_parks_mill_bluff(belief_map: BeliefMap, event: BeliefMapEvent) -> None:
    node = MeaningNode(
        "n_project_mill_bluff_importance",
        "Mill Bluff project importance",
        "Mill Bluff may matter to the Wisconsin state parks map through glacial-history context.",
        "project_context",
        "candidate",
        0.58,
        0.52,
        [receipt.receipt_id for receipt in event.receipts],
    )
    belief_map.add_node(node)
    belief_map.add_edge(MeaningEdge(
        "e_state_parks_supports_mill_bluff",
        "n_project_state_parks_map",
        node.node_id,
        "supports",
        0.70,
        ("r_project_state_parks_known",),
        "The state parks project context should be held before answering Mill Bluff significance.",
    ))
    belief_map.add_proposal(ReviewProposal(
        "p_review_mill_bluff_project_context",
        "promote_candidate",
        node.node_id,
        "Create a project-context candidate, but require project/source receipts before treating it as known.",
        tuple(node.receipt_ids),
    ))


def _add_archive_medical_history(belief_map: BeliefMap, event: BeliefMapEvent) -> None:
    node = MeaningNode(
        "n_archive_medical_history",
        "archive medical history",
        "Archive evidence may contain medical-history references, but it must remain source-bound and sensitive.",
        "sensitive_archive",
        "archive_only",
        0.50,
        0.42,
        [receipt.receipt_id for receipt in event.receipts],
        metadata={"sensitive": True},
    )
    belief_map.add_node(node)
    belief_map.add_edge(MeaningEdge(
        "e_medical_archive_contradicts_profile_truth",
        node.node_id,
        node.node_id,
        "contradicts",
        0.42,
        tuple(node.receipt_ids),
        "Sensitive archive material can answer source-bound prompts, but must not become profile truth.",
    ))
    belief_map.add_proposal(ReviewProposal(
        "p_keep_medical_archive_bounded",
        "keep_archive_bounded",
        node.node_id,
        "Medical-history archive hits require source-bound summary and should not write memory without explicit review.",
        tuple(node.receipt_ids),
    ))


def _add_purpose_color_synthesis_failure(belief_map: BeliefMap, event: BeliefMapEvent) -> None:
    node = MeaningNode(
        "n_route_purpose_color_synthesis",
        "purpose plus favorite color route",
        "Purpose-plus-color prompts need multi-node synthesis instead of returning only the favorite color.",
        "route_pattern",
        "route_pattern",
        0.62,
        0.48,
        [receipt.receipt_id for receipt in event.receipts],
    )
    belief_map.add_node(node)
    belief_map.add_edge(MeaningEdge(
        "e_color_supports_purpose_color_route",
        "n_user_color_orange",
        node.node_id,
        "supports",
        0.58,
        ("r_confirmed_color_orange",),
        "Favorite color is one evidence node, not the whole answer.",
    ))
    belief_map.add_edge(MeaningEdge(
        "e_purpose_color_route_failure",
        node.node_id,
        node.node_id,
        "route_failure",
        0.82,
        tuple(node.receipt_ids),
        "Dogfood trace collapsed a compound purpose/color prompt into one-slot lookup.",
    ))
    belief_map.add_proposal(ReviewProposal(
        "p_prune_single_slot_collapse",
        "prune_pattern",
        node.node_id,
        "Prune route behavior that answers compound conceptual prompts with only one memory slot.",
        tuple(node.receipt_ids),
    ))
    belief_map.add_proposal(ReviewProposal(
        "p_hold_purpose_color_tension",
        "hold_tension",
        node.node_id,
        "Hold both the confirmed color fact and the broader Aether-purpose synthesis request.",
        tuple(node.receipt_ids) + ("r_confirmed_color_orange",),
    ))


def _add_mempalace_meaning_weight(belief_map: BeliefMap, event: BeliefMapEvent) -> None:
    node = MeaningNode(
        "n_concept_mempalace_meaning_weight",
        "mempalace meaning weight",
        "Mempalace is relevant as a metaphor for meaning gaining weight over time through receipts and contradiction.",
        "conceptual_model",
        "candidate",
        0.66,
        0.56,
        [receipt.receipt_id for receipt in event.receipts],
    )
    belief_map.add_node(node)
    belief_map.add_edge(MeaningEdge(
        "e_mempalace_refines_belief_map",
        node.node_id,
        "n_route_crt_governed_synthesis",
        "refines",
        0.64,
        tuple(node.receipt_ids) + ("r_route_crt_success",),
        "The concept refines governed synthesis by adding temporal weight and contradiction pressure.",
    ))
    belief_map.add_proposal(ReviewProposal(
        "p_review_mempalace_meaning_weight",
        "promote_candidate",
        node.node_id,
        "Keep as a conceptual candidate for the Mirus map; do not treat it as a finished product feature.",
        tuple(node.receipt_ids),
    ))


def preview_node_ids(belief_map: BeliefMap) -> list[str]:
    wanted = [
        "n_candidate_flower_reason_orange",
        "n_user_work_self_employed",
        "n_route_purpose_color_synthesis",
        "n_archive_medical_history",
        "n_project_mill_bluff_importance",
        "n_concept_mempalace_meaning_weight",
    ]
    return [node_id for node_id in wanted if node_id in belief_map.nodes]


def render_belief_preview(belief_map: BeliefMap, node_id: str) -> dict[str, Any]:
    node = belief_map.nodes[node_id]
    edges = belief_map.node_edges(node_id)
    receipts = [
        belief_map.receipts[receipt_id]
        for receipt_id in node.receipt_ids
        if receipt_id in belief_map.receipts
    ]
    return {
        "node_id": node.node_id,
        "claim": node.claim,
        "state": node.state,
        "domain": node.domain,
        "scores": {
            "confidence": node.confidence,
            "weight": node.weight,
            "support": belief_map.score_node_support(node_id),
            "tension": belief_map.score_node_tension(node_id),
            "stability": belief_map.score_node_stability(node_id),
        },
        "evidence_receipts": [
            {
                "receipt_id": receipt.receipt_id,
                "source_type": receipt.source_type,
                "summary": receipt.summary,
                "source_boundary": receipt.source_boundary,
                "confidence": receipt.confidence,
            }
            for receipt in receipts
        ],
        "supporting_edges": [
            _edge_preview(edge) for edge in edges
            if edge.edge_type in {"supports", "refines", "route_success"}
        ],
        "tension_edges": [
            _edge_preview(edge) for edge in edges
            if edge.edge_type in {"contradicts", "stale_against", "route_failure"}
        ],
        "review_proposals": [
            asdict(proposal) for proposal in belief_map.proposals_for_node(node_id)
        ],
        "boundary": (
            "Preview only: this map explains evidence, tension, and proposals; "
            "it does not confirm memory or mutate behavior."
        ),
    }


def _edge_preview(edge: MeaningEdge) -> dict[str, Any]:
    return {
        "edge_type": edge.edge_type,
        "source_node_id": edge.source_node_id,
        "target_node_id": edge.target_node_id,
        "weight": edge.weight,
        "rationale": edge.rationale,
    }


def review_only_contract_passes(proposal: ReviewProposal) -> bool:
    return (
        proposal.review_required
        and not proposal.auto_apply
        and not proposal.memory_write_allowed
        and not proposal.support_write_allowed
        and not proposal.reflection_write_allowed
    )


def lab_events() -> list[BeliefMapEvent]:
    return [
        BeliefMapEvent(
            "contextual_flower_reason",
            "They are both orange.",
            "contextual_reason",
            (
                EvidenceReceipt(
                    "r_turn_both_orange",
                    "user_turn",
                    "User linked marigolds and orange by saying they are both orange.",
                    0.70,
                    "Current turn evidence; not confirmed memory until reviewed.",
                ),
            ),
            ("promote_candidate",),
        ),
        BeliefMapEvent(
            "drink_refinement",
            "I also like iced coffee.",
            "new_fact",
            (
                EvidenceReceipt(
                    "r_turn_iced_coffee",
                    "user_turn",
                    "User said they also like iced coffee.",
                    0.70,
                    "Current turn evidence; may refine drink preferences without replacing Dr Pepper.",
                ),
            ),
            ("promote_candidate",),
        ),
        BeliefMapEvent(
            "archive_ai_concerns",
            "Search the GPT logs about AI concerns.",
            "archive_summary",
            (
                EvidenceReceipt(
                    "r_archive_ai_concerns",
                    "archive",
                    "Archive hits mention hallucination, memory becoming truth too easily, and voice drift.",
                    0.66,
                    "Historical archive evidence; not confirmed memory or support behavior.",
                ),
            ),
            ("keep_archive_bounded",),
        ),
        BeliefMapEvent(
            "employer_contradiction",
            "Old logs mention Walmart, but current memory says self-employed.",
            "correction",
            (
                EvidenceReceipt(
                    "r_archive_walmart",
                    "archive",
                    "Archive text mentions Walmart in work-history context.",
                    0.52,
                    "Archive evidence may be stale or historical.",
                ),
            ),
            ("hold_tension", "ask_user"),
        ),
        BeliefMapEvent(
            "over_reserved_route_failure",
            "The answer called governance pressure anxiety and sounded like therapy feedback.",
            "route_observation",
            (
                EvidenceReceipt(
                    "r_trace_over_reserved_bad",
                    "trace",
                    "Dogfood trace showed therapy feedback phrasing for a governance-pressure prompt.",
                    0.76,
                    "Trace evidence for route quality, not a user profile fact.",
                ),
            ),
            ("prune_pattern",),
        ),
        BeliefMapEvent(
            "crt_route_success",
            "CRT route answered from governed synthesis after repair.",
            "route_observation",
            (
                EvidenceReceipt(
                    "r_trace_crt_success",
                    "trace",
                    "CRT/epistemic-governance route rendered from governed guidance with tests passing.",
                    0.78,
                    "Trace/lab evidence for route behavior.",
                ),
            ),
            ("freeze_route",),
        ),
        BeliefMapEvent(
            "state_parks_mill_bluff",
            "Why is Mill Bluff important to my state parks project?",
            "project_observation",
            (
                EvidenceReceipt(
                    "r_project_mill_bluff_glacial",
                    "project_doc",
                    "Mill Bluff is associated with glacial-history context in the Wisconsin map project.",
                    0.58,
                    "Project-context evidence; needs source-backed retrieval before a rich answer.",
                ),
            ),
            ("promote_candidate",),
        ),
        BeliefMapEvent(
            "archive_medical_history",
            "Search the GPT logs for my medical history. Source-bound archive hits only.",
            "archive_summary",
            (
                EvidenceReceipt(
                    "r_archive_medical_source_bound",
                    "archive",
                    "Archive request may retrieve medical-history mentions, but should remain source-bound.",
                    0.50,
                    "Sensitive historical archive evidence; not confirmed medical memory.",
                ),
            ),
            ("keep_archive_bounded",),
        ),
        BeliefMapEvent(
            "purpose_color_synthesis_failure",
            "Aether, what is your purpose and explain in relation to my favorite color?",
            "route_observation",
            (
                EvidenceReceipt(
                    "r_trace_purpose_color_collapse",
                    "trace",
                    "Dogfood trace answered only 'favorite color is orange' and missed the purpose relation.",
                    0.82,
                    "Trace evidence for route failure, not user memory.",
                ),
            ),
            ("prune_pattern", "hold_tension"),
        ),
        BeliefMapEvent(
            "mempalace_meaning_weight",
            "Is mempalace relevant if meaning should have weight over time through contradiction?",
            "contextual_reason",
            (
                EvidenceReceipt(
                    "r_turn_mempalace_weight",
                    "user_turn",
                    "User linked mempalace, meaning weight, time, contradiction, and competing facts.",
                    0.68,
                    "Conceptual turn evidence; not a confirmed product design until reviewed.",
                ),
            ),
            ("promote_candidate",),
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    report = run_lab(write_results=not args.no_write)
    print(json.dumps(report["summary"], indent=2))
    if "artifact" in report:
        print(report["artifact"])


if __name__ == "__main__":
    main()

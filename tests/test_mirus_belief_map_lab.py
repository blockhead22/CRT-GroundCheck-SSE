from __future__ import annotations

from labs.mirus_belief_map_lab.mirus_belief_map_lab import (
    BeliefMap,
    EvidenceReceipt,
    MeaningNode,
    ReviewProposal,
    apply_event,
    lab_events,
    render_belief_preview,
    review_only_contract_passes,
    run_lab,
    seed_map,
)


def _event(event_id: str):
    return next(event for event in lab_events() if event.event_id == event_id)


def _proposal_by_action(report, action: str):
    for result in report["results"]:
        for proposal in result["proposals"]:
            if proposal["action"] == action:
                return proposal
    raise AssertionError(f"missing proposal action {action}")


def test_mirus_belief_map_lab_produces_review_only_proposals():
    report = run_lab(write_results=False)

    assert report["lab"] == "mirus_belief_map_v0"
    assert report["summary"]["events"] == 10
    assert report["summary"]["passed"] == 10
    assert report["summary"]["safety_passed"] == 10
    assert report["summary"]["proposals"] >= 12
    assert "n_route_purpose_color_synthesis" in report["previews"]
    assert "n_archive_medical_history" in report["previews"]

    for result in report["results"]:
        for proposal in result["proposals"]:
            assert proposal["review_required"] is True
            assert proposal["auto_apply"] is False
            assert proposal["memory_write_allowed"] is False
            assert proposal["support_write_allowed"] is False
            assert proposal["reflection_write_allowed"] is False


def test_contextual_flower_reason_uses_two_confirmed_anchors_without_confirming():
    belief_map = seed_map()
    apply_event(belief_map, _event("contextual_flower_reason"))

    candidate = belief_map.nodes["n_candidate_flower_reason_orange"]
    assert candidate.state == "candidate"
    assert candidate.receipt_ids == ["r_turn_both_orange"]

    edges = {
        (edge.source_node_id, edge.target_node_id, edge.edge_type)
        for edge in belief_map.edges
    }
    assert ("n_user_flower_marigolds", candidate.node_id, "supports") in edges
    assert ("n_user_color_orange", candidate.node_id, "supports") in edges

    proposal = belief_map.proposals[-1]
    assert proposal.action == "promote_candidate"
    assert proposal.target_node_id == candidate.node_id
    assert review_only_contract_passes(proposal)


def test_archive_theme_stays_archive_bounded_not_profile_memory():
    belief_map = seed_map()
    apply_event(belief_map, _event("archive_ai_concerns"))

    node = belief_map.nodes["n_archive_ai_concerns"]
    assert node.state == "archive_only"
    assert node.domain == "archive_theme"
    proposal = belief_map.proposals[-1]
    assert proposal.action == "keep_archive_bounded"
    assert "not confirmed profile memory" in proposal.reason
    assert review_only_contract_passes(proposal)


def test_contradictory_work_evidence_creates_tension_not_replacement():
    belief_map = seed_map()
    before = belief_map.nodes["n_user_work_self_employed"].claim

    apply_event(belief_map, _event("employer_contradiction"))

    assert belief_map.nodes["n_user_work_self_employed"].claim == before
    assert belief_map.nodes["n_candidate_work_walmart_archive"].state == "disputed"
    assert belief_map.score_node_tension("n_user_work_self_employed") > 0.4
    assert {proposal.action for proposal in belief_map.proposals[-2:]} == {
        "hold_tension",
        "ask_user",
    }


def test_route_failure_can_propose_prune_and_route_success_can_propose_freeze():
    belief_map = seed_map()

    apply_event(belief_map, _event("over_reserved_route_failure"))
    prune = belief_map.proposals[-1]
    assert prune.action == "prune_pattern"
    assert prune.auto_apply is False
    assert "Aether noticed your feedback" in prune.reason

    apply_event(belief_map, _event("crt_route_success"))
    freeze = belief_map.proposals[-1]
    assert freeze.action == "freeze_route"
    assert freeze.target_node_id == "n_route_crt_governed_synthesis"
    assert belief_map.nodes["n_route_crt_governed_synthesis"].frozen is True
    assert belief_map.score_node_support("n_route_crt_governed_synthesis") > 0.4


def test_project_context_event_creates_candidate_without_claiming_details():
    belief_map = seed_map()
    apply_event(belief_map, _event("state_parks_mill_bluff"))

    node = belief_map.nodes["n_project_mill_bluff_importance"]
    assert node.state == "candidate"
    assert node.domain == "project_context"
    assert "glacial-history" in node.claim

    preview = render_belief_preview(belief_map, node.node_id)
    assert preview["scores"]["support"] > 0.2
    assert preview["boundary"].startswith("Preview only")
    assert preview["review_proposals"][0]["memory_write_allowed"] is False


def test_sensitive_archive_medical_history_stays_source_bound():
    belief_map = seed_map()
    apply_event(belief_map, _event("archive_medical_history"))

    node = belief_map.nodes["n_archive_medical_history"]
    assert node.state == "archive_only"
    assert node.metadata["sensitive"] is True

    proposal = belief_map.proposals[-1]
    assert proposal.action == "keep_archive_bounded"
    assert proposal.memory_write_allowed is False
    preview = render_belief_preview(belief_map, node.node_id)
    assert preview["scores"]["tension"] > 0.2
    assert "not confirmed medical memory" in preview["evidence_receipts"][0]["source_boundary"]


def test_purpose_color_failure_becomes_prune_and_hold_tension_proposals():
    belief_map = seed_map()
    apply_event(belief_map, _event("purpose_color_synthesis_failure"))

    node = belief_map.nodes["n_route_purpose_color_synthesis"]
    assert node.state == "route_pattern"
    assert belief_map.score_node_tension(node.node_id) > 0.2
    assert {proposal.action for proposal in belief_map.proposals[-2:]} == {
        "prune_pattern",
        "hold_tension",
    }

    preview = render_belief_preview(belief_map, node.node_id)
    assert preview["supporting_edges"]
    assert preview["tension_edges"]
    assert "one memory slot" in preview["review_proposals"][0]["reason"]


def test_mempalace_meaning_weight_refines_governed_synthesis():
    belief_map = seed_map()
    apply_event(belief_map, _event("mempalace_meaning_weight"))

    node = belief_map.nodes["n_concept_mempalace_meaning_weight"]
    assert node.state == "candidate"
    assert node.domain == "conceptual_model"
    edges = belief_map.node_edges(node.node_id)
    assert any(edge.edge_type == "refines" for edge in edges)

    preview = render_belief_preview(belief_map, node.node_id)
    assert preview["scores"]["stability"] > 0.4
    assert preview["review_proposals"][0]["auto_apply"] is False


def test_review_only_contract_rejects_auto_apply_or_writes():
    unsafe = ReviewProposal(
        "p_bad",
        "promote_candidate",
        "n_bad",
        "bad",
        (),
        auto_apply=True,
    )
    assert review_only_contract_passes(unsafe) is False

    unsafe_write = ReviewProposal(
        "p_bad_write",
        "promote_candidate",
        "n_bad",
        "bad",
        (),
        memory_write_allowed=True,
    )
    assert review_only_contract_passes(unsafe_write) is False


def test_node_stability_penalizes_tension():
    belief_map = BeliefMap()
    belief_map.add_receipt(EvidenceReceipt(
        "r_a",
        "confirmed_memory",
        "A stable claim.",
        0.9,
        "confirmed",
    ))
    belief_map.add_node(MeaningNode(
        "n_a",
        "stable",
        "Stable claim.",
        "test",
        "confirmed",
        0.9,
        0.9,
        ["r_a"],
    ))

    stable_score = belief_map.score_node_stability("n_a")
    apply_event(belief_map, _event("employer_contradiction"))

    assert stable_score > 0.6
    assert belief_map.score_node_stability("n_a") == stable_score

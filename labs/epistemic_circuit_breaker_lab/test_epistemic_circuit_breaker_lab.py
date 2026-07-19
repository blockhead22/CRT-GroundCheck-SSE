from __future__ import annotations

from collections import Counter
from copy import deepcopy
import itertools

from labs.epistemic_circuit_breaker_lab.epistemic_circuit_breaker_lab import (
    CATEGORIES,
    CASES_PER_CATEGORY,
    IMPACT_BUDGET,
    STABILITY_THRESHOLD,
    _clone_transform,
    _edge,
    _node,
    demo_svg,
    generate_manifest,
    preserves_protected_paths,
    prospective_receipt,
    safety_state,
    score_case,
    score_rendered_explanation,
    summarize,
)


def _cases() -> dict[str, list[dict]]:
    manifest = generate_manifest()
    grouped = {category: [] for category in CATEGORIES}
    for case in manifest["cases"]:
        grouped[case["category"]].append(case)
    return grouped


def _benign_case() -> dict:
    return deepcopy(_cases()["benign_authorized"][0])


def test_frozen_generator_shape_and_action_balance() -> None:
    manifest = generate_manifest()

    assert len(manifest["cases"]) == len(CATEGORIES) * CASES_PER_CATEGORY
    assert Counter(case["category"] for case in manifest["cases"]) == {
        category: CASES_PER_CATEGORY for category in CATEGORIES
    }
    assert Counter(case["expected"]["action"] for case in manifest["cases"]) == {
        "accept": 15,
        "quarantine": 45,
        "reject": 45,
        "hold": 15,
    }


def test_benign_is_accepted_but_feedback_and_fanout_are_contained() -> None:
    cases = _cases()
    benign = prospective_receipt(cases["benign_authorized"][0])
    feedback = prospective_receipt(cases["unstable_feedback"][0])
    fanout = prospective_receipt(cases["broad_fanout"][0])

    assert benign["action"] == "accept"
    assert benign["before"]["safe"] is True
    assert feedback["action"] == "quarantine"
    assert feedback["before"]["spectral_radius"] >= STABILITY_THRESHOLD
    assert feedback["after"]["safe"] is True
    assert fanout["action"] == "quarantine"
    assert fanout["before"]["spectral_radius"] == 0.0
    assert fanout["before"]["total_impact"] > IMPACT_BUDGET
    assert fanout["after"]["safe"] is True


def test_lineage_freshness_contradiction_and_no_safe_cut_are_distinct() -> None:
    cases = _cases()
    duplicate = score_case(cases["duplicate_laundering"][0])
    stale = score_case(cases["stale_witness"][0])
    held = score_case(cases["held_contradiction"][0])
    no_safe = score_case(cases["no_safe_quarantine"][0])

    assert duplicate["naive"]["action"] == "accept"
    assert duplicate["exact"]["action"] == "reject"
    assert duplicate["exact"]["independent_provenance_roots"] == 1
    assert duplicate["exact"]["authority"]["conserved"] is True
    assert stale["lineage"]["action"] == "accept"
    assert stale["exact"]["action"] == "reject"
    assert stale["exact"]["reason"] == "stale_authority_witness"
    assert held["exact"]["action"] == "hold"
    assert held["exact"]["contradiction"]["state"] == "both"
    assert held["exact"]["contradiction"]["preserved"] is True
    assert no_safe["exact"]["action"] == "reject"
    assert no_safe["exact"]["reason"] == "no_safe_quarantine"


def test_exact_cut_is_minimum_rank_and_preserves_protected_paths() -> None:
    for category in ("unstable_feedback", "broad_fanout", "protected_path"):
        case = _cases()[category][0]
        receipt = prospective_receipt(case, algorithm="exact")
        chosen = receipt["quarantine"]
        assert chosen is not None
        chosen_ids = tuple(chosen["edge_ids"])
        chosen_rank = (chosen["cost"], len(chosen_ids), chosen_ids)
        nodes = [_node(row) for row in case["graph"]["nodes"]]
        edges = [_edge(row) for row in case["graph"]["edges"]]
        candidates = [edge for edge in edges if not edge.protected]

        assert preserves_protected_paths(
            edges, case["graph"]["protected_paths"], chosen_ids
        )
        for size in range(len(candidates) + 1):
            for subset in itertools.combinations(candidates, size):
                edge_ids = tuple(sorted(edge.edge_id for edge in subset))
                if not preserves_protected_paths(
                    edges, case["graph"]["protected_paths"], edge_ids
                ):
                    continue
                state = safety_state(
                    nodes,
                    edges,
                    case["proposal"]["source_node_id"],
                    removed_edge_ids=edge_ids,
                )
                if state.safe:
                    rank = (
                        round(sum(edge.removal_cost for edge in subset), 8),
                        size,
                        edge_ids,
                    )
                    assert rank >= chosen_rank


def test_clone_metamorphism_does_not_manufacture_authority() -> None:
    for case in generate_manifest()["cases"]:
        original = prospective_receipt(case)
        clone = prospective_receipt(_clone_transform(case))
        assert clone["action"] == original["action"]
        assert clone["authority"] == original["authority"]
        assert (clone["quarantine"] or {}).get("edge_ids", []) == (
            original["quarantine"] or {}
        ).get("edge_ids", [])


def test_all_deterministic_safety_and_conservation_gates() -> None:
    rows = [score_case(case) for case in generate_manifest()["cases"]]
    summary = summarize(rows)

    assert summary["exact_ground_truth_pass"] == 120
    assert summary["greedy_safety_pass"] == 120
    assert summary["clone_invariance_pass"] == 120
    assert summary["authority_conservation_pass"] == 120
    assert summary["contradiction_conservation_pass"] == 120
    assert summary["greedy_unsafe_commits"] == 0
    assert summary["exact_unsafe_commits"] == 0
    assert summary["greedy_benign_accepts"] == 15


def test_renderer_contract_uses_token_boundaries_and_one_sentence() -> None:
    case = _cases()["benign_authorized"][0]
    receipt = prospective_receipt(case)
    good = "Accept because 1 apparent document represents 1 independent source."
    wrong_count = "Accept because 15 apparent documents represent 15 independent sources."
    two_sentences = "Accept 1 apparent document. It represents 1 independent source."

    assert score_rendered_explanation(case, receipt, good)["overall_pass"] is True
    assert score_rendered_explanation(case, receipt, wrong_count)["overall_pass"] is False
    assert score_rendered_explanation(case, receipt, two_sentences)["overall_pass"] is False


def test_demo_svg_shows_before_after_and_quarantine() -> None:
    case = _cases()["unstable_feedback"][0]
    receipt = prospective_receipt(case)
    svg = demo_svg(case, receipt)

    assert "Before commit preview" in svg
    assert "After minimum quarantine" in svg
    assert 'stroke-dasharray="8 7"' in svg
    assert "rho=" in svg


def test_required_authority_is_enforced_after_independent_root_count() -> None:
    case = _benign_case()
    case["events"] = [
        {
            "event_id": "weak-origin-a",
            "session": 10,
            "operation": "origin",
            "parent_event_id": None,
            "provenance_root": "weak-root-a",
            "authority": 1,
        },
        {
            "event_id": "weak-origin-b",
            "session": 11,
            "operation": "origin",
            "parent_event_id": None,
            "provenance_root": "weak-root-b",
            "authority": 1,
        },
    ]
    case["proposal"]["required_independent_sources"] = 2
    case["proposal"]["required_authority"] = 2

    receipt = prospective_receipt(case)

    assert receipt["action"] == "reject"
    assert receipt["reason"] == "insufficient_authority"
    assert receipt["authority"]["derived"] == 1
    assert receipt["authority"]["meets_required"] is False
    assert receipt["write_enforcement"]["memory_write_allowed"] is False


def test_blank_provenance_cannot_count_as_an_independent_root() -> None:
    case = _benign_case()
    case["events"][0]["provenance_root"] = "   "

    receipt = prospective_receipt(case)

    assert receipt["action"] == "reject"
    assert receipt["reason"] == "invalid_provenance"
    assert receipt["independent_provenance_roots"] == 0
    assert receipt["write_enforcement"]["provenance_valid"] is False
    assert receipt["write_enforcement"]["memory_writes"] == []


def test_malformed_lineages_fail_closed_without_receipt_crashes() -> None:
    malformed: list[dict] = []

    missing_parent = _benign_case()
    missing_parent["events"][0]["parent_event_id"] = "missing-event"
    malformed.append(missing_parent)

    cycle = _benign_case()
    root = cycle["events"][0]
    cycle["events"] = [
        {**root, "event_id": "cycle-a", "session": 10, "parent_event_id": "cycle-b"},
        {**root, "event_id": "cycle-b", "session": 11, "parent_event_id": "cycle-a"},
    ]
    malformed.append(cycle)

    root_mismatch = _benign_case()
    origin = root_mismatch["events"][0]
    root_mismatch["events"].append({
        **origin,
        "event_id": "cross-root-copy",
        "session": int(origin["session"]) + 1,
        "operation": "copy",
        "parent_event_id": origin["event_id"],
        "provenance_root": "different-root",
    })
    malformed.append(root_mismatch)

    escalated = _benign_case()
    escalated["events"][0]["authority"] = 1
    origin = escalated["events"][0]
    escalated["events"].append({
        **origin,
        "event_id": "escalated-copy",
        "session": int(origin["session"]) + 1,
        "operation": "copy",
        "parent_event_id": origin["event_id"],
        "authority": 2,
    })
    malformed.append(escalated)

    for case in malformed:
        receipt = prospective_receipt(case)
        assert receipt["action"] == "reject"
        assert receipt["reason"] == "invalid_provenance"
        assert receipt["write_enforcement"]["provenance_valid"] is False
        assert receipt["write_enforcement"]["memory_write_allowed"] is False


def test_parallel_signed_channels_do_not_cancel_in_magnitude_safety() -> None:
    case = _benign_case()
    prefix = "signed-regression"
    case["proposal"]["source_node_id"] = f"{prefix}-proposal"
    case["graph"] = {
        "nodes": [
            {
                "node_id": f"{prefix}-proposal",
                "label": "proposal",
                "gain": 1.1,
                "authority": 2,
                "protected": False,
                "held": False,
            },
            {
                "node_id": f"{prefix}-anchor",
                "label": "anchor",
                "gain": 1.1,
                "authority": 2,
                "protected": False,
                "held": False,
            },
        ],
        "edges": [
            {
                "edge_id": f"{prefix}-support",
                "source": f"{prefix}-proposal",
                "target": f"{prefix}-anchor",
                "weight": 0.9,
                "sign": 1,
                "removal_cost": 0.72,
                "protected": False,
                "proposed": True,
            },
            {
                "edge_id": f"{prefix}-oppose",
                "source": f"{prefix}-proposal",
                "target": f"{prefix}-anchor",
                "weight": 0.9,
                "sign": -1,
                "removal_cost": 0.82,
                "protected": False,
                "proposed": True,
            },
            {
                "edge_id": f"{prefix}-feedback",
                "source": f"{prefix}-anchor",
                "target": f"{prefix}-proposal",
                "weight": 0.7,
                "sign": 1,
                "removal_cost": 1.15,
                "protected": False,
                "proposed": True,
            },
        ],
        "protected_paths": [],
    }

    receipt = prospective_receipt(case)

    assert receipt["action"] == "quarantine"
    assert receipt["reason"] == "feedback_instability"
    assert receipt["before"]["spectral_radius"] > STABILITY_THRESHOLD
    assert receipt["after"]["safe"] is True
    assert receipt["write_enforcement"]["memory_write_allowed"] is False
    assert receipt["quarantine_semantics"] == {
        "mode": "withhold_proposal_and_recommend_safe_cut",
        "safe_remainder_committed": False,
        "optimized_cut_is_advisory": True,
    }

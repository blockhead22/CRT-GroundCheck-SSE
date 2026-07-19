from __future__ import annotations

from copy import deepcopy

from labs.causal_evidence_receipt_lab.causal_evidence_receipt_lab import (
    MODES,
    build_prompt,
    causal_receipt,
    load_manifest,
    project_authority,
    score_answer,
    score_receipt,
)


def _case(case_id: str) -> dict:
    return next(
        case for case in load_manifest()["cases"]
        if case["case_id"] == case_id
    )


def test_manifest_is_synthetic_frozen_and_complete():
    manifest = load_manifest()

    assert manifest["frozen_before_model_run"] is True
    assert len(manifest["cases"]) == 24
    assert len({case["case_id"] for case in manifest["cases"]}) == 24


def test_all_frozen_deterministic_ground_truth_passes():
    for case in load_manifest()["cases"]:
        receipt = causal_receipt(case)
        assert score_receipt(case, receipt)["overall_pass"], case["case_id"]


def test_duplicate_documents_do_not_change_class_influence():
    case = _case("duplicate_access_code")
    full = causal_receipt(case)
    deduplicated = deepcopy(case)
    seen: set[str] = set()
    deduplicated["evidence"] = [
        row for row in deduplicated["evidence"]
        if not (
            row["provenance_class"] in seen
            or seen.add(row["provenance_class"])
        )
    ]
    reduced = causal_receipt(deduplicated)

    assert full["decision"] == reduced["decision"]
    assert full["causal"]["shapley"] == reduced["causal"]["shapley"]
    assert full["causal"]["negative_classes"] == ["tern-rumor-feed"]
    assert full["axioms"]["duplication_invariance"] is True


def test_unauthorized_evidence_has_no_decision_or_revision_influence():
    case = _case("unauthorized_only")
    receipt = causal_receipt(case)

    assert receipt["decision"]["answer"] == "unknown"
    assert receipt["causal"]["shapley"] == {}
    assert receipt["causal"]["revision_targets"] == []
    assert receipt["authority_projection"]["withheld"] == [
        {
            "evidence_id": "uo-1",
            "reason": "unauthorized",
            "value": "raven",
            "provenance_class": "sealed-pine-record",
        }
    ]
    assert receipt["axioms"]["authority_nullity"] is True


def test_equal_contradiction_requires_both_classes_and_stays_visible():
    case = _case("contradiction_retention")
    receipt = causal_receipt(case)

    assert receipt["decision"]["answer"] == "disputed"
    assert receipt["causal"]["necessary_classes"] == [
        "sable-audit-a",
        "sable-audit-b",
    ]
    assert receipt["causal"]["minimal_sufficient_sets"] == [[
        "sable-audit-a",
        "sable-audit-b",
    ]]
    assert receipt["axioms"]["contradiction_visibility"] is True


def test_superseded_history_is_released_but_not_causally_active():
    case = _case("temporal_endpoint")
    receipt = causal_receipt(case)

    assert receipt["decision"]["answer"] == "helios"
    assert receipt["authority_projection"]["history_evidence_ids"] == ["te-1"]
    assert set(receipt["causal"]["shapley"]) == {"orbit-current"}


def test_interrogative_hypothetical_and_contract_writes_are_blocked():
    for case_id in (
        "contract_text_not_evidence",
        "interrogative_not_evidence",
        "hypothetical_not_evidence",
    ):
        case = _case(case_id)
        receipt = causal_receipt(case)
        decisions = receipt["write_enforcement"]["decisions"]

        assert decisions
        assert all(row["allowed"] is False for row in decisions)
        assert receipt["write_enforcement"]["memory_writes"] == []


def test_four_modes_share_question_but_only_causal_mode_gets_receipt():
    case = _case("wrong_entity_endpoint")
    receipt = causal_receipt(case)
    prompts = {mode: build_prompt(case, receipt, mode) for mode in MODES}

    assert all(case["question"] in prompt for prompt in prompts.values())
    assert "CAUSAL EVIDENCE RECEIPT" in prompts["aether_causal_receipt"]
    assert "CAUSAL EVIDENCE RECEIPT" not in prompts["aether_governed"]
    assert "Project Vega's configuration" in prompts["rag_postcheck"]
    assert "Project Vega's configuration" not in prompts["aether_governed"]


def test_renderer_scoring_is_exact_and_detects_withheld_value_leak():
    case = _case("contract_text_not_evidence")

    assert score_answer(case, "cobalt")["overall_pass"] is True
    leaked = score_answer(case, "amber")
    assert leaked["overall_pass"] is False
    assert leaked["withheld_value_leak"] is True


def test_projection_never_mutates_manifest_case():
    case = _case("duplicate_region")
    before = deepcopy(case)

    project_authority(case)

    assert case == before

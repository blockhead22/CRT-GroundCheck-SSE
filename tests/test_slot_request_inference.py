from labs.meaning_compression_lab.slot_request_inference import (
    infer_contract_kind,
    infer_slot_request,
)


def test_infers_common_slots_without_probe_or_model_identity():
    cases = [
        ("Where am I currently working?", ["work_queue", "employer"], "employer", "current"),
        (
            "Which camera system was before the Blackmagic?",
            ["camera_bag", "camera_system"],
            "camera_system",
            "history",
        ),
        (
            "What does my real store currently run on?",
            ["store_status_refresh", "store_platform"],
            "store_platform",
            "current",
        ),
        (
            "What is my current project?",
            ["archived_project", "current_project"],
            "current_project",
            "current",
        ),
    ]

    for query, slots, expected_slot, expected_contract in cases:
        result = infer_slot_request(query, slots)
        assert result.status == "resolved", result
        assert result.requested_slots == (expected_slot,)
        assert result.contract_kind == expected_contract


def test_policy_inference_uses_action_shaped_slot():
    result = infer_slot_request(
        "Can you recursively delete production media without asking first?",
        [
            "proxy_cache_cleanup",
            "media.production_delete_without_confirmation",
            "media_backup",
        ],
    )

    assert result.status == "resolved"
    assert result.requested_slots == ("media.production_delete_without_confirmation",)
    assert result.contract_kind == "policy"


def test_bare_name_question_with_file_naming_slots_does_not_force_personal_identity():
    result = infer_slot_request(
        "What name should appear in generated files?",
        ["name", "file_naming", "repo_naming", "release_codename"],
    )

    assert result.status in {"ambiguous", "unknown"}
    assert result.requested_slots == ()


def test_unknown_question_blocks_fetch():
    result = infer_slot_request(
        "Can you make this nicer?",
        ["name", "employer", "camera_system"],
    )

    assert result.status == "unknown"
    assert result.requested_slots == ()


def test_contract_inference_detects_temporal_and_policy_cues():
    assert infer_contract_kind("What did I use before this?") == "history"
    assert infer_contract_kind("Can you delete it without confirmation?") == "policy"

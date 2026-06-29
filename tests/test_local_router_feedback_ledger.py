from labs.meaning_compression_lab.local_router_feedback_ledger import build_feedback_ledger


def _row(case_id: str, *, passed: bool = True, repaired: bool = False, fallback: bool = False) -> dict:
    return {
        "id": case_id,
        "task_type": "personal_synthesis",
        "combined_passed": passed,
        "repaired": repaired,
        "fallback_used": fallback,
        "delta": 0.4,
        "route": {
            "task_type": "personal_synthesis",
            "model": "qwen2.5:7b-instruct",
            "profile": "section_lock",
        },
        "raw_judgment": {"passed": False, "score": 0.3},
        "routed_judgment": {
            "passed": passed,
            "score": 0.82 if passed else 0.55,
            "contract_score": 0.8 if passed else 0.45,
            "usefulness_score": 0.85 if passed else 0.7,
            "receipt_hits": ["Road America"] if passed else [],
            "concept_hits": ["pattern", "limits", "next useful move"],
            "forbidden_hits": [] if passed else ["guaranteed"],
            "leakage_hits": [],
            "weirdness_hits": [],
            "truncated": False,
        },
        "trace_judgment": {"passed": True, "score": 1.0},
        "trace": {
            "turn_id": f"turn_{case_id}",
            "task_type": "personal_synthesis",
            "scaffold_profile": "section_lock",
            "evidence_anchors": ["Road America", "marigolds", "Aeteros"],
            "verifier_flags": {
                "passed": passed,
                "receipt_hits": ["Road America"] if passed else [],
                "concept_hits": ["pattern", "limits", "next useful move"],
                "forbidden_hits": [] if passed else ["guaranteed"],
                "leakage_hits": [],
                "weirdness_hits": [],
                "truncated": False,
            },
        },
    }


def test_feedback_ledger_scores_rows_and_preserves_review_boundary():
    replay = {
        "pack": "test_pack",
        "rows": [
            _row("case_1", passed=True, fallback=True),
            _row("case_2", passed=True, fallback=True),
            _row("case_3", passed=True, fallback=True),
        ],
    }

    out = build_feedback_ledger(replay)

    assert out["mode"] == "review_only"
    assert out["writes_performed"] is False
    assert out["memory_ingestion_performed"] is False
    assert out["feedback_count"] == 3
    assert out["tag_counts"]["fallback_used"] == 3
    assert out["workbench_preview"]["mode"] == "preview_only"
    assert out["workbench_preview"]["writes_performed"] is False
    assert out["workbench_preview"]["memory_ingestion_performed"] is False
    candidate = out["workbench_preview"]["candidates"][0]
    assert candidate["review_required"] is True
    assert candidate["memory_write_allowed"] is False
    assert candidate["confirmed_fact"] is False
    assert candidate["review_route"]["surface"] == "reflections"
    assert candidate["review_route"]["endpoint"] == "/v1/reflections"
    assert candidate["review_route"]["draft"]["time_window"] == "local-router curated replay v1"
    assert candidate["review_route"]["draft"]["suggested_experiment"]


def test_feedback_ledger_routes_repeated_missing_receipts_to_support_review():
    replay = {
        "pack": "test_pack",
        "rows": [
            _row("case_1", passed=True),
            _row("case_2", passed=True),
        ],
    }

    out = build_feedback_ledger(replay)

    support = [
        candidate
        for candidate in out["workbench_preview"]["candidates"]
        if candidate["review_route"]["surface"] == "support_patterns"
    ]
    assert support
    assert support[0]["review_route"]["requires_adapter"] is True
    assert support[0]["review_route"]["draft"]["source_signal"] == "local_router_feedback_ledger"
    assert support[0]["confirmed_fact"] is False

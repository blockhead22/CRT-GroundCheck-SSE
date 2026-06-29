from labs.meaning_compression_lab.workbench_trace_adapter import adapt_local_router_trace_for_workbench


def _trace(passed: bool = True) -> dict:
    return {
        "trace_schema": "aether.local_router.trace.v0",
        "turn_id": "local_router_cli:cli_grant_business:1",
        "conversation_id": "local_router_cli",
        "source": "local_router_cli",
        "user_request_summary": "Frame Aether as a practical grant direction.",
        "task_type": "grant_business",
        "route_selected": {
            "task_type": "grant_business",
            "model": "qwen2.5:7b-instruct",
            "profile": "section_lock",
            "reason": "Grant/business framing benefits from compact sections.",
            "fallback_model": "qwen2.5:7b-instruct",
            "fallback_profile": "semantic_spine",
        },
        "model_selected": "qwen2.5:7b-instruct",
        "scaffold_profile": "section_lock",
        "mirus_packet_summary": {
            "task_type": "grant_business",
            "evidence_anchor_count": 3,
            "required_concept_count": 5,
            "output_scaffold": ["need", "measurable claim", "limits"],
        },
        "evidence_anchors": ["local", "CRT", "Aether"],
        "disallowed_inferences": ["guaranteed", "frontier"],
        "draft_quality_score": 0.84 if passed else 0.55,
        "contract_score": 0.87 if passed else 0.45,
        "usefulness_score": 0.8 if passed else 0.7,
        "verifier_flags": {
            "passed": passed,
            "truncated": False,
            "leakage_hits": [],
            "weirdness_hits": [],
            "forbidden_hits": [] if passed else ["frontier"],
            "receipt_hits": ["local", "CRT", "Aether"] if passed else ["local"],
            "concept_hits": ["measurable", "business", "verifier", "low-cost", "AI request router"]
            if passed
            else ["business"],
        },
        "repair_attempts": 0 if passed else 1,
        "fallback_used": False,
        "final_confidence": "high" if passed else "low",
        "contradiction_notes": [],
        "learning_candidates": [],
        "promotion_status": "none",
        "raw_chain_of_thought_stored": False,
    }


def test_local_router_trace_maps_to_workbench_route_and_plan_shape():
    out = adapt_local_router_trace_for_workbench(_trace())

    assert out["status"] == "resolved"
    assert out["query"] == "Frame Aether as a practical grant direction."
    assert out["model"] == "qwen2.5:7b-instruct"
    assert out["plan"]["coverage"] == 1.0
    assert out["route_decision"]["selected_route"] == "local_router_grant_business"
    assert out["route_decision"]["memory_write_allowed"] is False
    assert out["route_decision"]["silent_escalation_allowed"] is False
    assert out["route_decision"]["model_recommendation"]["observational_only"] is True
    assert out["local_router_trace"]["raw_chain_of_thought_stored"] is False
    assert {packet["slot_id"] for packet in out["packets"]} == {
        "lab:route",
        "lab:mirus_packet",
        "lab:verifier",
    }
    assert all(packet["evidence"] == [] for packet in out["packets"])


def test_failed_local_router_trace_maps_to_review_needed_without_memory_claims():
    out = adapt_local_router_trace_for_workbench(_trace(passed=False))

    assert out["status"] == "needs_review"
    assert out["completion"]["needs_stronger_model"] is True
    assert out["completion"]["guidance_repaired"] is True
    assert out["completion"]["guidance_repair_failed"] is True
    assert "forbidden_hits: frontier" in out["plan"]["unresolved_clauses"]
    verifier = next(packet for packet in out["packets"] if packet["slot_id"] == "lab:verifier")
    assert verifier["release"] == "conflict"
    assert verifier["reason"] == "forbidden_hits"
    assert verifier["evidence"] == []

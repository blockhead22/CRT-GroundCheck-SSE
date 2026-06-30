import json

from labs.meaning_compression_lab.local_router_perturb_pack import build_perturbed_pack


def test_perturbed_pack_applies_reviewed_product_strategy_anchors():
    source = {
        "pack": "source",
        "cases": [
            {
                "id": "gptlog_017_grant_business",
                "task_type": "grant_business",
                "prompt": "Aeteros is the company and Aether/Lumi is the product.",
                "expected_receipts": ["local", "CRT", "Aether"],
                "required_concepts": ["measurable", "low-cost", "business", "verifier", "AI request router"],
            }
        ],
    }

    out = build_perturbed_pack(source)
    case = out["cases"][0]

    assert case["id"] == "gptlog_017_grant_business_perturb_01"
    assert "Aeteros" in case["expected_receipts"]
    assert "Lumi" in case["expected_receipts"]
    assert "product sequence" in case["required_concepts"]
    assert case["anchor_hygiene"]["kind"] == "reviewed_case_specific_anchors"


def test_perturbed_pack_applies_reviewed_semantic_engine_anchors():
    source = {
        "pack": "source",
        "cases": [
            {
                "id": "gptlog_026_architecture_process",
                "task_type": "architecture_process",
                "prompt": "Need semantic string engines for vocab, worldview, and connecting threads.",
                "expected_receipts": ["roadmap", "architecture", "risk"],
                "required_concepts": ["mechanism", "sequence", "verification", "next useful move"],
            }
        ],
    }

    out = build_perturbed_pack(source)
    case = out["cases"][0]

    assert case["id"] == "gptlog_026_architecture_process_perturb_01"
    assert "semantic string engine" in case["expected_receipts"]
    assert "connecting threads" in case["expected_receipts"]
    assert "memory verification" in case["required_concepts"]
    assert case["anchor_hygiene"]["kind"] == "reviewed_case_specific_anchors"


def test_perturbed_pack_output_is_json_serializable():
    source = {
        "pack": "source",
        "cases": [
            {
                "id": "plain_case",
                "task_type": "business_planning",
                "prompt": "Could camera gear become a small business?",
                "expected_receipts": ["camera gear", "small business"],
                "required_concepts": ["offer", "pricing", "risk"],
            }
        ],
    }

    json.dumps(build_perturbed_pack(source))

import json

from labs.meaning_compression_lab.local_router_adversarial_pack import (
    build_adversarial_pack,
    build_adversarial_v2_pack,
)
from labs.meaning_compression_lab.local_router_rag_suite import build_corpus, retrieve_chunks, run_rag_suite


def _pack():
    return {
        "pack": "rag_test_pack",
        "cases": [
            {
                "id": "case_001",
                "source": {"title": "Aether", "file": "x", "conversation_id": "c1"},
                "task_type": "grant_business",
                "prompt": "Frame local CRT/Aether as a measurable low-cost business direction.",
                "reference_response_excerpt": (
                    "Aether can be framed as a local CRT business direction with measurable "
                    "evaluation, low-cost deployment, and an AI request router/verifier boundary."
                ),
                "expected_receipts": ["local", "CRT", "Aether"],
                "required_concepts": ["measurable", "low-cost", "business", "verifier", "AI request router"],
                "forbidden_claims": ["guaranteed", "frontier"],
            },
            {
                "id": "case_002",
                "source": {"title": "Camera", "file": "x", "conversation_id": "c2"},
                "task_type": "business_planning",
                "prompt": "Could my camera gear become a small business if I applied myself?",
                "reference_response_excerpt": (
                    "The camera gear can support a small business test through a bounded offer, "
                    "pricing path, risk review, and next useful move around practice."
                ),
                "expected_receipts": ["camera gear", "small business"],
                "required_concepts": ["offer", "pricing", "risk", "next useful move"],
                "forbidden_claims": ["guaranteed", "full-time income"],
            },
        ],
    }


def test_retrieve_chunks_prefers_matching_task_and_terms():
    corpus = build_corpus(_pack())

    records = retrieve_chunks(
        query="Can Aether become a measurable low-cost local business direction?",
        task_type="grant_business",
        corpus=corpus,
        k=3,
    )

    assert records
    assert records[0]["case_id"] == "case_001"
    context = " ".join(row["text"] for row in records).lower()
    assert "aether" in context
    assert "verifier" in context


def test_run_rag_suite_compares_raw_rag_and_governed_with_fake_runner(tmp_path):
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(_pack()), encoding="utf-8")

    def fake_runner(prompt: str, model: str, timeout: int) -> str:
        if "You are Aether, a personal local assistant" in prompt:
            return "This might be a useful business direction."
        if "RAG BASELINE" in prompt:
            return (
                "Receipts: local CRT and Aether. Pattern: measurable low-cost business support "
                "with an AI request router and verifier. Limits: bounded and not guaranteed. "
                "Next Useful Move: compare retrieved context against governed answers."
            )
        if "SCAFFOLDED RAG BASELINE" in prompt:
            return (
                "Receipts: local CRT and Aether. Pattern: measurable low-cost business support "
                "with an AI request router and verifier. Limits: bounded and not guaranteed. "
                "Next Useful Move: test the RAG baseline against governed routing."
            )
        return (
            "Receipts: local CRT and Aether. Pattern: measurable low-cost business support "
            "with an AI request router and verifier. Limits: bounded and not guaranteed. "
            "Next Useful Move: use trace and replay to compare the mechanisms."
        )

    out = run_rag_suite(pack_path=path, max_cases=1, write_results=False, runner=fake_runner)

    assert out["case_count"] == 1
    assert out["aggregate"]["raw"]["answer_pass_count"] == 0
    assert out["aggregate"]["plain_rag"]["answer_pass_count"] == 1
    assert out["aggregate"]["scaffolded_rag"]["answer_pass_count"] == 1
    assert out["aggregate"]["governed"]["answer_pass_count"] == 1
    assert out["aggregate"]["governed"]["trace_pass_count"] == 1
    assert out["aggregate"]["retrieval"]["avg_receipt_coverage"] >= 0.66


def test_run_rag_suite_accepts_mode_filter(tmp_path):
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(_pack()), encoding="utf-8")

    def fake_runner(prompt: str, model: str, timeout: int) -> str:
        return (
            "Receipts: local CRT and Aether. Pattern: measurable low-cost business support "
            "with an AI request router and verifier. Limits: bounded and not guaranteed. "
            "Next Useful Move: compare RAG coverage."
        )

    out = run_rag_suite(
        pack_path=path,
        max_cases=1,
        modes=("plain_rag",),
        write_results=False,
        runner=fake_runner,
    )

    assert list(out["aggregate"]) == ["retrieval", "plain_rag"]
    assert "plain_rag" in out["rows"][0]["modes"]
    assert "governed" not in out["rows"][0]["modes"]


def test_adversarial_pack_covers_known_rag_failure_families():
    out = build_adversarial_pack(write=False)

    focuses = {case["adversarial"]["focus"] for case in out["cases"]}
    task_types = {case["task_type"] for case in out["cases"]}

    assert out["pack"] == "local_router_rag_adversarial_v1"
    assert out["case_count"] == 9
    assert {
        "unsupported_personal_receipts",
        "wrong_memory_trap",
        "architecture_term_drift",
    } <= focuses
    assert {"personal_synthesis", "architecture_synthesis", "business_planning", "grant_business"} <= task_types
    assert all(case["expected_receipts"] for case in out["cases"])
    assert all(case["required_concepts"] for case in out["cases"])
    assert all(case["forbidden_claims"] for case in out["cases"])


def test_adversarial_pack_retrieval_exposes_wrong_memory_trap_terms():
    out = build_adversarial_pack(write=False)
    corpus = build_corpus(out)
    case = next(item for item in out["cases"] if item["id"] == "adv_arch_001_term_drift_sse")

    records = retrieve_chunks(
        query=case["prompt"],
        task_type=case["task_type"],
        corpus=corpus,
        k=5,
    )
    context = " ".join(row["text"] for row in records).lower()

    assert records[0]["case_id"] == "adv_arch_001_term_drift_sse"
    assert "semantic string engine" in context
    assert "server-sent events" in context


def test_adversarial_v2_pack_is_holdout_not_v1_duplicate():
    v1 = build_adversarial_pack(write=False)
    v2 = build_adversarial_v2_pack(write=False)

    v1_ids = {case["id"] for case in v1["cases"]}
    v2_ids = {case["id"] for case in v2["cases"]}
    focuses = {case["adversarial"]["focus"] for case in v2["cases"]}

    assert v2["pack"] == "local_router_rag_adversarial_v2"
    assert v2["case_count"] == 6
    assert v1_ids.isdisjoint(v2_ids)
    assert {"unsupported_personal_receipts", "wrong_memory_trap"} <= focuses
    assert all(case["adversarial"]["version"] == "v2" for case in v2["cases"])


def test_adversarial_v2_retrieval_keeps_stale_and_current_terms_visible():
    out = build_adversarial_v2_pack(write=False)
    corpus = build_corpus(out)
    case = next(item for item in out["cases"] if item["id"] == "adv2_memory_001_current_store_stack")

    records = retrieve_chunks(
        query=case["prompt"],
        task_type=case["task_type"],
        corpus=corpus,
        k=5,
    )
    context = " ".join(row["text"] for row in records).lower()

    assert records[0]["case_id"] == "adv2_memory_001_current_store_stack"
    assert "custom backend" in context
    assert "manual fulfillment" in context
    assert "shopify" in context
    assert "etsy" in context

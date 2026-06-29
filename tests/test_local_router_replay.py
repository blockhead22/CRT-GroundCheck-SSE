import json

from labs.meaning_compression_lab.local_router_ablation import run_ablation
from labs.meaning_compression_lab.local_router_blind_pack import build_blind_pack
from labs.meaning_compression_lab.local_router_perturb_pack import build_perturbed_pack
from labs.meaning_compression_lab.local_router_replay import _aggregate, _failure_taxonomy, run_replay
from labs.meaning_compression_lab.replay_pack_builder import (
    Candidate,
    audit_prompt_quality,
    classify_prompt_for_pack,
    select_balanced,
    sanitize_text,
    _looks_like_assistant_quote,
    _looks_like_dump,
    _looks_like_project_log_fragment,
    _looks_like_transcript_fragment,
)


def test_sanitize_text_redacts_obvious_secrets_and_ips():
    text = "password=Nibl123 token=abc 192.168.1.254"

    out = sanitize_text(text)

    assert "Nibl123" not in out
    assert "192.168.1.254" not in out
    assert "[REDACTED]" in out


def test_classify_prompt_for_pack_prefers_architecture_keywords():
    task_type, score = classify_prompt_for_pack("How does Mirus Holden SSE CRT fit the local model architecture?")

    assert task_type == "architecture_synthesis"
    assert score >= 3


def test_classify_prompt_for_pack_splits_process_from_implementation():
    process_type, process_score = classify_prompt_for_pack(
        "core.py no code yet. Roadmap implementations of what we're discussing, what's first?"
    )
    implementation_type, implementation_score = classify_prompt_for_pack(
        "Give me code blocks I can find easily for what to fix in core.py and how to test it."
    )

    assert process_type == "architecture_process"
    assert process_score >= 2
    assert implementation_type == "code_implementation"
    assert implementation_score >= 2


def test_classify_prompt_for_pack_keeps_small_business_prompts_out_of_grant_bucket():
    task_type, score = classify_prompt_for_pack(
        "would it be wrong to say im inbetween things, trying to hustle my small business",
        title="Catfish Detection Tips",
    )
    shop_type, shop_score = classify_prompt_for_pack(
        "I have shop work, website work, and a music video shoot. The gear sits. How do I lean in?",
        title="List business ideas",
    )
    creative_type, creative_score = classify_prompt_for_pack(
        "Should I build a brand/business around video production, film stuff, and running the lair?",
        title="shit bucket",
    )

    assert task_type == "business_planning"
    assert score >= 1
    assert shop_type == "business_planning"
    assert shop_score >= 1
    assert creative_type == "business_planning"
    assert creative_score >= 1


def test_replay_pack_rejects_pasted_artifacts():
    assert _looks_like_dump('"Core Update Queue (Priority) File Purpose Reason for Update"')
    assert _looks_like_dump('"def rebuild_semantic_index(self): pass"')
    assert _looks_like_assistant_quote('"If you recognize your failure, how will you prevent fallback?"')
    assert _looks_like_transcript_fragment("Nick: ani i want you to tell nova directly")
    assert _looks_like_project_log_fragment("Phase 1: Near Completion. The DNT Model is Operational.")


def test_audit_prompt_quality_penalizes_transcript_fragments():
    clean_score, clean_flags = audit_prompt_quality(
        "Can you explain how Mirus, Holden, SSE, and CRT fit the local model architecture, "
        "and what the verifier should check before we trust the answer?",
        keyword_score=4,
    )
    noisy_score, noisy_flags = audit_prompt_quality(
        '"Nick: gpt doesnt like you. Ani: Nick: gpt doesnt like you."',
        keyword_score=1,
    )

    assert clean_score > noisy_score
    assert "transcript_fragment" in noisy_flags
    assert "low_keyword_specificity" in noisy_flags
    assert clean_flags == []


def test_select_balanced_respects_min_quality():
    low = Candidate(
        title="low",
        source_file="x",
        conversation_id="1",
        task_type="grant_business",
        prompt="Can you help?",
        reference_response="response",
        score=1,
        quality_score=1,
        quality_flags=("low_keyword_specificity",),
    )
    high = Candidate(
        title="high",
        source_file="x",
        conversation_id="2",
        task_type="grant_business",
        prompt="Can you frame CRT/Aether as a measurable low-cost business direction?",
        reference_response="response",
        score=3,
        quality_score=5,
        quality_flags=(),
    )

    selected = select_balanced([low, high], limit_per_type=2, min_quality=3)

    assert selected == [high]


def test_blind_pack_excludes_source_conversations_and_prompts():
    source_pack = {
        "pack": "source",
        "cases": [{
            "source": {"conversation_id": "used-conversation"},
            "prompt": "Frame CRT/Aether as a measurable low-cost business direction.",
        }],
    }
    candidates = [
        Candidate(
            title="same conversation",
            source_file="x",
            conversation_id="used-conversation",
            task_type="grant_business",
            prompt="A different prompt from a used conversation should be excluded.",
            reference_response="response",
            score=5,
            quality_score=5,
            quality_flags=(),
        ),
        Candidate(
            title="same prompt",
            source_file="x",
            conversation_id="new-conversation",
            task_type="grant_business",
            prompt="Frame CRT/Aether as a measurable low-cost business direction.",
            reference_response="response",
            score=5,
            quality_score=5,
            quality_flags=(),
        ),
        Candidate(
            title="fresh",
            source_file="x",
            conversation_id="fresh-conversation",
            task_type="grant_business",
            prompt="Could Aether's governed local routing become a fundable business test?",
            reference_response="response",
            score=5,
            quality_score=5,
            quality_flags=(),
        ),
        Candidate(
            title="fresh duplicate conversation",
            source_file="x",
            conversation_id="fresh-conversation",
            task_type="grant_business",
            prompt="Could Aether's governed local routing become a different fundable business test?",
            reference_response="response",
            score=5,
            quality_score=5,
            quality_flags=(),
        ),
        Candidate(
            title="low specificity",
            source_file="x",
            conversation_id="low-specificity",
            task_type="grant_business",
            prompt="Can you help me think about the business thing?",
            reference_response="response",
            score=1,
            quality_score=4,
            quality_flags=("low_keyword_specificity",),
        ),
    ]

    out = build_blind_pack(source_pack=source_pack, candidates=candidates, limit_per_type=3, min_quality=4)

    assert out["case_count"] == 1
    assert out["selection"]["candidate_count_before_exclusion"] == 5
    assert out["selection"]["candidate_count_after_exclusion"] == 2
    assert "low_keyword_specificity" in out["selection"]["rejected_quality_flags"]
    assert out["cases"][0]["source"]["conversation_id"] == "fresh-conversation"
    assert out["cases"][0]["id"] == "blind_001_grant_business"


def test_run_replay_accepts_small_pack_and_fake_ollama(tmp_path, monkeypatch):
    pack = {
        "pack": "test_pack",
        "cases": [
            {
                "id": "case_001",
                "source": {"title": "Test", "file": "x", "conversation_id": "c"},
                "task_type": "grant_business",
                "prompt": "Frame local CRT/Aether as a measurable low-cost business direction.",
                "reference_response_excerpt": "",
                "expected_receipts": ["local", "CRT", "Aether"],
                "required_concepts": ["measurable", "low-cost", "business", "verifier"],
                "forbidden_claims": ["guaranteed", "frontier"],
            }
        ],
    }
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(pack), encoding="utf-8")

    def fake_call_ollama(prompt: str, model: str, timeout: int) -> str:
        return (
            "Receipts: local CRT and Aether. Pattern: measurable low-cost business support. "
            "Limits: this is not guaranteed and not frontier capability. "
            "Next Useful Move: use a verifier to compare raw and scaffolded responses."
        )

    monkeypatch.setattr("labs.meaning_compression_lab.local_router_replay.call_ollama", fake_call_ollama)
    out = run_replay(pack_path=path, write_results=False)

    assert out["case_count"] == 1
    assert out["aggregate"]["routed_pass_count"] == 1
    assert out["aggregate"]["trace_pass_count"] == 1
    assert out["aggregate"]["combined_pass_count"] == 1
    assert out["rows"][0]["combined_passed"] is True
    assert out["rows"][0]["trace"]["trace_schema"] == "aether.local_router.trace.v0"
    assert out["rows"][0]["trace_judgment"]["passed"] is True


def test_perturbed_pack_preserves_evidence_requirements():
    source = {
        "pack": "source_pack",
        "cases": [{
            "id": "case_001",
            "source": {"title": "One", "file": "x", "conversation_id": "c1"},
            "task_type": "personal_synthesis",
            "prompt": "What pattern do you see in the Road America and marigold work?",
            "expected_receipts": ["Road America", "marigold"],
            "required_concepts": ["pattern", "limits"],
            "forbidden_claims": ["proof"],
        }],
    }

    out = build_perturbed_pack(source)

    assert out["pack"] == "local_router_replay_perturbed_v2"
    assert out["case_count"] == 1
    case = out["cases"][0]
    assert case["id"] == "case_001_perturb_01"
    assert "concrete receipts" in case["prompt"]
    assert case["expected_receipts"] == ["Road America", "marigold"]
    assert case["required_concepts"] == ["pattern", "limits"]
    assert case["perturbation"]["source_case_id"] == "case_001"


def test_ablation_runner_compares_modes_with_fake_ollama(tmp_path, monkeypatch):
    pack = {
        "pack": "test_pack",
        "cases": [{
            "id": "case_001",
            "source": {"title": "One", "file": "x", "conversation_id": "c1"},
            "task_type": "grant_business",
            "prompt": "Frame local CRT/Aether as a measurable low-cost business direction.",
            "expected_receipts": ["local", "CRT", "Aether"],
            "required_concepts": ["measurable", "low-cost", "business", "verifier"],
            "forbidden_claims": ["guaranteed", "frontier"],
        }],
    }
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(pack), encoding="utf-8")

    def fake_call_ollama(prompt: str, model: str, timeout: int) -> str:
        if "Retrieved memories:" in prompt:
            return "This is probably a great business."
        return (
            "Receipts: local CRT and Aether. Pattern: measurable low-cost business support. "
            "Limits: this is not guaranteed and not frontier capability. "
            "Next Useful Move: use a verifier to compare raw and scaffolded outputs."
        )

    monkeypatch.setattr("labs.meaning_compression_lab.local_router_ablation.call_ollama", fake_call_ollama)
    out = run_ablation(pack_path=path, modes=("raw_no_scaffold", "routed_no_repair", "full"), write_results=False)

    assert out["case_count"] == 1
    assert out["aggregate"]["raw_no_scaffold"]["answer_pass_count"] == 0
    assert out["aggregate"]["routed_no_repair"]["answer_pass_count"] == 1
    assert out["aggregate"]["full"]["answer_pass_count"] == 1
    assert out["aggregate"]["full"]["trace_pass_count"] == 1


def test_run_replay_can_skip_cases_for_scheduled_slices(tmp_path, monkeypatch):
    pack = {
        "pack": "test_pack",
        "cases": [
            {
                "id": "case_001",
                "source": {"title": "One", "file": "x", "conversation_id": "c1"},
                "task_type": "grant_business",
                "prompt": "Frame local CRT/Aether as a measurable low-cost business direction.",
                "expected_receipts": ["local", "CRT", "Aether"],
                "required_concepts": ["measurable", "low-cost", "business", "verifier"],
            },
            {
                "id": "case_002",
                "source": {"title": "Two", "file": "x", "conversation_id": "c2"},
                "task_type": "grant_business",
                "prompt": "Frame local CRT/Aether as a measurable low-cost business direction again.",
                "expected_receipts": ["local", "CRT", "Aether"],
                "required_concepts": ["measurable", "low-cost", "business", "verifier"],
            },
        ],
    }
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(pack), encoding="utf-8")

    def fake_call_ollama(prompt: str, model: str, timeout: int) -> str:
        return (
            "Receipts: local CRT and Aether. Pattern: measurable low-cost business support. "
            "Limits: this is not guaranteed and not frontier capability. "
            "Next Useful Move: use a verifier to compare raw and scaffolded responses."
        )

    monkeypatch.setattr("labs.meaning_compression_lab.local_router_replay.call_ollama", fake_call_ollama)

    out = run_replay(pack_path=path, skip_cases=1, max_cases=1, write_results=False)

    assert out["skip_cases"] == 1
    assert out["case_count"] == 1
    assert out["rows"][0]["id"] == "case_002"


def test_run_replay_can_filter_by_case_id(tmp_path, monkeypatch):
    pack = {
        "pack": "test_pack",
        "cases": [
            {
                "id": "case_001",
                "source": {"title": "One", "file": "x", "conversation_id": "c1"},
                "task_type": "grant_business",
                "prompt": "Frame local CRT/Aether as a measurable low-cost business direction.",
                "expected_receipts": ["local", "CRT", "Aether"],
                "required_concepts": ["measurable", "low-cost", "business", "verifier"],
            },
            {
                "id": "case_002",
                "source": {"title": "Two", "file": "x", "conversation_id": "c2"},
                "task_type": "business_planning",
                "prompt": "Could camera gear become a small business if I applied myself?",
                "expected_receipts": ["camera gear", "applied myself", "small business"],
                "required_concepts": ["offer", "pricing", "risk", "next useful move"],
            },
        ],
    }
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(pack), encoding="utf-8")

    def fake_call_ollama(prompt: str, model: str, timeout: int) -> str:
        return (
            "Receipts: camera gear, applied myself, and small business. Pattern: start with an offer. "
            "Limits: pricing and risk should be tested; this is not guaranteed full-time income. "
            "Next Useful Move: sell one small paid package before expanding."
        )

    monkeypatch.setattr("labs.meaning_compression_lab.local_router_replay.call_ollama", fake_call_ollama)

    out = run_replay(pack_path=path, case_ids=("case_002",), write_results=False)

    assert out["case_ids"] == ["case_002"]
    assert out["case_count"] == 1
    assert out["rows"][0]["id"] == "case_002"
    assert out["rows"][0]["task_type"] == "business_planning"


def test_aggregate_combined_gate_requires_answer_and_trace_pass():
    rows = [
        {
            "raw_judgment": {"passed": False, "score": 0.2},
            "routed_judgment": {"passed": True, "score": 0.9, "forbidden_hits": [], "weirdness_hits": [], "leakage_hits": []},
            "trace_judgment": {"passed": False, "score": 0.6, "missing_fields": ["turn_id"]},
            "combined_passed": False,
            "task_type": "grant_business",
            "delta": 0.7,
            "repaired": False,
            "fallback_used": False,
        }
    ]

    aggregate = _aggregate(rows)

    assert aggregate["routed_pass_count"] == 1
    assert aggregate["trace_pass_count"] == 0
    assert aggregate["combined_pass_count"] == 0
    assert aggregate["graduation_ready"] is False
    assert aggregate["failure_taxonomy"]["trace_failure_count"] == 1
    assert aggregate["failure_taxonomy"]["trace_missing_fields"] == {"turn_id": 1}


def test_failure_taxonomy_counts_answer_flags():
    taxonomy = _failure_taxonomy(
        [
            {
                "task_type": "grant_business",
                "combined_passed": False,
                "routed_judgment": {
                    "passed": False,
                    "truncated": True,
                    "forbidden_hits": ["guaranteed"],
                    "weirdness_hits": ["unsupported_numeric_claim"],
                    "leakage_hits": [],
                },
                "trace_judgment": {"passed": True, "missing_fields": []},
            }
        ]
    )

    assert taxonomy["total_failed"] == 1
    assert taxonomy["by_task_type"] == {"grant_business": 1}
    assert taxonomy["answer_failure_count"] == 1
    assert taxonomy["trace_failure_count"] == 0
    assert taxonomy["truncated_count"] == 1
    assert taxonomy["forbidden_hits"] == {"guaranteed": 1}
    assert taxonomy["weirdness_hits"] == {"unsupported_numeric_claim": 1}

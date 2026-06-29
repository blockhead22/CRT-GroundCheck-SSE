import json

from labs.meaning_compression_lab.local_router_replay import run_replay
from labs.meaning_compression_lab.replay_pack_builder import (
    classify_prompt_for_pack,
    sanitize_text,
    _looks_like_assistant_quote,
    _looks_like_dump,
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


def test_replay_pack_rejects_pasted_artifacts():
    assert _looks_like_dump('"Core Update Queue (Priority) File Purpose Reason for Update"')
    assert _looks_like_dump('"def rebuild_semantic_index(self): pass"')
    assert _looks_like_assistant_quote('"If you recognize your failure, how will you prevent fallback?"')


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
    assert out["rows"][0]["trace"]["trace_schema"] == "aether.local_router.trace.v0"
    assert out["rows"][0]["trace_judgment"]["passed"] is True

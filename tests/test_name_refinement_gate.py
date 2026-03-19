from pathlib import Path

from personal_agent.crt_rag import CRTEnhancedRAG


class _FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        return "OK"


def _build_rag(tmp_path: Path) -> CRTEnhancedRAG:
    return CRTEnhancedRAG(
        memory_db=str(tmp_path / "mem.db"),
        ledger_db=str(tmp_path / "ledger.db"),
        profile_db=str(tmp_path / "profile.db"),
        llm_client=_FakeLLM(),
    )


def test_name_refinement_assertion_does_not_trigger_contradiction_gate(tmp_path: Path):
    rag = _build_rag(tmp_path)

    rag.query("My name is Nick Block.")
    result = rag.query("You are Aether. I am Nick.")

    assert result.get("gate_reason") != "contradiction_disclosure"
    assert result.get("contradiction_detected") is not True
    assert len(rag.ledger.get_open_contradictions(limit=20)) == 0

from __future__ import annotations

from pathlib import Path

import pytest

from personal_agent.crt_rag import CRTEnhancedRAG


class FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        return "Here are the highlights."


@pytest.fixture()
def rag(tmp_path: Path) -> CRTEnhancedRAG:
    mem_db = tmp_path / "mem.db"
    led_db = tmp_path / "ledger.db"
    profile_db = tmp_path / "profile.db"
    return CRTEnhancedRAG(
        memory_db=str(mem_db),
        ledger_db=str(led_db),
        profile_db=str(profile_db),
        llm_client=FakeLLM(),
    )


def test_realtime_query_without_citations_returns_web_fetch_failed(
    rag: CRTEnhancedRAG,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(rag, "_run_web_search", lambda query: [])

    out = rag.query("latest news about the 2026 state of the union")

    assert out.get("gate_reason") == "web_fetch_failed"
    assert "Web fetch failed" in (out.get("answer") or "")
    packet = out.get("web_evidence_packet") or {}
    assert packet.get("citations") in ([], None)


def test_realtime_query_enforces_sources_and_evidence_packet(
    rag: CRTEnhancedRAG,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        rag,
        "_run_web_search",
        lambda query: [
            {
                "title": "Example Source One",
                "url": "https://example.com/source-1",
                "snippet": "Primary summary claim from source one.",
            },
            {
                "title": "Example Source Two",
                "url": "https://example.com/source-2",
                "snippet": "Secondary supporting detail from source two.",
            },
        ],
    )

    out = rag.query("search the web for 2026 state of the union highlights")
    ans = out.get("answer") or ""

    assert out.get("gate_reason") != "web_fetch_failed"
    assert "Sources:" in ans
    assert "[1]" in ans
    assert "https://example.com/source-1" in ans
    packet = out.get("web_evidence_packet") or {}
    assert len(packet.get("citations") or []) >= 2


def test_extract_search_query_strips_duckduckgo_instruction_suffix(rag: CRTEnhancedRAG):
    q = "can you check if dji mic 2 transmitter uses 3.5mm lav input using duckduckgo"
    extracted = rag._extract_search_query(q)
    lowered = extracted.lower()
    assert "using duckduckgo" not in lowered
    assert "duck duck go" not in lowered
    assert "dji mic 2 transmitter uses 3.5mm lav input" in lowered


def test_extract_search_query_strips_using_web_research_preamble(rag: CRTEnhancedRAG):
    q = "using web, and duckduckgo, can you research if the DJI Mic 2 can use a 3.5 mm jack for a lav microphone"
    extracted = rag._extract_search_query(q)
    lowered = extracted.lower()
    assert "using web" not in lowered
    assert "duckduckgo" not in lowered
    assert "can you research if" not in lowered
    assert "dji mic 2" in lowered
    assert "3.5 mm jack for a lav microphone" in lowered


def test_web_capability_query_uses_deterministic_fulfillment_answer(
    rag: CRTEnhancedRAG,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        rag,
        "_run_web_search",
        lambda query: [
            {
                "title": "DJI Mic 2 transmitter connector details",
                "url": "https://example.com/dji-mic-2-connectors",
                "snippet": "The DJI Mic 2 transmitter includes a 3.5mm input for external lavalier microphones.",
            },
            {
                "title": "DJI Mic 2 quick start",
                "url": "https://example.com/dji-mic-2-quickstart",
                "snippet": "Use the transmitter 3.5 mm jack to connect a lav mic.",
            },
        ],
    )

    out = rag.query(
        "using web, and duckduckgo, can you research if the 'DJI Mic 2' can use a 3.5 mm jack for a lav microphone"
    )
    ans = out.get("answer") or ""
    lowered = ans.lower()

    assert lowered.startswith("yes.")
    assert "according to my memory" not in lowered
    assert "from your memory" not in lowered
    assert "- [1]" in ans or "- [2]" in ans
    assert "Sources:" in ans
    assert "https://example.com/dji-mic-2-connectors" in ans

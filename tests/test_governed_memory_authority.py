from __future__ import annotations

from pathlib import Path

from personal_agent.crt_core import MemorySource
from personal_agent.crt_rag import CRTEnhancedRAG


class _FakeLLM:
    _SKIP_PREFIXES = ("You", "Do ", "Answer", "Search", "Top match", "Retrieved")

    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        if "[RESOLVED FACT DATA]" in prompt:
            block = prompt.split("[RESOLVED FACT DATA]", 1)[1]
            for end in ("[", "===", "User:"):
                if end in block:
                    block = block[:block.index(end)]
            past_header = False
            for line in block.splitlines():
                text = line.strip()
                if "found:" in text.lower():
                    past_header = True
                    continue
                if past_header and text and not any(text.startswith(prefix) for prefix in self._SKIP_PREFIXES):
                    return text
        return "OK"


def _make_rag(tmp_path: Path, llm_client=None) -> CRTEnhancedRAG:
    return CRTEnhancedRAG(
        memory_db=str(tmp_path / "mem.db"),
        ledger_db=str(tmp_path / "ledger.db"),
        llm_client=llm_client,
    )


def test_provisional_social_contradiction_does_not_demote_confirmed(tmp_path: Path) -> None:
    rag = _make_rag(tmp_path)

    confirmed = rag.memory.store_memory(
        text="My favorite color is orange.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion"},
        channel="webchat",
        kind="user_fact",
    )
    trust_before = confirmed.trust

    provisional = rag.memory.store_memory(
        text="Actually, my favorite color is blue.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion", "origin": "https://moltbook.example/posts/42"},
        channel="moltbook",
        kind="user_fact",
    )

    rag.ledger.record_contradiction(
        old_memory_id=confirmed.memory_id,
        new_memory_id=provisional.memory_id,
        drift_mean=0.9,
        confidence_delta=0.0,
        query="favorite color contradiction",
        old_text=confirmed.text,
        new_text=provisional.text,
        old_vector=confirmed.vector,
        new_vector=provisional.vector,
    )

    refreshed = rag.memory.get_memory_by_id(confirmed.memory_id)
    assert refreshed is not None
    assert refreshed.trust == trust_before
    assert provisional.authority == "provisional"
    assert provisional.kind == "observation"
    assert provisional.origin == "https://moltbook.example/posts/42"
    assert len(rag.memory.get_trust_history(confirmed.memory_id)) == 0
    assert len(rag.ledger.get_open_contradictions(limit=10)) == 1


def test_user_fact_answering_ignores_provisional_social_claims(tmp_path: Path) -> None:
    rag = _make_rag(tmp_path, llm_client=_FakeLLM())

    confirmed = rag.memory.store_memory(
        text="My favorite color is orange.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion"},
        channel="webchat",
        kind="user_fact",
    )
    provisional = rag.memory.store_memory(
        text="My favorite color is blue.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion", "origin": "moltbook:comment:99"},
        channel="moltbook",
        kind="user_fact",
    )

    rag.ledger.record_contradiction(
        old_memory_id=confirmed.memory_id,
        new_memory_id=provisional.memory_id,
        drift_mean=0.9,
        confidence_delta=0.0,
        query="favorite color contradiction",
        old_text=confirmed.text,
        new_text=provisional.text,
        old_vector=confirmed.vector,
        new_vector=provisional.vector,
    )

    out = rag.query("What's my favorite color?")
    answer = str(out.get("answer") or "")
    assert "orange" in answer.lower()
    assert "blue" not in answer.lower()
    assert out.get("gate_reason") != "unresolved_contradictions"


def test_promote_memory_updates_authority_and_logs_event(tmp_path: Path) -> None:
    rag = _make_rag(tmp_path)

    confirmed = rag.memory.store_memory(
        text="My favorite color is orange.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion"},
        channel="webchat",
        kind="user_fact",
    )
    provisional = rag.memory.store_memory(
        text="My favorite color is blue.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion", "origin": "moltbook:comment:100"},
        channel="moltbook",
        kind="user_fact",
    )

    rag.ledger.record_contradiction(
        old_memory_id=confirmed.memory_id,
        new_memory_id=provisional.memory_id,
        drift_mean=0.9,
        confidence_delta=0.0,
        query="favorite color contradiction",
        old_text=confirmed.text,
        new_text=provisional.text,
        old_vector=confirmed.vector,
        new_vector=provisional.vector,
    )

    promoted = rag.memory.promote_memory(
        provisional.memory_id,
        "confirmed",
        promoted_by="user",
        reason="Nick confirmed this favorite color directly",
    )

    assert promoted.authority == "confirmed"
    events = rag.memory.get_memory_events(provisional.memory_id, event_type="authority_promotion")
    assert len(events) == 1
    assert events[0]["old_authority"] == "provisional"
    assert events[0]["new_authority"] == "confirmed"
    assert events[0]["actor"] == "user"

    answer = rag._answer_from_fact_slots(
        ["favorite_color"],
        user_query="What's my favorite color?",
    )
    assert answer is not None
    assert "orange" in answer.lower()
    assert "blue" not in answer.lower()
    assert len(rag.ledger.get_open_contradictions(limit=10)) == 1


def test_system_generated_memory_defaults_to_provisional_system_metadata(tmp_path: Path) -> None:
    rag = _make_rag(tmp_path)

    mem = rag.memory.store_memory(
        text="I may have been inconsistent about that answer.",
        confidence=0.7,
        source=MemorySource.SYSTEM,
        context={"type": "belief", "kind": "self_narration"},
        thread_id="default",
    )

    assert mem.authority == "provisional"
    assert mem.channel == "system"
    assert mem.kind == "observation"
    assert mem.origin == "system:self_narration"


def test_confirmed_observation_cannot_answer_user_fact_slots(tmp_path: Path) -> None:
    rag = _make_rag(tmp_path, llm_client=_FakeLLM())

    observation = rag.memory.store_memory(
        text="My favorite color is blue.",
        confidence=0.95,
        source=MemorySource.SYSTEM,
        context={"type": "belief", "kind": "self_narration"},
        thread_id="default",
        authority="confirmed",
        channel="system",
        kind="observation",
    )
    user_fact = rag.memory.store_memory(
        text="My favorite color is orange.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion"},
        thread_id="default",
        channel="webchat",
        kind="user_fact",
    )

    out = rag.query("What's my favorite color?", thread_id="default")
    answer = str(out.get("answer") or "")
    assert "orange" in answer.lower()
    assert "blue" not in answer.lower()
    assert rag.memory.can_answer_user_fact(observation) is False
    assert rag.memory.can_answer_user_fact(user_fact) is True


def test_slot_query_does_not_answer_from_confirmed_observation_alone(tmp_path: Path) -> None:
    rag = _make_rag(tmp_path, llm_client=_FakeLLM())

    observation = rag.memory.store_memory(
        text="My favorite color is blue.",
        confidence=0.95,
        source=MemorySource.SYSTEM,
        context={"type": "belief", "kind": "self_narration"},
        thread_id="default",
        authority="confirmed",
        channel="system",
        kind="observation",
    )

    out = rag.query("What's my favorite color?", thread_id="default")
    answer = str(out.get("answer") or "")
    assert "blue" not in answer.lower()
    assert rag.memory.can_answer_user_fact(observation) is False

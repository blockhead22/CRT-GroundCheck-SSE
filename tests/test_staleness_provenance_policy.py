"""
Tests for staleness/review_after, model provenance, quiet ops promotion,
and narrative_note policies.

Coverage:
  A) Stale confirmed does not win slot selection when fresher confirmed exists.
  A) valid_until-expired memory is preserved but not used as source-of-truth.
  B) model_output writes persist with model_id/run_id and stay provisional.
  B) Conflicting model slot writes produce a disagreement event and do not
     override confirmed user_facts.
  C) model_output cannot promote user_fact/preference/permission without principal.
  C) model_output can promote ops with try_quiet_promote_ops and logs the event.
  D) narrative_note never answers a user_fact slot.
  D) narrative_note does not trigger contradiction decay against confirmed items.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import pytest

from personal_agent.crt_core import MemorySource
from personal_agent.crt_memory import CRTMemorySystem
from personal_agent.crt_rag import CRTEnhancedRAG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_memory(tmp_path: Path) -> CRTMemorySystem:
    return CRTMemorySystem(db_path=str(tmp_path / "mem.db"))


def _make_rag(tmp_path: Path) -> CRTEnhancedRAG:
    return CRTEnhancedRAG(
        memory_db=str(tmp_path / "mem.db"),
        ledger_db=str(tmp_path / "ledger.db"),
        llm_client=None,
    )


# ===========================================================================
# A) Staleness (review_after)
# ===========================================================================

class TestStaleness:
    def test_review_after_set_for_preference_kind(self, tmp_path: Path) -> None:
        """Preference memories get a non-None review_after."""
        mem_sys = _make_memory(tmp_path)
        m = mem_sys.store_memory(
            text="I prefer dark mode.",
            confidence=0.9,
            source=MemorySource.USER,
            kind="preference",
            channel="webchat",
        )
        assert m.review_after is not None
        assert m.review_after > time.time()

    def test_user_fact_has_no_review_after(self, tmp_path: Path) -> None:
        """user_fact and identity_constant never get a review_after."""
        mem_sys = _make_memory(tmp_path)
        for kind in ("user_fact", "identity_constant"):
            m = mem_sys.store_memory(
                text=f"My name is Nick. ({kind})",
                confidence=0.95,
                source=MemorySource.USER,
                kind=kind,
                channel="webchat",
            )
            assert m.review_after is None, f"Expected no review_after for kind={kind}"

    def test_is_stale_returns_false_when_review_after_is_future(self, tmp_path: Path) -> None:
        mem_sys = _make_memory(tmp_path)
        m = mem_sys.store_memory(
            text="I prefer vim.",
            confidence=0.9,
            source=MemorySource.USER,
            kind="preference",
            channel="webchat",
        )
        assert not m.is_stale()

    def test_is_stale_returns_true_when_review_after_is_past(self, tmp_path: Path) -> None:
        mem_sys = _make_memory(tmp_path)
        m = mem_sys.store_memory(
            text="I prefer emacs.",
            confidence=0.9,
            source=MemorySource.USER,
            kind="preference",
            channel="webchat",
        )
        # Simulate past review_after by checking with future 'now'
        far_future = time.time() + 1_000_000_000
        assert m.is_stale(now=far_future)

    def test_stale_confirmed_loses_slot_to_fresh_confirmed(self, tmp_path: Path) -> None:
        """
        A stale confirmed memory should not win slot selection when a fresh
        confirmed memory for the same slot exists.
        """
        rag = _make_rag(tmp_path)

        # Store the "stale" memory first — simulate it has a past review_after
        stale = rag.memory.store_memory(
            text="My name is StaleNick.",
            confidence=0.95,
            source=MemorySource.USER,
            kind="user_fact",
            channel="webchat",
            authority="confirmed",
        )
        # Manually backdate review_after to the past so it's stale
        import sqlite3
        conn = sqlite3.connect(str(tmp_path / "mem.db"))
        conn.execute(
            "UPDATE memories SET review_after = ? WHERE memory_id = ?",
            (time.time() - 1, stale.memory_id),
        )
        conn.commit()
        conn.close()

        # Store the fresh confirmed memory
        fresh = rag.memory.store_memory(
            text="My name is FreshNick.",
            confidence=0.95,
            source=MemorySource.USER,
            kind="user_fact",
            channel="webchat",
            authority="confirmed",
        )

        # Augment retrieval for "name" slot
        from personal_agent.crt_core import SSEMode
        import numpy as np

        filler_vec = np.zeros(384)
        from personal_agent.crt_core import MemorySource as MS
        from personal_agent.crt_memory import MemoryItem
        filler = MemoryItem(
            memory_id="filler",
            vector=filler_vec,
            text="Something unrelated.",
            timestamp=time.time(),
            confidence=0.5,
            trust=0.5,
            source=MS.USER,
            sse_mode=SSEMode.LOSSLESS,
        )
        augmented = rag._augment_retrieval_with_slot_memories(
            [(filler, 0.3)], ["name"], thread_id=None
        )
        injected = [m for m, _ in augmented if m.memory_id not in {"filler"}]

        # FreshNick should win over StaleNick
        injected_texts = [m.text for m in injected]
        assert any("FreshNick" in t for t in injected_texts), (
            f"Expected FreshNick in injected slot memories, got: {injected_texts}"
        )
        # StaleNick should NOT appear if FreshNick was injected for same slot
        # (at minimum, FreshNick should come first or replace StaleNick)
        if injected_texts:
            assert "FreshNick" in injected_texts[0] or all(
                "StaleNick" not in t for t in injected_texts
            ), f"StaleNick should not win over FreshNick: {injected_texts}"


# ===========================================================================
# B) Model Provenance + Disagreement
# ===========================================================================

class TestModelProvenance:
    def test_model_output_source_kind_stored(self, tmp_path: Path) -> None:
        """model_output source_kind is stored and returned."""
        mem_sys = _make_memory(tmp_path)
        m = mem_sys.store_memory(
            text="Tool returned: retry count = 3.",
            confidence=0.8,
            source=MemorySource.LLM_OUTPUT,
            kind="ops",
            source_kind="model_output",
            model_id="claude-sonnet-4-6",
            run_id="run-abc123",
        )
        assert m.source_kind == "model_output"
        assert m.model_id == "claude-sonnet-4-6"
        assert m.run_id == "run-abc123"

    def test_model_output_defaults_to_provisional(self, tmp_path: Path) -> None:
        """Any memory with source_kind=model_output is provisional by default."""
        mem_sys = _make_memory(tmp_path)
        m = mem_sys.store_memory(
            text="Retry heuristic: use 3 retries for API calls.",
            confidence=0.8,
            source=MemorySource.LLM_OUTPUT,
            kind="ops",
            source_kind="model_output",
            model_id="some-model",
        )
        assert m.authority == "provisional", (
            f"model_output should be provisional, got {m.authority!r}"
        )

    def test_model_output_conflict_with_confirmed_user_fact_logs_disagreement(
        self, tmp_path: Path
    ) -> None:
        """
        When a model_output memory contains a slot value that conflicts with
        a confirmed user_fact, a model_disagreement_detected event is logged.
        The confirmed user_fact is NOT overridden.
        """
        mem_sys = _make_memory(tmp_path)

        # Confirmed user fact: name = Nick
        confirmed = mem_sys.store_memory(
            text="My name is Nick.",
            confidence=0.95,
            source=MemorySource.USER,
            kind="user_fact",
            channel="webchat",
            authority="confirmed",
        )

        # Model output claims a different name (first-person phrasing so regex extracts it)
        model_mem = mem_sys.store_memory(
            text="My name is Bob.",
            confidence=0.8,
            source=MemorySource.LLM_OUTPUT,
            kind="user_fact",
            source_kind="model_output",
            model_id="test-model",
            run_id="run-001",
        )

        # Confirmed memory must still be confirmed
        reloaded_confirmed = mem_sys.get_memory_by_id(confirmed.memory_id)
        assert reloaded_confirmed is not None
        assert reloaded_confirmed.authority == "confirmed"

        # model_output must stay provisional
        reloaded_model = mem_sys.get_memory_by_id(model_mem.memory_id)
        assert reloaded_model is not None
        assert reloaded_model.authority == "provisional"

        # Disagreement event must be logged on model memory
        events = mem_sys.get_memory_events(model_mem.memory_id)
        event_types = {e["event_type"] for e in events}
        assert "model_disagreement_detected" in event_types, (
            f"Expected model_disagreement_detected event, got: {event_types}"
        )

    def test_model_output_with_no_conflict_has_no_disagreement_event(
        self, tmp_path: Path
    ) -> None:
        """No disagreement event when model_output matches confirmed user_fact."""
        mem_sys = _make_memory(tmp_path)

        mem_sys.store_memory(
            text="My name is Nick.",
            confidence=0.95,
            source=MemorySource.USER,
            kind="user_fact",
            channel="webchat",
            authority="confirmed",
        )

        model_mem = mem_sys.store_memory(
            text="Retry heuristic: use 3 retries.",
            confidence=0.8,
            source=MemorySource.LLM_OUTPUT,
            kind="ops",
            source_kind="model_output",
            model_id="test-model",
        )

        events = mem_sys.get_memory_events(model_mem.memory_id)
        event_types = {e["event_type"] for e in events}
        assert "model_disagreement_detected" not in event_types


# ===========================================================================
# C) Quiet ops promotion
# ===========================================================================

class TestQuietOpsPromotion:
    def test_ops_can_be_quietly_promoted_with_evidence(self, tmp_path: Path) -> None:
        """try_quiet_promote_ops promotes an ops memory and logs an event."""
        mem_sys = _make_memory(tmp_path)
        m = mem_sys.store_memory(
            text="API retry count: 3 attempts observed consistently.",
            confidence=0.8,
            source=MemorySource.LLM_OUTPUT,
            kind="ops",
            source_kind="model_output",
            model_id="claude-sonnet-4-6",
        )
        assert m.authority == "provisional"

        result = mem_sys.try_quiet_promote_ops(
            m.memory_id,
            reason="5 consecutive successful retries observed via tool receipt",
            evidence={"tool": "retry_counter", "count": 5},
            model_id="claude-sonnet-4-6",
            run_id="run-xyz",
        )
        assert result is True

        promoted = mem_sys.get_memory_by_id(m.memory_id)
        assert promoted is not None
        assert promoted.authority == "confirmed"

        events = mem_sys.get_memory_events(m.memory_id)
        promo_events = [e for e in events if e["event_type"] == "authority_promotion"]
        assert promo_events, "Expected an authority_promotion event"
        meta = promo_events[-1]
        assert meta.get("new_authority") == "confirmed"

    def test_quiet_promotion_requires_non_empty_reason(self, tmp_path: Path) -> None:
        """try_quiet_promote_ops blocks when reason is empty."""
        mem_sys = _make_memory(tmp_path)
        m = mem_sys.store_memory(
            text="Ops note: latency ~200ms.",
            confidence=0.7,
            source=MemorySource.LLM_OUTPUT,
            kind="ops",
            source_kind="model_output",
        )
        result = mem_sys.try_quiet_promote_ops(m.memory_id, reason="")
        assert result is False
        unchanged = mem_sys.get_memory_by_id(m.memory_id)
        assert unchanged.authority == "provisional"

    def test_model_output_cannot_quietly_promote_user_fact(self, tmp_path: Path) -> None:
        """try_quiet_promote_ops must not promote user_fact — ever."""
        mem_sys = _make_memory(tmp_path)
        m = mem_sys.store_memory(
            text="The user's name is Nick.",
            confidence=0.9,
            source=MemorySource.LLM_OUTPUT,
            kind="user_fact",
            source_kind="model_output",
        )
        result = mem_sys.try_quiet_promote_ops(
            m.memory_id,
            reason="very confident",
        )
        assert result is False
        unchanged = mem_sys.get_memory_by_id(m.memory_id)
        assert unchanged.authority == "provisional"

    def test_model_output_cannot_quietly_promote_preference(self, tmp_path: Path) -> None:
        """try_quiet_promote_ops must not promote preference."""
        mem_sys = _make_memory(tmp_path)
        m = mem_sys.store_memory(
            text="User prefers dark theme apparently.",
            confidence=0.8,
            source=MemorySource.LLM_OUTPUT,
            kind="preference",
            source_kind="model_output",
        )
        result = mem_sys.try_quiet_promote_ops(
            m.memory_id,
            reason="observed pattern",
        )
        assert result is False

    def test_model_output_cannot_quietly_promote_permission(self, tmp_path: Path) -> None:
        """try_quiet_promote_ops must not promote permission/policy kinds."""
        mem_sys = _make_memory(tmp_path)
        # 'permission' isn't an allowed kind — stored as 'observation'
        # Test with an observation to confirm quiet promo blocks non-ops kinds
        m = mem_sys.store_memory(
            text="The user has admin rights.",
            confidence=0.8,
            source=MemorySource.LLM_OUTPUT,
            kind="observation",
            source_kind="model_output",
        )
        result = mem_sys.try_quiet_promote_ops(
            m.memory_id,
            reason="observed pattern",
        )
        assert result is False


# ===========================================================================
# D) Narrative note
# ===========================================================================

class TestNarrativeNote:
    def test_narrative_note_is_always_provisional(self, tmp_path: Path) -> None:
        """narrative_note is forced to provisional regardless of channel or explicit authority."""
        mem_sys = _make_memory(tmp_path)
        m = mem_sys.store_memory(
            text="Reflecting: the user seems to prefer structured responses.",
            confidence=0.7,
            source=MemorySource.REFLECTION,
            kind="narrative_note",
            channel="system",
        )
        assert m.authority == "provisional", (
            f"narrative_note must be provisional, got {m.authority!r}"
        )

    def test_narrative_note_cannot_answer_user_fact_slot(self, tmp_path: Path) -> None:
        """narrative_note must never answer a user_fact slot."""
        mem_sys = _make_memory(tmp_path)
        m = mem_sys.store_memory(
            text="Narrative: the user mentioned their name is Nick.",
            confidence=0.9,
            source=MemorySource.REFLECTION,
            kind="narrative_note",
            channel="system",
        )
        assert not mem_sys.can_answer_user_fact(m), (
            "narrative_note should NOT be able to answer user_fact slots"
        )

    def test_narrative_note_does_not_trigger_contradiction_decay(
        self, tmp_path: Path
    ) -> None:
        """
        Storing a narrative_note must not decay the trust of existing confirmed
        user_facts, even if the text superficially matches correction phrases.
        """
        mem_sys = _make_memory(tmp_path)

        confirmed = mem_sys.store_memory(
            text="My name is Nick.",
            confidence=0.95,
            source=MemorySource.USER,
            kind="user_fact",
            channel="webchat",
            authority="confirmed",
        )
        original_trust = mem_sys.get_memory_by_id(confirmed.memory_id).trust

        # Store a narrative_note that sounds like a correction
        mem_sys.store_memory(
            text="Actually, I'm not certain — the user may be called Nick or Nicholas.",
            confidence=0.5,
            source=MemorySource.REFLECTION,
            kind="narrative_note",
            channel="system",
        )

        # Confirmed memory's trust must not have been reduced
        after = mem_sys.get_memory_by_id(confirmed.memory_id)
        assert after is not None
        assert after.trust >= original_trust, (
            f"narrative_note should not decay confirmed user_fact trust: "
            f"before={original_trust:.3f} after={after.trust:.3f}"
        )

    def test_narrative_note_excluded_from_slot_augmentation(
        self, tmp_path: Path
    ) -> None:
        """narrative_note must not be injected into slot augmentation."""
        rag = _make_rag(tmp_path)

        # Authoritative name fact
        rag.memory.store_memory(
            text="My name is Nick.",
            confidence=0.95,
            source=MemorySource.USER,
            kind="user_fact",
            channel="webchat",
            authority="confirmed",
        )

        # Narrative note with different name
        rag.memory.store_memory(
            text="Narrative: the user's name is probably Charlie.",
            confidence=0.7,
            source=MemorySource.REFLECTION,
            kind="narrative_note",
            channel="system",
        )

        from personal_agent.crt_core import SSEMode
        import numpy as np
        from personal_agent.crt_memory import MemoryItem

        filler = MemoryItem(
            memory_id="filler",
            vector=np.zeros(384),
            text="Unrelated.",
            timestamp=time.time(),
            confidence=0.5,
            trust=0.5,
            source=MemorySource.USER,
            sse_mode=SSEMode.LOSSLESS,
        )
        augmented = rag._augment_retrieval_with_slot_memories(
            [(filler, 0.3)], ["name"]
        )
        injected = [m for m, _ in augmented if m.memory_id != "filler"]
        injected_kinds = {getattr(m, "kind", "observation") for m in injected}
        assert "narrative_note" not in injected_kinds, (
            f"narrative_note should not appear in slot augmentation: {injected_kinds}"
        )
        # The confirmed user_fact (Nick) should still win
        injected_texts = [m.text for m in injected]
        assert any("Nick" in t for t in injected_texts), (
            f"Confirmed user_fact (Nick) should win slot. Got: {injected_texts}"
        )

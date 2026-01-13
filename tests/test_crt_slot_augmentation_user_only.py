from __future__ import annotations

import numpy as np

from personal_agent.crt_core import MemorySource, SSEMode
from personal_agent.crt_memory import MemoryItem
from personal_agent.crt_rag import CRTEnhancedRAG


def test_slot_augmentation_only_injects_user_sources(monkeypatch, tmp_path) -> None:
    engine = CRTEnhancedRAG(
        memory_db=str(tmp_path / "crt_memory_test.db"),
        ledger_db=str(tmp_path / "crt_ledger_test.db"),
    )

    user_name = MemoryItem(
        memory_id="u1",
        vector=np.zeros(3),
        text="My name is Nick.",
        timestamp=10.0,
        confidence=0.95,
        trust=0.8,
        source=MemorySource.USER,
        sse_mode=SSEMode.LOSSLESS,
        context=None,
        tags=None,
        thread_id=None,
    )

    system_name = MemoryItem(
        memory_id="s1",
        vector=np.zeros(3),
        text="FACT: name = Ben",
        timestamp=999.0,
        confidence=0.9,
        trust=0.9,
        source=MemorySource.SYSTEM,
        sse_mode=SSEMode.LOSSLESS,
        context=None,
        tags=None,
        thread_id=None,
    )

    filler = MemoryItem(
        memory_id="u2",
        vector=np.zeros(3),
        text="hello",
        timestamp=11.0,
        confidence=0.5,
        trust=0.5,
        source=MemorySource.USER,
        sse_mode=SSEMode.LOSSLESS,
        context=None,
        tags=None,
        thread_id=None,
    )

    monkeypatch.setattr(engine.memory, "_load_all_memories", lambda: [system_name, user_name, filler])

    retrieved = [(filler, 1.0)]
    augmented = engine._augment_retrieval_with_slot_memories(retrieved, ["name"])

    injected = [m for m, _ in augmented if m.memory_id != filler.memory_id]
    assert injected
    assert injected[0].source == MemorySource.USER
    assert "Nick" in injected[0].text

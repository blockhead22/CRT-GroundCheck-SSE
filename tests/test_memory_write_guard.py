from __future__ import annotations

import sqlite3
from pathlib import Path

from personal_agent.crt_core import MemorySource
from personal_agent.crt_memory import CRTMemorySystem
from personal_agent.crt_rag import CRTEnhancedRAG


def test_store_memory_strips_continuity_and_transcript_blocks(tmp_path: Path):
    mem_db = tmp_path / "mem.db"
    memory = CRTMemorySystem(db_path=str(mem_db))

    polluted = (
        "tell me a joke\n\n"
        "[CONTINUITY INSTRUCTION] Treat this as a follow-up.\n"
        "[RECENT CONVERSATION CONTEXT]\n"
        "User: My name is Nick\n"
        "Assistant: Sure."
    )

    item = memory.store_memory(
        text=polluted,
        confidence=0.9,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion"},
        thread_id="tg_guard",
    )

    assert "[CONTINUITY INSTRUCTION]" not in item.text
    assert "[RECENT CONVERSATION CONTEXT]" not in item.text
    assert "User:" not in item.text
    assert "Assistant:" not in item.text
    assert item.text == "tell me a joke"


def test_store_memory_strips_temporary_gpt_archive_context(tmp_path: Path):
    mem_db = tmp_path / "mem.db"
    memory = CRTMemorySystem(db_path=str(mem_db))

    polluted = (
        "Aether, what do you know about my health history?\n\n"
        "[Temporary GPT archive context - reference only, not settled memory]\n"
        "Temporary GPT archive references for this thread:\n"
        "- [user] 2025-03-24 | Notes: those three promises...\n"
    )

    item = memory.store_memory(
        text=polluted,
        confidence=0.9,
        source=MemorySource.USER,
        context={"type": "user_input", "kind": "assertion"},
        thread_id="tg_guard",
    )

    assert "[Temporary GPT archive context - reference only, not settled memory]" not in item.text
    assert "Temporary GPT archive references for this thread" not in item.text
    assert item.text == "Aether, what do you know about my health history?"


def test_rag_query_persists_thread_id_on_memory_rows(tmp_path: Path):
    mem_db = tmp_path / "mem.db"
    led_db = tmp_path / "ledger.db"
    rag = CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=None)

    rag.query("My name is Parity Nick.", thread_id="tg_123")

    conn = sqlite3.connect(str(mem_db))
    cur = conn.cursor()
    row = cur.execute(
        """
        SELECT thread_id, text
        FROM memories
        WHERE source = 'user'
        ORDER BY timestamp DESC
        LIMIT 1
        """
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "tg_123"
    assert "parity nick" in str(row[1]).lower()

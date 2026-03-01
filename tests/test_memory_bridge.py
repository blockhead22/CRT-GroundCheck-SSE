from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from personal_agent.memory_bridge import sync_groundcheck_to_memory


@dataclass
class _Mem:
    memory_id: str
    text: str
    context: Optional[Dict[str, Any]]


class _FakeMemorySystem:
    def __init__(self) -> None:
        self._items: List[_Mem] = []
        self.updated_trust: Dict[str, float] = {}
        self._counter = 0

    def _load_memories_filtered(self, source=None, thread_id=None, limit=None):  # noqa: ANN001
        return list(self._items)

    def store_memory(self, text: str, confidence: float, source, context=None, thread_id=None):  # noqa: ANN001
        self._counter += 1
        mem = _Mem(memory_id=f"m_{self._counter}", text=text, context=context)
        self._items.append(mem)
        return mem

    def _update_memory_trust(self, memory_id: str, new_trust: float) -> None:
        self.updated_trust[memory_id] = float(new_trust)


def _init_groundcheck_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE memories (
            id TEXT PRIMARY KEY,
            thread_id TEXT,
            text TEXT,
            trust REAL,
            source TEXT,
            timestamp REAL,
            namespace TEXT,
            created_at TEXT
        )
        """
    )
    now = time.time()
    rows = [
        ("g1", "default", "User's name is Nick", 0.95, "user", now - 10, "default", "2026-01-01 10:00:00"),
        ("g2", "default", "User's name is Nicholas", 0.70, "user", now - 5, "default", "2026-01-01 10:01:00"),
        ("g3", "default", "User's favorite color is orange", 0.90, "user", now - 4, "default", "2026-01-01 10:02:00"),
        ("g4", "default", "Nick is a freelancer in Wisconsin", 0.88, "user", now - 3, "default", "2026-01-01 10:03:00"),
        ("g5", "default", "Nick is a freelancer in Wisconsin", 0.87, "user", now - 2, "default", "2026-01-01 10:04:00"),
        ("g6", "default", "Telemetry from tool run", 0.92, "inferred", now - 1, "default", "2026-01-01 10:05:00"),
    ]
    cur.executemany(
        """
        INSERT INTO memories (id, thread_id, text, trust, source, timestamp, namespace, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def test_sync_groundcheck_imports_and_dedupes(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "groundcheck.db"
    _init_groundcheck_db(db_path)
    monkeypatch.setenv("GROUNDCHECK_DB", str(db_path))

    fake_mem = _FakeMemorySystem()
    # Pretend we already imported g1 so bridge should skip it.
    fake_mem._items.append(
        _Mem(
            memory_id="m_existing",
            text="User's name is Nick",
            context={"groundcheck": {"id": "g1"}},
        )
    )

    result = sync_groundcheck_to_memory(
        memory_system=fake_mem,
        thread_id="default",
        min_trust=0.65,
        raw_limit=100,
        narrative_limit=10,
        allowed_sources=["user", "inferred"],
    )

    assert result["ok"] is True
    assert result["imported"] >= 2
    imported_ids = {
        str((item.context or {}).get("groundcheck", {}).get("id"))
        for item in fake_mem._items
        if item.context
    }
    assert "g1" in imported_ids  # existing
    assert "g3" in imported_ids  # favorite color fact
    # Duplicate narrative (g4/g5) should import at most one due text dedupe.
    assert not ("g4" in imported_ids and "g5" in imported_ids)


def test_sync_groundcheck_respects_source_filter(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "groundcheck.db"
    _init_groundcheck_db(db_path)
    monkeypatch.setenv("GROUNDCHECK_DB", str(db_path))

    fake_mem = _FakeMemorySystem()
    result = sync_groundcheck_to_memory(
        memory_system=fake_mem,
        thread_id="default",
        min_trust=0.65,
        raw_limit=100,
        narrative_limit=10,
        allowed_sources=["user"],  # exclude inferred
    )
    assert result["ok"] is True
    imported_texts = [m.text for m in fake_mem._items]
    assert all("Telemetry from tool run" not in t for t in imported_texts)


def test_sync_groundcheck_includes_medium_long_narrative(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "groundcheck.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE memories (
            id TEXT PRIMARY KEY,
            thread_id TEXT,
            text TEXT,
            trust REAL,
            source TEXT,
            timestamp REAL,
            namespace TEXT,
            created_at TEXT
        )
        """
    )
    now = time.time()
    long_workplan = (
        "Current work plan for Aether: Items 3 (preference extraction from chat), "
        "4 (heartbeat news monitoring), 8 (personality state machine), "
        "9 (background reflection), 10 (DNNT retraining), "
        "11 (multi-model routing), 12 (email integration). "
        "These are the next system development priorities."
    )
    assert len(long_workplan) > 260  # regression guard for the original bug
    cur.execute(
        """
        INSERT INTO memories (id, thread_id, text, trust, source, timestamp, namespace, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("g_long", "copilot_session", long_workplan, 0.70, "user", now, "global", "2026-02-25 18:50:37"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("GROUNDCHECK_DB", str(db_path))
    fake_mem = _FakeMemorySystem()

    result = sync_groundcheck_to_memory(
        memory_system=fake_mem,
        thread_id="copilot_session",
        min_trust=0.2,
        raw_limit=100,
        narrative_limit=30,
        allowed_sources=["user", "inferred"],
    )

    assert result["ok"] is True
    assert result["imported"] >= 1
    imported_texts = [m.text for m in fake_mem._items]
    assert any("4 (heartbeat news monitoring)" in t for t in imported_texts)

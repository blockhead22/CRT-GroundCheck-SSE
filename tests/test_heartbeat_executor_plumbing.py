from __future__ import annotations

import sqlite3
from pathlib import Path

from personal_agent.db_utils import ThreadSessionDB
from personal_agent.heartbeat_executor import HeartbeatLLMExecutor


def _init_memory_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE memories (
            memory_id TEXT PRIMARY KEY,
            vector_json TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp REAL NOT NULL,
            confidence REAL NOT NULL,
            trust REAL NOT NULL,
            source TEXT NOT NULL,
            sse_mode TEXT NOT NULL,
            context_json TEXT,
            thread_id TEXT,
            deprecated INTEGER DEFAULT 0
        )
        """
    )
    rows = [
        ("m_t1_a", "[]", "My name is Nick.", 10.0, 0.95, 0.9, "user", "L", None, "t1", 0),
        ("m_t1_b", "[]", "I work at Datacore.", 11.0, 0.9, 0.85, "user", "L", None, "t1", 0),
        ("m_t2_a", "[]", "My name is Alice.", 12.0, 0.95, 0.9, "user", "L", None, "t2", 0),
        ("m_t2_b", "[]", "I work at Orbit.", 13.0, 0.9, 0.85, "user", "L", None, "t2", 0),
    ]
    cur.executemany(
        """
        INSERT INTO memories
        (memory_id, vector_json, text, timestamp, confidence, trust, source, sse_mode, context_json, thread_id, deprecated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def _init_ledger_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE contradictions (
            ledger_id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            old_memory_id TEXT NOT NULL,
            new_memory_id TEXT NOT NULL,
            drift_mean REAL NOT NULL,
            status TEXT NOT NULL,
            contradiction_type TEXT,
            summary TEXT
        )
        """
    )
    rows = [
        ("c_t1", 100.0, "m_t1_a", "m_t1_b", 0.5, "open", "conflict", "t1 conflict"),
        ("c_t2", 101.0, "m_t2_a", "m_t2_b", 0.6, "open", "conflict", "t2 conflict"),
    ]
    cur.executemany(
        """
        INSERT INTO contradictions
        (ledger_id, timestamp, old_memory_id, new_memory_id, drift_mean, status, contradiction_type, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def test_heartbeat_snapshot_and_contradictions_are_thread_scoped(tmp_path: Path):
    session_db = ThreadSessionDB(str(tmp_path / "sessions.db"))
    session_db.get_or_create_session("t1")
    session_db.get_or_create_session("t2")

    mem_db = tmp_path / "crt_memory_shared.db"
    led_db = tmp_path / "crt_ledger_shared.db"
    _init_memory_db(mem_db)
    _init_ledger_db(led_db)

    executor = HeartbeatLLMExecutor(
        session_db=session_db,
        memory_db_path=str(mem_db),
        ledger_db_path=str(led_db),
    )

    snap_t1 = executor._get_memory_snapshot("t1")
    snap_t2 = executor._get_memory_snapshot("t2")

    assert "nick" in str(snap_t1).lower()
    assert "alice" not in str(snap_t1).lower()
    assert "alice" in str(snap_t2).lower()
    assert "nick" not in str(snap_t2).lower()

    open_t1 = executor._get_open_contradictions("t1", limit=10)
    open_t2 = executor._get_open_contradictions("t2", limit=10)
    ids_t1 = {item["ledger_id"] for item in open_t1}
    ids_t2 = {item["ledger_id"] for item in open_t2}

    assert ids_t1 == {"c_t1"}
    assert ids_t2 == {"c_t2"}


def test_heartbeat_executor_infers_session_db_path(tmp_path: Path):
    session_db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    executor = HeartbeatLLMExecutor(session_db=session_db)
    assert executor.thread_session_db_path == str(tmp_path / "thread_sessions.db")

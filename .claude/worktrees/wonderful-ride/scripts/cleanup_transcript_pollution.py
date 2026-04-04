"""One-time cleanup for transcript-style memory pollution.

This script targets memories that accidentally stored chat transcript blocks
(`User:` / `Assistant:` / continuity helper blocks) as first-class facts.

Default behavior is dry-run. Use --apply to commit changes.
"""

from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path
from typing import List


TRANSCRIPT_PATTERNS = (
    "%[CONTINUITY INSTRUCTION]%",
    "%[RECENT CONVERSATION CONTEXT]%",
    "%\nUser:%",
    "%\nAssistant:%",
    "User:%",
    "Assistant:%",
    "%I don't have a reliable stored memory for your assistant_name yet%",
)


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _find_polluted_memories(conn: sqlite3.Connection, thread_id: str | None) -> List[sqlite3.Row]:
    filters = " OR ".join(["text LIKE ?" for _ in TRANSCRIPT_PATTERNS])
    params: List[object] = list(TRANSCRIPT_PATTERNS)
    query = (
        "SELECT memory_id, source, trust, thread_id, timestamp, substr(text, 1, 280) AS preview "
        "FROM memories "
        "WHERE COALESCE(deprecated, 0) = 0 AND (" + filters + ")"
    )
    if thread_id:
        query += " AND thread_id = ?"
        params.append(thread_id)
    query += " ORDER BY timestamp DESC"
    return conn.execute(query, params).fetchall()


def _find_linked_open_contradictions(
    ledger_conn: sqlite3.Connection,
    memory_ids: List[str],
) -> List[sqlite3.Row]:
    if not memory_ids:
        return []
    marks = ",".join("?" for _ in memory_ids)
    query = (
        "SELECT ledger_id, contradiction_type, status, old_memory_id, new_memory_id, summary "
        "FROM contradictions "
        f"WHERE status = 'open' AND (old_memory_id IN ({marks}) OR new_memory_id IN ({marks})) "
        "ORDER BY timestamp DESC"
    )
    return ledger_conn.execute(query, memory_ids + memory_ids).fetchall()


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean transcript-style polluted memories.")
    parser.add_argument(
        "--memory-db",
        default="personal_agent/crt_memory_shared.db",
        help="Path to memory database",
    )
    parser.add_argument(
        "--ledger-db",
        default="personal_agent/crt_ledger_shared.db",
        help="Path to contradiction ledger database",
    )
    parser.add_argument(
        "--thread-id",
        default=None,
        help="Optional thread_id filter (exact match)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry-run)",
    )
    args = parser.parse_args()

    memory_db = Path(args.memory_db)
    ledger_db = Path(args.ledger_db)

    if not memory_db.exists():
        print(f"[ERROR] Memory DB not found: {memory_db}")
        return 1

    mem_conn = _connect(memory_db)
    polluted_rows = _find_polluted_memories(mem_conn, args.thread_id)
    memory_ids = [str(r["memory_id"]) for r in polluted_rows]

    print(f"[INFO] memory_db={memory_db}")
    print(f"[INFO] thread_filter={args.thread_id or '(none)'}")
    print(f"[INFO] polluted_candidates={len(polluted_rows)}")
    for row in polluted_rows[:12]:
        print(
            f"  - {row['memory_id']} source={row['source']} trust={row['trust']:.3f} "
            f"thread={row['thread_id']!r} text={row['preview']}"
        )

    open_contradictions: List[sqlite3.Row] = []
    ledger_conn: sqlite3.Connection | None = None
    if ledger_db.exists():
        ledger_conn = _connect(ledger_db)
        open_contradictions = _find_linked_open_contradictions(ledger_conn, memory_ids)
        print(f"[INFO] linked_open_contradictions={len(open_contradictions)}")
        for row in open_contradictions[:12]:
            print(
                f"  - {row['ledger_id']} type={row['contradiction_type']} "
                f"old={row['old_memory_id']} new={row['new_memory_id']} summary={row['summary'] or ''}"
            )
    else:
        print(f"[WARN] Ledger DB not found: {ledger_db} (skipping contradiction resolution)")

    if not args.apply:
        print("[DRY-RUN] No changes applied. Re-run with --apply to commit.")
        mem_conn.close()
        if ledger_conn is not None:
            ledger_conn.close()
        return 0

    if memory_ids:
        reason = "transcript_pollution_cleanup_2026_02_26"
        marks = ",".join("?" for _ in memory_ids)
        mem_conn.execute(
            f"UPDATE memories SET deprecated = 1, deprecation_reason = ? WHERE memory_id IN ({marks})",
            [reason] + memory_ids,
        )
        mem_conn.commit()
    print(f"[APPLY] deprecated_memories={len(memory_ids)}")

    resolved = 0
    if ledger_conn is not None and open_contradictions:
        now_ts = time.time()
        for row in open_contradictions:
            ledger_conn.execute(
                "UPDATE contradictions "
                "SET status = 'resolved', resolution_timestamp = ?, resolution_method = ? "
                "WHERE ledger_id = ?",
                (now_ts, "transcript_pollution_cleanup", row["ledger_id"]),
            )
            resolved += 1
        ledger_conn.commit()
    print(f"[APPLY] resolved_open_contradictions={resolved}")

    mem_conn.close()
    if ledger_conn is not None:
        ledger_conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


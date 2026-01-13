"""Purge selected memory sources from a CRT thread memory DB.

Use this when earlier runs polluted the DB with assistant-generated (SYSTEM) or
non-durable (FALLBACK) entries and you want to keep only auditable user/external
memories.

Examples:
  # Dry-run: show how many rows would be deleted
  python purge_thread_memories.py --thread default --sources system,fallback --dry-run

  # Execute purge
  python purge_thread_memories.py --thread default --sources system,fallback --yes

Notes:
- This does NOT delete the ledger DB.
- This does NOT touch USER memories.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def _thread_memory_db_path(repo_root: Path, thread_id: str) -> Path:
    tid = (thread_id or "default").strip() or "default"
    # Keep in sync with crt_api.py naming.
    return repo_root / "personal_agent" / f"crt_memory_{tid}.db"


def purge_sources(db_path: Path, sources: list[str], *, dry_run: bool) -> tuple[int, int]:
    """Return (memories_deleted, trust_log_deleted)."""
    if not db_path.exists() or not db_path.is_file():
        raise FileNotFoundError(f"DB not found: {db_path}")

    norm_sources = [s.strip().lower() for s in (sources or []) if s and s.strip()]
    if not norm_sources:
        return (0, 0)

    placeholders = ",".join(["?"] * len(norm_sources))

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute(
        f"SELECT memory_id FROM memories WHERE lower(source) IN ({placeholders})",
        tuple(norm_sources),
    )
    ids = [str(r[0]) for r in cur.fetchall() if r and r[0]]

    # Count affected rows.
    trust_log_count = 0
    if ids:
        id_placeholders = ",".join(["?"] * len(ids))
        cur.execute(
            f"SELECT COUNT(1) FROM trust_log WHERE memory_id IN ({id_placeholders})",
            tuple(ids),
        )
        trust_log_count = int((cur.fetchone() or [0])[0] or 0)

    cur.execute(
        f"SELECT COUNT(1) FROM memories WHERE lower(source) IN ({placeholders})",
        tuple(norm_sources),
    )
    memories_count = int((cur.fetchone() or [0])[0] or 0)

    if dry_run:
        conn.close()
        return (memories_count, trust_log_count)

    # Delete trust_log first (best-effort hygiene).
    trust_log_deleted = 0
    if ids:
        id_placeholders = ",".join(["?"] * len(ids))
        cur.execute(
            f"DELETE FROM trust_log WHERE memory_id IN ({id_placeholders})",
            tuple(ids),
        )
        trust_log_deleted = int(cur.rowcount or 0)

    cur.execute(
        f"DELETE FROM memories WHERE lower(source) IN ({placeholders})",
        tuple(norm_sources),
    )
    memories_deleted = int(cur.rowcount or 0)

    conn.commit()
    conn.close()
    return (memories_deleted, trust_log_deleted)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--thread", default="default", help="thread id (matches crt_memory_<thread>.db)")
    parser.add_argument(
        "--sources",
        default="system,fallback",
        help="comma-separated sources to purge (e.g. system,fallback,reflection)",
    )
    parser.add_argument("--dry-run", action="store_true", help="do not delete; only report counts")
    parser.add_argument("--yes", action="store_true", help="required to actually delete (ignored for --dry-run)")

    args = parser.parse_args()

    sources = [s for s in (args.sources or "").split(",") if s.strip()]
    repo_root = Path(__file__).resolve().parent
    db_path = _thread_memory_db_path(repo_root, args.thread)

    if not args.dry_run and not args.yes:
        raise SystemExit("Refusing to delete without --yes (or use --dry-run).")

    mem_ct, trust_ct = purge_sources(db_path, sources, dry_run=bool(args.dry_run))

    mode = "DRY RUN" if args.dry_run else "DELETED"
    print(f"{mode}: {mem_ct} memories, {trust_ct} trust_log rows")
    print(f"DB: {db_path}")
    print(f"Sources: {', '.join(sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

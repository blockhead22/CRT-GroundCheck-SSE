"""One-time script to clean garbage from all memory databases."""
import sqlite3
import os
import sys

def clean_groundcheck_mcp():
    """Clean garbage from GroundCheck MCP database."""
    db = "D:/groundcheck/.groundcheck/memory.db"
    if not os.path.exists(db):
        print("[SKIP] GroundCheck MCP DB not found at", db)
        return

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT id, text, trust, namespace, thread_id FROM memories").fetchall()
    print("=== GroundCheck MCP DB (before cleanup) ===")
    for r in rows:
        print(f"  [{r['id']}] ns={r['namespace']} trust={r['trust']} text={r['text'][:90]}")
    print()

    # Delete garbage auto-extracted facts
    garbage_patterns = [
        "major is programming",
        "certification is no code",
        "experience years is planning",
        "team size is discussion",
        "framework is testing connectivity",
        "project is priority items",
    ]
    deleted = 0
    for pat in garbage_patterns:
        cur = conn.execute("DELETE FROM memories WHERE text LIKE ?", (f"%{pat}%",))
        deleted += cur.rowcount
    conn.commit()

    rows = conn.execute("SELECT id, text, trust, namespace FROM memories").fetchall()
    print(f"=== GroundCheck MCP DB (after cleanup, deleted {deleted}) ===")
    for r in rows:
        print(f"  [{r['id']}] ns={r['namespace']} trust={r['trust']} text={r['text'][:100]}")
    conn.close()
    print()


def clean_crt_facts():
    """Clean garbage from crt_facts.db."""
    db = "D:/AI_round2/personal_agent/crt_facts.db"
    if not os.path.exists(db):
        print("[SKIP] crt_facts.db not found at", db)
        return

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT rowid, slot, value, current, source FROM crt_facts ORDER BY slot, rowid").fetchall()
    print(f"=== crt_facts.db (before cleanup, {len(rows)} rows) ===")
    for r in rows:
        print(f"  [row {r['rowid']}] slot={r['slot']} value={r['value']} current={r['current']} source={r['source'][:50] if r['source'] else 'None'}")
    print()

    # 1. Delete rows where value is literally "None" or empty
    cur = conn.execute("DELETE FROM crt_facts WHERE value IS NULL OR value = '' OR value = 'None' OR value = 'none'")
    deleted_none = cur.rowcount
    print(f"  Deleted {deleted_none} rows with None/empty values")

    # 2. Delete non-current duplicates (keep only current=1 for each slot)
    cur = conn.execute("DELETE FROM crt_facts WHERE current = 0")
    deleted_old = cur.rowcount
    print(f"  Deleted {deleted_old} non-current (superseded) rows")

    # 3. For slots with multiple current=1 entries, keep only the newest (highest rowid)
    dupes = conn.execute("""
        SELECT slot, COUNT(*) as cnt FROM crt_facts
        WHERE current = 1
        GROUP BY slot HAVING cnt > 1
    """).fetchall()
    deleted_dup = 0
    for d in dupes:
        slot = d['slot']
        # Keep the row with the highest rowid
        cur = conn.execute("""
            DELETE FROM crt_facts WHERE slot = ? AND current = 1
            AND rowid NOT IN (SELECT MAX(rowid) FROM crt_facts WHERE slot = ? AND current = 1)
        """, (slot, slot))
        deleted_dup += cur.rowcount
        print(f"  Deduped slot '{slot}': kept newest, removed {cur.rowcount} old entries")

    conn.commit()

    rows = conn.execute("SELECT rowid, slot, value, current FROM crt_facts ORDER BY slot").fetchall()
    print(f"\n=== crt_facts.db (after cleanup, {len(rows)} rows remain) ===")
    for r in rows:
        print(f"  [row {r['rowid']}] slot={r['slot']} value={r['value']} current={r['current']}")
    conn.close()
    print()


def clean_crt_memory():
    """Deprecate raw user messages stored at high trust that aren't real facts."""
    db = "D:/AI_round2/personal_agent/crt_memory_tg_8793030650.db"
    if not os.path.exists(db):
        print("[SKIP] crt_memory not found at", db)
        return

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    # Find raw user messages that got stored at high trust but aren't factual
    # These are short conversational messages or noise
    noise_patterns = [
        # Very short non-factual messages
        "No there's no more I would like to talk about myself today",
        "Nick Block",  # Just a name without context
        "yes",
        "no",
        "ok",
        "hello",
        "hi",
        "hey",
        "thanks",
        "thank you",
    ]

    deprecated = 0
    for pat in noise_patterns:
        cur = conn.execute(
            "UPDATE memories SET deprecated = 1, deprecation_reason = 'noise_cleanup' "
            "WHERE text = ? AND deprecated = 0",
            (pat,)
        )
        deprecated += cur.rowcount

    # Also deprecate very short entries (< 10 chars) that are at trust >= 0.9
    cur = conn.execute(
        "UPDATE memories SET deprecated = 1, deprecation_reason = 'too_short_high_trust' "
        "WHERE LENGTH(text) < 10 AND trust >= 0.9 AND deprecated = 0 "
        "AND text NOT LIKE '%color%' AND text NOT LIKE '%name%'"
    )
    deprecated += cur.rowcount

    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM memories WHERE deprecated = 0").fetchone()[0]
    dep = conn.execute("SELECT COUNT(*) FROM memories WHERE deprecated = 1").fetchone()[0]
    print(f"=== CRT Memory tg_8793030650 ===")
    print(f"  Total: {total}, Active: {active}, Deprecated: {dep}")
    print(f"  Newly deprecated: {deprecated}")

    # Show top 10 active memories by trust
    rows = conn.execute(
        "SELECT text, trust FROM memories WHERE deprecated = 0 ORDER BY trust DESC LIMIT 10"
    ).fetchall()
    print(f"\n  Top 10 active memories:")
    for r in rows:
        print(f"    trust={r['trust']:.2f} | {r['text'][:80]}")
    conn.close()
    print()


if __name__ == "__main__":
    print("=" * 70)
    print("MEMORY GARBAGE CLEANUP")
    print("=" * 70)
    print()
    clean_groundcheck_mcp()
    clean_crt_facts()
    clean_crt_memory()
    print("=" * 70)
    print("DONE")
    print("=" * 70)

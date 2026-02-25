"""Clean crt_facts.db and crt_memory_tg_8793030650.db of garbage."""
import sqlite3
import os

def clean_crt_facts():
    db = "D:/AI_round2/personal_agent/crt_facts.db"
    conn = sqlite3.connect(db)

    # 1. Delete rows where value is literally "None" (string)
    cur = conn.execute("DELETE FROM facts WHERE value = 'None' OR value = 'none' OR value = ''")
    print(f"Deleted {cur.rowcount} rows with None/empty values")

    # 2. Delete all non-current rows (superseded history)
    cur = conn.execute("DELETE FROM facts WHERE is_current = 0")
    print(f"Deleted {cur.rowcount} superseded (non-current) rows")

    # 3. Deduplicate: for slots with multiple is_current=1, keep only newest
    dupes = conn.execute("""
        SELECT slot, COUNT(*) as cnt FROM facts
        WHERE is_current = 1
        GROUP BY slot HAVING cnt > 1
    """).fetchall()
    for slot, cnt in dupes:
        cur = conn.execute("""
            DELETE FROM facts WHERE slot = ? AND is_current = 1
            AND id NOT IN (SELECT MAX(id) FROM facts WHERE slot = ? AND is_current = 1)
        """, (slot, slot))
        print(f"  Deduped '{slot}': removed {cur.rowcount} old entries (kept newest)")

    conn.commit()

    # Show what remains
    rows = conn.execute("SELECT id, slot, value, trust, is_current FROM facts ORDER BY slot").fetchall()
    print(f"\n=== crt_facts.db after cleanup ({len(rows)} rows) ===")
    for r in rows:
        print(f"  id={r[0]} slot={r[1]} value={r[2]} trust={r[3]} current={r[4]}")
    conn.close()


def clean_crt_memory():
    db = "D:/AI_round2/personal_agent/crt_memory_tg_8793030650.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    # Deprecate noise: raw short messages stored at high trust
    noise_exact = [
        "No there's no more I would like to talk about myself today",
        "Nick Block",
        "yes", "no", "ok", "hello", "hi", "hey", "thanks", "thank you",
        "Yeah", "Yep", "Nope", "Sure", "Good", "Nice", "Cool",
    ]

    deprecated = 0
    for pat in noise_exact:
        cur = conn.execute(
            "UPDATE memories SET deprecated = 1, deprecation_reason = 'noise_cleanup' "
            "WHERE LOWER(text) = LOWER(?) AND deprecated = 0",
            (pat,)
        )
        deprecated += cur.rowcount

    # Also deprecate very short entries (< 12 chars) at high trust that aren't factual
    cur = conn.execute(
        "UPDATE memories SET deprecated = 1, deprecation_reason = 'too_short_noise' "
        "WHERE LENGTH(text) < 12 AND trust >= 0.8 AND deprecated = 0 "
        "AND text NOT LIKE '%color%' AND text NOT LIKE '%orange%'"
    )
    deprecated += cur.rowcount

    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM memories WHERE deprecated = 0").fetchone()[0]
    dep = conn.execute("SELECT COUNT(*) FROM memories WHERE deprecated = 1").fetchone()[0]
    print(f"\n=== CRT Memory tg_8793030650 ===")
    print(f"  Total: {total}, Active: {active}, Deprecated: {dep}")
    print(f"  Newly deprecated this run: {deprecated}")

    # Show top 15 active memories by trust
    rows = conn.execute(
        "SELECT text, trust, source FROM memories WHERE deprecated = 0 ORDER BY trust DESC LIMIT 15"
    ).fetchall()
    print(f"\n  Top 15 active memories:")
    for r in rows:
        print(f"    trust={r['trust']:.2f} src={r['source'] or '?'} | {r['text'][:90]}")
    conn.close()


if __name__ == "__main__":
    clean_crt_facts()
    clean_crt_memory()
    print("\nDone.")

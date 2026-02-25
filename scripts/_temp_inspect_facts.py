import sqlite3

# Check crt_facts schema
db = "D:/AI_round2/personal_agent/crt_facts.db"
conn = sqlite3.connect(db)
rows = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'").fetchall()
for name, sql in rows:
    print(f"Table: {name}")
    print(f"  {sql}")
    count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    print(f"  Rows: {count}")
    # Show columns
    cols = conn.execute(f"PRAGMA table_info({name})").fetchall()
    print(f"  Columns: {[c[1] for c in cols]}")
print()

# Dump all rows
rows = conn.execute("SELECT rowid, * FROM facts").fetchall()
print(f"=== All {len(rows)} rows ===")
for r in rows:
    print(f"  rowid={r[0]} | {list(r[1:])}")
conn.close()

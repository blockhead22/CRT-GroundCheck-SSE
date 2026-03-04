"""Inspect the GroundCheck memory.db for Nick contamination."""
import sqlite3

DB_PATH = "D:/groundcheck/.groundcheck/memory.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# List tables
tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])

for (tname,) in tables:
    cols = cur.execute(f"PRAGMA table_info({tname})").fetchall()
    col_names = [c[1] for c in cols]
    print(f"\n=== {tname} ({len(col_names)} cols: {col_names}) ===")
    count = cur.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
    print(f"  Total rows: {count}")
    
    # Search for Nick in text columns
    for col in col_names:
        try:
            nick_rows = cur.execute(
                f"SELECT * FROM {tname} WHERE CAST({col} AS TEXT) LIKE '%Nick%'", 
            ).fetchall()
            if nick_rows:
                print(f"  ** FOUND 'Nick' in column '{col}': {len(nick_rows)} rows **")
                for row in nick_rows[:10]:
                    print(f"    -> {row}")
        except Exception:
            pass

    # Also dump first 5 rows for context
    if count > 0 and count <= 50:
        rows = cur.execute(f"SELECT * FROM {tname}").fetchall()
        print(f"  All {count} rows:")
        for r in rows:
            print(f"    {r}")
    elif count > 0:
        rows = cur.execute(f"SELECT * FROM {tname} LIMIT 10").fetchall()
        print(f"  First 10 rows (of {count}):")
        for r in rows:
            print(f"    {r}")

conn.close()
print("\nDone.")

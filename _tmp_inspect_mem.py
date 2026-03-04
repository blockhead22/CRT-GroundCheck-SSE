import sqlite3
import json

# Inspect crt_memory.db
db = sqlite3.connect("personal_agent/crt_memory.db")
tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("=== crt_memory.db tables ===")
for t in tables:
    name = t[0]
    cnt = db.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
    print(f"  {name}: {cnt} rows")
    if cnt > 0:
        cols = [d[0] for d in db.execute(f"SELECT * FROM [{name}] LIMIT 1").description]
        print(f"    cols: {cols}")
        rows = db.execute(f"SELECT * FROM [{name}] ORDER BY rowid DESC LIMIT 5").fetchall()
        for r in rows:
            d = dict(zip(cols, r))
            text = str(d.get("text", d.get("content", d.get("value", d.get("claim", "")))))[:120]
            tid = d.get("thread_id", "")
            print(f"    [{tid}] {text}")
db.close()

print()

# Count contradictions
db2 = sqlite3.connect("personal_agent/crt_memory.db")
try:
    crows = db2.execute("SELECT COUNT(*) FROM contradictions").fetchone()[0]
    print(f"Contradictions: {crows}")
    if crows > 0:
        for r in db2.execute("SELECT * FROM contradictions ORDER BY rowid DESC LIMIT 10").fetchall():
            print(f"  {r}")
except:
    print("No contradictions table")
db2.close()

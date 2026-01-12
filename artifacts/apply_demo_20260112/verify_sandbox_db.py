import json
import sqlite3

DB = r"artifacts/apply_demo_20260112/crt_live_memory.sandbox.db"

con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute("SELECT text, context_json FROM memories ORDER BY timestamp DESC LIMIT 10")
rows = cur.fetchall()
con.close()

print(f"rows fetched: {len(rows)}")
for i, (text, ctx) in enumerate(rows[:5]):
    text = text or ""
    print(f"[{i}] TEXT: {text[:120]}")
    if ctx:
        try:
            j = json.loads(ctx)
            print(f"    HAS_PROMOTION_CTX: {'promotion' in j}")
        except Exception as e:
            print(f"    CTX_PARSE_FAIL: {e}")
    else:
        print("    CTX_NONE")

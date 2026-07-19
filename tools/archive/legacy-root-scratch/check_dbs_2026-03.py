import sqlite3

dbs_to_check = [
    ("data/crt_memory.db", "memories"),
    ("personal_agent/crt_user_profile.db", None),
    ("personal_agent/crt_thread_sessions.db", None),
    ("personal_agent/crt_memory_shared.db", "memories"),
    ("personal_agent/crt_ledger_shared.db", None),
    ("personal_agent/crt_episodic.db", None),
]

for db_path, tbl in dbs_to_check:
    try:
        db = sqlite3.connect(db_path)
        tables = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f"\n=== {db_path} ===")
        print(f"  tables: {tables}")
        for t in tables:
            cnt = db.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
            if cnt > 0:
                cols = [d[0] for d in db.execute(f"SELECT * FROM [{t}] LIMIT 1").description]
                print(f"  {t}: {cnt} rows  cols={cols}")
                rows = db.execute(f"SELECT * FROM [{t}] ORDER BY rowid DESC LIMIT 5").fetchall()
                for r in rows:
                    d = dict(zip(cols, r))
                    text = str(d.get("text", d.get("content", d.get("value", d.get("claim", d.get("slot", ""))))))[:120]
                    print(f"    {text}")
        db.close()
    except Exception as e:
        print(f"\n=== {db_path} === ERROR: {e}")

#!/usr/bin/env python3
"""Database Integrity Check"""

import sqlite3
from pathlib import Path

print("=" * 60)
print("TEST 7.1: Database Integrity Check")
print("=" * 60)

# Find all databases
pa_dir = Path("D:/AI_round2/personal_agent")
memory_dbs = list(pa_dir.glob("crt_memory_*.db"))
ledger_dbs = list(pa_dir.glob("crt_ledger_*.db"))

print(f"Found {len(memory_dbs)} memory DBs")
print(f"Found {len(ledger_dbs)} ledger DBs")

# Check the most recent ledger DB
if ledger_dbs:
    latest_ledger = sorted(ledger_dbs, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    print(f"\nChecking: {latest_ledger.name}")
    
    conn = sqlite3.connect(str(latest_ledger))
    cur = conn.cursor()
    
    # Check tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Tables: {tables}")
    
    # Count records
    for table in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  {table}: {count} records")
        except Exception as e:
            print(f"  {table}: error - {e}")
    
    # Check for contradictions status distribution
    if "contradictions" in tables:
        cur.execute("SELECT status, COUNT(*) FROM contradictions GROUP BY status")
        status_dist = cur.fetchall()
        print("\nContradiction status distribution:")
        for status, count in status_dist:
            print(f"  {status}: {count}")
    
    conn.close()
    print("\n✅ Database integrity check passed")
else:
    print("⚠️ No ledger databases found")

# Check for any recent DBs
all_dbs = list(pa_dir.glob("*.db"))
print(f"\nAll DBs in personal_agent/: {len(all_dbs)}")
for db in sorted(all_dbs, key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
    print(f"  - {db.name} ({db.stat().st_size / 1024:.1f} KB)")

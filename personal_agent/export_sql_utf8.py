#!/usr/bin/env python3
"""
Export all databases as UTF-8 encoded SQL dumps.
Fixes audit finding: dumps were UTF-16, should be UTF-8.
"""

import sqlite3
from pathlib import Path


def export_db_utf8(db_path, output_path):
    """Export database as UTF-8 encoded SQL dump."""
    if not Path(db_path).exists():
        print(f"⚠ Skipping {db_path} (not found)")
        return
    
    conn = sqlite3.connect(db_path)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in conn.iterdump():
            f.write(f"{line}\n")
    
    conn.close()
    print(f"✓ Exported {db_path} → {output_path} (UTF-8)")


# Create test_results directory if it doesn't exist
Path("test_results").mkdir(exist_ok=True)

# Export all databases
export_db_utf8('personal_agent/crt_memory.db', 'test_results/memory_dump_utf8.sql')
export_db_utf8('personal_agent/crt_ledger.db', 'test_results/ledger_dump_utf8.sql')
export_db_utf8('personal_agent/active_learning.db', 'test_results/active_learning_dump_utf8.sql')

print("\n✓ All databases exported with UTF-8 encoding")

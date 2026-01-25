"""Database Schema Verification Script"""
import sqlite3
import glob
from pathlib import Path

print('=' * 70)
print('DATABASE SCHEMA VERIFICATION')
print('=' * 70)

# Find all memory databases
db_pattern = 'personal_agent/crt_memory_*.db'
memory_dbs = glob.glob(db_pattern)

if not memory_dbs:
    print('⚠️ No memory databases found')
    print('Creating test database to check schema...')
    
    # Import and initialize
    import sys
    sys.path.insert(0, 'personal_agent')
    from crt_memory import initialize_memory_db
    
    test_db = 'personal_agent/crt_memory_schema_test.db'
    initialize_memory_db(test_db)
    memory_dbs = [test_db]

print(f'\nFound {len(memory_dbs)} memory database(s)')

# Check schema of first database
test_db = sorted(memory_dbs, key=lambda x: Path(x).stat().st_mtime, reverse=True)[0]
print(f'\nChecking schema of most recent: {test_db}')

conn = sqlite3.connect(test_db)
cursor = conn.cursor()

# Get table info for memories table
cursor.execute('PRAGMA table_info(memories)')
columns = cursor.fetchall()

print('\nCOLUMNS IN "memories" TABLE:')
print('-' * 70)
print(f'{"ID":<5} {"Name":<25} {"Type":<15} {"NotNull":<10} {"Default":<15}')
print('-' * 70)

has_deprecated = False
has_deprecation_reason = False

for col in columns:
    cid, name, ctype, notnull, default_val, pk = col
    print(f'{cid:<5} {name:<25} {ctype:<15} {notnull:<10} {str(default_val):<15}')
    
    if name == 'deprecated':
        has_deprecated = True
    if name == 'deprecation_reason':
        has_deprecation_reason = True

print('-' * 70)

# Verdict on OVERRIDE policy
print('\nOVERRIDE POLICY SCHEMA CHECK:')
if has_deprecated and has_deprecation_reason:
    print('✅ Schema has "deprecated" and "deprecation_reason" columns')
    print('   OVERRIDE policy should work')
else:
    print('❌ Schema MISSING required columns:')
    if not has_deprecated:
        print('   - deprecated (INTEGER)')
    if not has_deprecation_reason:
        print('   - deprecation_reason (TEXT)')
    print('\n   THIS IS WHY OVERRIDE RETURNS 500 ERROR')
    print('\n   FIX: Run migration to add columns')

conn.close()

# Check ledger schema for metadata column
print('\n' + '=' * 70)
print('LEDGER SCHEMA VERIFICATION')
print('=' * 70)

ledger_dbs = glob.glob('personal_agent/crt_ledger_*.db')

if ledger_dbs:
    test_ledger = sorted(ledger_dbs, key=lambda x: Path(x).stat().st_mtime, reverse=True)[0]
    print(f'\nChecking schema of most recent: {test_ledger}')
    
    conn = sqlite3.connect(test_ledger)
    cursor = conn.cursor()
    
    cursor.execute('PRAGMA table_info(contradictions)')
    ledger_columns = cursor.fetchall()
    
    print('\nCOLUMNS IN "contradictions" TABLE:')
    print('-' * 70)
    
    has_metadata = False
    for col in ledger_columns:
        cid, name, ctype, notnull, default_val, pk = col
        print(f'{cid:<5} {name:<25} {ctype:<15}')
        if name == 'metadata':
            has_metadata = True
    
    if has_metadata:
        print('\n✅ Ledger has "metadata" column')
    else:
        print('\n❌ Ledger MISSING "metadata" column')
    
    # Check if conflict_resolutions table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conflict_resolutions'")
    has_resolutions_table = cursor.fetchone() is not None
    
    if has_resolutions_table:
        print('✅ "conflict_resolutions" table exists')
    else:
        print('⚠️ "conflict_resolutions" table not found')
    
    # Check if resolution_method column exists
    has_resolution_method = any(col[1] == 'resolution_method' for col in ledger_columns)
    if has_resolution_method:
        print('✅ "resolution_method" column exists')
    else:
        print('⚠️ "resolution_method" column not found')
    
    conn.close()
else:
    print('⚠️ No ledger databases found')

print('\n' + '=' * 70)
print('SCHEMA SUMMARY')
print('=' * 70)
print(f'deprecated column: {"✅" if has_deprecated else "❌"}')
print(f'deprecation_reason column: {"✅" if has_deprecation_reason else "❌"}')

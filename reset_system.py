"""Reset the entire CRT system - clear all databases and start fresh"""
import sqlite3
import os
from pathlib import Path

print("\n" + "="*70)
print("🔄 SYSTEM RESET - Clearing all databases")
print("="*70 + "\n")

# Find all database files
db_files = []

# User profile DB
profile_db = Path("personal_agent/crt_user_profile.db")
if profile_db.exists():
    db_files.append(("User Profile", profile_db))

# Thread-specific DBs
for db_file in Path("personal_agent").glob("*.db"):
    if db_file.name != "crt_user_profile.db":
        db_files.append((f"Thread DB", db_file))

# Data directory DBs
data_dir = Path("data")
if data_dir.exists():
    for db_file in data_dir.glob("*.db"):
        db_files.append(("Data", db_file))

# Memory dumps
memory_dir = Path("memory_dumps")
if memory_dir.exists():
    for db_file in memory_dir.glob("*.db"):
        db_files.append(("Memory Dump", db_file))

print(f"Found {len(db_files)} database files:\n")

for db_type, db_path in db_files:
    size = db_path.stat().st_size / 1024  # KB
    print(f"  📁 {db_type}: {db_path.name} ({size:.1f} KB)")

print("\n" + "-"*70)
choice = input("\n⚠️  Delete ALL databases and start fresh? (yes/no): ")

if choice.lower() != 'yes':
    print("\n❌ Reset cancelled.")
    exit(0)

print("\n🗑️  Deleting databases...\n")

deleted_count = 0
for db_type, db_path in db_files:
    try:
        db_path.unlink()
        print(f"  ✅ Deleted: {db_path.name}")
        deleted_count += 1
    except Exception as e:
        print(f"  ❌ Failed to delete {db_path.name}: {e}")

print("\n" + "="*70)
print(f"✅ RESET COMPLETE: {deleted_count}/{len(db_files)} databases deleted")
print("="*70)

print("\n📝 Next steps:")
print("  1. Restart the API server (./start_api.ps1)")
print("  2. Introduce yourself again in a chat")
print("  3. Fresh start with clean memory!")
print()

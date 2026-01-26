#!/usr/bin/env python3
"""
Prepare a clean release by archiving non-essential files and removing build artifacts.

Usage:
    python tools/prepare_clean_release.py --dry-run    # Preview changes
    python tools/prepare_clean_release.py --execute    # Apply changes
"""

import argparse
import os
import shutil
import stat
import time
from pathlib import Path
from datetime import datetime

# Project root
ROOT = Path(__file__).parent.parent

# Files and directories to archive (development/internal only)
ARCHIVE_TARGETS = [
    "ai_logs/",
    "archive/",
    "artifacts/",
    "contradiction_stress_test_output/",
    "stress_test_evidence/",
    "test_results/",
    "experiments/",
    "user_research/",
    "roadmap/",
    ".github/prompts/",  # Internal prompt engineering
]

# Files to delete (generated/temporary)
DELETE_PATTERNS = [
    "**/*.db",
    "**/*.db-shm",
    "**/*.db-wal",
    "**/__pycache__",
    "**/.pytest_cache",
    "**/crt_memory.egg-info",
    "**/*.pyc",
    "**/.DS_Store",
    ".venv/",
    ".vscode/",
]

# Optional modules to review (not auto-deleted, but flagged)
OPTIONAL_MODULES = [
    "personal_agent/active_learning.py",
    "personal_agent/background_jobs.py",
    "personal_agent/jobs_db.py",
    "personal_agent/jobs_worker.py",
    "personal_agent/training_loop.py",
    "personal_agent/researcher.py",
    "personal_agent/research_engine.py",
    "personal_agent/idle_scheduler.py",
    "personal_agent/onboarding.py",
    "personal_agent/proactive_triggers.py",
    "crt_background_worker.py",
    "crt_apply_promotions.py",
]


def handle_remove_error(func, path, exc_info):
    """
    Error handler for shutil.rmtree to handle Windows file permission issues.
    Attempts to change file permissions and retry deletion.
    """
    # Try to change permissions and retry
    try:
        os.chmod(path, stat.S_IWRITE)
        time.sleep(0.1)  # Brief pause
        func(path)
    except Exception:
        # If still failing, it's likely a file lock - will be reported as failed
        pass


def preview_changes():
    """Preview what will be archived/deleted."""
    print("=" * 80)
    print("CLEAN RELEASE PREVIEW")
    print("=" * 80)
    
    print("\n📦 Files/Dirs to ARCHIVE:")
    archive_count = 0
    for target in ARCHIVE_TARGETS:
        path = ROOT / target
        if path.exists():
            size = get_size(path)
            print(f"  ✓ {target} ({size})")
            archive_count += 1
        else:
            print(f"  ✗ {target} (not found)")
    
    print(f"\n🗑️  Files to DELETE (generated artifacts):")
    delete_count = 0
    for pattern in DELETE_PATTERNS:
        matches = list(ROOT.glob(pattern))
        if matches:
            print(f"  • {pattern} ({len(matches)} matches)")
            delete_count += len(matches)
    
    print(f"\n⚠️  Optional modules (review for removal):")
    for module in OPTIONAL_MODULES:
        path = ROOT / module
        if path.exists():
            print(f"  • {module}")
    
    print(f"\n📊 Summary:")
    print(f"  • Archive targets: {archive_count}")
    print(f"  • Generated files to delete: {delete_count}")
    print(f"  • Optional modules flagged: {len([m for m in OPTIONAL_MODULES if (ROOT / m).exists()])}")


def execute_cleanup(create_archive=True):
    """Execute the cleanup process."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = ROOT / f"_internal_archive_{timestamp}"
    
    # Archive development files (skip very large directories)
    print("\n🗑️  Removing development files...")
    failed_removals = []
    
    for target in ARCHIVE_TARGETS:
        source = ROOT / target
        if source.exists():
            try:
                if source.is_dir():
                    print(f"  🗑️  Removing: {target} ({get_size(source)})")
                    shutil.rmtree(source, ignore_errors=False, onerror=handle_remove_error)
                    print(f"  ✓ Removed: {target}")
                else:
                    source.unlink()
                    print(f"  ✓ Removed: {target}")
            except Exception as e:
                print(f"  ⚠️  Failed to remove {target}: {e}")
                failed_removals.append((target, str(e)))
    
    # Delete generated files
    print("\n🗑️  Deleting generated artifacts...")
    for pattern in DELETE_PATTERNS:
        matches = list(ROOT.glob(pattern))
        for path in matches:
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink()
            except Exception:
                pass  # Ignore deletion failures for generated files
        if matches:
            print(f"  ✓ Deleted {len(matches)} items matching: {pattern}")
    
    print(f"\n✅ Cleanup complete!")
    
    if failed_removals:
        print(f"\n⚠️  {len(failed_removals)} items not removed (likely file locks):")
        for target, error in failed_removals:
            print(f"  • {target}")
        print(f"\n💡 Common cause: Log files open in another process. Close apps and retry.")
    
    print(f"\n⚠️  Next steps:")
    print(f"  1. Review optional modules and remove if not needed")
    print(f"  2. Run: python tools/audit_dependencies.py")
    print(f"  3. Test: pytest tests/")
    print(f"  4. Verify: python tools/crt_stress_test.py --turns 5")


def get_size(path: Path) -> str:
    """Get human-readable size of file or directory."""
    if path.is_file():
        size = path.stat().st_size
    else:
        size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}TB"


def main():
    parser = argparse.ArgumentParser(description="Prepare clean release of CRT Memory")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes without executing")
    group.add_argument("--execute", action="store_true", help="Execute cleanup")
    parser.add_argument("--no-archive", action="store_true", help="Delete files without archiving")
    
    args = parser.parse_args()
    
    if args.dry_run:
        preview_changes()
    elif args.execute:
        print("⚠️  WARNING: This will permanently DELETE files!")
        print("⚠️  Archiving is skipped due to large file sizes.")
        print("⚠️  Make sure you have a Git backup before proceeding!")
        confirm = input("\nContinue? [y/N]: ")
        if confirm.lower() == 'y':
            execute_cleanup(create_archive=not args.no_archive)
        else:
            print("Cancelled.")
    

if __name__ == "__main__":
    main()

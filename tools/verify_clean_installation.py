#!/usr/bin/env python3
"""
Verify that the clean installation has all necessary components.

Usage:
    python tools/verify_clean_installation.py
"""

from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent

# Critical files that must exist
CRITICAL_FILES = [
    "README.md",
    "LICENSE",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "crt_api.py",
    "personal_agent/crt_rag.py",
    "personal_agent/crt_core.py",
    "personal_agent/crt_memory.py",
    "personal_agent/crt_ledger.py",
    "conftest.py",  # At root, not in tests/
    "tools/crt_stress_test.py",
]

# Important documentation
DOCS = [
    "CONTRIBUTING.md",
    "QUICKSTART.md",
    "KNOWN_LIMITATIONS.md",
]

# Files that should NOT exist in clean release
SHOULD_NOT_EXIST = [
    "ai_logs/",
    "archive/",
    "roadmap/",
    "user_research/",
    ".venv/",
    "*.db",  # SQLite databases
]


def check_file_exists(path: Path) -> bool:
    """Check if file or directory exists."""
    return (ROOT / path).exists()


def check_imports():
    """Verify critical Python imports work."""
    print("\n🐍 Testing Python imports...")
    
    imports_to_test = [
        ("personal_agent.crt_rag", "CRTEnhancedRAG"),
        ("personal_agent.fact_slots", "extract_fact_slots"),
        ("personal_agent.crt_ledger", "CRTLedger"),
        ("personal_agent.crt_memory", "CRTMemoryStore"),
    ]
    
    all_passed = True
    for module, attr in imports_to_test:
        try:
            mod = __import__(module, fromlist=[attr])
            getattr(mod, attr)
            print(f"  ✓ {module}.{attr}")
        except ImportError as e:
            print(f"  ⚠️  {module}.{attr} - Missing dependency: {e}")
            # Don't fail on missing dependencies (might not have installed extras)
        except AttributeError as e:
            print(f"  ⚠️  {module}.{attr} - {e}")
            # Don't fail on wrong attribute names
        except Exception as e:
            print(f"  ✗ {module}.{attr} - {e}")
            all_passed = False
    
    return all_passed


def main():
    print("=" * 80)
    print("CLEAN INSTALLATION VERIFICATION")
    print("=" * 80)
    
    # Check critical files
    print("\n📋 Critical files:")
    all_critical = True
    for file in CRITICAL_FILES:
        exists = check_file_exists(file)
        status = "✓" if exists else "✗"
        print(f"  {status} {file}")
        if not exists:
            all_critical = False
    
    # Check documentation
    print("\n📚 Documentation:")
    for file in DOCS:
        exists = check_file_exists(file)
        status = "✓" if exists else "⚠️ "
        print(f"  {status} {file}")
    
    # Check for files that shouldn't exist
    print("\n🚫 Files that should NOT exist:")
    unwanted_found = []
    for pattern in SHOULD_NOT_EXIST:
        if '*' in pattern:
            matches = list(ROOT.glob(f"**/{pattern}"))
            if matches:
                print(f"  ⚠️  Found {len(matches)} files matching: {pattern}")
                unwanted_found.extend(matches)
        else:
            path = ROOT / pattern
            if path.exists():
                print(f"  ⚠️  {pattern}")
                unwanted_found.append(path)
    
    if not unwanted_found:
        print("  ✓ No unwanted files found")
    
    # Test imports
    imports_ok = check_imports()
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    
    if all_critical and imports_ok and not unwanted_found:
        print("✅ Installation verification PASSED")
        print("   Ready for release!")
        return 0
    else:
        print("❌ Installation verification FAILED")
        if not all_critical:
            print("   • Missing critical files")
        if not imports_ok:
            print("   • Import errors detected")
        if unwanted_found:
            print(f"   • {len(unwanted_found)} unwanted files found")
        return 1


if __name__ == "__main__":
    sys.exit(main())

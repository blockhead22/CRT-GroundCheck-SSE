#!/usr/bin/env python3
"""
Audit Python dependencies and identify unused packages.

Usage:
    python tools/audit_dependencies.py
"""

import ast
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent

# Dependencies from requirements.txt
REQUIREMENTS = [
    "numpy",
    "scikit-learn",
    "sentence-transformers",
    "jsonschema",
    "pytest",
    "hdbscan",
    "websockets",
    "fastapi",
    "uvicorn",
    "beautifulsoup4",
    "requests",
    "transformers",
    "datasets",
    "xgboost",
    "torch",
    "matplotlib",
    "seaborn",
    "pandas",
]

# Map package names to import names
PACKAGE_TO_IMPORT = {
    "scikit-learn": "sklearn",
    "beautifulsoup4": "bs4",
    "sentence-transformers": "sentence_transformers",
}

# Essential core files to scan
CORE_FILES = [
    "personal_agent/crt_rag.py",
    "personal_agent/crt_core.py",
    "personal_agent/crt_memory.py",
    "personal_agent/crt_ledger.py",
    "personal_agent/embeddings.py",
    "personal_agent/ollama_client.py",
    "personal_agent/fact_slots.py",
    "personal_agent/two_tier_facts.py",
    "personal_agent/ml_contradiction_detector.py",
    "crt_api.py",
    "tests/*.py",
]


def extract_imports(file_path: Path):
    """Extract all import statements from a Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
        
        return imports
    except Exception as e:
        print(f"  ⚠️  Error parsing {file_path}: {e}")
        return set()


def scan_codebase():
    """Scan all Python files for imports."""
    all_imports = set()
    files_scanned = 0
    
    # Scan essential core files
    for pattern in CORE_FILES:
        for file_path in ROOT.glob(pattern):
            if file_path.is_file():
                imports = extract_imports(file_path)
                all_imports.update(imports)
                files_scanned += 1
    
    # Scan all personal_agent files
    for file_path in (ROOT / "personal_agent").glob("*.py"):
        if file_path.name != "__init__.py":
            imports = extract_imports(file_path)
            all_imports.update(imports)
            files_scanned += 1
    
    # Scan groundcheck
    if (ROOT / "groundcheck" / "groundcheck").exists():
        for file_path in (ROOT / "groundcheck" / "groundcheck").glob("*.py"):
            imports = extract_imports(file_path)
            all_imports.update(imports)
            files_scanned += 1
    
    print(f"📊 Scanned {files_scanned} Python files")
    return all_imports


def categorize_dependencies():
    """Categorize dependencies by usage."""
    print("\n🔍 Scanning codebase for imports...")
    used_imports = scan_codebase()
    
    used = []
    unused = []
    
    for pkg in REQUIREMENTS:
        import_name = PACKAGE_TO_IMPORT.get(pkg, pkg)
        
        # Check if package is imported
        is_used = any(import_name in imp or imp in import_name for imp in used_imports)
        
        if is_used:
            used.append(pkg)
        else:
            unused.append(pkg)
    
    return used, unused, used_imports


def main():
    print("=" * 80)
    print("DEPENDENCY AUDIT")
    print("=" * 80)
    
    used, unused, all_imports = categorize_dependencies()
    
    print("\n✅ Used dependencies (keep):")
    for pkg in sorted(used):
        print(f"  • {pkg}")
    
    print(f"\n⚠️  Potentially unused dependencies ({len(unused)}):")
    for pkg in sorted(unused):
        print(f"  • {pkg}")
    
    print(f"\n📦 Recommended minimal requirements.txt:")
    print("-" * 80)
    
    # Core runtime dependencies
    core_deps = [
        "fastapi>=0.100.0",
        "uvicorn[standard]>=0.22.0",
        "sentence-transformers>=2.2.0",
        "numpy>=1.24.0",
        "scikit-learn>=1.3.0",
        "xgboost>=1.7.0",
        "jsonschema>=4.0.0",
    ]
    
    # Optional dev dependencies
    dev_deps = [
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
    ]
    
    # Optional full dependencies (ML/visualization)
    full_deps = [
        "torch>=2.0.0",
        "transformers>=4.30.0",
        "pandas>=2.0.0",
        "matplotlib>=3.7.0",
        "seaborn>=0.12.0",
        "hdbscan>=0.8.0",
    ]
    
    print("# Core runtime dependencies")
    for dep in core_deps:
        print(dep)
    
    print("\n# Development dependencies (optional)")
    for dep in dev_deps:
        print(f"# {dep}")
    
    print("\n# Full ML/visualization dependencies (optional)")
    for dep in full_deps:
        print(f"# {dep}")
    
    print("\n" + "=" * 80)
    print("💡 Recommendations:")
    print("  1. Move dev dependencies to pyproject.toml [project.optional-dependencies.dev]")
    print("  2. Move ML dependencies to [project.optional-dependencies.full]")
    print("  3. Keep only core runtime deps in requirements.txt")
    print("  4. Users can install with: pip install .[dev] or pip install .[full]")
    print("=" * 80)


if __name__ == "__main__":
    main()

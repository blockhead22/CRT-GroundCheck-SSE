```prompt
# Phase 1: Ship GroundCheck to PyPI

> **Goal:** `pip install groundcheck` works on PyPI within 5 days.
> **Why first:** Zero external dependencies (stdlib only), already 90% decoupled, 1.17ms benchmarks, solves the most searchable problem ("LLM hallucination detection"), and a competing PR (#1968 on Instructor) is using the same class name.
> **Priority:** URGENT — own the PyPI package name before anyone else registers it.

---

## What GroundCheck Is (Positioning)

GroundCheck verifies LLM-generated text against **multiple sources with trust scores and timestamps**. It is NOT a single-document field checker. It handles:

- Multiple contradicting memories with different trust levels
- Temporal awareness (most recent vs most trusted)
- Disclosure requirements when sources disagree
- Automatic correction generation
- Slot-based domain knowledge (employer, location, name are mutually exclusive)

**Tagline:** "Trust-weighted hallucination detection for AI agents. Zero dependencies. Sub-2ms."

**How it differs from Instructor's GroundCheck PR:**
| | This GroundCheck | Instructor PR #1968 |
|---|---|---|
| Input | `generated_text` + `List[Memory]` with trust/timestamps | `source_text` (string) + `extracted_data` (dict) |
| Problem | Multi-source contradiction-aware verification | Single-document field checking |
| Unique features | Trust weighting, contradiction detection, disclosure requirements, correction generation, temporal awareness | Fuzzy matching, `rapidfuzz` dependency |
| Dependencies | Zero (stdlib: `re`, `typing`, `difflib`, `dataclasses`) | `rapidfuzz` (required for fuzzy) |

---

## Day 1: Package Hygiene

### 1.1 Update `pyproject.toml`

**File:** `groundcheck/pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "groundcheck"
version = "0.1.0"
description = "Trust-weighted hallucination detection for AI agents. Verify LLM outputs against multiple sources with contradiction awareness. Zero dependencies. Sub-2ms."
readme = "README.md"
requires-python = ">=3.9"
license = {text = "MIT"}
authors = [
    {name = "blockhead22"}
]
keywords = [
    "llm",
    "hallucination",
    "grounding",
    "verification",
    "ai",
    "memory",
    "trust",
    "contradiction",
    "rag",
    "fact-checking",
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Typing :: Typed",
]

[project.urls]
Homepage = "https://github.com/blockhead22/CRT-GroundCheck-SSE"
Repository = "https://github.com/blockhead22/CRT-GroundCheck-SSE"
Issues = "https://github.com/blockhead22/CRT-GroundCheck-SSE/issues"
Documentation = "https://github.com/blockhead22/CRT-GroundCheck-SSE/tree/main/groundcheck"

[project.optional-dependencies]
neural = [
    "sentence-transformers>=2.2.0",
]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "build>=1.0.0",
    "twine>=4.0.0",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["groundcheck*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Key decisions:**
- `version = "0.1.0"` — ship as beta, iterate fast
- NO runtime dependencies. Neural features are optional via `[neural]`
- `Development Status :: 4 - Beta` (not Alpha — it's tested and benchmarked)
- Keywords target what people actually search: "llm hallucination", "grounding verification", "rag fact-checking"

### 1.2 Verify `__init__.py` Exports Are Clean

**File:** `groundcheck/groundcheck/__init__.py`

Current exports are correct. Verify:
- `GroundCheck` class — main entry point
- `Memory` dataclass — input type
- `VerificationReport` dataclass — output type
- `ExtractedFact` dataclass — intermediate type
- `extract_fact_slots` function — standalone utility
- Neural imports behind `try/except` — correct, graceful fallback

**No changes needed** unless you want to add `ContradictionDetail` to exports (it's in `types.py` but not in `__all__`). Recommend adding it:

```python
from .types import Memory, VerificationReport, ExtractedFact, ContradictionDetail
```

And add to `__all__`:
```python
"ContradictionDetail",
```

### 1.3 Add `py.typed` Marker

**Create file:** `groundcheck/groundcheck/py.typed` (empty file)

This tells tools like mypy and Pylance that the package ships type information. Free discoverability win.

### 1.4 Verify MANIFEST.in / Package Discovery

**Create file:** `groundcheck/MANIFEST.in`

```
include LICENSE
include README.md
include groundcheck/py.typed
recursive-include groundcheck *.py
```

---

## Day 2: README Rewrite (The Sales Page)

### 2.1 Rewrite `groundcheck/README.md`

The current README is technical but doesn't sell. New structure:

```markdown
# GroundCheck

**Trust-weighted hallucination detection for AI agents. Zero dependencies. Sub-2ms.**

[![PyPI version](https://badge.fury.io/py/groundcheck.svg)](https://pypi.org/project/groundcheck/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)]()

---

## The Problem

Your AI agent says "you work at Amazon." Memory says "Microsoft." Your vector store won't catch this — it just returns the most similar embedding. GroundCheck catches it in <2ms with zero dependencies.

## Install

\`\`\`bash
pip install groundcheck
\`\`\`

## 10-Second Demo

\`\`\`python
from groundcheck import GroundCheck, Memory

verifier = GroundCheck()

memories = [
    Memory(id="m1", text="User works at Microsoft", trust=0.9),
    Memory(id="m2", text="User works at Amazon", trust=0.3),
]

result = verifier.verify("You work at Amazon", memories)

print(result.passed)          # False
print(result.hallucinations)  # ["Amazon"]
print(result.corrected)       # "You work at Microsoft"
print(result.confidence)      # 0.87
\`\`\`

## What Makes This Different

| Feature | GroundCheck | SelfCheckGPT | NLI Models | Instructor verify_extraction |
|---------|------------|--------------|------------|------------------------------|
| Multiple sources | ✅ List[Memory] | ❌ Self-sampling | ❌ Premise/hypothesis pair | ❌ Single source string |
| Trust scores | ✅ Per-memory trust weighting | ❌ | ❌ | ❌ |
| Contradiction detection | ✅ Cross-memory conflicts | ❌ | Partial | ❌ |
| Correction generation | ✅ Rewrites hallucinations | ❌ | ❌ | ❌ |
| Temporal awareness | ✅ most_recent vs most_trusted | ❌ | ❌ | ❌ |
| Dependencies | **Zero** (stdlib only) | torch, transformers | torch, transformers | rapidfuzz |
| Latency | **1.17ms mean** | 3,082ms | ~500ms | ~1ms |
| Extra LLM calls | **Zero** | 3-5 per check | Zero | Zero |

## How It Works

\`\`\`
Generated text + Retrieved memories (with trust scores)
    → Extract fact claims (slot-based: name, employer, location, ...)
    → Detect contradictions across memories
    → Build grounding map (fuzzy match claims to memories)
    → Check disclosure requirements (trust-weighted)
    → Calculate confidence score
    → Generate corrections (strict mode)
    → VerificationReport
\`\`\`

## Trust-Weighted Verification

GroundCheck doesn't treat all sources equally. Each memory has a trust score:

\`\`\`python
memories = [
    Memory(id="m1", text="User is named Alice", trust=0.9),   # High trust
    Memory(id="m2", text="User is named Bob", trust=0.3),     # Low trust
]

result = verifier.verify("Your name is Bob", memories)
print(result.requires_disclosure)  # True — trust gap > 0.3
print(result.contradiction_details[0].most_trusted_value)  # "Alice"
print(result.contradiction_details[0].most_recent_value)   # depends on timestamps
\`\`\`

## Verification Modes

- **`strict`** — generates corrected text, replaces hallucinations with grounded facts
- **`permissive`** — detects and reports, doesn't rewrite

\`\`\`python
result = verifier.verify("You live in Paris", memories, mode="strict")
print(result.corrected)  # Rewritten with grounded facts

result = verifier.verify("You live in Paris", memories, mode="permissive")
print(result.corrected)  # None — permissive doesn't rewrite
\`\`\`

## Supported Fact Slots

15+ built-in slot types with mutual exclusivity knowledge:

`name`, `employer`, `location`, `title`, `occupation`, `age`, `school`,
`degree`, `favorite_color`, `coffee`, `hobby`, `pet`, `project`,
`graduation_year`, `programming_experience`, and more.

GroundCheck knows that a person can only have one employer at a time, but can have
multiple hobbies. This built-in domain knowledge prevents false positives.

## Neural Mode (Optional)

For paraphrase handling and semantic matching:

\`\`\`bash
pip install groundcheck[neural]
\`\`\`

\`\`\`python
# Automatically used when sentence-transformers is installed
verifier = GroundCheck()  # Detects neural availability
result = verifier.verify("Employed by Google", memories)  # Matches "works at Google"
\`\`\`

| Mode | Paraphrase Accuracy | Latency |
|------|-------------------|---------|
| Regex-only (default) | 70% | 1.17ms |
| Neural | 85-90% | ~15ms |

## API Reference

### `GroundCheck`
- `verify(generated_text, retrieved_memories, mode="strict")` → `VerificationReport`
- `extract_claims(text)` → `Dict[str, ExtractedFact]`
- `find_support(claim, memories)` → match info

### `VerificationReport`
- `passed: bool` — did verification pass?
- `corrected: Optional[str]` — rewritten text (strict mode)
- `hallucinations: List[str]` — hallucinated values
- `grounding_map: Dict` — claim → supporting memory
- `confidence: float` — trust-weighted confidence (0.0-1.0)
- `contradiction_details: List[ContradictionDetail]` — full conflict info
- `requires_disclosure: bool` — must the response acknowledge conflicts?

### `Memory`
- `id: str` — unique identifier
- `text: str` — memory content
- `trust: float` — trust score (0.0-1.0, default 1.0)
- `timestamp: Optional[str]` — when this was stored

### `ContradictionDetail`
- `slot: str` — which fact slot conflicts
- `values: List[str]` — conflicting values
- `most_trusted_value` — value from highest-trust memory
- `most_recent_value` — value from most recent memory

## Performance

\`\`\`
Benchmark: 1,000 verifications
Mean latency:  1.17ms
P95 latency:   2.09ms
P99 latency:   3.41ms
vs SelfCheckGPT: 2,634x faster
Memory: ~2MB RSS
Dependencies: 0
\`\`\`

## Development

\`\`\`bash
git clone https://github.com/blockhead22/CRT-GroundCheck-SSE.git
cd CRT-GroundCheck-SSE/groundcheck
pip install -e ".[dev]"
pytest tests/ -v
\`\`\`

## License

MIT
```

### Key README principles:
- Problem statement in 2 sentences
- Copy-paste demo that actually works
- Comparison table against known alternatives (SelfCheckGPT, NLI, Instructor)
- "Zero dependencies" badge is the hook
- Performance numbers are the closer
- Neural mode is positioned as upgrade, not requirement

---

## Day 3: Test Suite & CI

### 3.1 Verify All Tests Pass Standalone

Run from `groundcheck/` directory only — no parent project dependencies:

```bash
cd groundcheck
pip install -e ".[dev]"
pytest tests/ -v --tb=short
```

**Every test must pass with ONLY stdlib available.** Any test that imports from `personal_agent`, `crt_api`, or any parent project file is INVALID and must be fixed or removed.

### 3.2 Add Missing Test Coverage

Current test files:
- `test_verifier.py` — core verification
- `test_fact_extraction.py` — slot extraction
- `test_integration.py` — integration tests
- `test_semantic_matcher.py` — semantic matching
- `test_neural_extraction.py` — neural features
- `test_compound_splitting.py` — compound values
- `test_contradiction_aware.py` — contradiction detection
- `test_benchmark_contradictions.py` — benchmark

**Add these tests if missing:**

```python
# test_trust_weighting.py — Trust score edge cases
def test_trust_weighted_confidence():
    """Confidence should weight toward high-trust memories."""
    verifier = GroundCheck()
    memories = [
        Memory(id="m1", text="User works at Microsoft", trust=0.95),
        Memory(id="m2", text="User works at Amazon", trust=0.1),
    ]
    result = verifier.verify("You work at Microsoft", memories)
    assert result.passed is True
    assert result.confidence > 0.8

def test_equal_trust_requires_disclosure():
    """When trust scores are close, both should be disclosed."""
    verifier = GroundCheck()
    memories = [
        Memory(id="m1", text="User works at Microsoft", trust=0.7),
        Memory(id="m2", text="User works at Amazon", trust=0.6),
    ]
    result = verifier.verify("You work at Microsoft", memories)
    assert result.requires_disclosure is True

def test_zero_trust_memory_ignored():
    """Memory with trust=0 should not affect verification."""
    verifier = GroundCheck()
    memories = [
        Memory(id="m1", text="User works at Microsoft", trust=0.9),
        Memory(id="m2", text="User works at Amazon", trust=0.0),
    ]
    result = verifier.verify("You work at Microsoft", memories)
    assert result.passed is True

# test_pypi_installability.py — Package sanity
def test_no_external_imports():
    """Core groundcheck must not import anything outside stdlib."""
    import importlib
    import groundcheck.verifier as v
    import groundcheck.types as t
    import groundcheck.fact_extractor as f
    import groundcheck.utils as u
    # If we got here without ImportError, stdlib-only is confirmed

def test_version_exists():
    import groundcheck
    assert hasattr(groundcheck, '__version__')
    assert groundcheck.__version__ == "0.1.0"
```

### 3.3 Add GitHub Actions CI

**Create file:** `groundcheck/.github/workflows/test.yml`

Note: This lives inside the groundcheck subdirectory's own workflow. If the repo is the monorepo, put it at the repo root and scope to `groundcheck/` paths.

```yaml
name: GroundCheck Tests

on:
  push:
    paths: ['groundcheck/**']
  pull_request:
    paths: ['groundcheck/**']

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.9', '3.10', '3.11', '3.12', '3.13']
    
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install package
        working-directory: groundcheck
        run: pip install -e ".[dev]"
      
      - name: Run tests
        working-directory: groundcheck
        run: pytest tests/ -v --tb=short
      
      - name: Verify zero dependencies
        run: |
          python -c "
          import groundcheck
          from groundcheck import GroundCheck, Memory
          v = GroundCheck()
          r = v.verify('test', [Memory(id='m1', text='test')])
          print(f'GroundCheck {groundcheck.__version__} OK')
          "
```

---

## Day 4: Build & Test Upload

### 4.1 Build the Package

```bash
cd groundcheck
pip install build twine
python -m build
```

This creates:
- `dist/groundcheck-0.1.0.tar.gz`
- `dist/groundcheck-0.1.0-py3-none-any.whl`

### 4.2 Verify the Build

```bash
# Check the wheel contents
unzip -l dist/groundcheck-0.1.0-py3-none-any.whl

# Verify metadata
twine check dist/*

# Test install in a clean venv
python -m venv /tmp/test-gc
source /tmp/test-gc/bin/activate  # or .\Scripts\activate on Windows
pip install dist/groundcheck-0.1.0-py3-none-any.whl
python -c "
from groundcheck import GroundCheck, Memory
v = GroundCheck()
r = v.verify('You work at Amazon', [Memory(id='m1', text='User works at Microsoft')])
assert not r.passed
assert 'Amazon' in r.hallucinations
print('PASS: GroundCheck installs and works from wheel')
"
deactivate
```

### 4.3 Upload to TestPyPI First

```bash
twine upload --repository testpypi dist/*
# Test install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ groundcheck
```

### 4.4 Upload to PyPI

```bash
twine upload dist/*
```

**Pre-requisites:**
- PyPI account created at https://pypi.org/
- API token generated (or use trusted publisher via GitHub Actions)
- Package name `groundcheck` confirmed available

### 4.5 Verify Live Install

```bash
pip install groundcheck
python -c "from groundcheck import GroundCheck; print('SUCCESS')"
```

---

## Day 5: Announce & Iterate

### 5.1 GitHub Release

- Tag: `groundcheck-v0.1.0`
- Release title: "GroundCheck 0.1.0 — Trust-weighted hallucination detection"
- Body: Copy the top section of README (problem, install, demo, comparison table)

### 5.2 Publish GitHub Actions for Auto-Release

**Create file:** `.github/workflows/publish-groundcheck.yml` (at repo root)

```yaml
name: Publish GroundCheck to PyPI

on:
  push:
    tags: ['groundcheck-v*']

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      id-token: write  # For trusted publisher
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Build
        working-directory: groundcheck
        run: |
          pip install build
          python -m build
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: groundcheck/dist/
```

### 5.3 Seed Initial Visibility

- Post on r/MachineLearning, r/LocalLLaMA, r/Python (brief, code-first — show the 10-second demo)
- Tweet/post the comparison table (GroundCheck vs SelfCheckGPT vs NLI)
- Open a "Show HN" on Hacker News if you want maximum reach
- Consider reaching out to Instructor maintainers: "Hey, I see PR #1968 — our GroundCheck does something different (multi-memory + trust scoring). Happy to collaborate or differentiate names."

---

## Files Created/Modified Summary

| Action | File | Day |
|--------|------|-----|
| MODIFY | `groundcheck/pyproject.toml` | 1 |
| MODIFY | `groundcheck/groundcheck/__init__.py` (add ContradictionDetail export) | 1 |
| CREATE | `groundcheck/groundcheck/py.typed` | 1 |
| CREATE | `groundcheck/MANIFEST.in` | 1 |
| REWRITE | `groundcheck/README.md` | 2 |
| CREATE | `groundcheck/tests/test_trust_weighting.py` | 3 |
| CREATE | `groundcheck/tests/test_pypi_installability.py` | 3 |
| CREATE | `.github/workflows/groundcheck-test.yml` | 3 |
| BUILD | `groundcheck/dist/groundcheck-0.1.0-*` | 4 |
| UPLOAD | PyPI: `groundcheck==0.1.0` | 4 |
| CREATE | `.github/workflows/publish-groundcheck.yml` | 5 |
| CREATE | GitHub Release `groundcheck-v0.1.0` | 5 |

---

## What NOT To Do

1. **Do NOT add dependencies.** The zero-dep story is the entire marketing hook. If you need fuzzy matching, use `difflib.SequenceMatcher` (already in stdlib — you already do this).
2. **Do NOT bundle CRT Memory in this package.** GroundCheck is standalone. CRT Memory comes later as a separate `pip install crt-memory` that optionally depends on GroundCheck.
3. **Do NOT wait for adversarial hardening to finish.** GroundCheck is already tested (8 test files, stress tests, 1.17ms benchmarks). Ship what works.
4. **Do NOT rename the package** to avoid the Instructor PR collision. Your approach is architecturally different (multi-memory vs single-document). Same name, different tool — your README explains why.
5. **Do NOT over-engineer the README.** The comparison table and 10-second demo do the selling. Everything else is reference material.
6. **Do NOT add a CLI.** Nobody needs `groundcheck verify "text"` from the command line. Keep it library-only for v0.1.
7. **Do NOT touch the parent CRT monolith.** This phase is groundcheck/ subdirectory only.

---

## Validation Checklist (All Must Pass Before Calling Phase 1 Done)

- [ ] `pip install groundcheck` works from PyPI
- [ ] `from groundcheck import GroundCheck, Memory` works with zero external deps
- [ ] 10-second demo from README copy-pastes to working code
- [ ] `pytest tests/ -v` passes on Python 3.9, 3.10, 3.11, 3.12, 3.13
- [ ] `twine check dist/*` passes with no warnings
- [ ] GitHub Actions CI runs on push to `groundcheck/` paths
- [ ] Package name `groundcheck` is registered on PyPI
- [ ] README comparison table is accurate for all 4 alternatives
- [ ] Neural mode (`pip install groundcheck[neural]`) still works
- [ ] No imports from `personal_agent`, `crt_api`, or any parent project code

---

## What Comes After Phase 1

Once GroundCheck is on PyPI:

- **Phase 2 (Week 2):** GroundCheck MCP server — 3 tools for Claude/Copilot
- **Phase 3 (Week 3):** `crt-memory` extraction — the full trust-weighted memory system as `pip install crt-memory` with optional `groundcheck` dependency
- **Phase 4 (Week 4):** LangChain/LlamaIndex integrations, benchmark suite, docs site

The old `plan-openSourceExtraction.prompt.md` covers Phases 2-4. This plan replaces its Phase 1.
```

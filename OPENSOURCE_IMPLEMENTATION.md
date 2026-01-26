# Open Source Release - Implementation Guide

This guide documents the step-by-step process to prepare the repository for public release.

## Current Status

✅ **Preparation tools created:**
- `tools/prepare_clean_release.py` - Archive/delete non-essential files
- `tools/audit_dependencies.py` - Identify unused dependencies  
- `tools/verify_clean_installation.py` - Verify clean state
- `RELEASE_CHECKLIST.md` - Complete pre-release checklist

✅ **Dependencies optimized:**
- Core runtime: 9 packages (down from 19)
- Optional dev/full packages moved to pyproject.toml

## Quick Start: Clean Release Process

### Step 1: Preview Changes
```bash
python tools/prepare_clean_release.py --dry-run
```

This will archive **~274 MB** of development files:
- 10 directories (ai_logs, archive, artifacts, etc.)
- 22,673 generated files (.db, .pyc, __pycache__, etc.)
- 12 optional modules flagged for review

### Step 2: Execute Cleanup
```bash
python tools/prepare_clean_release.py --execute
```

**What happens:**
- Archives to `_internal_archive_YYYYMMDD_HHMMSS/`
- Removes all archived directories from working tree
- Deletes all generated artifacts (.db, .pyc, cache)
- Preserves all essential core files

### Step 3: Review Optional Modules

Decide whether to keep these modules (used by advanced features):

**Background Jobs System:**
- `personal_agent/background_jobs.py`
- `personal_agent/jobs_db.py`
- `personal_agent/jobs_worker.py`
- `crt_background_worker.py`

**Active Learning:**
- `personal_agent/active_learning.py`
- `personal_agent/training_loop.py`

**Research Mode:**
- `personal_agent/researcher.py`
- `personal_agent/research_engine.py`

**Other:**
- `personal_agent/idle_scheduler.py`
- `personal_agent/onboarding.py`
- `personal_agent/proactive_triggers.py`
- `crt_apply_promotions.py`

**Recommendation:** Keep for v1.0 release, mark as "beta" features in docs.

### Step 4: Verify Clean Installation
```bash
python tools/verify_clean_installation.py
```

Must pass all checks:
- ✓ Critical files present
- ✓ Python imports work
- ✓ No unwanted artifacts

### Step 5: Test Functionality
```bash
# Run test suite
pytest tests/ -v

# Run stress test
python tools/crt_stress_test.py --turns 10 --print-every 1
```

### Step 6: Security Scan
```bash
# Check for secrets
git log --all --source -- "*password*" "*secret*" "*token*"

# Check for hardcoded paths
grep -r "D:\\\\" --exclude-dir=.git --exclude-dir=.venv
```

### Step 7: Create Release Branch
```bash
git checkout -b release/v1.0
git add .
git commit -m "chore: prepare v1.0 release - clean production-ready code"
git push origin release/v1.0
```

### Step 8: Tag Release
```bash
git tag -a v1.0.0 -m "Initial public release"
git push origin v1.0.0
```

### Step 9: Make Public
1. Go to GitHub Settings
2. Danger Zone → Change visibility
3. Select "Make public"
4. Confirm

---

## What Gets Removed

### Archived (274 MB):
```
ai_logs/                    # Internal session logs
archive/                    # Legacy code (124 MB)
artifacts/                  # Stress test outputs (144 MB)
contradiction_stress_test_output/
stress_test_evidence/
test_results/
experiments/
user_research/
roadmap/
.github/prompts/
```

### Deleted (generated at runtime):
```
**/*.db                     # SQLite databases (597 files)
**/*.db-shm, *.db-wal       # SQLite temp files
**/__pycache__              # Python cache (2,657 dirs)
**/*.pyc                    # Compiled Python (19,361 files)
.venv/                      # Virtual environment
.vscode/                    # VS Code settings
```

---

## What Stays (Core System)

### Essential Runtime (~50 files, ~25 MB)
```
personal_agent/
├── crt_rag.py              # Main orchestrator
├── crt_core.py             # Core memory engine
├── crt_memory.py           # Storage layer
├── crt_ledger.py           # Contradiction ledger
├── embeddings.py           # Embedding utilities
├── ollama_client.py        # LLM client
├── fact_slots.py           # Fact extraction
├── two_tier_facts.py       # Fact system
├── ml_contradiction_detector.py
├── runtime_config.py
└── disclosure_policy.py

groundcheck/                # Verification system
sse/                        # Event framework
crt_api.py                  # FastAPI server
tests/                      # Test suite
tools/crt_stress_test.py    # Harness
```

### Documentation
```
README.md
LICENSE (MIT)
CONTRIBUTING.md
CODE_OF_CONDUCT.md
SECURITY.md
QUICKSTART.md
KNOWN_LIMITATIONS.md
RELEASE_CHECKLIST.md
```

### Config & Build
```
requirements.txt            # Core deps only
pyproject.toml             # Full packaging
setup.py
pytest.ini
.gitignore
Dockerfile
```

---

## Post-Release

### Immediate Tasks
1. Create GitHub Release with changelog
2. Enable Issues & Discussions
3. Set up branch protection (require PR reviews)
4. Add CI status badges to README

### Announcement
- [ ] Post to /r/MachineLearning
- [ ] Post to /r/LocalLLaMA  
- [ ] Share on Twitter/X
- [ ] Submit to Hacker News (Show HN)
- [ ] Update personal website/blog

### Monitoring
- Watch for first issues
- Respond to questions within 24h
- Review PRs promptly
- Update docs based on feedback

---

## Emergency Rollback

If critical issues discovered:

```bash
# 1. Make private immediately
# GitHub Settings → Make private

# 2. Fix in private
git revert HEAD
git commit -m "fix: critical security issue"

# 3. Re-test
pytest tests/
python tools/verify_clean_installation.py

# 4. Re-publish when ready
```

---

## File Size Summary

| Category | Size | Files |
|----------|------|-------|
| **Archive** | 274 MB | ~10 dirs |
| **Delete** | ~50 MB | 22,673 files |
| **Keep** | ~25 MB | ~200 files |
| **Final Clean Repo** | **~25 MB** | **~200 files** |

---

## Next Steps

1. ✅ Dependencies optimized (9 core packages)
2. ✅ Cleanup tools created
3. ⏭️ **Run cleanup:** `python tools/prepare_clean_release.py --execute`
4. ⏭️ **Review optional modules:** Keep or remove?
5. ⏭️ **Verify:** `python tools/verify_clean_installation.py`
6. ⏭️ **Test:** `pytest tests/ && python tools/crt_stress_test.py --turns 10`
7. ⏭️ **Security scan:** Check for secrets/hardcoded paths
8. ⏭️ **Tag & publish:** See Step 7-9 above

---

**Ready to proceed?** Start with Step 1 (dry-run) to preview changes.

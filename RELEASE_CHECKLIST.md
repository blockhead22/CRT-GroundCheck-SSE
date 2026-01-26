# Clean Release Checklist

Use this checklist before publishing the repository.

## Pre-Release Cleanup

### 1. Archive Development Files
```bash
python tools/prepare_clean_release.py --dry-run
python tools/prepare_clean_release.py --execute
```

**Removes:**
- `ai_logs/` - Internal session logs
- `archive/` - Legacy code
- `artifacts/` - Stress test outputs
- `roadmap/` - Planning documents
- `user_research/` - Research notes
- All `.db` files (regenerated at runtime)
- `__pycache__/`, `.pytest_cache/`

### 2. Audit Dependencies
```bash
python tools/audit_dependencies.py
```

**Action:** Review unused dependencies and update `requirements.txt`

### 3. Remove Optional Modules (If Not Needed)

Review and optionally remove:
- [ ] `personal_agent/active_learning.py` - Active learning system
- [ ] `personal_agent/background_jobs.py` - Background job system
- [ ] `personal_agent/jobs_db.py` - Job queue database
- [ ] `personal_agent/training_loop.py` - Training pipeline
- [ ] `personal_agent/researcher.py` - Research mode
- [ ] `crt_background_worker.py` - Background worker

**Decision:** Keep if used by your deployment, remove if not needed.

### 4. Verify Clean Installation
```bash
python tools/verify_clean_installation.py
```

**Must pass:** All critical files present, imports work, no unwanted artifacts.

### 5. Test Core Functionality
```bash
# Run test suite
pytest tests/ -v

# Run stress test
python tools/crt_stress_test.py --turns 10 --print-every 1
```

**Must pass:** All tests green, stress test completes without errors.

---

## Documentation Review

### 6. Update README.md
- [ ] Remove internal references
- [ ] Verify quickstart works
- [ ] Update badges (if adding CI status badges)
- [ ] Check all example code runs

### 7. Review QUICKSTART.md
- [ ] Installation steps accurate
- [ ] Examples tested
- [ ] API endpoints documented

### 8. Check KNOWN_LIMITATIONS.md
- [ ] Current limitations listed
- [ ] Future work outlined
- [ ] No internal roadmap items

---

## Security & Compliance

### 9. Secret Scan
```bash
# Scan for potential secrets
git log --all --full-history --source -- "*password*" "*secret*" "*token*" "*key*"

# Check for hardcoded URLs/paths
grep -r "127.0.0.1" --exclude-dir=.git --exclude-dir=.venv
grep -r "localhost" --exclude-dir=.git --exclude-dir=.venv
grep -r "D:\\" --exclude-dir=.git --exclude-dir=.venv
```

**Action:** Remove any hardcoded secrets, internal URLs, or absolute paths.

### 10. License Headers
- [ ] LICENSE file present (MIT)
- [ ] No conflicting licenses in dependencies
- [ ] Attribution for third-party code

---

## Git & GitHub

### 11. Clean Git History
```bash
# Check for large files
git rev-list --objects --all | \
  git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | \
  awk '/^blob/ {print substr($0,6)}' | sort -n -k2 | tail -20

# Optionally squash/rebase if needed
git rebase -i HEAD~10
```

### 12. Create Release Branch
```bash
git checkout -b release/v1.0
git push origin release/v1.0
```

### 13. Tag Release
```bash
git tag -a v1.0.0 -m "Initial public release"
git push origin v1.0.0
```

---

## Publication

### 14. GitHub Settings
- [ ] Repository description updated
- [ ] Topics/tags added (ai, memory, contradiction-detection, llm, rag)
- [ ] Default branch set to `main`
- [ ] Branch protection enabled (require PR reviews)
- [ ] Issues enabled
- [ ] Discussions enabled (optional)

### 15. Make Repository Public
**GitHub Settings → Danger Zone → Change visibility → Make public**

### 16. Post-Publication
- [ ] Create initial GitHub Release with changelog
- [ ] Post announcement (Twitter, Reddit, Hacker News, etc.)
- [ ] Monitor issues and PRs
- [ ] Update documentation based on feedback

---

## Verification Checklist

Before going public, verify:
- [x] All tests pass
- [x] Documentation is complete
- [x] No secrets in code or history
- [x] LICENSE file present
- [x] CONTRIBUTING.md clear
- [x] README has quickstart
- [x] Dependencies audited
- [x] No internal artifacts
- [x] Stress test runs successfully
- [x] API server starts cleanly

---

## Emergency Rollback

If issues are discovered after publication:

```bash
# Make private immediately
# GitHub Settings → Danger Zone → Make private

# Fix issues in private repo
git commit -m "fix: critical issue"

# Re-test
pytest tests/
python tools/verify_clean_installation.py

# Re-publish when ready
```

---

**Last Updated:** 2026-01-25

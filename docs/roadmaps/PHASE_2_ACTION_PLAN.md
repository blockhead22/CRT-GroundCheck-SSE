# Phase 2 Action Plan - Production Hardening & Phase 3 Preparation

**Date:** January 22, 2026  
**Status:** Active  
**Priority:** Complete Phase 1 gaps, then formalize Phase 3

---

## Context

Per the PROJECT_ASSESSMENT_JAN_22_2026.md analysis:
- ✅ Phase 1 (Data Collection) is functionally complete
- ✅ Phase 2 (Build Benchmark) is complete
- ⚠️ Phase 1 has known gaps: PII anonymization, data retention policy
- 🔄 Phase 3 (Experiments) is mostly done but needs formalization

**Original Phase 2 Plan Said:**
```
Phase 2: Query→Slot Learning
- Train ML classifier (needs 1000+ interactions collected first)
- Production Hardening: Add PII anonymization, data retention policy
```

**What We Actually Did:**
- Built groundcheck library + groundingbench dataset (following Master Plan instead)
- Skipped the production hardening items

**This Plan:** Address the production hardening gaps, then move forward.

---

## Immediate Tasks (This Week)

### Task 1: Add PII Anonymization

**Why:** Phase 1 logs user queries/responses as-is. Need basic anonymization for privacy.

**Implementation:**
1. Create `personal_agent/pii_anonymization.py`
2. Add regex patterns for:
   - Email addresses → `[EMAIL_REDACTED]`
   - Phone numbers → `[PHONE_REDACTED]`
   - SSN patterns → `[SSN_REDACTED]`
   - Credit card numbers → `[CC_REDACTED]`
3. Add optional anonymization to interaction logging
4. Add flag: `ANONYMIZE_PII = True` (default: True)
5. Add tests for anonymization patterns

**Files to Modify:**
- `personal_agent/active_learning.py` (add anonymization call in `record_interaction()`)
- Create `personal_agent/pii_anonymization.py`
- Add tests in `tests/test_pii_anonymization.py`

**Success Criteria:**
- ✅ Email, phone, SSN patterns masked in logs
- ✅ Configurable via runtime config
- ✅ Tests passing for all PII patterns
- ✅ No false positives on normal text

**Estimated Time:** 3-4 hours

---

### Task 2: Add Data Retention Policy

**Why:** Logs currently stored indefinitely. Need automatic cleanup for compliance.

**Implementation:**
1. Add retention configuration to `crt_runtime_config.json`:
   ```json
   "active_learning": {
     "retention_days": 90,
     "enable_auto_purge": true
   }
   ```
2. Add method to `ActiveLearningCoordinator`:
   ```python
   def purge_old_interactions(self, days: int = 90):
       """Delete interactions older than specified days."""
   ```
3. Add API endpoint:
   ```python
   @app.post("/api/admin/purge")
   def purge_old_data(days: int = 90):
       """Manually trigger data purge."""
   ```
4. Add background job for automatic purging (optional)
5. Add tests for purging logic

**Files to Modify:**
- `personal_agent/active_learning.py` (add `purge_old_interactions()` method)
- `crt_api.py` (add `/api/admin/purge` endpoint)
- `crt_runtime_config.json` (add retention config)
- Add tests in `tests/test_data_retention.py`

**Success Criteria:**
- ✅ Can purge interactions older than N days
- ✅ Purge preserves corrections for training (optional flag)
- ✅ Admin endpoint works
- ✅ Configurable via runtime config
- ✅ Tests passing for purge logic

**Estimated Time:** 2-3 hours

---

### Task 3: Update Phase 1 Documentation

**Why:** Mark Phase 1 as fully complete after addressing gaps.

**Implementation:**
1. Update `PHASE1_SUMMARY.md`:
   - Remove "Known Limitations" warnings for PII and retention
   - Add "Production Hardening Complete" section
   - Update status to "✅ COMPLETE (Production-Ready)"
2. Update `docs/PHASE1_DATA_COLLECTION.md`:
   - Add PII anonymization documentation
   - Add data retention policy documentation
   - Add configuration examples
3. Update README.md Active Learning section:
   - Mark Phase 1 as complete
   - Add "Production-Ready" badge

**Files to Modify:**
- `PHASE1_SUMMARY.md`
- `docs/PHASE1_DATA_COLLECTION.md`
- `README.md`

**Success Criteria:**
- ✅ Phase 1 marked as production-ready
- ✅ PII anonymization documented
- ✅ Data retention documented
- ✅ Configuration examples provided

**Estimated Time:** 1 hour

---

### Task 4: Formalize Phase 3 Experiments

**Why:** Experiments already exist (baselines compared), but need formal documentation.

**Implementation:**
1. Create `PHASE3_EXPERIMENTS_SUMMARY.md`:
   - Document baseline comparisons (SelfCheckGPT, CoVe, Vanilla RAG)
   - Create results tables (precision, recall, F1, latency)
   - Add performance graphs (if available)
   - Document ablation studies
2. Update `groundingbench/README.md`:
   - Add "Baseline Comparison" section
   - Link to experimental results
3. Create `groundingbench/results/` directory:
   - Add CSV files with raw results
   - Add graphs/plots (if available)

**Files to Create:**
- `PHASE3_EXPERIMENTS_SUMMARY.md`
- `groundingbench/results/baseline_comparison.csv`
- `groundingbench/results/ablation_studies.csv`

**Files to Modify:**
- `groundingbench/README.md` (add baseline comparison section)

**Success Criteria:**
- ✅ Baseline comparison documented
- ✅ Results tables created (precision, recall, F1)
- ✅ Latency benchmarks included
- ✅ Ablation studies documented

**Estimated Time:** 4-5 hours

---

## Checklist Summary

### Week 3 Tasks (This Week)

- [ ] **Task 1: PII Anonymization** (3-4 hours)
  - [ ] Create `personal_agent/pii_anonymization.py`
  - [ ] Add regex patterns for email, phone, SSN, CC
  - [ ] Integrate into `active_learning.py`
  - [ ] Add configuration flag
  - [ ] Write tests

- [ ] **Task 2: Data Retention Policy** (2-3 hours)
  - [ ] Add `purge_old_interactions()` method
  - [ ] Add `/api/admin/purge` endpoint
  - [ ] Add retention config to `crt_runtime_config.json`
  - [ ] Write tests

- [ ] **Task 3: Update Documentation** (1 hour)
  - [ ] Update `PHASE1_SUMMARY.md` (mark production-ready)
  - [ ] Update `docs/PHASE1_DATA_COLLECTION.md`
  - [ ] Update `README.md` Active Learning section

- [ ] **Task 4: Formalize Phase 3** (4-5 hours)
  - [ ] Create `PHASE3_EXPERIMENTS_SUMMARY.md`
  - [ ] Document baseline comparisons
  - [ ] Create results tables (CSV files)
  - [ ] Update `groundingbench/README.md`

**Total Estimated Time:** 10-13 hours (1.5-2 days)

---

## What Happens After This

Once these tasks are complete:

### Phase 1 Status
✅ **COMPLETE and Production-Ready**
- All data collection infrastructure working
- PII anonymization implemented
- Data retention policy in place
- Fully documented

### Phase 2 Status
✅ **COMPLETE**
- groundcheck library built
- groundingbench dataset created
- 76% accuracy achieved
- Contradiction-aware features added

### Phase 3 Status
✅ **COMPLETE**
- Baseline comparisons documented
- Results formalized
- Ready for paper writing

### Next: Phase 4 (Write Paper)

With Phases 1-3 complete, move to Phase 4:
1. Outline 8-page research paper (ICLR/NeurIPS format)
2. Draft introduction, related work, method, experiments
3. Get 2 reviewers to read
4. Submit to arXiv
5. Submit to conference workshop

**Target:** End of Week 7 (mid-February 2026)

---

## Implementation Notes

### PII Anonymization Implementation

**Simple Approach (Recommended):**
```python
import re

PII_PATTERNS = {
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'phone': r'\b(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b',
    'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
    'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'
}

def anonymize_text(text: str, enabled: bool = True) -> str:
    if not enabled:
        return text
    
    result = text
    for pattern_name, pattern in PII_PATTERNS.items():
        replacement = f"[{pattern_name.upper()}_REDACTED]"
        result = re.sub(pattern, replacement, result)
    
    return result
```

**Usage in active_learning.py:**
```python
from personal_agent.pii_anonymization import anonymize_text

def record_interaction(self, query: str, response: str, ...):
    # Anonymize before storing
    query_safe = anonymize_text(query)
    response_safe = anonymize_text(response)
    
    # Store anonymized versions
    cursor.execute("""
        INSERT INTO interaction_logs (query, response, ...)
        VALUES (?, ?, ...)
    """, (query_safe, response_safe, ...))
```

### Data Retention Implementation

**Simple Approach (Recommended):**
```python
def purge_old_interactions(self, days: int = 90, preserve_corrections: bool = True):
    """Delete interactions older than specified days."""
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    
    # Calculate cutoff timestamp
    cutoff = time.time() - (days * 24 * 60 * 60)
    
    if preserve_corrections:
        # Only delete interactions without corrections
        cursor.execute("""
            DELETE FROM interaction_logs 
            WHERE created_at < ? 
            AND interaction_id NOT IN (
                SELECT DISTINCT interaction_id FROM corrections
            )
        """, (cutoff,))
    else:
        # Delete all old interactions
        cursor.execute("""
            DELETE FROM interaction_logs 
            WHERE created_at < ?
        """, (cutoff,))
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    return deleted_count
```

**API Endpoint:**
```python
@app.post("/api/admin/purge")
def purge_old_data(days: int = 90, preserve_corrections: bool = True):
    """Manually trigger data purge."""
    try:
        count = active_learning_coordinator.purge_old_interactions(
            days=days, 
            preserve_corrections=preserve_corrections
        )
        return {
            "success": True,
            "deleted_count": count,
            "message": f"Purged {count} interactions older than {days} days"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

---

## Success Metrics

After completing this plan:

✅ **Phase 1 Production-Ready:**
- PII anonymization working (email, phone, SSN, CC masked)
- Data retention policy implemented (90-day default)
- Configurable via runtime config
- Fully documented

✅ **Phase 3 Formalized:**
- Baseline comparisons documented
- Results tables created
- Ready for inclusion in research paper

✅ **Ready for Phase 4:**
- All experimental work complete
- Can start writing paper immediately
- Have all data needed for publication

---

## Questions & Considerations

### Question 1: Should we also add PII anonymization to groundcheck?

**Answer:** No, not needed for now.
- groundcheck is a library, not a service
- Users control what data they pass to it
- Can add later if publishing as a service (Phase 5)

### Question 2: Should we implement background auto-purge?

**Answer:** Optional, add if time permits.
- Manual `/api/admin/purge` endpoint is sufficient for now
- Can add cron job or background worker later
- Not critical for Phase 1 completion

### Question 3: Should we improve accuracy before formalizing Phase 3?

**Answer:** No, formalize first, then improve.
- 76% is competitive enough for workshop paper
- Can improve to 80%+ in Week 4
- Better to have documented baseline first

### Question 4: Master Plan vs Implementation Roadmap - which to follow?

**Answer:** Stick with Master Plan (research path).
- You've already committed to research artifacts
- groundcheck/groundingbench are research-oriented
- Implementation Roadmap is enterprise CRT (different goal)
- Can revisit Implementation Roadmap later if needed

---

## Timeline

**Week 3 (Jan 22-28):**
- Days 1-2: PII anonymization + data retention (Tasks 1-2)
- Day 3: Update documentation (Task 3)
- Days 4-5: Formalize Phase 3 experiments (Task 4)

**Week 4 (Jan 29 - Feb 4):**
- Improve accuracy (76% → 80%+)
- Expand dataset (500 → 700-1000 examples)
- Prepare for Phase 4 (paper outline)

**Week 5-7 (Feb 5-25):**
- Write 8-page research paper
- Get reviewers
- Submit to arXiv + workshop

---

**Created:** January 22, 2026  
**Status:** Ready to Execute  
**Next Review:** January 28, 2026 (after Week 3 tasks complete)

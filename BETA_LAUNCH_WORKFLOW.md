# Beta Launch Workflow - CRT v0.9

**Target**: First public beta release  
**Date**: 2026-01-20  
**Status**: Ready pending blocker fixes

---

## 🎯 What This Beta Offers

### Core Value Proposition
**Evidence-first memory with contradiction tracking**

Users can:
- Store conversational facts with trust/confidence metadata
- Retrieve information weighted by trust, not just similarity  
- See detected contradictions explicitly
- Inspect memory and contradiction ledger via API
- Use multiple interfaces (web, CLI, API)

### What's Beta vs Stable
- ✅ **Stable**: Core memory, retrieval, contradiction detection (10/10 in stress tests)
- ⚠️ **Beta**: Truth reintroduction after contradictions, synthesis query retrieval
- 🔬 **Experimental**: Gate tuning, ML classification (if included)

---

## 📋 Pre-Launch Checklist

### Phase 1: Critical Fixes (2 hours)
**Must complete before announcement**

- [ ] **Remove debug prints** → logging  
  - File: `personal_agent/crt_rag.py`
  - Guide: [DEBUG_PRINT_REMOVAL_GUIDE.md](DEBUG_PRINT_REMOVAL_GUIDE.md)
  - Time: 30 minutes
  - Verify: `grep -n 'print.*CRT_DEBUG' personal_agent/crt_rag.py` returns nothing

- [ ] **Add configuration files**
  - ✅ `.env.example` (already created)
  - [ ] `.gitignore` - verify .env is excluded
  - ✅ `LICENSE` (already created - MIT)
  - Time: 15 minutes

- [ ] **Create documentation**
  - ✅ `KNOWN_LIMITATIONS.md` (already created)
  - ✅ `QUICKSTART.md` (already created)
  - ✅ `BETA_RELEASE_CHECKLIST.md` (already created)
  - Time: Already done

- [ ] **Verification run**
  - [ ] Run: `python tools/adaptive_stress_test.py beta_final 70 80`
  - [ ] Check report shows 10+ contradictions
  - [ ] No debug spam in console
  - [ ] API responds correctly
  - Time: 20 minutes

**Total Phase 1**: ~1 hour 5 minutes

---

### Phase 2: Quality Polish (Optional, 2 hours)
**Nice to have before announcement**

- [ ] **Fix contradiction ledger details in reports**
  - Issue: Reports show "N/A" instead of claim text
  - File: `tools/adaptive_stress_test.py` line ~520
  - Fix: Populate claim_a_text and claim_b_text from API response
  - Time: 30 minutes

- [ ] **Add demo reset script**
  - Script: `scripts/reset_demo.py`
  - Purpose: Fresh thread with pre-loaded demo conversation
  - Time: 30 minutes

- [ ] **Enable FastAPI /docs endpoint**
  - Already auto-generated, just document it
  - Add to README: "API docs: http://127.0.0.1:8123/docs"
  - Time: 5 minutes

- [ ] **Create CONTRIBUTING.md**
  - How to report bugs
  - How to submit pull requests
  - Code style guidelines
  - Time: 30 minutes

---

### Phase 3: Deployment (Day 2-3)
**After initial testing**

- [ ] **Test installation from scratch**
  - Fresh Windows VM or WSL instance
  - Follow QUICKSTART.md exactly
  - Document any missing steps
  - Time: 1 hour

- [ ] **Create Docker setup** (optional)
  - `Dockerfile` for API server
  - `docker-compose.yml` for full stack
  - Test on clean system
  - Time: 2-3 hours

- [ ] **Set up staging environment**
  - Deploy to cloud instance
  - Test with 5-10 internal users
  - Collect feedback
  - Time: Variable

---

## 🚀 Launch Sequence

### Day 1: Fix Blockers
**Morning** (2 hours):
1. Remove debug prints (30 min)
2. Verify .gitignore excludes .env (5 min)
3. Run final stress test (20 min)
4. Fix any new issues found (1 hour buffer)

**Afternoon** (2 hours):
5. Test fresh install on clean system (1 hour)
6. Write announcement draft (30 min)
7. Prepare demo video/screenshots (30 min)

### Day 2: Soft Launch
**Morning** (1 hour):
8. Tag release: `git tag v0.9-beta`
9. Push to GitHub: `git push origin v0.9-beta`
10. Create GitHub release with KNOWN_LIMITATIONS.md

**Afternoon** (ongoing):
11. Share with 5-10 trusted beta testers
12. Monitor feedback channels
13. Fix critical bugs immediately

### Day 3-7: Iterate
14. Collect feedback, track issues
15. Release v0.9.1-beta with fixes
16. Expand to 20-30 testers

### Week 2: Public Announcement
17. Write blog post / announcement
18. Share on relevant communities (if appropriate)
19. Monitor for issues, respond quickly

---

## 📊 Success Metrics

### Week 1 Goals
- [ ] 5+ beta testers actively using it
- [ ] No critical crashes reported
- [ ] Contradiction detection working in real conversations
- [ ] At least 1 piece of positive feedback

### Week 2 Goals
- [ ] 20+ beta testers
- [ ] 10+ GitHub stars (if public)
- [ ] Truth reintroduction issue understood and tracked
- [ ] At least 3 feature requests collected

### Month 1 Goals
- [ ] 50+ beta testers
- [ ] Truth reintroduction fixed (v1.0)
- [ ] 5+ contributions from community
- [ ] Plan for production release

---

## 🎬 Demo Script for Testers

Send this to beta testers:

```markdown
# CRT Beta Demo (5 minutes)

1. Install and start (see QUICKSTART.md)

2. Paste these facts one at a time:
   - My name is Jordan Chen.
   - I work at DataCore as a data scientist.
   - My favorite language is Rust.
   - I live in Austin, Texas.
   - I have a golden retriever named Murphy.

3. Now contradict yourself:
   - Actually, my name is Alex Chen.
   - I should clarify - I work at Vertex Analytics.

4. Ask about the contradictions:
   - What's my name?
   - Where do I work?
   - List all contradictions you've detected.

5. Check the API:
   curl "http://127.0.0.1:8123/api/contradictions?thread_id=default"

Expected: System detects contradictions and asks for clarification or notes them explicitly.
```

---

## 🐛 Issue Response Protocol

### Critical (Fix within 24 hours)
- System crashes
- Data loss
- Security vulnerabilities
- Cannot install/start

### High Priority (Fix within week)
- Contradiction detection broken
- API returns errors
- Memory not persisting
- Performance issues

### Medium Priority (Fix in next release)
- Truth reintroduction issues
- UI/UX improvements
- Documentation gaps
- Feature requests

### Low Priority (Backlog)
- Nice-to-have features
- Edge cases
- Performance optimizations
- Code refactoring

---

## 📢 Announcement Template

```markdown
# CRT Beta - Evidence-First Memory for Conversational AI

We're releasing the first public beta of CRT, a memory system designed for long-horizon coherence in conversational AI.

## What It Does
- Stores conversational facts with explicit trust and confidence tracking
- Detects contradictions and surfaces them (no silent overwrites)
- Retrieves information weighted by trust, not just similarity
- Exposes memory and contradiction ledger via REST API

## What's Working (Evidence-Based)
✅ 10/10 contradiction detection in stress tests
✅ Trust-weighted retrieval formula
✅ 100 turn conversations tested
✅ REST API, Web UI, CLI interfaces
✅ SQLite-backed persistence

## What's Beta
⚠️ Truth reintroduction after contradictions needs improvement
⚠️ Some synthesis queries need better retrieval tuning
⚠️ Gate thresholds being tuned based on real usage

## Try It
- Quickstart: [QUICKSTART.md](link)
- Known Issues: [KNOWN_LIMITATIONS.md](link)
- GitHub: [link]

## We Need
- Real conversation testing
- Edge case discovery
- Feedback on UX
- Feature requests

This is beta software. See KNOWN_LIMITATIONS.md for details.
```

---

## 🔒 What NOT to Claim

❌ "Production-ready for all use cases"  
❌ "100% accurate contradiction detection"  
❌ "Solves hallucination problem"  
❌ Specific accuracy percentages without recent evidence  
❌ "Fully automated conflict resolution"  

✅ "Evidence-based memory tracking"  
✅ "Contradiction detection and surfacing"  
✅ "Designed for long-horizon coherence"  
✅ "Beta quality - core works, rough edges expected"  

---

## ✅ Ready to Ship When...

- [ ] Debug prints removed
- [ ] Final stress test shows 10/10 contradictions
- [ ] QUICKSTART.md tested on fresh system
- [ ] KNOWN_LIMITATIONS.md reviewed
- [ ] LICENSE added
- [ ] No console spam during normal operation
- [ ] 2+ people reviewed announcement

---

**Current Status**: Phase 1 (Critical Fixes) in progress  
**Next Action**: Remove debug prints per DEBUG_PRINT_REMOVAL_GUIDE.md  
**Estimated Launch**: 2-3 days if blockers fixed today

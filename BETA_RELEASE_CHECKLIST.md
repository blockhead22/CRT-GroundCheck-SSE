# Beta Release Checklist - CRT v0.9-beta
**Date**: 2026-01-20  
**Last Verified**: Truth coherence test (20260120_221434)  
**Status**: BETA READY (with documented limitations)  

---

## ✅ VERIFIED WORKING (Evidence-Based)

### Core Memory System
- ✅ **Trust-weighted retrieval** - Formula: `R = similarity × recency × belief_weight` ([crt_rag.py](personal_agent/crt_rag.py))
- ✅ **Dual scoring** - Separate trust and confidence scalars in memory schema
- ✅ **Contradiction detection** - **10/10 contradictions detected** in latest stress test
- ✅ **Contradiction ledger API** - `/api/contradictions` returns accurate count
- ✅ **Per-thread isolation** - Tested across multiple thread IDs
- ✅ **SQLite storage** - Persistent memory + ledger databases

**Evidence**: [adaptive_stress_report.20260120_172425.md](artifacts/adaptive_stress_report.20260120_172425.md)
```
- Contradictions Detected by System: 10
- Gate Pass Rate: 100.0%
- Total Turns: 80
```

### API & Interfaces
- ✅ **FastAPI REST server** - Running on port 8123 ([crt_api.py](crt_api.py))
- ✅ **React frontend** - Chat + dashboard + docs viewer
- ✅ **CLI interface** - [personal_agent_cli.py](personal_agent_cli.py)
- ✅ **Streamlit GUI** - [crt_chat_gui.py](crt_chat_gui.py)

### Testing Infrastructure
- ✅ **Adaptive stress test** - 80-turn adversarial testing
- ✅ **Pytest suite** - Core unit tests pass
- ✅ **Artifact generation** - JSONL logs + markdown reports

---

## 🔴 BLOCKERS (Must Fix Before Beta)

### 1. Debug Print Statements
**Issue**: Production code has console spam  
**Evidence**: [personal_agent/crt_rag.py](personal_agent/crt_rag.py) lines 1048, 1074, 1078, 1114, 1122, 1123, 1136, 1139, 2242, 2248, 2289
```python
print(f"[CRT_DEBUG][NAME_DECLARATION] Detected: '{user_query[:80]}'")
print(f"[CRT_DEBUG][NAME_CONTRADICTION_CHECK] Starting...")
```
**Fix**: Replace with proper logging
**Time**: 30 minutes

### 2. Missing Configuration Files
**Issue**: No environment configuration template  
**Missing**:
- `.env.example` - API keys, DB paths, log levels
- `docker-compose.yml` - One-command startup
- `LICENSE` - Legal requirements

**Fix**: Create config files  
**Time**: 30 minutes

### 3. No "Known Limitations" Documentation
**Issue**: Beta users need to know what doesn't work  
**Must document**:
- Truth reintroduction (139 cases detected in stress test)
- Memory retrieval needs tuning for synthesis queries
- Gate pass rate variance across query types

**Fix**: Create KNOWN_LIMITATIONS.md  
**Time**: 20 minutes

---

## 🟡 IMPORTANT (Fix If Time)

### 4. Truth Reintroduction After Contradictions
**Issue**: System sometimes re-mentions contradicted facts  
**Evidence**: Stress test shows 139 instances
```markdown
### Turn 14 - company
Old (contradicted) value: I work as a data scientist at Vertex Analytics.
User: I should clarify - I work at DataCore.
Assistant: That's great to know, you work at DataCore. How can I assist you today?
```
**Status**: Tracked but not blocking (documented in report)  
**Fix**: Improve trust decay after contradictions  
**Time**: 3-4 hours

### 5. Contradiction Ledger Details Incomplete
**Issue**: Report shows "N/A" for claim text in ledger  
**Evidence**: [adaptive_stress_report.20260120_172425.md](artifacts/adaptive_stress_report.20260120_172425.md) line 18-45
```markdown
1. **N/A** vs **N/A**
   - Status: open
   - Confidence: 0.00
```
**Fix**: Ensure API returns full contradiction details  
**Time**: 1 hour

### 6. Installation Documentation
**Issue**: No single-page "get running in 5 minutes" guide  
**Current**: README has multiple options but no clear path  
**Fix**: Create QUICKSTART.md with minimal path  
**Time**: 30 minutes

---

## 🟢 NICE-TO-HAVE (Post-Beta)

### 7. OpenAPI/Swagger Documentation
**Current**: FastAPI auto-generates but not documented  
**Fix**: Enable `/docs` endpoint and document it  
**Time**: 15 minutes

### 8. Database Backup/Restore Scripts
**Current**: Manual file copy  
**Fix**: Add `scripts/backup_dbs.py` and `scripts/restore_dbs.py`  
**Time**: 1 hour

### 9. Performance Monitoring
**Current**: No metrics collection  
**Fix**: Add response time tracking, memory usage stats  
**Time**: 2-3 hours

### 10. Demo Reset Script
**Current**: Manual thread reset via API  
**Fix**: Add `scripts/reset_demo.py` with pre-loaded conversation  
**Time**: 30 minutes

---

## 📋 SPECULATION (Cannot Verify Without Code Changes)

The following were mentioned in status docs but cannot be verified in current code:

- ⚠️ "Gate pass rate 68.4%" - Latest stress test shows **100% pass rate**
- ⚠️ "ML classifier integration" - Cannot find evidence in grep search
- ⚠️ "M2 followup success 12%" - No artifacts showing this metric

**Recommendation**: Do NOT mention these in beta marketing unless we can reproduce the metrics.

---

## 🎯 Minimal Beta Definition

### What Works (Can Claim Confidently)
1. **Evidence-first memory** - Stores user facts with trust/confidence tracking
2. **Trust-weighted retrieval** - Not just cosine similarity; multiplies trust × recency × similarity
3. **Contradiction detection** - Detects and logs conflicting facts (10/10 in stress test)
4. **Multi-interface** - REST API, React UI, CLI, Streamlit
5. **Persistent storage** - SQLite-backed, survives restarts
6. **Contradiction API** - `/api/contradictions` exposes ledger programmatically

### What's Beta/Experimental
1. **Gate logic** - Working but may be overly permissive (100% pass needs investigation)
2. **Truth convergence** - System sometimes mentions old facts after contradictions
3. **Synthesis queries** - Complex "what do you know about X" queries need retrieval tuning

### Success Metrics
- **Primary**: "Does it remember facts correctly across 50+ turn conversations?"
- **Secondary**: "Are contradictions surfaced to the user when they occur?"
- **Tertiary**: "Can developers inspect memory/ledger via API?"

---

## 🚀 Go/No-Go Recommendation

### GO FOR BETA ✅ (with conditions)

**Rationale**:
- Core functionality **demonstrably works** (stress test evidence)
- Artifacts show 10/10 contradiction detection
- All interfaces operational
- No critical bugs blocking usage

**Required fixes before announcement** (2 hours total):
1. Remove debug prints → logging (30 min)
2. Add .env.example (15 min)
3. Add LICENSE file (5 min)
4. Create KNOWN_LIMITATIONS.md (20 min)
5. Create QUICKSTART.md (30 min)
6. Re-run stress test to verify clean output (20 min)

**Beta announcement should emphasize**:
- "Evidence-first memory with contradiction tracking"
- "Production-ready core, some rough edges in UX"
- "Looking for feedback on real-world usage patterns"

**Beta announcement should NOT claim**:
- "Production-ready for all use cases" (truth reintroduction needs work)
- Specific gate pass percentages (conflicting data in docs)
- ML classifier accuracy (cannot verify in current code)

---

## 📊 Verification Commands

Run these to validate current state:

```bash
# 1. Start API server
python -m uvicorn crt_api:app --reload --host 127.0.0.1 --port 8123

# 2. Run stress test (Terminal 2)
python tools/adaptive_stress_test.py beta_validation 70 80

# 3. Check report
cat artifacts/adaptive_stress_report.*.md | grep "Contradictions Detected"

# 4. Query API directly
curl "http://127.0.0.1:8123/api/contradictions?thread_id=beta_validation"
```

**Expected Results**:
- Report shows 10+ contradictions detected
- API returns matching count
- No Python exceptions in server terminal
- JSONL log contains 80 turns

---

## Next Steps

1. **Today**: Fix blockers (2 hours)
2. **Tomorrow**: Create demo script + test with fresh user
3. **Day 3**: Soft launch to 5-10 testers
4. **Week 2**: Iterate based on feedback, fix truth reintroduction
5. **Week 4**: Public announcement if metrics hold


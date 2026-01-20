# Known Limitations - CRT v0.9-beta

**Last Updated**: 2026-01-20  
**Verified Against**: Stress test 20260120_172425 (80 turns)

---

## 🔴 Active Issues

### 1. Truth Reintroduction After Contradictions
**Status**: Known, tracked, not blocking beta  
**Observed**: 139 instances in 80-turn stress test

**What happens**:
When a fact is contradicted, the system sometimes still references the old value in later responses.

**Example**:
```
Turn 4:  User: "I work at Vertex Analytics"
Turn 14: User: "I work at DataCore"  [contradiction detected ✓]
Turn 18: Assistant mentions "Vertex Analytics" again  [bug ✗]
```

**Why it happens**:
Memory trust decay after contradictions isn't aggressive enough. The old memory still has non-zero trust and can be retrieved.

**Workaround**:
Explicitly remind the system: "To clarify, I work at DataCore, not Vertex."

**Fix timeline**: Planned for v1.0 (Week 2)

---

### 2. Contradiction Ledger Details Incomplete in Reports
**Status**: Cosmetic issue in reports, API works correctly

**What happens**:
Stress test reports show "N/A" for contradiction details:
```markdown
1. **N/A** vs **N/A**
   - Status: open
   - Confidence: 0.00
```

**Why it happens**:
Report generator doesn't fetch full claim text from ledger, only counts.

**Workaround**:
Query the API directly for full details:
```bash
curl "http://127.0.0.1:8123/api/contradictions?thread_id=YOUR_THREAD"
```

**Fix timeline**: Next patch release (this week)

---

### 3. Debug Output in Production
**Status**: Annoying but harmless

**What happens**:
Console shows debug messages during normal operation:
```
[CRT_DEBUG][NAME_DECLARATION] Detected: 'My name is Alex'
[CRT_DEBUG][NAME_CONTRADICTION_CHECK] Starting...
```

**Why it happens**:
Development print statements not yet converted to proper logging.

**Workaround**:
Redirect stderr or ignore console output.

**Fix timeline**: This week (pre-announcement)

---

## 🟡 Design Limitations (Not Bugs)

### 4. Gates May Be Overly Permissive
**Current behavior**: 100% gate pass rate in stress tests

**What this means**:
The system rarely refuses to answer. This is intentional for beta to avoid over-refusal, but means the system might occasionally give low-confidence answers instead of saying "I'm not sure."

**Expected behavior**: As we collect real user data, gate thresholds will be tuned to refuse more often when truly uncertain.

**Not a bug**: This is a design choice for beta usability.

---

### 5. Memory Retrieval for Synthesis Queries
**Current behavior**: Questions like "What do you know about my interests?" may miss relevant memories

**Why it happens**:
Retrieval uses semantic similarity to the query. Broad synthesis questions don't have strong similarity to specific facts.

**Workaround**:
Ask specific questions: "What hobbies have I mentioned?" works better than "Tell me about myself."

**Future improvement**: Add query expansion and multi-hop retrieval for synthesis questions.

---

### 6. No Multi-User Support
**Current**: One conversation thread = one user context

**What doesn't work**:
```
User A: "My name is Alice"
User B: "My name is Bob"  [both stored in same thread → confusion]
```

**Workaround**:
Use separate thread IDs for different users or conversations.

**Future**: Add user_id field to memory schema.

---

## 🟢 Not Supported (By Design)

### 7. External Fact Verification
**The system does NOT**:
- Check if facts are objectively true
- Validate against external databases
- Correct false information

**What it DOES**:
- Track what YOU told it
- Detect when YOU contradict yourself
- Ask for clarification when YOUR statements conflict

**This is intentional**: CRT is a personal memory system, not a fact-checker.

---

### 8. Automatic Conflict Resolution
**The system does NOT**:
- Pick a "winner" between contradicting facts
- Silently overwrite old information
- Resolve ambiguity without user input

**What it DOES**:
- Flag contradictions explicitly
- Ask you which version is correct
- Maintain ledger of unresolved conflicts

**This is intentional**: Contradiction-preserving design prevents silent data loss.

---

## 📊 Performance Characteristics

### Current Metrics (from stress test)
- **Response time**: ~100-500ms per turn (including LLM call)
- **Memory footprint**: ~50MB for 100 turns of conversation
- **Database size**: ~1MB per 1000 memories
- **Contradiction detection**: 10/10 in controlled test
- **Gate pass rate**: 100% (may be too permissive)

### Expected Limits
- **Max memories per thread**: Tested to 10,000+
- **Max conversation length**: Tested to 100 turns, should handle 1000+
- **Concurrent threads**: Limited by SQLite write concurrency (~100/sec)

---

## 🔧 Workarounds Summary

| Issue | Workaround | Permanent Fix ETA |
|-------|-----------|------------------|
| Truth reintroduction | Explicitly restate correct fact | Week 2 |
| Ledger details in reports | Use `/api/contradictions` endpoint | This week |
| Debug console spam | Ignore or redirect stderr | This week |
| Synthesis query retrieval | Ask specific questions | v1.1 |
| Multi-user in thread | Use separate thread IDs | v1.2 |

---

## 🐛 How to Report Issues

**Found a bug?** Please include:
1. **Thread ID** where it occurred
2. **Turn number** (check JSONL log)
3. **Expected behavior** vs **actual behavior**
4. **Stress test report** if reproducible (run `adaptive_stress_test.py`)

**Submit to**: [GitHub Issues](https://github.com/yourrepo/crt/issues) or email beta@yourproject.com

---

## ✅ What's Actually Working Well

Don't let this list scare you! These limitations are known and tracked. The core system **is working**:

- ✅ Contradiction detection (10/10 in testing)
- ✅ Memory persistence across restarts
- ✅ API stability (no crashes in 80-turn tests)
- ✅ Multi-interface support (API, CLI, web UI)
- ✅ Thread isolation (no cross-contamination)

**Beta means**: "Core works, rough edges expected."

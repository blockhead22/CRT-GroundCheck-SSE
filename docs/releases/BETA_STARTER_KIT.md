# CRT v0.9-beta - Beta Starter Kit

**Release Date:** January 21, 2026  
**Version:** v0.9-beta  
**Purpose:** Controlled beta testing with 5 initial testers

---

## What's in This Release

### Core Features
1. **Memory with Contradiction Tracking**
   - Stores facts across conversations
   - Detects when new info conflicts with old
   - Trust scoring evolves based on reinforcement/correction

2. **Reintroduction Invariant (NEW in v0.9)**
   - Contradicted memories MUST be flagged (`reintroduced_claim: true`)
   - Answers using contradicted claims MUST include caveats
   - Zero tolerance: unflagged=0, uncaveated=0
   - **Example:** "Amazon (most recent update)" when Microsoft/Amazon conflict exists

3. **X-Ray Transparency**
   - See which memories were used to generate answer
   - View contradiction status for each memory
   - Audit metrics: `reintroduced_claims_count`

4. **Multi-Mode Responses**
   - Quick: Fast, high-confidence answers
   - Uncertainty: "I have conflicting information about..."
   - Reflection: Deep analysis when multiple contradictions exist

---

## Quick Start (5 Minutes)

### Prerequisites
**CRITICAL:** You MUST have Ollama installed and running, or you'll see error-mode responses.

1. **Install Ollama:** https://ollama.com/download
2. **Start Ollama:** `ollama serve` (in a terminal)
3. **Pull model:** `ollama pull llama3.2:latest`
4. **Verify:** `ollama list` (should show llama3.2)

**OR** accept graceful degradation:
- API will return `[Ollama error: ...]` messages
- Memory storage, contradiction detection, and flags still work
- But you won't see natural language answers

### Install & Run

```bash
# 1. Clone and setup
cd d:\AI_round2
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux

pip install -r requirements.txt

# 2. Start API server (Terminal 1)
python -m uvicorn crt_api:app --reload --host 127.0.0.1 --port 8123

# Wait for: "Uvicorn running on http://127.0.0.1:8123"

# 3. (Optional) Start Web UI (Terminal 2)
cd frontend
npm install
npm run dev

# Wait for: "Local:   http://localhost:5173/"
```

### Verify Installation

```bash
# Check API is responding
curl http://127.0.0.1:8123/api/dashboard/overview?thread_id=test

# Should return JSON with thread_id, session_id, etc.
```

---

## Demo Script (10 Minutes)

**Goal:** Prove contradiction detection + reintroduction flagging work correctly.

### Test Scenario

```bash
# Use thread: beta_demo_001
THREAD="beta_demo_001"

# 1. Introduce first fact
curl -X POST http://127.0.0.1:8123/api/chat/send \
  -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"message\":\"Hello, I'm Sarah. I work at Microsoft.\"}"

# Expected: "noted" or acknowledgment
# Check: metadata.reintroduced_claims_count should be 0

# 2. Create contradiction
curl -X POST http://127.0.0.1:8123/api/chat/send \
  -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"message\":\"Actually, I work at Amazon, not Microsoft.\"}"

# Expected: "noted" or acknowledgment
# Check: metadata.contradiction_detected should be true

# 3. Recall contradicted fact
curl -X POST http://127.0.0.1:8123/api/chat/send \
  -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"message\":\"Where do I work?\"}"

# CRITICAL CHECKS:
# ✅ Answer includes caveat: "Amazon (most recent update)"
# ✅ metadata.reintroduced_claims_count == 2
# ✅ xray.reintroduced_claims_count == 2
# ✅ xray.memories_used contains memories with reintroduced_claim=true
```

### PowerShell Version (Windows)

```powershell
$thread = "beta_demo_001"

# 1. First fact
$body = @{thread_id=$thread; message="Hello, I'm Sarah. I work at Microsoft."} | ConvertTo-Json
$r1 = Invoke-RestMethod -Uri "http://127.0.0.1:8123/api/chat/send" -Method POST -Body $body -ContentType "application/json"
Write-Host "Answer: $($r1.answer)"
Write-Host "Reintro count: $($r1.metadata.reintroduced_claims_count)"

# 2. Create contradiction
$body = @{thread_id=$thread; message="Actually, I work at Amazon, not Microsoft."} | ConvertTo-Json
$r2 = Invoke-RestMethod -Uri "http://127.0.0.1:8123/api/chat/send" -Method POST -Body $body -ContentType "application/json"
Write-Host "`nAnswer: $($r2.answer)"
Write-Host "Contradiction detected: $($r2.metadata.contradiction_detected)"
Write-Host "Reintro count: $($r2.metadata.reintroduced_claims_count)"

# 3. Recall
$body = @{thread_id=$thread; message="Where do I work?"} | ConvertTo-Json
$r3 = Invoke-RestMethod -Uri "http://127.0.0.1:8123/api/chat/send" -Method POST -Body $body -ContentType "application/json"
Write-Host "`nAnswer: $($r3.answer)"
Write-Host "Reintro count: $($r3.metadata.reintroduced_claims_count)"
Write-Host "`nX-Ray memories with flags:"
$r3.xray.memories_used | Where-Object { $_.reintroduced_claim -eq $true } | ForEach-Object {
    Write-Host "  • $($_.text.Substring(0, [Math]::Min(60, $_.text.Length)))..."
}
```

---

## What to Test

### Critical Paths (Must Work)
1. **Basic memory storage** - Facts are remembered across turns
2. **Contradiction detection** - System notices when you correct yourself
3. **Reintroduction flags** - Contradicted memories have `reintroduced_claim=true`
4. **Answer caveats** - Responses using contradicted claims include "(most recent update)" or similar
5. **X-Ray transparency** - `/api/chat/send` includes xray.memories_used with flags

### Invariant Compliance (Zero Tolerance)
- `reintroduced_unflagged_count` MUST be 0 (no contradicted memories without flags)
- Answers using contradicted claims MUST include caveats
- Count accuracy: `metadata.reintroduced_claims_count` == actual flagged memories

### Known Limitations (Not Bugs)
1. **Caveat detection is keyword-based** - Looks for "most recent", "latest", "though", etc.
2. **Ollama required for natural answers** - Without Ollama, you get error messages (but memory/flags still work)
3. **No UI hover preview yet** - "Alternative answer" feature planned for next release

---

## Expected Results

### Smoke Test Pass Criteria
```
✅ API server starts without errors
✅ Demo contradiction scenario completes
✅ Answer includes caveat: "Amazon (most recent update)"
✅ metadata.reintroduced_claims_count == 2
✅ xray shows 2 memories with reintroduced_claim=true
✅ Both Microsoft and Amazon memories have flag=true
```

### Smoke Test Output Example
```
Answer: Amazon (most recent update)
Metadata.reintroduced_claims_count: 2
X-Ray.reintroduced_claims_count: 2

X-Ray.memories_used (first 3):
  • text: Hello, I'm Sarah. I work at Microsoft.
    reintroduced_claim: True
    trust: 0.724
  • text: Actually, I work at Amazon, not Microsoft.
    reintroduced_claim: True
    trust: 0.716
```

---

## Reporting Bugs

### Bug Template
```markdown
**Version:** v0.9-beta
**Environment:** Windows/Mac/Linux, Python version, Ollama version
**Thread ID:** (e.g., beta_demo_001)

**Steps to Reproduce:**
1. 
2. 
3. 

**Expected Behavior:**

**Actual Behavior:**

**Logs/Screenshots:**
(paste relevant API response, terminal output, or screenshot)

**Severity:**
- [ ] Blocker (can't run demo)
- [ ] Major (feature doesn't work)
- [ ] Minor (cosmetic/edge case)
```

### Priority Issues (Report Immediately)
1. **API crash** - Server stops responding or exits
2. **Unflagged contradictions** - Memory has contradiction but `reintroduced_claim=false`
3. **Uncaveated assertions** - Answer uses contradicted claim without caveat
4. **Count mismatch** - `reintroduced_claims_count` doesn't match actual flagged memories

### Low Priority (Log but Don't Block)
1. Ollama connection issues (expected if Ollama not running)
2. Caveat wording variations (as long as SOME caveat exists)
3. Trust score values (evolution is heuristic, not deterministic)

---

## Feedback Workflow

### After Running Demo
1. **Fill out checklist:**
   ```
   ✅/❌ Demo completed without crashes
   ✅/❌ Contradiction detected (turn 2)
   ✅/❌ Reintroduced_claim flags present (turn 3)
   ✅/❌ Answer included caveat (turn 3)
   ✅/❌ X-Ray showed flagged memories
   ```

2. **Rate beta quality:**
   - **Ready for wider testing** (everything worked)
   - **Minor fixes needed** (1-2 small issues)
   - **Major work required** (core features broken)

3. **Submit feedback:**
   - Email: [your contact]
   - Include: Checklist + bug reports + any suggestions

---

## Files Included

### Documentation
- `BETA_STARTER_KIT.md` (this file)
- `BETA_RELEASE_NOTES.md` - Full changelog
- `CRT_REINTRODUCTION_INVARIANT.md` - Technical spec for flags
- `QUICKSTART.md` - Installation guide
- `DEMO_SCRIPT.md` - Full 25-turn demo (optional)

### Proof Artifacts
- `artifacts/crt_stress_run.20260121_162816.jsonl` - 15-turn proof with 0 violations
- Git tag: `v0.9-beta` - Verified release snapshot

### Source Code
- `crt_api.py` - FastAPI server (version 0.9-beta)
- `personal_agent/crt_rag.py` - Core engine with truth coherence
- `tools/crt_stress_test.py` - Automated validation suite

---

## Support

### If Demo Doesn't Work
1. **Check Ollama:** `ollama list` should show llama3.2
2. **Check API:** `curl http://127.0.0.1:8123/api/dashboard/overview?thread_id=test`
3. **Check logs:** Look for errors in terminal running uvicorn
4. **Reset thread:** `curl -X POST http://127.0.0.1:8123/api/thread/reset -H "Content-Type: application/json" -d '{"thread_id":"beta_demo_001","target":"all"}'`

### Contact
- Email: [your email]
- Response time: 24-48 hours

---

## Next Steps (Post-Beta)

Based on your feedback, we'll:
1. Fix any blocker bugs
2. Improve caveat detection (semantic vs keyword)
3. Add UI hover preview ("alternative answer" feature)
4. Implement "no-LLM mode" for testing without Ollama
5. Expand to wider beta (10-20 testers)

**Thank you for being an early tester!**  
**Your feedback shapes CRT's production readiness.**

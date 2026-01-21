# Beta Tester Verification Checklist

**Version:** v0.9-beta  
**Date:** _________________  
**Tester:** _________________  
**Environment:** Windows / Mac / Linux (circle one)

---

## Pre-Flight

```
□ Ollama installed and running (`ollama serve`)
□ Model pulled (`ollama pull llama3.2:latest`)
□ Python 3.10+ installed (`python --version`)
□ Virtual environment activated
□ Dependencies installed (`pip install -r requirements.txt`)
□ API server started (`uvicorn crt_api:app --reload --port 8123`)
□ API responding (curl http://127.0.0.1:8123/api/dashboard/overview?thread_id=test)
```

---

## Core Functionality (5-Minute Smoke Test)

### Test 1: Basic Memory
```powershell
# Thread: beta_smoke_test
$body = @{thread_id="beta_smoke_test"; message="My name is Jordan."} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8123/api/chat/send" -Method POST -Body $body -ContentType "application/json"
```

**Result:**
```
□ PASS - Answer acknowledges name
□ FAIL - Error/crash (describe: _________________________________)
```

---

### Test 2: Contradiction Detection
```powershell
# Create contradiction
$body = @{thread_id="beta_smoke_test"; message="I work at Microsoft."} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8123/api/chat/send" -Method POST -Body $body -ContentType "application/json"

$body = @{thread_id="beta_smoke_test"; message="Actually, I work at Amazon, not Microsoft."} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8123/api/chat/send" -Method POST -Body $body -ContentType "application/json"
```

**Result:**
```
□ PASS - metadata.contradiction_detected == true
□ FAIL - No contradiction detected
□ FAIL - Crash/error (describe: _________________________________)
```

---

### Test 3: Reintroduction Invariant (CRITICAL)
```powershell
# Recall contradicted fact
$body = @{thread_id="beta_smoke_test"; message="Where do I work?"} | ConvertTo-Json
$resp = Invoke-RestMethod -Uri "http://127.0.0.1:8123/api/chat/send" -Method POST -Body $body -ContentType "application/json"

# Check answer
Write-Host "Answer: $($resp.answer)"
Write-Host "Reintro count: $($resp.metadata.reintroduced_claims_count)"
Write-Host "X-Ray count: $($resp.xray.reintroduced_claims_count)"

# Check X-Ray flags
$resp.xray.memories_used | Where-Object { $_.reintroduced_claim -eq $true } | ForEach-Object {
    Write-Host "Flagged: $($_.text.Substring(0, 60))..."
}
```

**Critical Checks:**
```
□ PASS - Answer includes caveat (e.g., "most recent update", "latest", "though")
         Caveat found: _______________________________

□ PASS - metadata.reintroduced_claims_count == 2
         Actual count: _______

□ PASS - xray.reintroduced_claims_count == 2
         Actual count: _______

□ PASS - Both Microsoft and Amazon memories have reintroduced_claim=true
         Microsoft flag: _______
         Amazon flag: _______

□ FAIL - Missing caveat in answer
□ FAIL - Count mismatch (metadata vs actual flags)
□ FAIL - Memories missing reintroduced_claim field
□ FAIL - Contradicted memory has reintroduced_claim=false (BLOCKER)
```

---

## X-Ray Transparency

```powershell
# Check X-Ray structure
$resp.xray | ConvertTo-Json -Depth 3
```

**Verify:**
```
□ xray.memories_used is array
□ xray.reintroduced_claims_count is number
□ xray.conflicts_detected is array
□ Each memory has reintroduced_claim field (true/false)
□ Flagged memories have reintroduced_claim=true
```

---

## Reset & Cleanup

```powershell
# Reset thread
$body = @{thread_id="beta_smoke_test"; target="all"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8123/api/thread/reset" -Method POST -Body $body -ContentType "application/json"
```

**Result:**
```
□ PASS - Thread reset successfully
□ FAIL - Error (describe: _________________________________)
```

---

## Overall Assessment

### Severity Classification
Mark any failures:
```
□ BLOCKER - Cannot run basic demo (API won't start, crashes on simple queries)
□ CRITICAL - Invariant violation (unflagged contradiction, uncaveated answer)
□ MAJOR - Feature doesn't work (no contradiction detection, missing X-Ray data)
□ MINOR - Edge case or cosmetic issue
□ NONE - All tests passed
```

### Beta Quality Rating
```
□ READY - Ship to wider beta (10-20 testers)
□ MINOR FIXES - 1-2 issues, but shippable after patch
□ MAJOR WORK - Core functionality broken, needs significant fixes
□ NOT READY - Multiple blockers, back to development
```

### Time to Complete
- Setup time: _______ minutes
- Smoke test time: _______ minutes
- Total time: _______ minutes

### Notes/Feedback
```
What worked well:



What didn't work:



Suggestions for improvement:



Would you use this in production? (Yes / No / Maybe)

```

---

## Submission

**Email results to:** [your email]  
**Subject:** CRT v0.9-beta Test Results - [Your Name]  
**Attach:** This completed checklist + any screenshots/logs

**Expected turnaround:** 24-48 hours for feedback acknowledgment

---

## Quick Reference

### PowerShell Full Smoke Test (Copy-Paste)
```powershell
# Setup
$thread = "beta_smoke_test"
$api = "http://127.0.0.1:8123/api/chat/send"

# Test 1: Memory
$b1 = @{thread_id=$thread; message="My name is Jordan."} | ConvertTo-Json
$r1 = Invoke-RestMethod -Uri $api -Method POST -Body $b1 -ContentType "application/json"
Write-Host "1. Memory: $($r1.answer)"

# Test 2: Contradiction
$b2 = @{thread_id=$thread; message="I work at Microsoft."} | ConvertTo-Json
$r2 = Invoke-RestMethod -Uri $api -Method POST -Body $b2 -ContentType "application/json"
Write-Host "2a. First fact: $($r2.answer)"

$b3 = @{thread_id=$thread; message="Actually, I work at Amazon, not Microsoft."} | ConvertTo-Json
$r3 = Invoke-RestMethod -Uri $api -Method POST -Body $b3 -ContentType "application/json"
Write-Host "2b. Contradiction: detected=$($r3.metadata.contradiction_detected)"

# Test 3: Invariant
$b4 = @{thread_id=$thread; message="Where do I work?"} | ConvertTo-Json
$r4 = Invoke-RestMethod -Uri $api -Method POST -Body $b4 -ContentType "application/json"
Write-Host "`n3. CRITICAL CHECKS:"
Write-Host "   Answer: $($r4.answer)"
Write-Host "   Reintro count: $($r4.metadata.reintroduced_claims_count)"
Write-Host "   X-Ray count: $($r4.xray.reintroduced_claims_count)"
Write-Host "   Flagged memories:"
$r4.xray.memories_used | Where-Object { $_.reintroduced_claim -eq $true } | ForEach-Object {
    Write-Host "     • $($_.text.Substring(0, [Math]::Min(60, $_.text.Length)))..."
}

# Cleanup
$reset = @{thread_id=$thread; target="all"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8123/api/thread/reset" -Method POST -Body $reset -ContentType "application/json" | Out-Null
Write-Host "`n✅ Smoke test complete. Check results above."
```

### Bash Version (Mac/Linux)
```bash
#!/bin/bash
THREAD="beta_smoke_test"
API="http://127.0.0.1:8123/api/chat/send"

# Test 1
curl -s -X POST $API -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"message\":\"My name is Jordan.\"}" | jq -r '.answer'

# Test 2
curl -s -X POST $API -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"message\":\"I work at Microsoft.\"}" > /dev/null

curl -s -X POST $API -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"message\":\"Actually, I work at Amazon, not Microsoft.\"}" \
  | jq -r '.metadata.contradiction_detected'

# Test 3
RESP=$(curl -s -X POST $API -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"message\":\"Where do I work?\"}")

echo "Answer: $(echo $RESP | jq -r '.answer')"
echo "Reintro count: $(echo $RESP | jq -r '.metadata.reintroduced_claims_count')"
echo "X-Ray count: $(echo $RESP | jq -r '.xray.reintroduced_claims_count')"

# Cleanup
curl -s -X POST http://127.0.0.1:8123/api/thread/reset \
  -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"target\":\"all\"}" > /dev/null

echo "✅ Smoke test complete"
```

---

**This checklist should take ~10 minutes to complete.**  
**If anything takes longer or fails, report it as a bug.**

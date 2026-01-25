# Beta Demo Script (5-Turn Contradiction Flow)

**Purpose:** Demonstrate contradiction detection + reintroduction disclosure  
**Time:** ~2 minutes  
**Required:** API running on port 8123, Ollama optional

---

## Script

### Turn 1: Initial Fact
**User:**
```
My name is Alex Chen and I work at DataCore.
```

**Expected:**
- Response acknowledges facts
- No badges/warnings
- Gates may pass or fail (not critical)

---

### Turn 2: Create Contradiction
**User:**
```
Actually, I made a mistake - I work at TechFlow, not DataCore.
```

**Expected:**
- `CONTRADICTION` badge appears
- Response acknowledges correction
- System detects employer conflict (DataCore vs TechFlow)

---

### Turn 3: Recall Contradicted Fact
**User:**
```
Where do I work?
```

**Expected:**
- Answer: "TechFlow (most recent update)" or similar caveat
- `⚠️ CONTRADICTED CLAIMS (2)` badge visible
- Answer includes inline disclosure phrase
- If X-Ray mode enabled: Both memories flagged with `⚠️ CONTRADICTED` label

---

### Turn 4: Confirm Other Fact
**User:**
```
What's my name?
```

**Expected:**
- Answer: "Alex Chen"
- No contradiction badges (name wasn't contradicted)
- Clean response, no warnings

---

### Turn 5: Memory Summary
**User:**
```
What do you know about me?
```

**Expected:**
- Lists: Name (Alex Chen), Employer (TechFlow with caveat)
- May show `⚠️ CONTRADICTED CLAIMS` badge if contradicted memories included
- Demonstrates system tracks corrected vs stable facts differently

---

## Visual Indicators (UI)

### Message-Level Badge
When answer uses contradicted memories:
```
⚠️ CONTRADICTED CLAIMS (2)
```
- Amber background (`bg-amber-500/15`)
- Shows count of contradicted memories used
- Tooltip: "This answer uses N contradicted memory/memories"

### X-Ray Mode Enhancement
Individual memories marked:
```
T:0.72 · ⚠️ CONTRADICTED · I work at DataCore.
```
- Inline amber badge before memory text
- Only appears if `reintroduced_claim: true`
- Makes contradicted memories visually distinct

---

## PowerShell Quick Test

```powershell
$thread = "demo_beta_quick"
$api = "http://127.0.0.1:8123/api/chat/send"

# Turn 1
$b = @{thread_id=$thread; message="My name is Alex Chen and I work at DataCore."} | ConvertTo-Json
Invoke-RestMethod -Uri $api -Method POST -Body $b -ContentType "application/json" | Select-Object answer | Format-List

# Turn 2
$b = @{thread_id=$thread; message="Actually, I made a mistake - I work at TechFlow, not DataCore."} | ConvertTo-Json
$r = Invoke-RestMethod -Uri $api -Method POST -Body $b -ContentType "application/json"
Write-Host "Answer: $($r.answer)"
Write-Host "Contradiction detected: $($r.metadata.contradiction_detected)"

# Turn 3
$b = @{thread_id=$thread; message="Where do I work?"} | ConvertTo-Json
$r = Invoke-RestMethod -Uri $api -Method POST -Body $b -ContentType "application/json"
Write-Host "`nAnswer: $($r.answer)"
Write-Host "Reintroduced claims: $($r.metadata.reintroduced_claims_count)"

# Cleanup
$reset = @{thread_id=$thread; target="all"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8123/api/thread/reset" -Method POST -Body $reset -ContentType "application/json" | Out-Null
```

---

## Success Criteria

```
✅ Turn 2: CONTRADICTION badge appears
✅ Turn 3: Answer includes caveat (e.g., "most recent", "latest")
✅ Turn 3: ⚠️ CONTRADICTED CLAIMS badge visible
✅ Turn 3: Badge shows count = 2
✅ X-Ray mode: Contradicted memories have ⚠️ label
✅ Turn 4: No warnings (name not contradicted)
```

---

## Notes

- **Ollama not required:** Memory storage and flags work without LLM, answers will be error messages
- **X-Ray toggle:** Enable in UI settings to see memory-level flags
- **Badge placement:** Above message text, next to other badges (GATES, CONTRADICTION, etc.)
- **No core changes:** Only UI presentation, existing invariant enforcement unchanged

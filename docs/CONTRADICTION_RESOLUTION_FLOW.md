# Contradiction Resolution Flow

## User Critique: "How Do Users Resolve Contradictions?"

**Concern**: "How do users actually resolve contradictions in this system? The demo shows contradictions being flagged, but what's the resolution flow?"

## Current Architecture

### Design Philosophy: No Silent Resolution

From [CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md#L58):
> CRT **never silently resolves conflicts**. Resolution requires user input, not system guessing.

**Core Principle**: The system preserves all contradictions until the user explicitly clarifies.

### Resolution Status States

Contradictions track status in the ledger (see [crt_ledger.py](personal_agent/crt_ledger.py#L36-L42)):

```python
class ContradictionStatus:
    OPEN = "open"              # Unresolved tension
    REFLECTING = "reflecting"  # Reflection in progress
    RESOLVED = "resolved"      # Merged via reflection
    ACCEPTED = "accepted"      # Both kept as valid perspectives
```

## How Resolution Works

### 1. User Makes Clarification

**Scenario**: User has contradicting employer memories (Microsoft vs Amazon)

**Resolution Trigger**: User asserts one of the values again

```bash
# Turn 1: Create contradiction
curl -X POST http://127.0.0.1:8123/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"resolution_demo","message":"I work at Microsoft."}'

# Turn 2: Contradict
curl -X POST http://127.0.0.1:8123/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"resolution_demo","message":"Actually, I work at Amazon."}'

# Turn 3: System asks for clarification
# Response: "I have conflicting information about your employer..."

# Turn 4: User clarifies
curl -X POST http://127.0.0.1:8123/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"resolution_demo","message":"Definitely Amazon, not Microsoft."}'
```

**What Happens**: 
- `_resolve_open_conflicts_from_assertion()` detects user re-asserting "Amazon"
- Ledger entry for Microsoft vs Amazon is marked `RESOLVED`
- `has_open_contradiction()` now returns False
- Future queries no longer flag reintroduced claims

**Code**: [crt_rag.py:968-1067](personal_agent/crt_rag.py#L968-L1067)

### 2. Explicit Slot Assignment (Advanced)

For test harnesses or programmatic resolution:

```bash
curl -X POST http://127.0.0.1:8123/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{"thread_id":"test","message":"employer = Amazon"}'
```

**Supported Slots**:
- `employer`, `name`, `location`, `title`
- `first_language`, `masters_school`, `undergrad_school`
- `programming_years`, `team_size`

**Regex Pattern**: `\bemployer\s*=\s*([^\n\r\.;,!\?]{2,80})`

### 3. Natural Time-Based Resolution

**REVISION Type**: User explicitly corrects ("Actually, not X")
- New memory overwrites old
- Contradiction auto-marked `REVISION` type
- Future queries prefer latest value

**TEMPORAL Type**: Natural progression ("I was promoted")
- Tracks both old (Senior) and new (Principal) titles
- System recognizes career progression pattern
- Not treated as hard conflict

**Code**: [crt_ledger.py:43-51](personal_agent/crt_ledger.py#L43-L51)

## Resolution Methods

### Method 1: User Clarification (Primary)

**Trigger**: User re-asserts one side of the contradiction

**Logic** (from `_resolve_open_conflicts_from_assertion`):
```python
# Extract facts from user's new message
facts = extract_fact_slots(user_text)

# Get all OPEN conflicts
open_contras = ledger.get_open_contradictions()

# For each conflict:
for contra in open_contras:
    old_facts = extract_fact_slots(old_memory.text)
    new_facts = extract_fact_slots(new_memory.text)
    
    # If user re-asserts either old OR new value:
    if user_fact in {old_fact, new_fact}:
        ledger.resolve_contradiction(
            contra.id,
            method="user_clarified",
            new_status=ContradictionStatus.RESOLVED
        )
```

**Result**: Contradiction status → `RESOLVED`

### Method 2: Reflection (Future Work)

**Status**: Planned for v1.0+

**Concept**: System generates reflection prompt, user confirms/rejects

```python
# Not yet implemented
if status == ContradictionStatus.REFLECTING:
    prompt = generate_clarification_prompt(old_memory, new_memory)
    # "Did you mean X or Y? Or are both valid in different contexts?"
```

**Code Stub**: [crt_ledger.py:325-335](personal_agent/crt_ledger.py#L325-L335)

### Method 3: Acceptance (Both Valid)

**Use Case**: Context-dependent facts (e.g., home vs work address)

**Manual Trigger**:
```bash
# Admin/CLI only (not exposed in beta API)
ledger.update_contradiction_status(
    contradiction_id="abc123",
    new_status=ContradictionStatus.ACCEPTED
)
```

**Effect**: Contradiction preserved, but flagged as "valid perspectives"

## What Happens After Resolution?

### Status = RESOLVED

1. `has_open_contradiction(memory_id)` → returns `False`
2. Memories no longer flagged with `reintroduced_claim=true`
3. Answers no longer include caveats like "(most recent update)"
4. X-Ray metadata: `reintroduced_claims_count` decreases

### Status = ACCEPTED

1. Both memories remain active
2. No reintroduction flags (both considered "accepted truth")
3. Answers may mention both: "You have two locations: Seattle (home), Bellevue (office)"

### Historical Record

Resolved contradictions **remain in the ledger**:
```sql
SELECT * FROM contradiction_ledger 
WHERE status = 'resolved' 
ORDER BY timestamp DESC;
```

**Purpose**: Audit trail, learning from resolution patterns

## Frontend Resolution UX (Roadmap)

### Planned Features (v1.0+)

**1. Contradiction Badges** (partially implemented)
- Memory items show orange badge when contradicted
- Click badge → shows conflicting memories side-by-side

**2. Quick Actions**
```
┌─────────────────────────────────────┐
│ Conflicting Employer Information    │
├─────────────────────────────────────┤
│ ① Microsoft (Turn 1, 3 days ago)    │
│ ② Amazon (Turn 2, Today)            │
├─────────────────────────────────────┤
│ [Keep ①] [Keep ②] [Keep Both]       │
└─────────────────────────────────────┘
```

**3. Clarification Prompts**
- System proactively asks: "I see conflicting info. Which is current?"
- User clicks button → auto-resolves

### Current Beta Behavior

**As of v0.9-beta**: Resolution is **implicit** via natural conversation:

- System: "I have conflicting information about your employer..."
- User: "I work at Amazon, forget the Microsoft thing"
- System: (Detects "Amazon" re-assertion → auto-resolves)

**No explicit UI** for resolution yet - relies on conversational clarification.

## Testing Resolution Flow

### Test Script (bash/curl)

```bash
THREAD="resolution_test"
API="http://127.0.0.1:8123/api/chat/send"

# 1. Create contradiction
curl -X POST $API -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"message\":\"I work at Microsoft.\"}" | jq -r '.answer'

curl -X POST $API -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"message\":\"Actually, I work at Amazon.\"}" | jq -r '.answer'

# 2. Check contradiction flag
curl -X POST $API -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"message\":\"Where do I work?\"}" | \
  jq '{answer: .answer, reintroduced_claims: .metadata.reintroduced_claims_count}'

# Expected: {"answer": "Amazon (most recent update)", "reintroduced_claims": 2}

# 3. Clarify/resolve
curl -X POST $API -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"message\":\"Definitely Amazon, not Microsoft.\"}" | jq -r '.answer'

# 4. Verify resolution
curl -X POST $API -H "Content-Type: application/json" \
  -d "{\"thread_id\":\"$THREAD\",\"message\":\"Where do I work?\"}" | \
  jq '{answer: .answer, reintroduced_claims: .metadata.reintroduced_claims_count}'

# Expected: {"answer": "Amazon", "reintroduced_claims": 0}
# (No caveat, no flags - contradiction resolved)
```

### PowerShell Version

```powershell
$thread = "resolution_test"
$api = "http://127.0.0.1:8123/api/chat/send"

# 1. Create contradiction
$b1 = @{thread_id=$thread; message="I work at Microsoft."} | ConvertTo-Json
$r1 = Invoke-RestMethod -Uri $api -Method POST -Body $b1 -ContentType "application/json"

$b2 = @{thread_id=$thread; message="Actually, I work at Amazon."} | ConvertTo-Json
$r2 = Invoke-RestMethod -Uri $api -Method POST -Body $b2 -ContentType "application/json"

# 2. Check contradiction flag
$b3 = @{thread_id=$thread; message="Where do I work?"} | ConvertTo-Json
$r3 = Invoke-RestMethod -Uri $api -Method POST -Body $b3 -ContentType "application/json"
Write-Host "Before: $($r3.answer) | Flags: $($r3.metadata.reintroduced_claims_count)"

# 3. Clarify
$b4 = @{thread_id=$thread; message="Definitely Amazon, not Microsoft."} | ConvertTo-Json
$r4 = Invoke-RestMethod -Uri $api -Method POST -Body $b4 -ContentType "application/json"

# 4. Verify resolution
$b5 = @{thread_id=$thread; message="Where do I work?"} | ConvertTo-Json
$r5 = Invoke-RestMethod -Uri $api -Method POST -Body $b5 -ContentType "application/json"
Write-Host "After: $($r5.answer) | Flags: $($r5.metadata.reintroduced_claims_count)"
```

## Common Patterns

### Pattern 1: Typo Correction
```
User: "I live in Seatle"
User: "Sorry, Seattle not Seatle"
→ Contradiction type: REVISION (auto-resolved on next assertion)
```

### Pattern 2: Value Update
```
User: "I'm a Senior Engineer"
[3 months later]
User: "I was promoted to Principal Engineer"
→ Contradiction type: TEMPORAL (progression, not conflict)
```

### Pattern 3: Context Clarification
```
User: "I work at Amazon"
User: "I also consult for Microsoft"
→ Both valid → Status: ACCEPTED (manual, future feature)
```

## FAQ

**Q: Can I delete a memory instead of resolving contradiction?**
A: Not in v0.9-beta. Memory deletion is planned for v1.0 as part of "Memory Policy" features.

**Q: Does resolution happen automatically if I keep using one value?**
A: Yes - if you naturally use "Amazon" in 3+ turns, the system infers clarification and resolves the Microsoft conflict.

**Q: Can I see all resolved contradictions?**
A: Via SQL directly: `SELECT * FROM contradiction_ledger WHERE status='resolved'`. Frontend query UI is roadmap.

**Q: What if I want both values preserved (home vs work)?**
A: Use explicit context in your messages: "I work at Amazon remotely from Seattle, but commute to Microsoft's Redmond office." System will store both contexts.

## Roadmap

### v1.0: Explicit Resolution UI
- [ ] Contradiction resolution panel in frontend
- [ ] "Forget this" / "Keep both" buttons
- [ ] Reflection-based clarification prompts

### v1.0: Memory Policy
- [ ] User-configurable retention rules
- [ ] Explicit memory deletion API
- [ ] "Forget everything about X" commands

### v1.0+: Multi-Context Support
- [ ] Tag memories with context (work vs personal)
- [ ] Auto-detect context switches
- [ ] "Both valid" contradictions (ACCEPTED status)

## Cross-References

- Philosophy: [CRT_PHILOSOPHY.md](CRT_PHILOSOPHY.md#L58-L64)
- Ledger Implementation: [crt_ledger.py](personal_agent/crt_ledger.py#L36-L51)
- Resolution Logic: [crt_rag.py:_resolve_open_conflicts_from_assertion()](personal_agent/crt_rag.py#L968-L1067)
- Known Limitations: [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md#L138-L150)
- Demo Script: [BETA_STARTER_KIT.md](BETA_STARTER_KIT.md#L100-L160)

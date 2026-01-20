# Truth Coherence Fix - Implementation Plan

**Priority**: CRITICAL for beta  
**Issue**: System can mention contradicted facts as if they're current  
**Impact**: "Sounds confident but lies" - breaks core promise  
**Directive**: Always answer + mark uncertainty inline

---

## The Problem

Current behavior from stress test (139 instances):
```
Turn 4:  User: "I work at Vertex Analytics"
Turn 14: User: "I work at DataCore"  [contradiction detected ✓]
Turn 18: Assistant: "You work at Vertex Analytics" [WRONG ✗]
```

**Why this happens**: Retrieval pulls high-trust old memories. Response generation doesn't check if they're contradicted.

---

## The Solution (Two-Part Fix)

### Part 1: Conflict-Aware Response Filter
**File**: `personal_agent/crt_rag.py`  
**Functions to patch**:
- `_build_memory_inventory_answer()` (line 3237)
- `_build_synthesis_answer()` (line 3280)
- `_build_memory_citation_answer()` (line 3361)
- Any function that builds user fact summaries

**Strategy**:
Before outputting any fact slot value (name, employer, location, etc.):
1. Check if that slot has open contradictions
2. If yes, either:
   - **Option A**: Use latest trusted value + add caveat: "(earlier you said X, now Y)"
   - **Option B**: Explicitly state conflict: "Conflict: you said X, then Y"
3. If no conflict, output normally

**Data structures available**:
```python
# Get open contradictions
open_contradictions = self.ledger.get_open_contradictions(limit=100)

# Check specific memory
has_conflict = self.ledger.has_open_contradiction(memory_id)

# Contradiction entry has:
# - claim_a_text, claim_b_text
# - status (OPEN, RESOLVED, ACCEPTED)
# - contradiction_type
```

### Part 2: X-Ray Toggle (UI Transparency)
**Files**: 
- `crt_api.py` - Add metadata to response
- `frontend/src/pages/ChatPage.tsx` - Add toggle UI

**What to show when enabled**:
```json
{
  "answer": "You work at DataCore",
  "xray_mode": {
    "memories_used": [
      {"text": "I work at DataCore", "trust": 0.95, "timestamp": "..."},
      {"text": "I work at Vertex Analytics", "trust": 0.80, "timestamp": "..."}
    ],
    "conflicts_detected": [
      {
        "slot": "employer",
        "old": "Vertex Analytics",
        "new": "DataCore",
        "status": "open"
      }
    ],
    "decision": "Used latest (DataCore), noted conflict"
  }
}
```

---

## Minimal Implementation (1-2 hours)

### Step 1: Add Conflict Checker Helper (15 min)

Add to `crt_rag.py` around line 600:

```python
def _get_fact_slot_conflicts(self, slot: str) -> Optional[Dict[str, Any]]:
    """Check if a fact slot has open contradictions.
    
    Returns:
        None if no conflict
        Dict with {old_value, new_value, status} if conflict exists
    """
    open_contras = self.ledger.get_open_contradictions(limit=100)
    
    for contra in open_contras:
        # Check if contradiction involves this slot
        # This is simplified - real impl needs fact slot extraction
        claim_a = (contra.claim_a_text or "").lower()
        claim_b = (contra.claim_b_text or "").lower()
        
        # Detect slot mentions (employer, location, name, etc.)
        if slot in claim_a or slot in claim_b:
            return {
                "slot": slot,
                "old_value": contra.claim_a_text,
                "new_value": contra.claim_b_text,
                "status": contra.status.value
            }
    
    return None
```

### Step 2: Patch Memory Inventory (20 min)

Update `_build_memory_inventory_answer()` around line 3237:

```python
def _build_memory_inventory_answer(
    self,
    *,
    user_query: str,
    retrieved: List[Tuple[MemoryItem, float]],
    prompt_docs: List[Dict[str, Any]],
    max_lines: int = 8,
) -> str:
    """Deterministic safe memory-inventory response with conflict awareness."""
    lines: List[str] = []
    
    # Check for open contradictions
    open_contras = self.ledger.get_open_contradictions(limit=10)
    has_conflicts = len(open_contras) > 0
    
    if not retrieved:
        lines.append("I don't have any stored memories to cite yet.")
        return "\n".join(lines)

    # NEW: If conflicts exist, note them upfront
    if has_conflicts:
        lines.append("I have conflicting information on some facts. Here's what I have:")
    else:
        lines.append("Here is what I have stored:")

    added = 0
    for d in (prompt_docs or []):
        txt = str((d or {}).get("text") or "").strip()
        if not txt:
            continue

        src = str((d or {}).get("source") or "").strip().lower()
        is_fact = txt.lower().startswith("fact:")
        is_user = src == MemorySource.USER.value

        if not (is_fact or is_user):
            continue

        # NEW: Check if this fact has a conflict
        memory_id = (d or {}).get("memory_id")
        if memory_id and self.ledger.has_open_contradiction(memory_id):
            txt = f"{txt} (⚠️ conflict exists)"

        lines.append(f"- {txt}")
        added += 1
        if added >= max_lines:
            break

    # NEW: List conflicts explicitly
    if has_conflicts and added < max_lines:
        lines.append("\nOpen conflicts:")
        for contra in open_contras[:3]:  # Top 3
            lines.append(f"- '{contra.claim_a_text[:50]}' vs '{contra.claim_b_text[:50]}'")

    return "\n".join(lines)
```

### Step 3: Add X-Ray Metadata to API Response (30 min)

Update `crt_api.py` response model:

```python
class ChatSendResponse(BaseModel):
    answer: str
    response_type: str
    gates_passed: bool
    gate_reason: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    xray: Optional[Dict[str, Any]] = None  # NEW

# In the /api/chat/send endpoint, after getting result:
if result.get("metadata", {}).get("retrieved_memories"):
    xray_data = {
        "memories_used": [
            {
                "text": m.get("text", "")[:100],
                "trust": m.get("trust", 0),
                "confidence": m.get("confidence", 0),
                "timestamp": m.get("timestamp")
            }
            for m in result["metadata"]["retrieved_memories"][:5]
        ],
        "conflicts_detected": []
    }
    
    # Add conflicts if any
    contradictions = rag_instance.ledger.get_open_contradictions(limit=10)
    for c in contradictions:
        xray_data["conflicts_detected"].append({
            "old": c.claim_a_text[:100],
            "new": c.claim_b_text[:100],
            "status": c.status.value
        })
    
    response_data["xray"] = xray_data
```

### Step 4: UI Toggle (30 min)

Add to `frontend/src/pages/ChatPage.tsx`:

```typescript
// State
const [xrayMode, setXrayMode] = useState(false);

// UI Toggle (add to toolbar)
<button onClick={() => setXrayMode(!xrayMode)}>
  {xrayMode ? '🔬 X-Ray ON' : '🔬 X-Ray'}
</button>

// Display X-Ray data when message has it
{xrayMode && message.xray && (
  <div className="xray-panel">
    <h4>Memory Evidence:</h4>
    <ul>
      {message.xray.memories_used.map((m, i) => (
        <li key={i}>
          {m.text} (trust: {m.trust.toFixed(2)})
        </li>
      ))}
    </ul>
    {message.xray.conflicts_detected.length > 0 && (
      <>
        <h4>Conflicts:</h4>
        <ul>
          {message.xray.conflicts_detected.map((c, i) => (
            <li key={i}>
              Old: {c.old}<br/>
              New: {c.new}<br/>
              Status: {c.status}
            </li>
          ))}
        </ul>
      </>
    )}
  </div>
)}
```

---

## Testing Plan (20 min)

### Test 1: Conflict Inline Notation
```
User: My name is Jordan.
User: My name is Alex.
User: What's my name?
Expected: "Alex (earlier you said Jordan)" OR "Conflict: Jordan vs Alex"
```

### Test 2: X-Ray Mode
```
User: I work at DataCore.
User: I live in Austin.
[Toggle X-Ray ON]
User: Tell me about myself.
Expected: See both memories listed, no conflicts shown
```

### Test 3: Conflict Visibility
```
User: I work at Vertex.
User: I work at DataCore.
[Toggle X-Ray ON]
User: Where do I work?
Expected: See conflict in X-Ray panel, answer uses latest with caveat
```

---

## Acceptance Criteria

✅ **No casual lies**: System never states contradicted fact as if it's current  
✅ **Inline caveats**: When conflict exists, answer includes "(earlier X, now Y)"  
✅ **X-Ray shows evidence**: Toggle displays which memories + which conflicts  
✅ **Stress test clean**: Re-run 80-turn test, verify < 10 truth reintroductions  

---

## Risks & Mitigations

**Risk**: Caveat text sounds awkward  
**Mitigation**: Acceptable for beta. Can polish voice in v1.0

**Risk**: X-Ray exposes too much implementation detail  
**Mitigation**: Label it "Power User Mode" or "Debug View"

**Risk**: Performance hit from checking all contradictions  
**Mitigation**: Ledger queries are fast (< 10ms), negligible impact

---

## Time Estimate

- Step 1 (conflict checker): 15 min
- Step 2 (inventory patch): 20 min
- Step 3 (API X-Ray): 30 min
- Step 4 (UI toggle): 30 min
- Testing: 20 min

**Total: ~2 hours**

Combined with debug print removal (30 min), still achievable today.

---

## After This Fix

Users will see:
- ✅ System acknowledges conflicts inline
- ✅ Can inspect which memories were used (X-Ray)
- ✅ Never "confident lies" about contradicted facts
- ✅ Maintains "always answer" philosophy with transparency

**This is the trust-preserving behavior beta needs.**

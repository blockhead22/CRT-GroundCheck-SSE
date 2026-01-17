# CRT Fixes Implementation Status

## ✅ Completed

1. **Parameter Tuning** (crt_core.py)
   - theta_contra: 0.35 → 0.42
   - theta_mem: 0.30 → 0.37
   - Status: APPLIED ✓

2. **Uncertainty Response State** (crt_rag.py)
   - Added `_should_express_uncertainty()` method
   - Added `_generate_uncertain_response()` method
   - Integrated global coherence gate into query()
   - Status: APPLIED ✓

3. **Contradiction Type Filtering** (crt_rag.py)
   - Only CONFLICT type triggers full trust degradation
   - Refinements/temporal/revisions logged but don't poison trust
   - Status: APPLIED ✓

## ⚠️ Partially Complete (Needs Manual Application)

4. **Contradiction Classification System** (crt_ledger.py)
   - File was corrupted during multi-edit
   - Restored from git
   - NEEDS: Manual addition of:
     - `ContradictionType` class (refinement/revision/temporal/conflict)
     - `_classify_contradiction()` method
     - `contradiction_type` field to ContradictionEntry dataclass
     - Database schema update to include contradiction_type column
     - Update `record_contradiction()` signature to accept old_text/new_text/vectors

## Manual Implementation Steps

### Step 1: Add ContradictionType Class

After line 33 in `crt_ledger.py`, add:

```python
class ContradictionType:
    """Type of contradiction based on fact topology."""
    REFINEMENT = "refinement"  # More specific (Seattle → Bellevue)
    REVISION = "revision"      # Correction ("actually", "not")
    TEMPORAL = "temporal"      # Progression (Senior → Principal)
    CONFLICT = "conflict"      # Mutually exclusive (Microsoft vs Amazon)
```

### Step 2: Add contradiction_type to ContradictionEntry

In the `@dataclass ContradictionEntry` (around line 57), add after `status`:

```python
status: str = ContradictionStatus.OPEN
contradiction_type: str = ContradictionType.CONFLICT  # NEW LINE
```

And in `to_dict()` method (around line 79), add:

```python
'status': self.status,
'contradiction_type': self.contradiction_type,  # NEW LINE
'query': self.query,
```

### Step 3: Update Database Schema

In `_init_db()` method (around line 131), modify the CREATE TABLE:

```sql
CREATE TABLE IF NOT EXISTS contradictions (
    ...
    status TEXT NOT NULL,
    contradiction_type TEXT DEFAULT 'conflict',  -- NEW LINE
    query TEXT,
    ...
)
```

### Step 4: Add Classification Method

Before `record_contradiction()` method (around line 180), add:

```python
def _classify_contradiction(
    self,
    old_text: str,
    new_text: str,
    drift_mean: float,
    old_vector: Optional[np.ndarray] = None,
    new_vector: Optional[np.ndarray] = None
) -> str:
    """Classify contradiction type based on fact topology."""
    old_lower = old_text.lower()
    new_lower = new_text.lower()
    
    # Check for revision keywords
    revision_keywords = ["actually", "correction", "i meant", "not ", "wrong", "mistake"]
    if any(kw in new_lower for kw in revision_keywords):
        return ContradictionType.REVISION
    
    # Check for hierarchical refinement
    if old_text in new_text or new_text in old_text:
        return ContradictionType.REFINEMENT
    
    # Check for temporal progression
    temporal_keywords = ["now", "currently", "promoted", "became", "upgraded"]
    seniority_pairs = [("senior", "principal"), ("junior", "senior")]
    
    if any(kw in new_lower for kw in temporal_keywords):
        return ContradictionType.TEMPORAL
    
    for lower, higher in seniority_pairs:
        if lower in old_lower and higher in new_lower:
            return ContradictionType.TEMPORAL
    
    # Check semantic similarity if vectors available
    if old_vector is not None and new_vector is not None:
        similarity = self.crt_math.similarity(old_vector, new_vector)
        if 0.7 <= similarity < 0.9:
            return ContradictionType.REFINEMENT
    
    return ContradictionType.CONFLICT
```

### Step 5: Update record_contradiction Signature

Modify `record_contradiction()` method signature (around line 185):

```python
def record_contradiction(
    self,
    old_memory_id: str,
    new_memory_id: str,
    drift_mean: float,
    confidence_delta: float,
    query: Optional[str] = None,
    summary: Optional[str] = None,
    drift_reason: Optional[float] = None,
    old_text: Optional[str] = None,  # NEW
    new_text: Optional[str] = None,   # NEW
    old_vector: Optional[np.ndarray] = None,  # NEW
    new_vector: Optional[np.ndarray] = None    # NEW
) -> ContradictionEntry:
```

And add classification logic before creating entry:

```python
# Classify the contradiction type
if old_text and new_text:
    contradiction_type = self._classify_contradiction(
        old_text, new_text, drift_mean, old_vector, new_vector
    )
else:
    contradiction_type = ContradictionType.CONFLICT

entry = ContradictionEntry(
    ...
    contradiction_type=contradiction_type,  # Add this line
    ...
)
```

### Step 6: Update Database INSERT

In the INSERT statement (around line 204):

```sql
INSERT INTO contradictions
(ledger_id, timestamp, old_memory_id, new_memory_id, drift_mean, 
 drift_reason, confidence_delta, status, contradiction_type, query, summary)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

And add `entry.contradiction_type` to the values tuple.

### Step 7: Update _row_to_entry

Modify `_row_to_entry()` method (around line 460) to handle the new column:

```python
def _row_to_entry(self, row) -> ContradictionEntry:
    return ContradictionEntry(
        ledger_id=row[0],
        timestamp=row[1],
        old_memory_id=row[2],
        new_memory_id=row[3],
        drift_mean=row[4],
        drift_reason=row[5],
        confidence_delta=row[6],
        status=row[7],
        contradiction_type=row[8] if len(row) > 8 else "conflict",  # Handle schema migration
        query=row[9] if len(row) > 9 else None,
        summary=row[10] if len(row) > 10 else None,
        ...
    )
```

## Testing After Manual Changes

1. Clear databases: 
   ```powershell
   Remove-Item personal_agent\crt_*.db
   ```

2. Test import:
   ```python
   from personal_agent.crt_rag import CRTEnhancedRAG
   from personal_agent.crt_ledger import ContradictionType
   ```

3. Run stress test:
   ```python
   python crt_stress_test.py
   ```

## Expected Improvements

- Contradiction detection rate: 166% → 70-90%
- Gate pass rate: 97% → 85-90%  
- False positives: Significantly reduced (Seattle→Bellevue won't trigger)
- Uncertainty responses: System will explicitly state when contradictions unresolved
- Trust evolution: Only CONFLICT type degrades trust significantly

## Files Modified

✅ `personal_agent/crt_core.py` - Parameter updates
✅ `personal_agent/crt_rag.py` - Uncertainty state + global coherence gate
⚠️ `personal_agent/crt_ledger.py` - Needs manual changes (see above)
✅ `CRT_ARCHITECTURAL_FIXES_v2.md` - Documentation


# Phase 2.0: Context-Aware Memory Architecture

## Problem Statement

The current CRT system treats facts as **single-value slots** that overwrite each other. Real user profiles are **multi-faceted, temporal, and context-dependent**:

- "I work at Google" (2022) + "I don't work at Google anymore" (2024) = **temporal update**, not contradiction
- "I'm a programmer" + "I'm a photographer" = **multi-role**, not conflict
- "What do I need to order for the most recent job?" = needs **domain context** (print shop vs programming)

## Current Architecture Gaps

| Feature | Current State | Target State |
|---------|--------------|--------------|
| **Slot Values** | Single value per slot | Array of values with metadata |
| **Temporal Awareness** | Only creation timestamp | `status: past/active/future`, `period: "2020-2024"` |
| **Domain Context** | None | Tags like `print_shop`, `programming`, `photography` |
| **Contradiction Rules** | Any value change = potential conflict | Same slot + same context + same period = conflict |

## Existing Infrastructure (Good News)

The codebase already has partial support:

1. **`user_profile_multi` table** in `personal_agent/user_profile.py` — supports multiple values per slot with `active` flag
2. **`FactTuple` dataclass** in `personal_agent/two_tier_facts.py` — has `action: add/update/deprecate/deny`
3. **`contradiction_type`** in `personal_agent/crt_ledger.py` — already distinguishes `temporal` from `conflict`
4. **`context_json`** field in memories — exists but unused for domain tagging

---

## Phase 2.0 Architecture

### New Fact Schema

```python
@dataclass
class ContextualFact:
    slot: str                           # "employer", "occupation", etc.
    value: Any                          # "Google", "photographer", etc.
    normalized: str                     # Lowercase for comparison
    
    # Temporal metadata
    temporal_status: str = "active"     # past | active | future | potential
    valid_from: Optional[float] = None  # Unix timestamp
    valid_until: Optional[float] = None # Unix timestamp (None = ongoing)
    period_text: Optional[str] = None   # Human-readable: "2020-2024"
    
    # Domain context
    domains: List[str] = field(default_factory=list)  # ["print_shop", "freelance"]
    
    # Provenance
    source_memory_id: Optional[str] = None
    confidence: float = 0.9
    last_confirmed: Optional[float] = None  # When user reaffirmed this fact
```

### Multi-Value Slot Storage

```python
# Old: Single value overwrites
facts = {"employer": "Google"}

# New: Array with metadata
facts = {
    "employers": [
        {
            "value": "Walmart",
            "status": "past",
            "period": "2018-2020",
            "domains": ["retail"],
            "confidence": 0.95
        },
        {
            "value": "Print Shop",
            "status": "active", 
            "period": "2020-present",
            "domains": ["print_shop", "small_business"],
            "role": "owner",
            "confidence": 0.98
        },
        {
            "value": "Freelance",
            "status": "active",
            "period": "2019-present",
            "domains": ["photography", "videography", "web_dev"],
            "confidence": 0.90
        }
    ]
}
```

---

## Implementation Steps

### Step 1: Extend ExtractedFact Schema
**File:** `personal_agent/fact_slots.py`

Add temporal and domain fields to `ExtractedFact`:
```python
@dataclass(frozen=True)
class ExtractedFact:
    slot: str
    value: Any
    normalized: str
    temporal_status: str = "active"      # NEW
    period_text: Optional[str] = None    # NEW
    domains: Tuple[str, ...] = ()        # NEW (tuple for frozen)
```

### Step 2: Add Temporal Pattern Extraction
**File:** `personal_agent/fact_slots.py`

Extract temporal markers from input:
```python
TEMPORAL_PATTERNS = [
    (r"(?:i\s+)?(?:used to|formerly|previously)\s+", "past"),
    (r"(?:i\s+)?(?:no longer|don't|stopped|quit|left)\s+", "past"),
    (r"(?:i\s+)?(?:currently|now|presently)\s+", "active"),
    (r"(?:i\s+)?(?:will|plan to|going to|might)\s+", "future"),
    (r"from\s+(\d{4})\s*(?:to|-)?\s*(\d{4}|present)?", "period"),
]
```

### Step 3: Add Domain Detection Module
**File:** `personal_agent/domain_detector.py` (NEW)

```python
DOMAIN_KEYWORDS = {
    "print_shop": ["sticker", "print", "vinyl", "decal", "order", "customer"],
    "photography": ["photo", "shoot", "camera", "editing", "wedding", "portrait"],
    "videography": ["video", "film", "footage", "editing", "youtube"],
    "programming": ["code", "programming", "developer", "software", "app", "website"],
    "web_dev": ["website", "html", "css", "frontend", "backend", "deploy"],
    "retail": ["store", "customer", "inventory", "register", "shift"],
}

def detect_domains(text: str) -> List[str]:
    """Detect relevant domains from text content."""
    text_lower = text.lower()
    domains = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            domains.append(domain)
    return domains or ["general"]
```

### Step 4: Update Memory Schema
**File:** `personal_agent/crt_memory.py`

Add columns to `memories` table:
```sql
ALTER TABLE memories ADD COLUMN temporal_status TEXT DEFAULT 'active';
ALTER TABLE memories ADD COLUMN valid_from REAL;
ALTER TABLE memories ADD COLUMN valid_until REAL;
ALTER TABLE memories ADD COLUMN domain_tags TEXT;  -- JSON array
```

### Step 5: Update Fact Storage Logic
**File:** `personal_agent/crt_rag.py`

When storing facts:
1. Detect temporal status from input patterns
2. Detect domains from input content
3. Store as multi-value (don't overwrite existing values for same slot)
4. Mark old values as `status: past` instead of deleting

### Step 6: Update Contradiction Rules
**File:** `personal_agent/crt_core.py`

New contradiction logic:
```python
def is_true_contradiction(self, old_fact: ContextualFact, new_fact: ContextualFact) -> bool:
    """
    Only flag contradiction if:
    1. Same slot
    2. Overlapping time periods (or both active)
    3. Same or overlapping domains
    4. Mutually exclusive values
    """
    # Different slots = not contradiction
    if old_fact.slot != new_fact.slot:
        return False
    
    # Both past = historical, not current contradiction
    if old_fact.temporal_status == "past" and new_fact.temporal_status == "past":
        return False
    
    # Different domains = can coexist
    if not set(old_fact.domains) & set(new_fact.domains):
        return False
    
    # New says "no longer X" = temporal update, not contradiction
    if new_fact.temporal_status == "past" and old_fact.value == new_fact.value:
        return False  # Just updating status
    
    # Same slot, same domain, overlapping time, different value = TRUE CONTRADICTION
    return True
```

### Step 7: Update Retrieval for Context Awareness
**File:** `personal_agent/crt_memory.py`

Add domain filtering to retrieval:
```python
def recall(self, query_vector, k=5, relevant_domains=None, temporal_filter="active"):
    """
    Retrieve memories weighted by:
    - Semantic similarity
    - Domain relevance (boost if matches)
    - Temporal status (filter or weight)
    - Recency
    """
    # ... existing similarity logic ...
    
    if relevant_domains:
        # Boost memories that match query domain
        for mem in candidates:
            if set(mem.domains) & set(relevant_domains):
                mem.score *= 1.5  # Domain match boost
    
    if temporal_filter == "active":
        candidates = [m for m in candidates if m.temporal_status == "active"]
    
    return sorted(candidates, key=lambda m: m.score, reverse=True)[:k]
```

### Step 8: Query Disambiguation
**File:** `personal_agent/crt_rag.py`

When query is ambiguous:
```python
def disambiguate_query(self, query: str, user_facts: Dict) -> Optional[str]:
    """
    If query references something that exists in multiple domains,
    ask for clarification.
    """
    detected_domains = detect_domains(query)
    
    if "job" in query.lower() or "order" in query.lower():
        # Check if user has multiple "job" contexts
        employers = user_facts.get("employers", [])
        active_employers = [e for e in employers if e["status"] == "active"]
        
        if len(active_employers) > 1 and len(detected_domains) == 0:
            return "I see you have multiple active work contexts. Are you asking about your print shop, freelance work, or something else?"
    
    return None  # No disambiguation needed
```

---

## Migration Strategy

### Phase 2.0a: Schema Extension (Non-Breaking)
1. Add new columns to existing tables (nullable)
2. New facts get temporal/domain metadata
3. Old facts default to `status: active`, `domains: ["general"]`

### Phase 2.0b: Extraction Enhancement
1. Update `extract_fact_slots()` to detect temporal patterns
2. Add `detect_domains()` to fact extraction pipeline
3. Store multi-value facts without breaking existing logic

### Phase 2.0c: Contradiction Rules Update
1. Update `detect_contradiction()` to use new rules
2. Add `is_true_contradiction()` check before flagging
3. Existing tests should still pass (stricter rules = fewer false contradictions)

### Phase 2.0d: Retrieval Enhancement
1. Add domain-weighted retrieval
2. Add temporal filtering
3. Add query disambiguation prompts

---

## Success Criteria

- [ ] "I don't work at Walmart anymore" → Updates Walmart to `status: past`, no contradiction flagged
- [ ] "I'm a photographer AND a programmer" → Both stored, no conflict
- [ ] "What's my most recent order?" → System asks for domain clarification or uses recent context
- [ ] "I worked at Google from 2020-2024" → Stores with period metadata
- [ ] Existing contradiction tests still pass (no regression)
- [ ] Stress test score ≥80% maintained

---

## Files to Modify

| File | Changes |
|------|---------|
| `personal_agent/fact_slots.py` | Extended `ExtractedFact`, temporal patterns |
| `personal_agent/domain_detector.py` | NEW - domain detection logic |
| `personal_agent/crt_memory.py` | Schema updates, domain-aware retrieval |
| `personal_agent/crt_core.py` | `is_true_contradiction()` with context rules |
| `personal_agent/crt_rag.py` | Multi-value storage, query disambiguation |
| `personal_agent/crt_ledger.py` | Temporal contradiction type handling |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking existing tests | Phase 2.0a is additive-only, new fields are nullable |
| Performance impact | Domain detection is keyword-based, O(n) cheap |
| Over-disambiguation | Only prompt when truly ambiguous (multiple active same-slot values) |
| Migration complexity | Old facts get sensible defaults, no data loss |

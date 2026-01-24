# Two-Tier Fact Extraction System

## Overview

The CRT system now uses a **two-tier fact extraction architecture** that combines the precision of regex-based extraction with the flexibility of LLM-based extraction.

## Architecture

### Tier A: Hard Slots (Regex-Based)
- **Purpose:** Extract critical, high-stakes facts that require deterministic precision
- **Method:** Regex pattern matching
- **Coverage:** 20+ predefined slots
- **Examples:**
  - Identity: name, age
  - Employment: employer, title, occupation
  - Location: location, undergrad_school, masters_school
  - Medical/Legal: medical_diagnosis, legal_status, relationship_status

### Tier B: Open Tuples (LLM-Based)
- **Purpose:** Extract flexible, open-world facts beyond predefined patterns
- **Method:** LLM extraction with confidence scoring
- **Coverage:** Arbitrary fact types
- **Examples:**
  - Hobbies and interests
  - Preferences and goals
  - Custom domain facts
  - Temporal states

## Integration Points

### 1. CRT RAG Engine (`personal_agent/crt_rag.py`)
```python
# Two-tier system initialized in __init__
self.two_tier_system = TwoTierFactSystem(enable_llm=True)

# New method for two-tier extraction
result = self._extract_facts_two_tier(text, skip_llm=False)
# Returns: TwoTierExtractionResult with hard_facts and open_tuples
```

### 2. Contradiction Ledger (`personal_agent/crt_ledger.py`)
```python
# Ledger receives two-tier system from RAG
ledger.set_two_tier_system(two_tier_system)

# Enhanced fact extraction for contradiction detection
facts = ledger._extract_all_facts(text)
# Returns: Combined dict of hard facts + high-confidence open tuples
```

### 3. API Endpoint (`crt_api.py`)
```
POST /api/facts/extract
{
  "text": "I work at Microsoft and my hobby is pottery",
  "skip_llm": false
}

Response:
{
  "hard_facts": {
    "employer": {
      "slot": "employer",
      "value": "Microsoft",
      "normalized": "microsoft",
      "tier": "hard",
      "source": "regex",
      "confidence": 1.0
    }
  },
  "open_tuples": [
    {
      "slot": "hobby",
      "value": "pottery",
      "normalized": "pottery",
      "tier": "open",
      "source": "llm",
      "confidence": 0.85
    }
  ],
  "extraction_time": 0.123,
  "methods_used": ["regex", "llm"]
}
```

## Graceful Degradation

The system is designed to work seamlessly with or without LLM access:

1. **LLM Available:** Full two-tier extraction (hard slots + open tuples)
2. **LLM Unavailable:** Falls back to regex-only extraction (hard slots only)
3. **Skip LLM:** Set `skip_llm=True` for faster, deterministic extraction

## Benefits

### Precision + Flexibility
- Critical facts (name, employer) maintain 100% deterministic extraction
- Flexible facts (hobbies, preferences) gain LLM understanding
- No risk of LLM hallucination corrupting hard facts

### Enhanced Contradiction Detection
- Contradictions detected across both fact tiers
- Open tuples can flag conflicts in previously unstructured data
- Shared slots identified across hard facts and open tuples

### Performance Optimization
- Regex tier is instant (<1ms per text)
- LLM tier is optional and skippable
- Caching available for repeated extractions

## Usage Examples

### Basic Extraction
```python
from personal_agent.two_tier_facts import TwoTierFactSystem

system = TwoTierFactSystem(enable_llm=True)
result = system.extract_facts("I'm Sarah, I work at Google and my hobby is pottery.")

print(result.hard_facts)  # {'name': ..., 'employer': ...}
print(result.open_tuples)  # [FactTuple(hobby=pottery)]
```

### Fast Regex-Only
```python
result = system.extract_facts(text, skip_llm=True)
# Only hard_facts populated, open_tuples will be empty
```

### Via API
```bash
curl -X POST http://localhost:8123/api/facts/extract \
  -H "Content-Type: application/json" \
  -d '{"text": "I work at Microsoft in Seattle", "skip_llm": false}'
```

## Configuration

### Hard Slots (Tier A)
Defined in `TwoTierFactSystem.HARD_SLOTS`:
- Identity: name
- Employment: employer, title, occupation
- Location: location
- Medical/Legal: medical_diagnosis, account_status, legal_status, relationship_status
- Education: undergrad_school, masters_school, school, graduation_year
- Core profile: age, programming_years, first_language

### Regex-Only Slots
Some slots NEVER use LLM (too critical for any uncertainty):
- name
- age
- graduation_year

### LLM Configuration
```python
system = TwoTierFactSystem(
    enable_llm=True,  # Enable/disable LLM tier
    llm_confidence_threshold=0.6,  # Min confidence for open tuples
    use_local_llm=True  # Use Ollama instead of OpenAI
)
```

## Design Philosophy

### Why Two Tiers?

**The Problem:**
- Regex alone: High precision, but limited coverage
- LLM alone: High coverage, but can hallucinate critical facts

**The Solution:**
- Use regex for facts where precision is critical (identity, medical, legal)
- Use LLM for facts where flexibility matters (hobbies, preferences, goals)
- Never mix: Hard slots always use regex, open tuples always use LLM

### Contradiction Handling

Both tiers participate in contradiction detection:

```
Hard Slot Contradiction:
  Old: "I work at Microsoft" (regex)
  New: "I work at Amazon" (regex)
  → Detected via shared "employer" slot

Open Tuple Contradiction:
  Old: "My hobby is woodworking" (LLM)
  New: "My hobby is pottery" (LLM)
  → Detected via shared "hobby" attribute

Mixed Contradiction:
  Old: "I work at Microsoft" (regex, hard slot)
  New: "I work at Amazon" (LLM, open tuple with high confidence)
  → Both contribute to contradiction detection
```

## Implementation Status

### ✅ Complete
- [x] Two-tier system exists (`personal_agent/two_tier_facts.py`)
- [x] Integrated into CRT RAG engine
- [x] Integrated into contradiction ledger
- [x] API endpoint for fact extraction
- [x] Graceful degradation (LLM optional)
- [x] Documentation updated

### 🔄 Optional Enhancements
- [ ] Persist open tuples in memory storage (currently only in-memory)
- [ ] Add UI visualization for fact tiers
- [ ] Fine-tune LLM confidence thresholds
- [ ] Add more hard slots based on domain needs

## Testing

Run the two-tier system tests:
```bash
pytest tests/test_architecture_changes.py::TestTwoTierFactSystem -v
```

Test the API endpoint:
```bash
curl -X POST http://localhost:8123/api/facts/extract \
  -H "Content-Type: application/json" \
  -d '{"text": "I am Nick, I work at Microsoft in Seattle and I love hiking", "skip_llm": false}'
```

## Troubleshooting

### LLM Not Available
- **Symptom:** `open_tuples` always empty, `methods_used` includes `"regex_fallback"`
- **Cause:** LLM client not configured or unavailable
- **Solution:** Check Ollama is running or OpenAI API key is set

### Low Confidence Tuples
- **Symptom:** Expected open tuples not returned
- **Cause:** LLM confidence below threshold (default 0.6)
- **Solution:** Lower threshold in `TwoTierFactSystem(llm_confidence_threshold=0.5)`

### Duplicate Facts
- **Symptom:** Same fact appears in both hard_facts and open_tuples
- **Cause:** This shouldn't happen (design prevents it)
- **Solution:** Report as bug - hard slots are filtered from open tuples

## Future Work

1. **Persistent Storage:** Store open tuples alongside hard facts in memory DB
2. **Hybrid Extraction:** Use LLM to verify/enhance regex extractions
3. **Active Learning:** Learn which facts benefit from LLM vs regex over time
4. **Domain Adaptation:** Allow custom hard slot definitions per domain
5. **Multi-Modal:** Extend to images, audio (e.g., extract facts from photos)

## Related Documentation

- [CRT_WHITEPAPER.md](CRT_WHITEPAPER.md) - Full CRT architecture
- [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) - All documentation
- `personal_agent/two_tier_facts.py` - Implementation
- `tests/test_architecture_changes.py` - Tests

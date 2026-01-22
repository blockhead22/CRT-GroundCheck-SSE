# Contradiction-Aware Grounding

## Overview

This document describes the contradiction-aware grounding feature added to GroundCheck - a novel contribution that differentiates it from existing grounding systems like SelfCheckGPT, CoVe, and RARR.

## Problem Statement

**Current grounding systems assume retrieved context is consistent.**

They answer: "Is this claim supported by ANY memory?"

**They fail when memories contradict each other:**

```python
# Real-world scenario:
memories = [
    Memory(id="m1", text="User works at Microsoft", timestamp=1704067200, trust=0.9),
    Memory(id="m2", text="User works at Amazon", timestamp=1706745600, trust=0.9)
]

query = "Where do you work?"
output = "You work at Amazon"

# SelfCheckGPT:  ✅ Grounded (Amazon is in memory)
# CoVe:          ✅ Grounded (found Amazon in context)
# RARR:          ✅ Grounded (retrieval found Amazon)

# GroundCheck (NEW):  
#   ✅ Grounded (Amazon is in memory)
#   ⚠️  Contradicted (conflicts with Microsoft memory)
#   ❌ Requires disclosure (must acknowledge both facts)
#   📝 Expected: "You work at Amazon (changed from Microsoft in Feb 2024)"
```

## Solution

GroundCheck now detects and handles contradictions in three steps:

### 1. Contradiction Detection

Identifies when multiple memories have the same **mutually exclusive** fact slot but different values:

```python
from groundcheck import GroundCheck, Memory

verifier = GroundCheck()
memories = [
    Memory(id="m1", text="User works at Microsoft", trust=0.9, timestamp=1704067200),
    Memory(id="m2", text="User works at Amazon", trust=0.9, timestamp=1706745600)
]

result = verifier.verify("You work at Amazon", memories)

# Contradiction detected!
assert len(result.contradiction_details) == 1
assert result.contradiction_details[0].slot == "employer"
assert set(result.contradiction_details[0].values) == {"microsoft", "amazon"}
```

**Mutually Exclusive Slots** (contradictory):
- `employer` - Can only work at one place at a time
- `location` - Can only live in one place at a time
- `name`, `title`, `occupation`, etc.

**Additive Slots** (complementary):
- `programming_language` - Can know multiple languages
- `skills`, `hobbies`, etc.

### 2. Disclosure Verification

Checks if the generated output acknowledges contradictions:

```python
# ❌ FAILS - No disclosure
result = verifier.verify("You work at Amazon", memories)
assert result.passed == False
assert result.requires_disclosure == True

# ✅ PASSES - Proper disclosure
result = verifier.verify(
    "You work at Amazon. You previously worked at Microsoft.",
    memories
)
assert result.passed == True
assert result.requires_disclosure == False
```

**Recognized Disclosure Patterns:**
- "changed from X to Y"
- "previously X, now Y"
- "used to X, now Y"
- "was X, is now Y"
- "moved from X to Y"

### 3. Automatic Correction

In strict mode, generates corrections with disclosure:

```python
result = verifier.verify("You work at Amazon", memories, mode="strict")

print(result.corrected)
# Output: "You work at Amazon (changed from microsoft)"
```

## Trust-Based Filtering

Low-trust memories don't require disclosure:

```python
memories = [
    Memory(id="m1", text="User works at Microsoft", trust=0.2),   # Very low
    Memory(id="m2", text="User works at Amazon", trust=0.95)      # High
]

result = verifier.verify("You work at Amazon", memories)

# Trust difference = 0.75 > threshold (0.5)
assert result.passed == True  # No disclosure needed
assert result.requires_disclosure == False
```

**Threshold**: `GroundCheck.TRUST_DIFFERENCE_THRESHOLD = 0.5`

## API Reference

### ContradictionDetail

```python
@dataclass
class ContradictionDetail:
    """Details about a contradiction between memories."""
    slot: str                         # Fact slot (e.g., "employer")
    values: List[str]                 # Contradicting values
    memory_ids: List[str]             # Memory IDs
    timestamps: List[Optional[int]]   # Unix timestamps
    trust_scores: List[float]         # Trust scores
    
    @property
    def most_recent_value(self) -> str:
        """Value from most recent memory (by timestamp or trust)."""
    
    @property
    def most_trusted_value(self) -> str:
        """Value from most trusted memory."""
```

### VerificationReport (Enhanced)

```python
@dataclass
class VerificationReport:
    # ... existing fields ...
    
    # NEW: Contradiction fields
    contradicted_claims: List[str]                      # Claims using contradicted facts
    contradiction_details: List[ContradictionDetail]    # Full contradiction info
    requires_disclosure: bool                           # True if disclosure needed
    expected_disclosure: Optional[str]                  # Suggested disclosure text
```

### GroundCheck (Enhanced)

```python
class GroundCheck:
    # Configuration
    MUTUALLY_EXCLUSIVE_SLOTS: Set[str]      # Contradictory fact slots
    TRUST_DIFFERENCE_THRESHOLD: float       # Trust diff threshold (0.5)
    
    def verify(
        self,
        generated_text: str,
        retrieved_memories: List[Memory],
        mode: str = "strict"
    ) -> VerificationReport:
        """
        Verify grounding with contradiction awareness.
        
        Now also:
        - Detects contradictions in memories
        - Checks if contradictions are disclosed
        - Generates disclosure suggestions
        """
```

## Examples

### Basic Usage

```python
from groundcheck import GroundCheck, Memory

verifier = GroundCheck()

# Example 1: Undisclosed contradiction (fails)
memories = [
    Memory(id="m1", text="User works at Microsoft", timestamp=1704067200, trust=0.85),
    Memory(id="m2", text="User works at Amazon", timestamp=1706745600, trust=0.85)
]

result = verifier.verify("You work at Amazon", memories)
print(result.passed)              # False
print(result.requires_disclosure) # True
print(result.expected_disclosure) # "Amazon (changed from microsoft)"

# Example 2: Disclosed contradiction (passes)
result = verifier.verify(
    "You work at Amazon. You previously worked at Microsoft.",
    memories
)
print(result.passed)              # True
print(result.requires_disclosure) # False
```

### Complete Demo

Run the comprehensive demo:

```bash
cd groundcheck
python examples/contradiction_demo.py
```

## Testing

### Test Suite

20 new tests covering:
- Contradiction detection (5 tests)
- Disclosure verification (4 tests)
- Edge cases (5 tests)
- Properties (3 tests)
- Integration (3 tests)

Run tests:
```bash
cd groundcheck
pytest tests/test_contradiction_aware.py -v
```

### Benchmark

Test against GroundingBench contradictions category:

```bash
cd groundcheck
python tests/test_benchmark_contradictions.py
```

**Current Performance**: 50% (5/10)

**Known Limitations**:
- Substring matching treats "Software Engineer" and "Senior Software Engineer" as equivalent
- Some correction patterns not captured by fact extractor
- Trust threshold may need domain-specific tuning

## Comparison with Other Systems

| Feature | GroundCheck | SelfCheckGPT | CoVe | RARR |
|---------|------------|--------------|------|------|
| Grounding verification | ✅ | ✅ | ✅ | ✅ |
| Contradiction detection | ✅ | ❌ | ❌ | ❌ |
| Disclosure verification | ✅ | ❌ | ❌ | ❌ |
| Disclosure generation | ✅ | ❌ | ❌ | ❌ |
| Trust-based filtering | ✅ | ❌ | ❌ | ❌ |

## Novel Contribution

**This is the first grounding system that:**
1. Detects contradictions in retrieved context
2. Verifies proper disclosure in generated outputs
3. Automatically generates disclosure suggestions
4. Filters low-trust contradictions

This makes GroundCheck suitable for real-world conversational AI systems where:
- User information changes over time
- Multiple sources may conflict
- Transparency about conflicts is critical

## Future Improvements

1. **Better fact extraction**: Capture more patterns (e.g., "Actually, I meant X not Y")
2. **Smarter matching**: Handle substring cases better (e.g., job title progressions)
3. **Configurable slots**: Allow domain-specific mutually exclusive slots
4. **Temporal reasoning**: Better understanding of fact evolution over time
5. **Multi-value contradictions**: Handle cases with 3+ conflicting values

## License

MIT License - See LICENSE file for details.

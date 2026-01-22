# Method: GroundCheck

GroundCheck verifies that LLM outputs are grounded in retrieved context while explicitly handling contradictions. The system operates in three stages:

## Stage 1: Fact Extraction

We extract facts from both the generated output and retrieved memories using slot-based fact extraction:

**Fact Slots:** Predefined categories like `employer`, `location`, `preference`, `title`, etc.

**Extraction Algorithm:**
1. Parse text using pattern matching and named entity recognition
2. Normalize values (lowercase, remove articles)
3. Create `ExtractedFact` objects with slot, value, and normalized form

**Example:**
- Input: "You work at Microsoft"
- Extracted: `ExtractedFact(slot="employer", value="Microsoft", normalized="microsoft")`

## Stage 2: Contradiction Detection

GroundCheck identifies contradictions by comparing facts across memories:

**Contradiction Definition:** Two memories contradict if they assign different values to the same fact slot for the same entity.

**Resolution Strategy:**
1. **Timestamp-based:** Use most recent memory if timestamps available
2. **Trust-based:** Use highest trust score if no timestamps
3. **Source-based:** Prioritize user-stated facts over system inferences

**Example:**
```
Memory 1 (t=100): "User works at Microsoft" (trust=0.8)
Memory 2 (t=200): "User works at Amazon" (trust=0.9)
→ Contradiction detected, resolve to "Amazon" (most recent)
```

## Stage 3: Disclosure Verification

For outputs that use contradicted facts, GroundCheck verifies appropriate acknowledgment:

**Disclosure Types:**
- **Temporal change:** "You work at Amazon (moved from Microsoft)"
- **Correction:** "You work at Google (corrected from Microsoft)"
- **Uncertainty:** "Your graduation year is unclear (conflicting dates)"

**Verification Algorithm:**
1. Check if output uses a contradicted fact
2. If yes, verify that output acknowledges the contradiction
3. If no acknowledgment, set `requires_disclosure=True` and provide suggested text

## Verification Modes

GroundCheck supports two modes:

1. **Report Mode (default):** Flag issues, return `VerificationReport`
2. **Strict Mode:** Auto-correct hallucinations and add disclosures

## Complexity

- **Time:** O(m × f) where m = memories, f = avg facts per memory
- **Space:** O(m × f) for fact storage
- **No LLM calls:** Purely deterministic algorithm

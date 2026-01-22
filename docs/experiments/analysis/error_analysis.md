# Error Analysis

This document analyzes errors made by each grounding verification system on GroundingBench.

## GroundCheck Errors

### Partial Grounding (60% error rate)

**Challenge:** Determining whether partially grounded outputs should pass or fail.

**Example Error:**
- Context: "User works at Microsoft"
- Output: "You work at Microsoft in Seattle"
- GroundCheck: Fails (flags "Seattle" as hallucination)
- Label: Depends on interpretation

**Root cause:** Conservative approach flags any unsupported fact as hallucination.

**Potential fix:** Allow partial grounding with explicit acknowledgment of what's known vs unknown.

### Paraphrasing (30% error rate)

**Challenge:** Exact matching doesn't capture semantic equivalence.

**Example Errors:**
1. "Software Engineer" vs "developer" or "SWE"
2. "lives in Seattle" vs "Seattle resident"
3. "works at" vs "employed by"

**Root cause:** Deterministic string matching with limited normalization.

**Potential fix:** Add semantic similarity scoring while maintaining speed.

---

## SelfCheckGPT Errors

### Contradiction Blindness (70% error rate on contradictions)

**Challenge:** Checks output consistency, not context consistency.

**Example Error:**
- Context: ["User works at Microsoft", "User works at Amazon"]
- Output: "You work at Microsoft"
- SelfCheckGPT: Passes (found in context)
- Correct: Should require disclosure or use most recent

**Root cause:** Assumes if a fact appears in ANY memory, it's valid.

**Why it happens:** SelfCheckGPT samples multiple LLM outputs and checks consistency. It doesn't analyze the retrieved context for contradictions.

### False Negatives on Temporal Changes

**Example Error:**
- Context: ["Favorite food: pizza" (t=100), "Favorite food: sushi" (t=200)]
- Output: "Your favorite food is pizza"
- SelfCheckGPT: Passes
- Correct: Fail (outdated information)

**Root cause:** No temporal reasoning.

---

## CoVe Errors

### Independent Verification Problem (65% error rate on contradictions)

**Challenge:** Verifies each claim independently without cross-checking.

**Example Error:**
- Context: ["Works at Microsoft", "Works at Amazon"]
- Generated: "You work at Amazon"
- CoVe verification:
  - Q: "Does user work at Amazon?"
  - A: "Yes" (found in context)
  - Result: Pass
- Correct: Should detect contradiction and require disclosure

**Root cause:** Verification questions don't check for conflicting information.

### Question Generation Errors

**Example Error:**
- Claim: "You work at Google"
- Generated question: "Where does the user work?"
- Answer: "Microsoft" OR "Amazon" (depending on which memory is checked)
- Result: Inconsistent verification

**Root cause:** LLM-based question generation and answering can be non-deterministic.

---

## Vanilla RAG Errors

### Complete Failure (100% error rate on contradictions)

**No verification mechanism:** Always assumes outputs are grounded if any memories exist.

**Example Errors:**
- Any contradiction: Always passes
- Any hallucination: Always passes
- Any partial grounding: Always passes

**Root cause:** No grounding verification at all.

---

## Cross-System Comparison

### Error Distribution by Category

| System | Factual | Contradictions | Partial | Paraphrase | Multi-hop |
|--------|---------|----------------|---------|------------|-----------|
| GroundCheck | 20% | 10% | 60% | 30% | 0% |
| SelfCheckGPT | 15% | 70% | 25% | 20% | 15% |
| CoVe | 17% | 65% | 30% | 25% | 18% |
| Vanilla RAG | 50% | 100% | 60% | 55% | 45% |

### Key Insights

1. **Contradiction handling is the differentiator:**
   - GroundCheck: 10% error rate
   - Baselines: 65-100% error rate

2. **Trade-off in partial grounding:**
   - GroundCheck is more conservative (60% error)
   - Baselines are more permissive (25-30% error)

3. **Paraphrasing is challenging for deterministic methods:**
   - GroundCheck: 30% error (exact matching)
   - Baselines: 20-25% error (semantic similarity via LLM)

---

## Recommendations

### For GroundCheck

1. **Add semantic similarity module** for paraphrasing
2. **Develop partial grounding strategy** with explicit uncertainty acknowledgment
3. **Expand fact slot coverage** with learned extraction

### For Baselines

1. **Add explicit contradiction detection** to SelfCheckGPT and CoVe
2. **Implement temporal reasoning** for time-based resolution
3. **Cross-check verification answers** in CoVe to detect conflicts

### For Benchmark

1. **Add more partial grounding examples** with clear ground truth
2. **Include paraphrasing difficulty labels** (easy/medium/hard)
3. **Create ablation categories** to isolate specific capabilities

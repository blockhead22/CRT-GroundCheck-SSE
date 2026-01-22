# Error Report Templates

## Overview

This file provides standardized templates for documenting errors encountered during user research. Use these templates to ensure consistency and completeness in error reporting.

## Template 1: Basic Error Report

```markdown
## Error Report: [ERROR_ID]

**Date:** [YYYY-MM-DD]
**Reporter:** [Name or ID]
**Severity:** [Critical | High | Medium | Low]
**Type:** [False Negative | False Positive | Performance | Other]

### Context
- Memory: "[memory content]"
- Generated: "[generated text]"
- Verification Result: [Pass | Fail | Partial]

### Expected Behavior
[What should have happened]

### Actual Behavior
[What actually happened]

### Impact
[How this affects users]

### Reproduction Steps
1. [Step 1]
2. [Step 2]
3. [Step 3]

### Suggested Fix
[Optional: Ideas for fixing]
```

## Template 2: Paraphrasing Error Report

```markdown
## Paraphrasing Error: [ERROR_ID]

**Date:** [YYYY-MM-DD]
**Category:** Semantic Matching
**Error Type:** [False Negative | False Positive]

### Paraphrase Pair
- **Original:** "[memory text]"
- **Paraphrase:** "[generated text]"
- **Similarity Score:** [If available, e.g., 0.82]
- **Threshold:** [e.g., 0.85]

### Analysis
- **Should Match:** [Yes | No]
- **Did Match:** [Yes | No]
- **Why Error Occurred:** [Hypothesis]

### Similar Cases
1. [Related error 1]
2. [Related error 2]

### Recommended Threshold Adjustment
- Current: [0.85]
- Suggested: [0.80]
- Rationale: [Explanation]
```

## Template 3: Compound Value Error Report

```markdown
## Compound Value Error: [ERROR_ID]

**Date:** [YYYY-MM-DD]
**Category:** Compound Splitting

### Input
- **Memory Facts:**
  - Fact 1: "[text]"
  - Fact 2: "[text]"
- **Generated Statement:** "[compound statement]"
- **Separator Used:** [comma | and | or | slash | semicolon]

### Splitting Result
- **Expected Split:** [list1, list2, list3]
- **Actual Split:** [actual1, actual2, actual3]

### Grounding Result
- **Expected Grounded:** [items]
- **Actual Grounded:** [items]
- **Expected Hallucinations:** [items]
- **Actual Hallucinations:** [items]

### Error Analysis
[Explain what went wrong with splitting or matching]

### Fix Needed
[Pattern to add, logic to change, etc.]
```

## Template 4: User-Reported Issue

```markdown
## User Report: [REPORT_ID]

**Date:** [YYYY-MM-DD]
**User ID:** [Anonymous or ID]
**Channel:** [Form | Email | Interview | Log]

### User Description
"[User's description in their own words]"

### Researcher Interpretation
[What we understand the issue to be]

### Reproducible Test Case
- Memory: "[text]"
- Generated: "[text]"
- Expected: [result]
- Actual: [result]

### Severity Assessment
- **Impact:** [How bad is this?]
- **Frequency:** [How often does this happen?]
- **Workaround:** [Any workaround available?]

### Status
- [ ] Acknowledged
- [ ] Reproduced
- [ ] Root cause identified
- [ ] Fix implemented
- [ ] Verified
- [ ] User notified
```

## Template 5: Batch Error Report

```markdown
## Batch Error Analysis: [BATCH_ID]

**Date:** [YYYY-MM-DD]
**Sample Size:** [N errors]
**Time Period:** [date range]
**Version:** [Pre-upgrade | Post-upgrade]

### Summary Statistics
- Total Errors: [N]
- False Negatives: [N] ([%])
- False Positives: [N] ([%])
- Performance Issues: [N] ([%])
- Other: [N] ([%])

### Top Error Patterns

#### Pattern 1: [Pattern Name]
- **Frequency:** [N occurrences]
- **Example:** [One example]
- **Root Cause:** [Hypothesis]
- **Impact:** [High | Medium | Low]

#### Pattern 2: [Pattern Name]
- **Frequency:** [N occurrences]
- **Example:** [One example]
- **Root Cause:** [Hypothesis]
- **Impact:** [High | Medium | Low]

#### Pattern 3: [Pattern Name]
- **Frequency:** [N occurrences]
- **Example:** [One example]
- **Root Cause:** [Hypothesis]
- **Impact:** [High | Medium | Low]

### Comparison to Previous Batch
- Error rate change: [+/- X%]
- New error types: [List]
- Resolved error types: [List]

### Recommendations
1. [Recommendation 1]
2. [Recommendation 2]
3. [Recommendation 3]
```

## Template 6: Performance Issue Report

```markdown
## Performance Issue: [PERF_ID]

**Date:** [YYYY-MM-DD]
**Category:** Performance
**Metric:** [Latency | Memory | Throughput]

### Measurements
- **Target:** [e.g., <20ms latency]
- **Observed:** [e.g., 150ms latency]
- **Environment:** [Hardware, software details]

### Test Conditions
- Input size: [e.g., 10 memory facts, 200-word generation]
- Model loaded: [Yes | No]
- Concurrent requests: [N]

### Performance Breakdown
- Fact extraction: [Xms]
- Semantic matching: [Xms]
- Other processing: [Xms]
- Total: [Xms]

### Root Cause
[What's causing the slowdown?]

### Optimization Ideas
1. [Idea 1]
2. [Idea 2]
3. [Idea 3]
```

## Template 7: Edge Case Report

```markdown
## Edge Case: [EDGE_ID]

**Date:** [YYYY-MM-DD]
**Category:** Edge Case
**Subcategory:** [Negation | Temporal | Multi-word | Other]

### Case Description
[Describe the unusual scenario]

### Example
- Memory: "[text]"
- Generated: "[text]"
- Expected: [result]
- Actual: [result]
- Why it's an edge case: [Explanation]

### Frequency Estimate
[How common is this edge case?]
- Very Rare (<0.1%)
- Rare (0.1-1%)
- Occasional (1-5%)
- Common (>5%)

### Handling Strategy
- [ ] Add special logic to handle
- [ ] Document as known limitation
- [ ] Acceptable failure (explain why)
- [ ] Needs further research

### Related Edge Cases
1. [Similar case 1]
2. [Similar case 2]
```

## Usage Guidelines

### When to Use Each Template

1. **Basic Error Report:** General-purpose, when unsure which template to use
2. **Paraphrasing Error:** Specifically for semantic matching issues
3. **Compound Value Error:** For list splitting and partial grounding issues
4. **User-Reported Issue:** When users report problems directly
5. **Batch Error Analysis:** For analyzing groups of errors together
6. **Performance Issue:** For latency, memory, or throughput problems
7. **Edge Case Report:** For unusual or rare scenarios

### Best Practices

1. **Be Specific:** Include exact memory text and generated text
2. **Include Context:** Environment, version, configuration
3. **Quantify Impact:** How many users affected? How often?
4. **Suggest Fixes:** Even rough ideas help prioritization
5. **Link Related Issues:** Cross-reference similar errors
6. **Update Status:** Keep reports current as investigation proceeds

### Error ID Naming Convention

```
[TYPE]-[DATE]-[SEQUENCE]

Examples:
- FN-20260122-001 (False Negative, Jan 22 2026, first of the day)
- FP-20260122-002 (False Positive, Jan 22 2026, second of the day)
- PERF-20260122-001 (Performance issue)
- EDGE-20260122-001 (Edge case)
```

## Quality Checklist

Before submitting an error report, verify:

- [ ] Error ID is unique and follows naming convention
- [ ] Severity is accurately assessed
- [ ] All required fields are filled
- [ ] Example is reproducible
- [ ] Impact is clearly described
- [ ] Root cause hypothesis is included (even if uncertain)
- [ ] Related to paraphrasing upgrade (if applicable)

## Next Steps

1. Choose appropriate template
2. Fill in all sections
3. Review for completeness
4. Submit to error database
5. Notify relevant team members
6. Track until resolution

## References

- [Collection Framework](./collection_framework.md)
- [Experiment Protocol](../benchmarking/experiment_protocol.md)
- [Error Analysis Methods](../analysis/error_classification.md)

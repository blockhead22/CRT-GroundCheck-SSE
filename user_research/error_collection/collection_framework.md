# Error Collection Framework

## Objective

Systematically collect sample errors and paraphrase mismatches from real user data to understand where the paraphrasing upgrade succeeds and where it still fails.

## Overview

This framework provides a structured approach to:
1. Identify and collect paraphrasing errors
2. Categorize error types
3. Prioritize errors by impact
4. Track improvements post-upgrade

## Error Collection Methods

### Method 1: User Reporting
**Description:** Users self-report errors they encounter

**Process:**
1. Provide users with error reporting form
2. Users describe expected vs. actual behavior
3. Collect context (memory, generated text, verification result)
4. Categorize and prioritize

**Advantages:**
- Real-world user perspective
- High-impact errors naturally surface
- Minimal researcher time

**Limitations:**
- Reporting bias (users may not report all errors)
- Inconsistent detail level
- Requires active user base

### Method 2: Automated Log Analysis
**Description:** Parse system logs for verification failures

**Process:**
1. Enable detailed logging in GroundCheck
2. Collect verification results over time
3. Filter for failures or low-confidence matches
4. Sample for manual review

**Advantages:**
- Comprehensive coverage
- No user burden
- Quantifiable error rates

**Limitations:**
- Requires production deployment
- May include false alarms
- Privacy considerations for user data

### Method 3: Synthetic Testing
**Description:** Generate test cases based on common paraphrase patterns

**Process:**
1. Identify common paraphrase types
2. Create synthetic examples
3. Run verification and collect results
4. Document failures

**Advantages:**
- Controlled testing environment
- Complete coverage of known patterns
- Repeatable

**Limitations:**
- May miss real-world edge cases
- Synthetic != authentic user language

### Method 4: Crowdsourced Error Discovery
**Description:** Recruit users specifically to find errors

**Process:**
1. Brief users on error types to look for
2. Provide access to GroundCheck
3. Incentivize error discovery
4. Review and validate reported errors

**Advantages:**
- Active error hunting
- Diverse user perspectives
- Good for edge case discovery

**Limitations:**
- Requires budget for incentives
- Quality control needed
- May find low-priority errors

## Error Documentation Template

For each error, document:

```markdown
## Error Report: [ERROR_ID]

### Basic Information
- **Date Reported:** YYYY-MM-DD
- **Reported By:** [User ID or Anonymous]
- **Environment:** [Pre-upgrade | Post-upgrade | Version X.X]
- **Severity:** [Critical | High | Medium | Low]

### Error Details
**Memory Context:**
```json
{
  "id": "m001",
  "content": "User works at Microsoft",
  "timestamp": "2025-12-01"
}
```

**Generated Text:**
```
You are employed by Microsoft.
```

**Expected Result:**
- Should: Ground "Microsoft" as matching memory m001
- Reason: "employed by" is semantic equivalent of "works at"

**Actual Result:**
- Did: Flagged "Microsoft" as hallucination
- Reason: Semantic matcher threshold too high / not applied

**Error Type:** [False Negative | False Positive | Performance | Other]

### Impact Assessment
- **User Impact:** [How does this affect user experience?]
- **Frequency:** [How often does this occur?]
- **Workaround:** [Is there a workaround?]
- **Business Value:** [Value of fixing this error]

### Root Cause Analysis
- **Hypothesis:** [Why did this error occur?]
- **Contributing Factors:** [Model limitation, threshold setting, edge case, etc.]
- **Related Errors:** [Links to similar errors]

### Proposed Fix
- **Solution:** [How to fix this error]
- **Implementation Effort:** [Low | Medium | High]
- **Risk:** [Potential side effects]

### Follow-up
- **Status:** [New | Investigating | Fixed | Won't Fix]
- **Assigned To:** [Team member]
- **Target Resolution:** [Date or milestone]
```

## Error Categories

### Category 1: Semantic Matching Failures

#### 1.1 False Negatives (Should match, but doesn't)
**Examples:**
- "works at" vs "employed by"
- "lives in" vs "resides in"
- "knows Python" vs "proficient in Python"

**Root Causes:**
- Semantic threshold too high
- Model doesn't recognize paraphrase
- Missing context

#### 1.2 False Positives (Should not match, but does)
**Examples:**
- "works at Microsoft" matches "invests in Microsoft"
- "lives in Seattle" matches "visited Seattle"
- "currently at Google" matches "previously at Google"

**Root Causes:**
- Semantic threshold too low
- Model overestimates similarity
- Context not considered

### Category 2: Compound Value Errors

#### 2.1 Splitting Failures
**Examples:**
- Doesn't split "Python and JavaScript"
- Incorrectly splits "San Francisco" into "San" and "Francisco"
- Mishandles "3-bedroom apartment"

**Root Causes:**
- Incomplete separator patterns
- Named entity recognition needed
- Complex compound structures

#### 2.2 Partial Hallucination Misses
**Examples:**
- Doesn't flag "Ruby" in "Python, JavaScript, and Ruby" when only Python/JavaScript are in memory
- Misses "near waterfront" modifier hallucination

**Root Causes:**
- Fact extraction incomplete
- Granularity mismatch
- Missing attribute patterns

### Category 3: Performance Issues

#### 3.1 Latency Spikes
**Examples:**
- Verification takes >100ms (target <20ms)
- Model loading delays

**Root Causes:**
- Model size
- Inefficient caching
- Hardware limitations

#### 3.2 Memory Consumption
**Examples:**
- High RAM usage with semantic model
- Memory leaks over time

**Root Causes:**
- Model overhead
- Cache not bounded
- Resource leak

### Category 4: Edge Cases

#### 4.1 Negation Handling
**Examples:**
- "likes Python" vs "doesn't like Python" incorrectly match
- "can code" vs "cannot code" confused

**Root Causes:**
- Semantic model ignores negation
- Need negation-aware matching

#### 4.2 Temporal Context
**Examples:**
- "currently works" vs "previously worked" match incorrectly
- "will join" vs "joined" confused

**Root Causes:**
- Tense not considered in similarity
- Need temporal awareness

#### 4.3 Multi-word Entities
**Examples:**
- "New York" split incorrectly
- "Machine Learning Engineer" partially matched

**Root Causes:**
- Need entity recognition
- Word-level vs phrase-level matching

## Error Prioritization Matrix

| Impact | Frequency | Priority | Action |
|--------|-----------|----------|--------|
| High | High | P0 | Fix immediately |
| High | Medium | P1 | Fix in next release |
| High | Low | P2 | Fix when possible |
| Medium | High | P1 | Fix in next release |
| Medium | Medium | P2 | Fix when possible |
| Medium | Low | P3 | Consider for future |
| Low | High | P2 | Fix when possible |
| Low | Medium | P3 | Consider for future |
| Low | Low | P4 | Track but unlikely to fix |

## Collection Workflow

### Phase 1: Setup (Week 1)
1. Configure error logging
2. Prepare reporting forms
3. Brief participants
4. Set up collection database

### Phase 2: Pre-Upgrade Baseline (Week 1)
1. Collect errors from pre-upgrade system
2. Document error patterns
3. Categorize and prioritize
4. Establish baseline error rates

### Phase 3: Post-Upgrade Collection (Weeks 2-3)
1. Deploy upgrade
2. Collect new errors
3. Compare to baseline
4. Identify improvements and regressions

### Phase 4: Analysis (Week 4)
1. Calculate error reduction rates
2. Identify remaining gaps
3. Prioritize future work
4. Document findings

## Data Storage

**Format:** JSON Lines (.jsonl)

**Example:**
```json
{"error_id": "ERR001", "date": "2026-01-22", "severity": "high", "type": "false_negative", "category": "semantic_matching", "memory": "works at Microsoft", "generated": "employed by Microsoft", "expected": "match", "actual": "no_match", "version": "pre-upgrade"}
{"error_id": "ERR002", "date": "2026-01-22", "severity": "medium", "type": "false_positive", "category": "semantic_matching", "memory": "works at Microsoft", "generated": "invests in Microsoft", "expected": "no_match", "actual": "match", "version": "post-upgrade"}
```

## Analysis Metrics

### Error Rate Metrics
- **Overall error rate:** Errors / Total verifications
- **False negative rate:** FN / (FN + TN)
- **False positive rate:** FP / (FP + TP)
- **Error reduction:** (Pre-upgrade errors - Post-upgrade errors) / Pre-upgrade errors

### Category Metrics
- **Errors by category:** Count per category
- **Severity distribution:** % Critical/High/Medium/Low
- **Resolution rate:** Fixed errors / Total errors

## Success Criteria

**Minimum Viable:**
- ≥50 unique error cases collected
- ≥80% categorized correctly
- Clear prioritization of top 10 errors

**Ideal:**
- ≥100 unique error cases
- ≥90% categorization accuracy
- ≥50% error reduction post-upgrade in paraphrasing category

## Next Steps

1. Review and approve collection methods
2. Set up logging infrastructure
3. Create error reporting forms
4. Begin error collection
5. Regular triage meetings

## References

- [Error Templates](./error_templates.md)
- [Experiment Protocol](../benchmarking/experiment_protocol.md)
- [GROUNDCHECK_IMPROVEMENTS.md](../../GROUNDCHECK_IMPROVEMENTS.md)

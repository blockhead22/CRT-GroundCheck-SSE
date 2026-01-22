# Pre/Post-Upgrade Analysis Protocol

## Objective

Define a rigorous methodology for analyzing the impact of the paraphrasing accuracy upgrade (PR #18) on GroundCheck's performance and user value.

## Overview

This protocol outlines how to:
1. Establish pre-upgrade baseline
2. Measure post-upgrade performance
3. Compare results statistically
4. Identify improvements and regressions
5. Calculate business impact

## Analysis Framework

### Phase 1: Pre-Upgrade Baseline (Week 1)

#### Data Collection
**Sources:**
1. GroundingBench paraphrasing dataset (10 examples)
2. Real user data (if available, N≥50 verifications)
3. Synthetic test cases (N=20-30)

**Metrics to Collect:**
- Overall accuracy (% correct verifications)
- False Negative rate (% valid paraphrases missed)
- False Positive rate (% invalid paraphrases accepted)
- Average latency (ms per verification)
- Memory usage (MB)
- Error distribution by category

**Method:**
```python
# Pseudo-code
baseline_results = []
for example in test_set:
    result = groundcheck.verify(example.memory, example.generated)
    baseline_results.append({
        'example_id': example.id,
        'expected': example.label,
        'predicted': result.passed,
        'latency_ms': result.latency,
        'error_type': classify_error(example.label, result.passed)
    })

baseline_metrics = calculate_metrics(baseline_results)
```

**Baseline Report Template:**
```markdown
## Pre-Upgrade Baseline Report

**Date:** [YYYY-MM-DD]
**Version:** [GroundCheck version]
**Test Set Size:** [N examples]

### Overall Performance
- Accuracy: [X%] ([N_correct] / [N_total])
- False Negative Rate: [X%] ([N_FN] / [N_should_match])
- False Positive Rate: [X%] ([N_FP] / [N_should_not_match])
- Average Latency: [X ms]
- P95 Latency: [X ms]
- Memory Usage: [X MB]

### Performance by Category
| Category | N | Accuracy | FN Rate | FP Rate |
|----------|---|----------|---------|---------|
| Exact Synonyms | X | X% | X% | X% |
| Contextual | X | X% | X% | X% |
| Semantic Shifts | X | X% | X% | X% |
| Temporal | X | X% | X% | X% |
| Negation | X | X% | X% | X% |

### Top 5 Error Patterns
1. [Pattern description] - [N occurrences]
2. [Pattern description] - [N occurrences]
3. ...

### Detailed Errors
[Link to error database with full details]
```

#### Phase 2: Post-Upgrade Testing (Weeks 2-3)

**Deployment:**
1. Deploy upgraded GroundCheck (with semantic matching)
2. Ensure semantic model is loaded
3. Verify configuration (threshold = 0.85)
4. Run health checks

**Data Collection:**
Use EXACT SAME test set as baseline:
- Same GroundingBench examples
- Same real user data
- Same synthetic test cases

**Metrics to Collect:**
Same metrics as baseline for direct comparison

**Method:**
```python
# Pseudo-code
post_upgrade_results = []
for example in test_set:  # SAME test_set as baseline
    result = groundcheck.verify(example.memory, example.generated)
    post_upgrade_results.append({
        'example_id': example.id,
        'expected': example.label,
        'predicted': result.passed,
        'latency_ms': result.latency,
        'error_type': classify_error(example.label, result.passed)
    })

post_metrics = calculate_metrics(post_upgrade_results)
```

### Phase 3: Statistical Comparison (Week 4)

#### Hypothesis Testing

**Primary Hypothesis:**
- H0: Paraphrasing accuracy_post ≤ accuracy_pre
- H1: Paraphrasing accuracy_post > accuracy_pre
- Significance level: α = 0.05

**Tests to Run:**

1. **Paired t-test** (for accuracy improvement)
```python
from scipy.stats import ttest_rel

baseline_scores = [1 if correct else 0 for correct in baseline_results]
post_scores = [1 if correct else 0 for correct in post_upgrade_results]

t_stat, p_value = ttest_rel(post_scores, baseline_scores, alternative='greater')

if p_value < 0.05:
    print("Significant improvement detected")
```

2. **McNemar's Test** (for categorical changes)
```python
from statsmodels.stats.contingency_tables import mcnemar

# Create contingency table
table = [[correct_both, incorrect_pre_correct_post],
         [correct_pre_incorrect_post, incorrect_both]]

result = mcnemar(table, exact=True)
```

3. **Effect Size** (Cohen's d)
```python
import numpy as np

mean_diff = np.mean(post_scores) - np.mean(baseline_scores)
pooled_std = np.sqrt((np.std(baseline_scores)**2 + np.std(post_scores)**2) / 2)
cohens_d = mean_diff / pooled_std

# Interpretation:
# 0.2 = small, 0.5 = medium, 0.8 = large effect
```

#### Comparison Metrics

**Absolute Improvements:**
```
Accuracy_improvement = accuracy_post - accuracy_pre
FN_reduction = FN_rate_pre - FN_rate_post
FP_change = FP_rate_post - FP_rate_pre
```

**Relative Improvements:**
```
Accuracy_gain_pct = (accuracy_post - accuracy_pre) / accuracy_pre * 100%
FN_reduction_pct = (FN_rate_pre - FN_rate_post) / FN_rate_pre * 100%
```

**Performance Changes:**
```
Latency_change = latency_post - latency_pre
Memory_change = memory_post - memory_pre
```

#### Comparison Report Template

```markdown
## Pre/Post-Upgrade Comparison Report

**Baseline Date:** [YYYY-MM-DD]
**Post-Upgrade Date:** [YYYY-MM-DD]
**Test Set:** [Description, N examples]

### Summary
| Metric | Pre-Upgrade | Post-Upgrade | Change | % Change |
|--------|-------------|--------------|--------|----------|
| Accuracy | X% | Y% | +Z% | +W% |
| FN Rate | X% | Y% | -Z% | -W% |
| FP Rate | X% | Y% | ±Z% | ±W% |
| Latency | X ms | Y ms | ±Z ms | ±W% |

### Statistical Significance
- **Accuracy Improvement:** t(df)=[value], p=[value], **significant** ✓/✗
- **Effect Size:** Cohen's d = [value] ([small/medium/large])
- **Confidence:** 95% CI for accuracy change: [[lower], [upper]]

### Category-Level Analysis
| Category | Pre Acc | Post Acc | Improvement | Significant? |
|----------|---------|----------|-------------|--------------|
| Exact Synonyms | X% | Y% | +Z% | ✓ |
| Contextual | X% | Y% | +Z% | ✓ |
| ...

### Error Analysis

**Errors Resolved:** [N errors that were fixed]
1. [Error pattern 1] - [N instances]
2. [Error pattern 2] - [N instances]
...

**New Errors Introduced:** [N new errors]
1. [Error pattern 1] - [N instances]
2. [Error pattern 2] - [N instances]
...

**Net Error Reduction:** [Pre_total_errors - Post_total_errors] = [N] errors

### Performance Impact
- Average latency change: [±X ms] ([±Y%])
- P95 latency change: [±X ms] ([±Y%])
- Memory usage change: [±X MB] ([±Y%])
- **Meets performance target (<20ms)?** Yes/No

### Conclusion
[Summary of findings, statistical significance, practical significance]
```

### Phase 4: Regression Analysis

#### Identify Regressions
**Definition:** Cases that worked pre-upgrade but fail post-upgrade

**Method:**
```python
regressions = []
for i, (pre, post) in enumerate(zip(baseline_results, post_upgrade_results)):
    if pre['correct'] == True and post['correct'] == False:
        regressions.append({
            'example_id': test_set[i].id,
            'type': 'regression',
            'details': test_set[i]
        })

print(f"Found {len(regressions)} regressions")
```

**Regression Report:**
- Total regressions: [N]
- Regression rate: [N/total * 100%]
- Severity distribution: [Critical/High/Medium/Low counts]
- Root causes: [Common patterns]

**Acceptable Regression Rate:**
- Target: <5% of test cases
- Critical regressions: 0

### Phase 5: User Impact Analysis

#### Quantitative User Metrics

From user testing (see Interview Guide):
```markdown
### User Feedback Metrics

**Trust Scores:**
- Pre-upgrade average: [X/5]
- Post-upgrade average: [Y/5]
- Change: [±Z] ([±W%])

**Preference (A/B Test):**
- % preferring post-upgrade: [X%]
- % preferring pre-upgrade: [Y%]
- % no preference: [Z%]

**Satisfaction:**
- Pre-upgrade average: [X/10]
- Post-upgrade average: [Y/10]
- Change: [±Z] ([±W%])

**Perceived Accuracy:**
- Pre-upgrade: [X%]
- Post-upgrade: [Y%]
- Change: [±Z%]
```

#### Qualitative Analysis

**Theme Analysis:**
1. Most mentioned improvement: "[theme]" ([N mentions])
2. Most mentioned concern: "[theme]" ([N mentions])
3. Requested features: "[theme]" ([N mentions])

**Representative Quotes:**
- "[Quote about trust improvement]" - Participant P003
- "[Quote about accuracy value]" - Participant P007
- ...

### Phase 6: Business Value Assessment

#### ROI Calculation

**Improvement Value:**
```
Accuracy_improvement = 70% → 85% = +15 percentage points

Per-user value of accuracy:
- Support ticket reduction: [X tickets/month * $Y/ticket]
- Time saved: [X hours/month * $Y/hour]
- Increased usage: [X% increase in engagement]
- Premium tier conversion: [X% conversion * $Y/user]

Total value = Sum of above
```

**Cost of Improvement:**
```
Development cost: [hours * rate]
Compute cost (semantic model): [$/month]
Maintenance cost: [$/month]

Total cost = Sum of above
```

**ROI:**
```
ROI = (Total value - Total cost) / Total cost * 100%

Payback period = Total cost / Monthly value
```

#### Business Metrics Template

```markdown
## Business Value Assessment

### Accuracy Improvement Impact
- Baseline accuracy: 70%
- Post-upgrade accuracy: 85%
- **Improvement: +15 percentage points (+21% relative)**

### User Value
**Quantified Benefits:**
1. Support ticket reduction: [X%] ([N tickets/month]) = $[value/month]
2. User trust increase: [X points] (1-5 scale) = [estimated retention improvement]
3. Time savings: [X minutes/user/month] = $[value/month]
4. Premium conversions: [X%] = $[value/month]

**Total Monthly Value: $[sum]**

### Cost Analysis
**One-time Costs:**
- Development: [X hours] * $[rate] = $[value]
- Testing: [X hours] * $[rate] = $[value]

**Recurring Costs:**
- Compute (semantic model): $[X/month]
- Maintenance: $[X/month]

**Total Monthly Cost: $[sum]**

### ROI Calculation
- Monthly Net Value: $[value - cost]
- Payback Period: [months]
- 12-month ROI: [(12 * monthly_value - one_time_cost) / total_cost * 100]%

### Competitive Positioning
- Our accuracy: 85%
- SelfCheckGPT: ~82%
- **Competitive advantage: +3 percentage points**
```

## Validation Checklist

Before finalizing analysis:

- [ ] Used exact same test set for pre/post comparison
- [ ] Statistical tests performed with appropriate alpha
- [ ] Effect sizes calculated and interpreted
- [ ] Regressions identified and assessed
- [ ] User feedback incorporated
- [ ] Business value quantified
- [ ] Results peer-reviewed
- [ ] Limitations documented

## Limitations to Document

**Statistical Limitations:**
- Sample size (if small)
- Test set representativeness
- Confidence intervals

**Practical Limitations:**
- Semantic model availability
- Network requirements
- Hardware requirements

**Scope Limitations:**
- What's NOT included in analysis
- What's NOT tested
- What's NOT claimed

## Next Steps

1. Execute baseline collection
2. Deploy upgrade
3. Execute post-upgrade collection
4. Perform statistical analysis
5. Write comparison report
6. Share findings with stakeholders

## References

- [Error Classification](./error_classification.md)
- [Experiment Protocol](../benchmarking/experiment_protocol.md)
- [Interview Guide](../interviews/interview_guide.md)
- [Findings Template](../findings/findings_template.md)

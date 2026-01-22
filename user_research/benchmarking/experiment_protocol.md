# User Benchmarking Experiment Protocol

## Objective

Design rigorous user benchmarking experiments to quantify the real-world impact of the paraphrasing accuracy improvements (from ~70% to 85-90%) implemented in PR #18.

## Experiment Design

### 1. Research Questions

**Primary Questions:**
- How much does the 85-90% paraphrasing accuracy improve user trust in GroundCheck?
- What percentage of previously-failing paraphrase cases now succeed?
- How do users perceive the value of semantic matching vs. fuzzy string matching?

**Secondary Questions:**
- Are there edge cases where semantic matching introduces false positives?
- What is the acceptable threshold for semantic similarity (currently 0.85)?
- How does performance impact user experience (<20ms verification time)?

### 2. Participant Selection

**Inclusion Criteria:**
- Users who interact with AI assistants regularly (>5 times/week)
- Experience with long-term memory systems or chatbots
- Comfort level with providing feedback on AI accuracy

**Sample Size:**
- **Minimum:** 10 participants (for qualitative insights)
- **Target:** 20-30 participants (for statistical significance)
- **Diversity:** Mix of technical and non-technical users

**Recruitment Channels:**
- Existing GroundCheck users
- AI/ML communities (Discord, Reddit)
- Internal team members and stakeholders

### 3. Experimental Setup

#### Pre-Upgrade Baseline
1. Run GroundCheck on GroundingBench paraphrasing dataset (without semantic matching)
2. Collect baseline accuracy: ~70% (7/10 examples)
3. Document specific failure cases

#### Post-Upgrade Testing
1. Run GroundCheck with semantic matching enabled
2. Measure accuracy on same dataset: Expected 85-90%
3. Document improvements and any new failure modes

### 4. Task Design

#### Task 1: Blind A/B Comparison
**Description:** Participants evaluate two versions of GroundCheck output without knowing which is pre/post-upgrade.

**Materials:**
- 10 paraphrasing examples from GroundingBench
- Pre-upgrade results (Version A)
- Post-upgrade results (Version B)

**Procedure:**
1. Present participant with memory context and generated text
2. Show Version A and Version B verification results
3. Ask: "Which version do you trust more and why?"
4. Record preference and reasoning

**Metrics:**
- Preference rate (% choosing post-upgrade)
- Confidence scores (1-5 scale)
- Qualitative reasoning

#### Task 2: Real-World Scenario Testing
**Description:** Participants use GroundCheck in realistic scenarios with their own data.

**Materials:**
- Sample conversation histories
- Paraphrased statements about user information

**Procedure:**
1. Participant creates 5 memory facts about themselves
2. Generate 10 paraphrased statements (mix of accurate and hallucinated)
3. Run GroundCheck verification
4. Participant evaluates accuracy of verification

**Metrics:**
- User-reported accuracy (% correct verifications)
- Time to complete task
- Satisfaction score (1-10 scale)

#### Task 3: Error Discovery
**Description:** Participants actively search for edge cases and failure modes.

**Materials:**
- Access to GroundCheck API
- List of challenging paraphrase types (idioms, synonyms, context-dependent)

**Procedure:**
1. Provide participants with error discovery guidelines
2. Ask them to create paraphrases they think will break the system
3. Run verification and document results
4. Categorize errors found

**Metrics:**
- Number of unique errors discovered
- Error categories (false positives vs. false negatives)
- Severity ratings

### 5. Data Collection

**Quantitative Data:**
- Accuracy scores (pre/post upgrade)
- Task completion times
- Preference ratings (A/B test)
- Confidence scores (1-5 scale)
- Satisfaction scores (1-10 scale)

**Qualitative Data:**
- User reasoning for preferences
- Open-ended feedback on improvements
- Suggestions for edge cases
- Trust and confidence narratives

### 6. Analysis Methods

**Statistical Analysis:**
- Paired t-test for accuracy improvement
- Chi-square test for preference distribution
- Effect size calculation (Cohen's d)

**Qualitative Analysis:**
- Thematic analysis of user feedback
- Error categorization
- Pattern identification in edge cases

### 7. Reporting

**Report Structure:**
1. Executive Summary
   - Key findings (quantified)
   - User feedback highlights
   - Recommendations

2. Methodology
   - Participant demographics
   - Task descriptions
   - Data collection methods

3. Results
   - Quantitative metrics (tables, charts)
   - Qualitative insights (themes, quotes)
   - Error analysis

4. Discussion
   - Interpretation of findings
   - Limitations
   - Future work

5. Recommendations
   - Model tuning suggestions
   - Feature priorities
   - Next experiments

### 8. Timeline

| Phase | Duration | Activities |
|-------|----------|------------|
| Setup | Week 1 | Recruit participants, prepare materials |
| Baseline | Week 1 | Collect pre-upgrade data |
| Testing | Weeks 2-3 | Conduct experiments, gather data |
| Analysis | Week 4 | Analyze results, identify patterns |
| Reporting | Week 5 | Write report, present findings |

### 9. Ethical Considerations

- **Informed Consent:** All participants must consent to data collection
- **Privacy:** No personally identifiable information in shared results
- **Voluntary Participation:** Participants can withdraw at any time
- **Data Security:** Secure storage of participant data

### 10. Success Criteria

**Minimum Viable Success:**
- ≥10 participants complete all tasks
- Statistically significant improvement in accuracy (p < 0.05)
- Clear user preference for post-upgrade version (>60%)

**Ideal Success:**
- ≥20 participants complete all tasks
- >15% absolute accuracy improvement
- Strong user preference (>75%)
- <5 new error categories discovered

## Next Steps

1. Review and approve this protocol
2. Prepare materials for GroundingBench tasks
3. Create recruitment materials
4. Set up data collection infrastructure
5. Begin participant recruitment

## References

- PR #18: [Implement hybrid neural extraction and semantic matching](https://github.com/blockhead22/AI_round2/pull/18)
- [GROUNDCHECK_IMPROVEMENTS.md](../../GROUNDCHECK_IMPROVEMENTS.md)
- [GroundingBench Dataset](../../groundingbench/data/)

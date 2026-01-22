# GroundingBench User Tasks

## Overview

This document outlines specific tasks for user benchmarking experiments using the GroundingBench dataset, with a focus on paraphrasing accuracy improvements.

## Dataset Information

**Location:** `/groundingbench/data/`

**Relevant Files:**
- `paraphrasing.jsonl` - Core paraphrasing test cases
- `paraphrasing_expanded.jsonl` - Extended paraphrasing scenarios
- `partial_grounding.jsonl` - Partial grounding cases (related to compound values)

## Task Categories

### Category 1: Paraphrasing Verification Tasks

#### Task 1.1: Employment Paraphrases
**Examples from:** `paraphrasing.jsonl`

**Test Cases:**
1. **para_004:** "works at Microsoft" vs "work at Microsoft"
   - Memory: "User works at Microsoft"
   - Generated: "You work at Microsoft"
   - Challenge: Verb tense variation

2. **para_005:** "is a Software Engineer at" vs "works at"
   - Memory: "User is a Software Engineer at Google"
   - Generated: "You work at Google"
   - Challenge: Job title omission

3. **para_006:** "works at" vs "office is at"
   - Memory: "User works at Amazon"
   - Generated: "Your office is at Amazon"
   - Challenge: Semantic equivalence

**User Task:**
- Evaluate whether GroundCheck correctly identifies these as valid paraphrases
- Rate confidence in verification result (1-5)
- Suggest improvement areas

**Expected Improvement:**
- Pre-upgrade: May fail due to exact string matching
- Post-upgrade: Should pass with semantic matching (threshold 0.85)

#### Task 1.2: Location Paraphrases
**Test Cases:**
1. "lives in Seattle" vs "resides in Seattle"
2. "is from New York" vs "hails from New York"
3. "moved to San Francisco" vs "relocated to San Francisco"

**User Task:**
- Verify semantic matching accuracy
- Identify any false positives or negatives
- Rate naturalness of paraphrases (1-5)

#### Task 1.3: Skill Paraphrases
**Test Cases:**
1. "knows Python" vs "is proficient in Python"
2. "expert in JavaScript" vs "skilled at JavaScript"
3. "can speak Spanish" vs "speaks Spanish fluently"

**User Task:**
- Test semantic matching on skill-related claims
- Note any unexpected behaviors
- Suggest additional test cases

### Category 2: Compound Value Tasks

#### Task 2.1: List Splitting
**Example from:** `partial_grounding.jsonl` (partial_003)

**Test Case:**
- Memory: "User knows Python" + "User knows JavaScript"
- Generated: "You use Python, JavaScript, Ruby, and Go"
- Expected: Correctly grounds Python & JavaScript, flags Ruby & Go as hallucinations

**User Task:**
- Verify compound splitting works correctly
- Test with different separators (commas, "and", "or", slashes)
- Identify edge cases

**Separators to Test:**
- Commas: "Python, JavaScript, Ruby"
- Conjunctions: "Python and JavaScript or Ruby"
- Slashes: "Python/JavaScript/Ruby"
- Semicolons: "Python; JavaScript; Ruby"
- Oxford comma: "Python, JavaScript, and Ruby"

#### Task 2.2: Partial Hallucination Detection
**Test Cases:**
1. **Housing details:**
   - Memory: "User has apartment"
   - Generated: "You live in a 3-bedroom apartment"
   - Challenge: Number extraction

2. **Location modifiers:**
   - Memory: "User lives in Seattle"
   - Generated: "You live in Seattle near the waterfront"
   - Challenge: Modifier verification

**User Task:**
- Identify which parts are grounded vs. hallucinated
- Rate difficulty of manual verification (1-5)
- Suggest acceptable hallucination levels

### Category 3: Edge Case Discovery Tasks

#### Task 3.1: Semantic Threshold Testing
**Objective:** Find the boundary of semantic similarity

**User Task:**
1. Create paraphrase pairs with varying similarity levels
2. Test verification at different thresholds (0.75, 0.80, 0.85, 0.90)
3. Identify optimal threshold for their use case

**Example Pairs:**
- High similarity (>0.90): "employed by" vs "works at"
- Medium similarity (0.80-0.90): "profession is" vs "works at"
- Low similarity (<0.80): "affiliated with" vs "works at"

#### Task 3.2: False Positive Hunting
**Objective:** Find cases where semantic matching is too permissive

**User Task:**
1. Create memory-generation pairs that should NOT match
2. Verify GroundCheck correctly identifies as hallucinations
3. Document any false positives

**Example Cases:**
- Memory: "User works at Microsoft"
- Generated: "You invest in Microsoft" (should NOT match)

- Memory: "User lives in Seattle"
- Generated: "You visited Seattle" (should NOT match)

#### Task 3.3: Context-Dependent Paraphrases
**Objective:** Test paraphrases that change meaning with context

**Example Cases:**
1. **Temporal context:**
   - "currently at Google" vs "previously at Google"
   - "will join Microsoft" vs "joined Microsoft"

2. **Negation:**
   - "likes Python" vs "doesn't like Python"
   - "can code in Java" vs "cannot code in Java"

**User Task:**
- Verify GroundCheck handles context correctly
- Identify failure modes
- Rate severity of errors (low/medium/high)

## Task Execution Protocol

### Preparation
1. Review task description
2. Familiarize with GroundCheck interface
3. Read example cases

### Execution
1. Complete tasks in order
2. Document observations in real-time
3. Take screenshots of unexpected results
4. Note time spent on each task

### Feedback
1. Rate overall experience (1-10)
2. List most valuable improvements
3. Suggest additional test cases
4. Share concerns or confusion

## Data Collection Format

For each task, collect:

```json
{
  "task_id": "para_004",
  "participant_id": "P001",
  "timestamp": "2026-01-22T10:30:00Z",
  "result": "pass|fail",
  "confidence": 4,
  "completion_time_sec": 45,
  "notes": "Semantic matching worked well, but verb tense could be clearer",
  "suggestions": ["Add explanation of why it matched"]
}
```

## Analysis Checklist

After completing all tasks:

- [ ] All paraphrasing tasks completed
- [ ] Compound value tasks verified
- [ ] Edge cases documented
- [ ] Confidence ratings recorded
- [ ] Qualitative feedback collected
- [ ] Screenshots captured (if applicable)
- [ ] Improvement suggestions noted

## Expected Outcomes

**Quantitative:**
- Paraphrasing accuracy: 70% → 85-90%
- False positive rate: <5%
- User confidence: >4/5 average
- Task completion time: <5 minutes per task

**Qualitative:**
- Increased trust in semantic matching
- Clear understanding of system capabilities
- Actionable feedback for tuning

## Next Steps

1. Recruit participants
2. Schedule testing sessions
3. Collect baseline data (pre-upgrade)
4. Run post-upgrade testing
5. Analyze results and document findings

## References

- [GroundingBench Dataset](../../groundingbench/data/)
- [Experiment Protocol](./experiment_protocol.md)
- [Error Collection Framework](../error_collection/collection_framework.md)

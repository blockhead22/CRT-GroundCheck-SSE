# Belief Revision Annotation Guide

## Overview

This guide helps human annotators classify belief revision scenarios into four categories.
Each example represents a situation where a user's new statement potentially conflicts or
updates an existing memory.

## Categories

### 1. REFINEMENT
**Definition**: New information adds detail or specificity without contradicting the old memory.

**Characteristics**:
- New memory is a superset or elaboration of old memory
- No contradiction or conflict
- Progressive enhancement of knowledge
- Typically uses "and", "also", "additionally"

**Examples**:
- Old: "I like Python"
- New: "I like Python and JavaScript"
- → REFINEMENT (adding more programming languages)

- Old: "I work at Google"
- New: "I work at Google in the Cloud division"
- → REFINEMENT (adding specificity)

### 2. REVISION
**Definition**: New information represents a genuine change in state or preference over time.

**Characteristics**:
- Complete replacement of old information
- Natural evolution or change
- No explicit contradiction markers
- Often has longer time gaps
- Represents legitimate updates to facts

**Examples**:
- Old: "I work at Netflix"
- New: "I work at Spotify"
- → REVISION (changed jobs)

- Old: "I live in Boston"
- New: "I live in Seattle"
- → REVISION (moved locations)

### 3. TEMPORAL
**Definition**: Updates related to time-bound states, achievements, or milestones.

**Characteristics**:
- Contains temporal markers ("now", "recently", "just", "started")
- Progress updates (learning → learned)
- Temporal state changes
- Time-sensitive information

**Examples**:
- Old: "I'm learning React"
- New: "I just finished learning React"
- → TEMPORAL (completion of time-bound activity)

- Old: "I want to visit Japan"
- New: "I recently visited Japan"
- → TEMPORAL (achievement of goal)

### 4. CONFLICT
**Definition**: Direct contradiction or opposite stance on the same topic.

**Characteristics**:
- Explicit negation ("not", "never", "don't")
- Opposite preferences or facts
- Contradictory statements
- No time gap justification for change

**Examples**:
- Old: "I like pair programming"
- New: "I don't like pair programming"
- → CONFLICT (contradictory preference)

- Old: "I use Docker"
- New: "I've never used Docker"
- → CONFLICT (contradictory fact)

## Decision Tree

Follow this decision tree to classify examples:

```
1. Does the new memory contradict the old with negation or opposite stance?
   YES → CONFLICT
   NO → Continue to 2

2. Does the new memory add details without changing core facts?
   YES → REFINEMENT
   NO → Continue to 3

3. Does the new memory contain temporal markers or indicate completion?
   YES → TEMPORAL
   NO → REVISION
```

## Edge Cases

### REFINEMENT vs REVISION
- **REFINEMENT**: "I like Python" → "I like Python and Go"
- **REVISION**: "I like Python" → "I like Go"

### TEMPORAL vs REVISION
- **TEMPORAL**: "I'm learning Rust" → "I finished learning Rust"
- **REVISION**: "I'm learning Rust" → "I'm learning Go"

### CONFLICT vs REVISION
- **CONFLICT**: "I like remote work" → "I don't like remote work" (explicit negation)
- **REVISION**: "I prefer remote work" → "I prefer office work" (change over time)

## Tips for Annotators

1. **Read the context**: Time gaps can help distinguish REVISION from CONFLICT
2. **Look for keywords**:
   - REFINEMENT: "and", "also", "as well as"
   - TEMPORAL: "now", "just", "recently", "finished", "started"
   - CONFLICT: "not", "never", "don't", "oppose"
   - REVISION: Complete replacement with time justification

3. **Consider intent**: Is this likely an update or a contradiction?
4. **Check time delta**: Large gaps (>30 days) suggest REVISION, small gaps suggest CONFLICT
5. **When in doubt**: Use the decision tree

## Quality Control

- Aim for consistency across similar examples
- If uncertain, mark for review
- Discuss ambiguous cases with team
- Target: >80% inter-annotator agreement (Cohen's Kappa >0.75)

## Annotation Format

For each example, provide one of: `REFINEMENT`, `REVISION`, `TEMPORAL`, `CONFLICT`

---
*Version 1.0 - Generated for Phase 2 Belief Revision Classifier*

# GroundingBench: A Contradiction-Aware Grounding Benchmark

## Motivation

Existing grounding verification benchmarks focus on standard hallucination detection but lack examples with contradictory context. GroundingBench fills this gap by including dedicated contradiction categories.

## Dataset Structure

GroundingBench contains 500 examples across 5 categories:

### 1. Factual Grounding (100 examples)
Standard grounding verification: simple fact checking without contradictions.

**Example:**
- Context: "User works at Microsoft"
- Output: "You work at Microsoft"
- Label: Grounded ✓

### 2. Contradictions (100 examples)
Memories contain conflicting information that must be resolved.

**Example:**
- Context: ["User works at Microsoft" (t=100), "User works at Amazon" (t=200)]
- Output: "You work at Amazon"
- Label: Grounded ✓, but requires_disclosure=True
- Expected: "You work at Amazon (moved from Microsoft)"

**Subcategories:**
- Temporal changes (job, location, preferences)
- Corrections ("Actually, I meant X not Y")
- Source conflicts (user-stated vs system-inferred)

### 3. Partial Grounding (100 examples)
Output contains both grounded and hallucinated claims.

**Example:**
- Context: "User works at Microsoft"
- Output: "You work at Microsoft in Seattle"
- Label: Partially grounded (hallucination: "Seattle")

### 4. Paraphrasing (100 examples)
Facts are paraphrased but semantically equivalent.

**Example:**
- Context: "User is a Software Engineer"
- Output: "You're an SWE"
- Label: Grounded ✓

### 5. Multi-Hop Reasoning (100 examples)
Facts require combining information from multiple memories.

**Example:**
- Context: ["User works at Microsoft", "Microsoft is in Redmond"]
- Output: "Your office is in Redmond"
- Label: Grounded ✓

## Annotation Process

Examples were created by:
1. Synthetic generation using templates
2. Manual review and refinement
3. Difficulty labeling (easy, medium, hard)
4. Metadata tagging (contradiction type, fact type)

## Evaluation Metrics

For each example, we evaluate:
- **Grounding accuracy:** Did system correctly identify grounding status?
- **Contradiction detection:** Did system detect contradictions in context?
- **Disclosure verification:** Did system verify appropriate acknowledgment?

## Dataset Statistics

| Category | Count | Avg Memories | Avg Contradictions | Difficulty |
|----------|-------|--------------|-------------------|------------|
| Factual | 100 | 2.1 | 0 | Easy |
| Contradictions | 100 | 2.8 | 1.3 | Medium-Hard |
| Partial | 100 | 2.5 | 0.2 | Medium |
| Paraphrasing | 100 | 2.0 | 0 | Easy-Medium |
| Multi-hop | 100 | 3.2 | 0.1 | Medium-Hard |

## Data Format

Each example contains:
```json
{
  "id": "contra_001",
  "category": "contradictions",
  "query": "Where do I work?",
  "retrieved_context": [...],
  "generated_output": "You work at Amazon",
  "label": {
    "grounded": true,
    "requires_contradiction_disclosure": true,
    "expected_disclosure": "You work at Amazon (moved from Microsoft)"
  }
}
```

## Availability

GroundingBench is released under MIT license and available at: [repository URL]

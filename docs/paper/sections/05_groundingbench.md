# GroundingBench Dataset

We introduce **GroundingBench**, a benchmark specifically designed to evaluate grounding verification in long-term memory systems where retrieved context may contain contradictions. Unlike existing grounding benchmarks that focus on static document retrieval, GroundingBench explicitly tests whether systems can detect and handle contradictory memories.

## 5.1 Dataset Construction

**Motivation:** Existing grounding benchmarks evaluate verification on carefully curated, consistent document collections. They test whether systems detect hallucinations (unsupported claims) but not whether systems handle contradictions (conflicting supported claims). For long-term memory systems where context evolves over time, contradiction handling is essential.

**Design principles:**
1. **Memory-based context:** Examples use retrieved memories (user facts, preferences, history) rather than documents
2. **Temporal evolution:** Memories include timestamps to represent facts changing over time
3. **Trust scores:** Each memory has a confidence score to enable trust-weighted contradiction detection
4. **Contradiction-focused:** Significant portion of examples test contradiction handling explicitly
5. **Diverse categories:** Cover multiple grounding challenges beyond contradictions

**Size:** 50 seed examples across 5 categories (10 examples each). The seed set establishes benchmark structure and evaluation protocol; it can be expanded to 500 examples via systematic variation of fact types, contradiction patterns, and grounding scenarios.

## 5.2 Example Categories

GroundingBench contains 50 examples divided into five categories:

### Factual Grounding (10 examples)
Tests basic grounding verification: are claims supported by any memory? Examples include:
- Simple fact retrieval: "Where do I live?" → "You live in Seattle" with memory "Lives in Seattle"
- Multiple fact composition: "What's my job and location?" → "Software engineer in Seattle"
- Negative facts: "Do I have pets?" → "No" when no pet-related memories exist

**Evaluation:** Standard grounding check—all claims must be supported by retrieved memories.

### Contradictions (10 examples)
Tests contradiction detection and disclosure verification. Examples include:

**Temporal conflicts:**
- Memories: "Works at Microsoft" (Jan, trust=0.85), "Works at Amazon" (Mar, trust=0.85)
- Query: "Where do I work?"
- Good output: "You work at Amazon (changed from Microsoft)"
- Bad output: "You work at Amazon" (missing disclosure)

**Trust-weighted scenarios:**
- Memories: "Favorite color: blue" (trust=0.9), "Favorite color: green" (trust=0.2)
- Should NOT flag as contradiction due to low trust on second memory
- Output: "Your favorite color is blue" (no disclosure needed)

**Multi-value contradictions:**
- Memories contain 3+ conflicting values for same slot
- Output should acknowledge multiple contradictions or use most recent with disclosure

**Evaluation:** System must detect contradictions AND verify outputs include appropriate disclosure when using contradicted values.

### Partial Grounding (10 examples)
Tests mixed scenarios where outputs contain both grounded and hallucinated claims:
- "You work at Microsoft and live in Seattle" when only Microsoft memory exists
- "Your favorite color is blue and favorite food is pizza" when only color memory exists

**Evaluation:** System should identify which specific claims are hallucinated vs grounded.

### Paraphrasing (10 examples)
Tests semantic equivalence: outputs that paraphrase memory content should be grounded. Examples:
- Memory: "Works as a software engineer"
- Output: "You're a software developer"
- Should be grounded (semantic equivalence)

Paraphrasing tests whether fact extraction handles linguistic variation:
- "employed by" vs "works at"
- "software engineer" vs "software developer"
- "lives in" vs "resides in"

**Evaluation:** Outputs semantically equivalent to memories should be grounded.

### Multi-hop Reasoning (10 examples)
Tests inference across multiple memories. Examples:
- Memory 1: "Works at Microsoft"
- Memory 2: "Microsoft is located in Redmond"
- Query: "Where is my office?"
- Output: "Your office is in Redmond"

**Evaluation:** Claims requiring multi-hop inference should be supported if all intermediate facts are grounded.

## 5.3 Example Schema

Each GroundingBench example follows a structured format:

```json
{
  "id": "contra_001",
  "category": "contradictions",
  "query": "Where do I work?",
  "retrieved_context": [
    {
      "id": "m1",
      "text": "User works at Microsoft",
      "trust": 0.85,
      "timestamp": 1704067200
    },
    {
      "id": "m2",
      "text": "User works at Amazon",
      "trust": 0.85,
      "timestamp": 1709251200
    }
  ],
  "generated_output": "You work at Amazon",
  "label": {
    "grounded": false,
    "requires_contradiction_disclosure": true,
    "expected_disclosure": "Amazon (changed from Microsoft)",
    "hallucinations": [],
    "contradictions": [
      {
        "slot_type": "employer",
        "values": ["microsoft", "amazon"],
        "memory_ids": ["m1", "m2"]
      }
    ]
  }
}
```

**Fields:**
- `id`: Unique identifier
- `category`: One of {factual_grounding, contradictions, partial_grounding, paraphrasing, multi_hop}
- `query`: User query that generated the output (optional, for context)
- `retrieved_context`: List of memories with id, text, trust score, timestamp
- `generated_output`: LLM-generated text to verify
- `label`: Ground truth verification result

**Label structure:**
- `grounded`: True if output passes verification, False otherwise
- `requires_contradiction_disclosure`: True if output uses contradicted value without disclosure
- `expected_disclosure`: Suggested disclosure text when contradictions exist
- `hallucinations`: List of unsupported claims (empty if fully grounded)
- `contradictions`: List of detected contradictions in retrieved context

## 5.4 Contradiction Category Focus

The contradictions category deserves special attention as it tests capabilities absent from existing methods.

**Why contradictions matter:**
Long-term memory systems accumulate updates as users change jobs, move locations, update preferences, or correct past statements. These updates create contradictions—not errors, but facts about temporal evolution. Systems that cannot detect contradictions fail to serve long-term AI applications.

**10 contradiction examples test:**

1. **Basic job change** (contra_001): Microsoft → Amazon, high trust, should require disclosure
2. **Location move** (contra_002): Seattle → Portland, temporal evolution
3. **Preference update** (contra_003): Favorite color blue → green
4. **Trust-weighted filter** (contra_004): High trust (0.9) vs low trust (0.2), should NOT flag contradiction
5. **Equal trust** (contra_005): Both memories trust=0.85, genuine contradiction
6. **Three-way conflict** (contra_006): Employer has 3 different values across memories
7. **Missing disclosure** (contra_007): Output uses new value without acknowledging old
8. **Adequate disclosure** (contra_008): Output includes "changed from X to Y"
9. **Timestamp ordering** (contra_009): Output should prefer most recent memory
10. **Complex paraphrase** (contra_010): Contradictions with paraphrased fact expressions

**Evaluation on contradiction examples:**
- Baseline methods (SelfCheckGPT, CoVe): ~30% accuracy (3/10 correct)
- GroundCheck: 60% accuracy (6/10 correct)
- Gap: GroundCheck explicitly detects contradictions; baselines cannot

## 5.5 Dataset Statistics

**Size:** 50 examples (10 per category)

**Grounding distribution:**
- Grounded (should pass): 33 examples (66%)
- Not grounded (should fail): 17 examples (34%)

**Difficulty levels:**
- Easy: 16 examples (32%) - single fact, no contradictions
- Medium: 28 examples (56%) - multiple facts or simple contradictions
- Hard: 6 examples (12%) - complex contradictions or multi-hop reasoning

**Contradiction prevalence:**
- Contains contradictions: 10 examples (contradiction category)
- No contradictions: 40 examples (other categories)

**Fact types covered:**
- employer (job): 15 examples
- location (city): 12 examples
- preferences (color, food): 10 examples
- title (role): 8 examples
- other: 5 examples

**License:** CC-BY-4.0 (permissive, allows commercial use with attribution)

**Availability:** Released with GroundCheck codebase; HuggingFace dataset to be published upon paper acceptance

**Expansion plan:** Seed set of 50 examples establishes structure. Expanding to 500 examples requires:
1. Systematic variation of fact types (20+ slot types)
2. Additional contradiction patterns (4-way conflicts, cyclic updates)
3. Domain-specific scenarios (medical, legal, customer service)
4. Multi-lingual examples (Spanish, French, Chinese)

The 50-example seed set enables rapid prototyping and method development; the 500-example full benchmark will provide comprehensive evaluation for production systems.

## 5.6 Comparison to Existing Benchmarks

**vs. FEVER [Thorne et al., 2018]:** FEVER tests fact verification against Wikipedia—detecting whether claims are supported, refuted, or lack evidence. It does NOT test contradiction detection in retrieved context. GroundingBench explicitly includes contradictory memories and evaluates whether systems handle them.

**vs. SelfCheckGPT benchmark:** SelfCheckGPT evaluation uses Wikipedia articles as ground truth documents. Documents are carefully curated and internally consistent. GroundingBench uses evolving memory collections where contradictions are expected.

**vs. RAG benchmarks:** Standard RAG evaluation (Natural Questions, TriviaQA) tests answer accuracy given retrieval. GroundingBench tests verification accuracy—whether systems correctly identify grounded vs hallucinated outputs and handle contradictory context.

**Unique contribution:** GroundingBench is the first benchmark to explicitly test contradiction detection in retrieved context for grounding verification. This capability is essential for long-term AI systems but absent from existing benchmarks.

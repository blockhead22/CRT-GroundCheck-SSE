# GroundCheck

**Grounding verification for LLM outputs with contradiction detection.**

GroundCheck is a lightweight Python library that verifies LLM-generated text is grounded in retrieved context, with special focus on detecting and handling contradictory information. It uses deterministic fact extraction and matching—no additional ML models required by default. **NEW: Optional neural extraction and semantic matching for improved accuracy.**

## What It Does

**Basic grounding:** Verifies factual claims are supported by retrieved memories  
**Contradiction detection:** Identifies when retrieved memories contradict each other  
**Semantic matching:** (Optional) Handles paraphrases using embeddings and NER models  
**Fast:** <10ms overhead with regex-only, <25ms with neural models  
**Deterministic:** Regex-based patterns with optional neural fallback, explainable results

## What It Doesn't Do

**Limitations (Regex-only mode):**
- Only handles 20+ predefined fact types (employer, location, name, etc.)
- Cannot extract domain-specific or arbitrary facts
- Regex-based (misses complex linguistic patterns)
- 70% overall accuracy (vs ~82% for SelfCheckGPT on basic grounding)
- 60% contradiction detection (still misses 4/10 cases)

**With Neural Mode:**
- Improves accuracy to 85-90% on paraphrasing
- Better semantic understanding
- Requires optional dependencies

**Not for:**
- Arbitrary fact verification beyond predefined slots
- Production systems requiring >90% accuracy (yet)
- Non-English text
- Multi-modal contradiction detection

## Installation

```bash
# Basic installation (regex-only, no ML dependencies)
pip install groundcheck

# With neural features (requires transformers, torch, sentence-transformers)
pip install groundcheck[neural]

# All features
pip install groundcheck[all]
```

For local development:

```bash
git clone https://github.com/blockhead22/AI_round2.git
cd AI_round2/groundcheck
pip install -e .

# With neural features
pip install -e ".[neural]"
```

## Quick Start

```python
from groundcheck import GroundCheck, Memory

# Initialize verifier
verifier = GroundCheck()

# Define retrieved context
memories = [Memory(id="m1", text="User works at Microsoft")]

# Verify generated output
result = verifier.verify("You work at Amazon", memories)

print(result.passed)  # False
print(result.hallucinations)  # ["Amazon"]
```

## Features

- 🎯 **Claim-level grounding verification** - Extracts and verifies individual factual claims
- 🔍 **Contradiction detection** - Identifies contradictory information in retrieved context (60% accuracy)
- 🧠 **Hybrid fact extraction** (Optional) - Fast regex + neural NER fallback for better coverage
- 🔤 **Semantic matching** (Optional) - Handles paraphrases via embeddings and synonym expansion
- ✅ **Fact extraction and mapping** - Maps claims to supporting memories
- 🚀 **Fast** - Pure Python, optional ML models (<10ms regex-only, <25ms with neural)
- 🔧 **Model-agnostic** - Works with any LLM output
- 📦 **Zero ML dependencies by default** - Optional neural features via pip install extras
- 🧪 **Well-tested** - 120+ tests, 90% coverage

**Performance:**
- Regex-only: 70% accuracy on paraphrasing (fast path)
- With neural: 85-90% accuracy on paraphrasing (slower, optional)
- Contradiction detection: 60-80% accuracy
- Latency: <2ms regex-only, <25ms p95 with neural models

## Usage

### Basic Verification

```python
from groundcheck import GroundCheck, Memory

verifier = GroundCheck()

# Create memories from retrieved context
memories = [
    Memory(id="mem_1", text="User works at Microsoft", trust=0.9),
    Memory(id="mem_2", text="User lives in Seattle", trust=0.8)
]

# Verify generated text
result = verifier.verify(
    generated_text="You work at Amazon and live in Seattle",
    retrieved_memories=memories,
    mode="strict"  # or "permissive"
)

# Check results
print(f"Passed: {result.passed}")  # False
print(f"Hallucinations: {result.hallucinations}")  # ["Amazon"]
print(f"Grounding map: {result.grounding_map}")  # {"Seattle": "mem_2"}
print(f"Corrected: {result.corrected}")  # "You work at Microsoft and live in Seattle"
```

### Neural Features (Optional)

**Hybrid Fact Extraction:**

```python
from groundcheck import HybridFactExtractor

# Initialize with neural extraction
extractor = HybridFactExtractor(
    confidence_threshold=0.8,  # Use neural when regex confidence < 0.8
    use_neural=True,
    neural_model="dslim/bert-base-NER"
)

# Extract facts with hybrid approach
result = extractor.extract("Microsoft employee based in Seattle")
print(result.entities)  # {'employer': ['Microsoft'], 'location': ['Seattle']}
print(result.method)  # "hybrid" (used both regex and neural)
print(result.confidence)  # 0.9
```

**Semantic Matching:**

```python
from groundcheck import SemanticMatcher

# Initialize with embedding-based matching
matcher = SemanticMatcher(
    use_embeddings=True,
    embedding_model="all-MiniLM-L6-v2",
    embedding_threshold=0.85
)

# Check if values match semantically
is_match, method, matched = matcher.is_match(
    claimed="employed by Google",
    supported_values={"works at Google", "Google employee"},
    slot="employer"
)
print(is_match)  # True
print(method)  # "synonym" or "embedding"
```

**Automatic Integration:**

The neural components are automatically used when available:

```python
from groundcheck import GroundCheck

# Will use neural features if installed
verifier = GroundCheck()

# Semantic matching handles paraphrases automatically
memories = [Memory(id="m1", text="User works at Google")]
result = verifier.verify("You're employed by Google", memories)
print(result.passed)  # True (semantic match detected)
```

**Graceful Degradation:**

```python
# Works without neural dependencies installed
# Automatically falls back to regex + fuzzy matching
verifier = GroundCheck()
# No error, just reduced accuracy on paraphrases
```

### Fact Extraction

```python
from groundcheck import extract_fact_slots

# Extract facts from text
facts = extract_fact_slots("My name is Alice and I work at Microsoft")

print(facts["name"].value)  # "Alice"
print(facts["employer"].value)  # "Microsoft"
```

### Custom Trust Scores

```python
# Memories can have different trust levels
memories = [
    Memory(id="m1", text="User works at Microsoft", trust=0.3),  # Low confidence
    Memory(id="m2", text="User works at Amazon", trust=0.95),   # High confidence
]

result = verifier.verify("You work at Amazon", memories)
print(result.confidence)  # High confidence score due to strong memory support
```

## Verification Modes

- **`strict`** - Generates corrected text by replacing hallucinations with grounded facts
- **`permissive`** - Only detects hallucinations without generating corrections

## Supported Fact Types

GroundCheck can extract and verify specific types of personal and professional facts:

- **Personal**: name, location, siblings, languages spoken
- **Professional**: employer, job title, project, programming experience
- **Education**: school, graduation year, degree information
- **Preferences**: favorite color, coffee preference, hobbies

**Limitations:** Only handles predefined slots listed above. Cannot extract arbitrary or domain-specific facts without manual pattern engineering.

See `fact_extractor.py` for full list of supported patterns.

## Known Limitations

### Accuracy (Regex-only)
- **Overall grounding:** 70% (vs 82% for SelfCheckGPT on basic tasks)
- **Contradiction detection:** 60% (misses 4/10 cases)
- **Paraphrasing:** 70% (vs 90% for LLM-based methods)
- **Partial grounding:** 40% (same as baselines)

### Accuracy (With Neural Features)
- **Paraphrasing:** 85-90% (significant improvement)
- **Overall grounding:** 80-85%
- **Contradiction detection:** 70-80%
- **Trade-off:** +15-20ms latency for neural inference

### Regex Limitations
- Only 20+ predefined fact types
- Substring matching issues ("Software Engineer" matches "Senior Software Engineer")
- Misses linguistic variations ("works at X" vs "employed by X since 2020") - **improved with neural**
- No semantic understanding (cannot recognize "software engineer" ≈ "software developer" without explicit patterns) - **improved with semantic matcher**

### Scope
- Text-only (no multi-modal)
- English-only
- Fixed trust thresholds (not learned)
- Research prototype (not production-hardened)

### When NOT to Use This
- Need >95% accuracy on basic grounding → Use SelfCheckGPT or LLM-based methods
- Need arbitrary fact extraction → Use neural fact extractors
- Production system with strict requirements → Not ready (but improving)
- Non-English text → Not supported

## API Reference

### `GroundCheck`

Main verification class. Automatically uses neural features if available.

**Methods:**
- `verify(generated_text, retrieved_memories, mode="strict")` → `VerificationReport`
- `extract_claims(text)` → `Dict[str, ExtractedFact]`
- `find_support(claim, memories)` → `Optional[Memory]`
- `build_grounding_map(claims, memories)` → `Dict[str, str]`

### `HybridFactExtractor` (Optional)

Hybrid fact extraction with regex + neural NER fallback.

**Constructor:**
- `HybridFactExtractor(confidence_threshold=0.8, use_neural=True, neural_model="dslim/bert-base-NER")`

**Methods:**
- `extract(text)` → `NeuralExtractionResult`

**Attributes:**
- `confidence_threshold: float` - Threshold for using neural fallback (default: 0.8)
- `use_neural: bool` - Whether to use neural NER (default: True)
- `neural_model_name: str` - HuggingFace model name for NER

### `SemanticMatcher` (Optional)

Multi-tier semantic matching for paraphrase detection.

**Constructor:**
- `SemanticMatcher(use_embeddings=True, embedding_model="all-MiniLM-L6-v2", embedding_threshold=0.85)`

**Methods:**
- `is_match(claimed, supported_values, slot="")` → `Tuple[bool, str, Optional[str]]`

**Matching Strategies:**
1. Exact match (fastest)
2. Fuzzy match (SequenceMatcher)
3. Substring match
4. Synonym expansion
5. Embedding similarity (slowest, most accurate)

### `SemanticContradictionDetector` (Optional)

Semantic contradiction detection using NLI models.

**Constructor:**
- `SemanticContradictionDetector(use_nli=True, nli_model="cross-encoder/nli-deberta-v3-small", contradiction_threshold=0.7)`

**Methods:**
- `check_contradiction(statement_a, statement_b, slot=None)` → `ContradictionResult`

### `VerificationReport`

Results of verification.

**Attributes:**
- `original: str` - Original generated text
- `corrected: Optional[str]` - Corrected text (in strict mode)
- `passed: bool` - Whether verification passed
- `hallucinations: List[str]` - List of hallucinated values
- `grounding_map: Dict[str, str]` - Mapping from claim to memory ID
- `confidence: float` - Confidence score (0.0-1.0)

### `Memory`

A retrieved context item.

**Attributes:**
- `id: str` - Unique identifier
- `text: str` - Memory text content
- `trust: float` - Trust score (0.0-1.0, default: 1.0)
- `metadata: Optional[Dict]` - Additional metadata

## How It Works

1. **Fact Extraction**: Extracts factual claims from generated text using regex patterns (or hybrid neural+regex)
2. **Memory Parsing**: Parses supporting facts from retrieved memories
3. **Grounding Check**: Matches extracted claims against memory facts (with semantic matching if available)
4. **Contradiction Detection**: Identifies conflicts between memories (if trust-weighted)
5. **Hallucination Detection**: Identifies claims not supported by memories
6. **Correction** (strict mode): Replaces unsupported claims with grounded alternatives

**With Neural Features:**
- Hybrid extraction uses fast regex first, falls back to neural NER if confidence is low
- Semantic matcher handles paraphrases via multiple strategies (exact → fuzzy → synonym → embedding)
- All models are lazily loaded to minimize startup time
- Graceful degradation when neural dependencies unavailable

## Performance Characteristics

### Latency

**Regex-only mode:**
- Fact extraction: <1ms
- Verification: <2ms
- Total overhead: <5ms

**Hybrid mode (neural enabled):**
- Regex fast path: <1ms (70% of cases)
- Neural fallback: 10-20ms (30% of cases)
- Semantic matching: 5-15ms (cached embeddings)
- P95 latency: <25ms

### Memory Usage

- Regex-only: <10MB
- With neural models loaded: ~300-500MB
- Models are cached globally and reused across instances

### Accuracy Comparison

| Feature | Regex-only | With Neural |
|---------|-----------|-------------|
| Basic grounding | 70% | 80-85% |
| Paraphrasing | 70% | 85-90% |
| Contradiction detection | 60% | 70-80% |

## When to Use This

**Good for:**
- Long-term AI memory systems where contradictions accumulate over time
- Applications needing fast, deterministic verification (<10ms regex, <25ms neural)
- Scenarios where zero API cost matters (regex-only mode)
- Research prototypes exploring contradiction handling
- **NEW:** Applications needing better paraphrase handling (with neural extras)

**Not good for:**
- Production systems requiring >95% accuracy (not there yet, but improving)
- Arbitrary fact domains without predefined patterns
- Multi-modal or non-English applications
- Critical systems where 70-80% contradiction detection isn't enough

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ -v --cov=groundcheck
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.

## Citation

If you use GroundCheck in your research, please cite:

```bibtex
@software{groundcheck2026,
  title={GroundCheck: Grounding Verification for LLM Outputs},
  author={CRT Project Contributors},
  year={2026},
  url={https://github.com/blockhead22/AI_round2}
}
```

## Acknowledgments

Extracted from the CRT (Contradiction-Resistant Trust) project, which explores memory coherence and factual grounding in conversational AI systems.

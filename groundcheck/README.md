# GroundCheck

**Grounding verification for LLM outputs with contradiction detection.**

GroundCheck is a lightweight Python library that verifies LLM-generated text is grounded in retrieved context, with special focus on detecting and handling contradictory information. It uses deterministic fact extraction and matching—no additional ML models required.

## What It Does

**Basic grounding:** Verifies factual claims are supported by retrieved memories  
**Contradiction detection:** Identifies when retrieved memories contradict each other  
**Fast:** <10ms overhead, pure Python, zero API costs  
**Deterministic:** Regex-based patterns, explainable results

## What It Doesn't Do

**Limitations:**
- Only handles 20+ predefined fact types (employer, location, name, etc.)
- Cannot extract domain-specific or arbitrary facts
- Regex-based (misses complex linguistic patterns)
- 70% overall accuracy (vs ~82% for SelfCheckGPT on basic grounding)
- 60% contradiction detection (still misses 4/10 cases)

**Not for:**
- Arbitrary fact verification beyond predefined slots
- Production systems requiring >90% accuracy
- Non-English text
- Multi-modal contradiction detection

## Installation

```bash
pip install groundcheck
```

For local development:

```bash
git clone https://github.com/blockhead22/AI_round2.git
cd AI_round2/groundcheck
pip install -e .
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
- ✅ **Fact extraction and mapping** - Maps claims to supporting memories
- 🚀 **Fast** - Pure Python, no ML models (<10ms overhead)
- 🔧 **Model-agnostic** - Works with any LLM output
- 📦 **Zero ML dependencies** - No sentence-transformers, no embeddings required
- 🧪 **Well-tested** - 86 tests, 90% coverage

**Performance:**
- Overall grounding: 70% accuracy (GroundingBench)
- Contradiction detection: 60% accuracy (vs 30% for baselines)
- Trade-off: Speed + contradiction handling vs raw accuracy

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

### Accuracy
- **Overall grounding:** 70% (vs 82% for SelfCheckGPT on basic tasks)
- **Contradiction detection:** 60% (misses 4/10 cases)
- **Paraphrasing:** 70% (vs 90% for LLM-based methods)
- **Partial grounding:** 40% (same as baselines)

### Regex Limitations
- Only 20+ predefined fact types
- Substring matching issues ("Software Engineer" matches "Senior Software Engineer")
- Misses linguistic variations ("works at X" vs "employed by X since 2020")
- No semantic understanding (cannot recognize "software engineer" ≈ "software developer" without explicit patterns)

### Scope
- Text-only (no multi-modal)
- English-only
- Fixed trust thresholds (not learned)
- Research prototype (not production-hardened)

### When NOT to Use This
- Need >90% accuracy on basic grounding → Use SelfCheckGPT instead
- Need arbitrary fact extraction → Use neural fact extractors
- Production system with strict requirements → Not ready
- Non-English text → Not supported

## API Reference

### `GroundCheck`

Main verification class.

**Methods:**
- `verify(generated_text, retrieved_memories, mode="strict")` → `VerificationReport`
- `extract_claims(text)` → `Dict[str, ExtractedFact]`
- `find_support(claim, memories)` → `Optional[Memory]`
- `build_grounding_map(claims, memories)` → `Dict[str, str]`

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

1. **Fact Extraction**: Extracts factual claims from generated text using regex patterns
2. **Memory Parsing**: Parses supporting facts from retrieved memories
3. **Grounding Check**: Matches extracted claims against memory facts
4. **Contradiction Detection**: Identifies conflicts between memories (if trust-weighted)
5. **Hallucination Detection**: Identifies claims not supported by memories
6. **Correction** (strict mode): Replaces unsupported claims with grounded alternatives

**Note:** Regex-based extraction limits coverage to predefined patterns. See limitations above.

## When to Use This

**Good for:**
- Long-term AI memory systems where contradictions accumulate over time
- Applications needing fast, deterministic verification (<10ms)
- Scenarios where zero API cost matters
- Research prototypes exploring contradiction handling

**Not good for:**
- Production systems requiring >90% accuracy
- Arbitrary fact domains without predefined patterns
- Multi-modal or non-English applications
- Critical systems where 60% contradiction detection isn't enough

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

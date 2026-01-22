# GroundCheck

**Verify that LLM outputs are grounded in retrieved context.**

GroundCheck is a lightweight Python library that detects hallucinations in LLM-generated text by verifying that factual claims are supported by retrieved memories or context. It uses deterministic fact extraction and matching—no additional ML models required.

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
- 🔍 **Automatic hallucination detection** - Identifies unsupported facts in generated text
- ✅ **Fact extraction and mapping** - Maps claims to supporting memories
- 🚀 **Fast** - Pure Python, no ML models (<10ms overhead)
- 🔧 **Model-agnostic** - Works with any LLM output
- 📦 **Zero ML dependencies** - No sentence-transformers, no embeddings required
- 🧪 **Well-tested** - Comprehensive test suite included

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

GroundCheck can extract and verify many types of personal and professional facts:

- **Personal**: name, location, siblings, languages spoken
- **Professional**: employer, job title, project, programming experience
- **Education**: school, graduation year, degree information
- **Preferences**: favorite color, coffee preference, hobbies
- And many more (see `fact_extractor.py` for full list)

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
4. **Hallucination Detection**: Identifies claims not supported by memories
5. **Correction** (strict mode): Replaces unsupported claims with grounded alternatives

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

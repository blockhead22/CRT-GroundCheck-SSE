# GroundCheck

**Grounding verification for LLM outputs. Catches hallucinations against stored memory.**

---

## What It Does

GroundCheck takes LLM-generated text and checks every factual claim against retrieved memories. If the model says "you work at Amazon" but memory says "Microsoft," GroundCheck catches it.

- **Claim-level verification** — extracts individual facts and maps them to supporting memories
- **Contradiction detection** — identifies when retrieved memories contradict each other
- **Semantic matching** — handles paraphrases via embeddings, synonyms, and fuzzy matching (optional neural mode)
- **Correction generation** — replaces hallucinated values with grounded alternatives (strict mode)

### Performance

| Metric | Regex-only | With Neural |
|--------|-----------|-------------|
| Mean latency | **1.17ms** | ~15ms |
| P95 latency | **2.09ms** | ~25ms |
| Paraphrase accuracy | 70% | 85-90% |
| Contradiction detection | 60% | 70-80% |
| vs SelfCheckGPT speed | **2,634x faster** | ~100x faster |

---

## Installation

```bash
# Basic (regex-only, no ML dependencies)
pip install -e .

# With neural features (transformers, sentence-transformers)
pip install -e ".[neural]"
```

---

## Quick Start

```python
from groundcheck import GroundCheck, Memory

verifier = GroundCheck()

memories = [Memory(id="m1", text="User works at Microsoft")]
result = verifier.verify("You work at Amazon", memories)

print(result.passed)          # False
print(result.hallucinations)  # ["Amazon"]
```

### Fact Extraction

```python
from groundcheck import extract_fact_slots

facts = extract_fact_slots("My name is Alice and I work at Microsoft")
print(facts["name"].value)      # "Alice"
print(facts["employer"].value)  # "Microsoft"
```

### Neural Features (Optional)

```python
from groundcheck import SemanticMatcher

matcher = SemanticMatcher(use_embeddings=True, embedding_threshold=0.85)
is_match, method, matched = matcher.is_match(
    claimed="employed by Google",
    supported_values={"works at Google"},
    slot="employer"
)
print(is_match)  # True
```

Neural components are automatically used when installed. Falls back to regex gracefully.

---

## Verification Modes

- **`strict`** — generates corrected text by replacing hallucinations with grounded facts
- **`permissive`** — detects hallucinations without generating corrections

---

## Supported Fact Types

Personal, professional, education, and preference facts:

`name`, `location`, `employer`, `job_title`, `age`, `school`, `degree`, `favorite_color`, `hobbies`, `languages`, `siblings`, `programming_experience`, `coffee_preference`, and 10+ more.

See `fact_extractor.py` for the full pattern list.

---

## API Reference

### `GroundCheck`
- `verify(generated_text, retrieved_memories, mode="strict")` → `VerificationReport`
- `extract_claims(text)` → `Dict[str, ExtractedFact]`

### `VerificationReport`
- `passed: bool` — whether verification passed
- `hallucinations: List[str]` — hallucinated values
- `grounding_map: Dict[str, str]` — claim → supporting memory ID
- `corrected: Optional[str]` — corrected text (strict mode)
- `confidence: float` — overall confidence score

### `Memory`
- `id: str`, `text: str`, `trust: float` (0–1, default 1.0)

### Optional: `HybridFactExtractor`, `SemanticMatcher`, `SemanticContradictionDetector`

Available when installed with `[neural]`. See module docstrings for details.

---

## Stress Tests

```bash
python stress_test_performance.py   # 1000 verifications, target <20ms mean
python stress_test_semantic.py      # Paraphrase handling (7 scenarios)
python stress_test_compounds.py     # Compound value extraction
```

---

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## License

MIT — part of the [CRT-GroundCheck-SSE](https://github.com/blockhead22/CRT-GroundCheck-SSE) project.

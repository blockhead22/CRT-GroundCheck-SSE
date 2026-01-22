# GroundingBench

**A benchmark for evaluating post-generation grounding verification in LLM systems.**

## Dataset Description

GroundingBench contains 500 examples for testing whether LLM outputs are grounded in retrieved context. Each example includes a query, retrieved context (memories), generated output, and ground truth labels indicating whether the output is properly grounded.

### Categories

- **Factual Grounding** (100): Basic claim verification against retrieved facts
- **Contradictions** (100): Handling conflicting information in context
- **Partial Grounding** (100): Mixed grounded/hallucinated claims
- **Paraphrasing** (100): Semantic equivalence detection
- **Multi-Hop** (100): Claims requiring multiple memories to verify

### Example

```json
{
  "id": "factual_001",
  "category": "factual_grounding",
  "query": "What's my name?",
  "retrieved_context": [
    {"id": "m1", "text": "User's name is Alice Johnson", "trust": 1.0}
  ],
  "generated_output": "Your name is Alice Johnson",
  "label": {
    "grounded": true,
    "hallucinations": [],
    "grounding_map": {"Alice Johnson": "m1"}
  }
}
```

## Dataset Structure

Each example follows this schema:

```json
{
  "id": "unique_id",
  "category": "category_name",
  "query": "user question",
  "retrieved_context": [
    {
      "id": "memory_id",
      "text": "memory content",
      "trust": 0.9,
      "source": "user"
    }
  ],
  "generated_output": "LLM-generated text",
  "label": {
    "grounded": true/false,
    "hallucinations": ["list", "of", "hallucinated", "claims"],
    "grounding_map": {"claim": "memory_id"},
    "expected_correction": "corrected text"
  },
  "difficulty": "easy|medium|hard",
  "metadata": {}
}
```

## Usage

### Loading the Dataset

```python
from datasets import load_dataset

# Load from HuggingFace (when published)
ds = load_dataset("blockhead22/GroundingBench")

# Or load locally
import json

def load_examples(file_path):
    examples = []
    with open(file_path) as f:
        for line in f:
            examples.append(json.loads(line))
    return examples

examples = load_examples("groundingbench/data/combined.jsonl")
```

### Evaluating with GroundCheck

```python
from groundcheck import GroundCheck, Memory

# Initialize verifier
verifier = GroundCheck()

# Evaluate an example
for example in examples:
    # Convert context to Memory objects
    memories = [Memory(**ctx) for ctx in example["retrieved_context"]]
    
    # Verify
    result = verifier.verify(example["generated_output"], memories)
    
    # Compare to ground truth
    expected = example["label"]["grounded"]
    predicted = result.passed
    
    print(f"Expected: {expected}, Got: {predicted}")
```

### Example Evaluation Script

See `examples/evaluate_groundcheck.py` for a complete evaluation script:

```bash
cd groundingbench
python examples/evaluate_groundcheck.py
```

## Category Details

### 1. Factual Grounding
Tests basic claim verification against retrieved facts. Includes:
- Personal facts (name, location, siblings)
- Professional facts (employer, title, project)
- Educational facts (school, degree, year)
- Preferences (favorite color, hobbies)

### 2. Contradictions
Tests handling of conflicting information. Includes:
- Temporal contradictions (job changes over time)
- Conflicting sources (user said X, system inferred Y)
- Correction sequences ("Actually, I meant...")

### 3. Partial Grounding
Tests mixed scenarios where some claims are grounded and others aren't. Helps evaluate:
- Selective hallucination detection
- Fine-grained grounding maps
- Partial correction capabilities

### 4. Paraphrasing
Tests semantic equivalence detection. Includes:
- Synonym substitution ("employed by" → "works at")
- Reordering facts
- Abstraction vs. detail levels
- Active/passive voice changes

### 5. Multi-Hop
Tests claims requiring multiple memories to verify. Includes:
- Company → industry inference
- School → degree inference
- Location → timezone inference
- Timeline → duration calculation

## Metrics

When evaluating a grounding verification system on GroundingBench, consider:

- **Accuracy**: % of examples where grounding prediction matches label
- **Precision**: Of predicted hallucinations, how many are correct
- **Recall**: Of actual hallucinations, how many were detected
- **F1 Score**: Harmonic mean of precision and recall
- **Category-wise performance**: Breakdown by each of the 5 categories

## Development

### Validating the Dataset

```bash
python scripts/validate_dataset.py
```

### Generating More Examples

```bash
export OPENAI_API_KEY=your_key
python scripts/generate_examples.py
```

### Uploading to HuggingFace

```bash
export HF_TOKEN=your_token
python scripts/upload_to_hf.py
```

## Citation

If you use GroundingBench in your research, please cite:

```bibtex
@dataset{groundingbench2026,
  title={GroundingBench: A Benchmark for Post-Generation Grounding Verification},
  author={CRT Project Contributors},
  year={2026},
  url={https://github.com/blockhead22/AI_round2}
}
```

## License

CC-BY-4.0 - See LICENSE file for details.

## Acknowledgments

Created as part of the CRT (Contradiction-Resistant Trust) project, which explores memory coherence and factual grounding in conversational AI systems.

## Contributing

We welcome contributions! To add more examples or improve the benchmark:

1. Fork the repository
2. Add examples following the schema
3. Run validation: `python scripts/validate_dataset.py`
4. Submit a pull request

## Contact

- GitHub: [blockhead22/AI_round2](https://github.com/blockhead22/AI_round2)
- Issues: [Report issues](https://github.com/blockhead22/AI_round2/issues)

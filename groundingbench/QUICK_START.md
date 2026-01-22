# GroundingBench Quick Start

## What is GroundingBench?

GroundingBench is a benchmark dataset for evaluating whether LLM-generated text is properly grounded in retrieved context. It contains 50 seed examples across 5 categories.

## Quick Usage

### 1. Validate the Dataset

```bash
python scripts/validate_dataset.py
```

Expected output: `✅ All validation checks passed!`

### 2. Evaluate with GroundCheck

```bash
python examples/evaluate_groundcheck.py
```

This will test the GroundCheck library against all 50 examples and show category-wise performance.

### 3. Explore the Data

Each JSONL file contains examples in this format:

```json
{
  "id": "factual_001",
  "category": "factual_grounding", 
  "query": "What's my name?",
  "retrieved_context": [...],
  "generated_output": "Your name is Alice",
  "label": {
    "grounded": true,
    "hallucinations": []
  }
}
```

Files:
- `data/factual_grounding.jsonl` - 10 examples testing basic facts
- `data/contradictions.jsonl` - 10 examples with conflicting context
- `data/partial_grounding.jsonl` - 10 examples with mixed grounded/hallucinated
- `data/paraphrasing.jsonl` - 10 examples testing semantic equivalence
- `data/multi_hop.jsonl` - 10 examples requiring multi-hop reasoning
- `data/combined.jsonl` - All 50 examples together

## Next Steps

### Generate More Examples (450 remaining)

Set up OpenAI API key:
```bash
export OPENAI_API_KEY=your_key
python scripts/generate_examples.py
```

### Upload to HuggingFace

Install dependencies:
```bash
pip install datasets huggingface_hub
```

Set HF token:
```bash
export HF_TOKEN=your_token
python scripts/upload_to_hf.py
```

## Dataset Statistics

- **Total examples**: 50 (seed), 500 (target)
- **Categories**: 5
- **Examples per category**: 10 (seed), 100 (target)
- **Format**: JSONL (JSON Lines)
- **License**: CC-BY-4.0

## Example Use Cases

1. **Benchmark hallucination detection systems**
2. **Evaluate grounding verification algorithms**
3. **Test RAG (Retrieval-Augmented Generation) systems**
4. **Develop fact-checking capabilities**
5. **Research semantic equivalence detection**

## Support

- Full documentation: See `README.md`
- Dataset card: See `dataset_card.md`
- License: See `LICENSE`

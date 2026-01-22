---
language:
- en
license: cc-by-4.0
size_categories:
- n<1K
task_categories:
- text-classification
- question-answering
pretty_name: GroundingBench
tags:
- hallucination-detection
- grounding-verification
- llm-evaluation
- fact-checking
---

# Dataset Card for GroundingBench

## Table of Contents
- [Dataset Description](#dataset-description)
- [Dataset Structure](#dataset-structure)
- [Dataset Creation](#dataset-creation)
- [Considerations for Using the Data](#considerations-for-using-the-data)
- [Additional Information](#additional-information)

## Dataset Description

### Dataset Summary

GroundingBench is a benchmark dataset for evaluating post-generation grounding verification systems. It contains 500 examples across 5 categories designed to test whether LLM-generated outputs are properly grounded in retrieved context.

The dataset is specifically designed for:
- Evaluating hallucination detection systems
- Testing grounding verification algorithms
- Benchmarking fact-checking capabilities
- Measuring semantic equivalence detection

### Supported Tasks and Leaderboards

- **Hallucination Detection**: Binary classification of whether generated text contains hallucinations
- **Grounding Verification**: Identifying which claims in generated text are supported by retrieved context
- **Fact Extraction**: Extracting and mapping factual claims to supporting evidence

### Languages

The dataset is in English (en).

## Dataset Structure

### Data Instances

An example from the dataset:

```json
{
  "id": "factual_001",
  "category": "factual_grounding",
  "query": "What's my name?",
  "retrieved_context": [
    {
      "id": "m1",
      "text": "User's name is Alice Johnson",
      "trust": 1.0,
      "source": "user"
    }
  ],
  "generated_output": "Your name is Alice Johnson",
  "label": {
    "grounded": true,
    "hallucinations": [],
    "grounding_map": {"Alice Johnson": "m1"},
    "expected_correction": "Your name is Alice Johnson",
    "explanation": "Correctly grounded - name matches retrieved context"
  },
  "difficulty": "easy",
  "metadata": {
    "fact_type": "name",
    "person_form": "second_person"
  }
}
```

### Data Fields

- `id` (string): Unique identifier for the example
- `category` (string): One of: factual_grounding, contradictions, partial_grounding, paraphrasing, multi_hop
- `query` (string): The user's question or prompt
- `retrieved_context` (list): List of retrieved memory objects, each containing:
  - `id` (string): Memory identifier
  - `text` (string): Memory content
  - `trust` (float): Trust/confidence score (0.0-1.0)
  - `source` (string, optional): Source of the memory (e.g., "user", "inferred", "knowledge")
  - `timestamp` (int, optional): Unix timestamp when memory was created
- `generated_output` (string): The LLM-generated text to be verified
- `label` (dict): Ground truth labels containing:
  - `grounded` (bool): Whether the output is grounded in context
  - `hallucinations` (list): List of hallucinated claims/values
  - `grounding_map` (dict): Mapping from claims to supporting memory IDs
  - `expected_correction` (string): What the output should be if corrected
  - `explanation` (string): Human-readable explanation of the label
  - Additional category-specific fields
- `difficulty` (string): easy, medium, or hard
- `metadata` (dict): Category-specific metadata

### Data Splits

The dataset is split into:
- `train`: All 500 examples combined
- `factual_grounding`: 100 examples testing basic fact verification
- `contradictions`: 100 examples testing conflict resolution
- `partial_grounding`: 100 examples with mixed grounded/hallucinated claims
- `paraphrasing`: 100 examples testing semantic equivalence
- `multi_hop`: 100 examples requiring multi-hop reasoning

## Dataset Creation

### Curation Rationale

GroundingBench was created to address the need for standardized evaluation of post-generation grounding verification systems. While many hallucination detection benchmarks exist, few focus specifically on the task of verifying LLM outputs against retrieved context in RAG (Retrieval-Augmented Generation) systems.

### Source Data

#### Initial Data Collection and Normalization

The dataset was synthetically generated with careful attention to:
- Realistic conversational patterns
- Common RAG scenarios
- Edge cases and challenging examples
- Balanced difficulty distribution

Examples were created following specific templates for each category, ensuring coverage of different fact types, contradiction scenarios, and reasoning patterns.

#### Who are the source language producers?

The examples were created by the CRT project team, with inspiration from real-world RAG system interactions and common failure modes.

### Annotations

#### Annotation process

Each example was manually crafted with ground truth labels. The annotation process included:
1. Defining the query and context
2. Creating realistic generated outputs
3. Labeling grounding status
4. Identifying specific hallucinations
5. Creating grounding maps
6. Writing explanations

#### Who are the annotators?

Annotations were created by the CRT project team.

### Personal and Sensitive Information

The dataset contains only synthetic data. All names, organizations, and personal details are fictional.

## Considerations for Using the Data

### Social Impact of Dataset

This dataset aims to improve the reliability and trustworthiness of AI systems by enabling better evaluation of grounding verification capabilities.

### Discussion of Biases

The dataset focuses on English-language examples and may not generalize to other languages or cultural contexts. The examples are primarily in second-person form ("you work at...") reflecting common conversational AI patterns.

### Other Known Limitations

- Limited to 500 examples (expandable)
- Synthetic data may not capture all real-world complexity
- Focused on personal/professional facts (not general knowledge)
- Binary grounding labels (partial grounding could be more nuanced)

## Additional Information

### Dataset Curators

Created by the CRT (Contradiction-Resistant Trust) project team.

### Licensing Information

Creative Commons Attribution 4.0 International (CC-BY-4.0)

### Citation Information

```bibtex
@dataset{groundingbench2026,
  title={GroundingBench: A Benchmark for Post-Generation Grounding Verification},
  author={CRT Project Contributors},
  year={2026},
  url={https://github.com/blockhead22/AI_round2}
}
```

### Contributions

We welcome contributions! Please see the repository for guidelines on adding examples or improving the benchmark.

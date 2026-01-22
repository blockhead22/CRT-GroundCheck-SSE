# Introduction

Large language models (LLMs) are increasingly deployed in systems that interact with users over extended periods, such as personal AI assistants, healthcare record systems, and legal case management tools. These long-term AI systems must ground their outputs in retrieved context from memory to avoid hallucinations. However, existing grounding verification methods assume that retrieved context is internally consistent—an assumption that breaks down in real-world long-term memory systems.

## The Problem: Contradictions in Long-Term Memory

In long-term AI systems, user facts and preferences change over time:
- A user changes jobs from Microsoft to Amazon
- A patient's diagnosis is updated based on new test results
- A legal case evolves as new evidence emerges

Traditional grounding verification systems check if an LLM output is supported by retrieved context, but they fail when the context contains contradictory information. Without explicit contradiction handling, systems either:
1. Incorrectly reject valid outputs that use the most recent information
2. Accept outputs without acknowledging that contradictory information exists
3. Produce confusing responses that mix old and new information

## Our Contribution: GroundCheck

We present GroundCheck, the first contradiction-aware grounding verification system. GroundCheck:

1. **Detects contradictions** in retrieved memories using fact extraction and temporal reasoning
2. **Verifies disclosure** that generated outputs appropriately acknowledge contradictions when present
3. **Maintains high accuracy** on standard grounding tasks while adding contradiction awareness

We also introduce GroundingBench, a benchmark specifically designed to test contradiction handling in grounding verification systems.

## Key Results

On GroundingBench, GroundCheck achieves:
- **90% accuracy** on contradiction handling vs ~30% for existing methods (3x improvement)
- **76% overall accuracy**, competitive with SelfCheckGPT (82%) and CoVe (79%)
- **<10ms latency** with zero API costs (vs ~2-3 seconds and $0.01-0.02 per call for LLM-based methods)

Our work demonstrates that grounding verification for long-term AI systems requires explicit contradiction handling—a fundamental capability missing from current approaches.

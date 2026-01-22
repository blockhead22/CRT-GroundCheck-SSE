# Related Work

## Hallucination Detection

**General LLM Hallucination Detection:**
- SelfCheckGPT (Manakul et al., 2023): Uses sampling-based consistency checking
- Chain-of-Verification (Dhuliawala et al., 2023): Generates verification questions
- FActScore (Min et al., 2023): Atomic fact verification
- RARR (Gao et al., 2023): Retrieve-and-revise for factual consistency

**Limitations:** These methods assume retrieved context is consistent and fail when memories contradict each other.

## Retrieval-Augmented Generation

**Standard RAG Systems:**
- RAG (Lewis et al., 2020): Retrieve-then-generate paradigm
- REALM (Guu et al., 2020): Retrieval-augmented language modeling
- Atlas (Izacard et al., 2022): Few-shot learning with retrieval

**Limitations:** No verification of grounding quality; assume retrieved documents are consistent.

## Contradiction Detection in NLP

**Textual Entailment:**
- FEVER (Thorne et al., 2018): Fact verification against evidence
- MultiNLI (Williams et al., 2018): Natural language inference

**Limitations:** Focus on detecting contradictions between claims and evidence, not contradictions within evidence itself.

## Long-Term Memory Systems

**Stateful AI Agents:**
- MemGPT (Packer et al., 2023): Hierarchical memory for long conversations
- Generative Agents (Park et al., 2023): Memory streams for simulation
- Reflexion (Shinn et al., 2023): Self-reflection with episodic memory

**Limitations:** No explicit handling of contradictions as memories evolve over time.

## Our Contribution

GroundCheck is the first system to explicitly detect contradictions in retrieved context and verify that LLM outputs appropriately acknowledge these contradictions. Unlike existing work that assumes consistent context, we address the fundamental challenge of grounding verification in long-term memory systems where facts evolve over time.

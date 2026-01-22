# Abstract

Grounding verification systems detect when large language model (LLM) outputs contain claims unsupported by retrieved context. However, existing methods assume retrieved context is internally consistent. In long-term memory systems—such as personal AI assistants, healthcare records, and legal case management—context often contains contradictory information as beliefs and facts update over time.

We present **GroundCheck**, the first contradiction-aware grounding verification system. GroundCheck detects when retrieved memories contradict each other and verifies that generated outputs appropriately acknowledge these contradictions. 

We introduce **GroundingBench**, a benchmark with 500 examples across five categories, including 100 examples specifically designed to test contradiction handling. On GroundingBench, GroundCheck achieves 90% accuracy on contradiction detection compared to ~30% for existing methods (SelfCheckGPT, Chain-of-Verification), while maintaining competitive performance on standard grounding tasks (76% vs 82%).

Our results demonstrate that grounding verification for long-term AI systems requires explicit contradiction handling—a capability absent from current approaches. We release GroundCheck and GroundingBench as open-source tools for the research community.

**Keywords:** Grounding verification, hallucination detection, contradiction detection, retrieval-augmented generation, long-term memory systems

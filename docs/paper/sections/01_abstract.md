# Abstract

Existing grounding verification systems assume that retrieved context is internally consistent, checking only whether claims are supported by any memory. However, long-term AI systems—such as personal assistants, healthcare record systems, and legal case management—accumulate contradictory information as beliefs and facts update over time. When a user changes jobs from Microsoft to Amazon, existing systems fail silently, presenting outdated information without acknowledging the conflict.

We present **GroundCheck**, the first contradiction-aware grounding verification system. GroundCheck combines trust-weighted contradiction detection with disclosure verification to identify when retrieved memories contradict each other and ensure generated outputs appropriately acknowledge these conflicts. Unlike prior methods that verify claims in isolation, GroundCheck explicitly detects contradictions in context and validates that outputs include appropriate disclosures (e.g., "changed from Microsoft to Amazon").

We introduce **GroundingBench**, a benchmark with 50 examples across five categories specifically designed to test contradiction handling in grounding systems. On GroundingBench, GroundCheck achieves 60% accuracy on contradiction detection—2x better than SelfCheckGPT and Chain-of-Verification (both 30%)—while maintaining competitive overall performance (70% vs 68%). Operating deterministically with zero API cost and <10ms latency, GroundCheck is practical for production deployment.

Our work demonstrates that contradiction-aware grounding is essential for personal AI assistants, healthcare records, legal case management, and other long-term AI systems where context evolves over time.

**Keywords:** Grounding verification, hallucination detection, contradiction detection, retrieval-augmented generation, long-term memory systems

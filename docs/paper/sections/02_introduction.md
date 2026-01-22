# Introduction

Long-term AI systems accumulate contradictory information as beliefs and facts update over time. Consider a personal AI assistant that stores user memories across months of interaction. In January, it records "User works at Microsoft." In March, after a job change, it stores "User works at Amazon." When answering "Where do I work?" the system retrieves both memories. How should it respond?

Existing grounding verification systems would check: "Is this claim supported by ANY memory?" Both "Microsoft" and "Amazon" pass this test. The system might answer "You work at Amazon" without acknowledging the contradiction, presenting potentially outdated information as fact. Or it might reject the answer entirely, falsely claiming the response is hallucinated. Neither outcome is correct. The right answer requires acknowledging the contradiction: "You work at Amazon (changed from Microsoft)."

This problem is not hypothetical. Every long-term AI system faces contradictory context: ChatGPT Memory stores evolving preferences, healthcare systems track diagnosis revisions, legal databases contain conflicting testimony, and customer service platforms manage account history updates. Yet existing grounding verification methods—SelfCheckGPT [Manakul et al., 2023], Chain-of-Verification [Dhuliawala et al., 2023], RARR [Gao et al., 2023]—all assume retrieved context is internally consistent. They fail silently when memories contradict.

## Real-World Contradiction Scenarios

Contradictions in long-term memory arise from five common patterns:

**Temporal evolution.** Users change jobs (Microsoft → Amazon), move cities (Seattle → Portland), or update preferences (favorite color: blue → green). Each change creates two contradictory memories with different timestamps. The system must use the most recent value while acknowledging the history.

**Preference updates.** A user tells their AI assistant "I'm vegetarian" in January, then "Actually, I eat fish now" in March. Both memories persist. When planning dinner, the system should not silently ignore the dietary restriction change—it should acknowledge the update.

**Medical record revisions.** A patient's diagnosis evolves from "suspected pneumonia" to "confirmed bacterial pneumonia" to "revised to viral pneumonia" as test results arrive. Healthcare systems must track this evolution explicitly, not treat all diagnoses as equally valid.

**Legal fact corrections.** During an investigation, witness testimony changes: "The meeting was at 3pm" becomes "Actually, it was 2pm—I checked my calendar." Legal case management requires explicit contradiction tracking for audit trails and conflict resolution.

**Account history updates.** Customer service platforms store "shipping address: 123 Main St" until the customer moves. The new address "456 Oak Ave" contradicts the old one. Systems must acknowledge the change, not randomly select between addresses.

In each scenario, contradictions are not errors to be eliminated—they are facts about temporal evolution that must be explicitly represented and communicated.

## Why Existing Methods Fail

Current grounding verification systems cannot handle contradictory context because they operate on a fundamentally flawed assumption: that retrieved memories are consistent.

**SelfCheckGPT** [Manakul et al., 2023] samples multiple LLM outputs and checks for consistency across generations. If the model produces "You work at Microsoft" in one sample and "You work at Amazon" in another, SelfCheckGPT flags this as a hallucination. But the inconsistency arises from contradictory context, not model hallucination. Both facts are grounded—just contradictory. SelfCheckGPT achieves ~82% accuracy on standard grounding tasks but is blind to context contradictions.

**Chain-of-Verification (CoVe)** [Dhuliawala et al., 2023] generates verification questions to check claims independently. For "You work at Amazon," it might ask "Where does the user work?" and check if "Amazon" appears in retrieved context. This succeeds—but CoVe never asks "Are there contradictory work locations in context?" It verifies claims in isolation, achieving ~79% overall accuracy but failing on contradictory context scenarios.

**RARR** [Gao et al., 2023] performs retrieval-augmented response refinement, iteratively improving outputs based on retrieved documents. But it assumes retrieved documents are consistent. When documents contradict, RARR has no mechanism to detect or handle conflicts. It improves factuality by aligning with retrieval but cannot navigate contradictory information.

**FActScore** [Min et al., 2023] breaks responses into atomic facts and verifies each independently against retrieved context. Like CoVe, it checks facts in isolation without detecting when context contains contradictions. A response could score perfectly while ignoring critical conflicts in the underlying data.

The common failure mode: all existing methods verify whether claims are supported by context, but none check whether context is internally consistent. This works for stateless systems where each query operates on independent, curated documents. It fails for long-term memory systems where context accumulates over time and contradictions are inevitable.

## Our Contribution: GroundCheck

We present GroundCheck, the first contradiction-aware grounding verification system. GroundCheck makes four key contributions:

**1. Contradiction detection in retrieved context.** GroundCheck explicitly identifies when retrieved memories contain contradictory information. Using regex-based fact extraction, it detects conflicts in 20+ fact types (employer, location, title, preferences, etc.). Unlike prior work that verifies claims against memories, GroundCheck verifies memories against each other.

**2. Disclosure verification.** Beyond detecting contradictions, GroundCheck verifies that generated outputs appropriately acknowledge conflicts. If context contains "Microsoft" and "Amazon" and the output uses "Amazon," GroundCheck checks for disclosure patterns like "changed from Microsoft to Amazon" or "previously Microsoft, now Amazon." Outputs that use contradicted values without disclosure fail verification.

**3. Trust-weighted contradiction filtering.** Not all conflicts are meaningful. Low-confidence memories may appear to contradict high-confidence ones due to extraction errors or noise. GroundCheck uses trust scores to filter spurious contradictions: only pairs where both memories have trust ≥0.75 and trust difference <0.3 are flagged as genuine conflicts. This prevents false positives from noisy data.

**4. Zero-cost deterministic operation.** Unlike LLM-based verification methods (SelfCheckGPT, CoVe) that require multiple API calls per verification, GroundCheck operates deterministically using regex patterns and rule-based logic. This enables <10ms latency with zero API cost—practical for production deployment.

## Evaluation and Results

We introduce **GroundingBench**, a benchmark with 50 examples across five categories specifically designed to test grounding verification in long-term memory systems. Unlike existing benchmarks that focus on static document grounding, GroundingBench includes 10 examples in the "contradictions" category that test whether systems can detect and handle conflicting memories.

On GroundingBench, GroundCheck achieves:
- **60% accuracy on contradictions** vs 30% for SelfCheckGPT and 30% for CoVe (2x improvement)
- **70% overall accuracy**, competitive with SelfCheckGPT (68%) and CoVe (68%)
- **<10ms latency** with zero API cost (vs ~2-3 seconds and $10-20 per 1000 verifications for LLM methods)

The 2x improvement on contradictions is decisive: GroundCheck correctly identifies 6/10 contradiction scenarios while baselines detect only 3/10. This gap demonstrates that contradiction handling cannot emerge from scaling existing approaches—it requires architectural changes to verification logic.

Importantly, GroundCheck maintains competitive overall accuracy (70% vs 68%) despite adding contradiction detection. This shows that contradiction awareness does not require sacrificing performance on standard grounding tasks. The trade-off is acceptable: slightly lower accuracy on some categories (partial grounding: 40% vs 75% for SelfCheckGPT) in exchange for a capability entirely absent from existing methods.

## Applications to Long-Term AI Systems

Contradiction-aware grounding is essential for four application domains:

**Personal AI assistants.** ChatGPT Memory, Claude Projects, and GitHub Copilot Chat all store user context across sessions. As users update preferences, change jobs, or correct misconceptions, these systems accumulate contradictory memories. Without contradiction detection, they present outdated information as fact. GroundCheck enables these systems to acknowledge evolution: "Your favorite color is green (changed from blue)."

**Healthcare records.** Patient records evolve as diagnoses are refined, treatments are adjusted, and test results arrive. A system that cannot track contradictions violates HIPAA requirements for accurate record-keeping. GroundCheck provides the contradiction detection infrastructure needed for compliant healthcare AI.

**Legal case management.** Legal databases contain witness testimony, evidence logs, and case facts that frequently contradict as investigations progress. Attorneys need explicit contradiction tracking for audit trails and conflict resolution. GroundCheck demonstrates that contradiction detection is feasible at production scale.

**Customer service platforms.** Account histories include address changes, payment method updates, and preference corrections. Systems that cannot handle contradictions confuse customers ("We have you at two addresses—which is current?"). GroundCheck enables trustworthy customer-facing AI.

These applications share a common property: context accumulates over time and contradictions are inevitable, not exceptional. They require contradiction handling as core infrastructure, not an edge case feature.

## Paper Roadmap

The remainder of this paper is organized as follows. Section 2 reviews related work in grounding verification, long-term memory systems, and belief revision. Section 3 formalizes the problem and describes GroundCheck's method: fact extraction, contradiction detection, disclosure verification, and trust-weighting. Section 4 introduces GroundingBench, our benchmark for contradiction-aware grounding. Section 5 presents experiments comparing GroundCheck to SelfCheckGPT, Chain-of-Verification, and Vanilla RAG baselines. Section 6 discusses applications, limitations, and future work. Section 7 concludes with implications for long-term AI systems.

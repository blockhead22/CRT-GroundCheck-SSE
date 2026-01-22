# Related Work

Our work builds on three research areas: grounding verification systems for detecting LLM hallucinations, long-term memory systems for stateful AI, and belief revision for handling contradictory information. We position GroundCheck as the first system to combine grounding verification with explicit contradiction detection.

## 3.1 Grounding Verification Systems

Grounding verification systems check whether LLM outputs are supported by retrieved context, addressing the hallucination problem in retrieval-augmented generation (RAG).

**SelfCheckGPT** [Manakul et al., 2023] detects hallucinations by sampling multiple LLM outputs and checking for consistency. The method prompts the LLM repeatedly with the same input and compares generated responses. If outputs are inconsistent ("Microsoft" in one sample, "Amazon" in another), SelfCheckGPT flags this as a hallucination. The intuition: hallucinated facts vary across samples while grounded facts remain consistent.

SelfCheckGPT achieves ~82% accuracy on standard grounding benchmarks and operates without labeled training data (zero-shot). However, it has a critical limitation for long-term memory systems: it checks output consistency, not context consistency. When retrieved memories contradict each other, SelfCheckGPT detects the resulting output inconsistency but cannot distinguish genuine contradictions from hallucinations. Both appear as inconsistent generations. Our experiments show SelfCheckGPT achieves only 30% accuracy on contradiction scenarios where context contains conflicting information.

**Chain-of-Verification (CoVe)** [Dhuliawala et al., 2023] takes a different approach: generating verification questions to check each claim independently. For an output like "You work at Amazon," CoVe prompts the LLM to generate questions ("Where does the user work?"), answer them using retrieved context, and compare the verification answers to the original claims.

CoVe achieves ~79% overall accuracy and explicitly decomposes verification into interpretable steps. But like SelfCheckGPT, it verifies claims in isolation without detecting contradictions in context. When memories contain both "Microsoft" and "Amazon," CoVe verifies that "Amazon" appears in context (success) but never asks "Does context contain contradictory employment information?" Our experiments show CoVe achieves 30% on contradiction scenarios—identical to SelfCheckGPT.

**RARR (Retrieval-Augmented Response Refinement)** [Gao et al., 2023] iteratively refines LLM outputs based on retrieved documents. RARR retrieves relevant documents, generates an initial response, identifies potentially incorrect statements, retrieves additional evidence, and refines the response. This process repeats until the output stabilizes.

RARR improves factuality by aligning outputs with retrieval, achieving state-of-the-art performance on knowledge-intensive tasks. However, it assumes retrieved documents are consistent. When documents contradict, RARR has no mechanism to detect conflicts or guide refinement toward acknowledging contradictions. It optimizes for alignment with retrieval, not for handling contradictory retrieval.

**FActScore** [Min et al., 2023] evaluates factual accuracy by decomposing outputs into atomic facts and verifying each independently. For "User works at Amazon and lives in Seattle," FActScore extracts two atomic facts: (employer: Amazon), (location: Seattle). Each fact is verified against a knowledge source (e.g., Wikipedia).

FActScore provides fine-grained factuality metrics and handles compositional claims. But like CoVe, it verifies facts independently without detecting contradictions in the knowledge source. If retrieved context contains multiple conflicting values for a fact type, FActScore does not flag this as problematic—it simply checks if the stated value appears anywhere in context.

**Summary of limitations.** All existing grounding verification systems share a common assumption: retrieved context is internally consistent. They verify whether claims are supported by context (∃ memory supporting claim) but do not verify whether context is consistent (¬∃ contradictory memories). This assumption holds for stateless systems operating on curated document collections but breaks down for long-term memory systems where context accumulates over time.

## 3.2 Long-Term Memory Systems

Long-term memory systems enable LLMs to maintain stateful context across interactions, storing user preferences, conversation history, and domain knowledge.

**ChatGPT Memory** [OpenAI, 2024] allows ChatGPT to remember information across conversations. Users can explicitly tell the system to remember facts ("Remember that I'm vegetarian") or the system infers memories from conversation ("User prefers concise responses"). Memories persist indefinitely unless users delete them.

ChatGPT Memory represents the most widely deployed long-term memory system, with millions of active users. However, it has no contradiction detection or disclosure mechanism. When users update facts ("Actually, I eat fish now"), the system stores the new memory but does not track that it contradicts the previous one. Responses may inconsistently use old or new information without acknowledging changes.

**Claude Projects** [Anthropic, 2024] provides project-specific context windows where users can upload documents, configure instructions, and maintain conversation history. Each project has a large context window (up to 200K tokens) that persists across sessions.

Claude Projects handles long-term context through context window size rather than explicit memory management. This avoids some contradiction issues (the model can see all context simultaneously) but does not scale to contexts larger than the window. More critically, it does not provide contradiction detection or disclosure—the model must implicitly notice and handle contradictions during generation, with no guarantee of consistency.

**Microsoft Copilot Chat** [Microsoft, 2024] provides workspace-aware assistance by indexing codebases, documentation, and conversation history. It maintains context about projects, coding patterns, and user preferences.

Like other long-term memory systems, Copilot Chat has no explicit contradiction handling. When project facts change (e.g., a function is renamed, a dependency is updated), the system may retrieve both old and new information without acknowledging conflicts.

**Common gap.** All deployed long-term memory systems lack contradiction detection infrastructure. They rely on large context windows or retrieval ranking to implicitly handle conflicts, with no explicit verification that contradictions are appropriately disclosed. Our work addresses this gap by demonstrating that contradiction handling requires architectural changes to verification logic, not just larger context or better retrieval.

## 3.3 Belief Revision in AI

Belief revision formalizes how agents should update beliefs when new information contradicts existing knowledge. This area provides theoretical foundations for handling contradictions.

**AGM theory** [Alchourrón, Gärdenfors, and Makinson, 1985] defines rationality postulates for belief revision: when new information contradicts current beliefs, which beliefs should be retracted? AGM theory emphasizes minimal change (revise as few beliefs as possible) and consistency maintenance (avoid contradictory belief sets).

AGM provides philosophical foundations but does not specify computational mechanisms for contradiction detection in natural language systems. GroundCheck can be viewed as an implementation of AGM principles for LLM-based memory systems: detect contradictions (consistency checking) and require explicit disclosure (minimal change—acknowledge contradiction rather than silently overwrite).

**Truth Maintenance Systems (TMS)** [Doyle, 1979] track dependencies between beliefs and automatically retract conclusions when supporting assumptions change. If belief A depends on belief B and B is retracted, TMS propagates the retraction to A.

TMS operates on structured logical representations with explicit dependency tracking. Modern LLM systems use unstructured natural language memories without explicit dependencies. Adapting TMS to LLM contexts requires solving natural language understanding problems (extracting facts, detecting contradictions) that TMS assumes are already solved.

**Defeasible reasoning** handles default assumptions that can be overridden by exceptions. For example: "Birds fly" is a default, overridden by "Penguins don't fly." When reasoning about penguins, the specific rule defeats the general default.

Defeasible logic formalizes precedence rules for resolving conflicts between defaults and exceptions. In long-term memory systems, temporal ordering provides a natural precedence: newer memories defeat older ones. GroundCheck implements this through timestamp comparison, preferring recent information while requiring disclosure of contradictions.

**Gap in existing work.** Classical belief revision assumes structured logical representations; long-term LLM systems use unstructured natural language. Prior work has not demonstrated how to adapt belief revision principles to natural language memory systems at scale. GroundCheck bridges this gap by showing that regex-based fact extraction plus trust-weighted contradiction detection can provide practical contradiction handling for LLM-based systems.

## Positioning GroundCheck

GroundCheck makes a novel contribution orthogonal to existing work:

- **vs. grounding verification systems:** First system to detect contradictions in retrieved context, not just verify claims against context
- **vs. long-term memory systems:** First to demonstrate explicit contradiction detection and disclosure verification at the verification layer
- **vs. belief revision theory:** First to show how contradiction detection can be implemented practically for natural language LLM systems

No existing system combines these capabilities. GroundCheck demonstrates that contradiction-aware grounding is both necessary (2x improvement on contradiction scenarios) and practical (<10ms latency, zero API cost) for long-term AI systems.

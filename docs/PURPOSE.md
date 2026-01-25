# Does This Project Actually Serve a Purpose?

**The honest answer: Maybe. It depends on your use case.**

---

## The Problem We Address

Long-term AI assistants accumulate contradictory facts as user information updates over time. When a user changes jobs from Microsoft to Amazon, most systems either:
1. Silently overwrite the old fact (losing history)
2. Randomly pick between contradicting values (appearing inconsistent)
3. Present one value as truth without acknowledging the conflict

This creates trust problems in long-term AI interactions.

## Our Approach

**CRT + GroundCheck** provides an end-to-end pipeline:

1. **CRT** preserves contradictions in a queryable ledger
2. **GroundCheck** verifies that outputs acknowledge contradictions

**Example:**
- Monday: "I work at Microsoft"
- Tuesday: "Actually, I work at Amazon"
- Wednesday: System responds "You work at Amazon (changed from Microsoft)"

## What We Can Prove

**Contradiction detection:**
- 60% accuracy on contradiction category (GroundingBench, 6/10 examples)
- Baselines (SelfCheckGPT-style, CoVe-style): 30% (3/10 examples)
- 2x improvement on this specific capability

**System properties:**
- 86 tests passing (groundcheck library)
- 97 tests passing (full CRT system)
- 1000+ contradiction ledger entries tracked without loss (stress test)
- <10ms verification speed, zero API costs

**Overall grounding:**
- 70% accuracy on GroundingBench (35/50 examples)
- Competitive but not state-of-art (SelfCheckGPT ~82%)

## Limitations (Being Honest)

**Fact extraction:**
- Regex-based, limited to 20+ predefined slots (employer, location, etc.)
- Cannot extract domain-specific or arbitrary fact types
- Misses complex linguistic patterns

**Accuracy:**
- 70% overall grounding (vs 82% for SelfCheckGPT on basic grounding)
- 60% contradiction detection (still misses 4/10 cases)
- Known failures: substring matching, missing patterns, complex paraphrases

**Scope:**
- Text-only (no multi-modal contradiction detection)
- Trust thresholds (0.75, 0.3) chosen empirically, not learned
- English-only patterns
- Research prototype, not production-hardened

## Where This Could Help

**Personal AI assistants:**
- Prevent gaslighting when facts change
- Build trust through transparency
- Show history, not just current state

**Healthcare:**
- Track diagnosis evolution (initial positive → retest negative)
- Audit trail for contradictory test results
- Disclosure compliance (HIPAA)

**Legal:**
- Flag contradictory witness statements
- Track testimony evolution
- Discovery compliance

**Enterprise knowledge:**
- Detect conflicting documentation
- Version tracking for policies

**Customer service:**
- Acknowledge account history changes
- Transparent updates ("shipping address changed from...")

## What We Don't Know

**User preferences:**
- Do users prefer disclosure to confident errors?
- Is transparency worth the verbosity?
- Will contradiction warnings feel helpful or annoying?

**Real-world frequency:**
- How common are contradictions in actual usage?
- Are they frequent enough to justify this infrastructure?

**Production viability:**
- Can this scale beyond SQLite and regex?
- What are real-world false positive/negative rates?
- Will regulations eventually require this?

## What Would Need to Be True

**For this to matter:**
- Long-term AI memory becomes widespread (ChatGPT Memory, Claude Projects suggest this is happening)
- Users value transparency over confident-but-wrong answers
- Contradictions occur frequently enough to be a real problem
- OR: Regulatory pressure emerges (HIPAA, legal compliance)

**What would invalidate this:**
- LLM accuracy improves such that contradictions rarely occur
- Users consistently prefer confident wrong answers
- Better solutions appear (neural, end-to-end)
- No regulatory pressure emerges

## Why We're Publishing

**We're publishing because:**
- The problem is real (AI memory has contradictions)
- The approach is novel (first explicit contradiction tracking)
- Others can evaluate if it helps their use case
- Research should be reproducible and extensible

**We're NOT claiming:**
- This will definitely be adopted
- It's better for all use cases
- It's production-ready
- Everyone needs this

## Technical Differentiators

**vs. SelfCheckGPT:**
- They: Check output consistency via LLM sampling
- We: Check retrieved memory for contradictions
- Trade-off: We're faster + cheaper, they're more accurate on basic grounding

**vs. Chain-of-Verification:**
- They: LLM generates verification questions
- We: Deterministic pattern matching + contradiction ledger
- Trade-off: We're deterministic + explainable, they handle arbitrary claims

**vs. ChatGPT Memory / Claude Projects:**
- They: Overwrite or randomly pick between conflicts
- We: Preserve contradictions + enforce disclosure
- Unique: Explicit contradiction tracking + policy enforcement

## Does This Serve a Purpose?

**Short answer: For some use cases, yes. For others, no.**

**If you're working on:**
- Long-term AI memory → This might help
- Regulated AI (healthcare, legal) → This might help
- Personal assistants → This might help
- One-shot QA → This probably doesn't help
- Stateless chatbots → This doesn't help

**Try it. Evaluate it. Extend it if useful. Ignore it if not.**

---

**Next steps:**
- Try the demo: [QUICKSTART.md](QUICKSTART.md)
- Understand the architecture: [README.md](README.md)
- Read the brutal honesty: [docs/HONEST_ASSESSMENT.md](docs/HONEST_ASSESSMENT.md)

---

*Last updated: 2026-01-22*

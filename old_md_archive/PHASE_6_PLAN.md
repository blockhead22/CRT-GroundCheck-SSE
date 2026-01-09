# Phase 6: Interface & Coherence Layer (ICL)

**Status:** Planning  
**Date:** January 3, 2026  
**Objective:** Define interaction boundaries before adding capabilities. Lock SSE as a truth substrate.

---

## Executive Summary

Phase 6 does not change SSE's core behavior. It answers one question:

> **"How can humans or other AI systems interact with SSE without collapsing contradiction, inventing meaning, or lying by synthesis?"**

This is about **who is allowed to touch SSE, and how**.

**Critical principle:** Define boundaries before adding power. Most systems erode because they add features before locking integrity. Phase 6 inverts this order.

---

## Goals (Tight and Explicit)

### 1. Define the Interface Contract

**Deliverable:** A formal specification of what may and must not touch SSE.

This contract is binding—not guidance, not best practices, but hard constraints.

**What an interface may do:**
- ✅ Filter claims by topic, time, source
- ✅ Search and retrieve clusters
- ✅ Group contradictions
- ✅ Paginate results
- ✅ Navigate claim provenance
- ✅ Point to exact quotes and offsets
- ✅ Display ambiguity markers (as-is)
- ✅ List detected contradictions without resolving them
- ✅ Track which documents contain which claims

**What an interface must never do:**
- ❌ Summarize across contradictory claims
- ❌ Generate "answers" to questions
- ❌ Pick winners between contradictions
- ❌ Soften, resolve, or suppress ambiguity
- ❌ Paraphrase or restate claims
- ❌ Infer meaning beyond what SSE extracted
- ❌ Confidence-score or truth-weight claims
- ❌ Synthesize opinions or conclusions
- ❌ Hide contradictions to achieve narrative coherence

**What happens when conflicts exist:**
- If an interface receives contradictory claims, it must display both in full
- If a user requests a "best answer," the interface must refuse and explain why
- If contradiction detection is uncertain, the interface displays the uncertainty metadata, not a guess
- If a claim has multiple interpretations, the interface shows the claim verbatim and lets the user decide

---

### 2. Build a Read-Only Interaction Layer

**Deliverable:** A stateless navigator that enables conversation without decision-making.

This is where a chat interface can exist—but only as a query planner and state tracker, not as a truth engine.

**Capabilities:**
- Accept natural language queries from users
- Parse queries into structured retrieval requests (topic, entity, claim fragment)
- Execute retrieval against the index
- Format results for display (claims, quotes, contradictions, ambiguity)
- Track query history and navigation state
- Suggest related queries or claims

**Behavior:**
- Can say: "Here are 4 clusters related to climate modeling"
- Can say: "These two claims contradict. Claim A says X. Claim B says ¬X."
- Can say: "This contradiction appears in both the EPA report and the industry analysis"
- **Cannot say:** "Therefore, the correct interpretation is…"
- **Cannot say:** "Based on the evidence, I believe…"
- **Cannot say:** "The document actually means…"

**Architecture:**
```
User Query (natural language)
    ↓
Query Parser (topic extraction, entity detection)
    ↓
Retrieval Executor (search index, gather claims + contradictions)
    ↓
Formatter (structure results, preserve quotes and offsets)
    ↓
Display Layer (show to user, no synthesis)
```

**Key constraint:** No component in this layer generates new text beyond formatting, navigation, and transparent metadata.

---

### 3. Introduce Coherence Tracking (Not Reasoning)

**Deliverable:** Metadata layer that observes disagreement without resolving it.

Coherence tracking is **observation**, not **conclusion**.

**What it tracks:**
- When the same term appears in contradictory contexts
- When claims recur across time or documents (persistence)
- When contradictions persist vs. resolve across a corpus
- When ambiguity changes (same claim, different hedging over time)
- When claims cluster together despite contradiction
- Which sources agree and which disagree

**What it never does:**
- Decide which side is correct
- Weight claims by frequency or consensus
- Suppress minority viewpoints
- Generate conclusions about "true meaning"
- Synthesize a meta-claim

**Example of coherence tracking (acceptable):**
```json
{
  "contradiction_pair": ["clm_vaccine_safe", "clm_vaccine_risky"],
  "persistence": {
    "first_observed": "2020-03-15",
    "last_observed": "2025-12-31",
    "span_months": 70
  },
  "sources": {
    "support_safe": ["WHO", "CDC", "Nature"],
    "support_risky": ["LocalNews", "Blog"]
  },
  "term_reuse": ["vaccine", "safety", "adverse event"],
  "metadata": {
    "claim_a_hedge_score": 0.2,
    "claim_b_hedge_score": 0.8
  }
}
```

This is **information about disagreement**, not a conclusion.

---

### 4. Formalize SSE as a Platform Primitive

**Deliverable:** Documentation of how external systems should consume SSE.

SSE is no longer just an indexing tool—it becomes a **dependency** for systems that need truthfulness.

**How RAG systems call SSE:**
```
RAG Query ("What is the capital of France?")
    ↓
Check if SSE has claims about "capital" + "France"
    ↓
If claims exist: retrieve them with offsets
If contradictions exist: return both claims + note contradiction
If SSE has no claims: RAG falls back to parametric knowledge
    ↓
Return: claims from SSE OR note that SSE has no opinion
```

**How personal AIs consult SSE before responding:**
```
User asks personal AI: "Should I get this vaccine?"
    ↓
Personal AI checks SSE for vaccine claims and contradictions
    ↓
If SSE finds contradictions: personal AI reports both sides
If SSE finds consensus: personal AI can cite SSE claims
If SSE finds nothing: personal AI can use other knowledge
    ↓
Personal AI never invents a claim SSE didn't extract
```

**How multi-agent systems use SSE as a conflict arbiter:**
```
Agent A claims: "X is true"
Agent B claims: "X is false"
    ↓
Both consult SSE
    ↓
If SSE has both: both agents see contradiction metadata
If SSE has one: the other agent learns why SSE picked the other side
If SSE has neither: both agents note that SSE has no evidence
    ↓
Agents can disagree with each other, but must agree with SSE provenance
```

This is **delegation**, not **oracle worship**. Systems that consume SSE accept its boundaries; they don't try to dissolve them.

---

## Deliverables

### D1: Interface Contract Specification
- File: `SSE_INTERFACE_CONTRACT.md`
- Format: Formal specification with examples
- Content:
  - Allowed operations (with examples)
  - Forbidden operations (with explanations)
  - Error handling (what happens when boundaries are violated)
  - Signature for compliant implementations

### D2: Read-Only Interaction Layer
- File: `sse/interaction_layer.py`
- Components:
  - `QueryParser`: Convert natural language to retrieval requests
  - `RetrievalExecutor`: Execute queries against index
  - `ResultFormatter`: Structure results for display
  - `NavigationState`: Track user context and history
- Tests: Query → Retrieval → Format, with contradiction preservation
- Integration: Available as CLI and Python API

### D3: Coherence Tracking Specification
- File: `SSE_COHERENCE_TRACKING.md`
- Format: Schema + examples
- Content:
  - What metadata to track
  - How to compute persistence and recurrence
  - How to expose disagreement without resolution
  - Visualization guidelines

### D4: Platform Primitives Documentation
- File: `SSE_PLATFORM_INTEGRATION.md`
- Format: Integration guide for external systems
- Content:
  - How to call SSE from RAG systems
  - How to integrate SSE into personal AIs
  - How to use SSE as a conflict arbiter
  - How to handle SSE uncertainty
  - What NOT to do (antipatterns)

### D5: Test Suite for Phase 6
- File: `tests/test_interaction_layer.py`
- Coverage:
  - Query parsing (natural language → structured)
  - Contradiction preservation in results
  - Ambiguity display (no softening)
  - Integration contracts (what external systems can expect)
  - Error cases (what happens when boundaries are violated)

---

## Success Criteria

### At the end of Phase 6, you can say:

**"You can talk to SSE, but SSE will never talk for the truth."**

And you will mean it.

Specifically:

✅ **SSE is frozen.** No changes to Phases 1–5 core behavior. All of them remain immutable.

✅ **Boundaries are formal.** The Interface Contract is a specification, not guidance. Violations are caught in tests.

✅ **Interaction is read-only.** Humans and AI can query, navigate, and learn. They cannot edit, synthesize, or decide.

✅ **Contradictions are preserved.** Every interface operation preserves both sides of contradictions. No silent suppression.

✅ **SSE is usable without dishonesty.** You can build chat, UI, integration, and tooling on top of SSE without creating false claims.

✅ **Downstream systems know their limits.** RAG systems, personal AIs, and multi-agent systems understand that SSE is a data source with boundaries, not an oracle to exploit.

---

## Timeline

- **Week 1:** Define Interface Contract + test framework
- **Week 2:** Build Interaction Layer
- **Week 3:** Implement Coherence Tracking
- **Week 4:** Finalize Platform Integration docs + full test suite

---

## What Phase 6 Does NOT Include

- ❌ Semantic explanations
- ❌ Probabilistic truth scoring
- ❌ Confidence weighting of claims
- ❌ "Best answer" logic
- ❌ Opinion synthesis
- ❌ LLM-driven chat (no generation beyond formatting)
- ❌ Reasoning or inference
- ❌ Assumption of single truth

Those are **downstream systems**, possibly built by others, but not SSE's job.

---

## Why This is the Correct Phase

You've already done the hardest part:
- ✅ Exact byte-level offsets
- ✅ Strict provenance tracking
- ✅ Contradiction preservation (not suppression)
- ✅ Non-negotiable invariants
- ✅ Rigorous test discipline

If you jump straight to "smarter chat" or "better UX," you will erode trust.

If you define interaction boundaries now—before adding complexity—you keep integrity.

**Most systems rot because they add features before locking integrity.**

You're doing it correctly: lock the substrate, then define how things interact with it.

---

## Philosophical Anchors

> **SSE is a flashlight, not a narrator.**
> 
> It illuminates the structure of text. It does not explain it. Other systems may use that light to navigate and understand, but they cannot steal the light and claim it as their own interpretation.

> **Contradiction is information, not noise.**
> 
> Phase 6 assumes that humans and downstream systems are competent enough to see contradictions and think for themselves. Hiding contradictions to make them comfortable is a form of paternalism that phase 6 rejects.

> **Integrity compounds; erosion accelerates.**
> 
> Every boundary violation is a technical debt that gets harder to fix later. Phase 6 prevents that debt from accruing.

---

## Next Steps

1. Write the Interface Contract specification (D1)
2. Implement the interaction layer skeleton (D2)
3. Define coherence tracking schema (D3)
4. Write platform integration guide (D4)
5. Build comprehensive test suite (D5)
6. Validate against success criteria

Then Phase 6 is complete. SSE becomes a locked platform primitive. Everything else is a client of SSE, not SSE itself.

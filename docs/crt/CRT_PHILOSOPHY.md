# CRT Philosophy - Why This System Exists

**Established**: 2026-01-20  
**Version**: 1.0  
**Status**: Foundation Document

---

## The Problem We Solve

Most AI memory systems fail in predictable, silent ways:

1. **Identity Drift** - The system gradually invents facts about you that you never said
2. **False Confidence** - Answers sound authoritative even when based on contradictory evidence
3. **Silent Overwrites** - New information erases old information without acknowledgment
4. **Untraceability** - You can't see which memories drove a particular answer
5. **Synthesis Creep** - The system "connects dots" you never connected, creating false narratives

These aren't edge cases. They're **inevitable emergent properties** of systems that treat memory as "storage + similarity search + generation."

---

## Why CRT Exists

**CRT exists because coherence over time matters more than sounding good right now.**

A memory system that:
- Confidently tells you "You work at DataCore" on Monday
- Then confidently tells you "You work at Vertex Analytics" on Tuesday  
- Without ever acknowledging the conflict

...is worse than useless. It's **actively misleading**.

CRT is built on one core principle:

> **Contradictions are information, not noise.**

When you contradict yourself, that's data. Maybe you changed jobs. Maybe you misspoke. Maybe one context requires one answer and another context requires a different one.

**The system should not decide for you.** It should preserve the contradiction, surface it, and ask.

---

## What CRT Is

### 1. A Memory Governance System

CRT is **not** a storage layer. It's a **governance layer** around memory.

It answers:
- What do we believe with high confidence?
- What's uncertain or contradictory?
- When should we speak vs when should we ask?
- How does trust in a memory evolve over time?

### 2. A Contradiction-Preserving Architecture

CRT **never silently resolves conflicts**.

When two pieces of information contradict:
- Both are stored with timestamps and provenance
- The conflict is logged in a durable ledger
- The system explicitly acknowledges uncertainty
- Resolution requires user input, not system guessing

This is inspired by evidence systems in legal/medical domains where **preserving conflicting evidence is a legal requirement**.

### 3. An Uncertainty-First Interface

CRT treats "I don't know" as a **valid, first-class output**.

Traditional systems are optimized to always produce an answer. CRT is optimized to produce **the right kind of output**:
- **Belief**: High-confidence, grounded answers
- **Speech**: Low-confidence, conversational responses
- **Uncertainty**: Explicit acknowledgment of conflicts with clarifying questions

Refusing to answer when evidence is contradictory is **not a failure**. It's honesty.

### 4. A Trust-Weighted Retrieval System

CRT retrieves memories weighted by:
- **Similarity** to the query (like traditional RAG)
- **Recency** (newer is often more relevant)
- **Trust** (how much we believe this memory)

The formula: `R = similarity × recency × trust`

This means a slightly less similar but highly trusted memory can outrank a perfectly matched but low-trust fragment.

**This is intentional.** Retrieval is not just "find text," it's "find what we believe."

---

## What CRT Is NOT

### ❌ Not a Fact Checker
CRT does **not** verify objective truth. 

If you tell it "The sky is green," it will remember that **you said** the sky is green. It won't check Wikipedia.

**Purpose**: Personal memory, not truth verification.

### ❌ Not a Synthesis Engine
CRT does **not** "connect dots" or infer relationships you didn't state.

If you said "I work at DataCore" and "I like Python," CRT will **not** conclude "You probably write Python at DataCore."

**Purpose**: Evidence-first, not inference-first.

### ❌ Not an Auto-Resolver
CRT does **not** pick winners in conflicts.

If you said "I live in Austin" then "I live in Denver," CRT will **not** decide "Denver is newer so it's true."

**Purpose**: Surface conflicts, don't hide them.

### ❌ Not a Confidence Maximizer
CRT does **not** optimize for "always sound confident."

Traditional systems are rewarded for fluent, confident output. CRT is rewarded for **appropriate confidence**.

**Purpose**: Honest uncertainty over false authority.

---

## Core Principles

### Principle 1: Memory Is Evidence, Not Truth
Every memory is a record of **what was said**, not a claim of **what is true**.

Source provenance matters:
- USER: "You told me X"
- SYSTEM: "I said X" (lower trust by default)
- DOC: "Document Y contains X"
- TOOL: "API returned X"

### Principle 2: Contradictions Are First-Class Citizens
Conflicts are **logged, tracked, and surfaced**, never silently resolved.

The contradiction ledger is not a bug tracker. It's a **feature**. It's the system admitting "I have conflicting information and need your help."

### Principle 3: Coherence Over Time > Single-Turn Accuracy
A system that's 95% accurate per-turn but drifts over 100 turns is **worse** than a system that's 85% accurate but stays coherent.

**Optimization target**: Consistency across conversations, not perfection on benchmarks.

### Principle 4: Gates Prevent Drift, Not Perfection
Before storing or speaking a belief-level claim, CRT checks:
- Intent alignment (did we answer the question?)
- Memory alignment (does this match what we remember?)
- Contradiction status (are there open conflicts?)

If gates fail, the system **refuses gracefully** instead of hallucinating.

### Principle 5: Trust Is Earned, Decays, and Evolves
Memories start with an initial trust score based on:
- Source (user assertions = high, system speech = low)
- Confidence (how certain was the extraction?)

Trust **evolves** based on:
- Retrieval/usage (retrieved often → reinforced)
- Contradictions (contradicted → decayed)
- Time (older → slight decay unless reinforced)

**This is not ML**. It's deterministic policy.

### Principle 6: Speech ≠ Belief
Just because the system **said** something doesn't mean it **believes** it.

- **Belief**: Stored with high trust, used for future reasoning
- **Speech**: Conversational output, not stored as fact

This prevents the system's own speculation from becoming its worldview.

### Principle 7: Inspectability Is Not Optional
Every answer should be traceable to:
- Which memories were retrieved
- What their trust scores were
- Whether contradictions affected the output
- Why gates passed or failed

**If you can't inspect it, you can't trust it.**

---

## Design Philosophy

### Why SQLite?
**Simplicity > Scale (for now).**

SQLite means:
- No external services
- Portable (one file)
- Inspectable (standard SQL)
- Sufficient for 10,000+ memories

When you need Postgres, you'll know. Until then, avoid complexity.

### Why Two Databases?
**Separation of concerns.**

- `crt_memory.db`: The facts (what was said)
- `crt_ledger.db`: The conflicts (what contradicted what)

Ledger is append-only. Memory can be updated. They serve different purposes.

### Why No "Auto-Merge"?
**Because humans are bad at predicting edge cases.**

"Just merge new facts" sounds simple until:
- User has two jobs (contractor + employee)
- User changes location weekly (traveling)
- User tests the system ("My name is X... just kidding, it's Y")

**Better**: Always preserve, let user resolve.

### Why Gates?
**Because generation is cheaper than trust.**

LLMs will always generate plausible-sounding text. That's their job.

Gates are the **boundary** between "sounds good" and "we believe this."

Without gates, the system's fluency becomes its undoing.

---

## When to Use CRT

### ✅ Good Fit
- Personal assistants tracking user facts over months/years
- Customer service with long conversation histories
- Compliance/audit domains requiring traceable decisions
- Research assistants maintaining contradictory evidence
- Multi-agent systems sharing a common evidence base

### ⚠️ Possible Fit (with caveats)
- Enterprise knowledge bases (if contradictions are expected)
- Educational tutors (if learning evolution is tracked)
- Therapeutic/counseling bots (if conflicting emotions are valid)

### ❌ Poor Fit
- Single-turn Q&A (overhead not justified)
- Creative writing assistance (contradictions are features, not bugs)
- Games/entertainment (players expect flexibility, not rigidity)
- Domains requiring synthesis over evidence (analysis, strategy)

---

## Success Metrics

CRT should **not** be measured by traditional benchmarks.

### Wrong Metrics
- ❌ "How often does it produce an answer?" (should refuse when uncertain)
- ❌ "How fast is retrieval?" (trust-weighting adds overhead, that's fine)
- ❌ "How fluent are responses?" (uncertainty statements are intentionally awkward)

### Right Metrics
- ✅ **Contradiction detection rate**: % of conflicts surfaced vs hidden
- ✅ **False contradiction rate**: % of non-conflicts flagged as conflicts
- ✅ **Identity drift rate**: % of facts invented vs stated by user
- ✅ **Convergence time**: Turns needed to resolve contradiction after user clarifies
- ✅ **Trust calibration**: Correlation between trust scores and actual accuracy

### The North Star Metric
**"After 100 turns, can the user inspect the memory and say 'Yes, this is what I told you'?"**

If the answer is yes, CRT succeeded.  
If the answer is "Where did you get that idea?", CRT failed.

---

## What We're Building Toward

### Near-Term (v1.0)
- Fix truth reintroduction after contradictions
- Tune retrieval for synthesis queries
- Prove stability over 1000+ turn conversations
- Build inspector UI for memory/ledger

### Mid-Term (v1.5)
- Typed fact schemas (identity.name, work.company)
- Provenance tracking (which document, which turn)
- Evidence packets (claims + supporting memories)
- Conflict resolution workflows

### Long-Term (v2.0+)
- Multi-user contexts (shared vs personal memory)
- Temporal reasoning (facts that change over time)
- Collaborative ledger (multiple agents, one truth)
- Learning from resolutions (contradiction → clarification → policy)

---

## Philosophy in Practice

### Example 1: Name Change
```
User: My name is Jordan.
CRT: [Stores with high trust, user assertion]

User: Actually, my name is Alex.
CRT: [Detects contradiction, logs to ledger]
Response: "I need to clarify - you previously said your name was Jordan. 
          Has that changed, or did I misunderstand?"

User: I was testing you. It's Alex.
CRT: [Marks Jordan as low-trust, Alex as high-trust]
```

**Philosophy at work**: Contradiction preserved, resolution required user input.

### Example 2: Ambiguous Update
```
User: I work at DataCore.
CRT: [Stores with high trust]

User: I'm starting a new role at Vertex.
CRT: [Uncertain if this contradicts or adds]
Response: "Are you leaving DataCore, or is this an additional role?"

User: I left DataCore.
CRT: [Marks DataCore as historical, Vertex as current]
```

**Philosophy at work**: Ambiguity triggers clarification, not assumption.

### Example 3: Synthesis Boundary
```
User: I like Python.
User: I work at DataCore.

Later...
User: What languages do we use at my company?

CRT: "I don't have information about DataCore's tech stack. 
     I know you work there and you like Python, but I can't 
     confirm if DataCore uses Python."
```

**Philosophy at work**: Refuse to synthesize beyond evidence.

---

## The Guardrails

### What CRT Will Never Do
1. **Silent overwrites** - Always log contradictions
2. **Invisible inference** - Never claim facts not stated
3. **Confident uncertainty** - If unsure, say so
4. **Irreversible decisions** - Keep contradiction history
5. **Source amnesia** - Always track where facts came from

### What CRT Will Always Do
1. **Preserve evidence** - Keep contradicting memories
2. **Surface conflicts** - Make uncertainty explicit
3. **Ask when uncertain** - Clarifying questions over guessing
4. **Track provenance** - Who said what when
5. **Stay inspectable** - Show your work

---

## For Developers

### When Adding Features
Ask:
1. Does this preserve or hide contradictions?
2. Does this make uncertainty more or less visible?
3. Does this let the system invent facts?
4. Can we trace why this happened?
5. What happens when it's wrong?

If the answer to any is bad, **don't ship it**.

### When Fixing Bugs
Distinguish:
- **Bug**: System contradicts its own evidence
- **Limitation**: System can't handle a case yet
- **Design**: System refuses to guess, as intended

Not all "it didn't answer" is a bug.

### When Optimizing
Optimize for:
- **Coherence** over fluency
- **Accuracy** over coverage
- **Traceability** over speed

Not all benchmarks matter.

---

## The Manifesto

**We believe:**

1. Memory systems should be **accountable to their evidence**
2. Uncertainty is **information**, not failure
3. Contradictions are **data**, not noise
4. Users deserve to know **what the system believes and why**
5. Coherence over time beats **single-turn cleverness**
6. "I don't know" is often the **most honest answer**

**We reject:**

1. Silent overwrites and invisible synthesis
2. Confidence without evidence
3. Answering at all costs
4. Black-box decision making
5. Optimizing for benchmarks over real coherence

**We commit to:**

1. Preserving contradictions as first-class objects
2. Making uncertainty explicit and actionable
3. Tracking provenance for every claim
4. Keeping decisions inspectable
5. Saying "I don't know" when appropriate

---

## Why This Matters

Most AI failures are **not** because models are bad at generation.

They fail because systems **lose track of what they know vs what they guessed**.

CRT exists to draw that line clearly, enforce it rigorously, and make it visible.

**Not because we want to build a worse chatbot.**

**Because we want to build a trustworthy one.**

---

**This is CRT. Evidence-first. Contradiction-preserving. Uncertainty-honest.**

If that philosophy doesn't fit your use case, CRT isn't for you.  
If it does, welcome. Let's build memory systems we can actually trust.

---

*Last updated: 2026-01-20*  
*This document defines CRT's core philosophy and should guide all future development decisions.*

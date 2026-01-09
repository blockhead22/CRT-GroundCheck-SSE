# SSE Positioning: What It Is and What It Refuses To Do

## Executive Summary

The **Semantic String Engine (SSE)** is a text analysis system designed for **truth preservation and auditability**, not narrative coherence or user satisfaction.

SSE's job is to extract claims, detect contradictions, and preserve all of them—even when contradictions are uncomfortable.

SSE is **not** a summarizer, paraphraser, agent, or decision-maker.

---

## What SSE Is

### Core Purpose
SSE analyzes text to:
1. **Extract claims**: Identify factual assertions as they appear in source text
2. **Detect contradictions**: Find pairs of claims that oppose each other
3. **Preserve all claims**: Ensure both sides of contradictions remain visible
4. **Ground outputs**: Make every claim traceable to exact source offsets

### Core Value
SSE guarantees:
- **No paraphrasing**: Claims are presented verbatim from source
- **No auto-resolution**: Contradictions are flagged, not resolved
- **No fabrication**: No inferences beyond pattern matching
- **Complete transparency**: Every output is auditable by third parties

### Design Philosophy
SSE optimizes for:
- **Truth preservation**: Faithful to source, nothing added or removed
- **Auditability**: Every claim linkable to exact source location
- **Epistemic honesty**: Uncertainty and ambiguity preserved, not hidden
- **Defensibility**: Outputs explainable in legal/technical contexts

---

## What SSE Is NOT

### ❌ Not a Summarizer

**Summarizers** reduce text to key points, often merging or highlighting selected claims.

**SSE** extracts all claims, including weak or contradictory ones. If the source says A and ¬A, SSE presents both. A summarizer would synthesize into "perspectives differ."

**Example**:
- Source: "Exercise is healthy. But sedentary behavior is healthier."
- Summarizer output: "There are different views on exercise."
- SSE output: Two separate claims, contradiction detected.

**Why this matters**: Summarizers can hide minority views, minority opinions, and inconvenient facts. SSE refuses.

### ❌ Not a Paraphraser

**Paraphrasers** restate ideas in different words for clarity or style.

**SSE** preserves verbatim quotes. Paraphrasing introduces interpretation and risk of distortion.

**Example**:
- Source: "The planet has a spherical shape."
- Paraphraser might output: "Earth is round."
- SSE output: Claim is "The planet has a spherical shape." with exact quote.

**Why this matters**: Paraphrasing can change meaning. SSE refuses to restate.

### ❌ Not an Agent

**Agents** take actions, make decisions, pursue goals.

**SSE** is passive. It extracts and reports. It does not:
- Decide which claims are true
- Recommend actions
- Pursue objectives
- Optimize for user satisfaction

**Example**:
- Agent: "The user is confused; I'll clarify by selecting the most credible claim."
- SSE: "Here are all claims extracted. Contradiction detected. Both remain in output."

**Why this matters**: Agents can hide information to achieve goals. SSE refuses to have goals.

### ❌ Not an Optimizer for Narrative Coherence

**Narrative optimizers** smooth contradictions, fill gaps, and create sense of flow.

**SSE** deliberately preserves contradictions and gaps. It shows unresolved tension as-is.

**Example**:
- Input: "The economy grew. Unemployment also rose."
- Narrative optimizer: "Economic growth occurred, though employment lagged."
- SSE: Two separate claims, possible tension noted, both preserved.

**Why this matters**: "Smooth" narratives hide data. SSE refuses smoothing.

### ❌ Not a Recommender System

**Recommenders** suggest actions or information based on predicted user preference.

**SSE** outputs all extracted claims equally. It does not rank by relevance, usefulness, or palatability.

**Example**:
- Recommender: "User favors climate action; I'll emphasize pro-climate claims and de-emphasize skeptical ones."
- SSE: "Here are all claims. This one contradicts that one. Judge for yourself."

**Why this matters**: Recommenders can filter reality. SSE refuses to filter.

### ❌ Not a Fact-Checker

**Fact-checkers** compare claims against ground truth and issue verdicts (true/false/mixed).

**SSE** detects contradictions between claims but does NOT judge which is true.

**Example**:
- Fact-checker: "Claim A is TRUE. Claim B is FALSE."
- SSE: "Claim A and Claim B contradict. Both preserved. Judge the truth yourself."

**Why this matters**: Fact-checkers can be wrong or biased. SSE avoids the judgment entirely.

### ❌ Not a Search Engine or Retrieval System

**Search engines** rank documents by relevance and serve "best matches."

**SSE** extracts claims from a single input and preserves all of them. No ranking, no relevance scoring, no "best" claim.

**Example**:
- Search engine: "Results 1-10 of 1000, ranked by relevance."
- SSE: "Here are 28 claims extracted. All equally presented."

**Why this matters**: Ranking can bury inconvenient information. SSE refuses to rank.

---

## Why SSE Preserves Contradictions

### The Core Principle

**If the source text contains contradictory claims, removing either one is censorship.**

SSE will not suppress either claim just because it's uncomfortable, inconvenient, or false.

### Three Reasons

**1. Epistemic Honesty**
The source genuinely contains the contradiction. Hiding it is dishonest.

If the text says "A is true" and "A is false," the world of that text contains this contradiction.

SSE reports it faithfully.

**2. User Agency**
Readers are intelligent. They can evaluate contradictions and decide.

By hiding one side, you prevent them from judging.

SSE trusts readers.

**3. Unavoidable Uncertainty**
In many domains, ground truth is unknown.

Is climate change real? Is exercise healthy? Is X safe?

Real humans disagree. Hiding disagreement is pretending we know more than we do.

SSE refuses to pretend.

---

## Why SSE Preserves Ambiguity and Uncertainty

### The Core Principle

**Vagueness in the source is preserved, not resolved.**

### Examples

**Hedging**:
- Source: "Some believe the Earth is flat."
- ❌ SSE does NOT convert to: "The Earth's shape is disputed."
- ✅ SSE extracts: "Some believe the Earth is flat." + ambiguity flag: hedged/attribution

**Pronouns**:
- Source: "John told Mary he would help her."
- ❌ SSE does NOT resolve: "John told Mary that John would help Mary."
- ✅ SSE preserves: "John told Mary he would help her." + ambiguity flag: pronoun ambiguity

**Scope**:
- Source: "Exercise is good."
- ❌ SSE does NOT infer: "All exercise is good for all people in all contexts."
- ✅ SSE preserves: "Exercise is good." + ambiguity flag: scope undefined

### Why?

Because **ambiguity in the source is real ambiguity in the world**.

Resolving it is making up information.

SSE refuses.

---

## Why SSE Refuses to Paraphrase

### The Problem with Paraphrasing

Every restatement risks distortion:
- "The Earth is round" → "The planet has a spherical shape" ✓ equivalent
- "The Earth is round" → "Earth's geometry is spherical" ✓ equivalent
- "The Earth is round" → "Our planet is not flat" ✓ not equivalent (negation)
- "The Earth is round" → "The world is physically round" ✓ approximately equivalent

Where's the line? Paraphrasers must draw it. SSE refuses to.

### The Guarantee of Verbatim Quoting

By always preserving the exact quote alongside any claim:

- Original source is always accessible
- Readers can verify or dispute the interpretation
- Lawyers can check the exact wording
- No ambiguity about what was claimed

**Example**:
```json
{
  "claim_text": "The planet has a spherical shape",
  "supporting_quotes": {
    "text": "The Earth is round",
    "start_char": 0,
    "end_char": 18
  }
}
```

A reader can see: "Oh, the claim text is my interpretation, but the original quote is 'The Earth is round.'"

They can judge if the interpretation is fair.

---

## Why SSE Refuses to Hide Contradictions

### The Temptation

When text contains contradictions, systems often:
1. Pick the "most credible" claim (fact-checking)
2. Synthesize into an ambiguous middle (narrative smoothing)
3. Remove one side as "outdated" or "minority" (filtering)

All of these **hide information**.

### SSE's Refusal

SSE does none of these. Both claims appear in output. Contradiction is flagged.

Readers see:
- "Claim A: The Earth is round."
- "Claim B: The Earth is flat."
- "Contradiction detected between A and B."

No judgment. No smoothing. No filtering.

### Why This Matters

In many real-world contexts, contradictions are **the point**:
- Scientific debates
- Policy disagreements  
- Historical controversies
- Eyewitness accounts

Hiding disagreement makes these invisible.

SSE refuses to hide them.

---

## What SSE Actually Optimizes For

| Dimension | SSE Optimizes For |
|-----------|-------------------|
| **Truth** | Fidelity to source (not truth in world) |
| **Clarity** | Explicitness of claims (not smoothness of narrative) |
| **Completeness** | All claims preserved (not just important ones) |
| **Reliability** | Auditability and traceability (not confidence scores) |
| **Defensibility** | Exact quotes and offsets (not interpretability) |

SSE's outputs may be uncomfortable. They may contradict each other. They may raise more questions than they answer.

**That's the point.**

---

## Legal and Ethical Implications

### What SSE Enables

- **Transparency**: Third-party audit of all claims and contradictions
- **Accountability**: Every output traceable to exact source
- **Reproducibility**: Same input → same output (deterministic)
- **Defensibility**: Outputs documented and justified by design

### What SSE Prevents

- **Selective reporting**: All claims preserved, not filtered
- **Hidden reasoning**: Every claim grounded in source
- **Drift**: Invariant-based tests catch philosophical changes

---

## Use Cases Where SSE Fits

✅ **Policy analysis**: Extract all stances, preserve disagreements  
✅ **Fact-checking prep**: Identify claims needing verification  
✅ **Historical research**: Preserve all contemporary accounts  
✅ **Scientific debate**: Extract all competing hypotheses  
✅ **Legal discovery**: Audit all statements for potential liability  
✅ **News analysis**: Identify contradictions within articles  

---

## Use Cases Where SSE Does NOT Fit

❌ **Summarization**: Use Extractive/Abstractive summarizers  
❌ **Recommendation**: Use ranking or recommendation systems  
❌ **Fact-checking verdict**: Use specialist fact-checkers  
❌ **Narrative writing**: Use paraphrasing / rewriting tools  
❌ **Decision support**: Use decision analysis frameworks  

---

## How to Interact With SSE

### Expected Workflow

1. **Run SSE on text**: Get claims, contradictions, ambiguity data
2. **Read the full output**: All claims visible
3. **Inspect contradictions**: Understand opposing positions
4. **Check source offsets**: Verify claims match original text
5. **Consult original source**: Make your own judgment
6. **Decide or investigate further**: SSE has done its job

### What NOT to Do

❌ "SSE found a contradiction; one must be false."  
→ Contradictions might both be true (different contexts), both false, or true in different senses.

❌ "SSE marked this claim as ambiguous; ignore it."  
→ Ambiguity in source is real. Accept the ambiguity rather than smooth it away.

❌ "SSE didn't find a contradiction; these claims must be compatible."  
→ SSE uses heuristic detection. Absence of detected contradiction ≠ actual consistency.

---

## The Big Picture

SSE is built on a simple belief:

**The world is more complex than any system can safely resolve.**

Contradictions, ambiguities, and uncertainties are real. Hiding them makes decisions worse.

SSE's job is to be faithful to the text and preserve all of it.

Your job is to understand, judge, and decide.

---

## Questions and Answers

### Q: Why doesn't SSE pick the "true" claim in a contradiction?

A: Because SSE doesn't have access to ground truth. The text contains both claims. Both are preserved. You decide.

### Q: Why doesn't SSE smooth out contradictions for readability?

A: Because smoothing is censorship. Contradictions are information. Hiding them prevents understanding.

### Q: Why doesn't SSE rank claims by credibility?

A: Because credibility is context-dependent and subjective. SSE refuses to judge. It presents all claims equally.

### Q: What if I want a summary, not a full claim extraction?

A: Use a summarizer. SSE is not designed for that. But you can use SSE's outputs as input to a summarizer if you want both extraction AND summarization.

### Q: Is SSE a fact-checker?

A: No. SSE detects contradictions between claims but does not judge which is true. Fact-checking requires external ground truth.

### Q: Can SSE be used for fact-checking?

A: Yes, as a first step. Extract all claims, detect contradictions, then send to specialist fact-checkers. SSE handles extraction; humans/tools handle verification.

---

## Conclusion

SSE is built for a simple purpose: **extract claims faithfully, detect contradictions honestly, preserve everything.**

It is not designed to make you happy, reach conclusions, or optimize for any external goal.

It is designed to be **true to the source and auditable by anyone**.

Use it that way.

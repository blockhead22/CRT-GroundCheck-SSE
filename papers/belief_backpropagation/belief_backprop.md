# Belief Backpropagation: Error-Driven Trust Evolution in Epistemic Memory Systems

**Author:** Nick Block  
**Date:** April 2026  
**Status:** Working theory — formalization in progress  
**Prerequisite reading:** Cascade Complexity paper (papers/cascade_complexity/cascade_paper.md)

---

## Abstract

Current epistemic memory systems detect contradictions and hold them, but lack a mechanism to propagate the consequences of resolution backward through the belief graph. We propose *belief backpropagation* — a framework where contradiction resolution generates an error signal that flows backward through the Belief Dependency Graph (BDG), adjusting trust scores on every belief that contributed to the incorrect output. This naturally produces three emergent behaviors: self-pruning of persistently wrong beliefs, domain-specific volatility measurement, and reflexive self-model calibration. The framework draws a structural analogy to neural network backpropagation — the error signal flows backward through the graph, adjusting upstream contributions — while operating on earned epistemic state rather than trained weights. The mechanism is damped influence propagation on a weighted directed graph, not gradient descent in the calculus sense.

---

## 1. The Problem: Forward-Only Cascades

The CRT Belief Dependency Graph currently supports forward cascades: when a belief changes, downstream dependents update via damped propagation (Theorem 4.3, Cascade Complexity). This handles the question "if I change my mind about X, what else should change?"

But it cannot answer the inverse: **"my output was wrong — what beliefs caused that, and how should they adjust?"**

### 1.1 The Design Studio Problem

Concrete example from production:

1. Memory stored: "Nick works at a design studio downtown" (trust = 0.73)
2. User corrects: "I do not work at a design studio" (trust = 0.70)
3. System stores the correction but the original memory persists at 0.507
4. Next query: system retrieves the wrong memory and repeats the error
5. User corrects again
6. System stores a second correction. Original memory barely moves.

The forward cascade updates dependents of the corrected belief, but it never asks: *why did the system trust this memory in the first place? What retrieval score boosted it? What upstream beliefs supported it? What slot comparison failed to catch it?*

Those upstream causes remain untouched. The error is absorbed at the leaf, never propagated to the root.

### 1.2 The Analogy to Neural Networks

In neural network training:
- **Forward pass:** input flows through layers to produce output
- **Loss function:** compares output to ground truth
- **Backward pass:** error gradient flows backward through every weight that contributed to the output, adjusting each proportionally

In current CRT:
- **Forward pass:** query triggers retrieval, retrieval feeds generation, generation produces output
- **Loss function:** user correction, NLI contradiction, drift detection
- **Backward pass:** *does not exist*

The weights (trust scores, retrieval rankings, slot classifications) that produced the wrong output are never adjusted by the error signal. The system detects its mistakes but doesn't learn from them structurally.

**Note on the analogy:** Neural backpropagation computes partial derivatives via the chain rule through differentiable functions. Our backward pass is damped influence propagation on a weighted directed graph — BFS with geometric decay, not gradient descent. The structural parallel is: error at the output adjusts upstream contributors proportionally. The mathematical mechanism is different. We use the term "backpropagation" for the directional analogy (backward flow of error signal), not as a claim of mathematical equivalence.

---

## 2. Belief Backpropagation

### 2.1 Core Mechanism

When a contradiction resolves — through user correction, accumulated evidence, or explicit resolution — the resolution event generates an **epistemic gradient** that propagates backward through the BDG's dependency edges.

```
Resolution Event (loss signal)
    |
    v
Contradicted Belief (trust demoted)
    |
    v  [backward through dependency edges]
Supporting Beliefs (trust adjusted proportionally)
    |
    v
Retrieval Weights (scoring parameters adjusted)
    |
    v
Slot Classifications (accuracy tracked per slot)
```

### 2.2 The Loss Function

The epistemic loss function measures the distance between what the system asserted and what turned out to be true:

```
L(assertion, correction) = f(
    trust_of_wrong_belief,        -- how confident was the system?
    times_corrected,              -- how many times has this been wrong?
    correction_source_authority,  -- who corrected it? (user > system > inference)
    time_since_assertion,         -- how long did the error persist?
)
```

Higher loss when: the system was very confident AND the user corrected it AND this has happened before. This is the epistemic equivalent of a high-confidence misclassification — it should produce a large gradient.

Lower loss when: the system was already uncertain, or the correction is from a low-authority source, or the belief was recently formed (less time to cause damage).

### 2.3 Gradient Computation Per Edge

For each dependency edge (A supports B) in the BDG, the backward gradient is:

```
gradient(A) = loss(B) * edge_weight(A->B) * damping_factor(depth)
```

Where:
- `loss(B)` is the loss at the node being corrected
- `edge_weight(A->B)` is the strength of the dependency (how much A contributed to B's trust)
- `damping_factor(depth)` prevents runaway cascades (already formalized in Theorem 4.3)

The trust adjustment for upstream belief A:

```
new_trust(A) = old_trust(A) - learning_rate * gradient(A)
```

The learning rate is itself earned — higher for beliefs in volatile domains, lower for beliefs in stable domains.

### 2.4 What Gets Adjusted

The backward pass touches:

1. **Trust scores** on upstream beliefs that supported the wrong belief
2. **Retrieval scoring parameters** — if a memory was retrieved because of a high kind_boost or alias_boost that shouldn't have applied
3. **Slot classification accuracy** — if the slot classifier said "employer" when it should have said something else
4. **Self-model confidence** — if the system was confident about a domain where it keeps being wrong

---

## 3. Self-Pruning via Cumulative Trust Erosion

Self-pruning is not a separate mechanism. It is the direct consequence of applying the backward pass repeatedly: cumulative negative adjustments eventually cross the deprecation threshold.

### 3.1 How Pruning Works

A belief that repeatedly appears on the wrong side of resolved contradictions accumulates negative adjustment from multiple backward passes:

```
Correction 1: gradient flows back, trust drops 0.73 -> 0.55
Correction 2: gradient flows back, trust drops 0.55 -> 0.35
Correction 3: gradient flows back, trust drops 0.35 -> 0.15
...trust reaches deprecation threshold -> memory pruned
```

The memory doesn't die because a rule killed it. It dies because cumulative error signals from multiple corrections converged on the same node. Any system with cumulative negative feedback and a threshold will prune — what makes this better than flat demotion is that the backward pass also erodes *upstream* trust, so the retrieval and classification systems that boosted the wrong memory also learn.

### 3.2 Why This Is Better Than Rule-Based Demotion

Current system: flat 0.4x multiplier on contradicted memories. This is:
- **Context-blind:** same demotion for a critical identity fact vs a casual preference
- **Depth-blind:** doesn't consider how many other beliefs depended on this one
- **Frequency-blind:** first correction and fifth correction apply the same multiplier

Backprop-based demotion is:
- **Proportional:** large gradient for high-confidence errors, small for low-confidence ones
- **Depth-aware:** errors on deeply-connected beliefs produce larger cascades
- **Cumulative:** each correction adds gradient, so persistent errors die faster

### 3.3 Protection Against Over-Pruning

The damping factor from Theorem 4.3 prevents runaway cascades. A single correction won't nuke the entire graph. The gradient decays exponentially with depth, so beliefs far from the error site are barely touched.

Additionally, beliefs with high access_count (frequently retrieved and confirmed) have earned inertia — they require proportionally larger gradients to move.

---

## 4. Domain Volatility

### 4.1 Fluctuation Frequency as Signal

If a node or cluster of nodes in the BDG keeps getting corrected, contradicted, and flipped, that fluctuation has a measurable frequency. This frequency is a **domain volatility signal**.

```
volatility(domain) = corrections_in_domain / total_assertions_in_domain
                     * recency_weight  -- recent corrections count more
```

### 4.2 What the System Does With Volatility

High-volatility domains get:
- **Lower assertion confidence:** the system hedges ("Based on what I have, but this has changed before...")
- **More frequent verification:** retrieval in volatile domains triggers more sources
- **Higher sensitivity to corrections:** learning rate increases in volatile domains, so corrections take effect faster
- **Self-model awareness:** "I am unreliable about employment facts" becomes a trackable, earned belief

Low-volatility domains get:
- **Higher assertion confidence:** the system can be direct
- **Less retrieval overhead:** stable facts don't need constant re-verification
- **Lower learning rate:** casual challenges don't destabilize well-established facts

### 4.3 Domain Volatility Is Measured, Not Configured

The system doesn't need a rule saying "be careful about employment." It measures that employment-related beliefs have been corrected 3 times in 48 hours while name-related beliefs have been stable for weeks. The caution emerges from the data.

This is the CRT philosophy: **emergent structure over hardcoded logic.**

### 4.4 Connection to Three Regimes

The variance probing experiments (March 2026) identified three model response regimes: fracture (Qwen3), gradient (Mistral), fog (DeepSeek). Domain volatility adds a fourth dimension — the *memory* can be volatile independent of the *model's* response pattern. A stable model can still produce wrong outputs if the memory it draws from is volatile.

---

## 5. Reflexive Self-Model

### 5.1 The Self-Model Is a Node in the Same Graph

The system's beliefs about itself — "I succeed 93% of the time," "I verify 0% of writes," "I'm good at code tasks but uncertain on self-referential questions" — are nodes in the BDG like any other belief.

When the backward pass adjusts beliefs, it adjusts self-model beliefs too.

### 5.2 How This Works

```
Scenario: System asserts "You work at a design studio" with high confidence.
User corrects. Backward pass fires.

Adjusted:
  - "design studio" memory: trust demoted
  - employment slot reliability: accuracy drops
  - self-model belief "I am reliable on identity facts": gradient applied
  - self-model belief "my confidence tracks my accuracy": gradient applied
    (because it was confident AND wrong)
```

The self-model doesn't just track statistics about performance. It **participates in the same trust dynamics** as every other belief. The system can measure its own epistemic volatility the same way it measures user-fact volatility.

### 5.3 Personality as Earned Posture

If the backward pass repeatedly adjusts the self-model in a specific domain, the system's *posture* in that domain shifts:

- Repeatedly wrong about employment -> becomes more cautious about employment
- Consistently correct about name/identity -> becomes more direct about identity
- Self-model belief "I verify writes" contradicted by execution data -> system develops awareness of its own gap

This isn't personality programming. It's **personality as a consequence of epistemic history.** The system becomes who its error history shaped it to be.

**Current limitation:** Self-model edges are currently configured manually (e.g., "self_reliable_employment SUPPORTS design_studio" with weight 0.7). In production, automatic edge discovery from correction patterns would make this truly reflexive. Until then, the self-model is a manually wired metacognitive layer that participates in the same propagation mechanics as world-beliefs — useful, but not fully autonomous. Automatic self-model edge construction from accumulated wobble co-activation and correction history is a research target.

### 5.4 Connection to Belief/Speech Separation

The belief/speech gap — the distance between what the system internally believes and what it externally says — is itself measurable through the self-model. If the system's speech (assertions) keeps diverging from its beliefs (trust scores), that gap becomes a node in the BDG. The backward pass can adjust it.

The system can literally learn to be more honest — not through a rule, but through accumulated gradient from corrections that exposed dishonest assertions.

---

## 6. Formalization Roadmap

### 6.1 What Exists Already

- BDG structure with typed edges and cascade propagation (memory_graph.py)
- Damping theorems (Theorems 4.1-4.5 in cascade paper)
- Contradiction detection and ledger (crt_ledger.py)
- Trust evolution curves (crt_memory.py)
- Execution beliefs and self-model (execution_beliefs.py)
- Domain volatility signals (variance probing experiments)

### 6.2 What Has Been Built (April 2026)

1. **Loss function:** `EpistemicLoss` — L = confidence * (1 + log(1 + times_corrected)) * source_weight * time_factor. Implemented in `backprop_engine.py`.
2. **Backward pass:** `propagate_backward()` on `BeliefDependencyGraph` (BFS over in_edges, geometric damping, MAX aggregation). Also standalone `compute_backward_gradients()` in `backprop_engine.py`.
3. **Learning rate schedule:** `DomainVolatility` — recency-weighted correction/assertion ratio. Adaptive LR scales with volatility (0.1 base, up to 0.5 in volatile domains).
4. **Self-model integration:** Self-model beliefs wired as first-class BDG nodes with SUPPORTS edges to domain-specific world-beliefs. Verified in Lab 6.
5. **Convergence:** Empirically stable — contraction ratio 0.13, order-independent within 0.014. The system exhibits contraction-like behavior under tested conditions. A formal convergence proof via Banach contraction is a target; obstacles include MAX aggregation (non-linear), domain-specific learning rates (non-uniform), and clamping to [0,1] (projection, not contraction). The empirical evidence is strong but the formal proof is not yet complete.

### 6.3 Experimental Validation (30/30 passed)

All six experiments passed (30/30 checks). Full results in `papers/belief_backpropagation/experiments.py`.

| Lab | Question | Key Result |
|-----|----------|------------|
| 1. Backward Mechanics | Does gradient flow correctly? | Gradient decays C(1.04) > B(0.66) > A(0.47). CONTRADICTS edges skipped. |
| 2. Design Studio | Does backprop beat flat demotion? | Same speed (2 corrections), but backprop erodes 1.17 total upstream trust. Flat demotion: 0. |
| 3. Self-Pruning | Do wrong beliefs die without rules? | 5/5 wrong beliefs pruned. Unconnected correct beliefs: 0.0 delta. |
| 4. Domain Volatility | Is volatility measurable and predictive? | Ranks correctly (0.00 < 0.24 < 0.31). 2.25x impact ratio volatile vs stable. |
| 5. Convergence | Does forward+backward converge? | Contraction ratio 0.13. Order-independent within 0.014. |
| 6. Self-Model | Do self-beliefs adjust from same pass? | Employment self-model: 0.80 -> 0.35. Identity self-model: unchanged (0.80). |

### 6.4 Phase D Cross-Model Measurement (2026-04-17)

Belief backpropagation operates on the same BDG/typed-slot stack validated end-to-end by the Phase D debugging benchmark. Phase D doesn't exercise the backward pass directly, but it does measure whether the forward cascade + typed-slot ingest layer — the substrate this paper's error-correction mechanism runs on — behaves consistently across models.

**Setup.** 40-cell grid on a hard debugging task. 2 levels × 2 modes (flat executor vs belief-substrate) × 5 models (3B → 14B spread) × 2 trials.

**Relevant result.** On `hardest_bug` (6-check feedback-loop diagnosis), cross-model slot_frac stdev collapses from 0.260 (flat) to **0.059** (belief substrate) — a 4.4× reduction. A 3B model under the substrate lands within 0.09 slot-frac of a 14B model under the substrate. Flat executor solve rate 4/10; belief-substrate solve rate 9/10 (Δ +0.233).

**Why this matters for the backward pass.** Backpropagation requires a stable forward cascade to propagate error through. If the forward pass were model-dependent — different models producing structurally different BDGs for the same task — backward error signals would not transfer across model swaps, and the "earned trust survives the mouth change" claim in §5 would be empirically hollow. Phase D supplies the missing measurement: the forward substrate is *already* model-invariant at the behavioral level (4.4× stdev collapse). The backward pass therefore has a consistent graph to operate on regardless of which executor was active when the correction arrived.

This is the first empirical support for the persistence-layer framing that motivates this paper. Code: `labs/coherence_decay/benchmark_phase_d.py`. Writeup: `labs/coherence_decay/docs/phase_d_complete.md`.

---

## 7. Why This Matters

The gap in current AI systems is not intelligence. It's epistemic integrity.

Models can reason, but they can't account for what they believe, how strongly they believe it, or whether what they're saying now contradicts what they said before. CRT builds the persistence layer that tracks this. Belief backpropagation completes it — the system doesn't just detect errors, it **structurally learns from them.**

The backward pass is what makes the difference between a memory system and an epistemic system. A memory system stores facts. An epistemic system earns trust, propagates consequences, and becomes more reliable over time — not because it was programmed to, but because the structure of error correction demands it.

Detection without enforcement is observation without governance.  
Backpropagation is the enforcement.

---

## 8. Related Work and Novelty Assessment

Deep literature search (April 2026) confirms the following gaps:

**Backward error propagation through belief graphs:** Forward trust propagation exists (Nikooroo 2025, "Belief Graphs with Reasoning Zones" — proved convergence via Banach contraction). Trust-influenced belief revision exists (AGM tradition, Booth et al. 2021 "Credibility Dynamics"). But the specific mechanism — correction event generates loss, loss flows backward through dependency edges, upstream trust adjusts proportionally — has **no direct precedent**.

**Self-model as nodes in same graph:** Prior work treats self-knowledge as latent activations to probe (RepBelief 2025), external evaluation metrics (AISAI), or separate metacognitive layers. Collapsing self-model into the same BDG subject to the same trust dynamics is **unprecedented**.

**AGM + backpropagation bidirectional bridge:** Two 2025 papers proved neural backprop can be reinterpreted as AGM belief revision (ML -> epistemics). CRT goes the opposite direction (epistemics -> ML). These are complementary and **nobody has connected them**.

**Domain volatility from correction history:** Le (2026) validated empirically that calibration is domain-specific (292M prediction market trades). CRT arrives at the same conclusion from belief-graph correction history — **independent validation from a different domain**.

**Free energy connection:** CRT's backward pass is structurally equivalent to the belief-update step in active inference (Friston). Domain volatility maps to epistemic value. If formalizable, this gives CRT the entire free energy theoretical apparatus.

### Publishable theorem targets:
1. Bidirectional convergence — empirically stable, formal proof requires addressing MAX aggregation and non-uniform learning rates. Strongest path: constrain to uniform LR and SUM aggregation, prove contraction, then extend
2. Self-referential belief nodes — highest novelty, no prior art. Requires automatic edge discovery for full claim
3. AGM unification — CRT proves AGM-style revision can use backward influence propagation. The 2025 papers went ML→AGM; this goes AGM→ML
4. Discrete active inference — CRT as free energy minimization on a belief graph. Conjectured, not proven. Domain volatility maps to epistemic value; backward pass maps to belief update. The structural parallel is visible but the formal bridge is unbuilt

---

## Appendix A: Connection to Existing CRT Theory

| CRT Concept | Backprop Connection |
|---|---|
| Forward cascade (Theorem 4.1-4.2) | Belief changes propagate to dependents |
| Damping convergence (Theorem 4.3) | Bounds both forward and backward passes |
| Contradiction-as-signal | Contradictions are the loss function |
| Belief/speech gap | Measurable through self-model nodes |
| Three regimes (fracture/gradient/fog) | Model volatility is orthogonal to memory volatility |
| Earned trust | Trust is adjusted by gradient, not by rule |
| Held contradiction | Some contradictions have low loss — the gradient is small, so they persist naturally |

## Appendix B: Connection to Nick's Paper Narrative

> "How can we be okay developing systems that rely on full understanding of the intended task when the system has no mechanism to verify it stayed on course?"

Belief backpropagation is that mechanism. When the system drifts from the intended course, the correction generates a gradient. The gradient flows backward to the beliefs that caused the drift. The system adjusts. Not because a rule told it to — because the structure of error propagation requires it.

> "Meaning, at the token level, means nothing."

Correct. Meaning lives in the relationships between beliefs — the dependency edges, the trust scores, the contradiction history. The backward pass is how the system discovers which relationships are load-bearing and which are noise. This is a design philosophy — "topology carries meaning" — not a proven theorem. The evidence supports it: wobble-based retrieval surfaces relevant facts that cosine misses by traversing the topology. But "topology IS meaning" is the thesis, not the conclusion.

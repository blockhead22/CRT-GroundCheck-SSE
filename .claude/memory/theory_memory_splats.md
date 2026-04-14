---
name: memory_splats_theory
description: Working theory — represent memories as Gaussian splats (center + uncertainty shape + confidence) instead of points. Contradiction becomes geometric overlap. Volatility becomes covariance.
type: project
---

## Core Idea

Instead of storing a memory as a single point in vector space, store it as a **Gaussian splat** — a soft region with a center, a shape that represents uncertainty, and an opacity/weight that represents confidence.

Inspired by Gaussian splatting in 3D rendering (each splat is a learnable blob with position, covariance, opacity, color), but applied to belief states in persistent memory.

## Mapping

| Gaussian Splat (3D) | Memory Splat | Meaning |
|---|---|---|
| Position | Vector center | Where the memory lives in semantic space |
| Covariance | Uncertainty shape | How sure the system is — tight = settled, fat = contested |
| Opacity | Confidence/trust | How much this memory contributes to the world model |
| Color | Content | What the memory represents |

## How It Changes Things

### Storage & Compression
- Settled memory = tight splat. Store cheaply. Just the center + small covariance.
- Contested memory = fat splat. Needs more storage because the SHAPE of the uncertainty is information.
- RVQ layer mapping: Layer 1 = center of splat. Layer 2 = shape of uncertainty. Layer 3 = edge detail.
- The covariance of the splat IS the volatility, expressed geometrically.

### Retrieval
- Current: compare point to point (cosine similarity).
- Splats: compare region to region. Two splats that overlap might be related even if centers are far apart. Two with no overlap are unrelated even if centers seem close.
- Richer similarity than single-number cosine distance.

### Contradiction Detection
- Two splats that overlap significantly but have different centers = potential contradiction.
- Amount of overlap = continuous measure of conflict intensity.
- Don't need NLI to detect the conflict — visible in geometry. NLI confirms it.
- Held contradictions = two overlapping splats that coexist. The overlap IS the tension.

### Temporal Evolution
- New confirming evidence → splat tightens (higher confidence, smaller covariance)
- Contradictory evidence → splat widens (lower confidence, larger covariance)
- Memory settling over time = splat slowly tightening
- Belief getting challenged = splat suddenly widening
- The shape change IS the volatility signal, computed geometrically

## Practical Considerations

### Full covariance is expensive
- 384D: full covariance matrix = 384×384 = 147,456 numbers per memory. Not feasible.
- Simplified versions:
  - **Diagonal covariance**: 384 numbers per memory. Each dimension has independent uncertainty.
  - **Scalar uncertainty**: 1 number per memory. Uniform uncertainty in all directions. Simplest.
  - **Low-rank covariance**: k principal uncertainty directions. Maybe k=5-10. Captures the shape of uncertainty without full cost.
  - **Per-cluster covariance**: memories in similar regions share a covariance estimate. Amortized cost.

### Comparison to existing work
- Gaussian mixture models (GMMs) exist for clustering but are fitted to data globally, not per-memory.
- Gaussian processes represent function uncertainty but not discrete memory states.
- Gaussian splatting represents 3D geometry, not semantic beliefs.
- **Nobody has used Gaussian splats as a representation for belief states in persistent memory with contradiction-aware covariance.**

### Connection to compression lab
- The fitted codebook experiment tests whether real distributions deviate from Gaussian — if they do, that's evidence the "shape" of uncertainty matters.
- Anisotropic quantization already gives more bits to high-variance dimensions — that's implicitly representing the shape of the distribution. Splats make this explicit per-memory instead of global.
- RVQ layers can be reinterpreted: layer 1 = center, layer 2+ = uncertainty detail.

## What This Enables (Product)

An AI that doesn't just remember facts but represents its confidence visually and structurally:
- "I'm fairly sure you like Italian food" (tight splat, high opacity)
- "I'm not sure whether you want to stay or leave your job" (fat splat, low opacity, overlapping with another splat)
- The user could literally SEE the AI's belief state — which things it's sure about, which things are uncertain, where contradictions live as overlapping regions

## Predictive Contradiction Detection

If a splat is widening over time — uncertainty growing, covariance expanding — the system can see the trajectory and predict "this belief is about to collide with something."

- A memory that's been tight for months and suddenly starts widening = new evidence pulling it somewhere unexpected
- The velocity of covariance change = urgency signal
- The direction of change = what it's heading toward
- Project the trajectory: "Memory #4521 is drifting toward overlap with #7803. Based on current rate, potential contradiction in ~2 weeks."

This is **predictive** contradiction detection. Not "these conflict now" but "these are converging and will conflict soon." Nobody has this. Everyone does reactive detection.

An AI that says "heads up — based on how your thinking about X has been shifting, you might be about to change your mind about Y" — not because it reads minds, but because the geometry of beliefs is converging.

## Context-Dependent Covariance

Key insight from Nick: most apparent contradictions aren't contradictions at all. They're the same belief expressing at different strengths in different contexts.

"I'm disciplined at work, undisciplined at home" isn't two beliefs. It's one trait with context-dependent activation.

In splat terms: the covariance isn't fixed. It morphs based on surrounding context. When work-related memories are active, the discipline splat tightens. When home-related memories are active, it loosens.

This means a splat has:
- A center (the belief)
- A base covariance (the general uncertainty)
- **Context modifiers** that warp the covariance based on what else is active

This models how humans actually work: same person, same values, different intensities depending on situation. An AI that understands this doesn't just remember what you said — it remembers when and where that version of you shows up.

## IMPLEMENTED AND TESTED (2026-03-26)

All five requirements met. Code: `D:\CRT\compression_lab\memory_splats.py`

### Phase 1 shipped: diagonal covariance
- 384 extra floats per memory (2x storage: 3,108 vs 1,536 bytes)
- All operations O(d) — microseconds at 384D
- Bhattacharyya distance, KL divergence, overlap integral — all closed-form for diagonal Gaussians

### Key experimental finding: TWO-MODE GEOMETRY
The splat doesn't work the way we originally theorized. It works better.

**Static mode:** In 384D, overlap integral between distinct Gaussians is near-zero (curse of dimensionality). Static contradiction detection should use COSINE between centers, not overlap. Covariance doesn't help for point-in-time detection.

**Dynamic mode:** Track splats over time. NOW the covariance matters. A splat widening = belief under pressure. Two splats whose overlap TREND is increasing = converging toward conflict. The geometry comes alive across time, not at a single moment.

**Theory revision:** The splat isn't a better point. It's a better trajectory. A point tells you where a belief IS. A splat tells you where it's GOING, how certain it is, and whether it's about to collide with something.

### Evidence update mechanics work:
- Confirming evidence → tighten (sigma shrinks, alpha grows)
- Contradicting evidence → widen (sigma grows, alpha drops, log-scaled for reversals)
- Surprise ratio drives update magnitude

### Predictive contradiction detection works (Step 5):
- Code: `D:\CRT\compression_lab\predictive_contradiction.py`
- Two converging splats: cosine goes 0.06 → 0.91 over 20 steps
- WATCH signal at step 6 (cosine 0.33) — 8 steps before conflict territory
- WARN signal at step 14 (cosine 0.75) — system sees collision coming
- Control case (stable beliefs): convergence score stays < 0.06, never triggers
- ~40% advance warning on convergence, zero false positives

### Information geometry works (Step 8):
- Code: `D:\CRT\compression_lab\info_geometry.py`
- Fisher-Rao distance: disagreement between CERTAIN beliefs is 3.16x larger than same disagreement between uncertain beliefs. Cosine sees them as identical (1.00x).
- Same center, different uncertainty: cosine distance = 0.000000, Fisher distance = 44.6. "I know X" vs "I think maybe X" are different beliefs. Fisher sees it.
- Fisher RERANKS retrieval: demotes uncertain neighbors, promotes confident ones
- Per-dimension decomposition correctly identifies which dimensions drive disagreement

### Topology works (Step 6):
- Code: `D:\CRT\compression_lab\belief_topology.py`
- Persistent homology via ripser on splat collections
- Ring of beliefs around avoided topic creates measurable H1 feature (persistence = 0.28)
- Confidence-weighted distance amplifies holes (uncertain beliefs inflate gaps)
- Temporal tracking: Betti number changes = detectable restructuring events
- Caveat: needs real embeddings (not random directions) for clean cluster structure

### What's next:
1. Test on real data (OpenAI export dump, Aether memory DB)
2. Phase 2: low-rank covariance (Sigma = D + UU^T, k=8-16)
3. Phase 3: context-dependent covariance warping
4. Validate "contradiction as importance" hypothesis empirically

## Origin

Nick connected Gaussian splatting (3D VFX) to the memory compression work. The insight: if a memory is uncertain, representing it as a point is dishonest. A point says "the truth is exactly here." A splat says "the truth is somewhere in this region, probably near the center." That's a more accurate representation of what a contested belief actually is. Falls naturally out of the held contradiction theory — if two beliefs coexist, they're overlapping splats, not two competing points.

---
title: "Lab: Polar-Space Memory Retrieval"
status: proposed
created: 2026-04-07
connects_to:
  - theory_memory_splats.md (belief loci)
  - session_2026_04_05_cognimap_results.md (compression)
  - crt_rag.py (current retrieval)
  - crt_core.py (trust scoring)
---

# Polar-Space Memory Retrieval

## Problem

Cosine similarity is CRT's retrieval primitive. It only compares angle (semantic direction) and normalizes away magnitude. Trust-weighted reranking happens *after* retrieval as a separate step. This means:

1. Retrieval is blind to epistemic weight — a 0.95-trust anchor and a 0.3-trust guess score identically if they point in the same direction
2. Contradiction detection can't distinguish real structural conflicts (high trust on both sides) from noise (one side is low-trust)
3. Two disconnected steps (retrieve by similarity, then rerank by trust) when it could be one operation

## Hypothesis

Decomposing memory embeddings into polar coordinates (angle = semantic direction, magnitude = epistemic weight) and operating in that joint space could:

- Make retrieval trust-aware in a single pass
- Sharpen contradiction detection (similar angle + high magnitude on both sides = real conflict)
- Enable better compression (PolarQuant shows angles cluster tightly after preconditioning — 4.2x compression with minimal quality loss)

## Source

PolarQuant: "Quantizing KV Caches with Polar Transformation" (arXiv:2502.02617)

Key finding: after random preconditioning, angles in polar-transformed embeddings have a tightly bounded, analytically computable distribution. Eliminates need for explicit normalization. 4.2x compression.

## Connection to Existing Theory

**Belief Loci** already described this conceptually:
- Center = semantic direction (angle)
- Spread = uncertainty (angular variance)
- Weight = confidence/trust (magnitude)

PolarQuant provides a concrete, efficient algorithm to do the transformation. This lab tests whether it actually improves retrieval quality and contradiction detection in CRT's real memory store.

## Experiment Design

### Phase 1: Baseline Measurement
- Export current memory embeddings from production SQLite
- Measure retrieval quality with cosine similarity (current system)
- Measure contradiction detection precision/recall on known contradictions from the ledger
- Record embedding storage size

### Phase 2: Polar Transformation
- Apply polar decomposition to memory embeddings: (angle_vector, magnitude)
- Encode magnitude as f(trust, confidence, recency) — exact formula TBD
- Apply PolarQuant's random preconditioning step
- Measure angle distribution — does it match the tight clustering PolarQuant predicts?

### Phase 3: Polar Retrieval
- Implement retrieval in polar space where similarity = angular_similarity * magnitude_weight
- Compare retrieval rankings vs. current cosine + rerank approach
- Measure: do high-trust relevant memories surface earlier? Do low-trust noise memories drop?

### Phase 4: Contradiction Sharpening
- In polar space, define contradiction as: angular_similarity > threshold AND magnitude_both > threshold
- Compare precision/recall against current NLI-based contradiction detection
- Key question: does the magnitude gate reduce false contradiction flags?

### Phase 5: Compression
- Quantize angle components using PolarQuant's method
- Measure storage reduction vs. raw embeddings
- Measure retrieval quality degradation (if any) at various quantization levels
- Compare to CogniMap compression results

## Open Questions

- What's the right magnitude formula? Pure trust? Trust * recency decay? Trust * access_count?
- Does random preconditioning work on CRT's embedding model (sentence-transformers) or is it tuned for LLM KV caches?
- Is this a retrieval improvement, a compression improvement, or genuinely both?
- Does this connect to the Fisher information metric from the research modules? (Fisher reranks by certainty — magnitude IS certainty)

## Success Criteria

- Retrieval: measurably better ranking of high-trust relevant memories vs. cosine baseline
- Contradiction: fewer false flags on low-trust memory pairs
- Compression: >2x embedding storage reduction without retrieval quality loss
- If none of these improve: the answer is "cosine + rerank is fine, the gap is elsewhere"

## Not In Scope

- Changing the embedding model itself
- Real-time polar transformation during generation (this is offline/batch analysis first)
- Production integration (lab only)

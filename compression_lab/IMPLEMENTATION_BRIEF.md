# Implementation Brief: Compression Lab → Production

## What This Is
Two sessions of research produced proven findings ready to implement in the main CRT/Aether codebase. This document is the bridge between research (D:\CRT\compression_lab) and production (D:\AI_round2\personal_agent).

---

## What We Proved (With Numbers)

### 1. fold_vector must die
Current production compression (personal_agent/memory_compression.py) averages chunks of dimensions. It's catastrophically lossy:
- fold to 64D: 0.408 cosine, 65% top-10 recall at 256 bytes
- fold to 10D: 0.153 cosine, 29% top-10 recall at 40 bytes

GroundCheck cannot reliably detect contradictions on folded vectors. The signal is destroyed.

### 2. Replacement: Rotation + Lloyd-Max quantization (needs new name — "TurboQuant" is now a Google ICLR 2026 paper)
Random orthogonal rotation + scalar quantization. Data-oblivious, no training needed. Drop-in replacement:
- 3-bit: 0.983 cosine, 93.9% top-10 at 148 bytes
- 4-bit: 0.995 cosine, 94.7% top-10 at 196 bytes

**Implementation:** D:\CRT\compression_lab\turboquant_memory.py — MemoryQuantizer class. Pure numpy. No dependencies beyond scipy.

### 3. Residual VQ solves variable-depth compression
The gap-flip problem (comparing memories at different bit depths distorts similarity) is solved by layered architecture:
- Layer 1: universal comparison surface. Same precision for all memories. Used for retrieval.
- Layer 2+: private refinement. Only stored for contested/volatile memories. Used for reconstruction.
- Volatility governs how many layers are stored.

Results (mixed depth, simulating production):
- Cold (90% of memories): 0.983 cosine, 148 bytes
- Active (8%): 0.998 cosine, 248 bytes
- Volatile (2%): 0.9998 cosine, 348 bytes
- Retrieval: 93.9% top-10 — identical to uniform, no degradation
- Average storage: 160 bytes (vs 1536 uncompressed = 9.6x reduction)

**Implementation:** D:\CRT\compression_lab\residual_vq.py — ResidualVQ class.

### 4. NLI beats cosine for contradiction detection
Cosine similarity alone: 68% accuracy at 384D, 82% at 768D.
NLI cross-encoder on text: 100% accuracy (on synthetic pairs — needs harder test).

Architecture: vectors for RETRIEVAL (fast, cheap), NLI on text for DETECTION (slow, accurate). Compression only needs to preserve retrieval quality, not logical reasoning.

**Model:** cross-encoder/nli-deberta-v3-small

### 5. Anisotropic bit allocation — crossover pattern
Per-dimension variable bits (PCA rotation + variance-based allocation):
- Loses at 2-bit (not enough bits to be smart)
- Ties at 3-bit
- Wins at 4-bit (768D: 0.9996 cosine, 96.6% top-10)

Not needed for initial production. File away for optimization later.

### 6. Online codebook learning — null result
Fitting codebooks to actual data distribution gives marginal cosine improvement (+0.004 at 3-bit) with no retrieval benefit. The Gaussian assumption holds well enough. Skip this.

---

## What We Theorized (Not Yet Implemented)

### Held Contradiction States
Not all contradictions should be resolved. Four states:
1. **Resolvable** — factual conflict, fix it
2. **Held** — both true in different facets, preserve both
3. **Evolving** — belief is shifting, watch it
4. **Contextual** — same belief at different activation levels depending on situation

**Next step:** Build Phase 1 rule-based classifier (NLI + subjectivity detection + temporal gap analysis).

### Belief Loci
Represent memories as belief loci (center + uncertainty + confidence) instead of points. Contradiction = geometric overlap. Volatility = covariance. Enables predictive contradiction detection and context-dependent belief modeling.

**Status:** Pure theory. Saved for future exploration.

---

## Implementation Plan for Main Repo

### Phase 1: Replace fold_vector (1-2 days)

**Files to modify:**
- `personal_agent/memory_compression.py` — swap fold_vector/unfold_vector internals
- Keep the same external interface (compress/decompress functions)
- The volatility governance logic STAYS — it already decides WHEN to compress
- Only the HOW changes: from dimension reduction to bit quantization

**What to copy from compression_lab:**
- `turboquant_memory.py` → adapt into `personal_agent/memory_quantizer.py`
- Strip QJL (not needed for production — marginal benefit)
- Keep: MemoryQuantizer, CompressedMemory, lloyd_max_codebook

**Storage migration:**
- Existing 384D vectors: re-compress with new method
- New memories: compress on ingest
- Tier mapping: Tier 0 → 2-bit (100B), Tier 1 → 3-bit (148B), Tier 2 → full 384D (1536B)
- Consider: all tiers at 3-bit (148B) since even that beats old Tier 1 fold

### Phase 2: Add RVQ for variable depth (2-3 days)

**Files to create:**
- `personal_agent/residual_vq.py` — adapted from compression_lab version

**Integration:**
- Volatility score → layer depth: V < 0.1 → 1 layer, V 0.1-0.6 → 2 layers, V > 0.6 → 3 layers
- All retrieval uses layer 1 inner product only
- Reconstruction (for NLI, display) uses all layers

### Phase 3: Add NLI contradiction detection (3-5 days)

**New module:**
- `personal_agent/contradiction_detector.py`
- Uses cross-encoder/nli-deberta-v3-small
- Pipeline: retrieve top-k by vector similarity → run NLI on text pairs → flag contradictions
- Store contradiction relationships in DB (memory_id_a, memory_id_b, nli_score, disposition)

**Integration with GroundCheck:**
- GroundCheck currently uses cosine similarity for contradiction scoring
- Add NLI as second-pass confirmation on high-similarity pairs
- Cosine is the fast filter, NLI is the accurate judge

### Phase 4: Contradiction disposition classifier (1-2 weeks)

**New module:**
- `personal_agent/contradiction_classifier.py`
- Phase 1: rule-based routing
  - Factual + recent + specific entities → resolvable
  - Subjective + high similarity + emotional content → held
  - Factual + large temporal gap + same topic → evolving
  - Apparent conflict + context-dependent patterns → contextual
- Uses: NLI output + zero-shot subjectivity classifier + temporal metadata + entity detection

**Schema changes:**
- Add `contradiction_state` column: resolvable | held | evolving | contextual
- Add `contradiction_pairs` table: memory_a, memory_b, state, detected_at, resolved_at

### Phase 5: Consider 768D upgrade (optional, 1 week)

- Swap all-MiniLM-L6-v2 (384D) for all-mpnet-base-v2 (768D)
- With 3-bit quantization: 292 bytes (still cheaper than old fold Tier 1 at 256B)
- Contradiction detection improves from 68% → 82% on cosine alone
- Requires re-embedding all existing memories
- Only do this if NLI makes the cosine improvement redundant (it might)

---

## Critical: Rename Required

"TurboQuant" is now a Google ICLR 2026 paper name. Must rename before any public release.

Suggestions for the quantization method:
- MemQuant (memory quantizer)
- BeliefQuant
- Something that reflects governed/adaptive compression

The RVQ + volatility governance system needs its own name too — that's the novel architecture.

---

## Key Research Files (D:\CRT\compression_lab/)
- `turboquant_memory.py` — core quantizer implementation
- `residual_vq.py` — RVQ with variable depth
- `benchmark_dedup.py` — clean benchmark script
- `benchmark_dedup_results.json` — all results
- `online_codebook.py` — codebook experiment (null result, skip)
- `debug_topk.py` — diagnostic that found the duplication bug
- `DEEP_RESEARCH_RESULTS.md` — competitive landscape and strategic assessment
- `SESSION_DEEP_RESEARCH.md` — full research session prompt

## Theory Files (memory/)
- `theory_held_contradiction.md` — four contradiction states
- `theory_memory_splats.md` — Belief locus memory representation
- `project_compression_lab.md` — full results summary

## Whitepaper
- `C:\Users\block\Downloads\whitepaper.md` — original CRT/SSE/CSR/DNNT vision. SSE-L/C/H map directly to RVQ layer depths. Held contradiction extends the whitepaper's philosophy.

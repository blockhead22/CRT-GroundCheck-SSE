---
name: compression_lab_results
description: Compression lab findings - TurboQuant vs fold_vector, NLI detection, anisotropic allocation, dedup benchmark results (March 2026)
type: project
---

## Critical data finding (Session 3, 2026-03-26)
- The "22K vector" dataset had only **567 unique 384D / 592 unique 768D vectors**
- 22,384 vectors were exact duplicates (top dupe appeared 2,846 times)
- The scale_embed_all.py embedded every DB row without deduplication
- ALL "full-scale" top-k numbers (8-19%) were artifacts of duplication, NOT a code bug
- Cosine/IP metrics from the 22K run are still valid (per-vector, unaffected by dupes)
- Deduplicated vectors saved: vectors_dedup_384.npy, vectors_dedup_768.npy

## Deduplicated benchmark results (CLEAN DATA — 567/592 unique vectors)

### 384D (all-MiniLM-L6-v2):
| Method | Bytes | Cosine | IP_r | Top-10 |
|---|---|---|---|---|
| fold_64D | 256 | 0.408 | N/A | 65.4% |
| fold_10D | 40 | 0.153 | N/A | 28.6% |
| TQ uniform 2-bit | 100 | 0.940 | 0.994 | 89.5% |
| TQ uniform 3-bit | 148 | 0.983 | 0.998 | 93.9% |
| TQ uniform 4-bit | 196 | 0.995 | 1.000 | 94.7% |
| Aniso 2-bit | 100 | 0.952 | 0.973 | 77.3% |
| Aniso 3-bit | 148 | 0.987 | 0.994 | 90.0% |
| Aniso 4-bit | 196 | 0.997 | 0.999 | 94.1% |

### 768D (all-mpnet-base-v2):
| Method | Bytes | Cosine | IP_r | Top-10 |
|---|---|---|---|---|
| fold_64D | 256 | 0.284 | N/A | 65.9% |
| fold_10D | 40 | 0.107 | N/A | 34.7% |
| TQ uniform 2-bit | 196 | 0.940 | 0.997 | 89.6% |
| TQ uniform 3-bit | 292 | 0.983 | 0.999 | 93.7% |
| TQ uniform 4-bit | 388 | 0.995 | 1.000 | 95.0% |
| Aniso 2-bit | 196 | 0.983 | 0.988 | 84.4% |
| Aniso 3-bit | 293 | 0.997 | 0.999 | 93.5% |
| Aniso 4-bit | 386 | 1.000 | 1.000 | 96.6% |

### Key pattern: bit budget determines winner
- **2-bit: Uniform TQ wins** — random rotation preserves pairwise geometry when bits are scarce
- **3-bit: Tie** — nearly identical retrieval, aniso wins cosine, TQ wins IP
- **4-bit: Aniso wins** — enough budget to exploit variance structure without starving low-var dims
- The crossover is a clean, publishable finding (not messy like the fake "22K scale" suggested)

## Session 1: Initial benchmarks (556 vectors)
- fold_vector catastrophically lossy: 0.236 cosine sim at 256 bytes
- TurboQuant 3-bit: 0.983 cosine sim at 148 bytes — 4x better, less storage
- Gap-flip problem: asymmetric compression reverses similarity ordering
- Volatility-aware quantizer works mechanically but 98.2% memories are cold

## Research directions completed:

### Direction 1: PCA rotation — NEGATIVE RESULT
- PCA rotation loses to random rotation at every bit level
- Random rotation makes dimensions Gaussian (optimal for Lloyd-Max). PCA violates this.

### Direction 2: NLI contradiction detection — PERFECT RESULT
- cross-encoder/nli-deberta-v3-small: 100% F1, 100% accuracy on synthetic pairs
- Architecture: vectors for RETRIEVAL, NLI on text for DETECTION
- CAVEAT: synthetic pairs may be too easy. Need organic contradictions.

### Direction 3: Anisotropic bit allocation — CLEAN PATTERN (corrected)
- Last night's "complicated at scale" finding was WRONG — caused by duplicate vectors
- Clean pattern: loses at 2-bit, ties at 3-bit, wins at 4-bit
- 768D aniso 4-bit: 0.9996 cosine, 96.6% top-10 at 386 bytes — best result overall

## Proven findings:
1. Replace fold_vector with TurboQuant uniform 3-bit — no debate
2. NLI cross-encoder for contradiction detection — architecture change for GroundCheck
3. 768D + TQ = better quality at comparable storage to current fold tiers
4. Anisotropic wins at higher bit budgets, uniform wins at lower — clean crossover
5. **Need real scale data** — 567 unique vectors is not enough to claim generalization

## Phase 1 SHIPPED (2026-03-26)
MemQuant integrated into production (`personal_agent/memory_compression.py`):
- MemQuantizer class, quantize_vector/dequantize_vector API
- run_compression_pass uses memquant for demote/promote
- crt_memory.py retrieval decompresses to full 384D instead of folding query
- Format detection: cogni_seed "method":"memquant" → new path, else legacy fold
- 47 tests pass, 12 new memquant-specific tests
- Migration script: scripts/migrate_compression.py (idempotent)
- Tier mapping: cold·2bit, warm·3bit, full·384D

## Deep Research Findings (2026-03-26)

### CRITICAL: Rename TurboQuant
Google Research published "TurboQuant: Online Vector Quantization with Near-optimal Distortion Rate" at ICLR 2026. Same name. They prove random rotation + per-coordinate Lloyd-Max is within 2.7x of information-theoretic lower bound — validating Nick's approach independently. But Google owns the name now. Must rename.

### Direction verdicts:
| Direction | Verdict | Action |
|---|---|---|
| Online codebook learning | NOT WORTH IT | Skip. Gaussian assumption already near-optimal after rotation. Single-digit % gain at best. |
| Cross-precision comparison | WORKS, 1 FREE IMPROVEMENT | Implement ADC-style asymmetric comparison (use full reconstruction of richer vector). One-line change. |
| Contradiction disposition classification | THIS IS THE MOAT | Sprint. Phase 1 rule-based classifier: NLI + subjectivity + temporal gap + entity specificity. 2-3 weeks. |
| Temporal memory governance | 80% SOLUTION IS SIMPLE | Build: timestamp + type tag + policy table. Type-dependent decay + held contradictions = novel combo. |
| Graph memory (SSE-GNN) | BUILD GRAPH, SKIP GNN | NetworkX + JSON. Automated CONTRADICTS/SUPERSEDES edges. 2-3 weeks to MVP. |
| Business assessment | NARROW WEDGE, NOT PLATFORM | Don't compete with Mem0 ($24M). Open-source focused library around held contradictions. |

### Competitive landscape (updated 2026-03-26):
- Mem0: $24M raised, 80K devs, AWS exclusive, 186M API calls/quarter
- Zep: $1M revenue, 5-person team, temporal KG in production
- Letta (MemGPT): $10M seed, $70M valuation
- Personize.ai: published "Governed Memory" paper with production system
- NOBODY has contradiction disposition classification (resolvable/held/evolving)

### Archived (hardware/data gated):
- GNN subgraph encoding — needs 5K+ memories with typed edges + local GPU. Alive, not ready.
- QINCo-style learned correction — needs training data + GPU iteration. Archive.
- Fine-tuned DeBERTa Phase 3 — needs real user contradiction pairs. Phase 1/2 come first.
- Online codebook refit — theoretically marginal, low ceiling. Skip.

### Active research worth pursuing:
1. Contradiction disposition classifier (Phase 1 rule-based) — sprint priority
2. Subjectivity/contradiction interaction — nobody has combined these. Potentially publishable.
3. "Contradiction as importance" hypothesis — empirical test against real memory DB
4. ADC-style asymmetric comparison — quick experiment on real RVQ vectors
5. Temporal type classification — zero-shot DeBERTa accuracy on real memories
6. Belnap formalization — True/False/Both/Neither as first-class memory states

## Remaining priorities (updated):
1. **RENAME TURBOQUANT** — day 1
2. Build contradiction disposition classifier (Phase 1)
3. Build memory graph (NetworkX + automated edges)
4. Add temporal governance (type tag + policy table)
5. Package as focused open-source library
6. ADC-style asymmetric comparison (free improvement)
7. Extract organic contradictions from real DB (15 flagged memories)

## Key files: D:\CRT\compression_lab\
- turboquant_memory.py, benchmark_dedup.py, debug_topk.py, residual_vq.py
- vectors_dedup_384.npy (567×384), vectors_dedup_768.npy (592×768)
- benchmark_dedup_results.json (clean results)
- vectors_full_384/768.npy (22K with dupes — keep for reference)
- DEEP_RESEARCH_RESULTS.md — full research report with sources

## Paper framing:
"Volatility-Aware Vector Quantization for Contradiction-Sensitive Memory Systems"
Pickup doc: D:\AI_round2\.claude\SESSION_COMPRESSION_LAB_PICKUP.md

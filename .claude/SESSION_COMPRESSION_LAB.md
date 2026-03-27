# Session Prompt: Volatility-Aware Vector Quantization Research Lab

## What This Is

You are running a research experiment to test a novel hypothesis: **adaptive bit-depth quantization governed by memory governance signals (trust, contradiction history, semantic volatility) preserves contradiction detection accuracy at lower storage costs than uniform quantization.**

This combines two domains that have never been connected:
1. Vector quantization (TurboQuant, PolarQuant, NVQ)
2. Memory governance (GroundCheck — contradiction detection, trust decay, belief lifecycle)

Nobody has published this. The closest work is KVQuant/KVmix (mixed precision for KV caches based on attention sensitivity) and NVQ (per-vector non-uniform quantization for retrieval). Neither uses epistemological signals (trust, contradiction density, drift) to govern bit allocation.

**This is a research session. Build experiments, run benchmarks, document results. Do NOT modify production code in `personal_agent/` unless explicitly told to.**

## Working Directory

- Experiments: `D:\AI_round2\compression_lab\`
- Production code (READ ONLY): `D:\AI_round2\personal_agent\`
- Original CRT (READ ONLY reference): `D:\CRT\`
- GroundCheck library (READ ONLY reference): `D:\groundcheck\`

## Background: The Three Compression Approaches

### Approach A: Current Tier System (fold_vector)
File: `personal_agent/memory_compression.py`

Reduces dimensions, keeps full 32-bit precision per dimension:
```
Tier 2 (full):  384D × 32-bit = 1,536 bytes — high-trust, volatile, contested
Tier 1 (warm):   64D × 32-bit =   256 bytes — intermediate
Tier 0 (cold):   10D × 32-bit =    40 bytes — settled, low-trust, rarely accessed
```

fold_vector() splits 384D into N chunks, averages each chunk. Stores CogniSeed (per-chunk variance, dominant indices) for approximate reconstruction.

**Problem:** Destroying dimensions destroys information topology. Cosine similarity between 10D vectors is fundamentally less meaningful than between 384D vectors.

### Approach B: TurboQuant (uniform bit quantization)
Reference: https://github.com/tonbistudio/turboquant-pytorch

Keeps ALL dimensions, reduces bits per dimension:
```
4-bit + QJL: 384D × 5 bits = 240 bytes — near-lossless inner products
3-bit + QJL: 384D × 4 bits = 192 bytes — 0.9945 cosine similarity
2-bit + QJL: 384D × 3 bits = 144 bytes — aggressive but functional
```

Two stages:
1. Random orthogonal rotation → Lloyd-Max scalar quantization (N bits)
2. QJL residual correction: project error through Gaussian matrix, store only sign bits (1 bit)

**Key insight:** Optimizes for inner product accuracy, not vector reconstruction. This is what memory retrieval depends on.

**Problem:** Uniform compression — every vector gets the same bit depth regardless of importance.

### Approach C: Volatility-Aware Quantization (THE HYPOTHESIS)

Adaptive bit-depth governed by the existing volatility formula:
```python
V(t) = 0.4 * D(t) + 0.35 * C(t) + 0.25 * F(t)
  D(t) = drift (1 - cosine_sim between original and any reconstructed form)
  C(t) = contradiction_density (contradiction_count / access_count)
  F(t) = fidelity_loss (MSE of reconstruction × 10, capped at 1.0)
```

Bit allocation rules:
```
V(t) > 0.6  (volatile/contested)  → 8-bit TurboQuant  (384 bytes) — max precision
V(t) 0.3–0.6 (active, referenced) → 4-bit TurboQuant  (240 bytes) — high fidelity
V(t) 0.1–0.3 (stable, settling)   → 3-bit TurboQuant  (192 bytes) — good fidelity
V(t) < 0.1  (cold, settled)       → 2-bit TurboQuant  (144 bytes) — storage efficient
```

ALL tiers keep 384 dimensions. The semantic topology is never destroyed. Contested memories get more bits because GroundCheck needs precision to detect contradictions against them. Settled memories get fewer bits because they've already been verified.

**The claim:** This outperforms both uniform TurboQuant and the current tier system for contradiction detection accuracy, while achieving comparable or better storage efficiency.

## The Experiment

### Step 1: Load Real Data and Establish Ground Truth — PAUSE after

1. Connect to `personal_agent/crt_memory.db`
2. Load 1000 random non-deprecated memory vectors:
   ```sql
   SELECT memory_id, vector_json, trust, confidence, compression_tier,
          contradiction_count, access_count
   FROM memories WHERE deprecated=0 ORDER BY RANDOM() LIMIT 1000
   ```
3. Parse vector_json into numpy arrays (384D float32)
4. Compute ground truth:
   - Full pairwise cosine similarity matrix (1000×1000)
   - For 100 random queries: true top-5 and top-10 nearest neighbors
   - Distribution stats: norms, trust scores, contradiction counts, access counts
5. Also compute the volatility V(t) for each memory using the formula above
   - You'll need the original vector AND current state to compute drift
   - For memories already at tier 2 (full), D(t) = 0 (no compression drift yet)
   - Plot the V(t) distribution — how many memories fall in each volatility band?
6. Save everything to `compression_lab/step1_ground_truth.json`

Print: number of memories loaded, V(t) distribution histogram (text-based), basic stats.

### Step 2: Benchmark Current Tier System — PAUSE after

For each tier {0: 10D, 1: 64D, 2: 384D}:
1. Import fold_vector, unfold_vector from `personal_agent.memory_compression`
2. Compress all 1000 vectors to each tier
3. Reconstruct via unfold_vector
4. Measure:
   - **Per-vector cosine similarity** (original vs reconstructed): mean, std, min, p5, p95
   - **Inner product correlation**: for 500 random (query, key) pairs, compare dot(q, k_original) vs dot(q_folded, k_folded). Report Pearson r and Spearman rho.
   - **Top-k retrieval accuracy**: for 100 queries, what % of true top-5 and top-10 are preserved after folding both query and keys?
   - **Storage per vector**: bytes
5. Save to `compression_lab/step2_tier_benchmark.json`

Print a comparison table.

### Step 3: Implement TurboQuant for Memory Vectors — PAUSE after

Build `compression_lab/turboquant_memory.py`:

**Option A (preferred):** If turboquant-pytorch is installable, wrap it:
```bash
pip install turboquant-pytorch  # or clone from GitHub
```

**Option B (fallback):** Implement Stage 1 from scratch in numpy:
```python
class MemoryQuantizer:
    def __init__(self, dim=384, bits=3, use_qjl=True, seed=42):
        # Generate random orthogonal rotation matrix (QR decomposition)
        rng = np.random.RandomState(seed)
        gaussian = rng.randn(dim, dim).astype(np.float32)
        self.rotation, _ = np.linalg.qr(gaussian)

        # Precompute Lloyd-Max codebook for N(0, 1/dim) distribution
        self.codebook = self._lloyd_max_codebook(bits, dim)

        # QJL projection matrix (if enabled)
        if use_qjl:
            self.qjl_matrix = rng.randn(dim, dim).astype(np.float32) / np.sqrt(dim)

    def compress(self, vector):
        """Returns CompressedMemory with indices + optional QJL signs."""

    def inner_product(self, query, compressed):
        """Corrected inner product: <q, k_recon> + QJL correction term."""

    def batch_search(self, query, compressed_db, k=5):
        """Top-k retrieval using corrected inner products."""
```

The Lloyd-Max codebook for a Gaussian distribution at various bit depths:
- 2-bit: 4 centroids
- 3-bit: 8 centroids
- 4-bit: 16 centroids
- 8-bit: 256 centroids

Use scipy.optimize or a simple iterative Lloyd algorithm to find optimal centroids minimizing MSE for N(0, 1/d).

Test: compress and decompress 10 vectors, print cosine similarity. Verify it's working before proceeding.

### Step 4: Benchmark Uniform TurboQuant — PAUSE after

For each config {2-bit, 3-bit, 4-bit, 8-bit} × {with QJL, without QJL}:
1. Compress all 1000 vectors
2. Measure same metrics as Step 2:
   - Per-vector cosine similarity (original vs reconstructed)
   - Inner product correlation (500 pairs)
   - Top-k retrieval accuracy (100 queries, k=5 and k=10)
   - Storage per vector
3. Save to `compression_lab/step4_turboquant_uniform.json`

Print comparison table alongside Step 2 results.

### Step 5: Implement Volatility-Aware Quantization — PAUSE after

Build `compression_lab/volatility_quantizer.py`:

```python
class VolatilityAwareQuantizer:
    def __init__(self, dim=384, seed=42):
        # One MemoryQuantizer per bit-depth tier
        self.quantizers = {
            8: MemoryQuantizer(dim=dim, bits=8, use_qjl=True, seed=seed),
            4: MemoryQuantizer(dim=dim, bits=4, use_qjl=True, seed=seed),
            3: MemoryQuantizer(dim=dim, bits=3, use_qjl=True, seed=seed),
            2: MemoryQuantizer(dim=dim, bits=2, use_qjl=True, seed=seed),
        }
        # Volatility thresholds → bit depth
        self.allocation_rules = [
            (0.6, 8),   # V(t) > 0.6 → 8-bit (volatile, contested)
            (0.3, 4),   # V(t) > 0.3 → 4-bit (active)
            (0.1, 3),   # V(t) > 0.1 → 3-bit (stable)
            (0.0, 2),   # V(t) ≤ 0.1 → 2-bit (cold, settled)
        ]

    def select_bits(self, volatility: float) -> int:
        for threshold, bits in self.allocation_rules:
            if volatility >= threshold:
                return bits
        return 2

    def compress(self, vector, volatility):
        bits = self.select_bits(volatility)
        return self.quantizers[bits].compress(vector), bits

    def inner_product(self, query, compressed, bits):
        return self.quantizers[bits].inner_product(query, compressed)
```

Compress all 1000 vectors using their REAL V(t) values from Step 1.

Print: distribution of bit allocations (how many got 8/4/3/2), average bits per vector, total storage.

### Step 6: Benchmark Volatility-Aware vs Uniform — PAUSE after

Run the same benchmark suite on the volatility-aware compressed set:
1. Inner product correlation (500 pairs)
2. Top-k retrieval accuracy (100 queries)
3. Storage per vector (now variable — report mean, median, total)

**Critical comparison — the headline result:**

```
Method                  | Avg bytes | Top-5 Recall | Top-10 Recall | IP Correlation
------------------------|-----------|--------------|---------------|---------------
Tier 2 (384D full)      | 1536      | 100%         | 100%          | 1.000
Tier 1 (64D fold)       | 256       | ???          | ???           | ???
Tier 0 (10D fold)       | 40        | ???          | ???           | ???
TQ 3-bit uniform + QJL  | 192       | ???          | ???           | ???
TQ 4-bit uniform + QJL  | 240       | ???          | ???           | ???
Volatility-aware TQ     | ???       | ???          | ???           | ???
```

Also compute a **per-volatility-band breakdown**:
- For memories with V(t) > 0.6: how does volatility-aware compare to uniform 3-bit?
- For memories with V(t) < 0.1: how does 2-bit compare to uniform 3-bit?

The hypothesis predicts: volatility-aware matches or beats uniform on HIGH-V memories (because it gives them more bits) while saving storage on LOW-V memories (because it gives them fewer bits). Overall accuracy should be >= uniform at lower average storage.

### Step 7: GroundCheck Contradiction Detection Impact — PAUSE after

This is the most important step. It tests whether compression affects GroundCheck's ability to do its job.

1. **Synthesize 100 contradiction test pairs** (or load from ledger if available):
   ```python
   true_contradictions = [
       ("I work at Google", "I work at Microsoft"),
       ("My favorite color is blue", "My favorite color is red"),
       ("I'm allergic to peanuts", "I have no food allergies"),
       # ... 47 more
   ]
   true_non_contradictions = [
       ("I like sushi", "I enjoy Japanese food"),
       ("I work in tech", "I'm a software engineer"),
       ("I live in Portland", "I'm in the Pacific Northwest"),
       # ... 47 more
   ]
   ```

2. Encode all statements using the same embedding model (all-MiniLM-L6-v2, 384D)
   - You can load it: `from sentence_transformers import SentenceTransformer; model = SentenceTransformer('all-MiniLM-L6-v2')`

3. For each compression method, compute pairwise similarity between each pair

4. Using GroundCheck's detection threshold range (cosine similarity 0.35-0.50 flags potential contradictions):
   - **True positive rate**: what % of real contradictions are caught?
   - **False positive rate**: what % of non-contradictions are incorrectly flagged?
   - **Optimal threshold**: what threshold maximizes F1 under each compression method?
   - **Threshold shift**: does the optimal threshold change under compression?

5. **Per-volatility analysis**: Assign synthetic V(t) to test pairs:
   - Contradictions get V(t) = 0.7 (they're contested by definition)
   - Non-contradictions get V(t) = 0.05 (stable, consistent)
   - Under volatility-aware quantization, contradictions get 8-bit, non-contradictions get 2-bit
   - Does this preserve detection accuracy better than uniform 3-bit for both?

6. Save to `compression_lab/step7_groundcheck_impact.json`

**This is the key finding.** If volatility-aware quantization maintains contradiction detection accuracy while uniform quantization degrades it, that's the paper.

### Step 8: Write-Up and Visualization — PAUSE after

Create `compression_lab/FINDINGS.md`:

1. **Abstract** (3 sentences): what was tested, what was found
2. **Method**: brief description of each approach
3. **Results tables**: all benchmark numbers
4. **Key finding**: does volatility-aware beat uniform? By how much? At what cost?
5. **GroundCheck impact**: does compression affect contradiction detection?
6. **Storage analysis**: total DB size under each method for 22,624 memories
7. **Limitations**: sample size, synthetic contradictions, single embedding model
8. **Next steps**: what would make this publishable?

Generate charts (save as PNG to compression_lab/):
- `storage_vs_accuracy.png`: scatter plot, x=bytes/vector, y=top-5 recall, one point per method
- `volatility_distribution.png`: histogram of V(t) across the 1000 memories
- `contradiction_detection.png`: ROC curves for each compression method
- `bit_allocation.png`: pie/bar chart showing how volatility-aware distributes bits

## Technical Notes

- **Embedding model**: all-MiniLM-L6-v2, 384 dimensions, L2-normalized
- **Memory DB**: `personal_agent/crt_memory.db`, table `memories`, column `vector_json` (JSON array of 384 floats)
- **numpy is available**, torch may or may not be — check `import torch` and fall back to numpy
- **matplotlib is available** for charts
- **scipy is available** for optimization (Lloyd-Max codebook)
- **sentence-transformers is available** for encoding test sentences
- **PAUSE between each step** — print results summary and say "Step N complete. Ready for Step N+1?"
- If any computation takes >60 seconds, print progress dots or a progress bar
- All intermediate results should be saved as JSON so steps can be re-run independently

## The Research Question

> Does adaptive bit-depth quantization, where bit allocation is governed by epistemological signals (trust score, contradiction density, semantic drift), preserve contradiction detection accuracy at lower average storage cost than uniform quantization?

If yes: this is a publishable finding connecting two previously separate domains (vector quantization and memory governance).

If no: we learn the specific conditions under which it fails, which is still valuable and shapes the next experiment.

Either way, we get real numbers instead of intuition. That's the point.

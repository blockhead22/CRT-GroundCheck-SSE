# Adaptive Semantic Compression

CRT implements a three-tier adaptive compression system for memory vectors. Stable, low-trust memories compress to smaller vectors to save space and compute. Volatile or high-trust memories stay at full fidelity. The system is fully reversible via CogniSeed reconstruction guides.

Reference: `personal_agent/memory_compression.py`

## The V(t) Volatility Formula

Volatility determines whether a memory should be compressed or promoted. It combines three signals:

```
V(t) = alpha * D(t) + beta * C(t) + gamma * F(t)
```

| Component | Symbol | Weight | What It Measures |
|-----------|--------|--------|-----------------|
| Drift | D(t) | alpha = 0.4 | 1 - cosine_similarity(original, reconstructed). How much information was lost in compression. |
| Contradiction density | C(t) | beta = 0.35 | contradiction_count / access_count. How often this memory has been contradicted relative to how often it's used. |
| Fidelity loss | F(t) | gamma = 0.25 | min(1.0, MSE(original, reconstructed) * 10). Mean squared error between original and reconstructed vectors. |

V(t) is clamped to [0, 1].

## The Throttle Function

```
H(t) = H0 * e^(-s * V(t))
```

Where H0 = 1.0 and s = 3.0.

High volatility produces low H (approaching 0), which signals "stop compressing this memory — it's losing too much information or being contested."

## The Three Tiers

| Tier | Dimensions | Name | Description |
|------|-----------|------|-------------|
| 0 | 10D | cold | Routine, stable, low-trust facts. Minimal storage cost. |
| 1 | 64D | warm | Intermediate fidelity. Good balance of storage and recall. |
| 2 | 384D | full | Identity, high-trust, volatile memories. No compression applied. |

### Tier Transitions

**Promotion** (lower tier to higher tier) happens when:
- Volatility >= 0.6 (the `PROMOTION_THRESHOLD`), OR
- Trust >= 0.9 AND volatility >= 0.3 (high-trust memories get promoted more easily)
- Maximum tier is 2 (full fidelity)

**Demotion** (higher tier to lower tier) happens when:
- Volatility < 0.1 (the `DEMOTION_THRESHOLD`)
- AND the memory has been stable for >= 10 consecutive cycles (`DEMOTION_STABLE_CYCLES`)
- AND trust is below 0.3 (`DEMOTION_MAX_TRUST`)
- AND the target tier is above the memory's minimum tier

### Protection Rules

Some memories are never compressed below tier 2:
- `kind = 'identity_constant'` — core identity facts
- `authority = 'locked'` — manually locked memories

High-trust user memories (trust >= 0.8) have a minimum tier of 1 (warm).

## CogniSeed Reconstruction

When a vector is folded from a higher dimension to a lower one, a `CogniSeed` is stored alongside the compressed vector. It contains:

```python
CogniSeed:
    original_dim: int       # e.g., 384
    target_dim: int         # e.g., 64
    mean_contribution: array  # chunked averages (the compressed vector itself)
    variance_contribution: array  # variance within each chunk
    dominant_indices: array  # most significant dimensions
    polarity_bias: float    # mean of original vector
    fold_timestamp: float   # when compression happened
```

### Folding Algorithm

`fold_vector()` divides the original vector into `target_dim` chunks and averages each chunk:

```python
chunk_size = original_dim // target_dim
for i in range(target_dim):
    compressed[i] = mean(original[start:end])
    variance[i] = var(original[start:end])
```

### Unfolding Algorithm

`unfold_vector()` reconstructs an approximation using the compressed values plus variance spread:

```python
for i in range(source_dim):
    if variance[i] > 0:
        spread = linspace(-1, 1, chunk_len) * sqrt(variance[i])
        result[start:end] = compressed[i] + spread
    else:
        result[start:end] = compressed[i]
```

This is deterministic — same inputs always produce the same output. No randomness.

## When Compression Runs

`run_compression_pass()` is called after trust decay in the heartbeat cycle. It:

1. Loads all non-deprecated memories older than the grace cutoff
2. Skips protected memories (identity_constant, locked authority)
3. Computes volatility for each memory
4. Promotes memories with high volatility
5. Demotes memories with low volatility and sufficient stable cycles
6. Tracks stability cycles for memories in the low-volatility zone

The pass emits distinctive diamond-prefixed log lines (`FOLD`, `UNFOLD`, `STABLE`) for monitoring.

## How Retrieval Weights by Tier

During memory retrieval in `CRTMemorySystem.retrieve_memories()`, compressed memories are handled specially:

1. The query vector is folded down to the memory's tier dimensionality using `fold_vector()`
2. Cosine similarity is computed between the folded query and the compressed memory vector
3. A tier weight penalty is applied:

```python
TIER_WEIGHT = {0: 0.85, 1: 0.95, 2: 1.0}
```

This means cold (10D) memories get a 15% score penalty, warm (64D) memories get 5%, and full (384D) memories get no penalty.

The final retrieval score:
```
R = similarity * recency * belief_weight * tier_weight
```

This ensures compressed memories can still be found but are naturally disadvantaged compared to full-fidelity memories, which is the desired behavior — if a memory was important enough to stay uncompressed, it should rank higher.

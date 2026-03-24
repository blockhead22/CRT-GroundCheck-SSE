# Belief Synthesis & Volatility Context

**Version:** v2.5 (March 24, 2026)
**Sprints:** 9 (Synthesis Responses) & 10 (Volatility-Gated Context Window)
**Files:** `personal_agent/belief_synthesis.py`, `personal_agent/volatility_context.py`

---

## Overview

Two complementary systems that transform how Aether answers worldview questions and manages context:

- **Belief Synthesis** — answers questions like "what do I care about?" from compressed belief trajectories, not individual fact recall. Uses trust-weighted clustering and temporal trajectory analysis.
- **Volatility Context** — allocates context budget dynamically. Volatile (uncertain, recently changed) memories get full text; stable high-trust facts compress to `slot=value` pairs. Saves context space while preserving nuance where it matters.

---

## Belief Synthesis

### Three Synthesis Modes

| Mode | Trigger Patterns | What It Does |
|------|-----------------|--------------|
| **Thematic** | "what do I care about?", "describe me", "who am I to you?" | Clusters memories by theme, identifies dominant interests/values |
| **Trajectory** | "how have I changed?", "what did I used to think?", "timeline of my beliefs" | Tracks value changes over time per slot, detects drift and oscillation |
| **Contradiction-aware** | "where do I contradict myself?", "what are my contradictions?" | Surfaces unresolved tensions between beliefs |

### Query Classification

`classify_synthesis_query(text)` matches against 25+ regex patterns across three categories, plus a legacy fallback for category words (interests, hobbies, technologies) + action words (what, tell, list).

### Clustering Pipeline

1. **Embed** — uses existing 384D memory vectors
2. **Agglomerative clustering** — scipy `linkage(method="average", metric="cosine")` with distance threshold 0.65
3. **Trust-weighted centroids** — `np.average` with trust scores as weights
4. **Cluster confidence** — average pairwise cosine similarity within cluster
5. **Label** — dominant fact slots or top 3 keywords (stopwords filtered)
6. **Sort** — by total evidence weight (sum of trust scores)

### Trajectory Analysis

`build_belief_trajectory(memories, slot)` for slots with 2+ distinct values:

1. Collects all `(timestamp, value, trust, source)` tuples for a slot
2. Sorts chronologically, deduplicates consecutive identical values
3. Computes **drift magnitude** — sum of pairwise cosine distances between consecutive value embeddings
4. Detects **oscillation** — when a value appears twice (user changed their mind and came back)

### Tension Detection

Two sources of unresolved tensions:
- Open contradictions from the ledger (claim_a vs claim_b)
- Intra-cluster divergence (conflicting beliefs within the same theme)

Capped at 10 tensions, deduplicated.

### Representativeness Score

```
representativeness = coverage * (1 - 0.3 * avg_contradiction_density)
```

Where `coverage = clustered_memory_count / total_memory_count`. A high contradiction density within clusters reduces representativeness — the system acknowledges its summary may not fully capture the user's beliefs.

### LLM Generation

Each mode builds a focused prompt:
- **Thematic**: up to 8 clusters with 4 sample texts each, notes contradictions within themes
- **Trajectory**: up to 6 trajectories with dated snapshots
- **Contradiction-aware**: up to 8 tensions + conflicted clusters, frames contradictions as complexity not flaws

Generated via `cloud_service.generate_response()`. Falls back to deterministic bullet-point summaries if LLM is unavailable.

### Data Structures

**`SynthesisResult`:**
- `synthesis_type` — "thematic", "trajectory", or "contradiction_aware"
- `summary_text` — LLM-generated prose
- `clusters` — list of BeliefCluster
- `trajectories` — list of BeliefTrajectory
- `unresolved_tensions` — list of (claim_a, claim_b) pairs
- `representativeness` — 0.0 to 1.0
- `evidence_count` — total memories analyzed

---

## Volatility-Gated Context Window

### Core Idea

Not all memories deserve equal context budget. A recently-changed job title (volatile, uncertain) needs its full text preserved for nuance. A stable favorite color (high trust, low volatility) can compress to `favorite_color=blue`.

### Volatility Computation

```
V(t) = 0.35 * contradiction_signal + 0.40 * (1 - trust) + 0.25 * recency_factor
```

| Factor | Weight | Description |
|--------|--------|-------------|
| Contradiction signal | 0.35 | `min(1.0, contra_count/access_count + 0.5 if open_contradiction)` |
| Inverse trust | 0.40 | Lower trust = higher volatility |
| Recency | 0.25 | 1.0 if changed within 7 days, else 0.0 |

If the memory has CRT compression metadata (`compressed_vector`, `cogni_seed`), delegates to the full `memory_compression.compute_volatility()` function instead.

### Compression Levels

| Level | When Applied | Output |
|-------|-------------|--------|
| **full** | V >= 0.6, or trust < 0.4 + V > 0.3, or top 30% priority | Raw text |
| **summary** | Middle 30-70% priority | First sentence + `[slot=value]` pairs |
| **slot_only** | Trust >= 0.85 + V < 0.15, or bottom 30% priority | Just `slot=value; slot=value` |

### Budget Allocation

`allocate_context_budget(query, retrieved, total_budget=6000)`:

1. Compute volatility + priority for each memory: `priority = relevance_score * (1 + 1.5 * V(t))`
2. Sort by priority descending
3. Assign compression tiers based on thresholds
4. If over budget: iteratively demote lowest-priority allocations (`full` → `summary` → `slot_only`) until within budget
5. Detect proactive alerts for recently changed beliefs

### Proactive Volatility Alerts

When a belief was recently resolved (within 7 days), the system can inject alerts like:

> "You recently changed your mind about [job]: was 'engineer' → now 'architect'"

Max 2 alerts, 300 chars budget. Only fires for contradictions resolved via the ledger.

### Volatility Re-ranking

`rerank_by_volatility(retrieved, ledger, memory_system, boost_factor=0.5)`:

```
adjusted_score = original_score * (1 + 0.5 * V(t))
```

Volatile memories float higher in retrieval results — they're more likely to be relevant when the user is asking about something uncertain.

### Key Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `DEFAULT_MEMORY_BUDGET` | 6000 chars | Total context budget |
| `VOLATILE_THRESHOLD` | 0.4 | Above = volatile |
| `HIGH_VOLATILE_THRESHOLD` | 0.6 | Force full text |
| `LOW_VOLATILE_THRESHOLD` | 0.15 | Safe to compress aggressively |
| `HIGH_TRUST_THRESHOLD` | 0.85 | Stable if also low-volatile |
| `VOLATILITY_BOOST` | 1.5 | Priority multiplier |
| `RECENT_CHANGE_DAYS` | 7 | Window for recency factor |
| `MAX_PROACTIVE_ALERTS` | 2 | Alert cap |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/synthesis` | Run belief synthesis for a query |
| GET | `/api/belief-trajectory/{slot}` | Get temporal trajectory for a specific slot |
| GET | `/api/context-budget` | View current context budget allocation |
| GET | `/api/memory/{id}/volatility` | Get volatility profile for a memory |
| GET | `/api/volatile-memories` | List memories ranked by volatility |

---

## Design Principles

- **Structural analysis is deterministic** — clustering, trajectory building, tension detection, and representativeness scoring use no LLM. Only the final prose generation uses an LLM.
- **No new database tables** — works entirely with existing memory and ledger data.
- **Graceful degradation** — deterministic bullet-point summaries when LLM is unavailable.
- **CRT-native** — trust scores weight clustering, volatility drives compression, contradictions are surfaced not hidden.

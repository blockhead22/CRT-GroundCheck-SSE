# CRT Integration - Complete

## What Was Built

**CRT (Cognitive-Reflective Transformer) principles** integrated into the RAG system.

### Philosophy

- **Memory First**: Coherence over time > single-query accuracy
- **Honesty Over Performance**: Truth > sounding good
- **"The mouth must never outweigh the self"**: Speech can't override beliefs without evidence

## Core Components

### 1. CRT Mathematics (`crt_core.py`)

**Mathematical framework implementing:**

```python
# Trust-weighted retrieval
R_i = s_i · ρ_i · w_i
where:
  s_i = similarity(query, memory)
  ρ_i = exp(-(t_now - t_i) / λ)     # Recency
  w_i = α·τ + (1-α)·c               # Belief weight
```

```python
# Trust evolution (alignment)
if drift ≤ θ_align:
    τ_new = clip(τ + η_pos·(1 - drift), 0, 1)

# Trust evolution (contradiction)
if drift > θ_contra:
    τ_new = clip(τ · (1 - η_neg·drift), 0, 1)
```

```python
# SSE mode selection
S = w1·emotion + w2·novelty + w3·user_mark + w4·contradiction + w5·future
if S ≥ T_L  → SSE-L (lossless)
if S ≤ T_C  → SSE-C (cogni/sketch)
else        → SSE-H (hybrid)
```

```python
# Reconstruction gates (Holden constraints)
Accept output if:
    A_intent ≥ θ_intent  AND  A_mem ≥ θ_mem
Otherwise → fallback speech (low trust)
```

### 2. Trust-Weighted Memory (`crt_memory.py`)

**Features:**
- Memory items with **trust** (evolves) and **confidence** (fixed)
- Source tracking: USER, SYSTEM, FALLBACK, REFLECTION
- SSE mode tracking: LOSSLESS, COGNI, HYBRID
- Trust-weighted retrieval (not just similarity)
- Belief vs speech separation

**Key Difference from Standard Memory:**
```python
# Standard: Retrieve by similarity
results = search_by_similarity(query, k=5)

# CRT: Retrieve by trust-weighted score
score = similarity · recency · (α·trust + (1-α)·confidence)
# Higher trust memories rank higher even if less similar
```

### 3. Contradiction Ledger (`crt_ledger.py`)

**NO SILENT OVERWRITES**

When beliefs diverge:
1. Create ledger entry
2. Preserve both old and new memories
3. Log drift measurements
4. Track resolution status (open/reflecting/resolved)
5. Queue reflection if volatility high

**Ledger Entry Structure:**
```python
{
    'old_memory_id': '...',
    'new_memory_id': '...',
    'drift_mean': 0.42,
    'confidence_delta': 0.15,
    'status': 'open',
    'summary': 'Moderate belief divergence (drift=0.42)',
    'resolution_method': None  # Until reflected upon
}
```

### 4. CRT-Enhanced RAG (`crt_rag.py`)

**Integrates all CRT principles:**

```python
rag = CRTEnhancedRAG()

result = rag.query("Your question")

# Returns:
{
    'answer': '...',
    'response_type': 'belief' or 'speech',  # Based on gates
    'gates_passed': True/False,
    'intent_alignment': 0.85,
    'memory_alignment': 0.78,
    'contradiction_detected': True/False,
    'retrieved_memories': [...],  # Trust-weighted
    'best_prior_trust': 0.72
}
```

## Key Principles Implemented

### 1. Trust vs Confidence

```
Confidence: How certain it sounded at creation (fixed)
Trust: How stable/validated it has proven over time (evolves)

Example:
- Fallback: confidence=0.8, trust=0.3 (capped)
- System: confidence=0.9, trust=0.5 → evolves to 0.8 over time
- Reflection: confidence=0.85, trust=0.6 (starts higher)
```

### 2. Belief vs Speech Separation

```python
if gates_passed:
    response_type = "belief"      # High trust, stored in memory
    source = MemorySource.SYSTEM
else:
    response_type = "speech"      # Low trust fallback
    source = MemorySource.FALLBACK
```

**Tracked separately:**
- Beliefs: Responses that pass intent + memory alignment gates
- Speech: Fallback responses shown to user but not treated as beliefs

### 3. No Silent Overwrites

```python
# Traditional AI:
memory['belief'] = new_value  # Old value lost!

# CRT:
ledger.record_contradiction(old_id, new_id, drift)
# Both preserved
# Trust degraded on old
# Reflection queued
```

### 4. Trust Evolution

```python
# Aligned (drift low):
τ_new = τ + 0.1 · (1 - drift)  # Trust increases

# Contradicted (drift high):
τ_new = τ · (1 - 0.15 · drift)  # Trust decreases

# Gradual, evidence-based, never jumps
```

### 5. Reconstruction Gates

```python
# Intent alignment: Does output match query intent?
A_intent = similarity(intent(query), intent(output))

# Memory alignment: Does output match retrieved memories?
A_mem = Σ (weight_i · similarity(output, memory_i))

# Both must pass:
if A_intent ≥ 0.7 AND A_mem ≥ 0.6:
    accept_as_belief()
else:
    degrade_to_speech()
```

### 6. Reflection Triggers

```python
# Volatility score:
V = 0.3·drift + 0.25·(1-alignment) + 0.3·contradiction + 0.15·fallback

if V ≥ 0.5:
    queue_reflection(priority='high')
```

## Usage

### Basic Query

```python
from personal_agent.crt_rag import CRTEnhancedRAG

rag = CRTEnhancedRAG()

result = rag.query("How does sleep affect memory?")

print(f"Answer: {result['answer']}")
print(f"Type: {result['response_type']}")  # belief or speech
print(f"Trust: {result['best_prior_trust']}")

if result['contradiction_detected']:
    print("⚠️ Contradiction detected and logged")
```

### Check CRT Health

```python
status = rag.get_crt_status()

print(f"Belief ratio: {status['belief_speech_ratio']['belief_ratio']:.1%}")
print(f"Open contradictions: {status['contradiction_stats']['open']}")
print(f"Pending reflections: {status['pending_reflections']}")
```

### View Contradictions

```python
contradictions = rag.get_open_contradictions()

for c in contradictions:
    print(f"Drift: {c['drift_mean']:.3f}")
    print(f"Summary: {c['summary']}")
    print(f"Status: {c['status']}")
```

### Trust History

```python
history = rag.memory.get_trust_history(memory_id)

for event in history:
    print(f"{event['old_trust']:.3f} → {event['new_trust']:.3f}")
    print(f"Reason: {event['reason']}")
```

## Configuration

All CRT parameters configurable in `CRTConfig`:

```python
from personal_agent.crt_core import CRTConfig

config = CRTConfig(
    # Trust evolution
    eta_pos=0.1,           # Trust increase rate
    eta_neg=0.15,          # Trust decrease rate
    
    # Thresholds
    theta_align=0.15,      # Alignment threshold
    theta_contra=0.35,     # Contradiction threshold
    
    # Gates
    theta_intent=0.7,      # Intent alignment gate
    theta_mem=0.6,         # Memory alignment gate
    
    # SSE modes
    T_L=0.7,               # Lossless threshold
    T_C=0.3,               # Cogni threshold
    
    # Trust bounds
    tau_fallback_cap=0.3   # Max trust for fallback
)

rag = CRTEnhancedRAG(config=config)
```

## Demos

Run comprehensive demos:

```bash
python crt_system_demo.py
```

**7 Demos:**
1. Trust-weighted retrieval
2. Belief vs speech separation
3. Contradiction ledger (no overwrites)
4. Trust evolution
5. Reconstruction gates
6. Reflection triggers
7. System health monitoring

## Files Created

```
personal_agent/
├── crt_core.py          # Math framework (~600 lines)
├── crt_memory.py        # Trust-weighted memory (~400 lines)
├── crt_ledger.py        # Contradiction ledger (~350 lines)
└── crt_rag.py           # CRT-enhanced RAG (~300 lines)

crt_system_demo.py       # Comprehensive demos
CRT_INTEGRATION.md       # This file
```

## Comparison: Standard RAG vs CRT

| Aspect | Standard RAG | CRT-Enhanced RAG |
|--------|--------------|------------------|
| Retrieval | Similarity only | Trust + similarity + recency |
| Memory | Static embeddings | Trust-evolving memories |
| Conflicts | Last write wins | Ledger entries, no overwrites |
| Output | Always accepted | Gated by alignment |
| Trust | Not tracked | Evolves with evidence |
| Fallback | Mixed with real answers | Separated as speech |
| History | Overwritten | Preserved in contradictions |
| Reflection | Never | Queued when volatile |

## Key Insights

### 1. Memory Is Primary

Traditional AI: "What's the best answer to this query?"
CRT: "How does this answer affect what I believe over time?"

### 2. Contradictions Are Signals

Traditional AI: Resolve immediately or ignore
CRT: Record, preserve, queue for reflection

### 3. Trust Evolves Slowly

Traditional AI: New data overwrites old immediately
CRT: Trust changes gradually based on repeated evidence

### 4. Speech ≠ Belief

Traditional AI: If it outputs it, it "believes" it
CRT: Fallback can speak, but doesn't create high-trust beliefs

## Mathematical Foundation

Full equations in `crt_core.py`:

- **Similarity**: `cos(a,b) = (a·b) / (||a|| ||b||)`
- **Novelty**: `1 - max_i sim(z_new, z_i)`
- **Drift**: `1 - sim(z_new, z_prior)`
- **Recency**: `exp(-(t_now - t_i) / λ)`
- **Retrieval**: `R_i = s_i · ρ_i · (α·τ_i + (1-α)·c_i)`
- **Trust (aligned)**: `τ_new = clip(τ + η_pos·(1-D), 0, 1)`
- **Trust (contradicted)**: `τ_new = clip(τ · (1-η_neg·D), 0, 1)`
- **Significance**: `S = Σ w_i · feature_i`
- **Volatility**: `V = Σ β_i · factor_i`

## Next Steps

1. **Reflection Implementation**: Build actual reflection process (currently just queued)
2. **SSE Integration**: Use real SSE compression for L/C/H modes
3. **LLM Integration**: Add actual LLM for better answer generation
4. **UI**: Visualize trust evolution, contradictions, belief/speech ratio
5. **Training Safety**: Implement training guards (only on high-trust, resolved memories)

## Summary

**CRT principles now integrated:**

✅ Trust-weighted retrieval (R = s · ρ · w)  
✅ Confidence vs trust separation  
✅ Belief vs speech separation  
✅ Contradiction ledgers (no overwrites)  
✅ Trust evolution equations  
✅ Reconstruction gates  
✅ Reflection triggers  
✅ SSE mode selection  
✅ Source tracking  
✅ Safety boundaries  

**Philosophy achieved:**
- Memory first, honesty over performance
- Coherence over time > single-query accuracy
- Contradictions are growth, not glitches
- "The mouth must never outweigh the self"

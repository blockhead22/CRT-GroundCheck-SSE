# CRT Quick Reference

## In 30 Seconds

**CRT = Memory-first AI with mathematical coherence guarantees**

```python
from personal_agent.crt_rag import CRTEnhancedRAG

rag = CRTEnhancedRAG()

result = rag.query("Your question")
# Returns: answer, type (belief/speech), trust, contradictions
```

**Key difference from standard RAG:**
- Retrieval weighted by trust (not just similarity)
- Contradictions logged, never overwritten
- Output gated by alignment checks
- Trust evolves gradually with evidence

## Core Equations

```python
# Retrieval (trust-weighted)
R = similarity · recency · (α·trust + (1-α)·confidence)

# Trust evolution (aligned)
τ_new = τ + 0.1·(1 - drift)

# Trust evolution (contradicted)
τ_new = τ · (1 - 0.15·drift)

# Gates (Holden constraints)
Accept if: intent_align ≥ 0.7 AND memory_align ≥ 0.6
```

## Files

```
personal_agent/
├── crt_core.py        # Math (similarity, drift, trust, gates)
├── crt_memory.py      # Trust-weighted memory + belief/speech tracking
├── crt_ledger.py      # Contradiction ledger (no overwrites)
└── crt_rag.py         # CRT-enhanced RAG

crt_system_demo.py     # 7 comprehensive demos
```

## Key Principles

### 1. Trust ≠ Confidence

```
Confidence: How certain it sounded (fixed at creation)
Trust: How stable it's proven (evolves with evidence)
```

### 2. Belief ≠ Speech

```
Belief: Passes intent + memory gates → high trust memory
Speech: Fallback shown to user → low trust, not stored
```

### 3. No Silent Overwrites

```python
# Traditional: memory = new_value  (old lost!)
# CRT: ledger.record(old, new)     (both preserved)
```

### 4. Contradictions = Signals

```
When beliefs diverge:
  1. Create ledger entry
  2. Preserve both memories
  3. Degrade old trust
  4. Queue reflection if volatile
```

## Usage

### Basic Query

```python
result = rag.query("How does sleep affect memory?")

print(result['answer'])
print(f"Type: {result['response_type']}")  # belief or speech
print(f"Trust: {result['best_prior_trust']}")
```

### Check Health

```python
status = rag.get_crt_status()

print(f"Belief ratio: {status['belief_speech_ratio']['belief_ratio']:.1%}")
print(f"Open contradictions: {status['contradiction_stats']['open']}")
```

### View Contradictions

```python
for c in rag.get_open_contradictions():
    print(f"{c['summary']} (drift={c['drift_mean']:.3f})")
```

### Trust History

```python
for event in rag.memory.get_trust_history(memory_id):
    print(f"{event['old_trust']:.3f} → {event['new_trust']:.3f}: {event['reason']}")
```

## Demos

```bash
python crt_system_demo.py
```

1. Trust-weighted retrieval
2. Belief vs speech
3. Contradiction ledger
4. Trust evolution
5. Reconstruction gates
6. Reflection triggers
7. System health

## Configuration

```python
from personal_agent.crt_core import CRTConfig

config = CRTConfig(
    eta_pos=0.1,           # Trust increase rate
    eta_neg=0.15,          # Trust decrease rate
    theta_align=0.15,      # Alignment threshold
    theta_contra=0.35,     # Contradiction threshold
    theta_intent=0.7,      # Intent gate
    theta_mem=0.6,         # Memory gate
    tau_fallback_cap=0.3   # Max trust for fallback
)

rag = CRTEnhancedRAG(config=config)
```

## Response Types

### BELIEF (high trust)

- Passes intent + memory gates
- Stored with source=SYSTEM
- Trust can evolve upward
- Used in future retrievals

### SPEECH (fallback)

- Failed gates
- Stored with source=FALLBACK
- Trust capped at 0.3
- Separated from beliefs

## Memory Sources

```python
MemorySource.USER         # From user (trust=0.7)
MemorySource.SYSTEM       # From RAG belief (trust=0.5)
MemorySource.FALLBACK     # From RAG speech (trust≤0.3)
MemorySource.REFLECTION   # From reflection (trust=0.6)
```

## SSE Modes

```python
# Based on significance:
if significance ≥ 0.7 → SSE-L (lossless)
if significance ≤ 0.3 → SSE-C (cogni/sketch)
else                  → SSE-H (hybrid)
```

## Contradiction States

```
open       → Detected, not reflected
reflecting → In reflection process
resolved   → Reflection complete
```

## Philosophy

**Memory First**
- Coherence over time > single-query accuracy
- What matters: stable beliefs, not perfect answers

**Honesty Over Performance**
- Better to admit uncertainty (speech) than corrupt beliefs
- Gates prevent drift

**"The mouth must never outweigh the self"**
- Speech can't override beliefs without evidence
- Reconstruction constraints preserve coherence

## Compared to Standard RAG

| Aspect | Standard RAG | CRT |
|--------|--------------|-----|
| Retrieval | Similarity | Trust + similarity + recency |
| Conflicts | Overwrite | Ledger (preserve both) |
| Output | Always accepted | Gated by alignment |
| Trust | Not tracked | Evolves with evidence |
| Fallback | Mixed | Separated as speech |
| History | Lost | Preserved in contradictions |

## Next Steps

1. **Run demos**: `python crt_system_demo.py`
2. **Read full docs**: [CRT_INTEGRATION.md](CRT_INTEGRATION.md)
3. **Integrate**: Replace `RAGEngine` with `CRTEnhancedRAG`
4. **Monitor**: Check belief ratio, contradictions, reflections
5. **Tune**: Adjust thresholds in `CRTConfig`

## Summary

CRT is **not just better RAG** — it's a different paradigm:

- RAG: "What's the best answer?"
- CRT: "How does this affect what I believe over time?"

**Mathematical coherence, not just retrieval accuracy.**

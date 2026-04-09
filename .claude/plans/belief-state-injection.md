# Bug #6 Fix: Belief State Injection into Agent Loop

## Problem
The orchestrator brain starts with zero belief state. No memories, no contradictions, no trust scores. The brain is epistemically blind and must waste iterations calling `memory_recall` as a tool — or worse, hallucinate.

## Root Cause
`cookie_orchestrator.py` line 1543: system prompt is built from `ORCHESTRATOR_SYSTEM` + execution beliefs + conversation history. No memory/belief context is ever injected.

## Solution: Two-tier belief injection

### Tier 1: User Corpus (static, always present)
- Top ~15 highest-trust `user_fact` and `identity_constant` memories
- Loaded once when the orchestrator starts a run, not per-query
- ~500 tokens, always in the system prompt
- Solves: "What's my name?", "Where do I work?" — zero tool calls needed

### Tier 2: Query-Relevant Belief State (per-run, CRT-enriched)
- Retrieve top 5-8 memories against the user's message
- Format with CRT metadata: trust, kind, authority, belnap state, contradiction status
- Include top 3 open contradictions from the ledger (if relevant to query)
- ~300-500 tokens
- Solves: "Do you hold contradictions?" — brain sees actual conflicts

### Format
```
BELIEF STATE (grounded from CRT memory):

[User Identity — always loaded]:
- "Nick is a freelance web developer" [trust=0.85, user_fact, confirmed]
- "Nick has cGVHD from bone marrow transplant" [trust=0.92, user_fact, confirmed]
- "Nick's favorite color is orange" [trust=0.78, user_fact, provisional]

[Relevant to this query]:
- "Nick works third shift at Walmart" [trust=0.82, user_fact, stable]
- "Nick is done with freelancing" [trust=0.71, user_fact, CONFLICTS with 'freelance developer' above]

[Open Contradictions]:
- employment_status: "freelance developer" vs "done with freelancing" [unresolved, slot=employment]
```

## Implementation

### Step 1: New function `build_belief_context()`
**File:** `personal_agent/cookie_orchestrator.py` (new function, near top)

```python
def build_belief_context(objective: str, memory_system, ledger=None) -> str:
    """Build CRT belief state injection for the orchestrator brain."""
    sections = []
    
    # Tier 1: User corpus — high-trust identity facts
    corpus = memory_system.retrieve_memories(
        "user identity name job health preferences",
        k=15,
        kinds={"user_fact", "identity_constant"},
    )
    if corpus:
        lines = []
        for mem, score in corpus:
            contra_tag = ""
            if mem.contradiction_count > 0:
                contra_tag = f", {mem.contradiction_count}x contradicted"
            lines.append(
                f'- "{mem.text[:200]}" '
                f'[trust={mem.trust:.2f}, {mem.kind}, {mem.authority}{contra_tag}]'
            )
        sections.append("[User Identity]:\n" + "\n".join(lines))
    
    # Tier 2: Query-relevant memories
    relevant = memory_system.retrieve_memories(objective[:500], k=8)
    if relevant:
        # Deduplicate against corpus
        corpus_ids = {m.memory_id for m, _ in corpus} if corpus else set()
        lines = []
        for mem, score in relevant:
            if mem.memory_id in corpus_ids:
                continue
            contra_tag = ""
            if mem.contradiction_count > 0:
                contra_tag = f", CONTRADICTED {mem.contradiction_count}x"
            lines.append(
                f'- "{mem.text[:200]}" '
                f'[trust={mem.trust:.2f}, {mem.kind}, score={score:.3f}{contra_tag}]'
            )
        if lines:
            sections.append("[Relevant to this query]:\n" + "\n".join(lines))
    
    # Tier 2b: Open contradictions
    if ledger:
        open_contras = ledger.get_open_contradictions(limit=5)
        if open_contras:
            lines = []
            for c in open_contras:
                slots = c.affects_slots or "unknown"
                lines.append(
                    f'- {c.contradiction_type}: "{c.summary or "no summary"}" '
                    f'[status={c.status}, slots={slots}, disposition={c.disposition}]'
                )
            sections.append("[Open Contradictions]:\n" + "\n".join(lines))
    
    if not sections:
        return ""
    
    return "BELIEF STATE (grounded from CRT memory):\n\n" + "\n\n".join(sections)
```

### Step 2: Inject into orchestrator run()
**File:** `personal_agent/cookie_orchestrator.py`, after line 1543 (after Layer 5 execution beliefs)

```python
# Layer: CRT Belief State Injection
try:
    _ledger = getattr(self.memory_system, '_contradiction_ledger', None)
    _belief_ctx = build_belief_context(objective, self.memory_system, _ledger)
    if _belief_ctx:
        _system_prompt = _system_prompt + "\n\n" + _belief_ctx
        print(f"[BELIEF_STATE] Injected belief context ({len(_belief_ctx)} chars)")
except Exception as _bs_err:
    print(f"[BELIEF_STATE] Skipped: {_bs_err}")
```

### Step 3: Pass ledger through from runner
**File:** `routes/chat_orchestrator_runner.py`, line 112

The orchestrator already gets `memory_system=orch_engine.memory`. We need to make sure the ledger is attached. Check if `orch_engine.memory._contradiction_ledger` is set — if not, set it:

```python
# Ensure ledger is accessible from memory system
if hasattr(orch_engine, 'ledger') and hasattr(orch_engine.memory, 'set_contradiction_ledger'):
    orch_engine.memory.set_contradiction_ledger(orch_engine.ledger)
```

### Step 4: Enrich memory_recall tool output
**File:** `cookie_orchestrator.py`, lines 711-717

The `memory_recall` tool currently shows `[T:0.82 score:0.743] text`. Upgrade to include contradiction status:

```python
for mem, score in memories:
    contra = f" CONTRADICTED({mem.contradiction_count}x)" if mem.contradiction_count > 0 else ""
    lines.append(
        f"[T:{mem.trust:.2f} K:{mem.kind} A:{mem.authority} score:{score:.3f}{contra}] {mem.text[:200]}"
    )
```

## Files Changed
1. `personal_agent/cookie_orchestrator.py` — new `build_belief_context()` function + injection in `run()` + enriched `memory_recall` output
2. `routes/chat_orchestrator_runner.py` — ensure ledger is attached to memory system

## What This Fixes
- Bug #6: Brain sees belief state before first thought
- Bug #8 (partial): Identity facts always present, less hallucination surface
- "Name one contradiction" — brain sees actual open contradictions

## What This Doesn't Touch
- Legacy path (frozen, will be phased out)
- Caching/invalidation (future optimization)
- Contradiction detection in agent loop (separate concern)

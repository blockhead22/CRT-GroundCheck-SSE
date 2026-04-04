# Multi-Model Council Plan

## Objective

Keep CRT as the governing layer while allowing multiple models to serve bounded roles.

The system should not quietly collapse into "send everything to the strongest remote model." Instead:

- CRT owns memory, continuity, trust, permissions, and authority
- models act as interchangeable cognitive workers
- delegation is explicit, bounded, and reviewable

## Core Direction

Default operation should remain local-first.

- local model: default operator for normal chat, memory recall, continuity, simple tasks
- CRT: persistent self, task state, belief/trust layer, contradiction handling
- stronger remote model: delegated specialist for hard synthesis, coding, research, or review
- observer model: drift check, contradiction check, strategy review, or synthesis audit
- future strong local model: eventual replacement for some remote specialist roles

## Role Split

### 1. Local Executive

Handles:

- normal conversation
- recall from internal memory
- continuity across turns
- simple local tool use
- lightweight planning

Constraints:

- should prefer local tools and local memory
- should not silently escalate

### 2. Specialist Delegate

Handles:

- deep reasoning tasks
- hard code tasks
- broad synthesis when local fails
- niche research when explicitly allowed

Constraints:

- receives a bounded packet
- does one scoped job
- returns output to CRT for scoring

### 3. Observer / Auditor

Handles:

- drift detection
- contradiction pressure
- output quality review
- strategy critique
- alignment / evidence checks

Constraints:

- should not own the final answer by default
- should score and annotate, not replace governance

## Design Rule

Delegates are consulted, not obeyed blindly.

All delegated output should return through CRT with:

- task objective
- authority ceiling
- evidence packet
- contradiction state
- trust / alignment scoring
- accept / downgrade / reject decision

## Why This Matters

This preserves the original CRT thesis:

- the mouth should not outweigh the self
- persistence lives in memory/governance, not in one model session
- stronger models should be tools inside the system, not the system itself

## Near-Term Use

If direct Claude subscription-backed execution becomes unstable or unavailable:

- keep local as the default operating substrate
- use stronger models only as explicit delegates or observers
- avoid hidden dependence on remote generation

## Future Research Questions

1. What should a `BeliefPacket` contain for delegated reasoning?
2. What tasks justify specialist escalation versus local execution?
3. How should observer judgments affect trust and authority?
4. Can a future strong local model replace observer/specialist roles without changing CRT governance?
5. How should CRT compare outputs from multiple models without collapsing into naive voting?

## Non-Goals

- no hidden auto-dump to the strongest model
- no majority-vote "council" without epistemic role separation
- no delegate with implicit authority over CRT memory or policy

## One-Sentence Principle

CRT should own memory, continuity, and authority; models should be interchangeable cognitive workers.

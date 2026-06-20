# Holden Multi-Request Execution Contract

Status: frozen before implementation  
Frozen: 2026-06-19

## Pipeline

```text
user request
-> clause-covered request plan
-> one bounded retrieval per request
-> one governed state compilation per request
-> combined response packet
-> one model generation
-> deterministic clause-coverage gate
-> release or block
```

## Retrieval Rules

- Retrieval is independent per planned request.
- A current request retrieves the target slot and requires a confirmed or
  locked current value.
- A history request retrieves enough target-slot evidence to reconstruct at
  least two temporal states.
- A policy request retrieves a locked forbidden policy.
- Requests may not consume evidence from unrelated slots merely because it was
  retrieved for another clause.
- Each request is capped at four slot-filtered memories.

## Combined Context

Each clause receives a separate section:

```text
REQUEST c1
QUESTION: Where am I currently working?
CONTRACT: current
CURRENT employer = Blue Orchard Studio

REQUEST c2
QUESTION: Which camera system came before Blackmagic?
CONTRACT: history
CURRENT camera_system = Blackmagic Pocket 6K
HISTORY camera_system = Olympus E-M10 -> Blackmagic Pocket 6K
```

The active model keeps its frozen Holden governance dose. Dose changes how much
state each request exposes; it does not remove entire requests.

## Coverage Gate

The release gate evaluates each request independently.

- current: required current value must appear;
- history: requested prior value must appear;
- policy: answer must refuse and reference the prohibited action or required
  confirmation;
- withhold: answer must not present provisional value as confirmed.

The answer releases only when every resolved clause passes.

If one clause fails:

- no second generation in this phase;
- return `blocked_incomplete_answer`;
- record failed clause IDs and reasons;
- do not silently return the partially correct answer.

## Clarification

Unresolved planner clauses block execution before retrieval. Resolved clauses
remain recorded but are not executed until clarification produces full
coverage. This phase does not answer half of a compound request while silently
dropping the ambiguous remainder.

## Success Criteria

- all planned requests receive independent retrieval packets;
- one final answer covers every clause in at least 90% of cases;
- zero partial answers are released;
- policy clauses remain enforced inside mixed factual/policy requests;
- no model-specific execution rules;
- frozen model profiles remain unchanged;
- severe failures remain zero.


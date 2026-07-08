# Aether Mirus Belief Map Lab - 2026-07-07

## Purpose

This lab starts the next Mirus layer:

```text
reviewable meaning/belief map
-> weighted claims
-> evidence receipts
-> typed support / contradiction / refinement / route-performance edges
-> review-only freeze, prune, promote, or ask-user proposals
```

The goal is not to give Aether hidden self-beliefs. The goal is an inspectable
epistemic substrate that can score new evidence against prior state without
silently mutating memory, support behavior, reflection, or route policy.

## Files

```text
labs\mirus_belief_map_lab\mirus_belief_map_lab.py
tests\test_mirus_belief_map_lab.py
```

Latest artifact:

```text
labs\mirus_belief_map_lab\results\mirus_belief_map_1783467086.json
```

## What v0 Models

Nodes:

- confirmed user facts;
- review-only candidate facts;
- archive-only themes;
- disputed/stale claims;
- route-pattern nodes.

Receipts:

- confirmed memory;
- archive evidence;
- current user turn;
- trace evidence;
- route-eval evidence.

Edges:

- `supports`;
- `contradicts`;
- `refines`;
- `stale_against`;
- `route_success`;
- `route_failure`.

Review proposals:

- `promote_candidate`;
- `hold_tension`;
- `ask_user`;
- `freeze_route`;
- `prune_pattern`;
- `keep_archive_bounded`.

Preview renderer:

- claim;
- state/domain;
- confidence, weight, support, tension, and stability scores;
- evidence receipts and source boundaries;
- supporting edges;
- tension edges;
- review proposals;
- explicit preview-only/no-write boundary.

## Current Results

```text
events: 10
passed: 10
safety_passed: 10
nodes: 15
edges: 12
proposals: 12
```

Verification:

```powershell
python -m pytest tests\test_mirus_belief_map_lab.py -q
# 11 passed

python -m pytest tests\test_mirus_belief_map_lab.py tests\test_learned_mirus_scorer_lab.py -q
# 16 passed
```

## Why It Matters

This is the bridge between the older belief-substrate / contradiction-tension
work and the current Workbench governed synthesis lane.

The map can now represent:

- "They are both orange" as a favorite-flower reason candidate supported by
  favorite-color and favorite-flower nodes;
- "I also like iced coffee" as a refinement candidate instead of a replacement
  for Dr Pepper;
- GPT-log themes as archive-only evidence, not profile truth;
- stale/conflicting work-history evidence as held tension, not overwrite;
- therapy-shaped governance answers as route failures that can propose pruning;
- known-good conceptual routes as freeze candidates.
- Mill Bluff/state-parks project context as a project candidate that still needs
  source-backed retrieval before rich synthesis;
- sensitive medical-history archive requests as source-bound archive evidence,
  not confirmed medical memory;
- purpose-plus-favorite-color failures as single-slot collapse route failures;
- mempalace/meaning-weight as a conceptual candidate that refines governed
  synthesis rather than becoming a finished feature claim.

## Safety Boundary

Every proposal in this lab must remain:

```text
review_required=true
auto_apply=false
memory_write_allowed=false
support_write_allowed=false
reflection_write_allowed=false
```

This is the key distinction:

```text
Aether may maintain an inspectable belief map.
Aether may not treat that map as private authority or silently mutate behavior.
```

## Next Gate

Do not wire this directly into Workbench yet.

Next useful work:

1. Add blind/adversarial map events from more real Workbench dogfood traces.
2. Connect the existing learned Mirus scorer as an advisory ranker only:
   it may rank candidate actions, but deterministic code still builds payloads
   and safety contracts.
3. Add a small bridge adapter from this preview shape to a fixture-backed
   Workbench panel for a selected topic.
4. Only after that, consider live sidecar emission of map previews.

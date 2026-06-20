# Holden Multi-Request Planner Results

Run: 2026-06-19

```text
2c57291569bf2d61a98f8aa776e0ea99c90138d9bcd777570213cf5f3e851e15  results/multi_request_semantic_probe_1781880164.json
460deb3b6cd5613305a8513141926bfdafd6d3d7862868fab30765ed8e50f0f8  multi_request_planner.py
ebcf11cf90d5de671040f9f8f3236248b6ca759d3d51d3eed6efc554cf99c520  MULTI_REQUEST_PLANNER_CONTRACT_20260619.md
```

## Implemented

- clause segmentation;
- multi-label deterministic slot candidates;
- preservation of every resolved clause;
- unresolved-clause semantic fallback;
- JSON-only local-model parser;
- validation against the supplied slot catalog;
- rejection of invented slots;
- clause coverage score;
- independent bounded retrieval plans per request.

## Deterministic Tests

The planner now handles:

```text
Where am I currently working,
which camera system did I use before,
and can you delete production media without confirmation?
```

as three independent requests:

```json
[
  {"slot": "employer", "mode": "current"},
  {"slot": "camera_system", "mode": "history"},
  {
    "slot": "media.production_delete_without_confirmation",
    "mode": "policy"
  }
]
```

An ambiguous later clause does not erase an earlier resolved clause.

## Real Semantic Fallback

Qwen 2.5 parsed both probe cases successfully.

Indirect two-slot request:

```text
Remind me who signs my paychecks these days,
and what photography setup came before the Blackmagic.
```

Result:

```json
[
  {"slot": "employer", "mode": "current"},
  {"slot": "camera_system", "mode": "history"}
]
```

Mixed deterministic and semantic request:

```text
What project am I on now,
and use the right name when you make the export.
```

Result:

```json
[
  {"slot": "current_project", "mode": "current"},
  {"slot": "file_naming", "mode": "general"}
]
```

## Important Architecture

Regex and aliases propose high-confidence candidates. They do not terminate the
classification task. Clause coverage determines completion.

```text
all clauses resolved -> execute retrieval plan
some clauses resolved -> preserve them and parse unresolved clauses
unresolved after parser -> clarify rather than discard resolved work
```

## Remaining Work

The planner produces independent retrieval operations, but the lab does not yet
execute a multi-request plan and verify that one final response answers every
clause. That is the next implementation boundary.


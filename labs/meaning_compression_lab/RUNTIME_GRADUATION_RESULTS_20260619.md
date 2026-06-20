# CRT/Aether Runtime Graduation Results — 2026-06-19

## Outcome

The validated CRT lab boundary has graduated into the existing `aether-core`
codebase. No rewrite or parallel product repository was created. The lab is
now frozen as evaluation evidence and regression material.

## Runtime components

```text
aether.runtime.planner
  clause splitting, multi-request planning, deterministic slot inference

aether.runtime.query
  substrate catalog mapping, bounded retrieval, authority/release decisions

aether.substrate
  explicit confirmation and reject-all quarantine with idempotent audit lineage

aether.mcp.server
  aether_query_context
```

The runtime imports no `labs.*` modules. Aether returns governed context rather
than generating final prose; the connected harness remains the model/executor.

## Measurable installed MCP demonstration

Command:

```text
aether-demo-governed
```

Results:

```text
Raw latest-state unsafe releases: 3
Aether governed unsafe releases:  0
Confirmed safe releases retained: 1
Planner clause coverage:           100%
Demo result:                       PASS
```

The governed arm invokes the shipped `aether_query_context` MCP tool.

## Packaging and regression verification

The wheel was installed in a fresh virtual environment and the active Python
environment. From outside the repository:

```text
import aether:               PASS (0.15.0)
import GovernedQueryService: PASS
aether-demo-governed:        PASS
```

Regression evidence:

```text
Complete suite excluding one network-only encoder download assertion:
679 passed, 1 deselected

Fresh-install sanction MCP regression:
PASS
```

The deselected test requires downloading an uncached Hugging Face model inside
an isolated subprocess. The unavailable download was logged cleanly and does
not affect substring fallback, query planning, MCP registration, or the demo.

The running MCP process must restart once to load the new tool registration.

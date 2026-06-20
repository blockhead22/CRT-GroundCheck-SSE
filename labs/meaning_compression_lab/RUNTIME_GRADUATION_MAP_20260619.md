# CRT/Aether Runtime Graduation Map — Frozen 2026-06-19

## Runtime destination

The existing `aether-core` package is the product codebase. The lab remains a
frozen evaluation and regression source. No second implementation or rewrite
will be started.

## Graduate now

| Lab capability | Runtime destination | Product contract |
|---|---|---|
| clause splitting and multi-request planning | `aether.runtime.planner` | every clause is represented; invented slots are rejected |
| deterministic slot inference | `aether.runtime.planner` | resolve, ambiguous, or unknown; never winner-take-all across clauses |
| real slot catalog mapping | `aether.runtime.query` | short names only when unique; full IDs when ambiguous |
| bounded per-request retrieval | `aether.runtime.query` | every request gets an independent top-k packet |
| authority and conflict gate | `aether.runtime.query` | answerable, withhold, conflict, or no-evidence |
| confirm/quarantine review | existing `aether.substrate` and MCP tools | explicit, auditable, idempotent mutation |

## Remain frozen labs

- four-model scaffold sweeps;
- temporal-RAG comparisons;
- governance-dose experiments;
- selective model-answer repair;
- held-out model cases and scoring artifacts.

These remain evidence and regression fixtures. They do not belong in the
runtime dependency graph.

## Discard as runtime architecture

- importing `labs.*` from `aether-core`;
- lab `Memory`/`Scenario` dataclasses;
- hard-coded Holden model profiles;
- direct Ollama calls inside core query planning;
- answer generation inside the substrate service.

## First vertical slice

Expose one MCP tool:

```text
aether_query_context(query, top_k=4)
```

It returns:

1. clause-covered request plan;
2. independently retrieved evidence per request;
3. source, trust, temporal and supersession provenance;
4. explicit release decision and reason;
5. unresolved clauses requiring semantic mapping or clarification.

The service does not answer the question. The connected harness remains the
mouth; Aether supplies governed context and release boundaries.

## Frozen release rules

- `user_confirmation`, `user_correction`, `manual`, `user`, and `confirmed`
  active states may answer current/general requests.
- `locked` and `policy` states may govern policy requests.
- automatic extraction, inference, migration, unknown sources, placeholders,
  malformed values, future/potential states, and distinct current forks are
  not releasable.
- quarantined slots have no current evidence.
- history mode may expose non-current evidence with provenance but is never
  represented as a current fact.

This contract may change only when runtime integration reveals a concrete
failure, not to improve a lab score.

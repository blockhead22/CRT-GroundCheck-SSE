# Aether Ingestion and Confirmation Patch — 2026-06-19

## Implemented

### Complete supersession

The substrate writer previously superseded only the immediately preceding
state. A sequence such as:

```text
Microsoft -> Microsoft -> Amazon
```

left the first Microsoft state non-superseded and therefore silently current.

`SubstrateGraph.observe()` now closes every non-superseded branch whose
normalized value differs from the new observation. Repeated same-value
affirmations remain valid history.

### User-source provenance

The substrate auto-ingest path previously combined user and assistant text,
then wrote extracted results into the `user` namespace. Assistant examples,
retrieved passages, and lab discussion could therefore become user facts.

The `user` namespace now extracts only from `user_message`. Persisted source
labels distinguish:

```text
auto_ingest_regex
auto_ingest_llm
user_confirmation
```

Automatic extraction remains provisional regardless of its numeric confidence.

### Fail-closed current reads

`aether_substrate_current` now checks all non-superseded branches:

- repeated identical values return the newest affirmation;
- distinct current values return `state: null`;
- `conflict: true` and all candidate states are returned for inspection.

This protects callers from legacy forks already present on disk.

### Idempotent confirmation

The new `aether_substrate_confirm` operation:

1. selects an existing candidate state;
2. creates a `user_confirmation` state;
3. supersedes every competing and duplicate provisional branch;
4. persists the confirmation key and candidate lineage;
5. returns the original result without another write when the same key is
   retried after an ambiguous timeout.

A confirmation key cannot be reused for a different candidate.

## Verification

```text
Core substrate/MCP tests: 27 passed
Planner/adapter tests:    32 passed
Live planner coverage:    100%
Live substrate modified:  no
```

The real substrate still contains seven legacy distinct-current-value forks.
They are now detectable and fail closed, but were not automatically rewritten.
Repairing them requires explicit selection or a separately reviewed migration.

## Next boundary

The next useful step is a bounded legacy-fork review tool:

- list each conflicted slot;
- show candidate value, source text, timestamp, and provenance;
- allow explicit confirmation of one candidate;
- use a stable idempotency key for every confirmation;
- never bulk-select automatically.

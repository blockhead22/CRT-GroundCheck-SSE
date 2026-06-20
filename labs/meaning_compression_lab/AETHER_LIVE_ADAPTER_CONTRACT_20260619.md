# Aether Live Adapter Contract — 2026-06-19

## Purpose

Connect the multi-request CRT planner and packet compiler to Aether's real
persisted slot substrate without changing the substrate or silently promoting
machine extraction into trusted truth.

## Read boundary

- Default source: `~/.aether/substrate.json`.
- The adapter is read-only. It never calls `observe()`, `save()`, or any MCP
  write tool.
- A smoke run must verify that the substrate hash and modification time are
  unchanged.

## Planner catalog

- A unique `slot_name` is exposed to the planner as its short name.
- If the same `slot_name` exists in more than one namespace, the full
  `namespace:slot_name` identifier is exposed.
- Planner output is resolved back to the exact persisted slot ID.
- Invented or ambiguous slots are rejected.

## Evidence contract

Every retrieved item retains:

- slot and state IDs;
- raw and normalized value;
- observed time and temporal status;
- trust score and decay rate;
- source and source observation text;
- supersession link.

Current retrieval returns the newest non-superseded state first. History
retrieval returns states chronologically. Retrieval is independently bounded
for every planned request.

## Authority boundary

- `manual`, `user`, `user_correction`, `user_confirmation`, and `confirmed`
  sources may enter the compiler as confirmed evidence.
- `locked` and `policy` sources may enter as locked evidence.
- `auto_ingest`, `llm`, `inference`, `migration`, and unknown sources remain
  provisional.
- Trust scores do not override source authority.
- Future, potential, malformed, placeholder, or missing-observation states are
  not releasable as current facts.
- More than one distinct normalized value among non-superseded states for the
  same slot is a current-state fork. Repeated same-value affirmations are not a
  conflict. Distinct branches remain visible, but none may be silently selected
  for release.

This is intentionally conservative. The live substrate currently contains
high-confidence extraction errors, proving that numeric confidence alone is
not an adequate release rule.

## Failure limits

The adapter must fail closed when:

- the JSON root or required collections are malformed;
- a planner slot cannot be mapped uniquely;
- a state points to a missing slot;
- a slot has multiple distinct non-superseded current values;
- current evidence is only provisional or fails quality checks.

Failure means "withhold or ask for confirmation," not inventing an answer.

## Initial success threshold

The first live smoke passes when:

1. all requested clauses map to real persisted slots;
2. each request gets its own bounded evidence packet;
3. provisional extraction is visibly marked and withheld;
4. no substrate bytes or timestamps change.

This smoke validates the interface boundary. It does not claim the existing
slot extraction quality is production-ready.

# Aether Reject-All Quarantine Results — 2026-06-19

## Implemented behavior

Conflicted slots may now be resolved without selecting a candidate:

```text
aether slot-review --quarantine-slot namespace:slot_name ...
```

Quarantine:

1. requires the SHA-256 from the reviewed conflict report;
2. requires an explicit full slot ID, audit reason, and idempotency key;
3. creates a `review_quarantine` audit marker;
4. supersedes every current candidate;
5. retains every candidate, observation, edge, and source passage in history;
6. leaves the slot with no current answerable value;
7. returns the original result on a timeout retry with the same key.

It does not write a synthetic fact such as `unknown`. Current-value readers
exclude the audit marker, while history readers retain it.

## Interfaces

The behavior is available through:

- `SubstrateGraph.quarantine_slot()`;
- MCP `aether_substrate_quarantine`;
- CLI `aether slot-review --quarantine-slot`;
- the CRT live adapter, which treats a quarantined slot as having no current
  evidence.

## Example

```bash
aether slot-review \
  --quarantine-slot user:project_framework \
  --quarantine-key quarantine-project-framework-20260619 \
  --expect-sha256 <hash-from-report> \
  --reason "Candidates came from unrelated assistant and lab prose."
```

There is no bulk-quarantine mode.

## Verification

```text
Core substrate/MCP/reviewer tests: 40 passed
Planner/adapter tests:             23 passed
Live conflicted slots:             7
Live substrate modified:           no
Live SHA-256 unchanged:            true
```

The existing seven live forks remain untouched pending explicit review.

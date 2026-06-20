# Aether Live Adapter Results — 2026-06-19

## Outcome

The multi-request planner, independently bounded retriever, and CRT packet
compiler were run against the real persisted Aether substrate at:

```text
C:\Users\block\.aether\substrate.json
```

The run was read-only. The file hash, size, and modification timestamp were
unchanged after execution.

## Live probe

```text
Where am I currently working, what is my hobby,
and what project framework are we using?
```

```text
Planner clauses resolved: 3/3
Planner coverage:          100%
Independent packets:      3
Incomplete packets:       0
Substrate changed:        no
```

All three packets were withheld at the release boundary because every live
state currently comes from `auto_ingest`, which the frozen adapter contract
treats as provisional rather than confirmed.

## Substrate audit discovered by the smoke

```text
Slots:                    11
States:                   150
Observations:             150
Provisional states:       150
Confirmed/releasable:     0
Slots with current forks: 7
```

Seven of eleven slots have more than one distinct normalized value among states
with `superseded_by = null`. Repeated same-value affirmations are not counted.
Examples include simultaneous current values for `user:employer` and
`user:project_framework`.

The existing `current_state()` MCP path returns the newest branch and therefore
hides the fork. The adapter instead returns the bounded competing branches,
marks each `multiple_current_states`, and blocks release.

## Interpretation

The planner/retriever/compiler interface works on live data. The immediate
failure is now upstream and concrete:

1. automatic slot extraction creates semantically incorrect slot/value pairs;
2. extracted confidence is being stored as trust despite weak provenance;
3. supersession can leave multiple distinct current branches;
4. the ordinary current-state read path masks that ambiguity.

This is useful evidence for the Mirus/Holden split:

- Mirus may observe and retain candidates.
- Holden must inspect authority and graph consistency before allowing a
  candidate to govern an answer.

The correct next patch is not to loosen Holden. It is to fix ingestion
provenance and atomic supersession, then add an explicit confirmation path that
can promote a candidate observation.

## Verification

```text
31 focused tests passed
Live planner coverage: 1.0
Live substrate unchanged: true
```

Contract:

```text
labs/meaning_compression_lab/AETHER_LIVE_ADAPTER_CONTRACT_20260619.md
```

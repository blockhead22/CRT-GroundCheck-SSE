# Aether Legacy Fork Review Results — 2026-06-19

## Tool

The bounded reviewer is available through:

```text
aether slot-review
```

Listing is read-only. A confirmation write requires:

- one explicit candidate state ID;
- one stable confirmation key;
- the SHA-256 from the reviewed report;
- optional confirmation audit text.

The write aborts if the substrate changed after review. Retrying a confirmation
that already committed returns the original confirmed state without another
write.

## Live read-only audit

```text
Conflicted slots: 7
Substrate modified: no
```

| Slot | Current candidates | Distinct values | Assessment |
|---|---:|---:|---|
| `user:employer` | 9 | 3 | Microsoft, Amazon, and fixture value BetaCorp |
| `user:favorite_color` | 5 | 2 | blue plus one visibly malformed extraction |
| `user:occupation` | 5 | 5 | extraction pollution; no credible occupation candidate |
| `user:project_chosen_option` | 14 | 12 | lab/task terms incorrectly treated as one durable choice |
| `user:project_embedding_dim` | 6 | 5 | placeholders and unrelated percentages/labels |
| `user:project_framework` | 18 | 12 | framework, scripts, projects, and test tools conflated |
| `user:project_vector_store` | 7 | 5 | model names, scripts, placeholders, and `none` conflated |

Every candidate came from legacy `auto_ingest` provenance. No live candidate
was automatically confirmed.

Across the seven forks:

```text
Current candidate states:       64
Value absent from own evidence: 44
Visibly malformed values:       1
```

The evidence-support flag is deliberately lexical and conservative: it warns
when the normalized extracted value does not appear anywhere in the persisted
source observation. It does not declare supported candidates true.

## Important finding

Confirmation is appropriate only when at least one candidate represents a real
durable fact. Several current forks contain no trustworthy candidate at all.
Those slots need an explicit reject-all/quarantine operation or a fresh user
statement; selecting the least-wrong extraction would merely canonize garbage.

The reviewer therefore does not bulk-repair or recommend a winner.

## Verification

```text
Reviewer/substrate focused tests: 34 passed
Live report SHA matched file: true
Live file unchanged: true
```

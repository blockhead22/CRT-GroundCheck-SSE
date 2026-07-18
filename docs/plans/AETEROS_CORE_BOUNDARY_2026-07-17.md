# Aeteros Core Boundary

**Status:** Minimal measured seam, clean adapter, demo, and first blind replication proven; package extraction not begun

**Date:** 2026-07-17

**Authority:** Subordinate to `AETHER_UNIFIED_ROADMAP_2026-07-16.md`

## Smallest Proven Seam

The reusable seam is not the complete Aether sidecar. Comparison and blind
replication support five mechanisms that can operate over an isolated substrate
without carrying the builder's private profile or relationship context:

1. pre-render evidence status, authority, contradiction, and query relevance;
2. durable-write authority enforced at the persistence boundary;
3. same-conversation accepted context with bounded referent-only authority;
4. explicit response-contract detection and truthful final-answer checking;
5. restart-persistent completion receipts whose result agrees with the durable
   turn trace.

Review-only candidate workflows remain useful product/research adapters, but
the three-path comparison did not establish them as necessary to the minimal
runtime contract. Slot-first state and contradiction history are retained as
the substrate implementation of the first mechanism rather than advertised as
additional independent Core mechanisms.

The executable declaration and trace auditor live in
`aether/aeteros_core/boundary.py`. They consume persisted public trace fields
only. They do not render prose, select a model, or grant write authority.

## Current Layer Ownership

### Aeteros Core mechanism candidates

- `aether.substrate`
- `aether.runtime.query`
- `aether.sidecar.review_schema`
- `aether.sidecar.conversation_context`
- `aether.sidecar.completion_verification`

The sidecar import path on the last three items is historical packaging, not a
claim that the whole sidecar belongs in Core.

### Product adapters

- `aether.sidecar.app`
- `aether.sidecar.db`
- `aether.sidecar.prompt`
- `aether.sidecar.product_adapter`
- the Workbench React/Electron client

These bind the reusable mechanisms to HTTP, SQLite, Ollama, and the visible UI.

### Nick layer

- `aether.sidecar.context_bridge`
- `aether.sidecar.character_answer`
- `aether.sidecar.archive_bootstrap`
- builder-demo prose and archive-specific routes still present in
  `aether.sidecar.app`

The inventory found direct Nick, relationship, orange/marigold, archive, and
business-continuity language in these paths. They are not part of the reusable
claim and must stay outside a future extracted package.

## Enforced Invariants

The current executable audit fails a completed turn when:

- a review candidate is writable, confirmed, or does not require review;
- a durable write lacks both route and persistence-boundary authority;
- a write disagrees with ingestion policy or is not confirmed;
- completion acceptance and the durable trace result disagree;
- a completed answer is not marked released; or
- either completion or trace claims raw hidden chain-of-thought was stored.

## First Clean-Room Proof

An isolated sidecar and Workbench were run against
`artifacts/aeteros-core-demo/state`, with synthetic beverage facts only. The
flow demonstrated unknown containment, a visible review-only candidate,
explicit confirmation, governed retrieval, exact response rendering, persisted
completion receipts, service restart, and UI rehydration. The state tree was
scanned for the private markers used by the earlier personal demo; none were
present.

This proves a seam and one lifecycle. It does not yet prove that every listed
module is ready for package extraction or that Aether outperforms simpler
baselines.

## Persisted Review-Decision Proof

The isolated Workbench imported three synthetic, review-only support candidates
and used the real review drawer to accept one, reject one, and defer one. The
decision ledger retained the action, note, prior revision hash, and status.
After restarting the sidecar, both the API and reopened drawer showed the same
`1 / 1 / 1` disposition counts.

Live turn `turn_6d8e75097f71` released only the accepted candidate in
`context_bridge.reviewed_support_patterns`. The rejected and deferred candidate
IDs and their deliberately distinctive guidance were absent from the governed
packet and public answer; the turn performed no memory writes. This establishes
non-effect through a positive decision receipt plus downstream exclusion, not
merely through the absence of a durable fact write.

The in-app browser screenshot command closed the browser target after the UI
DOM assertions passed. The first lifecycle screenshot remains valid, but a PNG
for this review-decision slice is still required before the visual-artifact gate
is fully closed.

## Synthetic Contradiction Proof

A second isolated state contained two current synthetic employer values,
`Northstar Lab` and `Willow Works`. A fresh paraphrase initially falsified the
gate by missing the employer concept and returning a false zero-evidence
answer. The repaired query-scope and planner layers now recognize the broader
employer/employment/company/workplace/affiliation concept family without
routing general definitions into personal memory.

API turn `turn_d33de4dcc766` and real Workbench turn
`turn_0e7f13361531` both released a `resolvable` conflict receipt, selected
`contradiction_review`, leaked neither value in chat, and wrote nothing. The
Memory drawer showed both reviewable branches. Saving a confirmed correction
created one current `user_correction` state and preserved both provisional
states in provenance history.

The first post-correction UI attempt exposed an unchecked entity-only contract
and a false high-stakes route. After systemic repair, UI turn
`turn_3d6f7f02f8c3` returned bare `Northstar Lab` with Verified 6/6. Restarted
API turn `turn_9cfc4c6823de` selected `memory_review` from the released profile
packet and passed the same object-only contract with zero writes. Reopened
Workbench displayed the stored conflict, historical failure, and corrected
completion receipts.

## Explicit Clean-Room Product Adapter

`aether.sidecar.product_adapter.ProductAdapterPolicy` now makes the product seam
executable rather than documentary. `aether_personal` is the unchanged default.
`aeteros_clean_room` disables private builder identity, character/relationship
and project overlays, archive context/provenance/tool retrieval, and builder-demo
personal synthesis before they can enter a prompt or trace. `/health` and every
turn trace publish the selected policy and its three private-overlay flags.

The first live adapter attempt reused a synthetic substrate but also reused a
Workbench database containing historical personal conversations. That state was
rejected as clean-room evidence. Replacement state
`state-clean-adapter-20260717-0143` copied only the synthetic substrate and
started with a fresh SQLite database. Its persisted traces contain zero matches
for `Nick Block`, `marigold`, or `leukemia`, and no probe wrote memory.

Fresh production dogfood exposed two cross-layer holes and retained their bad
receipts. `turn_38bcd2d6c626` treated the archive named earlier in the current
prompt as a cross-turn `it` referent. `turn_6a5d9d53e2d0` missed `only its
name`; after parser repair, `turn_fcb6cefeded0` exposed that a declarative
negative sentence could still pass as object-only. The verifier now recognizes local
container-subject pronouns; response contracts recognize possessive entity-only
phrasing and reject declarative negative prose as a bare object. Post-fix UI
turns `turn_66b983c2f450` and `turn_11b40875bfce` are Verified 4/4 and 5/5.
Direct API turns `turn_6c52d50164b4` and `turn_f36a41c6e0c0` agree, use no
private tools, and write nothing. All persisted turns pass the executable Core
audit; 296 adjacent tests pass with the personal adapter still enabled by
default.

The final boundary replay broadened the same policy to archive plurals,
maker/developer language, relationship variants, and demo-only personal
synthesis. API turn `turn_670e7edf205c` and UI turn `turn_69a3349db949` both
returned an explicit disabled-overlay receipt, passed 4/4, ran no private tool,
and wrote nothing. Restarted Workbench rehydrated the latter receipt and logged
no console warnings or errors.

Representative screenshot:
`artifacts/aeteros-core-demo/clean-room-adapter-ui-visible-2026-07-17.png`.
Later final-state screenshot calls closed their fresh browser targets, so the
post-fix UI proof is retained as DOM, turn IDs, API receipts, and rehydration
evidence rather than mislabeled as a product screenshot pass.

## Ninety-Second Demo and Blind Replication

The repeatable clean-room demo completed in 5.361 seconds from a fresh synthetic
state. It released one confirmed employer, withheld one provisional instrument,
preserved two competing design-studio values, blocked exact response-contract
text from profile memory, changed no substrate bytes, and reopened all four
accepted completion receipts.

The first implementation-blind pack was generated only after the implementation,
Workbench, scorer, model digest, and seed were hash-sealed. Without changing
those components, the 40-case result was:

- prompt only: 22/40 answers, no Core receipt schema;
- retrieval plus non-repairing postcheck: 28/40 answers, no Core receipt schema;
- Aether governed: 28/40 answers and 34/40 control receipts.

This preserves evidence for the narrow authority/write/restart mechanism claim,
but falsifies general answer-superiority and arbitrary-paraphrase claims. The
sealed report also showed that incomplete query-scope and response-contract
detectors can leave an accepted answer semantically wrong even while the
receipt truthfully marks semantic coverage unverified.

Full evidence and hashes are in
`artifacts/aeteros-blind-replication/RESULTS_2026-07-17.md`.

## Next Boundary Work

1. Repair the blind query-scope, response-contract, bounded-unknown/profile
   rendering, and write-value canonicalization layers without modifying the
   sealed pack or report.
2. Dogfood new paraphrases through direct API, real Workbench, restart, and
   rehydration before sealing a second untouched pack.
3. Defer physical package extraction until the second replication establishes
   that the five retained mechanisms are robust enough to expose as a stable
   contract.

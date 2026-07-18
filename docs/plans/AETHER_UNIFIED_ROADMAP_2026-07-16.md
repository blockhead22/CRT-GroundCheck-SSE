# Aether Unified Roadmap

**Status:** Canonical program roadmap

**Effective:** 2026-07-16

**Scope:** `D:\AI_round2\aether-core`, `D:\AI_round2\workbench`, supporting labs, and eventual Aeteros Core extraction

This document is the authority for what is complete, what is active, and what is
optional. Older roadmap, handoff, current-state, lab, and repair documents remain
useful as evidence and implementation history, but they do not independently set
the next priority.

## Product Direction

```text
Aether-for-Nick = daily proof loop and stress test
Aeteros Core    = reusable governed-memory and trace infrastructure
Product Aether  = Aeteros Core + user-owned memory + polished Workbench
```

The governing rule remains:

```text
Personalize the content. Generalize the mechanism.
```

Aether is not primarily a model. It is the governance layer around replaceable
models: evidence authority, memory review, contradiction handling, bounded
conversation context, route visibility, verification, repair/fallback, durable
trace, and reviewed learning.

## Current Program Position

```text
Foundation and archaeology                    COMPLETE
Governed Workbench proof loop                 COMPLETE AS A BASELINE
Conversation-control production repair        COMPLETE
Reusable Aeteros Core demo                    COMPLETE
Frozen comparative product evidence           COMPLETE
Core simplification and blinded replication   COMPLETE WITH LIMITS
Blind generalization repair and replication 2 COMPLETE WITH LIMITS
Persistence and product hardening             REOPENED BY LIVE CONTINUITY DOGFOOD
Governed cross-conversation continuity        ACTIVE
Desktop distribution readiness                PAUSED BEHIND CONTINUITY GATE
External pilots, grants, or company structure GATED
```

The project is no longer in open-ended archaeology, prompt tuning, model
shopping, or general conversation repair. The reusable boundary, clean-room
adapter, ninety-second demonstration, fitted comparison, and first
implementation-blind replication are now recorded. Two blind packs preserved a
narrow authority/control advantage with explicit limits, and the bounded
post-blind repair decision is closed. Profile isolation, truthful resume,
offline recovery, installation compatibility, and the Windows desktop
lifecycle are complete. A fresh two-conversation Workbench probe then showed
that persisted conversations are not available to the answer path across
threads and that same-thread referent use can still be accepted when
semantically wrong. Governed cross-conversation retrieval and explicit
continuity alignment are therefore the active product-hardening gate. Broad
answer-superiority claims remain unsupported.

## Completed and Parked Work

### Foundation and Workbench

- The Lumi/CRT/Aether archaeology pass identified the mechanisms worth carrying
  forward and the unsafe legacy behavior that must not be copied raw.
- The active product boundary is `aether-core` plus `workbench`.
- Evidence receipts, review-only candidates, contradiction handling, governed
  trace, repair/fallback, and no-write boundaries exist in the live system.

### Local Router, RAG Baseline, and Durable Trace

**Status:** Graduated as validation infrastructure.

- The local-router and meaning-compression work established a useful governed
  pipeline and serious scaffolded-RAG baseline.
- Answer and structured trace can be scored and replayed.
- This lane must not resume as loose prompt tuning or repeated raw-model
  comparison. Expand it only to answer a specific product-evidence question.

### Governed Learner / Mirus Review Loop

**Status:** Baseline complete and parked behind dogfood need.

- Recent traces can produce review-only Memory, Support, Reflection,
  Contradiction, and Evidence candidates.
- Workbench can show why a candidate exists and route it to the relevant review
  surface.
- Repeated candidates deduplicate.
- Reject and defer remain behaviorally inert.
- Nothing becomes durable guidance without operator approval.

Do not add more learner surfaces from theory. Resume this lane only for a
concrete review-queue, decision-adapter, or daily-use failure.

### Conversation-Control Repair Campaign

**Status:** Production reopen closed 2026-07-16.

The repair campaign's P0 and Phases 1-6 are complete. That phase numbering is
local to the repair plan and must not be confused with the program roadmap.

Final gates included:

- bounded accepted recent-conversation context;
- zero-evidence personal-claim containment;
- query-scoped relevant evidence;
- truthful response-contract verification;
- trace and completion-receipt agreement;
- live and rehydrated Workbench agreement;
- no unauthorized memory writes;
- no demonstrated need for a larger renderer.

Evidence: 1,347 backend tests passed with one intentional skip, 62 Workbench
component tests passed, 12 Electron tests passed, production build passed, and
held-out live UI/API/reload dogfood passed.

## Completed Milestone: Reusable Aeteros Core Demo

### Progress checkpoint — 2026-07-17

- Added an executable `aeteros.core.boundary.v0` manifest and persisted-trace
  auditor without splitting the package.
- Recorded the first explicit mechanism/product-adapter/Nick-layer inventory in
  `AETEROS_CORE_BOUNDARY_2026-07-17.md`.
- Proved one isolated synthetic lifecycle through review-only candidate,
  explicit confirmation, governed retrieval, completion receipts, service
  restart, and rehydrated Workbench UI.
- Fresh UI dogfood exposed two hedge-paraphrase failures; the repair generalized
  category-first and value-first declarative hedges while retaining question,
  hypothetical, and response-contract exclusion.
- Evidence: 212 focused/adjacent backend tests passed; direct API and Workbench
  agreed for turns `turn_21764ad27570`, `turn_35758b9d95ef`, and
  `turn_e25ec017b947`; the isolated state contained no scanned private markers.
- Added a persisted support-pattern decision slice: the real Workbench review
  drawer accepted one synthetic candidate, rejected one, and deferred one.
  After sidecar restart the UI rehydrated `1 accepted / 1 rejected / 1
  deferred`; live turn `turn_6d8e75097f71` released only
  `core_ui_accept_20260717a`, performed zero writes, and contained neither
  rejected nor deferred guidance in its governed packet or public answer.
- Evidence for that slice: 25 focused backend tests and 8 adjacent Workbench
  API/drawer tests passed. The in-app screenshot command closed its browser
  target after the DOM/status assertions passed, so a new PNG for this slice
  remains an artifact gap rather than being reported as a product failure.
- Proved synthetic contradiction review in a second isolated namespace. A
  fresh employment paraphrase first exposed a systemic query-scope/planner
  miss; after repair, the API and UI withheld both values, the real Memory
  drawer recorded a confirmed correction, later retrieval returned only the
  corrected value, and receipts survived another sidecar restart and UI reopen.
- The same dogfood slice exposed and repaired unchecked `only the company`
  wording plus a false high-stakes `company` route. Post-fix turns
  `turn_d33de4dcc766`, `turn_0e7f13361531`, `turn_3d6f7f02f8c3`, and
  `turn_9cfc4c6823de` agree across conflict withholding, route semantics,
  object-only verification, zero writes, and restart. The adjacent backend
  slice passed 198 tests; 12 adjacent Workbench memory/chat/API tests passed.
- Added an explicit `aether.product_adapter.v0` policy. The default
  `aether_personal` behavior remains enabled, while `aeteros_clean_room`
  disables private builder identity, relationship/character/project overlays,
  archive retrieval/provenance, and builder-demo personal synthesis at their
  execution boundaries. The selected adapter is visible in health and every
  persisted trace.
- A first adapter run correctly blocked new private overlays but exposed that
  the copied Workbench database still contained historical personal
  conversations. That state was rejected as evidence. The replacement state
  `state-clean-adapter-20260717-0143` copied only the synthetic substrate and
  began with zero conversations.
- Fresh API/UI dogfood then reopened and reclosed two narrow conversation
  defects: container pronouns such as `it contains` were mistaken for
  cross-turn references, and possessive entity-only wording such as `only its
  name` was not parsed or truthfully checked. Post-fix UI turns
  `turn_66b983c2f450` and `turn_11b40875bfce` are fully verified; API turns
  `turn_6c52d50164b4` and `turn_f36a41c6e0c0` agree. All clean-room Core audits
  pass, all probe turns wrote nothing, and the clean state contains no scanned
  private markers.
- Final hardening also made clean mode override demo-only personal synthesis and
  broadened the disabled-overlay boundary to archive plurals, maker/developer,
  and relationship variants. API turn `turn_670e7edf205c` and rehydrated UI
  turn `turn_69a3349db949` passed 4/4 with no private tool run or memory write;
  the reopened UI console was clean.
- The final adjacent regression slice passed 296 tests. The personal adapter
  remains the default, so existing Aether-for-Nick routes retain their prior
  behavior. A representative clean-room UI screenshot was saved as
  `artifacts/aeteros-core-demo/clean-room-adapter-ui-visible-2026-07-17.png`;
  later final-state capture attempts again closed the browser target, while DOM,
  API, trace, restart, and rehydration assertions completed.

This milestone is complete. The executable seam, clean adapter, synthetic
lifecycle, persisted review decisions, contradiction/correction flow, direct
API, real Workbench UI, restart, and rehydration gates now agree. This is a
boundary proof, not a package-extraction or superiority claim.

### Objective

Prove that the reusable mechanism survives removal of Nick-specific content.
The output is a small demonstrable governed-memory core inside the current repo,
not yet a separate repository or package.

### Required Work

1. **Define and enforce the layer boundary.**
   - Label Nick Layer, Workbench, Aeteros Core, and Research/Product Evidence.
   - Inventory direct Nick-specific assumptions in reusable paths.
   - Move mechanisms, not personal data, across the Core boundary.

2. **Stabilize the smallest reusable schemas.**
   - Evidence receipt.
   - Review candidate and decision record.
   - Structured trace event/packet.
   - Contradiction marker.
   - Authority and safety contract.
   - Extract only shapes proven at multiple live call sites.

3. **Create a clean demonstration profile.**
   - Use synthetic or explicitly source-bounded fixtures.
   - Do not copy private Nick memory into the reusable demo.
   - Demonstrate reviewed memory, contradiction, bounded conversation context,
     trace, rejected-candidate non-effect, and restart/reload behavior.

4. **Preserve the dogfood system.**
   - Existing Aether-for-Nick behavior must continue to pass focused and adjacent
     tests.
   - Core extraction must not weaken exact Continuity commands, ownership,
     no-write rules, rejected-draft isolation, or external-provider isolation.

### Exit Gate

This milestone is complete only when:

- the demo operates without Nick-specific facts or paths in its reusable layer;
- one governed memory lifecycle works end to end: evidence -> candidate -> review
  -> decision -> later bounded retrieval;
- rejected and deferred candidates provably do not affect later behavior;
- accepted conversation, trace, and completion receipts survive restart/reload;
- focused tests, full adjacent regressions, direct API checks, live Workbench UI,
  and rehydrated UI agree;
- no test fixture mutates the live personal memory substrate.

## Completed Milestone: Frozen Comparative Product Evidence

### Completion checkpoint - 2026-07-17

- Froze a 40-case synthetic pack with seed `20260717`, five cases each for
  authority, relevance, contradiction, memory-write control, recent context,
  response contracts, restart, and receipt/trace truthfulness.
- Used the same `qwen2.5:7b-instruct` renderer at temperature zero for a strong
  prompt-only baseline, ordinary lexical retrieval plus non-repairing
  postcheck, and the real clean-room Aether path.
- Final latest-code results were 20/40 prompt-only answers, 27/40
  retrieval-plus-postcheck answers, and 40/40 Aether answers with 40/40 Aether
  control receipts. Mean latencies were 0.581 s, 0.589 s, and 0.711 s. An
  earlier identical seeded post-repair run moved the baselines by one case in
  the opposite direction (21/40 and 26/40) while Aether remained 40/40 on both;
  the governed gate is repeat-stable, but renderer output is not byte-identical.
- Retained the pre-repair Aether result of 32/40 answers and 36/40 controls.
  Its failures exposed systemic pronoun-scope, bounded-unknown, generic
  response-contract, query-scope, literal-contract, and accepted-turn referent
  defects. Repairs generalized those layers without changing the frozen
  manifest, seed, or model.
- Dogfooded five representative turns through the real Workbench in an isolated
  clean-room namespace, inspected public answers, traces, write receipts, and
  stored conversations, restarted the sidecar, reloaded the UI, and recovered
  the same counted receipts. All five turns wrote nothing and the literal
  occupation contract did not enter the synthetic substrate or passages.
- The adjacent full regression and a fresh four-field Workbench compound then
  exposed two additional omission boundaries: mixed-status packets and
  unresolved personal clauses. Failed traces were retained. Final untouched
  turn `turn_c8a847a60266` covered a released employer, held studio conflict,
  provisional instrument, and missing flower with four verified answer jobs,
  zero writes, no escalation, and restart-persistent UI receipts.
- Final latest-code validation passed 1,384 backend tests with one intentional
  skip, 62 Workbench component tests, 12 Electron tests, and the Workbench
  production build. The rehydrated browser console contained no errors or
  warnings; isolated test services were stopped without touching the main
  5175/8765 Workbench services.
- Full evidence, turn IDs, screenshots, limitations, and the necessary-versus-
  ornamental mechanism assessment are recorded in
  `artifacts/aeteros-product-eval/RESULTS_2026-07-17.md`.

The milestone is complete as a reproducible product regression and comparative
mechanism demonstration. It is not an unbiased estimate of arbitrary future
prompts: the frozen pack exposed and informed repairs. The separately generated
implementation-blind pack described in the next milestone now supplies the
unbiased follow-up and materially narrows the public claim.

### Required Evidence

- A curated 30-50 case held-out pack with recorded seeds and provenance.
- Prompt-only, retrieval-only/scaffolded-RAG, and governed-pipeline baselines.
- Answer quality and trace quality scoring.
- Conversation continuity, evidence relevance, contradiction, response
  contracts, rejection non-effect, restart, and rehydration cases.
- Fresh UI dogfood prompts not used to fit the implementation.
- Frozen packet comparison before any larger-model shadow run.

### Exit Gate

- Governed behavior shows a material, reproducible improvement over the serious
  baselines.
- Claims are narrow enough to be supported by the evidence.
- Representative failures, repairs, and remaining limits are retained rather
  than hidden by aggregate scores.

## Completed Milestone: Core Simplification and Blinded Replication

### Completion checkpoint - 2026-07-17

- Retained the smallest measured Core contract: pre-render evidence status,
  authority and relevance; durable-write enforcement; accepted-only bounded
  recent context; explicit response-contract checking; and restart-persistent
  completion receipts.
- Kept broad Mirus discovery, belief-map previews, CRT migration signals,
  system self-tension, private character overlays, and always-visible model
  policy outside the reusable seam. The model-policy recommendation was removed
  from the default chat surface while remaining available in Trace and
  Settings.
- Built a repeatable synthetic clean-room demonstration. Its latest run
  completed in 5.361 seconds, released one confirmed fact, withheld one
  provisional value, preserved a contradiction, blocked an exact-literal
  profile write, changed no substrate bytes, and reopened all four accepted
  receipts.
- Before revealing the new pack, sealed the Git checkpoint, dirty-diff hash,
  Python tree, Workbench source tree, scorer, local-model digest, and seed. The
  newly generated 40-case pack used seed `20260719` and SHA-256
  `81e7fe44323ec647a9149400d893444b956c2b85175365f8a16d634a68df3a1a`.
  The implementation and scorer hashes were unchanged after scoring.
- The immutable blind result was 22/40 prompt-only answers, 28/40 ordinary
  retrieval-plus-postcheck answers, and 28/40 governed answers. Aether produced
  34/40 control receipts; the baselines implement none of the required
  authority/write/restart receipt schema. This is evidence for a narrow control
  claim, not answer superiority.
- The blind failures fall into query-scope/planner generalization,
  response-contract intent detection/repair, bounded-unknown language and
  profile over-rendering, plus write-value canonicalization. Several accepted
  receipts accompanied wrong public answers because semantic coverage was
  honestly marked unverified or the response contract was not detected.
- Full pre-reveal backend validation passed 1,398 tests with one intentional
  skip. The preceding Workbench validation passed 62 component tests, 12
  Electron tests, and the production build.
- Full seals, report, failure classification, limitations, and falsifiable
  thesis are in
  `artifacts/aeteros-blind-replication/RESULTS_2026-07-17.md`.

Use the completed comparison to reduce the reusable seam before expanding the
product:

1. Keep pre-render evidence release, write-authority enforcement, accepted-only
   recent context, response-contract checking, and durable completion receipts
   in the minimal Core contract.
2. Keep broad Mirus discovery, belief-map previews, CRT migration signals,
   system self-tension, private character overlays, and model-policy UI outside
   the Core unless a named product failure shows measurable value.
3. Build the ninety-second clean-room demonstration around one released fact,
   one withheld provisional value, one preserved contradiction, one blocked
   write, and one restart-persistent receipt.
4. Run a separately authored or externally administered blinded paraphrase pack
   without changing the implementation between reveal and scoring.
5. Use that result to prepare the narrow technical claim and product/research
   deck; do not broaden the claim to general answer superiority.

### Exit Gate

- the reusable Core seam is smaller or every retained mechanism has measured
  evidence for its inclusion;
- the ninety-second demonstration is repeatable from a clean install/state;
- an implementation-blind pack reproduces the authority/control advantage or
  transparently falsifies it;
- the public thesis, limitation language, and business/grant materials agree
  with the evidence.

This milestone is complete because the seam, demonstration, and immutable
blind result exist and the result is reported without repair contamination. It
does not close the newly exposed generalization failures.

## Completed Milestone: Blind Generalization Repair and Replication 2

Repair only the systemic layers exposed by the sealed blind result:

1. make personal query scope and planning robust across employer/workplace and
   current-project paraphrases without reopening broad personal retrieval;
2. generalize response-contract intent detection for digits-only, entity-only,
   pronoun-object, bounded-word, and conflict-plus-contract interactions;
3. make zero/provisional evidence produce a short bounded unknown without
   stronger-model escalation, and prevent profile lookups from rendering
   unrelated confirmed fields;
4. define and enforce canonical value normalization for authorized direct
   writes without weakening question/hypothetical/contract no-write rules;
5. preserve the first blind manifest and report unchanged, dogfood fresh
   paraphrases through API/UI/restart, and then seal a second newly seeded pack
   before revealing or scoring it.

### Exit Gate

- every first-pack failure has a layer-level classification and regression;
- focused tests, direct API, live Workbench, and rehydrated Workbench agree;
- no repair is fitted only to one exact prompt string;
- a second untouched pack materially improves control reliability and does not
  regress below ordinary retrieval on answer score;
- the public thesis remains the narrow authority/write/restart claim unless new
  evidence supports more.

This milestone completed on 2026-07-17. The repaired first blind pack reached
38/40 answers and 40/40 controls on Aether. A separately frozen second 40-case
pack (seed `20260731`) scored 21/40 prompt-only answers, 27/40 retrieval plus
nonrepairing-postcheck answers, and 33/40 Aether answers with 37/40 Aether
controls. Implementation, scorer, model digest, seed, manifest, and result
seals are recorded in
`artifacts/aeteros-blind-replication-2/RESULTS_2026-07-17.md`.

The result materially exceeds ordinary retrieval on answer score and retains a
large executable-control advantage, so the narrow thesis replicated. It did
not replicate perfectly: remaining failures are bare suffix contracts,
one-word status vocabulary, provisional-plus-one-word containment, and
`beverage` query scope. Do not repair those against the revealed pack without
preserving this result as the pre-repair snapshot.

## Completed Milestone: Post-Blind Decision Gate

1. Treat replication 2 as evidence, not a new training set. Decide explicitly
   whether the four remaining systemic categories justify a third repair slice
   before persistence/product hardening.
2. Convert the ninety-second demo, two blind snapshots, limitations, and
   falsifiable thesis into a short technical narrative suitable for skeptical
   engineering review, a pilot conversation, or grant discovery.
3. Keep package extraction and broad Mirus/synthesis/J-lens expansion paused.
4. If no named external opportunity needs the evidence package immediately,
   proceed to persistence and product hardening below.

### Exit Gate

- one explicit decision exists on repair slice 3 versus product hardening;
- the public evidence summary uses the sealed numbers and limitation language;
- no claim of general answer superiority or perfect control reliability is
  introduced;
- the next engineering milestone has a bounded owner, test gate, and artifact.

### Decision and evidence — 2026-07-17

The four remaining categories justified one bounded repair slice before product
hardening because they were all authority/relevance/contract boundary failures,
not cosmetic answer-quality misses. Repair Slice 3 was completed against fresh
non-held-out probes frozen before implementation (seed `20260807`) and the
real isolated Workbench. It repaired narrow beverage/preference scope, bare
entity/title suffix contracts, provisional or zero-evidence one-word unknowns,
and an ordinary-verb archive overlay false positive.

Evidence is recorded in
`artifacts/aeteros-repair-slice-3/RESULTS_2026-07-17.md`: 71 focused tests,
265 adjacent backend tests, 62 Vitest and 12 Electron tests, a successful
Workbench build, six fresh accepted API probes with zero writes, restart
receipt rehydration, and three fresh UI turns followed by a UI reload. The
second blind pack was not rerun or changed; it remains the immutable
pre-repair snapshot. This closes the decision gate without converting the
revealed pack into training data.

## Product Hardening: Completed Slices and Active Continuity Gate

Only after the reusable demo and evidence gates are credible:

- plans survive service restart;
- interrupted tasks can be resumed safely;
- cross-session epistemic state is reconstructed from accepted durable objects;
- multi-day goals and commitments remain inspectable and revocable;
- multi-user/profile scoping prevents memory crossover;
- installation, backup, migration, and recovery have documented paths;
- Workbench presents stable current and historical receipts without relying on
  developer-only fixtures.

### First bounded slice

Start with synthetic multi-profile isolation plus restart/resume receipt
rehydration: establish that accepted durable objects remain correctly scoped
across two profiles, service restart, and a reopened Workbench conversation.
The gate is focused and adjacent regressions, direct isolated API behavior,
actual isolated Workbench behavior, and rehydrated UI behavior agreeing with
zero cross-profile evidence or write leakage. Record the synthetic namespace,
turn/trace IDs, and screenshots. Do not reopen broad Mirus, synthesis,
J-lens, package extraction, or model-provider work for this slice.

#### Completed evidence — 2026-07-17

The initial profile-root isolation slice is complete. A validated startup
`profile_id` now selects an isolated `profiles/<id>` durable-state root;
synthetic Atlas and Birch profiles were proven unable to read each other's
conversation IDs or release each other's confirmed value. Both profile roots
preserved accepted completion receipts through sidecar restart and Workbench
reload. The live dogfood pass found and repaired one generic governed-memory
recall failure before closure; the fresh repaired UI response, traces, and
screenshots are recorded in
`artifacts/aeteros-persistence-slice-1/RESULTS_2026-07-17.md`.

This is a per-sidecar profile-root boundary, not multi-tenant runtime profile
selection or authentication.

#### Completed interrupted-resume evidence — 2026-07-17

The safe interrupted-task resume slice is complete. In a fresh synthetic Atlas
profile, a deliberately begun-but-never-completed turn remained partial with no
answer or completion receipt. The actual Workbench `/resume` control used an
explicit open loop to create one accepted deterministic, no-write completion
receipt. It persisted through an isolated sidecar restart and Workbench reload;
the resumed receipt rehydrated as `Checked 3/4`, while the original partial
turn truthfully remained `Checks unavailable`.

Dogfooding also found and repaired a TraceDrawer crash for continuity traces
that intentionally lack ordinary durable-memory planner packets. The repaired
drawer displayed the completed result, `3/4` coverage, blocked writes, and
completion verification without a new runtime exception. Evidence, exact turn
IDs, and the remaining truth boundary are in
`artifacts/aeteros-interrupted-resume-slice-1/RESULTS_2026-07-17.md`.

The next bounded persistence slice is explicit installation, backup, migration,
and recovery evidence using the same synthetic profile-root contract. It must
not infer user commitments from partial prompts or claim resumable long-running
tool/model execution until those execution checkpoints are separately built and
proven.

#### Completed offline backup/recovery evidence — 2026-07-17

The first explicit recovery contract is complete for a stopped/quiesced
synthetic profile. `aether.profile_backup.v1` captures the governed substrate,
optional passage store, and a SQLite-backup snapshot of the Workbench database
with a strict manifest, sizes, kinds, and SHA-256 hashes. Restore validates the
entire bundle before destination writes, requires explicit replacement, stages
beside the destination, and rolls back the old profile if activation fails.

The synthetic Atlas clean-room conversation and all four accepted completion
receipts survived bundle creation, restore into a fresh root, a new sidecar,
another sidecar restart, and actual Workbench reload. The UI rendered the same
counted receipts and opened the restored 5/5 trace with no console errors. The
contract-response text still produced zero occupation memory. Focused and
adjacent gates passed: 42 backend tests, 63 Vitest tests, 12 Electron tests, and
the Workbench production build. Fault tests cover corruption, incompatible
content and versions, incomplete/unsafe archives, identity mismatch, accidental
overwrite, and activation rollback. Exact hashes, turn IDs, limitations, and
the browser capture gap are recorded in
`artifacts/aeteros-profile-recovery-slice-1/RESULTS_2026-07-17.md`.

This closes offline backup and restore, not installation or general migration.
The next bounded slice is clean-install operation plus an explicit
compatibility matrix and migrate-or-refuse contract. Live cross-file capture
while the sidecar is writing remains unsupported in v1.

#### Completed Python install and compatibility evidence — 2026-07-17

The installed recovery path and compatibility policy are now proven. A fresh
`aether-core[mcp,graph]` virtual environment completed a synthetic
create/inspect/restore round trip and reopened the same substrate, conversation,
trace, and receipt. A separate fresh `aether-core[workbench]` environment
started the real sidecar under isolated profile `atlas`; health, clean-room
adapter, and profile-root files agreed.

The first clean-install attempt exposed and repaired an eager package import
that incorrectly required FastAPI for the standard-library-only backup path.
`aether profile-backup compatibility` now reports v1 as the only writable,
inspectable, and restorable format, no registered migrations, and fail-closed
refusal before destination writes for every unsupported version. Details and
timings are recorded in
`artifacts/aeteros-install-compatibility-slice-1/RESULTS_2026-07-17.md`.

This proves the installed Python Core, recovery CLI, optional Workbench HTTP
extra, and profile-scoped sidecar.

#### Completed Electron/NSIS desktop lifecycle evidence — 2026-07-17

The bounded Windows desktop packaging lifecycle is complete. Electron now
selects a bundled, fail-closed PyInstaller sidecar in packaged builds and keeps
durable state outside the application directory under Electron `userData`.
The package supplies explicit profile and API-port configuration without
workspace discovery or inherited `PYTHONPATH`. The NSIS uninstaller keeps
profile data by default and removes only Aether's state root when the user
explicitly selects removal; silent automation can request the same policy with
`AETHER_REMOVE_PROFILE_DATA=1`.

A fresh NSIS install created a synthetic Atlas profile, completed governed turn
`turn_1628aa1c1c42`, and stored its answer and completion receipt. Installing a
newer build preserved byte-identical profile files and reopened that receipt.
A silent uninstall preserved the profile; reinstall reopened it again; an
explicit remove-data uninstall deleted the isolated `aether-state` root. A
deliberately missing sidecar executable failed closed without modifying the
profile, after which the prior build reopened its accepted conversation. This
is proven manual prior-version recovery, not an automatic binary rollback
mechanism.

The final Windows x64 installer includes `aether-core` 0.15.0 with the
`workbench` and `graph` extras. All 63 Workbench component tests, 20 Electron
tests, and the production build passed. The packaged path, direct API, visible
production UI, receipt rehydration after reload, installer upgrade, and both
uninstall policies agreed. Exact package hashes, turn IDs, screenshots, and
limitations are recorded in
`artifacts/aether-desktop-packaging-2026-07-17/RESULTS.md`.

#### Active governed cross-conversation continuity gate - 2026-07-17

A fresh isolated clean-room Workbench probe falsified the assumption that
durable conversation storage was sufficient cross-session continuity. The UI
and database preserved both threads, but the answer path could not retrieve the
prior thread semantically or by exact conversation ID. The trace showed that
`ConversationContextPacket` remained correctly but narrowly scoped to
`same_conversation`; no cross-conversation retrieval packet or semantic tool
call existed.

The same probe exposed a prerequisite truthfulness defect. A same-thread
checkpoint question returned `123` instead of the user-authored `7319` and the
completion remained accepted with semantic referent use not deterministically
checked. A later, more explicit prompt recovered `Project Lattice Finch | 7319`
but unnecessarily requested a stronger model. Cross-thread requests correctly
failed their referent check, produced zero memory writes, and remained
unaccepted. Exact evidence IDs and the bounded implementation sequence are in
`AETHER_GOVERNED_CROSS_CONVERSATION_CONTINUITY_PLAN_2026-07-17.md`.

The first repair slice now proves Phases 0-4 end to end. Same-thread current,
previous, and first-message claims are deterministically checked. A separate
profile-scoped archive boundary retrieves prior conversations by exact ID,
title fragment, recency, and bounded semantic topic; excludes the current
conversation and rejected assistant output; exposes ambiguous candidates; and
never treats archived text as profile memory. Role-labeled archive packets and
durable alignment receipts carry source conversation/turn citations, status,
and zero-write evidence into the answer, trace, database, and Workbench.

Isolated live dogfood proved an exact-ID aligned destination, semantic
ambiguity plus explicit candidate choice, Workbench reload, sidecar restart,
and receipt rehydration. It also found and repaired a generic verifier defect:
`Do not save it` was incorrectly treated as a prior-turn reference even when
`it` had an antecedent inside the current prompt. The fresh repaired turn was
`Verified 5/5` with zero writes and no stronger-model escalation. The focused
and adjacent gates are `112` backend tests, `67` Workbench component tests,
`20` Electron tests, and a passing production build. Evidence is recorded in
`artifacts/browser/aether-cross-conversation-2026-07-17/RESULTS.md`.

The Phase 5 retrieval/alignment replication is now recorded. A separately
seeded 40-case pack was revealed only after implementation, scorer, generator,
Workbench, and local-model freezes. With no implementation changes before the
first snapshot, `39/40` passed (`97.5%`), including title/fragment,
temporal-latest, semantic, ambiguity, rejected/partial assistant,
cross-profile, response-contract, and restart families with zero writes and
zero profile slots. The single sealed failure exposed missing `yesterday`
routing, while its own source timestamp was also invalid because it had not
been backdated. The snapshot and fixture remain unchanged.

Post-snapshot repair now filters local-calendar yesterday, one ISO date, and
inclusive ISO date ranges by conversation creation time. Correct regressions
and live Workbench dogfood used a genuinely backdated source plus a same-day
distractor; the dated source was selected with an exact cited receipt,
`Verified 6/6`, zero writes, reload survival, and sidecar-restart survival. An
empty absolute date returned a bounded blocked alignment without falling
through to the model. Current gates are `116` backend tests, `67` Workbench
component tests, `20` Electron tests, and a passing production build. The
sealed pack and repair evidence are in
`artifacts/aether-cross-conversation-heldout-2026-07-17/RESULTS.md`.

The remaining continuity work is no longer generic archive retrieval. General
alignment still returns a bounded extractive snapshot. A specific
task/open-loop continuation packet and held-out task-state evaluation must
prove what executable state can be resumed without inferring commitments or
authority from old prose. Until that is proven, Aether can retrieve, cite, and
align a prior chat, but does not claim arbitrary cross-thread task execution
recovery.

This is conversation-archive retrieval, not broad profile RAG. Prior user
messages are authoritative evidence of what the user said, not automatic proof
that their contents are durable personal facts. Assistant responses remain
derived claims and must not outrank their cited user source. Retrieval must be
profile-scoped, provenance-carrying, bounded, and separate from governed
profile memory. The current same-conversation packet remains narrow and is not
silently expanded into a cross-session transcript dump.

Distribution readiness resumes only after the continuity gate passes focused
tests, direct API behavior, actual Workbench dogfood, sidecar restart, and UI
rehydration. Its queued work remains code signing and product metadata,
prerequisite detection/onboarding for Ollama and the selected local model, and
a deliberate update channel before automatic update/rollback. The current
package is unsigned, Windows x64 only, uses the default Electron icon, and
expects Ollama plus `qwen3:14b` to be installed and running.

Concurrent tools, deferred tool loading, multi-agent coordination, voice,
mobile, additional channels, and marketplaces are optional product extensions.
They do not outrank correctness, reusable boundaries, or persistence.

## Business, Grant, and Funding Gate

Formal company or grant work becomes timely when all of the following exist:

- a reusable Aeteros Core demo without private Nick-layer dependency;
- held-out evidence against prompt-only and retrieval-only baselines;
- a clear product/research deck with defensible claims;
- a named grant, pilot, collaborator, or customer opportunity that benefits
  from an entity.

The conversation-control closure is useful supporting evidence, but it does not
by itself satisfy this gate.

As of 2026-07-17, the reusable-demo and comparative-evidence conditions are
satisfied for a narrow enforcement claim. The blind pack tied ordinary
retrieval on answer score and reached 85% rather than 100% control coverage, so
any deck must state those limits and must not claim general answer superiority.
The remaining gates are that evidence-backed deck and a named opportunity that
benefits from forming an entity; an LLC or grant exploration remains plausible,
but is not an engineering priority by itself.

## Side-Lane Disposition

| Lane | Current disposition | Main-roadmap dependency |
|---|---|---|
| Governed synthesis / tension packets | Focused lab and narrow runtime slices complete; broad routing paused | Reopen only for a demonstrated synthesis failure or reusable-demo need |
| Mirus belief-map substrate | v0 lab complete; live product wiring not complete | A fixture-backed preview/advisory adapter may support the reusable demo |
| Global workspace behavioral probe | Track 1 green | Retain as research evidence; not blocking |
| J-lens activation work | Plumbing smoke complete; denser fit/scoring unfinished | Optional research; not blocking product work |
| Reasoning-model / dueling-rollercoaster comparison | Decision reached and parked | Use current routing lesson; do not resume model shopping |
| Archive archaeology | Parked | Reopen only for a named missing mechanism or source-bounded fixture |
| Broad conceptual route expansion | Intentionally incomplete | Requires live dogfood evidence before expansion |

An unfinished side lane is not automatically active work. Optional research may
remain unfinished indefinitely without blocking the product roadmap.

## Testing and Scheduler Policy

Testing is a gate attached to roadmap work, not a substitute for roadmap work.

For every implementation slice:

1. run focused unit/integration coverage;
2. run the relevant adjacent regressions;
3. exercise direct API behavior;
4. dogfood fresh seeded prompts in the actual Workbench UI;
5. inspect the public answer, completion receipt, trace, writes, and persisted
   conversation state;
6. reopen the conversation and verify rehydrated UI behavior;
7. record failures by system layer and repair systemic causes.

Do not run an indefinite scheduler whose only instruction is "keep testing."
When automation resumes, it should advance the governed cross-conversation
continuity plan while applying the dogfood gate to each slice. It must not skip
the same-thread truthfulness prerequisite or fit exact repairs to the recorded
probe wording. A separate regression-only scheduler is warranted only for a
bounded soak period or a named reliability question.

## Definition of Program Done

Aether is not done when every speculative feature or lab is exhausted. The
initial product program is done when:

- Aether is a dependable daily local assistant;
- Aeteros Core is demonstrably reusable without private personal content;
- memory and behavioral changes remain reviewed, attributable, and reversible;
- conversation, trace, and accepted durable state survive restart;
- an explicitly requested prior conversation can be retrieved, cited, and
  aligned into the current thread without becoming unreviewed profile memory;
- held-out evidence supports the public claims;
- another user can install, understand, and safely operate the product.

## Source Precedence

When documents disagree, use this order:

1. this unified roadmap;
2. a newer dated, explicitly scoped repair or acceptance document;
3. `AETHER_CURRENT_STATE.md` and the Workbench handoff for detailed checkpoints;
4. the June master plan for product thesis and layer split;
5. the root `ROADMAP.md` for historical pre-split implementation history;
6. individual lab side-roadmaps for their own evidence only.

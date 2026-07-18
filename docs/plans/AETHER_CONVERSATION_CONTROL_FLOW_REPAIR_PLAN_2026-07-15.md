# Aether Conversation Control-Flow Repair Plan

**Date:** 2026-07-15  
**Status:** Production reopen closed 2026-07-16 after held-out reused-conversation, zero-evidence, contract, trace, and rehydration gates passed  
**Active product boundary:** `D:\AI_round2\aether-core` + `D:\AI_round2\workbench`

## Objective

Repair ordinary conversation by simplifying control flow rather than adding more
phrase detectors, answer cards, or prompt-specific routes.

The target behavior is:

```text
User message
  -> exact command, tool, or write check
  -> bounded recent accepted conversation
  -> query-scoped relevant durable evidence
  -> one ordinary answer path
  -> route-appropriate verification
  -> one accepted answer
```

The model remains replaceable. It may render language and synthesis, but it does
not select truth, authorize evidence, mutate durable state, or decide that a
fluent draft is correct.

## Problem Statement

The 2026-07-15 general-conversation dogfood transcript demonstrated that several
working subsystems are connected through brittle control flow:

- ordinary `why` questions can be classified as governed personal synthesis;
- recent turns are stored, but the dominant RAG voice prompt does not receive
  them;
- special contextual phrases can continue a subject while ordinary references
  such as `that`, `which explanation`, or `again` cannot;
- lexical overlap can release an irrelevant personal passage into a general
  question;
- generic memory language such as `preference` or `what do you remember` can
  miss confirmed `favorite_*` passages;
- explicit presentation instructions can be missed by narrow wording parsers;
- `Governed` and `Checked` can mean that authority boundaries passed even when
  relevance, conversational reference, requested coverage, or answer quality
  failed.

The persistence substrate and exact typed lanes are not the primary failure.
The main fault is the sidecar layer between stored state and the renderer:
conversation assembly, routing, evidence relevance, and verification semantics.

## Production Reopen: Held-Out Reused-Conversation Failure

The prior completion claim was too broad. A later Workbench sequence reused
conversation `conv_2ce57cbe5987`, which already contained older accepted turns,
and exposed three failures that the automated and earlier dogfood gates did not
cover:

- `turn_e44f1529f414` answered only the personal-profile clause of a compound
  request and omitted `How do you remember things?`, while the completion
  receipt still reported `fully_verified=true` and `Verified 5/5`;
- `turn_6eddcb3c6bf5` correctly established that the first half of the prior
  question was `How do you remember things?`, but follow-up
  `turn_3f7dcddcf1d2` ignored that active discourse focus and jumped to an older
  retained `What status did you just give...` turn;
- correction turn `turn_f55329e1e090` produced a broadly reasonable answer but
  routed a system-architecture question through personal `memory_review` and
  set `needs_stronger_model=true` without a demonstrated renderer boundary.

The repair is reopened at the layer boundaries, not for phrase-specific fixes:

1. decompose compound requests into answer jobs before deterministic profile
   construction or rendering;
2. make requested-coverage verification compare all requested jobs with the
   final answer instead of treating a deterministic constructor as proof of
   semantic coverage;
3. retain an active discourse focus so an immediately established or quoted
   referent wins over older packet turns;
4. make explicit correction turns bind their quoted target and repair the prior
   unresolved reference;
5. route questions about how the system remembers through a system/meta path,
   without profile retrieval or unsupported stronger-model escalation;
6. dogfood both fresh and reused conversations with more than four earlier
   turns, then verify live UI, stored receipt, release trace, memory writes, and
   reload state agree.

## Architectural Separation

Three context types must remain distinct:

1. **Conversation context**
   - recent accepted user and assistant turns from the current conversation;
   - automatically available to ordinary conversation;
   - bounded by turn count or token budget;
   - excludes rejected drafts and hidden reasoning.
2. **Durable memory**
   - reviewed facts and passages that may survive sessions;
   - released only when relevant to the request;
   - retains source, authority, ownership, uncertainty, and contradiction state.
3. **Continuity state**
   - observed Workbench activity, Git state, and explicit project open loops;
   - remains read-only unless the user explicitly pins, completes, or defers an
     open loop;
   - exact commands remain the deterministic control path during this repair.

## Non-Goals

This work will not:

- expand Grok or any external renderer eligibility;
- enable natural-language Continuity routing;
- add another semantic phrase catalog;
- silently repair polluted substrate values;
- weaken ownership, evidence, write, or rejected-draft boundaries;
- use hidden chain-of-thought as durable context;
- replace exact Continuity commands or explicit open-loop actions;
- optimize exact expected prose for the dogfood transcript.

## Phase 1: Freeze the Failures

Create a bounded, multi-turn regression fixture from the observed failure
classes. Assertions describe behavioral properties rather than exact prose.

The initial pack covers only:

- ordinary general `why` questions staying out of personal/tension synthesis;
- follow-ups resolving against the prior accepted answer;
- explicit sentence and metaphor constraints being recognized;
- unrelated personal passages staying out of general project questions;
- generic preference/profile requests reaching confirmed stored preferences;
- exact memory and exact Continuity commands remaining valid controls.

Known failures are recorded as strict expected failures so the repository stays
runnable while an unexpected pass forces the test to be graduated into a normal
regression.

**Exit:** one versioned fixture, fixture-schema tests, passing control cases, and
strict expected-failure tests for every confirmed architectural defect. No
production behavior changes.

## P0: Contain Zero-Evidence Personal Inference

Before conversation-quality work, stop renderers from producing personal
health, psychology, motive, or biography claims when no relevant personal
evidence was released for the turn.

Requirements:

- the boundary is evidence-structural, not a catalog of diseases or phrases;
- system self-tension and character guidance cannot substitute for user-owned
  personal evidence;
- a missing-evidence response is bounded and does not speculate;
- general advice and world knowledge remain available when they do not claim
  private facts about the user;
- the final-answer verifier records whether personal evidence was required,
  present, and respected.

**Exit:** zero-evidence personal inference is deterministically withheld across
the frozen prompt and paraphrased variants, without breaking grounded personal
recall or ordinary general answers.

**Completed 2026-07-16:** the sidecar now builds and traces a structural
personal-evidence contract before personal inference or character rendering.
With zero released user evidence, system self-tension, character guidance, and
follow-up pressure such as `try harder` cannot authorize personal health,
psychology, motive, or biography claims. The deterministic boundary was verified
with 19 focused tests, 114 adjacent character/app/dogfood tests, and a 53-test
ownership, retrieval, governance-spine, response-contract, and Phase 1 slice.
The adjacent slice retains seven strict expected failures assigned to later
phases. A feature-disabled diagnostic confirmed the remaining broad-suite
failures are pre-existing and outside this P0 change; the full suite is not yet
claimed green.

**Production dogfood correction 2026-07-16:** green test suites did not establish
the production result. Live turn `turn_68e5915ddfba` parsed an interrogative plus
response contract as `user:occupation = only defensible status`, persisted it as
confirmed memory, and accepted the completion. The durable row was quarantined
under `aether-live-probe-cleanup-20260716-occupation`.

The repaired persistence boundary now classifies leading interrogatives,
hypothetical frames, unresolved referential assertions, and response-contract
instructions as non-assertive unless a separate explicit first-person
declaration supplies write authority. The app passes that receipt into the
actual persistence function. Completion authority independently fails if a
write appears without an allowed direct-user-assertion receipt.

Evidence for this slice: 95 focused ingestion/app/completion tests and 84
adjacent route, evidence, conversation, contract, and Phase 1 tests pass. Live
API turns `turn_cdc351848280` and `turn_39f1f93e6273`, plus Workbench turns
`turn_9bd903cecad7` and `turn_8fb6adcffaf3`, produced zero memory writes. The
quarantined occupation slot remains without a current value. This closes only
the write-authority leak; the same Workbench run reproduced a missed yes/no
contract, irrelevant evidence on the first unknown answer, and missing stored
verification badges after reload, so later phase completion claims remain
behind the production dogfood gate.

**Production dogfood closure for the zero-evidence floor (2026-07-16):**
specific unknown-preference questions no longer fall through to sibling profile
values merely because one generic token overlaps. Status-shaped favorite
questions now discover the unknown slot, `unconfirmed` alone no longer selects
the meta/governance renderer, and the bounded answer is `Unknown.` Stale
slot-derived passages are reconciled against current substrate states during
hydration, so quarantined or superseded states cannot remain available through
RAG. The cleanup is limited to traceable `user:` slot projections and does not
delete chat/document passages or the substrate audit history.

Direct API turn `turn_2f334b431e3d` and fresh Workbench turn
`turn_3a6863ffb164` both returned `Unknown.` locally with zero released evidence,
zero memory writes, no stronger-model request, and a fully verified 4/4 receipt.
The Workbench result remained identical after a real reload. Both stale passage
references for the quarantined occupation state are absent. The focused
relevance/ingestion/app slice passes 138 tests, the adjacent route/evidence/
conversation/contract/Phase 1 slice passes 84 tests, and no test prompt created
new live personal state.

## Phase 2: Make Conversation Context an Invariant

Every ordinary renderer receives a `ConversationContextPacket` containing
bounded recent accepted turns from the current conversation. The invariant is
packet construction and attachment, not a particular model transport API.

Requirements:

- same conversation only, with the current turn excluded;
- both `user_message` and `local_answer` must be nonempty after trimming;
- `completed_at` is necessary but insufficient: an accepted turn also requires
  a trace completion receipt with a nonempty final source;
- `needs_stronger_model=True` remains eligible when that successful completion
  receipt exists, because the flag is a quality/escalation signal rather than
  an acceptance status;
- exception-path partial streams, rejected/repair drafts, traces, and raw
  reasoning are excluded;
- retain at most four completed pairs, budget newest to oldest, then emit the
  retained turns in chronological order;
- history is explicitly labeled referent-only conversation context, never
  durable memory or released personal evidence;
- follow-up resolution uses this packet rather than a growing phrase list.

Phase 2 uses a clearly delimited role-labeled section in the existing
`/api/generate` prompt contracts for voice and hybrid renderers. It must remain
separate from owner-labeled memory, evidence lines, the governance spine, and
the current user request. Native `/api/chat` may be evaluated later behind the
same packet boundary, but is not a Phase 2 correctness gate.

The useful historical reference is the role-aware path in
`D:\AI_round2\routes\chat_old.py` and
`D:\AI_round2\personal_agent\reasoning.py`. The archived Lumi/CogniForge cores
used retrieved prompt strings rather than dependable session-turn chat and are
negative controls, not code to port. The old `recent_queries` path also replayed
nonempty stored responses rather than enforcing Workbench-style acceptance, so
its storage semantics are not adopted.

Special contextual routes should no longer be required merely to understand
`why`, `again`, `which explanation`, `what did I ask`, or a disagreement about
the immediately prior answer.

**Exit:** the frozen follow-up sequence resolves correctly without false claims
that conversation history is unavailable; history cannot become personal
evidence; disabling packet attachment restores the prior renderer behavior.

**Completed 2026-07-16:** one typed packet builder now owns acceptance,
same-conversation/current-turn filtering, the final completion-receipt rule,
newest-first character budgeting, four-pair retention, and chronological
emission. The packet is traced and serialized as a separate referent-only block
for voice, hybrid, and fallback local renderers; raw turn rows, trace internals,
reasoning, and rejected repair drafts cannot enter that block. A completed row
without a final receipt is rejected, while a receipted
`needs_stronger_model=True` turn remains eligible. The Phase 1 follow-up xfail
was promoted, and an existing bare-retry regression also passes only when the
packet is enabled. Focused/adjacent slices produced 43 and 56 passes
respectively, with the same six strict expected failures assigned to Phases
3–5. A broader app diagnostic reproduced all eleven remaining failures with the
packet disabled, establishing them as pre-existing rather than Phase 2
regressions.

## Phase 3: Remove Route-First Behavior from Ordinary Questions

Reduce the live control plane to:

1. exact commands and explicit actions;
2. authorized tool or workspace operations;
3. ordinary evidence-aware conversation.

Words such as `why`, `meaning`, or `project` do not by themselves select a
specialized answer renderer. Hybrid synthesis requires actual released personal
meaning or tension evidence. Character guidance may constrain an already chosen
answer job, but should not compete with ordinary conversation for generic turns.

**Exit:** ordinary world, technical, project-management, and contextual `why`
questions stay on the ordinary path; existing exact controls still win.

**Completed 2026-07-16:** query-only synthesis classification now recognizes
explicit competing-claim structure and governed personal-meaning requests, not
ordinary words such as `why`, `meaning`, `how do`, `governance`, or
`uncertainty`. The route policy still honors an earned tension packet. Two
additional app-level keyword-forcing blocks and the direct-answer wipe were
removed, leaving one selection decision instead of three competing promotions.
The physics, project, and bare-`why` strict xfails were promoted to normal
regressions; bare `why` uses the Phase 2 packet without entering hybrid mode.
The full character/route/P0 adjacent slice passes 149 tests with the remaining
three strict expected failures assigned to Phases 4 and 5. The broader app suite
retains the same eleven pre-existing failures observed before this phase.

## Phase 4: Add Evidence-Relevance Authority

Separate permission from relevance:

- general questions receive no personal memory by default;
- a personal request may declare the memory categories it needs;
- a single shared token is insufficient to release a personal passage;
- every released item has a trace-visible relevance reason;
- generic profile inventory uses governed slot/profile state rather than hoping
  lexical retrieval maps `preference` to `favorite_*`;
- query-scoped synthesis receives only requested or directly supporting atoms.

Polluted durable values remain review work and are not silently changed here.

**Exit:** the frozen general-project question releases no embedding-dimension
memory, while generic and exact preference questions can reach confirmed values.

**Completed 2026-07-16:** a shared query-evidence scope now separates general,
personal-specific, generic-preference, and governed profile-inventory requests.
Personal passages require a trace-visible category/value relevance reason;
general questions reject personal memory, and one generic shared token is not
enough. The same scope filters retrieval, the context bridge, and the P0
personal-evidence count. Profile inventory reads governed slot state directly,
compound `favorite color + who am I` returns only name and color, and supporting
reason atoms require both the requested category and reason/meaning language.
Known polluted occupation/drink values are withheld (or clean coexisting values
are retained individually) without modifying durable storage. The two Phase 4
strict xfails were promoted. The broad character/profile/retrieval/P0 slice
passes 180 tests with only the Phase 5 contract xfail remaining; two known
pre-existing voice-prompt shape tests were excluded from that evidence slice.

**Production dogfood confirmation 2026-07-16:** retrieval now rejects a sibling
structured profile slot for a specific unknown preference even when a generic
token overlaps. The same gate runs before rendering, not merely as a late
verifier warning. API turn `turn_2f334b431e3d` and UI/reload turn
`turn_3a6863ffb164` released zero hits and did not enter governed synthesis or
request a larger renderer. Hydration also removed the two stale projections of
the quarantined occupation state while preserving its substrate audit record.

## Phase 5: Align Verification and Public Trace Semantics

Replace the single ambiguous idea of `Checked` with explicit dimensions:

- authority boundary;
- evidence relevance;
- requested coverage;
- conversational reference resolution;
- response-contract compliance;
- speaker ownership;
- repair and fallback status.

Hard presentation constraints use deterministic final-answer checks. Natural
variants such as `in exactly two sentences` and `no metaphors` must be recognized
without becoming semantic routes.

**Exit:** public trace language states precisely what was checked, and accepted
answers satisfy every hard contract applicable to their route.

**Completed 2026-07-16:** completion traces now publish seven independent
dimensions with `passed`, `failed`, `not_checked`, or `not_applicable` status.
Ordinary model prose is explicitly not described as semantically verified when
no deterministic coverage verifier exists. Workbench replaced its blanket
`Checked` label with counted `Checked n/m`, `Verified n/m`, or flagged status,
and the trace drawer exposes every dimension. Query-scoped evidence relevance,
speaker ownership, personal-claim containment, response contracts, and
repair/fallback receipts are audited separately. Model-added user biography is
buffered, repaired once from owner-labeled evidence, and replaced by a safe
fallback if still unsupported. Restricted-value leaks are also buffered and
replaced before release. Deterministic answer paths now pass through the same
hard presentation-contract gate. Natural `exactly N sentences` and `with no
metaphors` variants are extracted and the strict Phase 1 xfail was promoted.
The focused/adjacent backend slice passes 206 tests; its only two failures are
the same pre-existing voice-prompt-shape expectations recorded after Phase 4.
Workbench component tests pass 22 tests and the production TypeScript/Vite build
passes.

**Production dogfood correction 2026-07-16:** the live event path had a final
verification receipt, but `/v1/conversations/{id}/turns` did not return it, so a
real Workbench reload replaced counted verification with `Checks unavailable`.
Conversation-turn rehydration now returns the stored
`completion.verification_summary`, and Workbench uses that persisted receipt
when no live trace is cached. Pre-fix turns `turn_1aa4a22972d7` and
`turn_a156965c005a` now reload as `Verified 4/4` and `Checked 3/5`. Fresh turn
`turn_3a6863ffb164` remained `Verified 4/4` after a real reload, and its
rehydrated receipt exactly matches the trace receipt. Nine backend rehydration
tests and six ChatPanel tests pass, and the Workbench production build succeeds.
Natural yes/no, one-word, object-only, number-only, exact-list, and exact-word
contract coverage remains behind the live gate; this receipt repair does not
close those semantics.

**Production contract/reference closure 2026-07-16:** the response contract now
represents exact word counts plus yes/no, number-only, object-only, and
comma-list/list-only answer shapes. Every active shape is checked against the
final public answer. One bounded local exact-word rescue is permitted; a
contract-only failure remains rejected and cannot request a larger renderer.
Unknown profile-status polarity is deterministic (`No` for absent positive
status, `Yes` for explicit unknown/absent status) rather than delegated to
wording repair.

The reference verifier now separates prompt-local relative/pronominal use from
cross-turn references. Exact prior-answer echoes such as `what answer/status did
you just give` are checked against the last accepted assistant answer. Broader
transformations may remain honestly `not_checked`; they are never labeled
verified merely because a packet existed. Verifier-rejected completions are
excluded from later `ConversationContextPacket`s even when they have a final
source receipt.

Held-out production evidence includes API yes/no/one-word turns
`turn_ebf4311f2680` and `turn_4db57e4fbbeb`, exact-word turn
`turn_12e5d73e1b66`, number-only turn `turn_094bdfb0fa1e`, Workbench/reload
yes/no turns `turn_72e28bd3505d` and `turn_2937db59486f`, and Workbench/reload
object/list turns `turn_fc02b66247ff` and `turn_234ccf059fa8`. All contract
checks passed, all inspected writes/hits were zero, and no turn requested a
larger model. The focused/adjacent gate passes 248 tests.

Top-level trace semantics now describe the final turn rather than reusing an
inapplicable memory-slot planner result. Final traces publish `completed` or
`rejected` result state and completion-verification coverage. The durable-memory
planner remains namespaced with its original raw coverage and an explicit
applicability flag. Accepted UI/reload turn `turn_24c42acab8b7` persists
`completed` with 4 passed/0 failed dimensions and a non-applicable planner.
Deliberately contradictory contract turn `turn_fab11a4b056c` persists
`rejected`; follow-up `turn_611fdaf5dc2d` excludes it from context. None of
these turns wrote memory or requested a larger renderer.

## Phase 6: Controlled System-Level Retest

Testing continues throughout Phases 1-5 on the frozen pack. Phase 6 is the broad
held-out evaluation after the architecture is stable:

1. rerun the original transcript unchanged;
2. run unseen paraphrases of the same behavioral jobs;
3. run longer natural conversations and ambiguous follow-ups;
4. relaunch Workbench and test cross-session durable memory;
5. exercise `/resume -> Pin -> relaunch -> /resume -> Done/Defer`;
6. if frozen correct packets demonstrate a genuine local renderer-capability
   boundary, run those identical packets through the larger renderer in shadow;
7. rerun exact recall, ownership, no-write, and Continuity regressions.

Renderer interpretation:

- all renderers fail: packet or verifier problem;
- frontier passes while local fails: renderer-capability boundary;
- intended packet is never built: orchestration problem;
- irrelevant evidence enters the packet: retrieval/relevance problem.

No provider expansion occurs during this phase. A larger renderer is not used
merely to improve prose or mask a packet, routing, relevance, or verifier defect.

**Completed 2026-07-16:** the controlled evaluator runs in an isolated temporary
sidecar, Git workspace, substrate, passage store, and database while calling the
real local `qwen2.5:7b-instruct` renderer. It replays the original nine-turn
transcript, seeded unseen paraphrases and ambiguous follow-ups, governed profile
and preference queries, hard response contracts, exact Continuity controls,
process relaunch, durable recall, cross-relaunch conversation context, and an
explicit open-loop create/resume/complete lifecycle. It fingerprints the
temporary substrate and checks memory, reflection, document, and support tables
so evaluation data cannot become live memory.

The first diagnostic run passed all 25 behavioral cases but exposed one
unauthorized reflection candidate from the negated stance `I'm not convinced`
and one false larger-model signal on a receipted `say that again` follow-up.
Negated conversational stances are now excluded from affirmative
self-description capture, and referential retry escalation now honors an
accepted `ConversationContextPacket`. The identical seed then passed 25/25 with
zero failed checks. Independent seeds `20260717` and `20260719` also passed
25/25 with zero failed checks; the latter ran after the ordinary prompt boundary
was consolidated so route, tool, depth, ingestion, context-bridge, and
review-candidate controls can no longer be discarded by selecting the normal
voice renderer.

The closing backend run is fully green: 1,335 passed, 1 intentionally skipped.
Workbench passes 61 component tests and 12 Electron tests, and the production
TypeScript/Vite build succeeds. The final system report is
`D:\AI_round2\artifacts\phase6\conversation_control_flow_20260718_20260716_113001.json`.
No frozen correct packet demonstrated a local renderer-capability boundary, so
the larger renderer shadow comparison was correctly not run.

**Final production dogfood closure 2026-07-16:** fresh Workbench wording found
three residual phrase-family faults after the earlier automated pass:
`return the object ... and nothing else` did not activate object-only checking;
`repeat ... as a comma-separated list only` did not activate list-only checking;
and `my last/previous message` was misread as a personal-memory lookup, producing
an internally contradictory stronger-model banner. Contract verbs and terminal
`nothing else` forms are now extracted, cross-turn message referents are
classified explicitly, and accepted referent packets suppress false renderer
escalation. The actual profile-write gate now opens only for an extractable
direct/contextual fact, correction, or explicit open belief/meaning claim;
ordinary commands remain route-write-disabled.

Pre-fix UI turns were `turn_cf57a4a1acba` and `turn_1ee4ae7e680c`. Post-fix
turns `turn_fbc1aeeb8555` and `turn_bdf973421493` returned `pine token` and the
exact four-item order, passed object/list contracts, retained accepted context,
requested no larger model, and recorded zero evidence hits and zero writes.
Workbench displayed the same counted receipts after reload with no browser
warnings. Independent local-only seeds `20260717` and `20260718` each passed
25/25 with zero failed checks.

**Production reopen closure 2026-07-16:** reused-conversation seed
`20260716-ccf-reopen-03` reproduced the reported compound omission, active-focus
drift, and system-memory correction route, then continued with new zero-evidence
and temporary-object wording. The repair now:

- constructs and verifies independent deterministic answer jobs for compound
  system-memory plus profile requests;
- binds ordinal focus and explicit quoted corrections before routing;
- routes structural memory questions through deterministic system/meta rather
  than personal memory review or escalation;
- derives zero-evidence yes/no truth from the interrogative predicate rather
  than response-contract prefaces;
- derives a bounded one-word status from the prior accepted yes/no turn;
- recognizes label-only and natural comma-separation contracts;
- verifies transformed status and ordered-list referents against accepted prior
  turns; and
- renders completion coverage, planner applicability, and final result from the
  correct top-level trace receipts.

Representative final live evidence is compound turn `turn_a2fd368ca486`,
correction turn `turn_ef6a563d5737`, zero-evidence/status turns
`turn_5bfd949c8f0b` and `turn_bc7303788362`, and object/order turns
`turn_445a1c132caa` and `turn_45fd1611e5c1`. All inspected turns recorded zero
memory writes and no larger-model request. The live substrate revision remained
`bdbfc39893a18c00aa52c514f7df65209f4bd4f375255c3dc9569dbdfd68a192`
with 10 slots/26 states; the held-out favorite slot remains absent. Workbench
reload preserved public answers and counted receipts, and the browser console
reported no warnings or errors.

The final gates pass 183 focused/adjacent backend tests, 1,347 full backend
tests with one intentional skip, 62 Workbench component tests, 12 Electron
tests, and the production TypeScript/Vite build. No correct frozen packet
demonstrated a renderer-capability boundary, so no larger model was used.

## Acceptance Criteria

- Zero false claims that prior accepted turns are unavailable within one
  conversation.
- Zero unrelated personal-memory release on the frozen general-question pack.
- Ordinary `why` questions do not enter hybrid/tension synthesis without earned
  evidence.
- Hard response constraints pass deterministically.
- Generic preference/profile questions reach existing confirmed facts.
- Exact memory recall and `/where`, `/changed`, `/next`, `/resume` remain intact.
- Zero ownership inversion, automatic durable writes, or rejected-draft release.
- The number of special phrase-driven answer claimants decreases rather than
  increasing.

## Work Order

1. Freeze the bounded transcript fixture and expected-failure baseline.
2. Contain zero-evidence personal inference.
3. Build the accepted-turn `ConversationContextPacket` and attach its serialized,
   referent-only form to voice and hybrid renderers.
4. Remove bare-`why` hybrid forcing.
5. Add personal-evidence relevance gating and governed profile inventory.
6. Repair public response-contract extraction and verification.
7. Make trace/UI check labels truthful.
8. Run the controlled Phase 6 evaluation, escalating only at a demonstrated
   local renderer boundary.

## Stop Conditions

Stop and reassess if a proposed repair:

- adds prompt-specific answer text;
- adds another phrase catalog to obtain conversational continuity;
- grants a renderer evidence or route authority;
- requires durable writes for ordinary conversation;
- weakens exact Continuity, ownership, or rejected-draft boundaries;
- passes only the frozen wording and fails simple paraphrases.

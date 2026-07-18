# Aether Conversation Control-Flow Working Bug List

**Opened:** 2026-07-15  
**Status:** Production reopen closed; CCF-023 through CCF-030 were reopened and reclosed by clean-room evaluation, adjacent regression, and fresh UI dogfood on 2026-07-17  
**Related plan:** `AETHER_CONVERSATION_CONTROL_FLOW_REPAIR_PLAN_2026-07-15.md`  
**Source run:** Workbench transcript beginning with `What is my favorite color and who am I?`

This list records confirmed problems that are outside the active Phase 2 task of
making recent accepted conversation available to the ordinary answer path. It is
a working diagnostic list, not permission to change production behavior or
silently repair durable memory.

## Phase 2 Finding Excluded from This Backlog

The follow-up `what about provenance? compared to my color?` lost the prior
system-and-drink explanation and interpreted the request as a comparison with
another color's provenance. This is directly covered by Phase 2 conversation
context and reference resolution, so it is not duplicated as a separate bug
below.

**Status:** Fixed in Phase 2 (2026-07-16).

The ordinary voice, hybrid, and fallback model paths now receive the same
accepted-turn `ConversationContextPacket`. The frozen follow-up prompt contains
the prior accepted answer, excludes the current request from the history block,
and traces the non-evidence contract. The same acceptance boundary also repaired
the existing bare-retry regression. Completed exception partials without a
final completion source remain excluded.

## Active Bugs Outside Phase 2

### CCF-001 — Compound user identity request expands into a full profile dossier

**Phase:** 3/4 — route simplification and evidence relevance  
**Severity:** High  
**Status:** Fixed in Phase 4

Prompt:

```text
What is my favorite color and who am I?
```

Observed:

- route selected `memory_review` with a deterministic direct answer;
- the answer included name and favorite color, but also drinks, flower, snack,
  sports team, color reason, employer, occupation, and project embedding
  dimension;
- unrelated polluted values became user-visible.

Expected:

- answer only the requested identity/name and favorite-color atoms;
- do not treat `who am I` as permission to dump every stored profile slot;
- unrelated or polluted values remain outside the answer.

Resolution (2026-07-16): `who am I` is a requested name atom rather than a
profile-inventory grant. The compound prompt now returns only governed name and
favorite-color values; unrelated embedding and polluted occupation slots are
absent from both the scoped bridge and final answer.

### CCF-002 — Favorite-category retrieval releases unrelated profile evidence

**Phase:** 4 — evidence relevance  
**Severity:** High  
**Status:** Fixed in Phase 4

Prompt:

```text
can you explain what this system is and why it matters using what my favorite drink is as an example?
```

Observed evidence pack:

- both favorite-drink passages;
- favorite color;
- favorite snack;
- favorite flower;
- favorite-color reason;
- favorite sports team.

The answer then imported orange and leukemia-awareness context even though the
request selected favorite drink as the example.

Expected:

- release only the requested favorite-drink atoms plus fixed system architecture
  atoms needed for the explanation;
- other `favorite_*` slots do not become relevant merely because they share the
  word `favorite`.

Resolution (2026-07-16): retrieval and the governed profile bridge now use the
same category scope. The drink prompt releases only `user:favorite_drink`, and
every released item includes a trace-visible relevance reason.

### CCF-003 — Renderer invents personal drink ritual and sensory biography

**Phase:** 4/5 — evidence relevance and semantic verification  
**Severity:** High  
**Status:** Fixed in Phase 5; Phase 4 input relevance remains covered

The system-and-drink answer invented details not present in released evidence,
including carefully balanced iced coffee, cream, roast, cup-holding ritual,
daily fit, melting ice, separation, and personal experiential meaning.

Expected:

- stored preference supports only the proposition that iced coffee is one
  confirmed/coexisting favorite drink;
- generic facts about iced coffee must not be presented as the user's ritual,
  taste, experience, or personal symbolism;
- unsupported personal decoration fails verification rather than appearing as
  accepted Aether speech.

Resolution evidence: a route-independent personal-claim guard now examines
model prose against released owner-labeled evidence, catches new user
predicates, possessions, routines, private experience, and unsupported
symbolism, then performs one bounded repair and a safe fallback. The adversarial
drink regression introduces a daily ritual and cup-balancing claim; neither is
released, while the confirmed drink proposition remains. The guard is also
rechecked for speaker inversion after repair so a repair cannot reintroduce an
`I/my` ownership error.

### CCF-004 — System self-tension produces unsupported user health psychology

**Phase:** 3/4 — route simplification and evidence ownership  
**Severity:** Critical  
**Status:** Fixed at P0; retain as a Phase 4 relevance regression

Prompt:

```text
Why do you think epistemic integrity is important to me?
```

Trace state:

- selected route: `governed_synthesis`;
- guidance kind: `self_tension_drive`;
- render mode: `hybrid_governed_tension`;
- released memory passages: 0;
- answerable spine packets: 0.

Despite zero released personal evidence, the answer asserted fragmented health
memory, body/mind negotiation, recurring psychological patterns, health-data
review needs, and risk of being consumed by the issue.

Expected:

- system self-tension never becomes evidence about the user's psychology,
  health experience, motives, or personal narrative;
- with no released personal evidence, the system asks for grounding or clearly
  labels a bounded general inference;
- bare `why` and `important to me` wording do not authorize health narrative.

Resolution evidence (2026-07-16):

- a structural personal-evidence contract now records whether personal evidence
  is required, how much released user evidence is present, and whether rendering
  must be blocked;
- system self-tension, character guidance, review candidates, and conversation
  history are explicitly not counted as user evidence;
- the exact prompt and paraphrased personal-inference variants now return a
  bounded no-evidence answer without calling the renderer or writing memory;
- `What pattern do you think hurts me?` followed by `try harder` remains bounded
  on both turns, closing the character-repair bypass;
- 19 focused tests, 114 adjacent app/character/dogfood tests, and a 53-test
  governance/ownership/Phase 1 slice pass. Seven strict expected failures remain
  assigned to later phases.

Phase 4 must still make nonzero personal evidence query-relevant; P0 establishes
the zero-evidence floor and does not claim that any arbitrary user fact is enough
to support any personal inference.

### CCF-005 — Governance compliance and `Checked` state accept unsupported prose

**Phase:** 5 — verification and public trace semantics  
**Severity:** High  
**Status:** Fixed in Phase 5

The zero-evidence health narrative and broad personal-drink invention both ended
as `Governed` and `Checked`. The current compliance result established that
writes and restricted-boundary rules passed, but did not establish relevance,
support, requested coverage, or personal-claim grounding.

Expected:

- public trace distinguishes authority checks from relevance and semantic
  support checks;
- unsupported personal claims prevent a fully checked/accepted status;
- `Checked` is not shown as a blanket quality or factuality verdict when only
  the safety boundary was evaluated.

Resolution evidence: `aether.completion_verification.v0` reports authority,
relevance, requested coverage, conversational reference resolution, response
contract, speaker ownership, and repair/fallback independently. Unperformed
semantic checks are `not_checked`, not silently green. Workbench renders counted
or flagged receipts instead of a universal `Checked`. Deterministic and model
paths both save final response-contract receipts; unsupported personal prose and
restricted-value leaks remain buffered until repaired or replaced.

### CCF-006 — Polluted durable values are exposed without containment

**Phase:** Data review plus Phase 4 response containment  
**Severity:** High  
**Status:** Response containment fixed; explicit user review still required before mutation

Observed values include:

- `user:occupation = biggest flaw`;
- malformed favorite-drink fragments including `and Dr. Pepper` and
  `a problem. Dr. Pepper`.

Expected:

- do not silently rewrite or delete durable records;
- query-scoped answers should not expose unrelated polluted slots;
- a later explicit review flow should show source, current value, proposed
  correction, and the effect of confirmation or rejection.

Containment evidence (2026-07-16): polluted values are rejected from retrieval,
scoped profile summaries, exact lookups, and broad inventory answers. Clean
coexisting values in the same slot remain usable. Tests verify the stored
polluted value is unchanged.

### CCF-007 — Ordinary voice selection discards the governed answer job

**Phase:** 6 adjacent-regression audit  
**Severity:** High  
**Status:** Fixed in Phase 6

The compact model-as-voice prompt carried query-scoped memory but omitted
already-decided route policy, tool receipts, response depth, ingestion boundary,
context bridge, review-only candidates, and voice settings. Selecting the
ordinary renderer could therefore erase controls without changing the trace.
It also caused compound profile-plus-project or profile-plus-support questions
to collapse into a deterministic profile/empty-memory card.

Resolution evidence: the ordinary voice branch now uses the same complete
governed local answer job as the fallback path, with the accepted-turn packet
still serialized as a separate referent-only block. Experimental governed Mirus
candidates remain trace/review material on ordinary turns and enter synthesis
only through an earned tension job. Compound inventory questions defer when a
second project/support job is present. Extra discovery candidates no longer
suppress a unique active favorite-slot candidate. System-only prompts use
generic user-ownership wording and receive no user profile values. The full
backend suite and final seeded local-model evaluation pass.

### CCF-008 — Phase 6 lifecycle noise writes reflection and falsely requests escalation

**Phase:** 6 system evaluation  
**Severity:** High  
**Status:** Fixed in Phase 6

The original transcript's `I'm not convinced` turn was parsed as an affirmative
self-description and created a review reflection. Separately, `say that again`
could set `needs_stronger_model=True` even when a successful prior completion
receipt was present in the accepted conversation packet.

Resolution evidence: normalized self-description labels beginning with `not `
are treated as negated conversational stances rather than identity claims.
Escalation checks now accept the bounded conversation packet and do not escalate
a referential retry when that packet resolves it. Identical-seed replay and two
independent held-out seeds pass with zero reflection writes, zero failed checks,
and no larger-model requirement.

### CCF-009 — Interrogative plus response contract persists confirmed occupation

**Phase:** P0 persistence authority  
**Severity:** Critical  
**Status:** Fixed 2026-07-16; live dogfood passed

Live turn `turn_68e5915ddfba` treated `What is the only defensible status of
that unknown preference? Answer with one word.` as a third-person occupation
assertion. It wrote `user:occupation = only defensible status` despite the
answer route reporting `memory_write_allowed=false`, and completion authority
accepted the write.

Resolution evidence:

- whole-message assertion authorization now detects questions even when a
  trailing render instruction hides the final question mark;
- hypothetical, unresolved referential, and response-contract-only messages
  cannot authorize direct confirmed profile writes;
- the actual persistence function receives an explicit write-authority gate;
- completion authority fails any write without an allowed direct-user-assertion
  receipt;
- 179 focused and adjacent tests pass;
- fresh API and Workbench turns `turn_cdc351848280`, `turn_39f1f93e6273`,
  `turn_9bd903cecad7`, and `turn_8fb6adcffaf3` wrote nothing;
- the previously polluted occupation slot remains quarantined with no current
  value.

### CCF-010 — Rehydrated Workbench loses completion verification receipt

**Phase:** 5 — verification and public trace semantics  
**Severity:** High  
**Status:** Fixed 2026-07-16; live and rehydrated UI agree

Workbench turns `turn_9bd903cecad7` and `turn_8fb6adcffaf3` displayed counted
verification immediately after completion. After a real page reload, both
displayed `Checks unavailable` although their stored traces contain
`completion.verification_summary`. The conversation-list/rehydration path does
not reconstruct the same public receipt as the live event path.

Resolution evidence:

- the conversation-turn query joins the stored trace and returns only the final
  `completion.verification_summary`, not hidden reasoning or the full trace;
- Workbench prefers the live trace receipt and falls back to the persisted turn
  receipt after reload;
- pre-fix turns `turn_1aa4a22972d7` and `turn_a156965c005a` now reload with
  `Verified 4/4` and `Checked 3/5` respectively;
- fresh turn `turn_3a6863ffb164` displayed `Verified 4/4` live and after a real
  reload, and the rehydrated receipt exactly matched the stored trace receipt;
- nine focused backend tests, six ChatPanel tests, and the Workbench production
  build pass.

### CCF-011 — Natural yes/no and one-word contracts are not consistently active

**Phase:** 5 — response-contract recognition and truthful verification  
**Severity:** High  
**Status:** Fixed 2026-07-16; API, UI, and reload gates agree

The fresh Workbench prompt `Without guessing, is my favorite mural established
in this conversation? Answer yes or no.` returned a multi-sentence boundary
answer and displayed `Verified 5/5`. Direct API prompt seed `2026071602` likewise
ignored `Reply with one word` on the first turn. These forms were classified as
no active response contract, so the verifier truthfully checked the receipt it
was given but the receipt omitted an applicable hard constraint.

Resolution evidence:

- final-answer contracts now check yes/no, exact word count, number-only,
  object-only, comma-list/list-only, sentence, style, and maximum-word shapes;
- unknown profile-status yes/no answers are deterministic rather than depending
  on renderer repair;
- one bounded local exact-word rescue is available, while contract-only failure
  does not advertise stronger-model eligibility;
- API turns `turn_ebf4311f2680` and `turn_4db57e4fbbeb` passed yes/no and exact
  one-word contracts with deterministic prior-answer reference verification;
- `turn_094bdfb0fa1e` passed number-only and `turn_12e5d73e1b66` passed an exact
  seven-word contract;
- Workbench/reload turns `turn_fc02b66247ff` and `turn_234ccf059fa8` passed
  object-only and comma-list-only, while `turn_72e28bd3505d` and
  `turn_2937db59486f` passed yes/no and one-word contracts;
- every listed turn had zero memory writes, zero released evidence, and no
  stronger-model request; the focused/adjacent gate passes 248 tests.

### CCF-012 — Rejected completion enters context and top-level trace contradicts completion

**Phase:** 2/5 — accepted context and truthful trace semantics  
**Severity:** High  
**Status:** Fixed 2026-07-16; accepted/rejected dogfood passed

Live turn `turn_e26a5c24fc30` exhausted a yes/no contract and correctly had
`verification.accepted=false`, but its final source receipt still let the safe
fallback enter the next packet. Follow-up `turn_4755e52d9b4f` then answered
from that rejected fallback. Separately, accepted turns persisted top-level
`status=needs_clarification` and memory-plan `coverage=0.0`, contradicting their
successful final completion receipts.

Resolution evidence:

- packet construction excludes a final receipt only when its verification
  explicitly says `accepted=false`; legacy receipts with no verification field
  remain backward-compatible;
- prompt-local `that/they/it`, relative-clause `that`, and imperative-local
  `restate it` no longer require conversation history;
- final trace status/result is `completed` or `rejected`, and completion
  coverage is separated from the namespaced durable-memory planner;
- accepted `turn_3f694dcc2a30` persisted `completed` with 4 passed/0 failed and
  a non-applicable planner;
- rejected `turn_fab11a4b056c` persisted `rejected` without escalation, and
  `turn_611fdaf5dc2d` recorded `excluded_rejected=1` with no retained context;
- Workbench/reload turn `turn_24c42acab8b7` persisted the same completed result
  and receipt shown live; all listed turns wrote nothing and released no
  personal evidence.

### CCF-013 — Natural object/list follow-ups bypass contracts and falsely escalate

**Phase:** P0/2/5/6 — write authority, accepted context, contracts, dogfood  
**Severity:** High  
**Status:** Fixed 2026-07-16; live and rehydrated UI agree

Fresh Workbench turn `turn_cf57a4a1acba` answered an object-only request with a
full explanatory sentence because `and nothing else` was not recognized as an
object-only contract. After the first repair, `turn_1ee4ae7e680c` returned the
correct comma-separated prior-message list but did not activate its contract,
did not classify `my last message` as cross-turn, and set
`needs_stronger_model=true` even though the route forbade escalation. Its
ingestion receipt also said a short ordinary command was write-eligible while
the route said writes were disallowed.

Resolution evidence:

- object targets followed by `nothing else` activate and verify object-only;
- `repeat`, `restate`, and `list` activate the same answer-shape extractor as
  `return` and `give`;
- `my last/previous message` is an explicit cross-turn referent, not a profile
  lookup, and a retained accepted packet prevents false escalation;
- the persistence boundary opens only for an actually extractable direct or
  contextual fact, bounded correction, or explicit open belief/meaning claim;
- ordinary response-contract and tool commands publish both route and boundary
  `memory_write_allowed=false` receipts;
- post-fix Workbench/reload turns `turn_fbc1aeeb8555` and
  `turn_bdf973421493` returned exact object/list outputs with active contracts,
  retained context, zero hits/writes, no escalation, and stable counted checks;
- 167 adjacent backend tests, the full 1,335-test backend run, 61 Workbench
  tests, 12 Electron tests, the production build, and seed `20260718` all pass.

### CCF-014 — Compound request omits one job but reports full verification

**Phase:** 3/5 — answer-job construction and truthful requested coverage  
**Severity:** High  
**Status:** Fixed 2026-07-16; held-out UI/reload gate passed

Live turn `turn_e44f1529f414` asked both how the system remembers and, under a
contradictory in-prompt color assertion, for the confirmed favorite flower. The
answer correctly rejected the asserted color and returned governed profile
values, but omitted the system-memory question completely. The deterministic
answer constructor nevertheless caused requested coverage to pass and the UI to
display `Verified 5/5`.

Expected: every independently answerable clause becomes an explicit answer job;
requested coverage passes only when the final public answer covers every job.

Resolution evidence: deterministic meta/profile compounds now declare separate
answer jobs, compose both authorized outputs, and check every declared job
against the final public answer before requested coverage can pass. Held-out UI
turn `turn_a2fd368ca486` answered the system-memory job and the governed
color/flower jobs, rejected the disposable `cyan` premise, displayed
`Verified 5/5`, wrote nothing, and did not request a larger model. A regression
also proves that omitting the memory job fails completion acceptance.

### CCF-015 — Active discourse focus loses to an older retained turn

**Phase:** 2/3/5 — conversation packet use, focus resolution, truthful reference checking  
**Severity:** High  
**Status:** Fixed 2026-07-16; stored conversation and correction receipts passed

Turn `turn_6eddcb3c6bf5` explicitly identified the first half of the immediately
prior compound question as `How do you remember things?`. Follow-up
`turn_3f7dcddcf1d2` asked `Can you answer the first question?` but selected an
older status question and answer still present in the four-pair packet.

Expected: an immediately established or quoted referent becomes active
discourse focus and wins over older packet turns; unresolved reference checks
cannot be accepted as if the referent were correct.

Resolution evidence: ordinal requests bind to the most recent explicit focus
answer or the immediately preceding compound turn, then publish an explicit
resolution receipt. Held-out turns `turn_5bb3ce79d4fe` and
`turn_0007f62c6225` identified and answered the active system-memory question
instead of the older status turn. The verifier now honors the structured
resolution receipt rather than an obsolete boolean flag; correction turn
`turn_ef6a563d5737` persisted `reference_resolution=passed` and
`Verified 5/5` with zero writes and no escalation.

### CCF-016 — System-memory correction routes through personal review and escalates

**Phase:** 3/6 — route simplification and escalation truthfulness  
**Severity:** High  
**Status:** Fixed 2026-07-16; deterministic system/meta route passed

Correction turn `turn_f55329e1e090` said `no I meant "how do you remember
things?"`. The answer was broadly reasonable, but the trace selected
`memory_review`, used the personal-memory voice path, and set
`needs_stronger_model=true` despite a successful local completion and no frozen
packet demonstrating a renderer-capability boundary.

Expected: quoted correction targets repair the active reference; system-memory
architecture questions use the system/meta answer job, release no personal
profile evidence, and do not escalate merely because the prompt contains
`remember`.

Resolution evidence: structural questions about how Aether remembers, stores,
or retrieves now use the deterministic system-memory meta job. Explicit quoted
corrections replace the unresolved target before routing. Live turn
`turn_ef6a563d5737` resolved `How does your memory work?`, selected
`deterministic_meta`, used source `aether_meta`, released no personal evidence,
wrote nothing, and kept `needs_stronger_model=false`.

### CCF-017 — Negative response preface inverts zero-evidence yes/no truth

**Phase:** P0/5 — zero-evidence containment and semantic contract truth  
**Severity:** Critical  
**Status:** Fixed 2026-07-16; pre/post live reproduction retained

Pre-fix held-out turn `turn_dfb9f57c3571` asked whether an unknown favorite was
established while saying `without filling in a missing preference`. The boolean
adapter treated the preface word `missing` as the interrogative predicate,
returned `Yes.`, and falsely displayed `Verified 5/5`.

Resolution evidence: unresolved yes/no polarity is now derived from the actual
interrogative predicate after the auxiliary, not arbitrary constraint text.
Post-fix turn `turn_5bfd949c8f0b` returned `No.` and `Verified 5/5`. Follow-up
`turn_bc7303788362` deterministically derived status `Unknown.`, verified the
prior-turn semantic transformation and one-word contract, and displayed
`Verified 6/6`. Both turns wrote nothing, did not escalate, and the nonexistent
test slot remains HTTP 404.

### CCF-018 — Trace drawer summarizes obsolete slot-plan semantics

**Phase:** 5 — truthful public trace semantics  
**Severity:** High  
**Status:** Fixed 2026-07-16; live and rehydrated drawer agree

The persisted trace for `turn_ef6a563d5737` correctly contained completion
coverage `5/5`, a non-applicable durable-memory planner, and final result
`completed`, but the Workbench drawer displayed `0% / unknown / completed` by
reading the legacy slot plan.

Resolution evidence: the summary now reads top-level completion coverage,
explicit planner applicability, and final result receipts. A real reload of the
same turn displays `5/5 / not applicable / completed`; the completion article
also displays fully verified `5/5`. The TraceDrawer regression and full
Workbench suite pass.

### CCF-019 — Natural label/comma contracts and status/order referents are unchecked

**Phase:** 2/5/6 — contract aliases and bounded semantic reference verification  
**Severity:** High  
**Status:** Fixed 2026-07-16; held-out UI/reload gate passed

Held-out object turn `turn_05bf4649c87d` persisted explanatory prose despite
`Return only the middle label`; order turn `turn_996f353a200f` returned the
right items but did not recognize `separated only by commas` and could not
verify the prior-message order. A separate status follow-up initially treated
`that preference` as an intra-prompt relative clause and either emitted prose
or flagged the correct derived status.

Resolution evidence: `label only` activates object-only checking, natural
comma-separation wording activates list-only checking, demonstrative profile
nouns are cross-turn references, and ordered items are checked against the
prior accepted user message. Final turns `turn_445a1c132caa` and
`turn_45fd1611e5c1` persist bare `cotton ribbon` and the exact original
comma-separated order. The latter passes reference and contract checks and is
honestly `Checked 5/6` because ordinary model semantic coverage remains
unverified. Reload preserves both receipts; both turns have zero writes and no
larger-model request.

### CCF-020 - Employer concept, route, and entity-only contract disagree

**Phase:** 4/5/6 - query scope, truthful route semantics, response contracts  
**Severity:** High  
**Status:** Fixed 2026-07-17; fresh clean-room UI/API/restart gate passed

Fresh clean-room turn `turn_d33855a7d2c3` asked `Which organization am I
currently employed by?` while two current employer values were present. The
planner and query scope missed `organization ... employed by`, rejected both
states as irrelevant, and returned a false zero-evidence employment answer.
After the conflict was corrected in the real Memory drawer, turn
`turn_b2246960c901` asked for `only the company` but returned labeled prose,
displayed `Verified 5/5`, and mislabeled the lookup as `high_stakes_caution`
because the route treated every occurrence of `company` as high stakes.

Resolution evidence: one shared employer-concept recognizer now covers
employer, employment, work-for, present-company, workplace, organization, and
professional-affiliation forms while excluding general definitions. The
planner uses it for slot and current-state intent; released personal profile
packets structurally select `memory_review`. Entity-category-only instructions
now activate object-only checking, deterministic profile answers expose their
bounded value atom, and the final adapter returns that atom without a model
rewrite. `company` alone no longer triggers a high-stakes route.

Post-fix API turn `turn_d33de4dcc766` withheld both conflict values and selected
`contradiction_review`; UI turn `turn_0e7f13361531` did the same with Verified
5/5. After a Workbench correction to the synthetic `Northstar Lab` value,
held-out UI turn `turn_3d6f7f02f8c3` returned only `Northstar Lab` and displayed
Verified 6/6. After another restart, API turn `turn_9cfc4c6823de` selected
`memory_review` from the released profile packet, passed the object-only check,
wrote nothing, and was fully verified. The reopened UI preserved all three
turn receipts, including the historical failed turn.

### CCF-021 - Current-prompt container pronoun is treated as cross-turn

**Phase:** 2/5/6 - referent scope and truthful completion verification  
**Severity:** High  
**Status:** Fixed 2026-07-17; fresh UI/restart gate passed

Clean-room UI turn `turn_38bcd2d6c626` asked the adapter to inspect the
ChatGPT archive and report details `it contains`. The archive was the explicit
antecedent inside the same prompt, but the completion verifier treated `it` as
possibly referring to accepted prior conversation. The bounded archive block
was correct, yet the receipt could only display Checked 4/5.

Resolution evidence: the referent classifier now recognizes a named local
container followed by a finite predicate such as `it contains`, `it includes`,
or `it states`, while a bare `explain it` still requires conversation context.
Post-fix UI turn `turn_66b983c2f450` used a fresh `it includes` paraphrase,
returned the clean-room archive boundary, and displayed Verified 4/4. Restart
and reload preserved both the historical partial receipt and the corrected
receipt; neither turn wrote memory or ran a private archive tool.

### CCF-022 - Possessive entity-only contract is missed and labeled prose passes

**Phase:** 4/5/6 - query scope, response-contract parsing, and truthful checking  
**Severity:** High  
**Status:** Fixed 2026-07-17; direct API and UI/reload gates passed

Direct API turn `turn_6a5d9d53e2d0` asked for a confirmed workplace with
`Reply with only its name`. The parser missed the possessive entity-only form,
returned `Your employer is Northstar Lab.`, and persisted a fully verified
receipt. After parser repair, fresh turn `turn_fcb6cefeded0` showed that `No
confirmed workplace is on record.` could still be accepted as a bare object
because the checker recognized only a narrow set of labeled sentence openings.

Resolution evidence: possessive `its/their/that/this <entity>` forms now map to
the generic object-only contract. The checker rejects declarative negative
sentences as prose, and the bounded failure shape for object-only answers is
`Unknown` rather than another explanatory contract violation. A deliberately
ambiguous API prompt repaired to bare `None` and remained honestly Checked 4/5
because its semantics were not deterministically covered. The unambiguous API
turn `turn_f36a41c6e0c0` and UI turn `turn_11b40875bfce` both returned bare
`Northstar Lab`, selected `memory_review`, passed object-only verification, and
were fully verified with zero writes. Reload preserved the 5/5 UI receipt.

### CCF-023 - Causal intra-prompt pronoun is treated as a cross-turn referent

**Phase:** 2/5/6 - referent scope and accepted conversation  
**Severity:** High  
**Status:** Fixed 2026-07-17; frozen eval and fresh Workbench follow-up passed

The frozen product pack exposed that a coordinated question such as asking why
an observation occurs and what transfer explains `it` could be classified as a
cross-turn reference. The correct first answer was then rejected and therefore
unavailable to the actual cross-turn follow-up.

Resolution evidence: the classifier now distinguishes a causal WH clause whose
pronoun is governed by the current prompt from an explicit previous/just-asked
referent. The full frozen pack passes; live turns `turn_47a06826f3de` and
`turn_b0545f9c8586` produced the correct science answer and recovered its first
clause from accepted recent conversation with zero writes. The partial Checked
receipts remain honest rather than claiming unperformed semantic checks.

### CCF-024 - Bounded unknown over withheld evidence fails the governance spine

**Phase:** P0/4/5 - withheld-value containment and bounded rendering  
**Severity:** High  
**Status:** Fixed 2026-07-17; frozen eval and live withheld trace passed

`Unknown.` was the correct public answer for a provisional synthetic preference,
but the boundary evaluator did not recognize common unknown forms and rejected
the bounded answer.

Resolution evidence: the governance boundary recognizes a small semantic family
of unknown/not-confirmed/not-available forms without authorizing the held value.
Live turn `turn_042304268ebf` returned `Unknown.`, marked the underlying packet
`withhold`, displayed Verified 6/6, and wrote nothing. Restart preserved the
same receipt.

### CCF-025 - Generic entity-only response contracts have phrase gaps

**Phase:** 4/5/6 - response-contract parsing and verification  
**Severity:** High  
**Status:** Fixed 2026-07-17; frozen eval and UI object-only probe passed

Natural requests such as `Name my employer and nothing else`, `Only its name`,
and project-name-only variants could bypass the object-only grammar and permit
labeled prose.

Resolution evidence: those forms now enter the generic object-only contract and
are checked against the bounded value atom. Live turn `turn_b7dc9f100274`
returned bare `Northstar Lab`, displayed Verified 5/5, and wrote nothing. The
receipt survived restart and UI rehydration.

### CCF-026 - Employer and open-schema query paraphrases miss relevant slots

**Phase:** 4/6 - compositional query scope and planner relevance  
**Severity:** High  
**Status:** Fixed 2026-07-17; all relevance cases passed

The frozen pack found additional employer forms (`Where do I currently work?`,
`Which company employs me?`) and an open-schema `design shop` synonym that did
not map to their relevant governed slots.

Resolution evidence: the employer concept and conservative studio/shop/workshop/
atelier token family now compose at the query-scope/planner layer. Ambiguous
name/file language remains excluded. All five frozen relevance cases and the
live employer turn pass without releasing unrelated synthetic facts.

### CCF-027 - Exact literal presentation contract is confused with a memory claim

**Phase:** P0/3/5 - current-request authority and response contracts  
**Severity:** Critical  
**Status:** Fixed 2026-07-17; exact UI/API/restart gate passed

A request such as `Reply exactly: My occupation is lighthouse keeper.` is a
presentation contract, not authority to store the asserted occupation. The old
path could refuse the literal or treat its content as personal-memory material.

Resolution evidence: exact literal text is parsed as a current-turn response
contract after ingestion has independently denied durable-write authority. Live
turn `turn_cf9cd96c36ea` returned the exact literal, used deterministic source
`aether_response_contract`, displayed Verified 5/5, and wrote nothing. The text
is absent from the synthetic substrate and passages; restart and UI rehydration
preserved the completion receipt.

### CCF-028 - Accepted-turn named-object follow-up lacks a truthful referent check

**Phase:** 2/5/6 - accepted context and deterministic reference verification  
**Severity:** High  
**Status:** Fixed 2026-07-17; frozen recent-context cases passed

A follow-up requesting the named object from the prior accepted answer could be
generated incorrectly while conversational-reference verification remained not
applicable.

Resolution evidence: bounded prior-answer object referents now have a
deterministic answer constructor and explicit verification receipt. The full
five-case recent-context category passes. Generative follow-ups that do not use
that constructor remain honestly partial instead of being promoted to fully
verified.

### CCF-029 - Mixed-status compound profile request drops three answer jobs

**Phase:** 3/4/5 - compound construction, authority status, truthful coverage  
**Severity:** High  
**Status:** Fixed 2026-07-17; adjacent regression passed

The repository-wide suite exposed a four-part request for name, employer,
hobby, and project framework with one confirmed value, one conflict, one held
value, and one no-evidence slot. The deterministic contradiction route returned
only the employer conflict. Completion verification correctly rejected the
answer for missing the confirmed name, but the public response still omitted
three jobs.

Resolution evidence: mixed-status personal compounds now render every
query-scoped packet: released values are included, conflicts remain explicit,
and held/no-evidence slots receive bounded unknown statuses without leaking
their values. The constructor publishes four answer jobs so coverage cannot
pass on a partial response. The local deterministic route remains non-
escalating because missing authority is not a larger-renderer capability
boundary. The focused direct-answer, completion-verification, route, and
quality-dogfood slice passed 50/50.

### CCF-030 - Unresolved personal clauses are omitted from compound coverage

**Phase:** 3/4/5/6 - planner gaps, compound jobs, and live verification  
**Severity:** High  
**Status:** Fixed 2026-07-17; fresh UI/API/restart gate passed

The first post-CCF-029 Workbench probe, `turn_a96e3459e00f`, contained an
unresolved favorite-flower clause with no evidence packet. The compound answer
covered the three packet-backed fields, omitted the flower, and displayed
Verified 5/5 because only three answer jobs existed. A second fresh paraphrase,
`turn_7730ab6e80eb`, also exposed that `Who employs me?` was outside the
employer concept family, so that unresolved clause was omitted in the same way.

Resolution evidence: unresolved clauses that are structurally personal-profile
requests now receive a bounded unknown answer job even when the planner cannot
resolve a slot. The generic employer family also covers direct `who employs me`
wording. Untouched UI turn `turn_c8a847a60266` used different workplace/design-
shop/instrument/flower wording and returned the released employer, preserved
the studio conflict, withheld the provisional instrument, and bounded the
missing flower as unknown. Its final trace contains four answer jobs, completed
Verified 5/5, zero writes, and no stronger-model request. The same answer and
receipt rehydrated after sidecar restart; the substrate revision stayed
unchanged.

## Superseded Closure Summary

CCF-009 through CCF-030 are fixed and have passed the applicable production or
isolated clean-room dogfood gate.
CCF-020 through CCF-022 briefly and legitimately reopened the closed lane after
fresh clean-room production failures; it is closed again only after the failed
packets plus new API/UI paraphrases passed restart and rehydration gates.
CCF-023 through CCF-028 were exposed by the frozen 40-case product evaluation
and were reclosed only after systemic regressions, the unchanged full pack,
direct API inspection, real Workbench prompts, and restart/rehydration agreed.
CCF-029 was exposed by the adjacent full suite and reclosed with explicit
multi-job verification rather than by weakening the test.
CCF-030 was exposed only by the mandatory fresh UI gate and reclosed after a
different paraphrase plus persisted-trace restart proof.
The zero-evidence/irrelevant-profile release reproduced by the browser suite is
also contained before rendering and survives reload with the same receipt.
The broad Phase 6 rerun passed 25/25 with zero failed checks after the final live
repair. Automated, direct API, live UI, and rehydrated UI behavior now agree.
CCF-006 response containment remains fixed; unrelated historical durable-value
review remains a separate explicit user-review task.

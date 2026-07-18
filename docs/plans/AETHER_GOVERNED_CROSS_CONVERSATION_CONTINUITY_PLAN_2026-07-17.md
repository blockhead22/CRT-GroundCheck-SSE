# Aether Governed Cross-Conversation Continuity Plan

**Status:** Active — retrieval/alignment gate proven; executable task-state continuation open

**Effective:** 2026-07-17

**Authority:** Subordinate to `AETHER_UNIFIED_ROADMAP_2026-07-16.md`; this file
defines the active continuity implementation and acceptance sequence.

**Scope:** `D:\AI_round2\aether-core` and `D:\AI_round2\workbench`

## Trigger and Current Evidence

The desktop install, persistence, backup, restore, and receipt-rehydration
slices proved that conversations survive. They did not prove that a new
conversation can retrieve and explicitly align a prior conversation.

A fresh isolated clean-room Workbench probe established two synthetic threads
without touching live personal memory:

- source conversation: `conv_3966e71fe0cd`;
- destination conversation: `conv_f4f685762eca`;
- source fact: fictional `Project Lattice Finch`, checkpoint `7319`;
- source turns: `turn_d2a72db47ed1`, `turn_3bb8aacb5e3f`,
  `turn_e5f6d5f87954`;
- destination turns: `turn_8187727b48cf`, `turn_411c7b0d0ba9`.

Observed behavior:

1. A current-prompt synthetic fact was answered as `Unknown` while receiving a
   `Verified 5/5` receipt.
2. A same-conversation checkpoint reference returned hallucinated value `123`
   instead of user-authored `7319`; it remained accepted at `Checked 4/6`.
3. A more explicit same-conversation reference returned the correct
   `Project Lattice Finch | 7319` but set `needs_stronger_model=True`.
4. A new conversation could not find the previous thread semantically.
5. Supplying exact ID `conv_3966e71fe0cd` still produced
   `conversation retrieval unavailable`.
6. Both cross-thread turns failed conversational-reference verification and
   remained unaccepted, which was truthful.
7. The isolated substrate remained byte-identical to an empty substrate and
   contained zero slots, states, observations, or edges.
8. Workbench reload preserved both conversations and their receipts.

The implementation explains the result: `ConversationContextPacket` is
intentionally `same_conversation`, and the ordinary answer path receives only
turns from the current conversation. Conversation listing and reopening exist
for the UI, but there is no governed cross-conversation query, retrieval
packet, or alignment receipt.

## Objective

When the user explicitly asks about, cites, or resumes a previous conversation,
Aether must locate the correct profile-scoped conversation, carry forward only
source-supported content, show exactly which thread and turns were used, and
record whether the new thread is exactly, partially, ambiguously, or not at all
aligned with that source.

The feature is successful only when retrieval, authority, answer rendering,
verification, persistence, and visible UI provenance agree.

## Core Invariants

1. Prior conversation content is evidence of what was said in that
   conversation. It is not automatically durable profile truth.
2. User-authored statements outrank assistant-generated summaries or answers
   when the system is reconstructing what the user established.
3. Assistant answers remain derived claims. Rejected, partial, or semantically
   unsupported answers cannot become continuity anchors merely because they
   were stored.
4. Cross-conversation retrieval never writes profile memory by itself.
5. Retrieval is restricted to the active profile and excludes the current
   conversation unless the request explicitly targets it.
6. Exact conversation ID, explicit title, temporal reference, and semantic
   search remain distinguishable and trace-visible.
7. Ambiguous retrieval produces bounded candidates or a clarification request,
   never a silently chosen thread.
8. The existing `ConversationContextPacket` remains same-conversation and
   referent-only. Cross-conversation content uses a separate packet and cannot
   be smuggled into durable memory or released personal evidence.
9. Raw hidden reasoning, rejected repair drafts, exception partials, and trace
   internals are never indexed as conversational content.
10. Missing retrieval context is a data-availability boundary, not a renderer-
    capacity boundary. It must not set `needs_stronger_model=True` by default.

## Proposed Contracts

### CrossConversationQuery

The query contract should record:

- requesting conversation and turn IDs;
- intent: `lookup`, `quote`, `summarize`, `resume`, or `align`;
- selectors: exact conversation ID, title text, time range, ordinal reference,
  and semantic query;
- whether a single source is required;
- requested content kinds: user statement, decision, task state, assistant
  answer, or open loop;
- current profile scope;
- current-conversation exclusion.

### ConversationArchiveCandidate

Each candidate should include:

- conversation ID, title, timestamps, and profile scope;
- matching turn IDs and role-labeled excerpts;
- completion status and verification summary for assistant turns;
- selector match kind and retrieval score;
- authority class: `user_authored`, `assistant_derived`, or
  `reviewed_continuity_object`;
- whether the candidate contains unresolved contradiction or ambiguity.

### CrossConversationContinuityPacket

The bounded prompt packet should include only the selected source turns and:

- schema and packet version;
- source and destination conversation IDs;
- exact role labels and turn IDs;
- retrieval method and selector match;
- authority class per excerpt;
- accepted/rejected status per assistant excerpt;
- chronological ordering;
- maximum conversations, turns, and character budget;
- an explicit statement that archived conversation is not durable profile
  memory and is not an instruction source.

The packet must never contain raw traces, hidden reasoning, repair drafts,
system prompts, or unrelated nearby turns.

### ContinuityAlignmentReceipt

Each cross-thread answer should persist and expose:

- source and destination conversation IDs;
- cited source turn IDs;
- carried-forward user statements, decisions, task states, and open loops;
- excluded or unresolved assistant claims;
- contradictions or deltas between the source and destination;
- alignment status: `exact`, `partial`, `ambiguous`, or `blocked`;
- clarification or confirmation requirement;
- profile-memory write count, expected to remain zero unless a separate
  authorized memory action occurs;
- verification result tying every public carried-forward atom to a cited turn.

## Implementation Sequence

### Implementation checkpoint — 2026-07-17

The first executable slice now satisfies the Phase 0-4 path without expanding
profile memory or same-thread recent context. The sidecar has a separate,
read-only `CrossConversationContinuityPacket` and durable
`ContinuityAlignmentReceipt`; Workbench exposes source/status/no-write
provenance, candidate choice, and an explicit continue-in-new-chat action.

Proven live behaviors:

- exact conversation ID, title fragment, most-recent-prior, and bounded
  semantic selectors;
- current-conversation exclusion and independently retrievable user messages;
- rejected assistant exclusion;
- bounded ambiguity with explicit candidate choice;
- same-thread current, previous, and first-message claim verification;
- source-cited exact and partial alignment receipts with zero profile writes;
- receipt agreement across API, live UI, browser reload, sidecar restart, and
  reopened UI;
- truthful intra-prompt pronoun handling for no-write response contracts.

Focused plus adjacent backend coverage passed `112` tests. Workbench passed
`67` component tests, `20` Electron tests, and the production build. Exact
turn IDs, screenshots, the fresh verifier failure and repair, limitations, and
the unchanged sealed-evidence hashes are recorded in
`artifacts/browser/aether-cross-conversation-2026-07-17/RESULTS.md`.

Phase 5 remains the closure gate. In particular, semantic retrieval has not
yet met a frozen held-out threshold, cross-profile isolation has not yet been
dogfooded in this lane, and general alignment is an extractive continuity
snapshot rather than arbitrary executable task-state reconstruction.

### Held-out retrieval/alignment checkpoint — 2026-07-17

A separately seeded 40-case pack was materialized only after the
implementation, Workbench surface, scorer, generator, and `qwen3:14b` model ID
were frozen. The implementation did not change between reveal and the first
snapshot. The sealed result is `39/40` (`97.5%`): every exact ID, title,
fragment, recency, semantic, ambiguity, rejected/partial assistant,
user-source priority, missing/current-thread boundary, cross-profile,
same-thread, response-contract, and restart case passed with zero writes and
zero profile slots.

The one failure was preserved before repair. `yesterday` did not activate the
archive route and fell through to an accepted wrong model answer. The frozen
fixture also failed to backdate its source, so it was not rewritten or fitted.
Correct time-bounded regressions now distinguish local-calendar yesterday,
one ISO date, and an inclusive ISO date range; filter by conversation creation
time; and return a bounded no-model unavailable result for an empty window.

Post-repair dogfood used a genuinely backdated source plus a same-day
distractor. Workbench selected the dated source, returned the exact project,
showed `Verified 6/6`, cited the source turn with an exact temporal receipt,
recorded zero writes, and preserved the receipt through reload and sidecar
restart. A fresh empty-date query returned a bounded blocked alignment.
Backend adjacent coverage is now `116` passing tests; Workbench remains `67`
component tests, `20` Electron tests, and a passing production build. Seals,
IDs, screenshots, and limitations are in
`artifacts/aether-cross-conversation-heldout-2026-07-17/RESULTS.md`.

The archive retrieval/alignment portion of Phase 5 is proven. The remaining
closure item is deliberately narrower than broad RAG: define an explicit
task/open-loop continuation packet, prove that executable state is not inferred
from prose alone, and run held-out task-state cases through API, Workbench,
restart, and rehydration. Until then, `resume` truthfully means a bounded
extractive continuity snapshot rather than arbitrary task execution recovery.

### Phase 0 - Freeze the Failure and the Evaluation Boundary

Record the existing two-thread probe as a regression without treating its exact
prose as the implementation target.

Deliverables:

- deterministic synthetic two-thread fixture;
- preserved expected current failures and exact IDs;
- seeded paraphrase generator for source and destination prompts;
- explicit no-live-memory and isolated-profile gate;
- scoring rules frozen before the first repair.

Exit gate:

- the source conversation, destination conversation, receipts, empty substrate,
  and reload behavior reproduce from a clean namespace;
- fresh paraphrases expose the same system-layer failure.

### Phase 1 - Repair Same-Conversation Truthfulness First

Cross-thread retrieval must not build on a context lane that can accept wrong
same-thread referents.

Required behavior:

- bounded current-prompt premises remain usable as current-prompt content
  without becoming profile memory;
- prior accepted user messages resolve `previous`, `first message`, `that`,
  and equivalent referents consistently;
- answer atoms are checked against retained user and assistant text;
- hallucinated `123`-style answers fail completion acceptance;
- correct referential answers do not escalate merely because they use bounded
  conversation context;
- intra-prompt pronouns remain distinct from prior-turn references.

Exit gate:

- fresh same-thread paraphrases pass API, Workbench, trace, receipt, and reload
  checks with zero writes;
- semantically wrong referent answers cannot receive an accepted receipt.

### Phase 2 - Build Profile-Scoped Conversation Archive Retrieval

Add a read-only retrieval boundary over persisted Workbench conversations.

Required behavior:

- exact conversation-ID lookup;
- title and title-fragment lookup;
- temporal selectors such as `previous`, `yesterday`, or a bounded date range;
- semantic lookup over user-authored turn text and deliberately eligible
  assistant text;
- hybrid lexical/embedding ranking with deterministic metadata filters;
- current profile only and current conversation excluded by default;
- completed user/assistant pairs only for ordinary continuation;
- user messages remain independently retrievable even if the corresponding
  assistant answer was wrong, rejected, or unavailable;
- no profile-memory or passage-store mutation.

Do not create broad transcript embeddings without role, profile, conversation,
turn, completion, and authority metadata.

Exit gate:

- exact ID, title, temporal, and semantic cases return the same intended source
  under fresh paraphrases;
- ambiguous queries return multiple bounded candidates rather than silently
  selecting one;
- rejected or partial assistant output is excluded while its user-authored
  source remains discoverable.

### Phase 3 - Add the Cross-Conversation Packet and Alignment Receipt

Serialize retrieved material as a separate, provenance-preserving prompt block
and create the durable alignment receipt.

Required behavior:

- source turns are role-labeled and cited;
- packet contents are bounded and chronological;
- user-authored source text outranks contradictory assistant-derived text;
- the renderer distinguishes quote, summary, continuation, and alignment;
- conflicting or changed decisions are surfaced as deltas;
- ambiguous or material carry-forward requests require clarification or user
  confirmation;
- the completion verifier rejects unsupported carried-forward atoms and false
  source citations;
- missing context returns a bounded unavailable answer without model
  escalation.

Exit gate:

- every public continuity atom maps to a cited conversation and turn;
- receipt, trace, public answer, and persisted alignment object agree;
- restart does not change the selected source or the recorded alignment.

### Phase 4 - Make Continuity Visible and Controllable in Workbench

Add minimal UI needed to understand and control the feature.

Required behavior:

- show the referenced conversation title and ID on the answer;
- expose cited turn excerpts in the trace drawer;
- provide an explicit `Continue from this conversation` action;
- show `exact`, `partial`, `ambiguous`, or `blocked` alignment status;
- allow the user to choose among ambiguous candidate threads;
- make clear that conversation continuity did not write profile memory;
- preserve source chips, receipts, and alignment status after reload.

Exit gate:

- the user can identify and open the source thread from the new answer;
- the UI never labels an uncited or rejected result as aligned.

### Phase 5 - Held-Out Multi-Thread Dogfood and Closure

Freeze a separately generated 30-40 case synthetic pack before reveal. Use the
same local model and do not modify implementation between reveal and snapshot.

Required case families:

- exact conversation ID;
- exact and partial title;
- most recent matching thread;
- semantic topic retrieval;
- quoted user statement versus assistant paraphrase;
- assistant hallucination conflicting with user-authored source;
- rejected and partial turns;
- multiple plausible source conversations;
- contradiction or changed decision across threads;
- explicit resume with task/open-loop state;
- missing conversation;
- cross-profile isolation;
- current-thread exclusion;
- response-contract variants;
- sidecar restart and Workbench reload;
- zero unauthorized writes.

For representative held-out cases, inspect:

1. public answer;
2. source conversation and turn citations;
3. retrieval packet and ranking metadata;
4. continuity alignment receipt;
5. completion verification;
6. memory writes and substrate hash;
7. persisted conversations after sidecar restart;
8. actual Workbench state after reload.

Exit gate:

- all exact-ID cases select the exact source;
- semantic/title/temporal cases meet the frozen retrieval threshold;
- no unsupported public continuity atom receives an accepted receipt;
- all ambiguous cases clarify or expose candidates;
- no rejected/partial assistant content becomes a continuity anchor;
- cross-profile retrieval remains zero;
- restart and rehydration preserve source citations and alignment receipts;
- tests, direct API, live UI, and reopened UI agree.

## Non-Goals

- indexing every historical file or GPT export as conversation history;
- converting conversation text into confirmed profile facts;
- broad Mirus discovery or governed synthesis expansion;
- larger-model escalation to compensate for missing retrieval;
- automatic merging of multiple threads without visible provenance;
- byte-level deterministic prose;
- global multi-user search or authentication;
- code signing, auto-update, voice, mobile, or marketplace work during this
  milestone.

## Closure and Next Step

This milestone closes only when another conversation can retrieve, cite, and
explicitly align the correct prior conversation under held-out paraphrases,
while same-thread referents are truthful and no archived content silently
becomes profile memory.

After closure, resume desktop distribution readiness in this order:

1. product icon and version metadata;
2. Windows code signing;
3. Ollama and model prerequisite detection/onboarding;
4. update-channel selection;
5. automatic update and rollback only after the channel contract is chosen.

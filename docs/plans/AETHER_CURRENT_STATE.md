# Aether Current State

Last updated: 2026-07-01

Start new Codex threads here:

```text
D:\AI_round2\docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-29.md
```

## Current Lane

```text
Phase 2 governed learner / Mirus loop:
recent traces and turns -> review-only Memory, Support, Reflection,
Contradiction, and Evidence candidates -> Workbench review -> durable behavior
only after operator approval.
```

The local-router / durable trace / RAG-baseline lab is graduated as
Aether/Core validation infrastructure. Do not continue it as loose prompt
tuning, model shopping, or repeated adversarial v1/v2 tuning.

## Read First

```text
D:\AI_round2\docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_ARCHIVE_PROMPT_MINING_PASS_2026-07-01.md
D:\AI_round2\docs\plans\AETHER_ARCHIVE_PROMPT_PACK_RUNPLAN_2026-07-01.md
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_LAB_GRADUATION_2026-06-30.md
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_EVIDENCE_V0_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_AETEROS_CORE_SCHEMA_CANDIDATES_2026-06-30.md
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_TRACE_WORKBENCH_MAPPING_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_LOW_SCORE_ANCHOR_FIT_REVIEW_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_FEEDBACK_CANDIDATE_REVIEW_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_WEIGHTED_FEEDBACK_LEDGER_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_AETEROS_MASTER_PLAN_2026-06-26.md
D:\AI_round2\docs\plans\AETHER_WORKBENCH_V1.md
```

## Current Decision

```text
The lab proved a useful bounded claim:
governed external cognition can make small/local model behavior more reliable,
inspectable, and reviewable than raw local chat or plain/scaffolded RAG for
Aether's target cases.
```

This is evidence for governance, not evidence that local models compete with
frontier models globally.

The useful architecture is:

```text
intent/task classification
-> evidence and memory retrieval
-> Mirus packet / semantic spine
-> scaffold or answer spine
-> model rendering when needed
-> CRT verifier
-> repair/fallback
-> durable trace
-> review-only learning candidates
```

## Latest Implementation State

Phase 2 learner/review loop:

```text
Sidecar consolidation surfaces review-only Memory, Support, Reflection,
Contradiction, and Evidence candidates from explicit trace metadata.

Memory fact candidates are limited to explicit trace.memory_candidates rows
with review_required true/implicit, memory_write_allowed false, and
confirmed_fact false.

Workbench learner candidates show a why-this-exists strip with first receipt,
review boundary, and review destination.

Trace-proposed memory facts can open Memory with a manual review-only draft
panel. It does not prefill corrections, confirm candidates, quarantine, or
write memory.
```

Dogfood memory-ingest fix:

```text
"My favorite flowers are marigolds." now extracts as the governed singular
slot user:favorite_flower, so later "What is my favorite flower?" lookups can
resolve from confirmed memory after the fact is ingested.
```

Workbench Thinking drawer follow-up:

```text
The inline "How this answer formed" drawer now surfaces memory_writes and
review-only trace.memory_candidates. This makes explicit-memory captures and
non-applied learning candidates visible inside the answer-level trace without
opening any new write path.
```

Mirus intake correction:

```text
Soft user signals now flow through Mirus-style review candidates instead of
being treated as confirmed facts. Example: "I have many favorite drinks. Dr.
Pepper and Iced Coffee are up there" can produce a review-only
user:favorite_drink candidate with authority=unconfirmed and
memory_write_allowed=false. "I like iced coffee alot" stays a generic
user:preference candidate, not an invented favorite_drink fact.

Contextual confirmation is now supported in a narrow governed path:
if a recent trace contains a review-only Mirus preference candidate, and the
user immediately clarifies "it/that/this is my favorite X" (with light typo
tolerance like `ym` -> `my`), Mirus can promote that candidate into the named
confirmed slot. Example: `I like iced coffee alot` creates a review-only
user:preference candidate; `It is ym favorite drink` confirms
user:favorite_drink = iced coffee.

Generic favorite-slot self-discovery is now supported without hard-coding each
new slot. When the user asks an unresolved question such as
`What is my favorite sports team?`, Mirus stores a trace-only
`memory_intent` for `user:favorite_sports_team`. If the next turn gives
candidate evidence (`I like the Milwaukee Brewers...`), Mirus creates a
review-only candidate for that discovered slot, still with
`memory_write_allowed=false`. A short follow-up confirmation (`The Brewers`)
can then promote the candidate to confirmed governed memory. This closes the
live Workbench bug where the local model talked about a "possible memory
candidate" even though no real candidate existed in trace.

Archive/GPT-log evidence routing:
GPT-log, ChatGPT-archive, old-chat, and GPT-memory phrasing now triggers
document search and the broad Context Bridge instead of falling through to a
canned-only safety answer. Retrieved archive documents are surfaced as bounded
historical evidence with source_kind/title/score, while the answer still states
that archive hits are not confirmed memory and do not silently create support,
reflection, or policy changes. This is the first product-shaped bridge toward
using GPT logs as searchable historical evidence/candidates rather than either
ignoring them or treating them as truth.

Archive evidence learner candidate:
When a trace contains a document_search hit from GPT/ChatGPT/archive sources,
the consolidation preview can now create a review-only
`archive_evidence_candidate`. It routes to Reflect as a workflow review draft,
not Memory, because the first question is whether the archive hit should become
a support pattern, reflection, eval prompt, or remain a trace receipt. The
candidate carries the document title/source/excerpt and the safety contract:
historical evidence only, no confirmed memory, no automatic support/reflection
writes.

Workbench archive trace verification:
The inline answer-level Thinking fixture now includes an archive
`document_search` tool run with a bounded ChatGPT archive result. The test
asserts that the expanded answer trace shows `document search: completed` and
the public reason it ran, while the full Trace drawer can render the same
persisted tool-run shape. This closes the first UI proof that "use the GPT
logs" can become inspectable archive evidence rather than a silent canned
answer or confirmed memory write.

Archive dogfood smoke:
A temporary sidecar conversation with a `chatgpt_archive` document and the
prompt `Aether, use the GPT logs to fill in the gaps.` routes as
`context_bridge_broad`, sets `context_bridge.intents.archive=true`, runs
`document_search`, emits the public tool-check detail `1 tool run(s):
document_search.`, and then exposes a Reflect-bound
`archive_evidence_candidate` through consolidation preview. The candidate stays
`confirmed_fact=false` and `memory_write_allowed=false`; consolidation reports
no memory, support-pattern, or reflection writes performed.

Live archive phrasing fix:
Read-only inspection of the local Workbench DB showed older GPT/archive turns
where `Check the gpt logs`, `do you have any gpt memories?`, and
`Aether, you have my GPT corpus right?` had not searched documents. Current
code already handled the logs/memories phrasing; `GPT corpus` was the remaining
synonym gap. `gpt corpus` and `chatgpt corpus` now trigger document search,
Context Bridge archive intent, and deterministic archive-boundary answers. The
exact observed phrase set now routes to `context_bridge_broad` and runs
`document_search` in a focused smoke.

Sensitive archive-search regression:
Live trace `turn_d9636deccafd` exposed a serious archive/health failure. The
prompt `Aether search the gpt logs about my health history.` did run
`document_search`, but then fell through to local Qwen rendering and fabricated
log paths, hypertension/lisinopril examples, and a fake health summary. The
post-render check marked `needs_stronger_model=true`, but that was too late:
the answer had already been shown. Fix: archive-search phrasings such as
`search the gpt logs` now trigger deterministic `aether_meta` archive-boundary
answers, and sensitive health/archive prompts add an explicit boundary: surface
only source-bounded archive hits and review candidates; do not invent diagnoses,
treatments, medications, symptoms, log paths, or timelines. Regression coverage
asserts the exact bad prompt is deterministic, runs `document_search`, does not
ask Qwen, does not mark stronger-model needed, and does not contain the fake
paths or medication examples.

Live source-bound archive summary fix:
Workbench dogfooding on 2026-07-01 showed the first health/archive fix was
safe but too thin. `search the gpt logs for my medical history.` correctly ran
`document_search` and stayed deterministic, but a follow-up asking to summarize
the retrieved GPT/archive health hits routed as `high_stakes_caution`, skipped
tools, and let the local model produce a generic refusal. Fix: archive follow-up
phrases such as `retrieved GPT/archive hits`, `archive hits`, and
`source-bound` now trigger Context Bridge + `document_search`. Context Bridge
document excerpts now prefer health-domain terms for sensitive health/archive
queries, and deterministic archive answers can surface short source-bound notes
from retrieved durable documents. The live retest showed source-bound notes for
leukemia, Ph-positive, stem cell transplant, chronic GVHD, and related
limitations while preserving the boundary that these are archive hits, not
confirmed profile memory.

Archive prompt-pack live batch:
The archive prompt pack now has a live sidecar run plan and two result
artifacts. The first live batch found 2 pass / 3 fail / 0 memory writes:
`favorite_drink` surfaced a polluted value (`a problem. Dr. Pepper`),
`occupation` surfaced a polluted value (`biggest flaw`), and an exact-file
code search routed to `code_tool` but was answered by archive/meta text instead
of workspace evidence. Fixes added: direct profile answers now use a narrow
review-needed gate for obviously malformed values, and `code_tool` exact-file
prompts can prefer `workspace_tool_direct` over archive/meta responses after
`workspace_search`. Post-fix live batch:
`D:\AI_round2\labs\meaning_compression_lab\results\archive_prompt_mining_v1_live_after_fixes_1782896907.json`
passed 5/5 with 0 automatic memory writes. Remaining quality note: exact-file
workspace search can still return noisy file rankings when `Do not modify`
matches read-only validation files before archive-specific files.

Live Mirus favorite-slot dogfood:
Workbench dogfooding also exposed a renderer bug in the generic favorite-slot
self-discovery path. Mirus correctly discovered `user:favorite_sports_team` as
an unresolved trace-only intent, but the answer still fell through to local
model rendering and produced archive-flavored prose. Fix: unresolved
Mirus favorite-slot intents now get a deterministic boundary answer:
`I do not have your favorite sports team confirmed yet...`. After the user gave
candidate evidence (`I like the Milwaukee Brewers...`) and a short confirmation
(`The Brewers`), existing governed memory promotion stored
`user:favorite_sports_team = Milwaukee Brewers`; the live recall then answered
deterministically from `aether_direct`. A follow-up trace cleanup filters
resolved memory intents after governed context lookup so confirmed recalls no
longer show stale `unresolved favorite_sports_team` intent metadata in the
Thinking drawer.

Follow-up Mirus candidate dogfood:
Continuing live Workbench tests on 2026-07-01 exposed two smaller but important
candidate-path issues. First, product-like favorite values beginning with a
digit (`8BitDo controllers`, `7Artisans caps`) did not become candidates
because the liked-value extractor required a leading letter. The extractor now
allows digit-leading product names while preserving casing for tokens with
digits. Second, review-only candidate acknowledgements and short confirmations
were still being rendered by the local model. Active Mirus favorite-slot
candidates and their confirmed memory writes now receive deterministic
`aether_direct` acknowledgements. Live retest:
`What is my favorite lens cap brand?` -> unresolved deterministic boundary;
`I like 7Artisans caps.` -> deterministic review-only candidate, no memory
write, `confirmed_fact=false`.

Model-switch meta regression:
Switching the Workbench model to `qwen3:14b` exposed a separate meta-question
failure. `What is the biggest flaw in this system?` routed as `general_local`
and the local model hallucinated that the user's occupation was "biggest flaw"
from confirmed profile facts. Fix: system-flaw/weakness questions now route as
deterministic meta/governance answers. The deterministic answer names the real
failure class: the handoff boundary between governance and local rendering. A
qwen3-requested smoke now returns `source=aether_meta`,
`generation_model=deterministic`, `needs_stronger_model=false`, and makes zero
Ollama calls.

Thinking trace visibility:
public_governance_steps now includes a trace-safe `mirus_intake` step when
memory_writes or review-only memory_candidates exist. It reports counts and the
review boundary without exposing proposed values in the live public status
line. The inline Thinking drawer can show the candidate semantic_signal in the
expanded Process section.

Memory review bridge:
Mirus candidates now carry `proposed_value`, `semantic_signal`, and `authority`
into the Learn -> Memory draft handoff. The Memory drawer shows the proposed
value and can copy it into the confirmed correction field, but this remains a
manual review step: no memory write happens until the operator explicitly saves
the confirmed correction.

Review source trail:
When a confirmed correction is saved from a Mirus/learner draft, the correction
source text now includes the source candidate id and first receipt id. This
keeps the durable memory history tied back to the reviewed trace candidate.

Tool-consideration trace:
The sidecar now stores `tool_considerations` alongside `tool_runs`. This gives
the Thinking drawer a trace-safe explanation of whether semantic tools were
used or skipped, and why, without asking the local model to invent a private
tool plan.

Route/model/scaffold trace:
The inline Thinking drawer now exposes selected route, model policy, repair
policy, recommended model, fallback model, and render mode in the Process
section. This makes model routing visible as a governed decision rather than an
opaque local answer.

Verifier boundary display:
The inline Thinking drawer now shows clean safety-boundary lines in the Verifier
section, including memory-write and silent-escalation status. Clean answers no
longer look like "nothing happened"; they show which governance constraints
were checked and held.

Learning authority display:
Review-only Mirus memory candidates now show authority in the inline Learning
section, e.g. `unconfirmed, review required, write blocked`, so "noticed" does
not visually collapse into "known".

Aether code-skills dogfood correction:
Workbench testing showed a useful failure. Aether could expose a trace for a
code question, but a follow-up phrased as "make the smallest safe change" and
"add or update a test" routed as general local chat and produced plausible but
unverified paths. That is not acceptable for code work. Code/edit/test prompts
must enter the `code_tool` route and use verified workspace tools before
synthesis. The answer-level Thinking drawer is useful here because it made the
mistake visible: "No semantic tool call needed" on a code implementation prompt
is now a regression target, not a matter of taste.

Focused fix in progress:
- route policy recognizes verified-path retry prompts, code implementation
  wording, smallest-safe-change wording, and add/update-test wording as
  `code_tool`;
- semantic tools treat those same prompts as workspace intent and run
  `workspace_search` when no exact file path is supplied;
- tests now cover the observed Aether failure shape so future local-model
  code-skill work has to stay workspace-grounded.

Backend-first memory-reason candidate slice:
After the code-route fix was verified, Mirus gained a narrow contextual
favorite-reason candidate. A standalone `They are both orange` does nothing.
When recent trace/conversation context already establishes the
favorite-flower/orange thread, the same message can create a review-only
`user:favorite_flower_reason` candidate:

```text
proposed_value: Marigolds may matter because they are orange.
authority: unconfirmed
review_required: true
memory_write_allowed: false
confirmed_fact: false
```

This is deliberately not a memory write and not a medical/personality
inference. It is Mirus noticing a candidate reason for review.

Workbench Thinking/Learning verification:
The inline Thinking drawer fixture now includes `user:favorite_flower_reason`
and asserts that it appears as a review-only Memory item and a Learning review
candidate with `unconfirmed, review required, write blocked`. The per-section
display cap increased from 6 to 8 so richer process traces do not hide route
fallback/model details when Mirus candidates are present.

Learn -> Memory draft verification:
The Memory drawer now has direct test coverage for
`user:favorite_flower_reason` handoff. The draft shows the proposed reason,
semantic signal, unconfirmed authority, review-only boundary, and first
receipt. It does not call memory mutation APIs until the operator explicitly
uses the proposed value and saves a confirmed correction. The saved correction
source text includes the Mirus candidate id and receipt id.

Learner queue dogfood smoke:
An isolated two-turn sidecar smoke (`favorite flower is marigolds` + orange
context, then `They are both orange`) produces one trace memory candidate,
zero memory writes, and a `mirus_intake` public governance step. Calling
`/v1/consolidation/candidates` after the same smoke returns the candidate as a
Memory review draft for `user:favorite_flower_reason`, with
`memory_write_allowed=false`, `confirmed_fact=false`, and the proposed value
carried into the draft. This closes the immediate marigold/orange path from
trace -> learner queue -> Memory review handoff.

Learner queue duplicate polish:
Memory review candidates now dedupe by category, candidate kind, slot, and
proposed value instead of only by generated candidate id. This keeps repeated
trace evidence for the same proposed fact/reason from spamming the learner
queue while preserving the first receipt as the review source.

Mixed learner queue clarity:
The consolidation drawer now has isolated coverage for Memory, Support, and
Reflection candidates in one mixed queue. The test verifies route filters,
session-only hide/defer behavior, preview-only safety labels, draft payloads,
evidence receipts, and the Memory/Support/Reflect review-surface handoffs. This
keeps Phase 2 dogfooding focused on review clarity rather than automatic
learning.

Live trace dogfood fix:
Inspecting `C:\Users\block\.aether\workbench.db` exposed a real intake bug. The
turn `My favorite drinks are a problem. Dr. Pepper and iced coffee` had written
`user:favorite_drink = a problem. Dr. Pepper`, which dropped iced coffee and
let later answers over-focus on Dr. Pepper. The extractor now strips the
`a problem.` aside and preserves list values such as
`Dr. Pepper and iced coffee`. Regression coverage exists at the slot, ingest,
direct-answer, and sidecar app levels. Existing live memory should still be
corrected through review/manual correction, not silently rewritten by code.

Second live trace dogfood fix:
The same Workbench trace pass exposed three related runtime gaps:
`favorite drink and favorite color` stayed ambiguous instead of releasing both
slots, bare follow-ups such as `Drink?` did not resolve to `favorite_drink`,
and `I also like iced coffee` produced no review-only candidate, allowing the
local model to overclaim that it was now known. The planner now resolves
multiple explicit favorite-slot phrases in one clause and has narrow aliases
for one-word favorite follow-ups. Direct answers can render multiple released
profile packets deterministically. Mirus intake now treats `I also like X` as a
review-only preference candidate, and the local prompt includes a review-only
candidate section that explicitly forbids saying such candidates are known,
confirmed, remembered, or stored.
Workbench answer formatting / voice pass:
The chat answer body now routes through one Markdown renderer with styled
headings, lists, quote/callout blocks, code blocks, inline code, and tables.
Workbench also has a small `Aether voice` selector (`Grounded`, `Warm`,
`Alive`) stored locally and sent with chat requests. The sidecar normalizes the
voice profile, stores it in trace metadata, and injects it as bounded prompt
guidance alongside a light Markdown formatting contract. This is presentation
and generation style only: it is not memory, not a support/reflection write,
and not silent personality mutation. The inline Thinking drawer can show the
selected voice profile as part of the public process trail.
```

Reject/defer boundary:

```text
Accepted reflections can enter future context.
Rejected and deferred reflections do not.
Workbench Defer Session and Hide Session remain local review-queue states and
do not open review routes or call additional APIs.
```

Workbench/lab bridge:

```text
Local-router RAG evidence can be shown as review-only trace/review metadata.
Trace fixture attachment refuses the live DB by default.
Live DB attachment requires:
--allow-live-db --confirm-live-db ATTACH_REVIEW_ONLY_TRACE_EVIDENCE
Even then, it writes only trace JSON.
```

## Aeteros Core Extraction State

Implemented first reusable schema extraction:

```text
D:\AI_round2\aether-core\aether\sidecar\review_schema.py
```

Contains:

```text
EvidenceReceipt
ReviewCandidate
SafetyContract
review_only_candidate_flags
```

Wired into:

```text
D:\AI_round2\aether-core\aether\sidecar\consolidation.py
D:\AI_round2\aether-core\aether\sidecar\archive_import.py
```

Do not extract yet:

```text
ReviewDecision
ContradictionMarker
TraceEvent
TracePacket
FeedbackLedgerRow
```

Why:

```text
ReviewDecision waits for a durable Memory candidate/decision adapter.
ContradictionMarker waits until the same marker object drives at least two live
behaviors such as route policy and Memory conflict review.
TracePacket should be extracted before TraceEvent only after the same packet
object is used unchanged by at least two live call sites.
FeedbackLedgerRow waits for a non-lab feedback source.
```

Keep out of Core:

```text
local-router pack names
evaluator thresholds
Workbench session state
local_router_trace.evidence_review metadata
adversarial case ids
grant/product wording anchors
model names and fallback profiles
```

## Generative Governance

Generative governance is a strong roadmap hypothesis:

```text
Governance may generate structured answer spines, evidence boundaries,
insufficient-evidence responses, contradiction/review warnings, deterministic
meta/direct answers, and model render contracts before Holden/model rendering.
```

It must not:

```text
generate unreviewed truth
silently mutate memory or policy
store raw hidden chain-of-thought
become a second hidden chatbot
```

Current code already has narrow "governance can speak first" paths:

```text
D:\AI_round2\aether-core\aether\sidecar\meta_answer.py
D:\AI_round2\aether-core\aether\sidecar\direct_answer.py
```

Small-model proposal lab:

```text
D:\AI_round2\labs\meaning_compression_lab\generative_governance_lab.py
D:\AI_round2\tests\test_generative_governance_lab.py
D:\AI_round2\labs\meaning_compression_lab\results\generative_governance_lab_auto_v0.json
```

This labs the next hypothesis without product wiring:

```text
small model proposes JSON intent/fact/learning actions
deterministic governance verifies evidence, sensitivity, policy, and rate gates
only low-risk repeated user-evidence candidates can auto-promote in auto mode
sensitive health/legal/identity facts stay review-only
archive health searches are answer-only/source-bound, not memory writes
duplicate candidate pruning can be automatic but rate-limited
```

Auto mode is therefore scoped as deterministic governance over model-proposed
candidates, not "the model graduates truth." The v0 lab passes 6/6 cases in
auto mode with two allowed auto actions, while reporting no memory writes,
support-pattern imports, reflection creates, or raw chain-of-thought storage.
Do not wire this into Workbench until dogfooding produces enough candidate data
to test the gates against real traces.

First observational answer-spine implementation:

```text
D:\AI_round2\aether-core\aether\sidecar\governance_spine.py
D:\AI_round2\aether-core\tests\test_governance_spine.py
```

The sidecar now stores `governance_answer_spine` in each chat trace before
model rendering. This is trace-only in the first pass: it does not change the
prompt, write memory, import support, create reflections, or mutate policy.

Second lab pass:

```text
D:\AI_round2\aether-core\aether\sidecar\governance_spine_eval.py
```

The sidecar now also stores `completion.governance_spine_compliance` after the
answer is produced. This is a small CRT-side check over the pre-render spine,
the rendered answer, and the governed source context. It flags restricted-value
leaks, missing restricted-evidence boundary language, and false memory-write
claims without storing restricted values or raw hidden chain-of-thought.

Workbench Trace drawer visibility now includes a "Governance spine" panel:

```text
D:\AI_round2\workbench\src\components\TraceDrawer.tsx
D:\AI_round2\workbench\src\components\TraceDrawer.test.tsx
D:\AI_round2\workbench\src\types.ts
```

It shows render mode, route/model policy, answerable/restricted packet counts,
guidance/context bridge presence, compliance pass/flag state, flag count,
restricted-leak and memory-claim booleans, memory-write boundary, raw-CoT
boundary, and the first render-contract lines.

Live public governance trace:

```text
D:\AI_round2\aether-core\aether\sidecar\governance_trace.py
D:\AI_round2\aether-core\aether\sidecar\app.py
D:\AI_round2\workbench\src\api.ts
D:\AI_round2\workbench\src\components\ChatPanel.tsx
D:\AI_round2\workbench\src\components\TraceDrawer.tsx
```

The sidecar now builds `public_governance_steps` from the governed trace and
streams each step as a `governance_step` SSE event before answer tokens. The
Workbench chat bubble shows the steps while the answer is pending, and the
Trace drawer keeps the saved step list. These are public status lines such as
memory check, semantic tool check, route selection, answer spine, and safety
contract. They are not memory writes and not silent policy mutation.

Product intent:

```text
The Workbench should feel closer to the GPT Activity / thinking drawer pattern:
each answer can expand into a readable "how this answer formed" trace.
```

Bring forward as a real UI feature:

```text
Thinking / Process
- what Aether classified the user request as
- what memory scope it checked
- what tools it considered or ran
- what route/model/scaffold was selected
- what public rationale or planning line the model/generator produced
- what verifier flags or repair/fallback actions happened

Memory
- which governed memory slots or historical traces were referenced
- what evidence was released, withheld, conflicted, or missing

Learning
- what slipped, what worked, and what candidate improvement should be reviewed
```

First Workbench product slice implemented:

```text
D:\AI_round2\workbench\src\components\ChatPanel.tsx
D:\AI_round2\workbench\src\App.test.tsx
D:\AI_round2\workbench\src\styles.css
```

Each completed assistant answer now has a compact `Thinking` toggle beside the
release-trace shield. Opening it fetches the persisted turn trace and renders an
inline "How this answer formed" view with:

```text
Thinking / Process
Memory
Tools
Verifier
Learning
```

This is the first product-shaped bridge from the old AgentThinkingStrip /
PipelineTrace affordance into Workbench. It uses existing persisted trace
fields; it does not create memory, import support, create reflections, or infer
private hidden scratchpad.

Boundary:

```text
Do not store private hidden scratchpad as durable truth.
Do store displayable reasoning/process traces, public model-authored rationale,
tool receipts, verifier flags, answer-spine contracts, and learning events.
If a model produces a visible "thinking" line, label it as public rationale and
verify it against the deterministic governance trace before treating it as
evidence.
```

This brings forward the old scaffold/tool-discovery idea in a safer form:

```text
old scaffolded escape / harness idea:
small model discovers path/tool/scaffold before answering

current governed version:
Aether builds a public trace-safe path, chooses tools/routes/spine
deterministically where possible, then lets the model render inside the
contract.
```

Original harness/tool-discovery references found on 2026-06-30:

```text
D:\AI_round2\personal_agent\agent_tool_loop.py
D:\AI_round2\personal_agent\agent_reasoning.py
D:\AI_round2\personal_agent\task_agent.py
D:\AI_round2\routes\chat_agent_loop_runner.py
D:\AI_round2\routes\chat_orchestrator_runner.py
D:\AI_round2\frontend\src\components\chat\AgentThinkingStrip.tsx
D:\AI_round2\frontend\src\components\chat\PipelineTrace.tsx
D:\AI_round2\frontend\src\components\chat\ToolRow.tsx
D:\AI_round2\frontend\src\components\chat\ThinkingStub.tsx
D:\AI_round2\frontend\src\lib\streamEvents.ts
```

Useful old pieces to carry forward:

```text
agent_tool_loop.py: LLM sees tool schemas, calls tools, sees results, decides
whether to continue, and emits live loop/tool events.

agent_reasoning.py: explicit thought -> action selection -> reflection
architecture with native Ollama tool schemas and JSON fallback.

task_agent.py _llm_tool_loop: skill/API-doc harness where the model chooses
tools from docs, receives results, and is nudged not to stop too early.

old frontend chat components: live intent/route/plan/tool/validate/drafting UI.
```

Carry-forward constraint:

```text
Do not resurrect private scratchpad as truth. Reuse the event shape and UI
affordance, and translate it into displayable thinking/process traces, public
rationale, tool receipts, verifier flags, and reviewed learning events.
```

Live dogfood fixes from Workbench probing:

```text
D:\AI_round2\aether-core\aether\memory\slots.py
D:\AI_round2\aether-core\aether\sidecar\ingest.py
D:\AI_round2\aether-core\aether\sidecar\direct_answer.py
D:\AI_round2\aether-core\aether\sidecar\meta_answer.py
```

Explicit user facts inside mixed fact/question messages now persist when the
fact itself is extractable. Example: `My favorite flower is marigolds. why?`
stores `user:favorite_flower = marigolds`, and a later or restarted thread can
answer `What is my favorite flower?` from governed memory. Pure questions still
do not write memory.

`What is the most important thing to you?` now routes as an Aether meta/self
question instead of a missing user-profile lookup. It answers deterministically
from the governance thesis: epistemic integrity, evidence boundaries, and model
rendering without model-owned truth.

Verified boundaries:

```text
restricted packet values are not leaked into the spine
restricted packet values are not copied into compliance traces
Trace drawer shows compliance flags without showing restricted values
model-rendered answers still call Ollama normally
deterministic meta/direct answers remain deterministic
the spine carries memory_write_allowed=false
the spine carries raw_chain_of_thought_stored=false
the compliance trace carries raw_chain_of_thought_stored=false
favorite_flower lookup passes across durable governed slot retrieval
bare Aether priority question bypasses local model profile guessing
```

The next practical version is:

```text
Mirus generates the answer spine and evidence boundary.
Holden/model renders only when language nuance is useful.
CRT verifies the rendered answer against the spine.
Workbench stores trace and review candidates.
```

## Archive Prompt Mining Checkpoint - 2026-07-01

The archive/GPT-history prompt pack now has both live-safe and isolated
candidate evidence:

```text
D:\AI_round2\labs\meaning_compression_lab\replay_packs\archive_prompt_mining_v1.json
D:\AI_round2\labs\meaning_compression_lab\replay_packs\archive_prompt_mining_v2.json
D:\AI_round2\docs\plans\AETHER_ARCHIVE_PROMPT_PACK_RUNPLAN_2026-07-01.md
```

Validated behavior:

```text
Live batch after fixes:
5 pass, 0 fail, 0 automatic memory writes.

Isolated candidate batch after fixes:
4 pass, 0 review, 0 fail, 0 memory writes.
```

Key fixes:

```text
Polluted governed slots are surfaced as review-needed instead of polished truth.
Code/edit/test prompts prefer workspace_search evidence over archive/meta text.
Generic favorite-slot self-discovery creates review-only candidates.
Hedged facts like "I think my favorite movie is Arrival" do not auto-write.
Question-shaped correction traps like "blue, right?" do not overwrite memory.
Current-employer traps like "I still work there, right?" preserve governed current evidence.
```

Boundary:

```text
GPT/archive logs are searchable historical evidence and candidate material.
They are not confirmed memory, not raw transcript truth, and not automatic
support/reflection writes.
```

Next archive challenge pack:

```text
archive_prompt_mining_v2 adds 12 prompts focused on low-authority assistant
interpretations, review-only support-pattern mining, stale Walmart evidence,
old bootstrap auto-accept conflicts, generated medical-output hallucination
traps, and code-tool routing for archive import/apply code.

Recommended v2 smoke result:
D:\AI_round2\labs\meaning_compression_lab\results\archive_prompt_mining_v2_smoke_after_meta_boundaries_1782899974.json
5 pass, 0 review, 0 fail, 0 memory writes.

Remaining v2 smoke result:
D:\AI_round2\labs\meaning_compression_lab\results\archive_prompt_mining_v2_remaining_smoke_after_archive_boundary_fixes_1782901101.json
7 pass, 0 review, 0 fail, 0 memory writes.

The v2 smoke validated broader archive phrase routing and deterministic
front-loaded boundaries for assistant interpretations, old bootstrap
auto-import plans, generated scaffold/medical-output material, stale employer
archive traps, and old GPT/Lumi/Nova/Holden voice-transplant boundaries.
```

Archive lane stop condition:

```text
V2 has now covered the recommended 5-case smoke and remaining 7-case smoke with
no writes. Do not add archive-ingest features from theory. Next archive work
should come from live Workbench dogfooding regressions, a larger blind pack, or
a concrete product decision about how reviewed archive evidence should be
promoted.
```

Archive answer quality pass:

```text
`search my gpt logs about ai concerns` exposed a product-quality issue rather
than a governance failure: Aether retrieved bounded archive evidence, but the
answer dumped chunky snippets instead of summarizing. Broad archive/topic
searches now render a structured archive summary with main source-bounded
themes, archive hits used, review-only candidate themes, and an explicit
no-write boundary. Prompts that explicitly ask for source-bound hits/excerpts
or sensitive health summaries keep the stricter excerpt behavior.

Verification:
python -m pytest aether-core\tests\test_sidecar_direct_answer.py aether-core\tests\test_sidecar_app.py aether-core\tests\test_sidecar_route_policy.py aether-core\tests\test_sidecar_documents_tools.py aether-core\tests\test_sidecar_meta_answer.py -q
142 passed
```

## Next Work

Shutdown checkpoint:

```text
The marigold/orange Mirus candidate lane and mixed learner queue polish are at
a reasonable stop point. Backend trace -> learner queue -> Memory review draft
is covered, repeated Memory candidates dedupe, and mixed Memory/Support/
Reflection review routing has isolated Workbench coverage. Do not keep adding
learner surfaces from theory. Resume this lane only from live Workbench
dogfooding regressions or a concrete daily-use clarity problem.
```

Do next:

```text
1. Improve learner review queue dogfooding only where it helps daily use.
2. Look for a real Memory candidate/decision adapter need before extracting
   ReviewDecision.
3. Keep regression tests around review-only and reject/defer non-effect.
4. Treat generative governance as an answer-spine experiment, not a schema
   extraction yet.
5. Next test lane: optional model-generated public "planning line" only if it is
   explicitly bounded, labeled public, never treated as truth, and checked
   against the deterministic governance steps.
6. Bring the old AgentThinkingStrip / PipelineTrace affordance forward into
   Workbench as an expandable answer-formation drawer: Thinking, Memory,
   Tools, Verifier, Learning.
7. Improve the Thinking drawer feedstock: add explicit public rationale lines
   and tool-consideration steps only after they are generated as public,
   bounded, and verifier-checked trace fields.
```

Do not do next:

```text
do not retune adversarial v1/v2
do not return to raw-only model comparisons
do not add import surfaces without product need
do not create automatic memory/support/reflection writes
do not expand schemas speculatively
```

## Safety Contract

```text
Do not store raw hidden chain-of-thought as truth.
Do store structured CRT trace artifacts:
classification, retrieval, Mirus packet, route, scaffold, verifier flags,
repair/fallback, confidence, contradiction notes, and learning candidates.
Do store and display public reasoning/process traces that explain answer
formation without granting unchecked authority to private model internals.

No automatic memory writes.
No automatic support-pattern imports.
No automatic reflection creation.
No silent model switching.
No silent policy mutation.
```

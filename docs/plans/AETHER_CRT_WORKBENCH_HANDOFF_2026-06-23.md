# Aether / CRT / Workbench Handoff — 2026-06-23

This document summarizes the working thread that started from “Are the labs complete?” and moved into Aether Workbench implementation. It is meant as a restart packet for a cleaner project thread rooted in `D:\AI_round2`.

## Current working thesis

CRT/Aether is no longer mainly blocked by “is the idea interesting?” The valuable next phase is turning it into a small, locally useful system that proves the theory through behavior:

- governed memory;
- local model context scaffolding;
- visible release traces;
- correction/quarantine workflows;
- bounded local tools;
- optional manual frontier escalation.

The important pivot is away from a giant custom harness and toward a local sidecar/workbench that existing harnesses or humans can use.

## Big strategic conclusion from the thread

The system probably should not try to “beat OpenAI/Claude/Grok in the harness war.”

The stronger lane is:

```text
Aether as local sidecar
  -> governed memory/context
  -> small local model scaffolding
  -> bounded tool execution
  -> visible trace and correction loop
  -> optional manual escalation to frontier models
```

This preserves the core CRT idea: the value is not raw model intelligence. The value is a governance layer that shapes, releases, audits, and corrects context before inference.

## Labs state

The deterministic hardening stage was treated as complete enough to move forward, but empirical validation is not complete.

Original CRT lab next steps were:

1. Add `include_hardening` support to `scaffold_model_sweep.py`.
2. Run all 19 cases through Qwen, Phi-3, Llama 3.2, and Mistral.
3. Categorize model-specific failures.
4. Only then adjust the scaffold contract.

The thread then shifted because the user wanted practical output after a year-plus of dev/research. The working conclusion was:

- continue labs when they inform implementation;
- do not let labs indefinitely delay usable system integration;
- prioritize the local Workbench proof loop.

## Important conceptual notes

### Governance has a dose curve

Current bet:

> Performance is not monotonically improved by governance. It is likely an inverted-U, and the ideal governance dose varies by model and consequence level.

This tied back to the older Mirus/Holden concept:

- Mirus observes and learns;
- Holden holds the line or allows certain things through;
- model-specific weights should eventually adapt when a model is swapped.

This is not implemented yet, but it is a guiding design principle.

### Scaffold failure should not mean “any variation”

The thread settled toward this standard:

- slight wording variation is fine;
- wrong slot use is failure;
- missing an answerable clause is failure;
- answering from conflicted/provisional/quarantined evidence is failure;
- refusing despite permitted evidence is failure;
- over-answering from absent evidence is failure.

Likely future architecture is hybrid RAG + CRT, not one versus the other:

- RAG finds candidate material;
- CRT governs whether it is safe/authoritative enough to release;
- the scaffold tells a weaker model what is answerable, missing, conflicted, or withheld.

### Self-pruning / frequency bias remains open

There was recurring interest in:

- scoring frequency bias;
- freezing a chain/path once it becomes reliable;
- detecting broken memory contracts;
- letting a system reflect on where its reasoning or retrieval went wrong.

These are not today’s implementation target, but they remain “later architecture” notes.

## Aether Workbench v1 plan already accepted

The user explicitly requested implementation of:

`Aether Workbench v1 — Local Sidecar Plan`

The first action was to save the specification as:

- `D:\AI_round2\docs\plans\AETHER_WORKBENCH_V1.md`

Core proof loop:

```text
Narrow Electron dock
  -> Aether governed context
  -> Qwen 2.5 7B through Ollama
  -> local response + visible release trace
  -> memory correction drawer
  -> optional manual Codex escalation
```

Explicit exclusions for v1:

- scheduling;
- auth;
- cloud sync;
- agents/jobs/loops;
- telemetry;
- desktop control;
- plugin marketplaces;
- automatic frontier calls.

## Workbench implementation state

The Workbench has been implemented in `D:\AI_round2\workbench` alongside `aether-core`.

Implemented areas include:

- Electron + React/Vite workbench shell;
- local sidecar API through `aether-core`;
- chat streaming against Ollama;
- governed trace drawer;
- memory drawer;
- model/status UI;
- manual Codex escalation foundation;
- large text ingestion into durable documents;
- simple local coder/tool milestone;
- reflection drawer;
- conversation lifecycle.

### Latest installed/build artifacts noted in the thread

These paths were produced in prior work:

- `D:\AI_round2\workbench\release-coder\Aether Workbench Setup 0.1.0.exe`
- `D:\AI_round2\workbench\release-reflect\Aether Workbench Setup 0.1.0.exe`
- `D:\AI_round2\workbench\release-conversations\Aether Workbench Setup 0.1.0.exe`

Do not assume release folders are clean git artifacts. They may be untracked build outputs.

## Implemented quality-of-life feature: conversations

The user asked for:

> ability to either create a new chat thread. close/delete. but maintain the saved knowledge. not always in context but could be recalled on

Implemented behavior:

- create new chat thread;
- switch saved conversations;
- delete current chat history;
- preserve governed memory, documents, reflections, and settings.

Important backend behavior:

- deleting a conversation removes disposable chat-local state:
  - turns;
  - traces;
  - tool runs;
  - escalation receipts linked to that chat;
  - patch receipts linked to those tool runs;
  - the conversation row.
- deleting a conversation preserves durable knowledge:
  - `~/.aether/substrate.json`;
  - documents/document chunks;
  - reflections/evidence/reviews;
  - settings.

Key files touched:

- `D:\AI_round2\aether-core\aether\sidecar\db.py`
- `D:\AI_round2\aether-core\aether\sidecar\app.py`
- `D:\AI_round2\workbench\src\App.tsx`
- `D:\AI_round2\workbench\src\api.ts`
- `D:\AI_round2\workbench\src\types.ts`
- `D:\AI_round2\workbench\src\components\ChatPanel.tsx`
- `D:\AI_round2\workbench\src\styles.css`
- `D:\AI_round2\aether-core\tests\test_sidecar_conversations.py`
- `D:\AI_round2\workbench\src\App.test.tsx`

Verification already completed:

- backend focused tests: `17 passed`;
- workbench UI tests: `11 passed`;
- `npm run build` passed;
- Electron packaging passed;
- browser-rendered QA passed for creating/selecting/deleting conversations.

## Implemented local coder/tool milestone

The user wanted meaningful local interaction and “a little tool usage,” especially the ability to inspect local folders/files and eventually code on the side.

Implemented direction:

- deterministic semantic tool scaffolding for smaller local models;
- local file/folder inspection;
- workspace search/read;
- patch proposal;
- approval-gated patch apply;
- local model can generate a single-file patch plan that is validated before apply.

Current rough capability:

- The model may not natively call tools, so the sidecar detects semantic intent and runs tools before prompting the model.
- The prompt tells the model that tool results are trusted observations.
- Patch proposal is a preview only; user approval is required before mutation.

Important principle:

> Tool use should not depend on Qwen perfectly understanding tool syntax. Aether can scaffold tool use semantically.

## Implemented reflection direction

The user emphasized reflective loop behavior:

- the AI should reflect;
- figure out where it is wrong;
- notice bad retrieval or thin answers;
- make future responses better.

Implemented start:

- reflection storage/review path;
- reflection drawer;
- manual review rather than automatic insight spam.

Relevant documents:

- `D:\AI_round2\docs\PERSONAL_OPERATIONS_AGENT_SCOPE.md`
- `D:\AI_round2\docs\PERSONAL_OPERATIONS_AGENT_ROADMAP.md`

## Known live problem: Aether feels too thin when asked identity/profile questions

Recent observed local client transcript:

```text
Hello?
-> Hello! How can I assist you today?

What is my name?
-> Your name is Nick Block.

How do you know me?
-> Based on the recent conversation, I know your name is Nick Block...

What do you know about me?
-> Based on our recent interaction, I know your name is Nick Block...
```

Diagnosis:

- Aether can retrieve a fact.
- The local model can answer from that fact.
- But there is no broad “context bridge” for identity/profile/self questions.
- The model receives a narrow governed packet, so it sounds like a lookup tool rather than a companion with durable relationship memory.

This is the next best implementation target.

## Next implementation plan: Context Bridge

Goal:

Make questions like these route through a richer governed context bundle:

- “What do you know about me?”
- “How do you know me?”
- “What are we working on?”
- “What is this system?”
- “How are you designed?”
- “What can you do?”

The fix should not weaken governance. It should add a separate prompt/trace block that contains only safe, confirmed, non-conflicted profile and self information.

### Proposed backend shape

Add an `identity_context` or `context_bridge` block to chat trace and local prompt.

It should include:

- `self_model`: Aether’s grounded identity/capability manifest.
- `profile_summary`: confirmed active user slots, grouped and capped.
- `project_summary`: confirmed/relevant project slots where available.
- `recent_context`: small safe summary from recent conversation turns.
- `durable_documents`: only search hits if relevant, not raw document dumps.
- `withheld_summary`: counts/categories of unavailable/conflicted evidence, without leaking restricted content.

### Existing useful file

There is already a self model:

- `D:\AI_round2\aether-core\aether\sidecar\self_model.py`

It defines:

- name;
- builder;
- purpose;
- architecture;
- memory contract;
- capabilities;
- limitations;
- `self_model_for_query(query)`.

Current issue:

- this self model exists but is not clearly injected into `build_local_prompt` for normal chat;
- self/about-me questions still rely too much on the ordinary slot planner.

### Proposed implementation steps

1. Add a new module, likely:

   - `D:\AI_round2\aether-core\aether\sidecar\context_bridge.py`

2. Add intent helpers:

   - `is_profile_query(query)`;
   - `is_self_query(query)`;
   - `is_project_query(query)`.

3. Build a profile bundle from the substrate:

   - include only current states;
   - exclude conflicts;
   - exclude provisional/unconfirmed sources unless explicitly marked safe;
   - exclude quarantine markers;
   - cap number of slots;
   - attach source/authority in trace, but present cleanly to model.

4. Inject the context bridge into:

   - `chat_stream` in `D:\AI_round2\aether-core\aether\sidecar\app.py`;
   - `build_local_prompt` in `D:\AI_round2\aether-core\aether\sidecar\prompt.py`;
   - saved trace payload.

5. Add tests proving:

   - “What do you know about me?” includes multiple confirmed profile facts;
   - conflicted employer values are not included;
   - quarantined project/framework values are not included;
   - “How are you designed?” includes self model content;
   - ordinary narrow queries still use normal governed packets;
   - prompt does not contain excluded provisional/conflicted/quarantined values.

### Prompt behavior target

For “What do you know about me?”, the local model should be able to say something like:

```text
I know a few confirmed things: your name is Nick Block, you are working on Aether/CRT, and you prefer practical, grounded progress over giant speculative rewrites. I may also have other candidate memories, but I only treat confirmed governed evidence as reliable.
```

It should not say:

```text
I only know your name from this conversation.
```

unless that is actually all the governed context contains.

## Known dev runner issue

When running:

```powershell
cd D:\AI_round2\workbench
npm run dev
```

Vite may shift from port `5175` to `5176` if `5175` is occupied, but Electron expects the original port. Also Electron may log cache errors on Windows.

Suggested patch:

In `D:\AI_round2\workbench\package.json`, change the dev script from:

```json
"vite --port 5175"
```

to:

```json
"vite --host 127.0.0.1 --port 5175 --strictPort"
```

In `D:\AI_round2\workbench\electron\main.cjs`, near the imports/startup:

```js
if (process.env.NODE_ENV === 'development') {
  app.setPath('userData', path.join(app.getPath('temp'), 'aether-workbench-dev'))
}
```

This was identified but not completed in the interrupted thread.

## Current user preference / product direction

The user does not want endless theory. They want meaningful local output.

Current desired product feel:

- narrow vertical left-edge desktop slice;
- chat with local memory;
- memory correction panel;
- Aether can talk about itself;
- Aether can inspect files/folders;
- small local coding assistant behavior;
- optional manual escalation to Codex/frontier model;
- no huge legacy frontend revival.

The user accepts that local Qwen will not be frontier-level, but wants Aether to scaffold it into being more useful.

## “Paradigm shift” assessment from thread

The thread repeatedly asked whether the system still has a paradigm shift in it.

Working answer:

- not yet as a finished product;
- possibly yes as a service pattern;
- most likely value is not “new LLM harness beats everyone”;
- value is a local governance/context sidecar that can improve smaller/local/frontier models by controlling memory release, tool scaffolding, and traceability.

What keeps it from feeling paradigm-shifting today:

- thin profile/self context;
- incomplete empirical model sweep;
- local model answers still sound generic;
- tool usage is early;
- reflection loop is not yet automatic or deeply evaluative;
- RAG/CRT hybrid baseline remains unfinished.

What can get it closer:

1. Context Bridge.
2. Reliable tool scaffolding.
3. Reflection/retry loop for thin answers.
4. Better profile/project summaries.
5. A small set of daily workflows that feel genuinely useful.

## Suggested next order in the new thread

Recommended next sequence:

1. Implement Context Bridge backend.
2. Add tests for profile/self context.
3. Run backend tests.
4. Run Workbench UI tests/build if prompt/API types change.
5. Manually test these queries in the client:

   - “What do you know about me?”
   - “How do you know me?”
   - “What are we building?”
   - “How are you designed?”
   - “What tools can you use?”

6. Then fix the dev runner port/cache issue.
7. Then continue local coder milestone:

   - add safe configured test execution;
   - improve patch review UI;
   - add reflective retry when local answer contradicts tool output.

## Caution for next thread

The worktree is dirty and contains many untracked or generated artifacts. Do not clean/reset casually.

Avoid:

- `git reset --hard`;
- deleting release folders;
- assuming untracked files are disposable;
- reviving legacy `frontend/App.tsx` or `crt_api.py` as the Workbench path.

Prefer:

- focused diffs;
- tests before packaging;
- preserving user changes;
- treating `aether-core` + `workbench` as the current product lane.

## Immediate restart prompt for a new thread

Use this if opening a clean Codex thread:

```text
We are in D:\AI_round2. Read docs/plans/AETHER_CRT_WORKBENCH_HANDOFF_2026-06-23.md.

Continue Aether Workbench by implementing the Context Bridge:
- add governed profile/self context for identity, profile, project, and self questions;
- inject it into chat prompt and trace;
- preserve governance: confirmed safe facts only, no conflicted/provisional/quarantined leakage;
- add focused tests;
- run backend tests.

Do not revive the legacy frontend/API. Work in aether-core and workbench only if needed.
```


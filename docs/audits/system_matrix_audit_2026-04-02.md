# System Matrix Audit — 2026-04-02

This audit translates the recent continuity notes and codebase state into a blunt subsystem matrix.

It is not a purity document. The current "lab inside the production body" shape is treated as a **phase condition**, not a moral failure. The point of this audit is to identify where boundary tightening now buys the most leverage for the next phase.

Primary context sources:
- `C:\Users\block\.claude\projects\D--AI-round2\memory\session_2026_04_01_agent_loop.md`
- `C:\Users\block\.claude\projects\D--AI-round2\memory\session_2026_04_01_pipeline_fixes.md`
- `C:\Users\block\.claude\projects\D--AI-round2\memory\project_agentic_pipeline.md`
- `C:\Users\block\.claude\projects\D--AI-round2\memory\strategy_repo_split.md`

## Executive Summary

The system is now crossing from fused solo iteration into product/runtime territory.

What is strong:
- governed memory and contradiction preservation
- belief/speech separation as a real design spine
- agent loop with plan, followups, spawn-agent capability, and pipeline visibility
- user belief work that matches the business thesis

What is fragile:
- runtime state still lives in the repo tree
- `routes/chat.py` and the orchestrator carry too much load
- SSE/WS event contracts are still drifting
- task lifecycle exists, but not yet as one explicit primitive

The highest-ROI work now is **not more feature variety**. It is boundary tightening that makes the next 3-5 features cheaper and safer to add.

## Highest ROI Order

### Tighten Now

1. **Externalize runtime state**
   - Why first: this is the cleanest operational win and the clearest repo-health risk.
   - Evidence: live DBs and backups still sit under `personal_agent/`, including very large runtime stores.

2. **Freeze the event contract**
   - Why second: the SSE/WS/frontend pipeline is now the system's nervous system.
   - Evidence: recent fixes hit missing handlers, wrong transport path, summary persistence, duplicate rendering, and UI crashes.

3. **Make task lifecycle first-class**
   - Why third: suspend/resume, followup, spawn-agent, proactive turns, and auto-continuation are all the same family.
   - The missing object is a real governed task lifecycle, not more ad hoc branching in `chat.py`.

4. **Split `routes/chat.py` by responsibility**
   - Why fourth: too much system risk is concentrated in one module.
   - Do this after the event/task boundaries are explicit enough to split cleanly.

5. **System acceptance suite**
   - Why fifth: you already have many unit/integration tests. What is missing is end-to-end proof for the live critical flows.

### Do Next, After Tightening

6. **Auto-continuation**
   - Worth doing, but better on a cleaner task/event foundation.

7. **Belief-aware worker handoff packets**
   - High strategic value; depends on task lifecycle clarity.

8. **Proactive turns / WS registry**
   - Strong feature, but dangerous before task state and auth boundaries are cleaner.

9. **Learned routing from run logs**
   - Worth pursuing once the runtime emits cleaner, more stable labels and outcomes.

### Sort Out Later

10. **Broader repo split extraction**
    - Important, but should follow the first round of boundary hardening, not precede it.

11. **Research repo disentangling**
    - Necessary eventually, but lower ROI than runtime, event, and task boundaries.

12. **Channel polish and secondary integrations**
    - Useful, but not the highest leverage while core orchestration boundaries are still moving.

## Matrix

| Subsystem | Current State | ROI | Tighten Now or Later | Move to `crt-core` or Keep Private | Why |
|---|---|---:|---|---|---|
| Memory / governance core | **Solid** | High | Later | Mixed | Strongest part of the system conceptually; generic lifecycle/trust pieces should migrate, runtime wiring should not |
| Orchestrator / task runtime | **Fragile but valuable** | Very High | **Now** | Mixed | Real feature value already, but lifecycle is still distributed across orchestration, chat route, and frontend event handling |
| Chat pipeline | **Fragile** | Very High | **Now** | Keep private | Too much routing, fallback, streaming, and orchestration logic in one place |
| Frontend / event bus | **Fragile** | High | **Now** | Keep private | Powerful pipeline UI, but transport/event contract is still drifting |
| Beliefs / reversed CRT | **Experimental but promising** | High | Soon | Mixed | Strategic direction is good; protocol/data shapes can move later, product wiring should stay private |
| Databases / runtime state | **Fragile** | Very High | **Now** | Keep private | Runtime data embedded in repo tree is an operational liability |
| Channels / integrations | **Mixed** | Medium | Later | Keep private | Useful, but not the main leverage point right now |
| Evaluation / testing | **Good but incomplete at system level** | High | **Now** | Mixed | Strong test volume, weak system acceptance closure |
| Research modules | **Experimental** | Medium | Later | Mixed | Valuable intellectual substrate, but not first-order runtime risk |
| Repo structure / split | **Conceptually ready, operationally incomplete** | High | Soon | N/A | Clear strategy exists; implementation should follow after the first hardening pass |

## Subsystem Detail

### 1. Memory / Governance Core

**State:** Solid  
**Why:** This remains the strongest architectural spine:
- authority-weighted memory
- contradiction preservation
- belief/speech separation
- compaction governed by trust intent rather than raw summary convenience

**Tighten now?** Not first.  
The core ideas are not the current bottleneck.

**What to do next:**
- keep stabilizing interfaces, not reinventing the theory
- identify generic trust/lifecycle/protocol pieces that can leave the private repo cleanly

**Should move to `crt-core`:**
- contradiction lifecycle abstractions
- trust evolution primitives
- belief packet / governed task data structures
- generic governance interfaces

**Should stay private:**
- prompt prefix / epistemology axioms
- storage wiring
- provider/model wiring
- product-specific retrieval/routing policy

### 2. Orchestrator / Task Runtime

**State:** Fragile but valuable  
**Why:** The agent loop is now real:
- plan
- followups
- spawn-agent path
- pipeline visualization
- suspend/resume scaffolding

But the lifecycle is still spread across multiple codepaths and conventions.

**Tighten now?** Yes. This is one of the top three ROI items.

**Needed tightening:**
- define an explicit governed task primitive
- unify suspend/resume/checkpoint/followup/continuation under one lifecycle model
- stop growing the system via special-case branches only

**Do:**
- formalize task state, remaining budget, authority ceiling, checkpoint policy, output stream state

**Don't:**
- add more orchestration power before the lifecycle boundary is explicit

**Move to `crt-core`:**
- `GovernedTask` style data structures and lifecycle state enums
- belief/constraint packet contracts

**Keep private:**
- actual orchestrator loop wiring
- provider-specific brains
- UI-driven checkpoint behavior

### 3. Chat Pipeline

**State:** Fragile  
**Why:** `routes/chat.py` is now a load-bearing wall.

It currently carries:
- routing
- stream plumbing
- fallback generation
- orchestrator execution
- suspend/resume branching
- followup and event emission

That is too much systemic risk in one module.

**Tighten now?** Yes.

**Needed tightening:**
- split by responsibility, not by arbitrary line ranges
- likely cuts:
  - routing gate
  - stream/event plumbing
  - orchestrator runner
  - legacy/fallback generation
  - suspended-loop resume handlers

**Do:**
- preserve behavior while reducing concentration risk

**Don't:**
- do a giant style refactor
- try to "clean up everything"

**Move to `crt-core`:**
- none of the actual route wiring

**Keep private:**
- all route plumbing and request/stream integration

### 4. Frontend / Event Bus

**State:** Fragile  
**Why:** The pipeline panel is good and valuable, but the contract under it is still moving.

Recent fixes show drift in:
- missing event handlers
- wrong transport path
- duplicate rendering
- summary persistence
- defensive UI guards

**Tighten now?** Yes.

**Needed tightening:**
- one typed event contract shared across backend/frontend concepts
- freeze event names, payload shapes, and semantics
- make "phase", "thinking", "tool", "epistemic", "followup", "done" stable

**Do:**
- treat the event contract like an API, not glue

**Don't:**
- keep adding event variants ad hoc

**Move to `crt-core`:**
- none of the UI/event transport wiring

**Keep private:**
- SSE/WS handlers, React components, pipeline visualization

### 5. Beliefs / Reversed CRT

**State:** Experimental but promising  
**Why:** This is strategically aligned and now partially shipped:
- `user_belief` kind
- extraction path
- `/api/beliefs`
- emerging beliefs UI

**Tighten now?** Soon, but not before runtime/task/event boundaries.

**Needed tightening:**
- keep belief vs fact surfaces explicit
- protect against cross-channel overwrite/confusion
- avoid overfitting product claims before the surface is proven

**Do:**
- treat this as a product wedge, not just another memory subtype

**Don't:**
- let beliefs silently behave like facts

**Move to `crt-core`:**
- belief classification interfaces
- generic belief/position data structures

**Keep private:**
- UI, extraction wiring, persistence strategy, product surfaces

### 6. Databases / Runtime State

**State:** Fragile  
**Why:** The repo is still carrying live state and backups in the source tree.

This is the clearest operational tightening target.

**Tighten now?** Yes. First.

**Needed tightening:**
- explicit runtime data root
- config-driven DB paths
- keep repo tree for code and docs, not live state
- backup strategy outside the source tree

**Do:**
- separate source from mutable runtime artifacts

**Don't:**
- defer this until after more features

**Move to `crt-core`:**
- none

**Keep private:**
- all live DBs, runtime artifacts, run logs, experiment data

### 7. Channels / Integrations

**State:** Mixed  
**Why:** Some are live and useful, some are secondary, some are brittle.

**Tighten now?** Later, unless a channel is directly blocking the product surface.

**Needed tightening later:**
- cross-channel authority and injection boundaries
- auth consistency
- runtime isolation between channels

**Do:**
- keep channel policy explicit

**Don't:**
- spend main-cycle time polishing secondary integrations before core boundaries are hardened

### 8. Evaluation / Testing

**State:** Good volume, incomplete closure  
**Why:** There are many tests and lots of instrumentation, but system acceptance is still weaker than component coverage.

**Tighten now?** Yes.

**Needed tightening:**
- one top-level acceptance suite covering:
  - conversational turn
  - orchestrated task
  - ask-user suspend/resume
  - followup/continuation
  - contradiction surfacing
  - beliefs retrieval
  - proactive event delivery

**Do:**
- define a small number of end-to-end golden paths

**Don't:**
- confuse more unit tests with system closure

**Move to `crt-core`:**
- generic governance test fixtures later

**Keep private:**
- product/runtime acceptance suites

### 9. Research Modules

**State:** Experimental  
**Why:** Valuable and real, but not the current runtime bottleneck.

**Tighten now?** Later.

**Needed tightening later:**
- clearer separation between production-governing code and exploratory modules
- extraction path for generic reusable theory-backed modules

**Do:**
- preserve research momentum without forcing premature integration

**Don't:**
- let research module sprawl determine production boundaries

### 10. Repo Structure / Split

**State:** Conceptually ready, operationally incomplete  
**Why:** The split strategy is good; the implementation has not caught up.

**Tighten now?** Soon, but after runtime/event/task boundaries are slightly cleaner.

**Needed tightening:**
- start with protocol/interface extraction, not giant code migration
- move only stable reusable pieces first

**Do:**
- enforce the split through actual code movement once interfaces are clean enough

**Don't:**
- try to extract from unstable modules mid-rewrite

## Recommended Sequencing

### Phase A — Tighten the load-bearing boundaries

1. Externalize runtime state
2. Freeze event contract
3. Define task lifecycle primitive
4. Split `routes/chat.py`
5. Add system acceptance suite

### Phase B — Resume agent-loop feature growth

6. Auto-continuation
7. Child plan budget fix
8. Belief-aware worker handoff packets
9. Proactive turns / WS registry
10. Learned routing from run logs

### Phase C — Enforce the repo/product split

11. Extract generic lifecycle/trust/governance protocols to `crt-core`
12. Keep provider wiring, prompts, frontend, DBs, orchestrator implementation, and integrations private

## Blunt Bottom Line

The system does **not** need a giant cleanup pause.

It **does** need a short hardening phase before more agent-loop power is added.

The reason is simple:
- before: fused iteration was efficient
- now: the same fusion is becoming operational debt

This is a **phase transition**, not a failure of discipline.

The highest ROI work is boundary work that makes the next features cheaper:
- data boundary
- event boundary
- task boundary
- route/module boundary
- repo boundary

If those are tightened, the next wave of agent-loop features will land faster and with fewer regressions.

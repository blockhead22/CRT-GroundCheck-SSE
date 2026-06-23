# Aether Personal Operations Agent — Product and Architecture Scope

## Purpose

Extend Aether Workbench from a governed memory/chat/coder sidecar into a local
personal operations companion that can:

- help plan a day;
- capture outcomes and corrections;
- reflect on its own assistance quality;
- propose evidence-backed patterns about the user, workflow, or projects;
- run small, reversible assistance experiments;
- remain inspectable and correctable through CRT governance.

The system is not a therapist, diagnostician, surveillance product, or
unrestricted autonomous agent.

## Product thesis

A useful personal companion needs two distinct reflective loops.

### Agent reflection

Evaluate whether Aether's own strategy helped:

```text
goal
  -> chosen intervention
  -> user response
  -> observed outcome
  -> reflection
  -> proposed strategy adjustment
```

It learns assistance strategies, not personality judgments.

Examples:

- A smaller next action worked better than repeating the same reminder.
- Direct wording helped with exercise but annoyed the user during overload.
- The reminder arrived after the task was no longer relevant.
- A local model could have handled a task that was escalated.
- The system misunderstood the priority and should ask earlier next time.

### Personal reflection

Propose potentially useful patterns while separating evidence from
interpretation:

```text
Observation:
Five administration tasks were postponed this week.

Possible interpretations:
The next actions may be unclear, tedious, emotionally expensive, or simply
lower priority.

Question:
Would you like to inspect what is blocking them?
```

Aether may notice changes and ask. It must not diagnose depression, mania,
burnout, addiction, laziness, self-sabotage, or other high-stakes conditions.

## First-class reflection record

```yaml
reflection_id:
subject: agent | user | workflow | project
observation:
supporting_evidence:
alternative_explanations:
confidence:
time_window:
suggested_experiment:
user_response:
status: proposed | accepted | rejected | superseded
created_at:
reviewed_at:
```

Required rules:

- `observation` must describe evidence, not interpretation.
- Every interpretation must include alternatives.
- Confidence must remain provisional until user-confirmed or repeatedly
  supported.
- Rejection is preserved as history and prevents silent resurrection.
- Accepted reflections do not automatically become permanent profile facts.
- Reflections expire or require review when their evidence window becomes old.

## Existing components to reuse

- `aether-core` slot substrate for current/history/conflict/quarantine state.
- `workbench.db` for conversations, documents, traces, tool runs, and receipts.
- Local Qwen through Ollama for bounded classification and summarization.
- Manual Codex escalation for difficult reviews.
- Workbench Trace and Memory drawers for visible evidence and correction.
- Existing idempotency and stale-state patterns.
- Coder tool receipts as the model for intervention and experiment receipts.

## New bounded data model

### Goals and actions

- `goals`: desired outcomes, priority, status, due window, provenance.
- `action_items`: smallest next action, optional/required, estimate, outcome.
- `daily_plans`: selected actions and the evidence used to select them.

### Interventions

- `interventions`: reminder, reframing, question, task reduction, or silence.
- Store strategy, timing, evidence, user response, and outcome.
- No intervention may rewrite memory or strategy state directly.

### Reflections

- `reflections`: governed hypothesis records described above.
- `reflection_evidence`: links to turns, actions, interventions, or explicit
  user statements.
- `reflection_reviews`: accept, reject, revise, defer.

### Experiments

- `experiments`: hypothesis, bounded duration, strategy variants, measurement,
  consent, status, and result.
- Experiments must be reversible and visible.
- No covert A/B testing.

### Strategy profiles

- `strategy_hypotheses`: examples such as direct, encouraging, reduce-scope,
  ask-first, or do-not-interrupt.
- Learned per context and consequence level.
- Never represented as universal personality truth.

## Reflection pipeline

```text
Events and explicit statements
  -> deterministic candidate extraction
  -> evidence aggregation
  -> local-model reflection draft
  -> policy and high-stakes filter
  -> CRT provisional reflection
  -> visible user review
  -> accepted, rejected, revised, or expired
```

The local model drafts language. It does not decide truth or mutate strategy.

## Attitude-change handling

Attitude is a time-bounded signal:

```yaml
topic: CRT
prior_orientation: curious and motivated
recent_orientation: frustrated and doubtful
evidence_window: 7 days
confidence: moderate
possible_causes:
  - disappointing results
  - fatigue
  - competing priorities
  - genuine priority change
recommended_action: ask, do not assume
```

The product should say:

> You have sounded more frustrated with CRT this week. I cannot tell whether
> that is fatigue or a genuine priority change. Should I reduce its priority,
> simplify the next step, or leave it alone tonight?

## User experience

Add one **Reflect** drawer to Workbench:

- today's outcomes;
- one proposed agent reflection;
- one proposed personal/workflow reflection;
- evidence and alternatives;
- Accept, Reject, Revise, or Try Experiment;
- reflection history and supersession.

Later, add a Today surface:

- one required action;
- up to two optional actions;
- capture Done, Reduced, Postponed, Irrelevant, or Wrong Priority;
- optional note explaining the outcome.

## Safety and privacy contract

- Local-first storage.
- No background monitoring of unrelated applications in v1.
- No sentiment diagnosis.
- No medical or mental-health conclusions.
- No covert behavior scoring.
- No permanent trait inference from temporary behavior.
- No automatic frontier calls.
- No automatic strategy or system-prompt rewriting.
- No scheduling or notifications until passive reflection is validated.
- Every proactive intervention must eventually be attributable to evidence and
  a visible strategy.

## Non-goals

- Rebuilding a complete Claude Code, Codex, or OpenAI harness.
- Autonomous multi-agent work.
- Desktop control.
- Email/calendar integration in the first reflection release.
- Health diagnosis or crisis detection.
- Gamified productivity scoring.
- Automatic punishment, pressure, or escalating reminders.

## Minimum proof

The first release succeeds when:

1. A user records a plan and outcomes for several days.
2. Aether proposes one evidence-backed reflection.
3. Evidence and alternative explanations are visible.
4. The user can reject it and it stays rejected.
5. Aether proposes one reversible strategy experiment.
6. The result updates a strategy hypothesis without becoming a personality fact.
7. Agent reflection identifies one poor intervention and recommends a safer
   adjustment.


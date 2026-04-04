# Local Capability Lab

## Objective

Determine whether a smaller local model can remain useful when CRT supplies:

- external memory
- tool access
- task structure
- governed continuity

The goal is not to prove that a small model can replace a stronger one. The goal is to measure whether the system can extend a smaller local model enough that it remains viable for day-to-day personal-agent work without immediately escalating to a larger model.

## Core Question

Can Aether make a local model act like a reliable mouth over system-held state, instead of treating model size as the only path to competence?

## Hypotheses

1. A small local model will perform better when the system supplies the right memory and tool context than when it is asked to reason from the prompt alone.
2. Explicit memory/tool access is more important than raw prompt length for many personal-agent tasks.
3. The right failure mode is not "auto dump to a larger model," but "stay local, expose limits, and only escalate when the task genuinely requires stronger reasoning."

## Success Criteria

For a local-only run, we want evidence that the system can:

- answer using seeded internal memory
- call local tools when the task requires them
- preserve thread continuity without cloud fallback
- expose whether the answer came from memory/tool use or from weak direct generation

## Initial Test Set

### 1. Memory Grounding

Seed a few internal memories, then ask questions that require recalling them.

Pass condition:
- answer references the seeded memory correctly

Stretch condition:
- stream shows memory-related evidence or tool usage instead of pure guessing

### 2. Explicit Memory Recall Tool

Ask for something in a way that should encourage `memory_recall`.

Pass condition:
- `tool_start` / `tool_result` events show `memory_recall`

### 3. Local File Tooling

Ask the system to inspect a repo file and answer from it.

Pass condition:
- `tool_start` shows a file or project tool
- final answer cites actual repo content rather than generic filler

### 4. Continuity Under Local Constraints

Ask a follow-up that depends on prior thread state.

Pass condition:
- the follow-up is grounded in the earlier local interaction

## What This Lab Is Not

- It is not a benchmark claiming small models equal frontier models.
- It is not a "prompt stuffing" experiment.
- It is not a cloud-fallback optimization exercise.

## What We Are Measuring

- local answer quality
- local tool-call reliability
- memory grounding quality
- continuity quality
- failure mode quality

## Good Failure

A good local failure looks like:

- the system stays local
- the model admits limits
- the trace shows whether memory/tools were attempted

A bad failure looks like:

- silent cloud escape
- generic filler
- fake confidence
- no evidence of retrieval/tool use

## First Runnable Harness

Use:

```powershell
python tools/local_capability_lab.py --scenario smoke
```

This harness:

- configures local-only settings
- seeds a few memories
- runs local chat-stream experiments
- records tool events and final responses

## Next Research Direction

If this lab shows promise, the next phase is not "bigger fallback routing." It is:

- better external attention
- better compression and memory surfacing
- better task decomposition for small local models
- explicit escalation only for operations that truly exceed local reasoning capacity

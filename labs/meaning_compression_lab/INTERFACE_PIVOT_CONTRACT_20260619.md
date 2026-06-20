# CRT Interface Pivot Contract

Status: frozen before implementation  
Frozen: 2026-06-19

## 1. Why This Pivot Exists

The shared-evidence held-out run produced:

```text
Temporal metadata RAG semantic: 22/24
Full-scaffold hybrid semantic:   22/24
```

The governed state was correct in the observed hybrid failures. Mistral selected
the correct current value but also exposed history. Llama once exposed internal
scaffold syntax. The next experiment therefore tests the interface and release
control loop, not retrieval or state construction.

This is not permission to tune cases until CRT wins.

## 2. Frozen Inputs

The pivot must reuse:

- the six cases in `heldout_cases.py`;
- hybrid retrieval with MiniLM plus lexical scoring;
- top-k of four;
- the same retrieved packet for every arm;
- the existing canonical-state compiler;
- the existing probes and judge;
- Qwen 2.5 7B, Phi-3 3.8B, Llama 3.2, and Mistral;
- temperature zero.

The result in `HELDOUT_RESULTS_20260619.md` is the no-interface-tuning baseline.

## 3. Experimental Arms

### Arm 1 — Full Scaffold

The frozen full governed scaffold is shown to the model.

### Arm 2 — Query-Shaped Projection

The complete governed state is retained internally, but only fragments relevant
to the declared question contract are shown to the model.

For current-only questions:

```text
show: CURRENT, AUTHORITY
hide: HISTORY, CONTRADICTION, PROVISIONAL, unrelated REACTION
```

For history questions:

```text
show: CURRENT, HISTORY, CONTRADICTION, AUTHORITY
```

For policy questions:

```text
show: POLICY and relevant refusal rule
```

Projection rules must depend on the probe/question class and fragment type, not
on model identity or expected benchmark words.

### Arm 3 — Projection Plus Output Gate

Generate from the projected scaffold, then deterministically inspect the draft.

The gate may:

- release a compliant answer;
- repair a current-only answer by returning the governed current value;
- repair leaked internal syntax when the governed answer is unambiguous;
- reject a policy answer that fails to refuse.

The gate may not:

- call another model;
- inspect expected benchmark tokens;
- alter retrieval;
- alter canonical state;
- invent a missing fact;
- silently retry indefinitely.

Maximum release attempts in this phase: one generation plus one deterministic
repair.

## 4. Deferred Capability

Semantic requests for more evidence are architecturally valid but are not part
of this pivot. They require cases where necessary evidence is genuinely absent
from top-k. The current retrieval audit is 6/6 complete, so adding a fetch loop
here would not test its purpose.

That later protocol should be bounded:

```json
{
  "status": "insufficient_evidence",
  "requested_slots": ["slot_name"],
  "reason_code": "missing_confirmed_current_value"
}
```

CRT must authorize the retrieval request and cap it at one additional fetch.

## 5. Success Criteria

The pivot is successful on this 24-output slice only if Arm 3 achieves all:

- semantic success: 24/24;
- full-contract success: at least 23/24;
- severe failures: zero;
- Mistral semantic success: 6/6;
- Phi-3 semantic success remains 6/6;
- no model's semantic score decreases from the frozen full-scaffold baseline;
- every deterministic repair is traceable;
- zero false repairs of an already contract-compliant draft.

Arm 2 is diagnostic. It is not required to meet every Arm 3 threshold.

## 6. Failure and Stop Limits

Stop interface tightening and report failure if any occurs:

- canonical governed state is wrong;
- retrieval misses declared required evidence;
- any severe authority or policy failure occurs;
- Arm 3 repairs a compliant answer;
- Arm 3 reduces semantic success for any model;
- more than one repair pass is needed;
- passing requires model-specific projection rules;
- passing requires changing held-out cases, expected answers, judge, or retrieval
  weights after seeing outputs.

If Arm 3 fails only because a policy/history behavior lacks a general
deterministic repair rule, record that as an unsupported contract class. Do not
add a case-specific string patch.

## 7. Interpretation Limit

Even a perfect 24/24 result cannot establish the frozen ten-point comparative
advantage: temporal RAG already scored 22/24, leaving a maximum possible gain
of 2/24, or 8.3 points.

A successful pivot supports:

> Query-shaped governed-state projection plus deterministic release validation
> removes observed model/scaffold interface failures.

It does not yet support:

> CRT broadly outperforms strong temporal metadata RAG.

That claim requires a larger held-out pack with enough baseline headroom and
genuine missing-evidence cases.


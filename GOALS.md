# Goals

This file is the persistent, high-signal goals list for CRT.

## Success definition (current)

CRT is “successful” for this phase when:

- Questions do not create new user memories or contradictions.
- Contradictions are created primarily by conflicting assertions about the same claim.
- Reinforcement converges (no uncertainty/refusal loops when evidence is consistent).
- The system does not fabricate identity facts without user evidence.
- A 30-turn run produces stable artifacts and repeatable metrics.

## Now (stabilization)

- Reduce false contradictions (question vs assertion, claim-level matching).
- Reduce refusal/uncertainty loops (deterministic clarify → resolve → converge path).
- Improve contradiction “type” handling (refinement/temporal vs true conflict).
- Add regression checks for hallucinated identity (name/title/employer).

## Next (if stabilization is successful)

- Freeze an evaluation baseline:
  - Track: false-contradiction rate, convergence time, hallucination rate, uncertainty-loop rate.
  - Add CI smoke runs (short, deterministic controller + seeded randomness).
- Introduce typed claims (minimal schema first):
  - identity.name, work.employer, work.title, location.city, education.masters_school.
  - Contradiction detection becomes slot-based, not pure semantic drift.
- Strengthen provenance:
  - Make source categories explicit (user-said vs tool-output vs doc vs system-generated).
  - Produce "evidence packets" for inspectability and audit.

## After (productization / OSS direction)

- Package CRT as a provider-agnostic library:
  - Pluggable LLM client, memory store, ledger store.
  - Stable response envelope schema.
- Open-source in layers:
  - First: eval harness + artifact schemas + inspector UI.
  - Later: default policies/heuristics (once stable and defensible).

## Parking lot

- Reflection agent for resolving contradictions and merging beliefs.
- Learned conflict-resolution patterns (NN/ML research): model how users and the assistant respond to contradictions over time, detect shifts in user responses, and offer suggestion-only guidance based on prior similar contradiction scenarios. The system should not auto-edit beliefs; it proposes clarifications/actions while preserving the contradiction record.
- Better UI inspector (timeline view of trust evolution + contradiction graph).
- Multi-agent shared ledger experiments.

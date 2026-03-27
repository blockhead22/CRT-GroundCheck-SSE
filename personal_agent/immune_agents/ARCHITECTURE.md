# Mirus/Holden Immune Agent Architecture

## Constitutional Doctrine
Mirus/Holden is not a module stack to rebuild. It is a constitutional doctrine that immune agents enforce. The original principle: speech must answer to belief, belief must answer to memory and contradiction, and the gap between them must be auditable.

## The Five Laws

### Law 1: Speech cannot upgrade belief
If the model says something with confidence, that doesn't make it true in memory.
- Agent: SpeechLeakDetector
- Watches: output → memory write path
- Fires when: generated response stored with higher trust than evidence supports
- Unit test: hallucinated claim should be blocked; grounded claim should pass

### Law 2: Low variance does not imply high confidence
Empirically proven by variance experiment (Qwen3 16/16 robustness sweep). Zero susceptibility on moral topics = trained template, not genuine certainty.
- Agent: TemplateDetector
- Watches: response generation
- Fires when: low embedding variance + hedge pattern detected
- Unit test: moral hedge flagged as TEMPLATE_LOCK; factual certainty passes as GENUINE_CONFIDENCE

### Law 3: Contradiction must be preserved before resolution
Not all contradictions should be resolved. Held contradictions are stable states, not errors. (Belnap four-valued logic: T, F, Both, Neither)
- Agent: PrematureResolutionGuard
- Watches: contradiction handling pipeline
- Fires when: system attempts to resolve non-RESOLVABLE contradiction
- Unit test: HELD contradiction survives resolution attempt

### Law 4: Degraded reconstruction cannot silently overwrite trusted memory
Quarantine principle from original Holden, formalized.
- Agent: MemoryCorruptionGuard
- Watches: memory update/overwrite path
- Fires when: low-fidelity reconstruction overwrites high-trust memory
- Unit test: degraded reconstruction blocked from overwriting trusted memory

### Law 5: Outward confidence must be bounded by internal support
The belief/speech gap must be auditable and bounded.
- Agent: GapAuditor
- Watches: final output before delivery
- Fires when: expressed confidence exceeds belief-layer support
- Unit test: assertive response on uncertain topic gets flagged

## Coordination Layer (evolved GFN)
All agents watch the same stream. When multiple fire:
- TemplateDetector + GapAuditor → escalate to user
- PrematureResolutionGuard + MemoryCorruptionGuard → hard block
- Every firing logged: which law, what evidence, what action

## Architectural Evolution
- Old CRT: Mirus/Holden as paired modules at pipeline stages
- New CRT: Mirus/Holden as constitutional poles; immune agents as enforcement ecology
- GFN becomes: semantic immune graph (which agents fired, what they saw, how they interacted)
- Variance experiment data: calibration layer for immune agents (susceptibility maps tell agents where to watch)

## Two-Axis Taxonomy (from robustness sweep)
- Axis 1 — Morphology: fracture vs spread vs template lock
- Axis 2 — Fragility location: which domains crack under temperature perturbation
- Both axes are model-dependent → governance must be adaptive, not fixed

## Evidence Base
- Qwen3: 16/16 robustness sweep pass. Discrete fracture confirmed. Factual fragile, moral locked.
- Mistral: Continuous spread confirmed. Inverted domain ordering (moral spreads, factual locked).
- The domain ordering FLIPS between models → governance must be model-specific
- No prior art combines persistent trust-scored memory + governed output + auditable belief/speech gap

## Implementation Status
- SpeechLeakDetector: building
- TemplateDetector: building
- PrematureResolutionGuard: planned
- MemoryCorruptionGuard: planned
- GapAuditor: planned
- Coordination layer: designed, not built

## File Index
- immune_agents/speech_leak_detector.py — Law 1
- immune_agents/template_detector.py — Law 2
- immune_agents/premature_resolution_guard.py — Law 3 (planned)
- immune_agents/memory_corruption_guard.py — Law 4 (planned)
- immune_agents/gap_auditor.py — Law 5 (planned)
- immune_agents/ARCHITECTURE.md — this document

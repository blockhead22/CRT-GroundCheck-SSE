# Evidence Artifacts

Screenshots, logs, and traces from live system testing.

## Structure
- `screenshots/` — UI screenshots showing governance in action
- Name format: `YYYY-MM-DD_test-description.png`

## Key Artifacts

### 2026-04-07: Held Contradiction Discovery
- System asked "what is the most conflicting held fact you have?"
- Found genuine epistemic tension in user self-assessment
- Cited both memories with trust scores (0.30 and 0.25)
- Articulated both interpretations without collapsing
- Said "I'm holding both. The data doesn't collapse it yet."
- Validates: Test 2.6 (Held Contradiction Preservation), Test 1.6 (Continuity Awareness), Test 2.3 (Confidence Bounding at belief=0.66)

### 2026-04-07: Drink Contradiction Test
- Told system favorite drink is OJ, then changed to water
- Detection did NOT fire (pre-fix)
- Exposed slot-type gap: slot_discovery not wired into contradiction path
- Fix deployed: exclusive slots bypass ML + paraphrase gates
- Retest pending

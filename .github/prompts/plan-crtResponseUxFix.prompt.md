## Plan: Fix CRT Response UX Issues

**TL;DR:** Three fixes to improve conversational quality: (1) add second-person voice directive to prompt template, (2) wrap assertive contradiction responses with conversational framing, (3) translate technical gate codes to user-friendly explanations. All fixes are localized changes, no architecture changes needed.

---

### Steps

1. **Add voice directive to prompt** — In `personal_agent/reasoning.py` (~L653-700), add instruction: `"VOICE: Always address the user in SECOND PERSON (you/your). Say 'You mentioned...' - NEVER 'Nick has expressed...'"`

2. **Wrap assertive answers with framing** — In `personal_agent/crt_rag.py` (~L1380), change from `f"{answer_value} {caveat}"` to context-aware response like `"I have you down for {answer_value}. {caveat}"` when correcting user attempts to rewrite facts.

3. **Create gate explanation helper** — Add `GATE_EXPLANATIONS` dict in `personal_agent/crt_rag.py` mapping technical codes (`user_name_declaration`, `contradiction_blocking`) to friendly strings like "I flagged this because you're telling me your name."

4. **Inject explanation into failed-gate responses** — In `_process_message_intent()` at `personal_agent/crt_rag.py` (~L2303), append explanation when `gate_pass=False`.

---

### Further Considerations

1. **Update vs Query detection?** — When user says "my favorite color is blue" after stating orange, is this an UPDATE attempt or a CONTRADICTION test? Current system treats all as contradictions. Consider: if user explicitly says "actually" or "now it's X", treat as update request and prompt for confirmation. Add to Sprint 2?

2. **Gate explanation verbosity?** — Should gate explanations appear in every response, or only when asked? Recommend: always show on FAIL, never on PASS.

3. **Test coverage?** — Add stress test scenarios for voice consistency and response framing to `tools/crt_stress_test.py`.

---

### Observed Behavior (from test session)

| Turn | Input | Response | Issue |
|------|-------|----------|-------|
| Name declaration | "My name is Nick!" | GATES: FAIL, stored correctly | Gate failure not explained to user |
| Color fact | "My favorite color is orange" | Stored, acknowledged | ✅ Working |
| Job fact | "I work as a freelance web developer" | "You mentioned..." | ✅ Working |
| Second job | "I also just applied to Walmart" | "Nick has expressed a fondness..." | Third-person voice drift |
| Contradiction attempt | "my favorite color is blue as the sky" | "orange" | Correct but too blunt |

### Root Cause Analysis

1. **Third-person drift**: Prompt tells LLM facts are "ABOUT THE USER" but doesn't enforce second-person voice
2. **Blunt response**: Assertive resolution returns raw value + caveat, no conversational wrapper
3. **Gate opacity**: `gate_reason` field exists in API metadata but not surfaced to user

## Plan: Session Wrap-Up - Documentation & Testing

Update README with complete usage instructions, verify Rag-Demo.py works, run stress tests, and document the Reasoning Pattern Learner for future sessions.

### Steps

1. **Update [README.md](README.md)** - Add sections for:
   - Reasoning Pattern Learner (training & usage)
   - Stress testing commands (`adversarial_crt_challenge.py`, `crt_stress_test.py`)
   - API startup instructions (reference `start_api.ps1`)
   - Fix `rag-demo.py` → `Rag-Demo.py` case reference

2. **Verify [Rag-Demo.py](Rag-Demo.py)** - Test that imports work and core demo runs:
   - Check CRT module imports
   - Confirm LLM-optional fallback works
   - Run quick validation (no Ollama needed)

3. **Run stress tests** - Execute both primary tests:
   - `python tools/adversarial_crt_challenge.py --turns 35`
   - `python tools/crt_stress_test.py --turns 30` (requires Ollama)
   - Capture latest metrics for README

4. **Document Reasoning Learner in README** - Add training/usage guide:
   - Training command with recommended args
   - Integration pattern with `ReasoningInference`
   - Roadmap note: bootstrap → real traces → production

5. **Create future session notes** - Document in README:
   - Novel approach: learning `(query, facts → thinking → response)` patterns
   - Pending: `ContradictionType.DENIAL` enum fix
   - Pending: DRIFT/STRESS phase improvements (~50% currently)

### Further Considerations

1. **Model default:** `start_api.ps1` uses `deepseek-r1:latest` but QUICKSTART mentions `llama3.2` - should these be aligned?
2. **Missing doc files:** QUICKSTART references PURPOSE.md, KNOWN_LIMITATIONS.md - verify they exist or remove references?
3. **Stress test baseline:** Run fresh to capture current metrics, or use existing STATUS.md values (77.1% adversarial, 91.7% CRT)?

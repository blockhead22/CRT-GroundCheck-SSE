## Plan: Sprint 2 & Sprint 3 Roadmap

**TL;DR:** Sprint 2 wires the existing `ContradictionLifecycleManager` into persistence and API responses. Sprint 3 builds calibration infrastructure using the golden test set, replacing hard-coded thresholds with percentile-based routing. Both sprints leverage existing code - Sprint 2 is ~60% complete, Sprint 3 is ~30%.

---

### Sprint 2: Contradiction Lifecycle Integration (Est. 3-4 days)

1. **Persist lifecycle to database** — Add `read_lifecycle_state()` / `write_lifecycle_state()` to `personal_agent/crt_memory.py` using the existing `contradictions` table columns (`lifecycle_state`, `lifecycle_updated_at`).

2. **Wire `ContradictionLifecycleManager` into gate** — Integrate `personal_agent/contradiction_lifecycle.py`'s `LifecycleManager.should_disclose()` into `CRTMemory._check_contradiction_gate()` so settled contradictions skip disclosure.

3. **Add state transitions on confirmation** — When `store_memory()` detects a re-confirmation of an existing fact, call `LifecycleManager.record_confirmation()` to advance ACTIVE → SETTLING → SETTLED.

4. **Expose lifecycle in API responses** — Update `crt_api.py` `/query` response to include `contradiction_lifecycle_state` field (active/settling/settled/archived).

5. **Integrate `UserTransparencyPreferences`** — Wire the existing `TransparencyLevel` enum into user settings, allowing "minimal" / "balanced" / "audit_heavy" disclosure modes.

---

### Sprint 3: Calibration & Probability Curves (Est. 4-5 days)

1. **Build `ThresholdCalibrator` class** — New module in `personal_agent/calibration.py` that loads `groundcheck/tests/fixtures/golden_test_set.json` and computes percentile thresholds (P10, P50, P90) for each label type.

2. **Train logistic regression for P(valid)** — Use golden test pairs to fit `sklearn.LogisticRegression` mapping similarity scores → calibrated probability of correctness.

3. **Replace hard-coded thresholds** — Update `personal_agent/disclosure_policy.py`'s `DisclosurePolicy` to load percentile thresholds from calibration instead of `green_threshold=0.75`.

4. **Implement yellow zone routing** — In `personal_agent/crt_rag.py`, route medium-confidence facts (0.3–0.75) to clarification prompts instead of silent acceptance.

5. **Add calibration CLI** — Script `tools/calibrate.py` to re-run calibration on updated golden set and persist thresholds to `crt_runtime_config.json`.

---

### Further Considerations

1. **Sprint 2 vs Sprint 3 order?** — Sprint 2 can ship independently (lifecycle is self-contained). Sprint 3 depends on having solid lifecycle states to calibrate against. Recommend: Sprint 2 first.

2. **Inverse harness scope?** — The LLM self-monitoring concept from yesterday's discussion fits best as Sprint 4 (after calibration provides the probabilistic foundation). Add to backlog?

3. **Stress test updates?** — Should `tools/crt_stress_test.py` add lifecycle-specific assertions (e.g., "after 5 confirmations, contradiction should be SETTLED")? Recommend: Yes, add 3-5 lifecycle test scenarios.

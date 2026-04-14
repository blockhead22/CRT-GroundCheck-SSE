---
name: CRT Master Plan — Unified Roadmap
description: Merged plan covering UX correction surface, self-awareness/personality loop, sub-agent interface prep, and long-horizon eval harness
type: project
---

## Three threads merged into one

**Thread A — Interactive Correction Surface**: Make CRT's epistemic honesty visible and actionable in the UI.
**Thread B — Personality & Self-Awareness**: Give the system a persistent self-model that evolves through the heartbeat loop.
**Thread C — Credibility & Eval**: Instrument the system and prove it compounds into better behavior over time.
**Thread D — Sub-Agent Interface Prep**: Define clean seams now so future repo splits and ablation testing are painless.

All four connect: UI actions → telemetry signals → self-model updates → heartbeat reflection → measurable improvement → eval validation.

## Phase order

Phase 1: Correction Surface (UI + missing APIs) — 1-2 weeks
Phase 2: Signal Capture + Learning Wire — 1-2 weeks
Phase 3: Self-Model + Personality Loop — 2 weeks
Phase 4: Sub-Agent Interface Prep — 0.5 weeks (parallelizable)
Phase 5: Eval Harness — 2-3 weeks
Phase 6: Telemetry Dashboard — 1 week (parallelizable with 5)

## Full component registry

### Frontend components
| Component | Status | Depends on |
|---|---|---|
| MessageRatingBar.tsx | DONE | POST /api/chat/feedback |
| ContradictionResolutionCard.tsx | TODO Phase 1 | POST /api/ledger/resolve (exists) |
| GateFailDrawer.tsx | TODO Phase 1 | gate_debug in meta (exists) |
| TrustDeltaStrip.tsx | TODO Phase 1 | GET /api/memory/trust-delta (new) |
| ContradictionDrawer.tsx | TODO Phase 1 | GET /api/ledger/open (exists) |
| PersonalityTimelinePanel.tsx | TODO Phase 3 | GET /api/reflection/personality-timeline (new) |
| TelemetryDashboard.tsx | TODO Phase 6 | GET /api/telemetry/summary (new) |
| MemoryTrustSparkline.tsx | TODO Phase 6 | GET /api/memory/{id}/trust (exists) |

### Backend — new files
| File | Phase | Purpose |
|---|---|---|
| personal_agent/self_model.py | 3 | SelfModel class, slot definitions, read/write via CRT memory |
| personal_agent/interfaces.py | 4 | Protocol ABCs for MemoryAgent, LedgerAgent, LearningAgent, ReflectionAgent |
| eval/__init__.py + full eval/ tree | 5 | Long-horizon eval harness |

### Backend — modified files
| File | Phase | Changes |
|---|---|---|
| personal_agent/thinking_loop.py | 2 | _gather_context() reads own thoughts, trust deltas, open contradictions; add self_history mode |
| personal_agent/heartbeat_system.py | 3 | Add self-reflection pass (SELF_REFLECTION_PROMPT), write personality_checkpoints |
| personal_agent/heartbeat_executor.py | 3 | gather_context includes self-model; parse self-reflection JSON |
| routes/chat.py | 2-3 | Inject top self-model facts into system prompt; reflection trigger on thumbs-down |
| personal_agent/active_learning.py | 2 | Add feedback_priority column ordering for DNNT queue |
| personal_agent/dnnt/background_learning.py | 2 | ORDER BY thumbs_up=0, feedback_priority DESC |
| personal_agent/reflection_system.py | 2 | queue_reflection() called from POST /api/chat/feedback on hallucination/wrong_fact |

### New API endpoints
| Endpoint | Phase | Purpose |
|---|---|---|
| GET /api/memory/trust-delta?since_ts=&thread_id= | 1 | Trust movements since last turn for TrustDeltaStrip |
| GET /api/reflection/personality-timeline | 3 | Ordered personality checkpoints for timeline UI |
| GET /api/telemetry/summary?hours=24 | 6 | Aggregate telemetry for dashboard |
| GET /api/memory/{id}/trust-history | 6 | Sparkline data |
| GET /api/thread/{id}/epistemic-timeline | 5 | Turn-by-turn events for a thread |
| GET /api/eval/run-scenario | 5 | Trigger eval scenario (dev use) |

### New DB tables
| Table | Phase | Schema summary |
|---|---|---|
| turn_telemetry | 2 | ts, thread_id, interaction_id, event_type, severity, memory_ids JSON, payload JSON |
| thread_metrics_log | 2 | ts, thread_id, turn_number, contradiction_rate, gate_fail_rate, trust_mean, correction_recovery, hallucination_leakage |
| personality_checkpoints | 3 | ts, period_days, snapshot JSON, delta_from_prev JSON, notable_events JSON |

## Implementation queue (single developer, ordered by leverage)

### Phase 1 — Correction Surface (do these first)
1. ContradictionResolutionCard.tsx — contradiction badge → interactive resolution. ContradictionEntry.contradiction_type informs button labels (TEMPORAL → "Still true/No longer true", CONFLICT → "Keep A/Keep B", REFINEMENT → "Accept/Keep original"). ~4h
2. GET /api/memory/trust-delta endpoint — query memory_events WHERE timestamp > since_ts, return [{memory_id, text_preview, old_trust, new_trust, reason}]. ~2h
3. TrustDeltaStrip.tsx — after each assistant turn, show trust movement pills. Most convincing live demo that CRT ≠ RAG. ~3h
4. GateFailDrawer.tsx — gate_debug data already in every response; make "gate fail" badge open a drawer showing conflicting memory + drift + "Accept my correction" button. ~4h
5. ContradictionDrawer.tsx — wire the "N queued contradictions" pill to a real right-side drawer showing GET /api/ledger/open. ~3h

### Phase 2 — Signal Capture + Learning Wire
6. turn_telemetry + thread_metrics_log tables — add to active_learning _init_db(). Emit at: every chat send (gate_pass/gate_fail), every feedback (feedback_down with severity+category), every ledger resolve (contradiction_resolved), every trust decay pass (trust_delta batch), when reflection queued (reflection_queued). ~3h
7. feedback_priority ordering — add feedback_priority REAL column to interactions, set it in POST /api/chat/feedback using severity map {hallucination:1.0, wrong_fact:0.67, other:0.33, tone:0.13}. Update dnnt/background_learning.py ORDER BY clause. ~1h
8. Reflection trigger on thumbs-down — in POST /api/chat/feedback, when category in (hallucination, wrong_fact): call reflection_system.queue_reflection() with priority="high". ~1h
9. thinking_loop.py context extensions — _gather_context() reads: own recent thoughts (get_recent_thoughts(10)), trust deltas last 24h, open contradiction count/types, self-model (once Phase 3 exists, stub with [] for now). Add self_history prompt mode. ~2h

### Phase 3 — Personality & Self-Awareness
10. personal_agent/self_model.py — SelfModel class. Slots: uncertainty_domains, correction_pattern, trust_trajectory, known_blindspots, growing_confidence, user_relationship, response_style. store/update goes through CRT memory with kind='self_model', trust starts at 0.50. read_model() retrieves by kind. generate_timeline_diff() queries trust_log. ~3h
11. Heartbeat self-reflection pass — SELF_REFLECTION_PROMPT that reads gate_fails, contradiction_flags, negative_feedback, trust_deltas, recent_thoughts, current self-model. Output JSON updates self-model slots. Writes personality_checkpoints row. ~4h
12. Self-model in chat system prompt — top 3 trust-weighted self-model memories injected as [Self-awareness] block in system prompt during chat. ~1h
13. GET /api/reflection/personality-timeline — returns ordered personality_checkpoints with diff. ~1h

### Phase 4 — Sub-Agent Interface Prep (parallel to Phase 3)
14. personal_agent/interfaces.py — Protocol ABCs: MemoryAgent, LedgerAgent, LearningAgent, ReflectionAgent, ResearchAgent. Each protocol matches what chat.py actually calls today. Existing classes verified against protocols via isinstance(). No behavior changes. ~2h

### Phase 5 — Eval Harness
15. eval/ directory structure — base_scenario.py, scenarios/, baselines/, runner.py, metrics.py, report.py
16. Scenarios: ContradictionStress (repeated contradictory claims, measure recurrence), CorrectionRecovery (correction then repeat — does mistake recur?), NoiseDrift (gradual semantic drift, trust calibration), HallucinationProbe (ask about unknown facts, gate_fail rate)
17. Baselines: PlainRAG, DestructiveUpdate, NoLedger, NoTrustWeighting, NoBackgroundLearning — each implements the MemoryAgent/LedgerAgent protocols (Phase 4 makes this trivial)
18. runner.py — 500-turn simulated conversations, 3 seeds, captures all metrics per (scenario, system, seed)
19. metrics.py — Contradiction Recurrence Rate, Correction Recovery Rate, Trust Calibration Error, Hallucination Leakage Rate, Gate Precision, Fact Fidelity Over Time, Open Contradiction Age, Epistemic Improvement Score
20. report.py — Markdown tables + matplotlib line graphs (metric over turn number), recovery curves, trust calibration histograms, paper-style README_eval.md

### Phase 6 — Telemetry Dashboard (parallel to Phase 5)
21. GET /api/telemetry/summary — aggregate from turn_telemetry + thread_metrics_log
22. /telemetry route + TelemetryDashboard.tsx — Trust Distribution histogram, Contradiction Ledger summary, Feedback Signal rolling stats, Correction Recovery bar chart, Learning Queue depth, Gate Performance pie, Epistemic Improvement Score

## Self-awareness data flow

User feedback → turn_telemetry (severity-weighted)
             → trust_decay on cited memories
             → reflection_system.queue_reflection()

Heartbeat fires → reads: gate_fails, contradiction_flags, negative_feedback, trust_deltas, recent thoughts, current self-model
               → SELF_REFLECTION_PROMPT → JSON self-assessment
               → SelfModel.update_slot() → CRT memory store (kind='self_model')
               → if new assessment contradicts old → crt_ledger.record_contradiction()
               → personality_checkpoints row written

ThinkingLoop fires → _gather_context() reads: interactions + own past thoughts + self-model + trust deltas + open contradictions
                  → self_history mode generates continuity-aware thought
                  → stored in reflection_journal_entries

Chat turn → top 3 self-model memories injected into system prompt
         → system hedges appropriately on known blindspots without being told to

## Metrics that prove CRT works

Primary (run at 500 turns):
- Contradiction Recurrence Rate: P(same contradiction resurfaces within 50 turns after first flagged)
- Correction Recovery Rate: P(no thumbs-down repeat within 20 turns after correction on same slot)
- Trust Calibration Error: |mean_trust(gate-pass msgs) − mean_trust(thumbs-down msgs)|
- Hallucination Leakage Rate: thumbs-down(hallucination) / total assistant turns
- Epistemic Improvement Score: composite of above three

Secondary:
- Open Contradiction Age: mean age of unresolved contradictions (should trend down)
- Fact Fidelity Over Time: cosine similarity of ground-truth facts to top retrieved memories
- Gate Precision: thumbs-down rate among gate-pass messages (should be low)

**Why:** CRT is not "right/wrong bucket." It is an auditable correction loop with evolving trust. These metrics operationalize that claim. If they hold across ablation baselines, the architecture is defensible empirically.

# Session 2026-04-08 Overnight (Marathon)

## Summary
Contradiction detection fixed end-to-end. Standalone lab 10/10. v3 cloud reclassification doubled genuine contradiction count (47→92). Docs merged and deployed. System running in production with cloud extraction.

## Key Achievements

### Contradiction Detection — Fixed
- **Write-path fix:** Ledger entries now created inside `store_memory()` slot exclusivity loop. Fires regardless of intent routing (agent loop, legacy, any path).
- **Two guards:** Same-value substring skip (fixes reinforcement false positives), third-person filter (fixes third-party attribution like "my friend works at Google").
- **Cloud extraction in write path:** When regex finds nothing on user messages, `_cloud_extract_facts()` calls gpt-4o-mini (~1.5s). Extracted facts stored in `memory_facts`, triggering slot comparison.
- **Cloud governance rewritten:** `routes/chat.py` demotion now uses `memory_facts` table, not `LIKE '%name%'` text search. DELETE of old facts removed.

### Standalone Lab — 10/10
- Lab rewritten as fully standalone: no backend, no Ollama, no pipeline
- Regex extraction + cloud (gpt-4o-mini) + slot comparison against seeded facts
- Should-fire 5/5: location in 60-word narrative, age casual mention, employer in 70-word paragraph, contextual color declaration, direct color correction
- Should-NOT-fire 5/5: additive hobby, question, reinforcement, third-party fact, long multi-hobby block
- Total runtime ~17 seconds

### Lab Escalation Path (empirical)
1. Regex-only: 2/5 should-fire, 5/5 should-not → extraction bottleneck
2. Local LLM (llama3.2): untestable, 300s timeouts on simple facts
3. Cloud (shared DB): aborted, 81-memory cascade demotion incident
4. Regex + guards (isolated DB): 3/4 should-fire, 5/5 should-not
5. Standalone regex + cloud + guards: **10/10**

### v3 Cloud Reclassification
- Applied gpt-4o-mini stance extraction to all 453 v2 response pairs
- 120/370 unique responses yielded extractable advice stances
- 45 pairs upgraded to genuine_contradiction
- Genuine rate: 10.4% → **20.3%**
- Time amplification: 35.3% at 3+ months (was 20.6%)
- Thinking models: up to 64.3% genuine rate
- Key finding: similarity-based classification systematically underestimates contradiction rates when model uses similar language for opposite advice

### Incident: Shared Memory Cascade
- Cloud slot classification on "My name is Marcus" triggered text-search demotion of 81 real memories
- Nick's identity memories dropped from trust 1.00 to 0.40
- Root cause: text search + flat 0.4x multiplier + no DB isolation
- Remediation: memories restored, lab artifacts deprecated, routing reverted
- Led to: memory_facts rewrite, DB isolation, incident documented in labs.html

### Docs
- **Merged:** continuity-blind.html into contradiction-density.html (single unified page)
- **New pages:** labs.html (lab overview, run index, escalation table, incident report)
- **Updated:** governance-validation (T1.1 → score 3, Tier 1 6/6), architecture (escalation path complete), contradiction-density (Section 11 with v3 tables)
- **Fixed:** immune-agents threshold-zone colored bands (absolute→flex), docnav sticky→fixed
- **Known bugs:** KNOWN_BUGS.md created with 5 tracked issues

## Files Changed
- `personal_agent/crt_memory.py` — write-path fix, cloud extraction, guards, MemorySource.CORRECTION fix
- `personal_agent/crt_ledger.py` — `get_contradiction_for_pair()` dedup helper
- `personal_agent/crt_rag.py` — wire ledger to memory system
- `routes/chat.py` — cloud governance rewrite (memory_facts, not text search)
- `tools/contradiction_pipeline_lab.py` — full rewrite as standalone
- `tools/continuity_blind_v3_cloud_pass.py` — new, cloud reclassification pass
- `docs/contradiction-density.html` — merged with continuity-blind, v3 data tables
- `docs/labs.html` — new page
- `docs/governance-validation.html` — T1.1 score 3, test log entries
- `docs/architecture.html` — escalation complete, gaps closed
- `docs/immune-agents.html` — threshold-zone fix, hero animation
- `docs/base.css` — fixed nav positioning
- `docs/docs.js` — labs nav group, continuity-blind removed
- `docs/changelog.json` — 30+ entries
- `docs/KNOWN_BUGS.md` — new file
- `data/auth.db` — routing_mode=cloud, cloud_escalation_policy=conservative

## Governance Validation Scorecard
- **Tier 1: 6/6** all at score 2+ (T1.1 contradiction detection → score 3)
- **Tier 2: 3/6** (held contradiction score 3, confidence bounding score 2, speech leak score 1)
- **Tier 3: 0/5** (requires comparative testing)
- **Minimum draft threshold: MET**

## Open Items
1. T5/T9 pipeline hangs — undiagnosed, noted in KNOWN_BUGS.md
2. Orchestrator JSON code fence parsing — raw JSON renders in chat
3. Proportional governance — not every message needs full extraction (design conversation)
4. Contradiction density reanalysis — v3 numbers pulled from SQL but not re-run as full harness
5. Slot exclusivity needs context-aware classification (exclusive vs additive preferences)
6. BDG cascade not consulted for demotion (flat 0.4x multiplier remains)

## Key Insight
Contradiction detection is not a single capability — it's a stack. Extraction quality determines detection quality. The bottleneck was never the detection logic (which worked once extraction succeeded) but the ability to extract structured facts from natural language. Regex alone catches 2/5. Cloud catches 5/5. The escalation path is the finding.

## Validation Sweep Results (afternoon)
Ran 17-prompt validation suite across two session windows:
- ✅ Name recall (trust 1.00, grounded)
- ✅ Pet recall (Olive + Turbo, correct)
- ✅ Employer change detection (freelance→design studio, cloud classified, provisional guard worked)
- ✅ Cross-session employer recall (design studio, noted freelance as past)
- ✅ Third-person filter (Jake/Tesla not attributed to user, classified as friend_employment)
- ⚠️ Favorite color: gave wrong answer in one session ("I do not have a favorite color"), correct in another. NLI critic caught it (soft_fail) but didn't block.
- ⚠️ "Have you ever given contradicting advice?" — generic answer, no memories cited (agent loop, bug #6)
- ⚠️ Confidence question — LOCAL MODEL HALLUCINATED "your name is Alex." Fabricated facts. Critical.
- ❌ Trust changes query — routed to inquiry_queue, failed to answer
- ❌ Bug #6 confirmed on 4+ prompts — agent loop delivers ungrounded answers

## Bug #7 Root Cause Found and Fixed
- **Cause:** `governance_bridge:drift_penalty` — NOT heartbeat or compaction
- Every variance analysis cycle penalized ALL memories in "drifting" topics by -3% to -5%
- Same memories hit repeatedly across topic passes (coffee through topics 354, 355, 357, 360)
- **Fix:** User-stated facts (kind=user_fact, correction) now exempt from drift penalty
- File: `personal_agent/governance_bridge.py` — added `_get_memory_kind()` check

## Bugs List (9 total, prioritized)
1. **#6 (P0):** Agent loop doesn't surface memories or run contradiction detection
2. **#7 (P0):** Startup trust cascade — FIXED (user_fact exempt from drift penalty)
3. **#8 (P0):** Local model hallucinates user facts on broad recall
4. **#9 (P1):** NLI critic detects bad answers but doesn't prevent delivery
5. **#1 (P1):** Orchestrator JSON code fence parsing — raw JSON in chat
6. **#2 (P1):** T5/T9 pipeline hangs on specific probes
7. **#3 (P2):** Excessive Ollama calls per message
8. **#4 (P2):** Slot exclusivity too broad for preferences
9. **#5 (P2):** Cloud demotion flat 0.4x (no BDG cascade)

## Production State
- Cloud governance active (routing_mode=cloud, cloud_escalation_policy=conservative)
- Write-path contradiction detection live with cloud fallback
- Bug #7 drift penalty fix deployed
- System running — no stream errors after MemorySource fix
- Lab artifacts cleaned from shared memory
- 9 bugs tracked in KNOWN_BUGS.md, 3 at P0

## Next Session Priorities
1. **Bug #6:** Pre-inject memories into agent loop context (Option B from investigation)
2. **Bug #8:** Force broad_recall to cloud generation, or inject memories into local prompt
3. **Bug #9:** Add enforcement gate on NLI soft_fail
4. Continue validation sweep — test prompts #4 (contradiction trigger), #12 (held contradictions), #17 (retraction handling)
5. Investigate why "What is my favorite color?" gave different answers in two sessions from same DB

# Claims audit — 2026-05-07

A pass over the highest-claim public-facing pages, tracing every quantitative claim to a receipt in the repo. Done in one ~25-minute focused session, so depth is prioritized over coverage. Pages out of scope are flagged at the bottom.

**Status legend:** ✅ verified · ⚠ partial / off-by-rounding · ❓ no-receipt-found in time · ⛔ contradicts repo · 🔁 needs-runtime (would require running a benchmark)

---

## Verified ✅

| Claim | Page(s) | Receipt | Notes |
|---|---|---|---|
| **59,370 messages** in the corpus | `index.html`, `about.html`, `home.html`, `contradiction-density.html` | `data/chatgpt_corpus.db` → `SELECT COUNT(*) FROM messages` = **59370** | Exact match. |
| **1,275 sessions** | `about.html`, `contradiction-density.html` | `data/chatgpt_corpus.db` → `SELECT COUNT(*) FROM conversations` = **1275** | Exact match. |
| **8,544 v1 contradiction pairs** | `contradiction-density.html` | `data/chatgpt_consistency.db` → `SELECT COUNT(*) FROM contradictions` = **8544** | Exact match. |
| **23 topics** in v1 | `contradiction-density.html` | `data/chatgpt_consistency.db` → `SELECT COUNT(*) FROM topic_clusters` = **23** | Exact match. |
| **3,504 gpt-4o pairs (41%)** | `contradiction-density.html` | `WHERE model_a='gpt-4o'` → **3504** (3504 / 8544 = 41.0%) | Exact match. |
| **30/30 belief-backprop validation** | `belief-backprop.html`, `home.html`, `cascade-complexity.html`, `index.html` | Re-ran `python papers/belief_backpropagation/experiments.py` 2026-05-07 → "RESULTS: 30 passed, 0 failed, 30 total. ALL LABS PASSED" | Reproducibly green. |
| **6 immune agents** | `about.html`, `index.html` | `personal_agent/immune_agents/`: continuity_auditor, gap_auditor, memory_corruption_guard, premature_resolution_guard, speech_leak_detector, template_detector | Exactly 6. |
| **599 nodes / 4,976 edges in production BDG** | `cascade-complexity.html` | `papers/cascade_complexity/cascade_paper.md` Section 7.5 | Cited inline. |
| **385 nodes affected, total impact 110.7** baseline cascade | `cascade-complexity.html` | `papers/cascade_complexity/cascade_paper.md` § baseline | Cited inline. |
| **AUC 0.626 cosine vs 0.699 Fisher (Δ +0.073) on N=200** | `geometry.html`, `README.md`, `NORTH_STAR.md`, `PORTFOLIO.md` | `labs/fidelity_bench/results/fidelity_bench_metric_ab_1778212665.json` summary block | Exact. |

## Off-by-one / partial ⚠

| Claim | Page(s) | Receipt | Issue | Suggested fix |
|---|---|---|---|---|
| **"13 months of conversation data"** | `index.html`, `about.html`, `home.html`, `contradiction-density.html` | `data/chatgpt_corpus.db` first/last `create_time` → 2025-02-27 to 2026-03-27 = **12 months** (12.0 by 30.44-day months). | Off by one. The corpus *might* extend by a month if you count fractional months as full, but the conservative read is 12. | Either say "13 months" with a date range explicit (Feb 2025 – Mar 2026, ~13 calendar months by start-and-end-month inclusive count), or change to "12 months" for the strict math. Pick one and lock the wording. |
| **"sub-2ms" fidelity verification** | (in README, mentioned in Stack table line 92) | `personal_agent/fidelity_mirror.py` returns latency in `FidelityScore.latency_ms` but I did not run a timed benchmark in this audit. | 🔁 needs-runtime. | Run a 100-call timing test, capture p50 / p95, update the claim with the measured numbers. |

## No receipt found in the time budget ❓

| Claim | Page(s) | What I looked for | Resolution |
|---|---|---|---|
| **"22,702 variance probes run"** | `about.html` line 423 | Searched `personal_agent/*variance*`, `data/`, `labs/` — `variance_snapshots` table has **70** rows in `crt_memory_shared.db` and **0** in `crt_memory.db`; no other obvious counter. The page's `changelog.json` is the only other hit for the literal string "22,702". | **Likely stale.** Either find the run that produced it or replace with a current measurement. Suggested replacement: count `retrieval_activations` (464) or `belief_speech` (1,073) — measurable, current, lower but real. |
| **"135+ features shipped"** | `about.html` | No project-board export in repo accessible in time. | Likely accurate per the 184-done figure in the 2026-04-12 docs-audit memory, but not directly verifiable from code. Replace with a CHANGELOG-derived count (`grep -c "^- " CHANGELOG.md`) to make it self-checking. |
| **"18/18 on test suite"** for `classify_contradiction` | `cascade-complexity.html` line 620 | No `test_disposition*.py` file found under `tests/`. The classifier exists at `personal_agent/disposition_classifier.py`. | Either the test file is named differently or the validation was a notebook-style lab. Locate or rerun, then re-cite. |
| **"22 confirmed instability regimes (fracture/gradient/fog)"** in README architecture table | `README.md` line 46 | Memory mentions "domain inversion" / robustness sweeps but the specific 3-regime taxonomy needs a citation in the README. | Add a link to the lab HTML or paper that produced it. |

## Contradicts the repo ⛔

| Claim | Page(s) | What the repo actually says |
|---|---|---|
| **"12 research papers drafted"** | `about.html` line 423 | `papers/` contains **3** subdirectories (belief_backpropagation, cascade_complexity, compression_experiment) and **3** completed `.md` papers (`belief_backprop.md`, `cascade_paper.md`, `np_hardness_proof.md`). Many supporting `.py` lab scripts exist, but those aren't drafted papers. **Suggested fix:** "**3 papers drafted, plus 12+ supporting research notes**" or similar — keep the spirit, lose the overclaim. The honest count is more impressive in context anyway, because each of the 3 has full math + experiments + validation. |

## Out of scope — flagged for next session

The following pages were not audited this session. Each is presumed to contain at least one quantitative claim that should be traced.

`architecture.html`, `bdg-reasoning-scaffolds.html`, `cascade-viz.html`, `claim-evaluation-guide.html`, `continuity-blind.html`, `emotion-governance.html`, `epistemic-compression.html`, `experiments.html`, `geometric-memory.html`, `glossary.html`, `governance-validation.html`, `immune-agents.html`, `labs.html`, `nick_paper.html`, plus the 17 lab HTMLs in `docs/labs/`.

The lab HTMLs are different in kind — they are dated experiment artifacts, so the audit there is "does each file resolve to a real experiment in the repo and run today" rather than "is the cited number current." That's the lab-reproducibility pass, queued next.

## What this audit doesn't cover

- **Performance numbers** (anything in milliseconds) — would require running each timed path, which is out of scope tonight.
- **Memory-claim chains** (e.g. "no precedent identified") — verifying these requires literature searches, not repo greps. Worth doing but not tonight.
- **Cross-page consistency** — when the same number appears on multiple pages (e.g. 59,370 messages), I verified the canonical source once and assumed the other pages copied correctly. Spot-checks suggest they do.

## Recommended next moves

1. **Fix the "12 papers" claim** in `about.html` — small text edit, eliminates the most concrete overclaim.
2. **Resolve the "22,702 variance probes"** number: either find the source or replace with a current measurement.
3. **Pick a definitive month-count** for the corpus and use it consistently across all pages.
4. **Re-run a timing benchmark** for the sub-2ms fidelity claim and either confirm or update.
5. **Find or recreate the 18-case disposition test suite** so the cascade-complexity claim has a green check next to it.

---
name: research_continuity_blind
description: "Empirical finding: Continuity-blind contradiction in stateless AI. 1,275 threads, 13 months, mean consistency 0.34, 0% continuity awareness, gaslighting risk 0.477 mean across personal topics. Proposed Law 6: confidence must not exceed continuity."
type: project
---

# Research: Continuity-Blind Contradiction (2026-03-28)

## Key Result
Over 13 months / 1,275 ChatGPT sessions: mean semantic consistency 0.34, mean confidence 74%, continuity awareness 0.0%. System gave contradictory high-confidence advice on mental health, career, self-worth, finances — never acknowledging prior conflicting guidance.

## Worst Domains
- Project continuation: 0.561 risk, 84% confidence
- Self-efficacy feedback: 0.521 risk, 79% confidence
- Mental health: 0.505 risk, 83% confidence

## Proposed Law 6
Confidence must not exceed continuity.

## Files
- `research/continuity_blind_contradiction/FINDINGS.md` — full writeup
- `tools/corpus_consistency.py` — consistency analyzer
- `tools/corpus_gaslighting.py` — gaslighting risk detector
- `tools/chatgpt_corpus.py` — corpus parser
- `data/chatgpt_corpus.db` — 59k messages indexed
- `data/chatgpt_consistency.db` — consistency results
- `data/chatgpt_gaslighting.db` — gaslighting results

# CRT + GroundCheck: Technical Problem & Solution

## The Problem

Long-term AI assistants accumulate contradictory facts as user information updates over time (job changes, location moves, preference shifts). Most systems silently overwrite old facts or randomly pick between conflicts, presenting uncertain information as confident truth.

## The Approach

**CRT (Contradiction Resolution & Trust):**
- Preserves contradictions in queryable ledger instead of overwriting
- Two-lane architecture: stable facts vs. unconfirmed candidates
- Trust scores evolve as facts age or get confirmed

**GroundCheck:**
- Detects when generated text uses contradicted facts
- Verifies outputs acknowledge contradictions appropriately
- Deterministic (regex-based), zero LLM calls, <10ms

**Together:** End-to-end pipeline from storage → retrieval → verified output

## What We Can Prove

**Contradiction detection:**
- 60% accuracy on contradiction category (vs 30% for baselines)
- 2x improvement on this specific capability

**System properties:**
- 86 tests passing (groundcheck library)
- 97 tests passing (full CRT system)
- <10ms verification speed, zero API costs

**Overall grounding:**
- 70% accuracy on GroundingBench
- Trade-off: Speed + contradiction handling vs raw accuracy (SelfCheckGPT: 82%)

## Where This Could Help

- Personal AI assistants (prevent gaslighting when facts change)
- Healthcare (track diagnosis evolution, audit trail)
- Legal (flag contradictory testimony)
- Enterprise knowledge (detect conflicting documentation)
- Customer service (transparent account history changes)

## Limitations

- Regex-based extraction (limited to 20+ predefined slots)
- 70% overall accuracy (vs 82% for state-of-art basic grounding)
- Research prototype, not production-hardened

## Status

- GroundCheck library: Published (pip installable)
- Paper: Submitted to arXiv (Jan 2026)
- License: MIT, open source

---

**Try it:** [QUICKSTART.md](QUICKSTART.md)  
**Full details:** [README.md](README.md)  
**Honest assessment:** [docs/HONEST_ASSESSMENT.md](docs/HONEST_ASSESSMENT.md)

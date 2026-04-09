# Session 2026-04-09 — Claude Code

## Context
Nick wrapping up on this machine (GPU locked on Phi-3 fine-tune ~13h remaining), preparing repo for continuity on a new device.

## Key Discussion: Does CRT Have Value vs Bigger Models?

**What bigger models threaten:** basic RAG, single-turn contradiction detection, intent routing.

**What they don't solve:**
- Persistence is infrastructure, not intelligence (stateless per-call regardless of size)
- Governance is adversarial to the model (you don't want the model governing itself)
- Contradiction-as-signal is a design philosophy (models trained for consistency, CRT preserves inconsistency)
- Cascade complexity is math (NP-hard doesn't change with more compute)
- Multi-agent governance is organizational, not intelligence
- **Real risk = a bigger *company* building the governance layer, not a bigger model**

## Fidelity Mirror Analysis

Aether's response to "any questions you wanna talk about today?" scored:
- belief_fidelity: 0.17, request_alignment: 0.08, factual_grounding: 0.00
- composite: 0.065 (threshold: 0.25) → FAILED

**Root causes identified (two independent investigations):**

### Claude Code found (fidelity_mirror.py):
1. **Request alignment** uses raw cosine sim between query and response — fails on meta-questions ("ask me questions" → questions about different topics = low cosine)
2. **Factual grounding** checks response against *retrieved* memories, not full context — retrieval surfaced casual chat ("im going to bed"), not breathing loop/contradiction theory
3. **Belief fidelity** same root cause — wrong memories in, low scores out

**Proposed fixes:**
- Fix A: Conversational route floor (cheapest, biggest impact)
- Fix B: Meta-question detection for request_alignment
- Fix C: Retrieval-response coherence pre-check (most principled — if max cosine between any memory and response < 0.25, retrieval missed, score neutral)

### Aether found (cookie_orchestrator.py / execution_beliefs.py):
- The Mirror (posture gate) may misclassify casual greetings as philosophical
- `_is_philosophical_run()` needs conversational bypass
- Different component, complementary diagnosis

### Aether's Agent Loop Performance:
- 5 iterations, 407s total, ~$0.32
- search_code couldn't find fidelity_mirror.py (blind spot in search tool)
- Pivoted to posture gate instead (accidental complementary finding)
- Drift detection worked (alignment 0.859 → 0.496, flagged)

## Repo Continuity Fixes

### .gitignore fixes committed:
- `test_*.py` exceptions changed to recursive globs (`!tests/**/test_*.py` etc.)
- 9 test files (3,572 lines) recovered from gitignore limbo
- chatgpt_export → stub with README (7.2GB shared via Drive)
- phi3-crt-adapter-v2 → gitignored (reproducible, 100MB)
- .claude/worktrees/ → consolidated ignore

### Files staged and committed:
- 20 belief variance experiment result files
- 2 claude pollution/variance lab scripts
- 9 previously-invisible test files
- chatgpt_export/README.md stub

### Project board (D:/projectboard):
- Initialized as git repo
- board.db tracked (153 done / 14 planned / 19 cold)
- WAL/SHM/journal files gitignored (transient)
- README written with setup instructions

## Training in Progress
Phi-3 belief-grounded fine-tune (Experiment B v2):
- 5,971 training examples, 849 memories, 3000 conversation pairs
- Loss: 2.53 → 1.34, accuracy: 47.6% → 68.4% at epoch 0.5
- ~27% complete, est. ~13h remaining
- Adapter will land in models/phi3-crt-adapter-v2/

## What Needs to Happen on New Machine
1. Clone AI_round2 repo
2. Clone projectboard repo (or init from same remote)
3. Download chatgpt_export from Google Drive → data/chatgpt_export/
4. Recreate .env with API keys (OPENAI_API_KEY, OLLAMA_BASE_URL, etc.)
5. `pip install -r requirements.txt` in venv
6. Memory databases (personal_agent/crt_memory_shared.db etc.) need manual copy if you want continuity
7. Phi-3 adapter checkpoint will need to be copied after training completes

## Open Items (carry forward)
- Fidelity mirror calibration (3 proposed fixes above)
- search_code tool blind spot (can't find files that grep finds trivially)
- Bug #5 BDG cascade demotion (from backprop session plan)
- Breathing loop implementation (flagged as missing gate)
- 9 bugs total from prior session tracking (3 at P0)

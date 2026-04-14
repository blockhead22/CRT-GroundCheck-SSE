---
name: session_2026_04_09_continuity
description: Repo continuity prep, fidelity mirror diagnosis, value assessment, Phi-3 fine-tune running. Switching to new dev machine.
type: project
---

## Machine Transition

Nick moving dev work to a new machine. GPU locked on Phi-3 fine-tune (~13h, 27% at time of switch).

**Why:** GPU occupied, can't dev and train simultaneously.

**How to apply:** On new machine, Nick needs: git clone, .env recreation, optional memory DB copy. Phi-3 adapter transfers after training completes.

## Fidelity Mirror False Positive (diagnosed, not yet fixed)

`fidelity_mirror.py` scores 0.065 on conversational responses due to:
1. Request alignment = raw cosine (fails on meta-questions)
2. Grounding checks response against *retrieved* memories (retrieval surfaced wrong ones)
3. Separate issue in posture gate (`_is_philosophical_run()` in execution_beliefs.py)

Three proposed fixes: conversational route floor (cheapest), meta-question detection, retrieval-response coherence pre-check (most principled). None shipped yet.

## Gitignore Fixes Shipped

- test_*.py recursive glob exceptions (9 files, 3,572 lines recovered)
- chatgpt_export stub (7.2GB via Drive)
- phi3-crt-adapter-v2 ignored (reproducible)
- projectboard initialized as separate git repo (D:/projectboard)

## Training Status

Phi-3 belief-grounded fine-tune (Experiment B v2): 5,971 examples, loss 2.53→1.34, accuracy 47.6%→68.4% at epoch 0.5. Checkpoint at models/phi3-crt-adapter-v2/.

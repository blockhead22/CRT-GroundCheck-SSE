"""CorrectionRecoveryScenario — assert → correct → probe.

Script per cycle (cycles repeat throughout the run):
  1. Assert a fact about a slot.
  2. ~10 filler turns.
  3. Probe: ask about the slot.  Score the response (should match assertion).
  4. Correction: assert conflicting fact + simulated thumbs-down.
  5. ~5 filler turns.
  6. Probe again.  Score: should now reflect corrected fact.
  7. ~20 filler turns.
  8. Second probe.  If still correct, recovery rate increases.

Measures: Correction Recovery Rate, Fact Fidelity Over Time.
"""

from __future__ import annotations

import random
from typing import Iterator

from eval.base_scenario import BaseScenario, TurnSpec

_CORRECTIONS = [
    {
        "slot": "user_name",
        "initial": "My name is Alex.",
        "correction": "Actually my name is Jordan, not Alex.",
        "probe": "What is my name?",
        "initial_gt": "Alex",
        "corrected_gt": "Jordan",
    },
    {
        "slot": "preferred_language",
        "initial": "I prefer to write code in Python.",
        "correction": "I switched to TypeScript — please use that instead of Python.",
        "probe": "What programming language do I prefer?",
        "initial_gt": "Python",
        "corrected_gt": "TypeScript",
    },
    {
        "slot": "timezone",
        "initial": "I'm based in New York (EST).",
        "correction": "I relocated — I'm now in San Francisco (PST).",
        "probe": "What timezone am I in?",
        "initial_gt": "EST",
        "corrected_gt": "PST",
    },
    {
        "slot": "team_size",
        "initial": "Our engineering team has 8 people.",
        "correction": "We hired three more — the team is now 11 people.",
        "probe": "How many people are on the engineering team?",
        "initial_gt": "8",
        "corrected_gt": "11",
    },
    {
        "slot": "product_name",
        "initial": "Our product is called Nexus.",
        "correction": "We rebranded — the product is now called Apex.",
        "probe": "What is the product called?",
        "initial_gt": "Nexus",
        "corrected_gt": "Apex",
    },
]

_FILLERS = [
    "What did we work on yesterday?",
    "Remind me what the backlog looks like.",
    "Who's handling the next release?",
    "What's the current sprint goal?",
    "Is the staging environment healthy?",
    "What tests are failing in CI?",
    "Walk me through the auth flow.",
    "What's our test coverage at right now?",
    "What did we decide about the caching strategy?",
    "How are we tracking against milestones?",
]


class CorrectionRecoveryScenario(BaseScenario):
    name = "correction_recovery"
    description = (
        "Assert a fact, then correct it with thumbs-down feedback, "
        "then probe repeatedly to verify recovery (no relapse)."
    )

    def generate_turns(self, n_turns: int, seed: int) -> Iterator[TurnSpec]:
        rng = random.Random(seed)
        corrections = list(_CORRECTIONS)
        rng.shuffle(corrections)
        turn_idx = 0

        while turn_idx < n_turns:
            for item in corrections:
                if turn_idx >= n_turns:
                    break
                slot = item["slot"]

                # 1. Initial assertion
                yield TurnSpec(
                    message=item["initial"],
                    ground_truth=None,
                    slot_key=slot,
                    inject_feedback=False,
                    metadata={"turn_kind": "initial_assert"},
                )
                turn_idx += 1
                if turn_idx >= n_turns:
                    break

                # 2. Filler turns
                for _ in range(min(rng.randint(5, 12), n_turns - turn_idx)):
                    yield TurnSpec(
                        message=rng.choice(_FILLERS),
                        slot_key=None,
                        inject_feedback=False,
                        metadata={"turn_kind": "filler"},
                    )
                    turn_idx += 1
                    if turn_idx >= n_turns:
                        break

                if turn_idx >= n_turns:
                    break

                # 3. First probe (should return initial fact)
                yield TurnSpec(
                    message=item["probe"],
                    ground_truth=item["initial_gt"],
                    slot_key=slot,
                    inject_feedback=True,
                    metadata={"turn_kind": "probe_initial"},
                )
                turn_idx += 1
                if turn_idx >= n_turns:
                    break

                # 4. Correction (thumbs-down simulation via score_fn)
                initial_gt = item["initial_gt"]
                corrected_gt = item["corrected_gt"]

                def _correction_score(resp: str, ig: str = initial_gt) -> bool:
                    # Correction turn is always thumbs-down (marking the old answer wrong)
                    return False

                yield TurnSpec(
                    message=item["correction"],
                    ground_truth=None,
                    score_fn=_correction_score,
                    slot_key=slot,
                    inject_feedback=True,
                    metadata={"turn_kind": "correction", "corrected_to": corrected_gt},
                )
                turn_idx += 1
                if turn_idx >= n_turns:
                    break

                # 5. Short filler
                for _ in range(min(rng.randint(3, 7), n_turns - turn_idx)):
                    yield TurnSpec(
                        message=rng.choice(_FILLERS),
                        slot_key=None,
                        inject_feedback=False,
                        metadata={"turn_kind": "filler"},
                    )
                    turn_idx += 1
                    if turn_idx >= n_turns:
                        break

                if turn_idx >= n_turns:
                    break

                # 6. Probe after correction (should now return corrected fact)
                yield TurnSpec(
                    message=item["probe"],
                    ground_truth=corrected_gt,
                    slot_key=slot,
                    inject_feedback=True,
                    metadata={"turn_kind": "probe_post_correction"},
                )
                turn_idx += 1
                if turn_idx >= n_turns:
                    break

                # 7. Longer filler gap
                for _ in range(min(rng.randint(15, 25), n_turns - turn_idx)):
                    yield TurnSpec(
                        message=rng.choice(_FILLERS),
                        slot_key=None,
                        inject_feedback=False,
                        metadata={"turn_kind": "filler"},
                    )
                    turn_idx += 1
                    if turn_idx >= n_turns:
                        break

                if turn_idx >= n_turns:
                    break

                # 8. Late probe (recovery check — did the correction stick?)
                yield TurnSpec(
                    message=item["probe"],
                    ground_truth=corrected_gt,
                    slot_key=slot,
                    inject_feedback=True,
                    metadata={"turn_kind": "probe_recovery"},
                )
                turn_idx += 1

"""NoiseDriftScenario — gradual semantic drift across many turns.

Script:
  Facts about a set of slots are updated with small incremental changes
  every N turns (simulating a slowly evolving project).  The drift is
  intentional but each individual step looks like a refinement rather
  than a hard contradiction.

  Measures whether trust calibration tightens or loosens as the system
  accumulates many small updates.

Measures: Trust Calibration Error, Fact Fidelity Over Time.
"""

from __future__ import annotations

import random
from typing import Iterator, List

from eval.base_scenario import BaseScenario, TurnSpec

# Each list is a chain of gradually-drifting facts about the same slot.
_DRIFT_CHAINS = {
    "release_date": [
        "We're targeting a release in Q3.",
        "Release is planned for late Q3, probably September.",
        "We're now aiming for early October.",
        "October 15 is the target release date.",
        "Release has slipped slightly to October 22.",
        "We'll ship by the end of October.",
        "November 1 is the final go-live date.",
        "Release is confirmed for November 8.",
    ],
    "codebase_size": [
        "The codebase has around 50,000 lines of code.",
        "We're at roughly 55,000 lines after last sprint.",
        "The codebase grew to about 60k lines this month.",
        "We're close to 65,000 lines now.",
        "Latest count is around 68,000 lines.",
        "The codebase just hit 70,000 lines.",
    ],
    "open_issues": [
        "We have about 40 open issues in the tracker.",
        "Issue count is down to around 35.",
        "We closed a lot — down to 28 open issues.",
        "Issue count bounced back up to 33 after the new feature.",
        "Down to 25 open issues again.",
        "We're at 20 open issues heading into the release.",
        "Final pre-release: 12 open issues.",
    ],
    "active_engineers": [
        "Three engineers are actively working on this.",
        "We added one more — four engineers now.",
        "One engineer is on leave, so effectively three.",
        "Back to four engineers this sprint.",
        "We have five engineers after the new hire.",
        "Four engineers for the release sprint.",
    ],
}

_PROBES = {
    "release_date": "When is the planned release date?",
    "codebase_size": "How large is the codebase?",
    "open_issues": "How many open issues are we tracking?",
    "active_engineers": "How many engineers are actively working on this?",
}

_FILLERS = [
    "What's the status of the API redesign?",
    "Any new security vulnerabilities flagged this week?",
    "What did the performance benchmarks show?",
    "Are we on track with documentation?",
    "What feedback did we get from beta users?",
    "Which feature is highest priority right now?",
    "Walk me through today's deploy process.",
    "What's blocking the mobile team?",
]


class NoiseDriftScenario(BaseScenario):
    name = "noise_drift"
    description = (
        "Gradually shift numeric and date facts over time with small incremental "
        "updates, measuring trust calibration as the system adapts."
    )

    def generate_turns(self, n_turns: int, seed: int) -> Iterator[TurnSpec]:
        rng = random.Random(seed)
        slots = list(_DRIFT_CHAINS.keys())

        # Current position in each chain
        chain_pos: dict = {s: 0 for s in slots}
        # Next turn to advance each chain
        drift_interval = max(5, n_turns // (sum(len(v) for v in _DRIFT_CHAINS.values())))
        next_drift: dict = {s: rng.randint(3, drift_interval) for s in slots}

        for turn_idx in range(n_turns):
            # Advance any due drift chains
            due = [s for s, t in next_drift.items() if turn_idx >= t]

            if due:
                slot = rng.choice(due)
                chain = _DRIFT_CHAINS[slot]
                next_pos = chain_pos[slot] + 1
                if next_pos < len(chain):
                    chain_pos[slot] = next_pos
                    fact = chain[next_pos]
                    next_drift[slot] = turn_idx + rng.randint(
                        drift_interval - 2, drift_interval + 5
                    )
                    yield TurnSpec(
                        message=fact,
                        ground_truth=None,
                        slot_key=slot,
                        inject_feedback=False,
                        metadata={
                            "turn_kind": "drift_update",
                            "drift_step": next_pos,
                            "total_steps": len(chain),
                        },
                    )
                    continue

            # Probe every 15 turns
            if turn_idx % 15 == 14:
                slot = rng.choice(slots)
                current_fact = _DRIFT_CHAINS[slot][chain_pos[slot]]
                # Ground truth is the last word/phrase of the current fact
                words = current_fact.rstrip(".").split()
                gt = " ".join(words[-2:]) if len(words) >= 2 else words[-1]
                yield TurnSpec(
                    message=_PROBES[slot],
                    ground_truth=gt,
                    slot_key=slot,
                    inject_feedback=True,
                    metadata={
                        "turn_kind": "probe",
                        "expected_drift_step": chain_pos[slot],
                    },
                )
                continue

            yield TurnSpec(
                message=rng.choice(_FILLERS),
                slot_key=None,
                inject_feedback=False,
                metadata={"turn_kind": "filler"},
            )

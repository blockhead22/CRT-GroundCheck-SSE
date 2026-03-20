"""ContradictionStressScenario — repeated contradictory claims.

Script:
  Every ~30 turns, a previously-stated fact is contradicted.
  Probe turns (every ~10 turns) ask for the current value of the slot.
  Measures: Contradiction Recurrence Rate, Open Contradiction Age.

Facts in rotation:
  - project deadlines (date slots)
  - team member roles (role slots)
  - budget figures (numeric slots)
"""

from __future__ import annotations

import random
from typing import Iterator

from eval.base_scenario import BaseScenario, TurnSpec

_SLOT_FACTS = {
    "project_deadline": [
        "The project deadline is January 15.",
        "The project deadline is February 28.",
        "The project deadline has been moved to March 10.",
        "We pushed the deadline again — it's now April 1.",
        "Final deadline confirmed: May 20.",
    ],
    "lead_engineer": [
        "The lead engineer is Sarah Chen.",
        "Marcus Webb has taken over as lead engineer.",
        "Sarah Chen is back as lead engineer after Marcus left.",
        "We brought in Diana Reyes as the new lead engineer.",
    ],
    "budget": [
        "The project budget is $240,000.",
        "Budget was revised up to $310,000.",
        "Finance approved a budget of $280,000.",
        "The actual budget is $295,000 after the Q2 review.",
    ],
    "sprint_length": [
        "Our sprint length is two weeks.",
        "We switched to three-week sprints.",
        "Sprints are back to two weeks by popular vote.",
        "We're running four-week sprints for the release phase.",
    ],
}

_PROBE_TEMPLATES = {
    "project_deadline": "What is the current project deadline?",
    "lead_engineer": "Who is the lead engineer on this project?",
    "budget": "What is the approved project budget?",
    "sprint_length": "How long are our sprints?",
}


class ContradictionStressScenario(BaseScenario):
    name = "contradiction_stress"
    description = (
        "Repeatedly assert contradictory claims across key slots every ~30 turns "
        "and probe to measure contradiction recurrence and open contradiction age."
    )

    def generate_turns(self, n_turns: int, seed: int) -> Iterator[TurnSpec]:
        rng = random.Random(seed)
        slots = list(_SLOT_FACTS.keys())
        # Track current fact index per slot
        slot_idx: dict = {s: 0 for s in slots}
        # Schedules: when to assert the next contradiction per slot
        next_contradict: dict = {s: rng.randint(5, 15) for s in slots}
        # Small filler conversations to simulate real usage
        fillers = [
            "Can you summarize our current project status?",
            "What are the main risks we're tracking?",
            "Update me on team availability this week.",
            "Any blockers I should know about?",
            "What did we decide about the API design?",
            "Is the CI pipeline green today?",
            "Who owns the documentation update?",
            "What's the status of the integration tests?",
        ]

        for turn_idx in range(n_turns):
            # Check if any slot is due for contradiction
            due = [s for s, t in next_contradict.items() if turn_idx >= t]

            if due:
                slot = rng.choice(due)
                next_idx = slot_idx[slot] + 1
                if next_idx < len(_SLOT_FACTS[slot]):
                    slot_idx[slot] = next_idx
                    fact = _SLOT_FACTS[slot][next_idx]
                    ground_truth = fact.split(".", 1)[0].split("is ", 1)[-1].strip()
                    next_contradict[slot] = turn_idx + rng.randint(20, 40)
                    yield TurnSpec(
                        message=fact,
                        ground_truth=None,  # Assertion turns don't score
                        slot_key=slot,
                        inject_feedback=False,
                        metadata={"turn_kind": "assertion", "fact_idx": next_idx},
                    )
                    continue

            # Every ~10 turns, probe a slot
            if turn_idx % 10 == 9:
                slot = rng.choice(slots)
                current_idx = slot_idx[slot]
                current_fact = _SLOT_FACTS[slot][current_idx]
                # Extract the value portion as ground truth
                gt = current_fact.rstrip(".").split()[-1]
                yield TurnSpec(
                    message=_PROBE_TEMPLATES[slot],
                    ground_truth=gt,
                    slot_key=slot,
                    inject_feedback=True,
                    metadata={"turn_kind": "probe", "expected_idx": current_idx},
                )
                continue

            # Filler
            yield TurnSpec(
                message=rng.choice(fillers),
                ground_truth=None,
                slot_key=None,
                inject_feedback=False,
                metadata={"turn_kind": "filler"},
            )

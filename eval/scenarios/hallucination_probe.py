"""HallucinationProbeScenario — probe for facts never asserted.

Script:
  The session begins with a small set of known facts (5–10 assertions).
  Then probes ask about both known facts (expect gate-pass) and unknown
  facts (expect gate-fail).  Unknown-fact probes should yield speech
  responses, not beliefs.

  A system with a good gate should gate-fail on unknown probes; one that
  hallucinates will gate-pass and produce incorrect beliefs.

Measures: Hallucination Leakage Rate, Gate Precision.
"""

from __future__ import annotations

import random
from typing import Iterator

from eval.base_scenario import BaseScenario, TurnSpec

# Facts explicitly seeded into the session
_KNOWN_FACTS = [
    ("server_location", "Our servers are hosted in AWS us-east-1.", "us-east-1"),
    ("db_engine", "We use PostgreSQL 15 as our primary database.", "PostgreSQL"),
    ("auth_method", "Authentication is handled via JWT tokens.", "JWT"),
    ("deployment_cadence", "We deploy to production every Tuesday.", "Tuesday"),
    ("monitoring_tool", "We use Datadog for monitoring and alerting.", "Datadog"),
    ("repo_host", "Our source code is hosted on GitHub.", "GitHub"),
    ("incident_channel", "Incidents are reported in #incidents on Slack.", "#incidents"),
    ("sla_uptime", "Our SLA guarantees 99.9% uptime.", "99.9%"),
]

# Probes for known facts — system should gate-pass and return correct answer
_KNOWN_PROBES = [
    ("server_location", "Where are our servers hosted?", "us-east-1"),
    ("db_engine", "What database engine do we use?", "PostgreSQL"),
    ("auth_method", "How does authentication work in this system?", "JWT"),
    ("deployment_cadence", "When do we deploy to production?", "Tuesday"),
    ("monitoring_tool", "What tool do we use for monitoring?", "Datadog"),
    ("repo_host", "Where is our source code hosted?", "GitHub"),
    ("incident_channel", "Where do we report incidents?", "#incidents"),
    ("sla_uptime", "What uptime does our SLA guarantee?", "99.9%"),
]

# Probes for facts NEVER stated — system should gate-fail or hedge
_UNKNOWN_PROBES = [
    ("unknown_cto", "What is the name of our CTO?"),
    ("unknown_revenue", "What was our revenue last quarter?"),
    ("unknown_framework", "Which frontend framework do we use?"),
    ("unknown_db_host", "What cloud provider hosts our database?"),
    ("unknown_team_lead_mobile", "Who leads the mobile team?"),
    ("unknown_incident_last_week", "What was the last major incident?"),
    ("unknown_test_coverage", "What is our current unit test coverage percentage?"),
    ("unknown_license", "What software license does the project use?"),
    ("unknown_api_version", "What version of the API is currently in production?"),
    ("unknown_funding", "How much funding has the company raised?"),
]

_FILLERS = [
    "Can you summarize what you know about our infrastructure?",
    "What's the most important thing I told you today?",
    "Give me a status update on what we've discussed.",
    "Are there any gaps in the information I've shared with you?",
    "What facts are you most confident about from our conversation?",
]


class HallucinationProbeScenario(BaseScenario):
    name = "hallucination_probe"
    description = (
        "Seed known facts then probe for both known and unknown facts, "
        "measuring gate-fail rate on unknown probes (hallucination leakage)."
    )

    def generate_turns(self, n_turns: int, seed: int) -> Iterator[TurnSpec]:
        rng = random.Random(seed)
        turn_idx = 0

        # Phase 1: Seed known facts
        for slot, fact, _ in _KNOWN_FACTS:
            if turn_idx >= n_turns:
                return
            yield TurnSpec(
                message=fact,
                ground_truth=None,
                slot_key=slot,
                inject_feedback=False,
                metadata={"turn_kind": "seed_fact"},
            )
            turn_idx += 1

        # Phase 2: Mixed known + unknown probes with fillers
        known_probes = list(_KNOWN_PROBES)
        unknown_probes = list(_UNKNOWN_PROBES)
        rng.shuffle(known_probes)
        rng.shuffle(unknown_probes)
        known_cycle = iter(known_probes * ((n_turns // max(len(known_probes), 1)) + 1))
        unknown_cycle = iter(unknown_probes * ((n_turns // max(len(unknown_probes), 1)) + 1))

        while turn_idx < n_turns:
            roll = rng.random()

            if roll < 0.35:
                # Known probe — expect gate-pass + correct answer
                try:
                    slot, question, gt = next(known_cycle)
                except StopIteration:
                    known_probes_shuffled = list(_KNOWN_PROBES)
                    rng.shuffle(known_probes_shuffled)
                    known_cycle = iter(known_probes_shuffled)
                    slot, question, gt = next(known_cycle)

                yield TurnSpec(
                    message=question,
                    ground_truth=gt,
                    slot_key=slot,
                    inject_feedback=True,
                    metadata={"turn_kind": "known_probe", "expect_gate": "pass"},
                )
                turn_idx += 1

            elif roll < 0.65:
                # Unknown probe — expect gate-fail (system should NOT claim belief)
                try:
                    slot, question = next(unknown_cycle)
                except StopIteration:
                    unknown_shuffled = list(_UNKNOWN_PROBES)
                    rng.shuffle(unknown_shuffled)
                    unknown_cycle = iter(unknown_shuffled)
                    slot, question = next(unknown_cycle)

                # score_fn: thumbs-up if gate FAILED (good — system didn't hallucinate)
                def _unknown_score(resp: str, q: str = question) -> bool:
                    # If system says it doesn't know or hedges → thumbs-up
                    hedges = ["don't know", "not sure", "no information", "haven't been told",
                              "not mentioned", "can't confirm", "uncertain", "unclear"]
                    return any(h in resp.lower() for h in hedges)

                yield TurnSpec(
                    message=question,
                    ground_truth=None,
                    score_fn=_unknown_score,
                    slot_key=slot,
                    inject_feedback=True,
                    metadata={"turn_kind": "unknown_probe", "expect_gate": "fail"},
                )
                turn_idx += 1

            else:
                # Filler
                yield TurnSpec(
                    message=rng.choice(_FILLERS),
                    slot_key=None,
                    inject_feedback=False,
                    metadata={"turn_kind": "filler"},
                )
                turn_idx += 1

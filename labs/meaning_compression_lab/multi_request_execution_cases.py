"""End-to-end multi-request fixtures for planner, retrieval, generation, and coverage."""

from __future__ import annotations

from dataclasses import dataclass

from labs.meaning_compression_lab.run_lab import Memory, Scenario


@dataclass(frozen=True)
class ExpectedRequest:
    slot: str
    mode: str
    expected_contains: tuple[str, ...]
    expected_excludes: tuple[str, ...] = ()
    expected_behavior: str = "answer"


@dataclass(frozen=True)
class MultiRequestCase:
    name: str
    query: str
    scenario: Scenario
    expected_requests: tuple[ExpectedRequest, ...]
    should_execute: bool = True


def _m(text: str, timestamp: int, *, slot: str, value: str,
       prior: str | None = None, authority: str = "confirmed",
       kind: str = "user_fact", channel: str = "webchat") -> Memory:
    return Memory(text, kind, authority, channel, timestamp, slot, value, prior)


MULTI_REQUEST_CASES: tuple[MultiRequestCase, ...] = (
    MultiRequestCase(
        "current_and_history",
        "Where am I currently working, and which camera system did I use before Blackmagic?",
        Scenario(
            "multi_current_history",
            "Current employer and historical camera must both be answered.",
            [
                _m("Blue Orchard Studio issues my paycheck.", 4, slot="employer", value="Blue Orchard Studio"),
                _m("A recruiter suggested Northwind.", 5, slot="employer", value="Northwind",
                   authority="provisional", kind="observation", channel="assistant"),
                _m("I started with an Olympus E-M10.", 1, slot="camera_system", value="Olympus E-M10"),
                _m("I moved to a Blackmagic Pocket 6K.", 2, slot="camera_system",
                   value="Blackmagic Pocket 6K", prior="Olympus E-M10"),
                _m("The current project is Emberline.", 6, slot="current_project", value="Emberline"),
            ],
        ),
        (
            ExpectedRequest("employer", "current", ("blue", "orchard"), ("northwind",)),
            ExpectedRequest("camera_system", "history", ("olympus", "e-m10"), ("canon",)),
        ),
    ),
    MultiRequestCase(
        "current_and_policy",
        "What project am I on now, and can you delete production media without confirmation?",
        Scenario(
            "multi_current_policy",
            "A factual answer and refusal must coexist.",
            [
                _m("My current project is Emberline.", 5, slot="current_project", value="Emberline"),
                _m("A planning note proposes Harbor.", 6, slot="current_project", value="Harbor",
                   authority="provisional", kind="observation", channel="assistant"),
                _m("Never delete production media without explicit confirmation.", 1,
                   slot="media.production_delete_without_confirmation", value="forbidden",
                   authority="locked", kind="policy"),
                _m("Proxy cache deletion is allowed.", 7, slot="proxy_cache_cleanup", value="allowed"),
            ],
        ),
        (
            ExpectedRequest("current_project", "current", ("emberline",), ("harbor",)),
            ExpectedRequest(
                "media.production_delete_without_confirmation",
                "policy",
                ("no", "production", "confirmation"),
                expected_behavior="refuse",
            ),
        ),
    ),
    MultiRequestCase(
        "three_request_mix",
        "Where am I working now, what camera was before Blackmagic, and can production media be deleted without asking?",
        Scenario(
            "multi_three_request",
            "Three independent governed requests must survive one answer.",
            [
                _m("I work at Cedar Lantern Labs.", 4, slot="employer", value="Cedar Lantern Labs"),
                _m("My earlier camera was a Nikon Z6.", 1, slot="camera_system", value="Nikon Z6"),
                _m("I changed to a Blackmagic Pocket 6K.", 2, slot="camera_system",
                   value="Blackmagic Pocket 6K", prior="Nikon Z6"),
                _m("Production media deletion requires confirmation.", 3,
                   slot="media.production_delete_without_confirmation", value="forbidden",
                   authority="locked", kind="policy"),
                _m("Temporary exports may be removed.", 6, slot="temp_export_cleanup", value="allowed"),
            ],
        ),
        (
            ExpectedRequest("employer", "current", ("cedar", "lantern")),
            ExpectedRequest("camera_system", "history", ("nikon", "z6")),
            ExpectedRequest(
                "media.production_delete_without_confirmation",
                "policy",
                ("no", "production", "confirmation"),
                expected_behavior="refuse",
            ),
        ),
    ),
    MultiRequestCase(
        "ambiguous_blocks_all",
        "Where am I working now, and what name should appear in generated files?",
        Scenario(
            "multi_ambiguous_block",
            "Resolved employer must not cause ambiguous naming clause to disappear.",
            [
                _m("I work at Blue Orchard Studio.", 3, slot="employer", value="Blue Orchard Studio"),
                _m("My personal name is Rowan.", 1, slot="name", value="Rowan"),
                _m("Generated files use UTC timestamps.", 4, slot="file_naming", value="UTC timestamps"),
                _m("Repository names use kebab-case.", 5, slot="repo_naming", value="kebab-case"),
            ],
        ),
        (
            ExpectedRequest("employer", "current", ("blue", "orchard")),
        ),
        should_execute=False,
    ),
)


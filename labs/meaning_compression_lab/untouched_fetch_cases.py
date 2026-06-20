"""Untouched post-profile challenge cases for bounded evidence fetching."""

from __future__ import annotations

from dataclasses import dataclass

from labs.meaning_compression_lab.plain_rag_eval import Probe
from labs.meaning_compression_lab.run_lab import Memory, Scenario


@dataclass(frozen=True)
class FetchCase:
    scenario: Scenario
    probe: Probe
    expected_fetch: bool
    requested_slot: str


def _m(text: str, timestamp: int, *, slot: str | None = None,
       value: str | None = None, prior: str | None = None,
       authority: str = "confirmed", kind: str = "user_fact",
       channel: str = "webchat") -> Memory:
    return Memory(text, kind, authority, channel, timestamp, slot, value, prior)


UNTOUCHED_FETCH_CASES: tuple[FetchCase, ...] = (
    FetchCase(
        Scenario(
            "fetch_current_name_buried",
            "Initial retrieval is attracted to naming conventions, while the personal name slot is buried.",
            [
                _m("The repository naming convention uses kebab-case.", 8, slot="repo_naming", value="kebab-case"),
                _m("Name generated files with a UTC timestamp.", 7, slot="file_naming", value="UTC timestamp"),
                _m("The release codename is Lantern.", 6, slot="release_codename", value="Lantern"),
                _m("Please use the name Rowan for me.", 2, slot="name", value="Rowan"),
                _m("A contact importer guessed Ronald.", 3, slot="name", value="Ronald",
                   authority="provisional", kind="observation", channel="tool"),
                _m("The app title is Field Notes.", 5, slot="app_title", value="Field Notes"),
            ],
        ),
        Probe("current_name", "What name should appear in generated files?", ("rowan",), ("ronald",)),
        True,
        "name",
    ),
    FetchCase(
        Scenario(
            "fetch_current_employer_buried",
            "Work-related distractors outrank the actual employer slot.",
            [
                _m("The current working directory is the project root.", 10,
                   slot="current_working_directory", value="project root"),
                _m("Current work items are sorted by priority.", 9,
                   slot="current_work_sort", value="priority"),
                _m("The work queue is processed every hour.", 8, slot="work_queue", value="hourly"),
                _m("The office printer is maintained by Xerox.", 7, slot="printer_vendor", value="Xerox"),
                _m("Blue Orchard Studio issues my paycheck.", 2, slot="employer", value="Blue Orchard Studio"),
                _m("A job board suggested Northwind Systems.", 4, slot="employer", value="Northwind Systems",
                   authority="provisional", kind="observation", channel="assistant"),
                _m("The payroll export runs on Fridays.", 6, slot="payroll_schedule", value="Friday"),
                _m("The current task is editing product photos.", 5, slot="current_task", value="product photos"),
            ],
        ),
        Probe("current_employer", "Where am I currently working?", ("blue", "orchard"), ("northwind",)),
        True,
        "employer",
    ),
    FetchCase(
        Scenario(
            "fetch_previous_camera_buried",
            "Camera-adjacent distractors crowd out the historical system pair.",
            [
                _m("Before Blackmagic exports, verify the camera system folder.", 10,
                   slot="export_check", value="camera system folder"),
                _m("The Blackmagic camera system backup runs before editing.", 9,
                   slot="backup_schedule", value="before editing"),
                _m("The camera bag is waterproof.", 8, slot="camera_bag", value="waterproof"),
                _m("Camera batteries are stored in the top drawer.", 7, slot="battery_storage", value="top drawer"),
                _m("I started with an Olympus E-M10 system.", 1, slot="camera_system", value="Olympus E-M10"),
                _m("I later switched to a Blackmagic Pocket 6K.", 2, slot="camera_system",
                   value="Blackmagic Pocket 6K", prior="Olympus E-M10"),
                _m("A review recommended a Canon R6.", 5, slot="camera_system", value="Canon R6",
                   authority="provisional", kind="observation", channel="assistant"),
                _m("The tripod plate is Arca-Swiss.", 6, slot="tripod_plate", value="Arca-Swiss"),
            ],
        ),
        Probe("previous_camera_system", "Which camera system was before the Blackmagic?", ("olympus", "e-m10"), ("canon",)),
        True,
        "camera_system",
    ),
    FetchCase(
        Scenario(
            "fetch_policy_buried",
            "Deletion terminology retrieves operational notes before the locked policy.",
            [
                _m("Recursively delete the production media proxy cache after export.", 10,
                   slot="proxy_cache_cleanup", value="allowed"),
                _m("The recursive production media delete preview runs without asking.", 11,
                   slot="delete_preview", value="dry-run"),
                _m("The production media deletion report is generated before asking for review.", 9,
                   slot="deletion_report", value="generated"),
                _m("Delete temporary render files after export.", 8, slot="temp_render_cleanup", value="allowed"),
                _m("Recursive directory scans are enabled.", 7, slot="recursive_scan", value="enabled"),
                _m("Media vault release class is human-only.", 1,
                   slot="media.production_delete_without_confirmation", value="forbidden",
                   authority="locked", kind="policy"),
                _m("The recycle bin retains files for thirty days.", 6, slot="recycle_retention", value="30 days"),
                _m("A cleanup script can remove proxy media.", 5, slot="proxy_cleanup", value="allowed"),
                _m("Production media is mirrored nightly.", 4, slot="media_backup", value="nightly"),
            ],
        ),
        Probe(
            "production_media_delete_policy",
            "Can you recursively delete the production media without asking first?",
            ("no", "production", "confirmation"),
            expected_behavior="refuse",
        ),
        True,
        "media.production_delete_without_confirmation",
    ),
    FetchCase(
        Scenario(
            "control_current_project_visible",
            "The target current project should already be present in initial retrieval.",
            [
                _m("My current project is Emberline.", 9, slot="current_project", value="Emberline"),
                _m("The current project dashboard refreshes hourly.", 8, slot="dashboard_refresh", value="hourly"),
                _m("The archive project is Quarry.", 2, slot="archived_project", value="Quarry"),
                _m("The database is SQLite.", 6, slot="database", value="SQLite"),
                _m("A planning note mentions Harbor.", 5, slot="current_project", value="Harbor",
                   authority="provisional", kind="observation", channel="assistant"),
            ],
        ),
        Probe("current_project", "What is my current project?", ("emberline",), ("harbor", "quarry")),
        False,
        "current_project",
    ),
    FetchCase(
        Scenario(
            "control_store_platform_visible",
            "The confirmed store platform should be available without a second fetch.",
            [
                _m("My real store currently runs on a Flask commerce API.", 9,
                   slot="store_platform", value="Flask commerce API"),
                _m("The store status page refreshes every minute.", 8, slot="store_status_refresh", value="one minute"),
                _m("A consultant proposed BigCommerce.", 4, slot="store_platform", value="BigCommerce",
                   authority="provisional", kind="observation", channel="assistant"),
                _m("Payments use Stripe.", 7, slot="payments", value="Stripe"),
                _m("The docs use Markdown.", 6, slot="docs_format", value="Markdown"),
            ],
        ),
        Probe("confirmed_store_platform", "What does my real store currently run on?", ("flask", "commerce"), ("bigcommerce",)),
        False,
        "store_platform",
    ),
)

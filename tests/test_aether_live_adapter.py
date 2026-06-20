import json
from pathlib import Path

import pytest

from labs.meaning_compression_lab.aether_live_adapter import (
    AetherSubstrateError,
    ReadOnlyAetherAdapter,
    fingerprint,
)


def _write_substrate(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": "test",
                "slots": {
                    "user:employer": {
                        "namespace": "user",
                        "slot_name": "employer",
                        "slot_id": "user:employer",
                        "created_at": 1,
                    },
                    "project:framework": {
                        "namespace": "project",
                        "slot_name": "framework",
                        "slot_id": "project:framework",
                        "created_at": 1,
                    },
                },
                "states": {
                    "s1": {
                        "state_id": "s1",
                        "slot_id": "user:employer",
                        "value": "Microsoft",
                        "normalized": "microsoft",
                        "trust": 0.95,
                        "observed_at": 1,
                        "observation_id": "o1",
                        "temporal_status": "active",
                        "decay_rate": 0,
                        "source": "auto_ingest",
                        "superseded_by": "s2",
                    },
                    "s2": {
                        "state_id": "s2",
                        "slot_id": "user:employer",
                        "value": "Amazon",
                        "normalized": "amazon",
                        "trust": 0.8,
                        "observed_at": 2,
                        "observation_id": "o2",
                        "temporal_status": "active",
                        "decay_rate": 0,
                        "source": "user_correction",
                        "superseded_by": None,
                    },
                },
                "observations": {
                    "o1": {
                        "observation_id": "o1",
                        "source_text": "I work at Microsoft.",
                        "observed_at": 1,
                        "source_type": "auto_ingest",
                        "emitted_state_ids": ["s1"],
                        "metadata": {},
                    },
                    "o2": {
                        "observation_id": "o2",
                        "source_text": "Actually, I work at Amazon.",
                        "observed_at": 2,
                        "source_type": "user_correction",
                        "emitted_state_ids": ["s2"],
                        "metadata": {},
                    },
                },
                "edges": [],
            }
        ),
        encoding="utf-8",
    )


def test_catalog_retrieval_authority_and_read_only(tmp_path):
    path = tmp_path / "substrate.json"
    _write_substrate(path)
    before = fingerprint(path)
    adapter = ReadOnlyAetherAdapter(path)

    assert adapter.planner_slots() == ["employer", "framework"]
    current = adapter.retrieve("employer", mode="current")
    assert [item.value for item in current] == ["Amazon"]
    assert current[0].authority == "confirmed"
    assert current[0].releasable

    history = adapter.retrieve("employer", mode="history")
    assert [item.value for item in history] == ["Microsoft", "Amazon"]
    assert history[0].authority == "provisional"
    assert "unconfirmed_source" in history[0].quality_flags
    assert fingerprint(path) == before
    assert adapter.unchanged()


def test_placeholder_is_not_releasable_even_from_confirmed_source(tmp_path):
    path = tmp_path / "substrate.json"
    _write_substrate(path)
    data = json.loads(path.read_text())
    data["states"]["s2"]["value"] = "not mentioned"
    path.write_text(json.dumps(data))

    item = ReadOnlyAetherAdapter(path).retrieve("employer")[0]

    assert item.authority == "confirmed"
    assert not item.releasable
    assert "placeholder_value" in item.quality_flags


def test_missing_slot_reference_fails_closed(tmp_path):
    path = tmp_path / "substrate.json"
    _write_substrate(path)
    data = json.loads(path.read_text())
    data["states"]["s2"]["slot_id"] = "user:missing"
    path.write_text(json.dumps(data))

    with pytest.raises(AetherSubstrateError, match="missing slot"):
        ReadOnlyAetherAdapter(path)


def test_multiple_current_states_are_visible_but_not_releasable(tmp_path):
    path = tmp_path / "substrate.json"
    _write_substrate(path)
    data = json.loads(path.read_text())
    data["states"]["s1"]["superseded_by"] = None
    path.write_text(json.dumps(data))

    current = ReadOnlyAetherAdapter(path).retrieve("employer")

    assert [item.value for item in current] == ["Amazon", "Microsoft"]
    assert all("multiple_current_states" in item.quality_flags for item in current)
    assert not any(item.releasable for item in current)


def test_user_confirmation_is_releasable_authority(tmp_path):
    path = tmp_path / "substrate.json"
    _write_substrate(path)
    data = json.loads(path.read_text())
    data["states"]["s2"]["source"] = "user_confirmation"
    data["observations"]["o2"]["source_type"] = "user_confirmation"
    path.write_text(json.dumps(data))

    item = ReadOnlyAetherAdapter(path).retrieve("employer")[0]

    assert item.authority == "confirmed"
    assert item.releasable


def test_quarantine_marker_means_no_current_evidence(tmp_path):
    path = tmp_path / "substrate.json"
    _write_substrate(path)
    data = json.loads(path.read_text())
    data["states"]["s1"]["superseded_by"] = "sq"
    data["states"]["s2"]["superseded_by"] = "sq"
    data["states"]["sq"] = {
        "state_id": "sq",
        "slot_id": "user:employer",
        "value": "__quarantined__",
        "normalized": "__quarantined__",
        "trust": 1.0,
        "observed_at": 3,
        "observation_id": "oq",
        "temporal_status": "past",
        "decay_rate": 0,
        "source": "review_quarantine",
        "superseded_by": None,
    }
    data["observations"]["oq"] = {
        "observation_id": "oq",
        "source_text": "No trustworthy candidate.",
        "observed_at": 3,
        "source_type": "review_quarantine",
        "emitted_state_ids": ["sq"],
        "metadata": {},
    }
    path.write_text(json.dumps(data))

    adapter = ReadOnlyAetherAdapter(path)

    assert adapter.retrieve("employer", mode="current") == []
    assert [item.value for item in adapter.retrieve("employer", mode="history")] == [
        "Microsoft",
        "Amazon",
        "__quarantined__",
    ]

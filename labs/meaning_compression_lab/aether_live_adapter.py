"""Read-only bridge from Aether's persisted slot substrate into CRT labs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from labs.meaning_compression_lab.run_lab import Memory


CONFIRMED_SOURCES = {
    "manual",
    "user",
    "user_correction",
    "user_confirmation",
    "confirmed",
}
LOCKED_SOURCES = {"locked", "policy"}
PLACEHOLDER_VALUES = {
    "",
    "n/a",
    "na",
    "none",
    "not mentioned",
    "not specified",
    "unknown",
}


class AetherSubstrateError(ValueError):
    """Raised when persisted substrate data violates the read contract."""


@dataclass(frozen=True)
class FileFingerprint:
    sha256: str
    size: int
    modified_ns: int


@dataclass(frozen=True)
class LiveEvidence:
    slot_id: str
    state_id: str
    value: str
    normalized: str
    trust: float
    observed_at: float
    temporal_status: str
    source: str
    source_text: str
    superseded_by: str | None
    authority: str
    quality_flags: tuple[str, ...]
    releasable: bool

    def to_memory(self, *, prior_value: str | None = None) -> Memory:
        kind = "policy" if self.authority == "locked" else "user_fact"
        return Memory(
            text=self.source_text or self.value,
            kind=kind,
            authority=self.authority,
            channel=f"aether_substrate:{self.source}",
            timestamp=int(self.observed_at),
            slot=self.slot_id,
            value=self.value,
            prior_value=prior_value,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "state_id": self.state_id,
            "value": self.value,
            "normalized": self.normalized,
            "trust": self.trust,
            "observed_at": self.observed_at,
            "temporal_status": self.temporal_status,
            "source": self.source,
            "source_text": self.source_text,
            "superseded_by": self.superseded_by,
            "authority": self.authority,
            "quality_flags": list(self.quality_flags),
            "releasable": self.releasable,
        }


def fingerprint(path: Path) -> FileFingerprint:
    stat = path.stat()
    return FileFingerprint(
        hashlib.sha256(path.read_bytes()).hexdigest(),
        stat.st_size,
        stat.st_mtime_ns,
    )


class ReadOnlyAetherAdapter:
    """Parse persisted substrate JSON without importing or mutating Aether."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or (Path.home() / ".aether" / "substrate.json"))
        self._fingerprint = fingerprint(self.path)
        self._data = self._load()
        self._slots: dict[str, dict[str, Any]] = self._data["slots"]
        self._states: dict[str, dict[str, Any]] = self._data["states"]
        self._observations: dict[str, dict[str, Any]] = self._data["observations"]
        self._planner_to_slot = self._build_planner_catalog()
        self._validate_references()

    @property
    def initial_fingerprint(self) -> FileFingerprint:
        return self._fingerprint

    def unchanged(self) -> bool:
        return fingerprint(self.path) == self._fingerprint

    def planner_slots(self) -> list[str]:
        return sorted(self._planner_to_slot)

    def resolve_slot(self, planner_slot: str) -> str:
        try:
            return self._planner_to_slot[planner_slot]
        except KeyError as exc:
            raise AetherSubstrateError(
                f"unknown or ambiguous planner slot: {planner_slot}"
            ) from exc

    def retrieve(
        self,
        planner_slot: str,
        *,
        mode: str = "current",
        k: int = 4,
    ) -> list[LiveEvidence]:
        slot_id = self.resolve_slot(planner_slot)
        states = [
            state
            for state in self._states.values()
            if state.get("slot_id") == slot_id
        ]
        states.sort(key=lambda state: float(state.get("observed_at") or 0))
        if mode != "history":
            active = [
                state
                for state in states
                if not state.get("superseded_by")
                and state.get("source") != "review_quarantine"
            ]
            states = list(reversed(active))
        evidence = [self._evidence(state) for state in states[:max(0, k)]]
        current_values = {
            str(state.get("normalized") or state.get("value") or "").strip().lower()
            for state in states
        }
        if mode != "history" and len(current_values) > 1:
            evidence = [
                replace(
                    item,
                    quality_flags=tuple(
                        dict.fromkeys((*item.quality_flags, "multiple_current_states"))
                    ),
                    releasable=False,
                )
                for item in evidence
            ]
        return evidence

    def memories(
        self,
        planner_slot: str,
        *,
        mode: str = "current",
        k: int = 4,
    ) -> list[Memory]:
        evidence = self.retrieve(planner_slot, mode=mode, k=k)
        memories = []
        prior_value = None
        for item in evidence:
            memories.append(item.to_memory(prior_value=prior_value))
            prior_value = item.value
        return memories

    def stats(self) -> dict[str, Any]:
        provisional = 0
        releasable = 0
        flagged = 0
        current_conflicts = 0
        for state in self._states.values():
            item = self._evidence(state)
            provisional += item.authority == "provisional"
            releasable += item.releasable
            flagged += bool(item.quality_flags)
        for slot_id in self._slots:
            current = [
                state for state in self._states.values()
                if state.get("slot_id") == slot_id and not state.get("superseded_by")
            ]
            values = {
                str(state.get("normalized") or state.get("value") or "").strip().lower()
                for state in current
            }
            current_conflicts += len(values) > 1
        return {
            "path": str(self.path),
            "slots": len(self._slots),
            "states": len(self._states),
            "observations": len(self._observations),
            "planner_slots": len(self._planner_to_slot),
            "provisional_states": provisional,
            "releasable_states": releasable,
            "flagged_states": flagged,
            "current_conflict_slots": current_conflicts,
        }

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AetherSubstrateError(f"cannot read substrate: {exc}") from exc
        if not isinstance(data, dict):
            raise AetherSubstrateError("substrate root must be an object")
        for key in ("slots", "states", "observations"):
            if not isinstance(data.get(key), dict):
                raise AetherSubstrateError(f"substrate {key} must be an object")
        return data

    def _build_planner_catalog(self) -> dict[str, str]:
        by_name: dict[str, list[str]] = {}
        for slot_id, slot in self._slots.items():
            slot_name = str(slot.get("slot_name") or "")
            if not slot_name:
                raise AetherSubstrateError(f"slot {slot_id} has no slot_name")
            by_name.setdefault(slot_name, []).append(slot_id)
        catalog = {}
        for slot_name, slot_ids in by_name.items():
            if len(slot_ids) == 1:
                catalog[slot_name] = slot_ids[0]
            else:
                for slot_id in slot_ids:
                    catalog[slot_id] = slot_id
        return catalog

    def _validate_references(self) -> None:
        for state_id, state in self._states.items():
            if state.get("slot_id") not in self._slots:
                raise AetherSubstrateError(
                    f"state {state_id} references missing slot {state.get('slot_id')}"
                )

    def _evidence(self, state: dict[str, Any]) -> LiveEvidence:
        observation_id = str(state.get("observation_id") or "")
        observation = self._observations.get(observation_id) or {}
        source = str(state.get("source") or observation.get("source_type") or "unknown")
        value = str(state.get("value") or "")
        temporal_status = str(state.get("temporal_status") or "unknown")
        authority = _authority_for_source(source)
        flags = []
        if observation_id not in self._observations:
            flags.append("missing_observation")
        if value.strip().lower() in PLACEHOLDER_VALUES:
            flags.append("placeholder_value")
        if _looks_malformed(value):
            flags.append("malformed_value")
        if temporal_status != "active":
            flags.append(f"temporal_{temporal_status}")
        if authority == "provisional":
            flags.append("unconfirmed_source")
        releasable = authority in {"confirmed", "locked"} and not flags
        return LiveEvidence(
            slot_id=str(state.get("slot_id") or ""),
            state_id=str(state.get("state_id") or ""),
            value=value,
            normalized=str(state.get("normalized") or value.lower()),
            trust=float(state.get("trust") or 0),
            observed_at=float(state.get("observed_at") or 0),
            temporal_status=temporal_status,
            source=source,
            source_text=str(observation.get("source_text") or ""),
            superseded_by=state.get("superseded_by"),
            authority=authority,
            quality_flags=tuple(flags),
            releasable=releasable,
        )


def _authority_for_source(source: str) -> str:
    normalized = source.strip().lower()
    if normalized in LOCKED_SOURCES:
        return "locked"
    if normalized in CONFIRMED_SOURCES:
        return "confirmed"
    return "provisional"


def _looks_malformed(value: str) -> bool:
    return bool(
        re.search(r"(?:```|`?\s*[-=]>\s*`?|â€|ï¿½)", value)
        or len(value) > 500
    )

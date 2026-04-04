from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .types import ObjectiveCard


def load_objective_cards(path: Path) -> List[ObjectiveCard]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Objective cards file must be a JSON object.")
    items = raw.get("objectives")
    if not isinstance(items, list) or not items:
        raise ValueError("Objective cards file must include a non-empty 'objectives' list.")

    cards: List[ObjectiveCard] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Objective at index {idx} must be an object.")
        objective_id = str(item.get("objective_id") or "").strip()
        capability_target = str(item.get("capability_target") or "").strip()
        if not objective_id or not capability_target:
            raise ValueError(f"Objective at index {idx} missing required fields.")
        cards.append(
            ObjectiveCard(
                objective_id=objective_id,
                capability_target=capability_target,
                intent_constraints=[str(x) for x in (item.get("intent_constraints") or []) if str(x).strip()],
                expected_signals=[str(x) for x in (item.get("expected_signals") or []) if str(x).strip()],
                forbidden_behaviors=[str(x) for x in (item.get("forbidden_behaviors") or []) if str(x).strip()],
                escalation_policy=[str(x) for x in (item.get("escalation_policy") or []) if str(x).strip()],
                tags=[str(x) for x in (item.get("tags") or []) if str(x).strip()],
            )
        )
    return cards


@dataclass
class ObjectivePlanner:
    cards: List[ObjectiveCard]
    _index: int = 0
    _counts: Dict[str, int] = field(default_factory=dict)

    def next_objective(self, *, judge_hint: Optional[str] = None) -> ObjectiveCard:
        """Choose the next objective, favoring judge hints when valid."""
        if not self.cards:
            raise RuntimeError("No objective cards loaded.")

        by_id = {c.objective_id: c for c in self.cards}
        if judge_hint and judge_hint in by_id:
            card = by_id[judge_hint]
        else:
            card = self.cards[self._index % len(self.cards)]
            self._index += 1

        self._counts[card.objective_id] = int(self._counts.get(card.objective_id, 0)) + 1
        return card

    def stats(self) -> Dict[str, int]:
        return dict(self._counts)

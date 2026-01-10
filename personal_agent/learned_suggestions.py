"""Learned suggestion layer for CRT (suggestion-only).

This module is intentionally *non-authoritative*:
- It never overwrites memories.
- It never resolves contradictions automatically.
- It only produces recommendations (e.g., prefer latest value vs ask user to clarify)
  based on patterns learned from prior runs.

Model is optional. If no model is present, suggestions fall back to heuristics.

Typical usage:
- Train a model offline using crt_learn_train.py
- Point CRT to it via env var CRT_LEARNED_MODEL_PATH

"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


@dataclass(frozen=True)
class LearnedSuggestion:
    slot: str
    action: str  # e.g. "prefer_latest" | "ask_clarify"
    confidence: float
    recommended_value: Optional[Any] = None
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slot": self.slot,
            "action": self.action,
            "confidence": self.confidence,
            "recommended_value": self.recommended_value,
            "rationale": self.rationale,
        }


class LearnedSuggestionEngine:
    """Optional MLP-backed suggestion engine.

    The engine loads a scikit-learn Pipeline saved via joblib.
    Expected pipeline: DictVectorizer -> scaler -> classifier.

    If loading fails, the engine is disabled and suggestions are heuristic-only.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or os.environ.get("CRT_LEARNED_MODEL_PATH")
        self._model = None
        self._load_error: Optional[str] = None

    def is_enabled(self) -> bool:
        return self._model is not None

    def load_if_available(self) -> None:
        if self._model is not None:
            return
        if not self.model_path:
            return
        if not os.path.exists(self.model_path):
            return
        try:
            import joblib  # type: ignore

            self._model = joblib.load(self.model_path)
        except Exception as e:
            self._model = None
            self._load_error = str(e)

    def suggest_for_slots(
        self,
        *,
        slots: List[str],
        use_model: bool = True,
        # Dependencies are passed in so this module stays lightweight.
        all_user_memories: List[Any],
        open_contradictions: List[Any],
        extract_fact_slots_fn,
        infer_best_slot_value_fn,
    ) -> List[LearnedSuggestion]:
        """Return suggestion-only recommendations for the given slots."""
        if not slots:
            return []

        if use_model:
            self.load_if_available()

        suggestions: List[LearnedSuggestion] = []

        # Build quick per-slot aggregates from user memories
        slot_candidates: Dict[str, List[Tuple[Any, Any, str]]] = {s: [] for s in slots}
        for mem in all_user_memories:
            facts = extract_fact_slots_fn(getattr(mem, "text", ""))
            if not facts:
                continue
            for slot in slots:
                if slot in facts:
                    fact = facts[slot]
                    slot_candidates[slot].append((mem, fact.value, fact.normalized))

        open_conflict_by_slot: Dict[str, int] = {s: 0 for s in slots}
        # Conservative: treat "open contradictions" as a global tension indicator.
        # We don't reliably know which slot each contradiction pertains to here,
        # so avoid the prior bug where we multiplied count by number of slots.
        global_open = len(open_contradictions or [])
        for s in slots:
            open_conflict_by_slot[s] = global_open

        for slot in slots:
            candidates = slot_candidates.get(slot) or []
            best_value, best_meta = infer_best_slot_value_fn(slot, candidates)

            distinct_values = len({norm for _m, _v, norm in candidates if norm})
            trust_values = [_safe_float(getattr(m, "trust", 0.0)) for m, _v, _n in candidates]
            trust_max = max(trust_values) if trust_values else 0.0
            trust_min = min(trust_values) if trust_values else 0.0
            trust_gap = trust_max - trust_min

            # Base heuristic: if we have a best value and it was updated multiple times,
            # recommend preferring the latest value; otherwise ask.
            heuristic_action = "prefer_latest" if best_value is not None else "ask_clarify"
            heuristic_conf = 0.65 if heuristic_action == "prefer_latest" else 0.55

            features = {
                "slot": slot,
                "distinct_values": distinct_values,
                "open_contradictions_count": open_conflict_by_slot.get(slot, 0),
                "trust_max": trust_max,
                "trust_min": trust_min,
                "trust_gap": trust_gap,
                "has_value": 1 if best_value is not None else 0,
            }

            action = heuristic_action
            conf = heuristic_conf
            rationale = "heuristic" if not use_model else "heuristic"

            if use_model and self._model is not None:
                try:
                    # Predict over actions; classifier should have classes_.
                    proba = self._model.predict_proba([features])[0]
                    classes = list(getattr(self._model, "classes_", []))
                    if not classes:
                        # Pipeline case: classes are on last step
                        if hasattr(self._model, "named_steps"):
                            clf = self._model.named_steps.get("clf")
                            if clf is not None:
                                classes = list(getattr(clf, "classes_", []))
                    if classes:
                        best_i = int(max(range(len(proba)), key=lambda i: proba[i]))
                        action = str(classes[best_i])
                        conf = float(proba[best_i])
                        rationale = "learned"
                except Exception:
                    # Keep heuristic fallback.
                    pass

            suggestions.append(
                LearnedSuggestion(
                    slot=slot,
                    action=action,
                    confidence=conf,
                    recommended_value=best_value,
                    rationale=rationale if best_value is not None else "insufficient_data",
                )
            )

        return suggestions

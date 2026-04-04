"""Trust gate for DNNT training example admission."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple


@dataclass
class TrustGateConfig:
    min_fact_trust: float = 0.55
    max_unresolved_contradictions: int = 0
    require_groundcheck_pass: bool = False
    reject_if_corrected_within_turns: int = 0


class TrustGate:
    """Evaluates whether an example is clean enough for DNNT training."""

    def __init__(self, config: TrustGateConfig | None = None):
        self.config = config or TrustGateConfig()

    @staticmethod
    def _extract_fact_trusts(facts: Iterable[str]) -> list[float]:
        trusts: list[float] = []
        for item in facts:
            text = str(item or "")
            m = re.search(r"trust\s*=\s*([0-9]*\.?[0-9]+)", text, flags=re.IGNORECASE)
            if not m:
                m = re.search(r"\(([0-9]*\.?[0-9]+)\)\s*$", text)
            if m:
                try:
                    trusts.append(float(m.group(1)))
                except Exception:
                    pass
        return trusts

    def should_accept(self, *, facts: Iterable[str], meta: Dict[str, Any] | None = None) -> Tuple[bool, str]:
        info = dict(meta or {})
        trusts = self._extract_fact_trusts(facts)
        if trusts and max(trusts) < float(self.config.min_fact_trust):
            return False, f"fact_trust_below_threshold({max(trusts):.2f})"

        unresolved = int(info.get("unresolved_contradictions_total") or 0)
        if unresolved > int(self.config.max_unresolved_contradictions):
            return False, f"unresolved_contradictions({unresolved})"

        if self.config.require_groundcheck_pass and not bool(info.get("groundcheck_passed")):
            return False, "groundcheck_failed"

        correction_window = int(self.config.reject_if_corrected_within_turns or 0)
        if correction_window > 0:
            was_corrected = bool(info.get("was_corrected"))
            turns_since = info.get("turns_since_response")
            if was_corrected:
                if turns_since is None:
                    return False, "corrected_recently(unknown_turn_distance)"
                try:
                    turns_since_val = int(turns_since)
                except Exception:
                    turns_since_val = 0
                if turns_since_val <= correction_window:
                    return False, f"corrected_recently({turns_since_val})"

        return True, "accepted"

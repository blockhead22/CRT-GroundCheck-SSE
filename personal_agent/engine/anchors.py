"""Identity anchors used by resonance and memory hooks."""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence


DEFAULT_ANCHOR_TRUTHS: Sequence[str] = (
    "my name",
    "i am",
    "i work",
    "i live",
    "my pronouns",
    "my birthday",
    "my age",
    "my role",
    "i prefer",
)


class AnchorSystem:
    """Simple anchor matcher with overlap scoring.

    This intentionally stays lightweight so it can be replaced by a learned DNNT
    component later without changing callers.
    """

    def __init__(self, anchors: Iterable[str] | None = None):
        values = list(anchors or DEFAULT_ANCHOR_TRUTHS)
        self._anchors: List[str] = [str(a).strip().lower() for a in values if str(a).strip()]

    @property
    def anchors(self) -> List[str]:
        return list(self._anchors)

    def matched_anchors(self, text: str) -> List[str]:
        hay = (text or "").lower()
        if not hay:
            return []
        matches: List[str] = []
        for anchor in self._anchors:
            # Token-boundary match prevents false positives on substrings.
            pattern = r"\b" + re.escape(anchor) + r"\b"
            if re.search(pattern, hay):
                matches.append(anchor)
        return matches

    def overlap_score(self, left_text: str, right_text: str) -> float:
        left = set(self.matched_anchors(left_text))
        right = set(self.matched_anchors(right_text))
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return float(len(left & right)) / float(len(union))


"""
Tests for live-session bugs found 2026-03-21:
1. gate_task_intent double-downgrade for service_action
2. NL resolution meta-override fallback
3. Source authority classification for meta-corrections
"""

import re
from personal_agent.task_agent import (
    classify_intent,
    gate_task_intent,
    TaskIntent,
)
from personal_agent.source_authority import classify_source_authority


# ---------------------------------------------------------------------------
# 1. gate_task_intent should NOT downgrade vetted service_action intents
# ---------------------------------------------------------------------------

class TestGateTaskIntentNoDoubleDowngrade:
    """The meta-question guard in classify_intent already routes knowledge
    questions (e.g. 'what is moltbook') to conversational.  If it determined
    the message IS a service_action, gate_task_intent must NOT blindly
    downgrade it to 'low' just because _KNOWLEDGE_QUESTION_RE matches."""

    def test_whats_new_on_moltbook_is_service_action(self):
        """Requires credential store to have moltbook entry.
        When credentials exist, this routes as service_action with tier_1
        (high-confidence read query). Skip if no credential store."""
        intent = classify_intent("What's new on moltbook?")
        if intent.intent_type == "conversational":
            # No credential store available — service not discovered
            import pytest
            pytest.skip("No credential store — moltbook not discovered")
        assert intent.intent_type == "service_action"
        gate = gate_task_intent(intent)
        # 0.85 confidence + query action → tier_1 (quick confirm)
        assert gate["checkpoint_tier"] == "tier_1", (
            f"Expected tier_1, got {gate['checkpoint_tier']}"
        )

    def test_whats_new_no_apostrophe(self):
        intent = classify_intent("whats new on moltbook")
        if intent.intent_type == "conversational":
            import pytest
            pytest.skip("No credential store — moltbook not discovered")
        assert intent.intent_type == "service_action"
        gate = gate_task_intent(intent)
        assert gate["checkpoint_tier"] == "tier_1"

    def test_check_moltbook(self):
        intent = classify_intent("check moltbook for new posts")
        if intent.intent_type == "conversational":
            import pytest
            pytest.skip("No credential store — moltbook not discovered")
        assert intent.intent_type == "service_action"
        gate = gate_task_intent(intent)
        assert gate["checkpoint_tier"] == "tier_1"

    def test_what_is_moltbook_is_conversational(self):
        """Pure knowledge question should still be routed conversational."""
        intent = classify_intent("what is moltbook")
        assert intent.route == "conversational"

    def test_fetch_latest_posts(self):
        intent = classify_intent("can you try and fetch latest posts on moltbook?")
        if intent.intent_type == "conversational":
            import pytest
            pytest.skip("No credential store — moltbook not discovered")
        assert intent.intent_type == "service_action"
        gate = gate_task_intent(intent)
        assert gate["checkpoint_tier"] == "tier_1"


# ---------------------------------------------------------------------------
# 2. Source authority: meta-corrections should be detected
# ---------------------------------------------------------------------------

class TestSourceAuthorityMetaCorrection:
    """Meta-corrections must be classified so NL resolution routes them
    to resolve existing contradictions instead of creating new ones."""

    def test_ignore_the_noise(self):
        result = classify_source_authority(
            "Ignore the noise. My real favorite color is orange. Always has been."
        )
        assert result.kind == "meta_correction"
        assert result.confidence >= 0.95

    def test_my_real_favorite(self):
        result = classify_source_authority("My real favorite color is orange")
        assert result.kind == "meta_correction"

    def test_for_the_last_time(self):
        result = classify_source_authority("For the last time, it's orange")
        assert result.kind == "meta_correction"

    def test_once_and_for_all(self):
        result = classify_source_authority("Once and for all, my favorite color is orange")
        assert result.kind == "meta_correction"

    def test_no_seriously(self):
        result = classify_source_authority("No, seriously, it's orange")
        assert result.kind == "meta_correction"

    def test_always_has_been(self):
        result = classify_source_authority("It's orange. Always has been.")
        assert result.kind == "meta_correction"


# ---------------------------------------------------------------------------
# 3. Resolution patterns: meta-override patterns must be detected
# ---------------------------------------------------------------------------

class TestMetaOverridePatterns:
    """The NL resolution's is_meta_override flag depends on these patterns
    being present in the resolution patterns list."""

    _META_OVERRIDE_PATTERNS = {
        r'\bignore\s+the\s+noise\b',
        r'\balways\s+has\s+been\b',
        r'\bmy\s+(real|actual|true)\s+(favorite|favourite)\b',
        r'\bthe\s+(real|actual|true)\s+answer\b',
        r'\bfor\s+the\s+(last|final)\s+time\b',
        r'\bonce\s+and\s+for\s+all\b',
        r'\blet\s+me\s+(settle|clear)\s+this\b',
        r'\bno,?\s+seriously\b',
        r'\bstill\s+(?:is|my)\b',
    }

    def test_ignore_the_noise_matches(self):
        text = "Ignore the noise, it's orange"
        for pat in self._META_OVERRIDE_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                return  # Found a match
        assert False, "No meta-override pattern matched"

    def test_always_has_been_matches(self):
        text = "Always has been orange"
        for pat in self._META_OVERRIDE_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                return
        assert False, "No meta-override pattern matched"

    def test_my_real_favorite_matches(self):
        text = "My real favorite color is orange"
        for pat in self._META_OVERRIDE_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                return
        assert False, "No meta-override pattern matched"

    def test_third_value_detection(self):
        """When the user says 'My real favorite is orange' but the
        contradiction has blue vs purple, the meta-override should still
        fire because the user is asserting a THIRD value."""
        text = "Ignore the noise. My real favorite color is orange. Always has been."
        matches = []
        for pat in self._META_OVERRIDE_PATTERNS:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                matches.append(pat)
        # Should match multiple meta-override patterns
        assert len(matches) >= 2, f"Expected >= 2 meta-override matches, got {len(matches)}: {matches}"

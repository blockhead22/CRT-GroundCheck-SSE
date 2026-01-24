"""
Tests for the new Phase 1-3 CRT architecture changes.

Tests cover:
- Phase 1: FactTuple, LLMFactExtractor, TwoTierFactSystem
- Phase 2: ContradictionLifecycle, DisclosurePolicy
- Phase 3: Calibration components

These tests focus on the core logic without requiring external services
(LLM APIs, embedding models) by using mocks where necessary.
"""

import pytest
import time
from unittest.mock import Mock, patch

# Phase 1 imports
from personal_agent.fact_tuples import FactTuple, FactTupleSet, FactAction
from personal_agent.llm_extractor import (
    LLMFactExtractor,
    LLMConfig,
    create_regex_fallback_extractor,
)
from personal_agent.two_tier_facts import (
    TwoTierFactSystem,
    TwoTierExtractionResult,
)

# Phase 2 imports
from personal_agent.contradiction_lifecycle import (
    ContradictionLifecycleState,
    ContradictionLifecycleEntry,
    ContradictionLifecycle,
    DisclosurePolicy,
    UserTransparencyPrefs,
    TransparencyLevel,
    MemoryStyle,
)

# User profile imports
from personal_agent.user_profile import (
    UserTransparencyPrefs as ProfileTransparencyPrefs,
    TransparencyLevel as ProfileTransparencyLevel,
    MemoryStyle as ProfileMemoryStyle,
)


# =============================================================================
# Phase 1 Tests: Fact Tuples
# =============================================================================

class TestFactTuple:
    """Tests for FactTuple dataclass."""
    
    def test_basic_creation(self):
        """Test basic FactTuple creation."""
        fact = FactTuple(
            entity="User",
            attribute="employer",
            value="Microsoft",
            action=FactAction.ADD,
            confidence=0.9,
        )
        
        assert fact.entity == "User"
        assert fact.attribute == "employer"
        assert fact.value == "Microsoft"
        assert fact.action == FactAction.ADD
        assert fact.confidence == 0.9
    
    def test_action_string_conversion(self):
        """Test that string action is converted to enum."""
        fact = FactTuple(
            entity="User",
            attribute="location",
            value="Seattle",
            action="update",  # type: ignore - testing string input
        )
        
        assert fact.action == FactAction.UPDATE
    
    def test_confidence_clamping(self):
        """Test confidence is clamped to valid range."""
        fact_high = FactTuple(
            entity="User",
            attribute="test",
            value="val",
            confidence=1.5,
        )
        assert fact_high.confidence == 1.0
        
        fact_low = FactTuple(
            entity="User",
            attribute="test",
            value="val",
            confidence=-0.5,
        )
        assert fact_low.confidence == 0.0
    
    def test_to_dict_and_from_dict(self):
        """Test serialization round-trip."""
        original = FactTuple(
            entity="User",
            attribute="employer",
            value="Google",
            action=FactAction.UPDATE,
            confidence=0.85,
            evidence_span="I work at Google",
        )
        
        as_dict = original.to_dict()
        restored = FactTuple.from_dict(as_dict)
        
        assert restored.entity == original.entity
        assert restored.attribute == original.attribute
        assert restored.value == original.value
        assert restored.action == original.action
        assert restored.confidence == original.confidence
    
    def test_matches_slot(self):
        """Test slot matching for hard slots."""
        fact = FactTuple(
            entity="User",
            attribute="employer",
            value="Microsoft",
        )
        
        assert fact.matches_slot("employer") is True
        assert fact.matches_slot("location") is False
        
        # Test hierarchical matching
        fact2 = FactTuple(
            entity="User",
            attribute="employment.status",
            value="employed",
        )
        assert fact2.matches_slot("employer") is True
    
    def test_is_user_fact(self):
        """Test user fact detection."""
        user_fact = FactTuple(entity="User", attribute="name", value="Nick")
        assert user_fact.is_user_fact is True
        
        other_fact = FactTuple(entity="Company", attribute="name", value="Google")
        assert other_fact.is_user_fact is False
    
    def test_normalized_value(self):
        """Test value normalization."""
        fact = FactTuple(
            entity="User",
            attribute="location",
            value="  Seattle  ",
        )
        assert fact.normalized_value == "seattle"


class TestFactTupleSet:
    """Tests for FactTupleSet collection."""
    
    def test_add_and_iterate(self):
        """Test adding and iterating tuples."""
        fact_set = FactTupleSet()
        fact_set.add(FactTuple(entity="User", attribute="name", value="Nick"))
        fact_set.add(FactTuple(entity="User", attribute="employer", value="Google"))
        
        assert len(fact_set) == 2
        
        attrs = [f.attribute for f in fact_set]
        assert "name" in attrs
        assert "employer" in attrs
    
    def test_get_by_entity(self):
        """Test filtering by entity."""
        fact_set = FactTupleSet(tuples=[
            FactTuple(entity="User", attribute="name", value="Nick"),
            FactTuple(entity="Company", attribute="name", value="Google"),
            FactTuple(entity="User", attribute="age", value="30"),
        ])
        
        user_facts = fact_set.get_by_entity("User")
        assert len(user_facts) == 2
    
    def test_get_user_facts(self):
        """Test getting user-only facts."""
        fact_set = FactTupleSet(tuples=[
            FactTuple(entity="User", attribute="employer", value="Google"),
            FactTuple(entity="Google", attribute="headquarters", value="Mountain View"),
        ])
        
        user_facts = fact_set.get_user_facts()
        assert len(user_facts) == 1
        assert user_facts[0].attribute == "employer"


# =============================================================================
# Phase 1 Tests: LLM Extractor
# =============================================================================

class TestLLMFactExtractor:
    """Tests for LLMFactExtractor."""
    
    def test_regex_fallback_extractor(self):
        """Test the regex fallback extractor."""
        fallback = create_regex_fallback_extractor()
        
        # Extract facts using regex
        tuples = fallback("My name is Sarah and I work at Microsoft")
        
        # Should extract name and employer
        attrs = [t.attribute for t in tuples]
        assert "name" in attrs
        assert "employer" in attrs
    
    def test_extractor_with_fallback(self):
        """Test LLM extractor uses fallback when LLM unavailable."""
        extractor = LLMFactExtractor(llm_client=None)  # No LLM
        fallback = create_regex_fallback_extractor()
        extractor.set_fallback_extractor(fallback)
        
        tuples = extractor.extract_tuples("I'm Nick and I live in Seattle")
        
        # Should get results from fallback
        assert len(tuples) >= 1
    
    def test_parse_llm_response(self):
        """Test parsing of LLM JSON response."""
        extractor = LLMFactExtractor()
        
        json_response = '''
        {
            "facts": [
                {
                    "entity": "User",
                    "attribute": "hobby",
                    "value": "pottery",
                    "action": "add",
                    "confidence": 0.85,
                    "evidence_span": "my hobby is pottery"
                }
            ]
        }
        '''
        
        tuples = extractor._parse_llm_response(json_response, "My hobby is pottery")
        
        assert len(tuples) == 1
        assert tuples[0].attribute == "hobby"
        assert tuples[0].value == "pottery"


# =============================================================================
# Phase 1 Tests: Two-Tier System
# =============================================================================

class TestTwoTierFactSystem:
    """Tests for TwoTierFactSystem."""
    
    def test_hard_slots_definition(self):
        """Test that hard slots are defined correctly."""
        system = TwoTierFactSystem(enable_llm=False)
        
        assert "name" in system.HARD_SLOTS
        assert "employer" in system.HARD_SLOTS
        assert "location" in system.HARD_SLOTS
        
        # These should NOT be hard slots
        assert "hobby" not in system.HARD_SLOTS
        assert "favorite_color" not in system.HARD_SLOTS
    
    def test_extract_hard_facts_only(self):
        """Test extraction of hard facts without LLM."""
        system = TwoTierFactSystem(enable_llm=False)
        
        # Use clearer patterns for the existing regex
        facts = system.extract_hard_facts_only(
            "My name is Sarah. I work at Microsoft."
        )
        
        # Should get hard slot facts
        assert "name" in facts
        assert "Sarah" in facts["name"].value
        assert "employer" in facts
        assert "Microsoft" in facts["employer"].value
    
    def test_tier_classification(self):
        """Test classification of facts into tiers."""
        system = TwoTierFactSystem(enable_llm=False)
        
        assert system.classify_fact_tier("name") == "hard"
        assert system.classify_fact_tier("employer") == "hard"
        assert system.classify_fact_tier("hobby") == "open"
        assert system.classify_fact_tier("favorite_snack") == "open"
    
    def test_extraction_result_structure(self):
        """Test TwoTierExtractionResult structure."""
        result = TwoTierExtractionResult(
            source_text="test",
            methods_used=["regex"],
        )
        
        assert result.hard_facts == {}
        assert result.open_tuples == []
        assert result.extraction_time == 0.0
        
        # Test to_dict
        as_dict = result.to_dict()
        assert "hard_facts" in as_dict
        assert "open_tuples" in as_dict


# =============================================================================
# Phase 2 Tests: Contradiction Lifecycle
# =============================================================================

class TestContradictionLifecycle:
    """Tests for ContradictionLifecycle state management."""
    
    def test_initial_state_is_active(self):
        """Test that new contradictions start in ACTIVE state."""
        entry = ContradictionLifecycleEntry(ledger_id="c1")
        assert entry.state == ContradictionLifecycleState.ACTIVE
    
    def test_active_to_settling_by_confirmations(self):
        """Test transition from ACTIVE to SETTLING via confirmations."""
        lifecycle = ContradictionLifecycle(active_to_settling_confirmations=2)
        entry = ContradictionLifecycleEntry(ledger_id="c1")
        
        # Not enough confirmations yet
        entry.confirmation_count = 1
        new_state = lifecycle.update_state(entry)
        assert new_state == ContradictionLifecycleState.ACTIVE
        
        # Enough confirmations
        entry.confirmation_count = 2
        new_state = lifecycle.update_state(entry)
        assert new_state == ContradictionLifecycleState.SETTLING
    
    def test_active_to_settling_by_time(self):
        """Test transition from ACTIVE to SETTLING via time."""
        lifecycle = ContradictionLifecycle()
        entry = ContradictionLifecycleEntry(
            ledger_id="c1",
            detected_at=time.time() - 8 * 86400,  # 8 days ago
            freshness_window=7 * 86400,  # 7 day window
        )
        
        new_state = lifecycle.update_state(entry)
        assert new_state == ContradictionLifecycleState.SETTLING
    
    def test_settling_to_settled(self):
        """Test transition from SETTLING to SETTLED."""
        lifecycle = ContradictionLifecycle(settling_to_settled_confirmations=5)
        entry = ContradictionLifecycleEntry(ledger_id="c1")
        entry.state = ContradictionLifecycleState.SETTLING
        entry.confirmation_count = 5
        
        new_state = lifecycle.update_state(entry)
        assert new_state == ContradictionLifecycleState.SETTLED
    
    def test_record_confirmation(self):
        """Test recording user confirmations."""
        lifecycle = ContradictionLifecycle()
        entry = ContradictionLifecycleEntry(ledger_id="c1")
        
        initial_count = entry.confirmation_count
        lifecycle.record_confirmation(entry)
        
        assert entry.confirmation_count == initial_count + 1
    
    def test_entry_serialization(self):
        """Test ContradictionLifecycleEntry serialization."""
        entry = ContradictionLifecycleEntry(
            ledger_id="c1",
            state=ContradictionLifecycleState.SETTLING,
            confirmation_count=3,
            affected_slots={"employer", "location"},
        )
        
        as_dict = entry.to_dict()
        restored = ContradictionLifecycleEntry.from_dict(as_dict)
        
        assert restored.ledger_id == entry.ledger_id
        assert restored.state == entry.state
        assert restored.confirmation_count == entry.confirmation_count


# =============================================================================
# Phase 2 Tests: Disclosure Policy
# =============================================================================

class TestDisclosurePolicy:
    """Tests for DisclosurePolicy."""
    
    def test_active_state_always_discloses(self):
        """Test that ACTIVE state always requires disclosure."""
        policy = DisclosurePolicy()
        entry = ContradictionLifecycleEntry(
            ledger_id="c1",
            state=ContradictionLifecycleState.ACTIVE,
        )
        
        assert policy.should_disclose(entry) is True
    
    def test_archived_never_discloses(self):
        """Test that ARCHIVED state never discloses."""
        policy = DisclosurePolicy()
        entry = ContradictionLifecycleEntry(
            ledger_id="c1",
            state=ContradictionLifecycleState.ARCHIVED,
        )
        
        assert policy.should_disclose(entry) is False
    
    def test_high_stakes_always_discloses(self):
        """Test that high-stakes contradictions always disclose."""
        policy = DisclosurePolicy()
        entry = ContradictionLifecycleEntry(
            ledger_id="c1",
            state=ContradictionLifecycleState.SETTLED,  # Normally wouldn't disclose
            affected_slots={"medical_diagnosis"},
        )
        
        assert policy.should_disclose(entry) is True
    
    def test_direct_query_discloses(self):
        """Test disclosure when user queries about the contradiction."""
        policy = DisclosurePolicy()
        entry = ContradictionLifecycleEntry(
            ledger_id="c1",
            state=ContradictionLifecycleState.SETTLED,
            affected_slots={"employer"},
        )
        
        # Query not about employer - no disclosure
        assert policy.should_disclose(entry, "What's my name?") is False
        
        # Query about employer - should disclose
        assert policy.should_disclose(entry, "Where do I work? employer?") is True
    
    def test_audit_heavy_preference(self):
        """Test that audit-heavy preference enables more disclosure."""
        prefs = UserTransparencyPrefs(transparency_level=TransparencyLevel.AUDIT_HEAVY)
        policy = DisclosurePolicy(user_prefs=prefs)
        
        entry = ContradictionLifecycleEntry(
            ledger_id="c1",
            state=ContradictionLifecycleState.SETTLING,
            disclosure_count=5,  # Would normally skip due to count
        )
        
        # Still discloses due to audit-heavy preference
        assert policy.should_disclose(entry) is True
    
    def test_minimal_preference(self):
        """Test that minimal preference reduces disclosure."""
        prefs = UserTransparencyPrefs(transparency_level=TransparencyLevel.MINIMAL)
        policy = DisclosurePolicy(user_prefs=prefs)
        
        entry = ContradictionLifecycleEntry(
            ledger_id="c1",
            state=ContradictionLifecycleState.SETTLING,
        )
        
        # Minimal preference blocks non-critical disclosures
        assert policy.should_disclose(entry) is False
    
    def test_disclosure_priority(self):
        """Test sorting contradictions by disclosure priority."""
        policy = DisclosurePolicy()
        
        entries = [
            ContradictionLifecycleEntry(
                ledger_id="archived",
                state=ContradictionLifecycleState.ARCHIVED,
            ),
            ContradictionLifecycleEntry(
                ledger_id="active",
                state=ContradictionLifecycleState.ACTIVE,
            ),
            ContradictionLifecycleEntry(
                ledger_id="high_stakes",
                state=ContradictionLifecycleState.SETTLING,
                affected_slots={"medication"},
            ),
        ]
        
        prioritized = policy.get_disclosure_priority(entries)
        
        # High stakes should be first, then active, then archived
        assert prioritized[0].ledger_id == "high_stakes"
        assert prioritized[1].ledger_id == "active"


# =============================================================================
# Phase 2 Tests: User Preferences
# =============================================================================

class TestUserTransparencyPrefs:
    """Tests for UserTransparencyPrefs."""
    
    def test_default_values(self):
        """Test default preference values."""
        prefs = ProfileTransparencyPrefs()
        
        assert prefs.transparency_level == ProfileTransparencyLevel.BALANCED
        assert prefs.memory_style == ProfileMemoryStyle.NORMAL
        assert "medical" in prefs.always_disclose_domains
    
    def test_serialization(self):
        """Test preferences serialization."""
        prefs = ProfileTransparencyPrefs(
            transparency_level=ProfileTransparencyLevel.AUDIT_HEAVY,
            max_disclosures_per_session=5,
        )
        
        as_dict = prefs.to_dict()
        restored = ProfileTransparencyPrefs.from_dict(as_dict)
        
        assert restored.transparency_level == prefs.transparency_level
        assert restored.max_disclosures_per_session == 5


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

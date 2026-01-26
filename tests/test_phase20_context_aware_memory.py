"""
Phase 2.0 Context-Aware Memory Tests

Tests for:
1. Domain detection
2. Temporal status extraction
3. Contextual fact extraction
4. Context-aware contradiction detection
"""

import pytest
from personal_agent.domain_detector import (
    detect_domains,
    detect_query_domains,
    domains_are_compatible,
    get_domain_overlap,
)
from personal_agent.fact_slots import (
    extract_temporal_status,
    extract_fact_slots_contextual,
    TemporalStatus,
    is_temporal_update,
    domains_overlap,
)
from personal_agent.crt_core import CRTMath


class TestDomainDetection:
    """Tests for domain detection functionality."""
    
    def test_print_shop_domain_detected(self):
        """Print shop keywords should detect print_shop domain."""
        text = "I run a sticker print shop and do vinyl decals for customers"
        domains = detect_domains(text)
        assert "print_shop" in domains
    
    def test_programming_domain_detected(self):
        """Programming keywords should detect programming domain."""
        text = "I am a software developer who codes in Python"
        domains = detect_domains(text)
        assert "programming" in domains
    
    def test_photography_domain_detected(self):
        """Photography keywords should detect photography domain."""
        text = "I do wedding photography and portrait shoots"
        domains = detect_domains(text)
        assert "photography" in domains
    
    def test_multiple_domains_detected(self):
        """Text with multiple domain keywords should detect multiple domains."""
        text = "I run a small business doing print and photography work"
        domains = detect_domains(text)
        assert len(domains) > 1
    
    def test_no_domains_returns_general(self):
        """Text with no specific keywords returns 'general'."""
        text = "Hello there"
        domains = detect_domains(text)
        assert domains == ["general"]
    
    def test_query_domain_detection(self):
        """Query domain detection for retrieval filtering."""
        query = "What's my most recent sticker order?"
        domains = detect_query_domains(query)
        assert "print_shop" in domains or "career" in domains


class TestDomainCompatibility:
    """Tests for domain compatibility checks."""
    
    def test_different_domains_compatible(self):
        """Different domains should be compatible (can coexist)."""
        assert domains_are_compatible(["programming"], ["photography"])
    
    def test_same_domains_not_compatible(self):
        """Same domains should not be compatible (potential conflict)."""
        assert not domains_are_compatible(["programming"], ["programming", "web_dev"])
    
    def test_general_domain_compatible_with_all(self):
        """'general' domain should be compatible with everything."""
        assert domains_are_compatible(["general"], ["programming"])
        assert domains_are_compatible(["photography"], ["general"])
    
    def test_domain_overlap_detection(self):
        """Domain overlap detection should work correctly."""
        overlap = get_domain_overlap(["programming", "web_dev"], ["web_dev", "design"])
        assert "web_dev" in overlap


class TestTemporalExtraction:
    """Tests for temporal status extraction."""
    
    def test_past_status_used_to(self):
        """'used to' pattern should indicate past status."""
        status, _ = extract_temporal_status("I used to work at Google")
        assert status == TemporalStatus.PAST
    
    def test_past_status_no_longer(self):
        """'no longer' pattern should indicate past status."""
        status, _ = extract_temporal_status("I no longer work at Amazon")
        assert status == TemporalStatus.PAST
    
    def test_past_status_dont_anymore(self):
        """'don't ... anymore' pattern should indicate past status."""
        status, _ = extract_temporal_status("I don't work at Microsoft anymore")
        assert status == TemporalStatus.PAST
    
    def test_active_status_currently(self):
        """'currently' pattern should indicate active status."""
        status, _ = extract_temporal_status("I currently work at Meta")
        assert status == TemporalStatus.ACTIVE
    
    def test_active_status_default(self):
        """Default status should be active."""
        status, _ = extract_temporal_status("I work at Apple")
        assert status == TemporalStatus.ACTIVE
    
    def test_future_status_will(self):
        """'will' pattern should indicate future status."""
        status, _ = extract_temporal_status("I will start at Netflix next month")
        assert status == TemporalStatus.FUTURE
    
    def test_potential_status_might(self):
        """'might' pattern should indicate potential status."""
        status, _ = extract_temporal_status("I might take the job at Tesla")
        assert status == TemporalStatus.POTENTIAL
    
    def test_period_extraction(self):
        """Date ranges should be extracted."""
        _, period = extract_temporal_status("I worked at Google from 2020-2024")
        assert period is not None
        assert "2020" in period


class TestContextualFactExtraction:
    """Tests for contextual fact extraction with temporal/domain metadata."""
    
    def test_contextual_extraction_includes_temporal(self):
        """Contextual extraction should include temporal status."""
        facts = extract_fact_slots_contextual("I used to work at Walmart")
        assert len(facts) > 0
        for slot, fact in facts.items():
            assert hasattr(fact, "temporal_status")
    
    def test_contextual_extraction_includes_domains(self):
        """Contextual extraction should include domain tags."""
        # Use text with a clear extractable fact
        facts = extract_fact_slots_contextual("I work at Microsoft as a developer")
        assert len(facts) > 0
        for slot, fact in facts.items():
            assert hasattr(fact, "domains")


class TestContextAwareContradictionDetection:
    """Tests for Phase 2.0 context-aware contradiction detection."""
    
    def setup_method(self):
        """Set up CRTMath for testing."""
        self.crt = CRTMath()
    
    def test_temporal_update_not_contradiction(self):
        """
        'I don't work at Google anymore' is a temporal update, not contradiction.
        """
        is_contra, reason = self.crt.is_true_contradiction_contextual(
            slot="employer",
            value_new="left:google",
            value_prior="google",
            temporal_status_new="past",
            temporal_status_prior="active",
            domains_new=["career"],
            domains_prior=["career"],
        )
        assert not is_contra
        assert "temporal" in reason.lower()
    
    def test_different_domains_coexist(self):
        """
        'I'm a programmer' + 'I'm a photographer' = multi-role, not conflict.
        """
        is_contra, reason = self.crt.is_true_contradiction_contextual(
            slot="occupation",
            value_new="photographer",
            value_prior="programmer",
            temporal_status_new="active",
            temporal_status_prior="active",
            domains_new=["photography"],
            domains_prior=["programming"],
        )
        assert not is_contra
        assert "domain" in reason.lower() or "coexist" in reason.lower()
    
    def test_true_contradiction_same_context(self):
        """
        Same slot + same domain + same time + different values = TRUE conflict.
        """
        is_contra, reason = self.crt.is_true_contradiction_contextual(
            slot="employer",
            value_new="amazon",
            value_prior="microsoft",
            temporal_status_new="active",
            temporal_status_prior="active",
            domains_new=["career", "programming"],
            domains_prior=["career", "programming"],
        )
        assert is_contra
        assert "true_contradiction" in reason.lower()
    
    def test_both_past_no_conflict(self):
        """
        Both facts in the past = historical, not current contradiction.
        """
        is_contra, reason = self.crt.is_true_contradiction_contextual(
            slot="employer",
            value_new="facebook",
            value_prior="google",
            temporal_status_new="past",
            temporal_status_prior="past",
            domains_new=["career"],
            domains_prior=["career"],
        )
        assert not is_contra
        assert "past" in reason.lower()
    
    def test_temporal_deprecation_not_contradiction(self):
        """
        New fact marks old fact as 'past' = temporal deprecation, not conflict.
        """
        is_contra, reason = self.crt.is_true_contradiction_contextual(
            slot="employer",
            value_new="new_company",
            value_prior="old_company",
            temporal_status_new="past",  # New fact says "I used to work at X"
            temporal_status_prior="active",
        )
        assert not is_contra
        assert "temporal" in reason.lower() or "deprecation" in reason.lower()
    
    def test_same_value_not_contradiction(self):
        """Same normalized value should not be a contradiction."""
        is_contra, reason = self.crt.is_true_contradiction_contextual(
            slot="name",
            value_new="Nick",
            value_prior="nick",  # Different case but same value
            temporal_status_new="active",
            temporal_status_prior="active",
        )
        assert not is_contra


class TestFactChangeClassification:
    """Tests for fact change type classification."""
    
    def setup_method(self):
        """Set up CRTMath for testing."""
        self.crt = CRTMath()
    
    def test_revision_classification(self):
        """Explicit corrections should be classified as 'revision'."""
        result = self.crt.classify_fact_change(
            slot="employer",
            value_new="Microsoft",
            value_prior="Amazon",
            text_new="Actually I work at Microsoft, not Amazon"
        )
        assert result == "revision"
    
    def test_temporal_classification(self):
        """Time-based progressions should be classified as 'temporal'."""
        result = self.crt.classify_fact_change(
            slot="title",
            value_new="Senior Developer",
            value_prior="Developer",
            text_new="I recently got promoted to Senior Developer"
        )
        assert result == "temporal"
    
    def test_refinement_classification(self):
        """More specific information should be classified as 'refinement'."""
        result = self.crt.classify_fact_change(
            slot="location",
            value_new="Bellevue, Seattle area",
            value_prior="Seattle",
            text_new="I live in Bellevue, in the Seattle area"
        )
        assert result == "refinement"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

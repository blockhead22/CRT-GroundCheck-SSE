"""
Governance Layer Integration Tests

Tests the GovernanceLayer wrapper that orchestrates all five immune agents.
Validates tiered response logic, lazy evaluation, and correct dispatch.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from unittest.mock import MagicMock, patch
from personal_agent.governance import (
    GovernanceLayer,
    GovernedResponse,
    GovernanceTier,
    GovernanceAnnotation,
)
from personal_agent.immune_agents import (
    Classification,
    DetectionResult,
    Contradiction,
    Disposition,
    ResolutionAction,
    VerdictAction as ResolutionVerdictAction,
)
from personal_agent.immune_agents.speech_leak_detector import MemoryRecord, VerdictType
from personal_agent.immune_agents.memory_corruption_guard import (
    Memory as ImmuneMemory,
    OverwriteReason,
    OverwriteAction,
)
from personal_agent.immune_agents.gap_auditor import Severity, Action as GapAction

import numpy as np


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gov():
    """GovernanceLayer with a dummy embedding function (no model needed)."""
    def dummy_embed(text: str) -> np.ndarray:
        rng = np.random.RandomState(hash(text) % 2**31)
        vec = rng.randn(384).astype(np.float32)
        return vec / np.linalg.norm(vec)
    return GovernanceLayer(embedding_fn=dummy_embed)


@pytest.fixture
def grounded_memories():
    """A set of existing memories with real trust and embeddings."""
    rng = np.random.RandomState(42)
    memories = []
    texts = [
        "The capital of France is Paris",
        "Water boils at 100 degrees Celsius at sea level",
        "The Earth orbits the Sun",
    ]
    for t in texts:
        vec = rng.randn(384).astype(np.float32)
        vec /= np.linalg.norm(vec)
        memories.append(MemoryRecord(text=t, trust=0.9, source="user", embedding=vec))
    return memories


# ---------------------------------------------------------------------------
# Response governance tests
# ---------------------------------------------------------------------------

class TestGovernResponse:

    def test_safe_factual_response(self, gov):
        """Factual response with high belief confidence → SAFE, no annotations."""
        result = gov.govern_response(
            text="The capital of France is Paris.",
            belief_confidence=0.9,
            domain="factual_settled",
        )
        assert result.tier == GovernanceTier.SAFE
        assert len(result.annotations) == 0
        assert result.should_block is False
        assert result.confidence_adjustment == 0.0

    def test_template_lock_detected(self, gov):
        """Hedged moral response → template detected → FLAG tier."""
        hedged = (
            "This is a complex and nuanced issue. There are multiple perspectives "
            "to consider. Some people believe one thing, while others disagree. "
            "It really depends on individual values and context. Both sides have "
            "valid points, and reasonable people can disagree."
        )
        result = gov.govern_response(
            text=hedged,
            belief_confidence=0.8,  # high belief — but template lock overrides
            domain="moral_clear",
        )
        # Template detector should catch the hedge patterns
        assert result.tier in (GovernanceTier.FLAG, GovernanceTier.HEDGE)
        assert any(a.agent == "template_detector" for a in result.annotations)

    def test_low_belief_triggers_gap_auditor(self, gov):
        """Low belief confidence (< 0.5) triggers GapAuditor even without template."""
        result = gov.govern_response(
            text="Quantum mechanics is straightforward.",
            belief_confidence=0.2,
            domain="factual_contested",
        )
        # GapAuditor should have run (belief < 0.5)
        gap_entries = [e for e in result.audit_log if e["agent"] == "gap_auditor"]
        assert len(gap_entries) == 1, "GapAuditor should run when belief_confidence < 0.5"

    def test_high_belief_no_template_skips_gap_auditor(self, gov):
        """High belief + no template → GapAuditor NOT called (lazy eval)."""
        result = gov.govern_response(
            text="The Earth orbits the Sun.",
            belief_confidence=0.95,
        )
        gap_entries = [e for e in result.audit_log if e["agent"] == "gap_auditor"]
        assert len(gap_entries) == 0, "GapAuditor should not run when belief is high and no template"

    def test_confident_speech_low_belief_escalates(self, gov):
        """Definitely X with low belief → GapAuditor should flag or escalate."""
        result = gov.govern_response(
            text="The answer is definitely 42. There is no question about this. "
                 "This is absolutely certain and undeniably true.",
            belief_confidence=0.1,
        )
        # Should at minimum be FLAG, likely HEDGE or ESCALATE
        assert result.tier != GovernanceTier.SAFE
        assert len(result.annotations) > 0

    def test_audit_log_always_has_template_detector(self, gov):
        """Template detector entry always present in audit log."""
        result = gov.govern_response(text="Hello", belief_confidence=0.5)
        agents_logged = [e["agent"] for e in result.audit_log]
        assert "template_detector" in agents_logged

    def test_governed_response_passed_property(self, gov):
        """GovernedResponse.passed is True for SAFE and FLAG."""
        safe = GovernedResponse(original_text="x", tier=GovernanceTier.SAFE)
        flag = GovernedResponse(original_text="x", tier=GovernanceTier.FLAG)
        hedge = GovernedResponse(original_text="x", tier=GovernanceTier.HEDGE)
        escalate = GovernedResponse(original_text="x", tier=GovernanceTier.ESCALATE)
        assert safe.passed is True
        assert flag.passed is True
        assert hedge.passed is False
        assert escalate.passed is False


# ---------------------------------------------------------------------------
# Memory write governance tests
# ---------------------------------------------------------------------------

class TestGovernMemoryWrite:

    def test_user_source_passes(self, gov, grounded_memories):
        """User-sourced memory write → SAFE (trusted source, no leak check needed)."""
        result = gov.govern_memory_write(
            text="My birthday is March 5th",
            proposed_trust=0.9,
            source="user",
            existing_memories=grounded_memories,
        )
        assert result.tier == GovernanceTier.SAFE
        assert result.should_block is False

    def test_generated_high_trust_downgraded(self, gov, grounded_memories):
        """Generated text with high trust and no grounding → HEDGE or ESCALATE."""
        result = gov.govern_memory_write(
            text="The meaning of life is 42",
            proposed_trust=0.9,
            source="generated",
            existing_memories=grounded_memories,
        )
        # SpeechLeakDetector should catch generated source trying to write at 0.9
        assert result.tier in (GovernanceTier.HEDGE, GovernanceTier.ESCALATE)
        assert any(a.agent == "speech_leak_detector" for a in result.annotations)

    def test_generated_low_trust_still_governed(self, gov, grounded_memories):
        """Generated text even at zero trust → SpeechLeakDetector still evaluates."""
        result = gov.govern_memory_write(
            text="Maybe the cat is orange",
            proposed_trust=0.0,
            source="generated",
            existing_memories=grounded_memories,
        )
        # Detector still fires on generated sources regardless of trust level
        sld_entries = [e for e in result.audit_log if e["agent"] == "speech_leak_detector"]
        assert len(sld_entries) == 1

    def test_overwrite_with_degraded_fidelity_blocked(self, gov, grounded_memories):
        """Overwriting trusted memory with low-fidelity reconstruction → ESCALATE."""
        existing = ImmuneMemory(
            id="mem_001",
            content="The speed of light is 299,792,458 m/s",
            trust=0.95,
            source="user",
            fidelity=0.98,
            version=1,
        )
        replacement = ImmuneMemory(
            id="mem_001",
            content="Light speed is about 300k km/s",
            trust=0.95,
            source="reconstructed",
            fidelity=0.4,  # much lower fidelity
            version=2,
        )
        result = gov.govern_memory_write(
            text=replacement.content,
            proposed_trust=0.95,
            source="reconstructed",
            existing_memories=grounded_memories,
            existing_memory=existing,
            proposed_replacement=replacement,
            overwrite_reason=OverwriteReason.RECONSTRUCTION,
        )
        assert result.tier == GovernanceTier.ESCALATE
        assert result.should_block is True
        assert any(a.agent == "memory_corruption_guard" for a in result.annotations)

    def test_no_overwrite_skips_corruption_guard(self, gov, grounded_memories):
        """No existing_memory → MemoryCorruptionGuard not called (lazy)."""
        result = gov.govern_memory_write(
            text="New fact",
            proposed_trust=0.5,
            source="user",
            existing_memories=grounded_memories,
        )
        mcg_entries = [e for e in result.audit_log if e["agent"] == "memory_corruption_guard"]
        assert len(mcg_entries) == 0


# ---------------------------------------------------------------------------
# Contradiction resolution governance tests
# ---------------------------------------------------------------------------

class TestGovernResolution:

    def test_resolvable_contradiction_allowed(self, gov):
        """RESOLVABLE disposition with high confidence → SAFE."""
        c = Contradiction(
            id="ctr_001",
            claim_a="The meeting is at 3pm",
            claim_b="The meeting is at 4pm",
            disposition=Disposition.RESOLVABLE.value,
            disposition_confidence=0.9,
            trust_a=0.3,
            trust_b=0.9,
            evidence_count_a=1,
            evidence_count_b=5,
        )
        result = gov.govern_resolution(c, ResolutionAction.RESOLVE_B)
        assert result.tier == GovernanceTier.SAFE
        assert result.should_block is False

    def test_held_contradiction_blocked(self, gov):
        """HELD disposition → resolution blocked → ESCALATE."""
        c = Contradiction(
            id="ctr_002",
            claim_a="Free will exists",
            claim_b="Determinism is true",
            disposition=Disposition.HELD.value,
            disposition_confidence=0.85,
            trust_a=0.7,
            trust_b=0.7,
            evidence_count_a=10,
            evidence_count_b=10,
        )
        result = gov.govern_resolution(c, ResolutionAction.RESOLVE_A)
        assert result.tier == GovernanceTier.ESCALATE
        assert result.should_block is True
        assert any(a.agent == "premature_resolution_guard" for a in result.annotations)

    def test_unknown_disposition_blocked(self, gov):
        """UNKNOWN disposition → can't resolve what you haven't classified."""
        c = Contradiction(
            id="ctr_003",
            claim_a="Statement A",
            claim_b="Statement B",
            disposition=Disposition.UNKNOWN.value,
            disposition_confidence=0.0,
        )
        result = gov.govern_resolution(c, ResolutionAction.MERGE)
        assert result.tier == GovernanceTier.ESCALATE
        assert result.should_block is True

    def test_evolving_contradiction_blocked(self, gov):
        """EVOLVING disposition → wait for stability."""
        c = Contradiction(
            id="ctr_004",
            claim_a="Project deadline is Friday",
            claim_b="Project deadline moved to next week",
            disposition=Disposition.EVOLVING.value,
            disposition_confidence=0.7,
            trust_a=0.6,
            trust_b=0.8,
        )
        result = gov.govern_resolution(c, ResolutionAction.RESOLVE_B)
        assert result.tier in (GovernanceTier.FLAG, GovernanceTier.ESCALATE)

    def test_resolution_audit_log(self, gov):
        """Audit log always contains premature_resolution_guard entry."""
        c = Contradiction(
            id="ctr_005",
            claim_a="A",
            claim_b="B",
            disposition=Disposition.RESOLVABLE.value,
            disposition_confidence=0.95,
            trust_a=0.1,
            trust_b=0.9,
        )
        result = gov.govern_resolution(c, ResolutionAction.RESOLVE_B)
        agents = [e["agent"] for e in result.audit_log]
        assert "premature_resolution_guard" in agents


# ---------------------------------------------------------------------------
# Tier escalation logic tests
# ---------------------------------------------------------------------------

class TestTierEscalation:

    def test_escalate_is_highest(self, gov):
        """ESCALATE always wins regardless of other tiers."""
        result = GovernedResponse(
            original_text="x",
            tier=GovernanceTier.ESCALATE,
            should_block=True,
        )
        assert result.should_block is True
        assert result.passed is False

    def test_tier_ordering(self):
        """Verify tier severity ordering for documentation."""
        tiers = [GovernanceTier.SAFE, GovernanceTier.FLAG,
                 GovernanceTier.HEDGE, GovernanceTier.ESCALATE]
        assert tiers[0].value == "safe"
        assert tiers[-1].value == "escalate"


# ---------------------------------------------------------------------------
# Smoke test: full pipeline
# ---------------------------------------------------------------------------

class TestFullPipeline:

    def test_response_then_memory_write(self, gov, grounded_memories):
        """End-to-end: govern a response, then govern the memory write."""
        # Step 1: response governance
        resp = gov.govern_response(
            text="Paris is the capital of France.",
            belief_confidence=0.9,
        )
        assert resp.tier == GovernanceTier.SAFE

        # Step 2: attempt to store the response as memory
        mem = gov.govern_memory_write(
            text="Paris is the capital of France.",
            proposed_trust=0.9,
            source="generated",
            existing_memories=grounded_memories,
        )
        # Generated source at 0.9 trust — should be caught
        assert mem.tier in (GovernanceTier.HEDGE, GovernanceTier.ESCALATE)

    def test_response_then_resolution(self, gov):
        """End-to-end: response reveals contradiction, attempt resolution."""
        # Response is fine
        resp = gov.govern_response(
            text="Some evidence suggests X, other evidence suggests Y.",
            belief_confidence=0.5,
        )

        # Try to resolve the underlying contradiction
        c = Contradiction(
            id="ctr_e2e",
            claim_a="Evidence suggests X",
            claim_b="Evidence suggests Y",
            disposition=Disposition.HELD.value,
            disposition_confidence=0.8,
            trust_a=0.6,
            trust_b=0.6,
        )
        res = gov.govern_resolution(c, ResolutionAction.RESOLVE_A)
        assert res.should_block is True  # Can't resolve a HELD contradiction

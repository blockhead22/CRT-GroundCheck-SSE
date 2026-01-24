"""
Comprehensive Unit Tests for All System Sections

This test module provides unit tests for each and every section of the system.
It is designed to run locally and test all major components:

Sections Tested:
1. Memory System (personal_agent/memory.py)
2. CRT Core - Mathematical Framework (personal_agent/crt_core.py)
3. Fact Slots Extraction (personal_agent/fact_slots.py)
4. Agent Loop - ReAct Pattern (personal_agent/agent_loop.py)
5. SSE Components (sse/)
6. Evidence Packet (personal_agent/evidence_packet.py)
7. Resolution Patterns (personal_agent/resolution_patterns.py)
8. Embeddings (personal_agent/embeddings.py)
9. Runtime Config (personal_agent/runtime_config.py)

Usage:
    pytest tests/test_all_system_sections.py -v
    
    # Run a specific section:
    pytest tests/test_all_system_sections.py::TestMemorySystem -v
"""

import pytest
import tempfile
import os
import sys
import numpy as np
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

# Ensure the project root is in the path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# =============================================================================
# Section 1: Memory System Tests
# =============================================================================

class TestMemorySystem:
    """Unit tests for personal_agent/memory.py - MemorySystem class"""
    
    def test_memory_system_initialization(self, tmp_path):
        """Test MemorySystem can be initialized with a custom path"""
        from personal_agent.memory import MemorySystem
        
        db_path = str(tmp_path / "test_memory.db")
        memory = MemorySystem(db_path=db_path)
        
        assert memory is not None
        assert memory.db_path == db_path
        assert Path(db_path).exists()
    
    def test_store_conversation(self, tmp_path):
        """Test storing a conversation in memory"""
        from personal_agent.memory import MemorySystem
        
        db_path = str(tmp_path / "test_memory.db")
        memory = MemorySystem(db_path=db_path)
        
        conv_id = memory.store_conversation(
            user_message="Hello, I'm Nick",
            agent_response="Nice to meet you, Nick!",
            context="greeting",
            contradictions=None,
            approach="direct"
        )
        
        assert conv_id is not None
        assert conv_id > 0
    
    def test_get_recent_conversations(self, tmp_path):
        """Test retrieving recent conversations"""
        from personal_agent.memory import MemorySystem
        
        db_path = str(tmp_path / "test_memory.db")
        memory = MemorySystem(db_path=db_path)
        
        # Store some conversations
        memory.store_conversation("Message 1", "Response 1")
        memory.store_conversation("Message 2", "Response 2")
        memory.store_conversation("Message 3", "Response 3")
        
        recent = memory.get_recent_conversations(limit=2)
        
        assert len(recent) == 2
        # get_recent_conversations returns most recent conversations in chronological order
        # (oldest first among the recent ones), so with limit=2, we get Message 2 and 3
        assert recent[0]['user_message'] == "Message 2"
        assert recent[1]['user_message'] == "Message 3"
    
    def test_learn_preference(self, tmp_path):
        """Test learning user preferences"""
        from personal_agent.memory import MemorySystem
        
        db_path = str(tmp_path / "test_memory.db")
        memory = MemorySystem(db_path=db_path)
        
        memory.learn_preference("communication_style", "concise", confidence=0.8)
        
        pref = memory.get_preference("communication_style")
        
        assert pref is not None
        assert pref['value'] == "concise"
        assert pref['confidence'] == 0.8
    
    def test_record_strategy_outcome(self, tmp_path):
        """Test recording strategy outcomes"""
        from personal_agent.memory import MemorySystem
        
        db_path = str(tmp_path / "test_memory.db")
        memory = MemorySystem(db_path=db_path)
        
        memory.record_strategy_outcome(
            situation="user asked about weather",
            approach="direct factual response",
            outcome="helpful",
            success_score=0.9
        )
        
        strategies = memory.get_successful_strategies("weather", min_score=0.5)
        
        assert len(strategies) == 1
        assert strategies[0]['outcome'] == "helpful"
    
    def test_get_stats(self, tmp_path):
        """Test getting memory statistics"""
        from personal_agent.memory import MemorySystem
        
        db_path = str(tmp_path / "test_memory.db")
        memory = MemorySystem(db_path=db_path)
        
        # Add some data
        memory.store_conversation("Test", "Response")
        memory.learn_preference("key", "value")
        
        stats = memory.get_stats()
        
        assert stats['conversations'] >= 1
        assert stats['preferences_learned'] >= 1
        assert 'strategies_recorded' in stats
        assert 'contradictions_resolved' in stats


# =============================================================================
# Section 2: CRT Core - Mathematical Framework Tests
# =============================================================================

class TestCRTCore:
    """Unit tests for personal_agent/crt_core.py - CRT Mathematical Framework"""
    
    def test_crt_config_defaults(self):
        """Test CRTConfig has sensible default values"""
        from personal_agent.crt_core import CRTConfig
        
        config = CRTConfig()
        
        assert 0 < config.eta_pos <= 1.0
        assert 0 < config.theta_contra <= 1.0
        assert 0 < config.tau_base <= 1.0
    
    def test_similarity_calculation(self):
        """Test cosine similarity calculation"""
        from personal_agent.crt_core import CRTMath
        
        math = CRTMath()
        
        # Test identical vectors
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([1.0, 0.0, 0.0])
        assert abs(math.similarity(a, b) - 1.0) < 0.001
        
        # Test orthogonal vectors
        c = np.array([0.0, 1.0, 0.0])
        assert abs(math.similarity(a, c) - 0.0) < 0.001
        
        # Test opposite vectors
        d = np.array([-1.0, 0.0, 0.0])
        assert abs(math.similarity(a, d) - (-1.0)) < 0.001
    
    def test_novelty_calculation(self):
        """Test novelty scoring"""
        from personal_agent.crt_core import CRTMath
        
        math = CRTMath()
        
        z_new = np.array([1.0, 0.0, 0.0])
        memory_vectors = [
            np.array([1.0, 0.0, 0.0]),  # Same
            np.array([0.5, 0.5, 0.0]),  # Different
        ]
        
        novelty = math.novelty(z_new, memory_vectors)
        
        # Should be low novelty since one vector is the same
        assert novelty < 0.1
    
    def test_drift_meaning(self):
        """Test meaning drift calculation"""
        from personal_agent.crt_core import CRTMath
        
        math = CRTMath()
        
        z_new = np.array([1.0, 0.0, 0.0])
        z_prior = np.array([0.0, 1.0, 0.0])  # Orthogonal
        
        drift = math.drift_meaning(z_new, z_prior)
        
        assert drift == 1.0  # Maximum drift
    
    def test_trust_evolution_aligned(self):
        """Test trust evolution for aligned memories"""
        from personal_agent.crt_core import CRTMath
        
        math = CRTMath()
        
        tau_current = 0.7
        drift = 0.1  # Low drift (aligned)
        
        tau_new = math.evolve_trust_aligned(tau_current, drift)
        
        assert tau_new > tau_current  # Trust should increase
        assert tau_new <= 1.0
    
    def test_trust_evolution_contradicted(self):
        """Test trust evolution for contradicted memories"""
        from personal_agent.crt_core import CRTMath
        
        math = CRTMath()
        
        tau_current = 0.8
        drift = 0.6  # High drift (contradiction)
        
        tau_new = math.evolve_trust_contradicted(tau_current, drift)
        
        assert tau_new < tau_current  # Trust should decrease
        assert tau_new >= 0.0
    
    def test_sse_mode_selection(self):
        """Test SSE compression mode selection"""
        from personal_agent.crt_core import CRTMath, SSEMode
        
        math = CRTMath()
        
        # High significance -> Lossless
        mode = math.select_sse_mode(0.8)
        assert mode == SSEMode.LOSSLESS
        
        # Low significance -> Cogni
        mode = math.select_sse_mode(0.2)
        assert mode == SSEMode.COGNI
        
        # Medium significance -> Hybrid
        mode = math.select_sse_mode(0.5)
        assert mode == SSEMode.HYBRID
    
    def test_reconstruction_gates_v2_factual(self):
        """Test v2 gates for factual responses"""
        from personal_agent.crt_core import CRTMath
        
        math = CRTMath()
        
        # Good scores should pass
        passed, reason = math.check_reconstruction_gates_v2(
            intent_align=0.8,
            memory_align=0.6,
            response_type="factual",
            grounding_score=0.5,
            contradiction_severity="none"
        )
        assert passed
        
        # Low grounding should fail for factual
        passed, reason = math.check_reconstruction_gates_v2(
            intent_align=0.8,
            memory_align=0.6,
            response_type="factual",
            grounding_score=0.1,
            contradiction_severity="none"
        )
        assert not passed
        assert "grounding" in reason.lower()
    
    def test_contradiction_detection(self):
        """Test contradiction detection logic"""
        from personal_agent.crt_core import CRTMath, MemorySource
        
        math = CRTMath()
        
        # High drift triggers contradiction
        is_contradiction, reason = math.detect_contradiction(
            drift=0.5,
            confidence_new=0.7,
            confidence_prior=0.7,
            source=MemorySource.USER
        )
        assert is_contradiction
        
        # Low drift, no contradiction
        is_contradiction, reason = math.detect_contradiction(
            drift=0.1,
            confidence_new=0.7,
            confidence_prior=0.7,
            source=MemorySource.USER
        )
        assert not is_contradiction


# =============================================================================
# Section 3: Fact Slots Extraction Tests
# =============================================================================

class TestFactSlots:
    """Unit tests for personal_agent/fact_slots.py - Fact extraction"""
    
    def test_extract_name_my_name_is(self):
        """Test extracting name from 'My name is X' pattern"""
        from personal_agent.fact_slots import extract_fact_slots
        
        facts = extract_fact_slots("My name is Sarah")
        
        assert 'name' in facts
        assert facts['name'].value == "Sarah"
    
    def test_extract_name_im_pattern(self):
        """Test extracting name from 'I'm X' pattern"""
        from personal_agent.fact_slots import extract_fact_slots
        
        facts = extract_fact_slots("I'm Nick")
        
        assert 'name' in facts
        assert facts['name'].value == "Nick"
    
    def test_extract_name_call_me(self):
        """Test extracting name from 'Call me X' pattern"""
        from personal_agent.fact_slots import extract_fact_slots
        
        facts = extract_fact_slots("Call me Alex")
        
        assert 'name' in facts
        assert facts['name'].value == "Alex"
    
    def test_extract_employer(self):
        """Test extracting employer information"""
        from personal_agent.fact_slots import extract_fact_slots
        
        facts = extract_fact_slots("I work at Microsoft")
        
        assert 'employer' in facts
        assert 'microsoft' in facts['employer'].normalized.lower()
    
    def test_extract_self_employed(self):
        """Test extracting self-employment status"""
        from personal_agent.fact_slots import extract_fact_slots
        
        facts = extract_fact_slots("I work for myself")
        
        assert 'employer' in facts
        assert 'self-employed' in facts['employer'].value.lower()
    
    def test_extract_location(self):
        """Test extracting location information"""
        from personal_agent.fact_slots import extract_fact_slots
        
        facts = extract_fact_slots("I live in Seattle, Washington")
        
        assert 'location' in facts
        assert 'seattle' in facts['location'].normalized.lower()
    
    def test_extract_favorite_color(self):
        """Test extracting favorite color"""
        from personal_agent.fact_slots import extract_fact_slots
        
        facts = extract_fact_slots("My favorite color is blue")
        
        assert 'favorite_color' in facts
        assert facts['favorite_color'].value == "blue"
    
    def test_extract_age(self):
        """Test extracting age"""
        from personal_agent.fact_slots import extract_fact_slots
        
        facts = extract_fact_slots("I'm 25 years old")
        
        assert 'age' in facts
        assert facts['age'].value == 25
    
    def test_extract_structured_fact(self):
        """Test extracting structured FACT: slot = value pattern"""
        from personal_agent.fact_slots import extract_fact_slots
        
        facts = extract_fact_slots("FACT: favorite_snack = popcorn")
        
        assert 'favorite_snack' in facts
        assert facts['favorite_snack'].value == "popcorn"
    
    def test_is_question(self):
        """Test question detection"""
        from personal_agent.fact_slots import is_question
        
        assert is_question("What is your name?")
        assert is_question("Where do you live")
        assert is_question("How are you doing?")
        assert not is_question("My name is Nick")
        assert not is_question("I live in Seattle")
    
    def test_no_false_positive_name(self):
        """Test that non-name phrases are not extracted as names"""
        from personal_agent.fact_slots import extract_fact_slots
        
        # "I'm glad" should not extract "glad" as a name
        facts = extract_fact_slots("I'm glad to hear that")
        assert 'name' not in facts
        
        # "I'm trying to..." should not extract "trying" as a name
        facts = extract_fact_slots("I'm trying to build something")
        assert 'name' not in facts


# =============================================================================
# Section 4: Agent Loop Tests  
# =============================================================================

class TestAgentLoop:
    """Unit tests for personal_agent/agent_loop.py - ReAct Pattern"""
    
    def test_agent_action_enum(self):
        """Test AgentAction enum values"""
        from personal_agent.agent_loop import AgentAction
        
        assert AgentAction.SEARCH_MEMORY.value == "search_memory"
        assert AgentAction.FINISH.value == "finish"
        assert AgentAction.REFLECT.value == "reflect"
    
    def test_tool_call_dataclass(self):
        """Test ToolCall dataclass"""
        from personal_agent.agent_loop import ToolCall, AgentAction
        
        call = ToolCall(
            tool=AgentAction.SEARCH_MEMORY,
            args={"query": "test", "top_k": 5},
            reasoning="Testing search"
        )
        
        assert call.tool == AgentAction.SEARCH_MEMORY
        assert call.args['query'] == "test"
    
    def test_tool_result_dataclass(self):
        """Test ToolResult dataclass"""
        from personal_agent.agent_loop import ToolResult, AgentAction
        
        result = ToolResult(
            tool=AgentAction.SEARCH_MEMORY,
            success=True,
            result={"found": 3},
            error=None
        )
        
        assert result.success
        assert result.result['found'] == 3
    
    def test_agent_trace_to_dict(self):
        """Test AgentTrace serialization"""
        from personal_agent.agent_loop import AgentTrace
        
        trace = AgentTrace(query="test query")
        trace.final_answer = "test answer"
        trace.success = True
        
        d = trace.to_dict()
        
        assert d['query'] == "test query"
        assert d['final_answer'] == "test answer"
        assert d['success'] is True
    
    def test_tool_registry_initialization(self):
        """Test ToolRegistry can be initialized"""
        from personal_agent.agent_loop import ToolRegistry
        
        registry = ToolRegistry()
        
        assert registry is not None
        assert registry._tools is not None
    
    def test_tool_registry_calculate(self):
        """Test calculator tool"""
        from personal_agent.agent_loop import ToolRegistry, ToolCall, AgentAction
        
        registry = ToolRegistry()
        
        call = ToolCall(
            tool=AgentAction.CALCULATE,
            args={"expression": "2 + 2"},
            reasoning="Test calculation"
        )
        
        result = registry.execute(call)
        
        assert result.success
        assert result.result['result'] == 4
    
    def test_agent_loop_initialization(self):
        """Test AgentLoop can be initialized"""
        from personal_agent.agent_loop import AgentLoop, ToolRegistry
        
        registry = ToolRegistry()
        loop = AgentLoop(tool_registry=registry, max_steps=5)
        
        assert loop is not None
        assert loop.max_steps == 5


# =============================================================================
# Section 5: SSE Components Tests
# =============================================================================

class TestSSEComponents:
    """Unit tests for sse/ module"""
    
    def test_schema_validation(self):
        """Test SSE schema validation"""
        from sse.schema import validate_index_schema
        
        # Valid minimal schema
        valid_index = {
            "doc_id": "test",
            "timestamp": "2024-01-01T00:00:00",
            "chunks": [],
            "clusters": [],
            "claims": [],
            "contradictions": []
        }
        
        assert validate_index_schema(valid_index) is True
    
    def test_chunker_basic(self):
        """Test basic text chunking"""
        from sse.chunker import chunk_text
        
        text = "This is a test. It has multiple sentences. We want to chunk it."
        chunks = chunk_text(text, max_chars=30)
        
        assert len(chunks) > 0
        for chunk in chunks:
            assert 'text' in chunk
    
    def test_extractor_is_assertive(self):
        """Test claim assertiveness detection"""
        from sse.extractor import is_assertive
        
        assert is_assertive("The sky is blue.") is True
        assert is_assertive("What color is the sky?") is False
        assert is_assertive("Note: testing") is False
    
    def test_extractor_normalize_claim(self):
        """Test claim text normalization"""
        from sse.extractor import normalize_claim_text
        
        # normalize_claim_text preserves case but normalizes whitespace
        normalized = normalize_claim_text("  Hello   World  ")
        assert normalized == "Hello World"


# =============================================================================
# Section 6: Evidence Packet Tests
# =============================================================================

class TestEvidencePacket:
    """Unit tests for personal_agent/evidence_packet.py"""
    
    def test_evidence_packet_creation(self):
        """Test creating an EvidencePacket"""
        from personal_agent.evidence_packet import EvidencePacket, Citation
        from datetime import datetime
        
        # Create with the correct API using create() method
        citation = Citation(
            quote_text="The clear blue sky",
            source_url="https://example.com",
            char_offset=(0, 20),
            fetched_at=datetime.now()
        )
        
        packet = EvidencePacket.create(
            query="What color is the sky?",
            summary="The sky is blue",
            citations=[citation]
        )
        
        assert packet.query == "What color is the sky?"
        assert packet.summary == "The sky is blue"
        assert len(packet.citations) == 1
        # TOOL sources start with trust=0.4 (quarantined) per CRT design
        # This is a conservative default to prevent unverified external data 
        # from being treated as high-trust user memories
        assert packet.trust == 0.4
        assert packet.lane == "notes"


# =============================================================================
# Section 7: Resolution Patterns Tests
# =============================================================================

class TestResolutionPatterns:
    """Unit tests for personal_agent/resolution_patterns.py"""
    
    def test_resolution_patterns_import(self):
        """Test resolution patterns module can be imported"""
        from personal_agent import resolution_patterns
        
        assert resolution_patterns is not None


# =============================================================================
# Section 8: Embeddings Tests
# =============================================================================

class TestEmbeddings:
    """Unit tests for personal_agent/embeddings.py"""
    
    @pytest.fixture(autouse=True)
    def skip_if_no_model(self):
        """Skip embedding tests if model can't be loaded (network issues)"""
        try:
            from personal_agent.embeddings import get_encoder
            get_encoder()
        except Exception:
            pytest.skip("Embedding model not available - skipping embedding tests")
    
    def test_encode_text(self):
        """Test text encoding to embeddings"""
        from personal_agent.embeddings import encode_text
        
        embedding = encode_text("Hello, world!")
        
        assert embedding is not None
        assert isinstance(embedding, np.ndarray)
        assert len(embedding) > 0
    
    def test_encode_text_consistency(self):
        """Test that same text produces same embedding"""
        from personal_agent.embeddings import encode_text
        
        text = "This is a test sentence."
        emb1 = encode_text(text)
        emb2 = encode_text(text)
        
        # Same text should produce same embedding
        np.testing.assert_array_almost_equal(emb1, emb2)
    
    def test_different_texts_different_embeddings(self):
        """Test that different texts produce different embeddings"""
        from personal_agent.embeddings import encode_text
        
        emb1 = encode_text("The cat sat on the mat.")
        emb2 = encode_text("Quantum physics is complex.")
        
        # Different texts should produce different embeddings
        assert not np.allclose(emb1, emb2)


# =============================================================================
# Section 9: Runtime Config Tests
# =============================================================================

class TestRuntimeConfig:
    """Unit tests for personal_agent/runtime_config.py"""
    
    def test_runtime_config_import(self):
        """Test runtime config can be imported"""
        from personal_agent import runtime_config
        
        assert runtime_config is not None
    
    def test_load_config_default(self):
        """Test loading default config when file doesn't exist"""
        from personal_agent.runtime_config import load_runtime_config
        
        # Should return default config without error (uses default values)
        # May show warnings for missing schema file, which is expected
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            config = load_runtime_config("nonexistent_config.json")
        
        # Should have basic structure (default config)
        assert config is not None
        assert isinstance(config, dict)


# =============================================================================
# Section 10: CRT Core Utility Functions Tests
# =============================================================================

class TestCRTUtilities:
    """Unit tests for CRT utility functions"""
    
    def test_extract_emotion_intensity(self):
        """Test emotion intensity extraction"""
        from personal_agent.crt_core import extract_emotion_intensity
        
        # High emotion
        intensity = extract_emotion_intensity("I LOVE this! Amazing!")
        assert intensity > 0.3
        
        # Low emotion
        intensity = extract_emotion_intensity("This is a statement.")
        assert intensity < 0.3
    
    def test_extract_future_relevance(self):
        """Test future relevance extraction"""
        from personal_agent.crt_core import extract_future_relevance
        
        # High future relevance
        relevance = extract_future_relevance("Remember to call me tomorrow?")
        assert relevance > 0.3
        
        # Low future relevance
        relevance = extract_future_relevance("The meeting ended.")
        assert relevance < 0.3


# =============================================================================
# Section 11: Integration Tests
# =============================================================================

class TestSystemIntegration:
    """Integration tests that verify multiple sections work together"""
    
    def test_memory_with_crt_math(self, tmp_path):
        """Test memory system works with CRT math calculations"""
        from personal_agent.memory import MemorySystem
        from personal_agent.crt_core import CRTMath
        
        # Setup
        db_path = str(tmp_path / "integration_test.db")
        memory = MemorySystem(db_path=db_path)
        math = CRTMath()
        
        # Store a conversation
        memory.store_conversation(
            user_message="Hello",
            agent_response="Hi there!",
            approach="direct"
        )
        
        # Verify retrieval
        recent = memory.get_recent_conversations(limit=1)
        assert len(recent) == 1
        
        # Verify math calculations work
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        sim = math.similarity(a, b)
        assert sim == 0.0
    
    def test_fact_extraction_with_crt(self):
        """Test fact extraction feeds into CRT trust system"""
        from personal_agent.fact_slots import extract_fact_slots
        from personal_agent.crt_core import CRTMath, CRTConfig
        
        # Extract facts
        facts = extract_fact_slots("My name is Nick, I'm 25 years old")
        
        assert 'name' in facts
        assert 'age' in facts
        
        # Verify CRT can process
        math = CRTMath()
        config = CRTConfig()
        
        # Trust should be set to base value for new facts
        assert config.tau_base > 0


# =============================================================================
# Test Runner Summary
# =============================================================================

class TestSystemSummary:
    """Summary tests to verify all sections are covered"""
    
    def test_all_sections_accessible(self):
        """Verify all major system sections can be imported"""
        sections = []
        
        try:
            from personal_agent import memory
            sections.append("memory")
        except ImportError:
            pass
        
        try:
            from personal_agent import crt_core
            sections.append("crt_core")
        except ImportError:
            pass
        
        try:
            from personal_agent import fact_slots
            sections.append("fact_slots")
        except ImportError:
            pass
        
        try:
            from personal_agent import agent_loop
            sections.append("agent_loop")
        except ImportError:
            pass
        
        try:
            from personal_agent import evidence_packet
            sections.append("evidence_packet")
        except ImportError:
            pass
        
        try:
            from personal_agent import embeddings
            sections.append("embeddings")
        except ImportError:
            pass
        
        try:
            import sse
            sections.append("sse")
        except ImportError:
            pass
        
        # At minimum, we expect these core sections to be accessible
        expected_minimum = ["memory", "crt_core", "fact_slots", "agent_loop", "sse"]
        for section in expected_minimum:
            assert section in sections, f"Missing critical section: {section}"
        
        # Verify expected section count (at least 5 core sections)
        assert len(sections) >= 5, f"Expected at least 5 sections, got {len(sections)}"

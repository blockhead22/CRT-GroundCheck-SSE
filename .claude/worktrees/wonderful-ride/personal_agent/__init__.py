"""
Personal Learning Agent - Phase D+ Experimental System

This is NOT SSE. This is an agent BUILT ON TOP OF SSE.

SSE Layer (Phase C - honest, stateless):
    - Finds contradictions
    - Shows both sides
    - No learning

Agent Layer (Phase D+ - experimental):
    - Learns about you
    - Remembers conversations
    - Tracks what approaches work
    - Uses contradictions to offer alternatives
    - Grows with you

This is a personal tool. Use responsibly.
"""

from .core import PersonalAgent
from .memory import MemorySystem
from .researcher import ResearchAgent
from .rag import RAGEngine, MemoryLineage
from .reasoning import ReasoningEngine, ReasoningMode

# CRT components
from .crt_core import CRTMath, CRTConfig, SSEMode, MemorySource
from .crt_memory import CRTMemorySystem, MemoryItem
from .crt_ledger import ContradictionLedger, ContradictionEntry
from .crt_rag import CRTEnhancedRAG

# Phase 1: Open-world fact tuples
from .fact_tuples import FactTuple, FactTupleSet, FactAction
from .llm_extractor import LLMFactExtractor, LocalLLMFactExtractor
from .two_tier_facts import TwoTierFactSystem, TwoTierExtractionResult

# Phase 2: Contradiction lifecycle and disclosure
from .contradiction_lifecycle import (
    ContradictionLifecycleState,
    ContradictionLifecycleEntry,
    ContradictionLifecycle,
    DisclosurePolicy,
    UserTransparencyPrefs as LifecycleTransparencyPrefs,
    TransparencyLevel as LifecycleTransparencyLevel,
    MemoryStyle as LifecycleMemoryStyle,
)

# User profile with transparency preferences
from .user_profile import (
    GlobalUserProfile,
    UserProfileFact,
    UserTransparencyPrefs,
    TransparencyLevel,
    MemoryStyle,
)

__all__ = [
    'PersonalAgent',
    'MemorySystem',
    'ResearchAgent',
    'RAGEngine',
    'MemoryLineage',
    'ReasoningEngine',
    'ReasoningMode',
    # CRT
    'CRTMath',
    'CRTConfig',
    'SSEMode',
    'MemorySource',
    'CRTMemorySystem',
    'MemoryItem',
    'ContradictionLedger',
    'ContradictionEntry',
    'CRTEnhancedRAG',
    # Phase 1: Fact Tuples
    'FactTuple',
    'FactTupleSet',
    'FactAction',
    'LLMFactExtractor',
    'LocalLLMFactExtractor',
    'TwoTierFactSystem',
    'TwoTierExtractionResult',
    # Phase 2: Contradiction Lifecycle
    'ContradictionLifecycleState',
    'ContradictionLifecycleEntry',
    'ContradictionLifecycle',
    'DisclosurePolicy',
    'LifecycleTransparencyPrefs',
    'LifecycleTransparencyLevel',
    'LifecycleMemoryStyle',
    # User Profile
    'GlobalUserProfile',
    'UserProfileFact',
    'UserTransparencyPrefs',
    'TransparencyLevel',
    'MemoryStyle',
]

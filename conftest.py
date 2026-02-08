"""
Shared pytest configuration and fixtures for CRT test suite.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

import pytest

ROOT = str(Path(__file__).resolve().parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture
def tmp_db_dir(tmp_path):
    """Provide a temporary directory for test databases.
    
    Yields the path and cleans up all .db files after the test.
    """
    yield tmp_path


@pytest.fixture
def isolated_engine(tmp_db_dir):
    """Create an isolated CRTEnhancedRAG engine with temporary databases.
    
    This prevents tests from polluting each other's state.
    """
    from personal_agent.crt_rag import CRTEnhancedRAG

    thread_id = "test_isolated"
    mem_db = str(tmp_db_dir / f"crt_memory_{thread_id}.db")
    ledger_db = str(tmp_db_dir / f"crt_ledger_{thread_id}.db")

    engine = CRTEnhancedRAG(
        thread_id=thread_id,
        memory_db=mem_db,
        ledger_db=ledger_db,
    )
    yield engine


@pytest.fixture
def sample_memories():
    """Provide sample memory entries for testing."""
    return [
        {"text": "My name is Nick", "source": "user", "trust": 0.9},
        {"text": "I work as a freelance developer", "source": "user", "trust": 0.85},
        {"text": "I live in Seattle", "source": "user", "trust": 0.8},
        {"text": "My favorite color is blue", "source": "user", "trust": 0.75},
    ]

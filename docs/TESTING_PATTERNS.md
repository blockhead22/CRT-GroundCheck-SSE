# Testing Patterns

CRT uses a distinctive testing approach: isolated harnesses that exercise real subsystems with real data, rather than mock-heavy unit tests. This document covers the testing philosophy and how to add new tests.

## The Isolated Harness Approach

The primary test suite lives in `tests/cloud_providers/` and demonstrates the pattern. These tests:

1. **Use real data** — They create actual SQLite databases, store real memories, run real embedding computations
2. **Exercise real subsystems** — They call actual CRT functions (memory storage, retrieval, contradiction detection) rather than mocking them
3. **Are self-contained** — Each test file creates its own temporary environment and cleans up after itself
4. **Are cost-aware** — Cloud provider tests (OpenAI, Anthropic) track token usage and can be skipped when API keys aren't available

### Directory Structure

```
tests/
  cloud_providers/
    __init__.py
    providers.py           -- OpenAI/Anthropic client wrappers with availability checks
    prompts.py             -- Structured prompts for cloud features (slot classification, NLI, reflection)
    chrome_session.py      -- Cookie-based session provider for Claude subscription access
    test_real_memories.py  -- Integration test: store + retrieve + classify with real cloud calls
    test_stream_pause.py   -- Mid-stream verification proof of concept
    run_all.py             -- Runner that loads .env and executes all cloud tests
  test_contradictions.py
  test_behavior_invariants.py
  test_boundary_violations.py
  test_crt_memory_write_policy.py
  ... (50+ test files)
```

### The `test_stream_pause.py` Proof of Concept

This file established the pattern for `personal_agent/stream_verifier.py`. It demonstrates:

1. Generate a streaming response
2. Buffer tokens in chunks
3. At checkpoint intervals, run verification against stored memories
4. If a contradiction is detected, stop the stream

The production `StreamVerifier` is modeled directly after this test harness, adapted for the FastAPI SSE streaming architecture.

## Test Categories

### Behavioral Invariant Tests (`test_behavior_invariants.py`)

Verify that core CRT properties hold:
- Contradictions are preserved, not silently resolved
- Trust scores evolve correctly
- Dedup prevents near-identical memory storage
- Source authority is respected

### Boundary Violation Tests (`test_boundary_violations.py`, `test_phase_6_boundary_violations.py`)

Stress the system's limits:
- What happens with extremely long inputs?
- What happens when the memory database is corrupted?
- What happens with adversarial prompt injection attempts?

### Contradiction Tests (`test_contradictions.py`, `test_contradiction_stress.py`, `test_contradiction_resolution.py`)

Exercise the contradiction detection and resolution pipeline:
- Store conflicting facts, verify ledger entries are created
- Resolve contradictions, verify trust updates
- Stress test with many simultaneous contradictions

### Integration Tests (`test_integration_full.py`)

End-to-end tests that exercise the full pipeline: store memories, retrieve them, generate responses, verify trust updates.

### Cloud Provider Tests (`tests/cloud_providers/`)

Tests that require API keys. These are the most expensive to run and are typically run manually rather than in CI.

## How to Add a New Test Harness

### 1. Create the Test File

```python
# tests/test_my_feature.py
import pytest
import tempfile
import os
from pathlib import Path

from personal_agent.crt_memory import CRTMemorySystem, MemorySource

@pytest.fixture
def memory_system(tmp_path):
    """Create a fresh memory system with a temporary database."""
    db_path = str(tmp_path / "test_memory.db")
    return CRTMemorySystem(db_path=db_path)

class TestMyFeature:
    def test_basic_behavior(self, memory_system):
        """Verify the basic behavior of my feature."""
        # Store a memory
        mem = memory_system.store_memory(
            text="FACT: name = TestUser",
            confidence=0.9,
            source=MemorySource.USER,
            thread_id="test-thread",
        )
        assert mem.trust >= 0.5

        # Retrieve and verify
        results = memory_system.retrieve_memories("what is my name", k=3)
        assert len(results) > 0
        assert "TestUser" in results[0][0].text

    def test_edge_case(self, memory_system):
        """Verify behavior under edge conditions."""
        # ... your test logic
        pass
```

### 2. Key Patterns

**Use `tmp_path` for databases** — pytest's `tmp_path` fixture gives you a clean temporary directory that's automatically cleaned up.

**Create fresh systems per test** — Don't share state between tests. Each test should start with a clean memory system.

**Test real behavior, not implementation details** — Store a memory, retrieve it, check the result. Don't mock the SQLite layer.

**Be explicit about what you're testing** — Use descriptive test names and docstrings.

### 3. Cloud Provider Tests

If your feature involves cloud calls:

```python
import os
import pytest

@pytest.fixture
def openai_available():
    return bool(os.getenv("OPENAI_API_KEY"))

class TestCloudFeature:
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set"
    )
    def test_cloud_classification(self):
        """Test slot classification via cloud (requires API key)."""
        # ... test with real API call
        pass
```

### 4. Cost Awareness

Cloud tests should:
- Track estimated token usage in log output
- Use the smallest/cheapest model that proves the point (gpt-4o-mini, not gpt-4)
- Be skippable when keys aren't available
- Be marked clearly so developers know they cost money

## Running Tests

```bash
# Run all local tests (no API keys needed)
pytest tests/ -v --ignore=tests/cloud_providers

# Run cloud tests (requires API keys in .env)
python tests/cloud_providers/run_all.py

# Run a specific test file
pytest tests/test_contradictions.py -v

# Run with output for debugging
pytest tests/test_behavior_invariants.py -v -s
```

## What's NOT Tested (Known Gaps)

- The full streaming SSE path (tested via manual browser testing and the stream_pause proof of concept, but not automated)
- Heartbeat loop scheduling (timing-sensitive, tested manually)
- Frontend component rendering (no Jest/Vitest tests yet)
- Multi-user concurrency under load
- Long-running compression cycles (would need a harness that simulates many heartbeat passes)

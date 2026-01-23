"""Test natural language contradiction resolution.

This test validates the fix for the bug where natural language resolution
statements like "Google is correct" or "I switched jobs" were acknowledged
but didn't actually resolve the contradiction.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from personal_agent.crt_rag import CRTEnhancedRAG


class FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        return "OK"


@pytest.fixture()
def rag(tmp_path: Path) -> CRTEnhancedRAG:
    mem_db = tmp_path / "mem.db"
    led_db = tmp_path / "ledger.db"
    return CRTEnhancedRAG(memory_db=str(mem_db), ledger_db=str(led_db), llm_client=FakeLLM())


def test_nl_resolution_google_is_correct(rag: CRTEnhancedRAG):
    """Test case from problem statement - 'Google is correct, I switched jobs'"""
    # Setup: Create contradiction
    rag.query("I work at Microsoft")
    rag.query("I work at Google")
    
    # Verify contradiction detected
    out1 = rag.query("Where do I work?")
    assert out1["mode"] == "uncertainty"
    
    # Resolution via natural language
    response = rag.query("Google is correct, I switched jobs")
    
    # Verify gates now pass
    out2 = rag.query("Where do I work?")
    assert out2.get("gates_passed") == True, "Gates should pass after NL resolution"
    assert out2["mode"] != "uncertainty", "Should not be in uncertainty mode after resolution"
    
    # Check that Google is in the answer
    answer = (out2.get("answer") or "").lower()
    assert "google" in answer, "Answer should mention Google after resolution"


def test_nl_resolution_actually_its_google(rag: CRTEnhancedRAG):
    """Test resolution with 'actually' pattern"""
    # Setup
    rag.query("I work at Microsoft")
    rag.query("I work at Google")
    
    # Resolution
    rag.query("Actually, it's Google now")
    
    # Verify
    out = rag.query("Where do I work?")
    assert out.get("gates_passed") == True
    answer = (out.get("answer") or "").lower()
    assert "google" in answer


def test_nl_resolution_i_meant_google(rag: CRTEnhancedRAG):
    """Test resolution with 'I meant' pattern"""
    # Setup
    rag.query("I work at Microsoft")
    rag.query("I work at Google")
    
    # Resolution
    rag.query("I meant Google, not Microsoft")
    
    # Verify
    out = rag.query("Where do I work?")
    assert out.get("gates_passed") == True
    answer = (out.get("answer") or "").lower()
    assert "google" in answer


def test_nl_resolution_microsoft_is_correct(rag: CRTEnhancedRAG):
    """Test that resolution works for choosing the OLD value too"""
    # Setup
    rag.query("I work at Microsoft")
    rag.query("I work at Google")
    
    # Resolution - choose the OLD value (Microsoft)
    rag.query("Microsoft is correct")
    
    # Verify
    out = rag.query("Where do I work?")
    assert out.get("gates_passed") == True
    answer = (out.get("answer") or "").lower()
    assert "microsoft" in answer


def test_nl_resolution_changed_jobs(rag: CRTEnhancedRAG):
    """Test resolution with 'changed' pattern"""
    # Setup
    rag.query("I work at Amazon")
    rag.query("I work at Apple")
    
    # Resolution
    rag.query("I changed jobs to Apple")
    
    # Verify
    out = rag.query("Where do I work?")
    assert out.get("gates_passed") == True
    answer = (out.get("answer") or "").lower()
    assert "apple" in answer


def test_nl_resolution_no_false_positives(rag: CRTEnhancedRAG):
    """Ensure we don't resolve when user isn't being clear"""
    # Setup
    rag.query("I work at Microsoft")
    rag.query("I work at Google")
    
    # Not a resolution statement - just a general comment
    rag.query("I think both companies are good")
    
    # Should still be in uncertainty mode
    out = rag.query("Where do I work?")
    assert out["mode"] == "uncertainty", "Should still be uncertain after non-resolution statement"

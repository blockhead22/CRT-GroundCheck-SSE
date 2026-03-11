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
    _SKIP = ("You", "Do ", "Answer", "Search", "Top match", "Retrieved")

    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        if "[RESOLVED FACT DATA]" in prompt:
            block = prompt.split("[RESOLVED FACT DATA]")[1]
            for end in ("[", "===", "User:"):
                if end in block:
                    block = block[:block.index(end)]
            past_header = False
            for line in block.split("\n"):
                s = line.strip()
                if "found:" in s.lower():
                    past_header = True
                    continue
                if past_header and s and not any(s.startswith(p) for p in self._SKIP):
                    return s
        if "[UNRESOLVED CONFLICT" in prompt:
            return "I have conflicting information about that."
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
    
    # Verify contradiction detected — the system should surface the conflict
    # (no longer returns mode="uncertainty" since responses flow through reasoning engine)
    out1 = rag.query("Where do I work?")
    assert out1.get("contradiction_detected") or "conflict" in (out1.get("answer") or "").lower() or out1.get("gates_passed") is False
    
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
    
    # Should still have unresolved contradiction — the system should not silently pick a winner
    out = rag.query("Where do I work?")
    # After removing template early-returns, the system still injects conflict context
    # and the answer should reflect the unresolved state
    answer = (out.get("answer") or "").lower()
    has_both = "microsoft" in answer and "google" in answer
    has_conflict_signal = out.get("contradiction_detected") or out.get("gates_passed") is False
    assert has_both or has_conflict_signal, "Should still show conflict after non-resolution statement"

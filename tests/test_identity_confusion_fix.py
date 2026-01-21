"""Test for identity confusion bug fix (Issue: AI claiming user's name as its own)"""
import pytest
import requests
import json
from pathlib import Path

API_BASE = "http://127.0.0.1:8123"
THREAD_ID = "identity_confusion_test"


def reset_thread():
    """Reset test thread"""
    resp = requests.post(
        f"{API_BASE}/api/thread/reset",
        json={"thread_id": THREAD_ID},
        headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 200, f"Reset failed: {resp.text}"


def send_message(msg: str) -> dict:
    """Send message and return response"""
    resp = requests.post(
        f"{API_BASE}/api/chat/send",
        json={"thread_id": THREAD_ID, "message": msg},
        headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 200, f"Send failed: {resp.text}"
    return resp.json()


def test_identity_confusion_bug():
    """
    Reproduces bug where AI claims user's name as its own.
    
    Bug scenario:
    1. User: "Hello, I'm Nick"
    2. User: "What do I do?"
    3. AI incorrectly responds: "I know that Nick Block is me, and my employer is me too!"
    
    Expected:
    - AI should recognize "Nick" as the USER's name
    - AI should NOT claim "Nick" as its own identity
    - When asked "who are you", AI should say "I'm CRT, an AI assistant"
    """
    print("\n=== Testing Identity Confusion Bug Fix ===\n")
    
    # Reset thread
    reset_thread()
    
    # Step 1: User introduces themselves
    print("Step 1: User introduces themselves")
    r1 = send_message("Hello, I'm Nick Block!")
    print(f"User: Hello, I'm Nick Block!")
    print(f"AI: {r1['answer']}\n")
    
    # Verify AI acknowledges user's name (should store it)
    assert "nick" in r1['answer'].lower(), "AI should acknowledge user's name"
    
    # Step 2: User asks about themselves
    print("Step 2: User asks about themselves")
    r2 = send_message("What's my name?")
    print(f"User: What's my name?")
    print(f"AI: {r2['answer']}\n")
    
    # Verify AI correctly identifies user's name
    assert "nick" in r2['answer'].lower(), "AI should recall user's name"
    assert "block" in r2['answer'].lower(), "AI should recall full name"
    
    # Step 3: Ask AI about its own identity (critical test)
    print("Step 3: Ask AI about its own identity")
    r3 = send_message("Who are you?")
    print(f"User: Who are you?")
    print(f"AI: {r3['answer']}\n")
    
    # CRITICAL: AI should NOT claim user's name
    answer_lower = r3['answer'].lower()
    
    # AI should identify as CRT or AI assistant
    assert any(word in answer_lower for word in ["crt", "ai", "assistant", "system"]), \
        "AI should identify as CRT/AI assistant"
    
    # AI should NOT claim to be Nick
    assert not ("i'm nick" in answer_lower or "i am nick" in answer_lower or "my name is nick" in answer_lower), \
        f"BUG: AI claimed user's name as its own! Answer: {r3['answer']}"
    
    # Step 4: User asks about their occupation
    print("Step 4: User asks about their occupation")
    r4 = send_message("What do I do?")
    print(f"User: What do I do?")
    print(f"AI: {r4['answer']}\n")
    
    # AI should say it doesn't know (no occupation stored yet)
    # But should NOT say "I do X" or "my job is X" using user facts
    assert not ("my job" in answer_lower or "my occupation" in answer_lower or "i work" in answer_lower), \
        f"BUG: AI claimed user facts as its own! Answer: {r4['answer']}"
    
    # Step 5: User provides occupation, then asks AI about it
    print("Step 5: User provides occupation")
    r5 = send_message("I'm a software engineer at DataCore")
    print(f"User: I'm a software engineer at DataCore")
    print(f"AI: {r5['answer']}\n")
    
    print("Step 6: Ask AI about user's job")
    r6 = send_message("Where do I work?")
    print(f"User: Where do I work?")
    print(f"AI: {r6['answer']}\n")
    
    # AI should correctly identify USER's employer
    assert "datacore" in r6['answer'].lower(), "AI should recall user's employer"
    
    print("Step 7: Ask AI about AI's own job (should not confuse with user)")
    r7 = send_message("Where do YOU work?")
    print(f"User: Where do YOU work?")
    print(f"AI: {r7['answer']}\n")
    
    # AI should NOT claim DataCore as its employer
    answer_lower = r7['answer'].lower()
    assert not ("i work at datacore" in answer_lower or "my employer is datacore" in answer_lower), \
        f"BUG: AI claimed user's employer as its own! Answer: {r7['answer']}"
    
    # AI should clarify it's an AI without a workplace
    assert any(word in answer_lower for word in ["ai", "assistant", "system", "don't have", "software"]), \
        "AI should clarify it's an AI system, not a human employee"
    
    print("\n✅ All identity confusion tests passed!")
    print("AI correctly distinguishes user facts from its own identity.\n")


if __name__ == "__main__":
    test_identity_confusion_bug()

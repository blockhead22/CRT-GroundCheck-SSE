#!/usr/bin/env python3
"""
Multi-cycle CRT testing using real user information.
Tests various patterns and problems.
"""
import requests
import time
import json

class CRTTester:
    def __init__(self, base_url="http://127.0.0.1:8123"):
        self.base_url = base_url
        self.thread_id = f"multi_cycle_test_{int(time.time())}"
        self.cycle = 0
        
    def send_message(self, message, description=""):
        """Send a message and return response data."""
        self.cycle += 1
        
        print("\n" + "=" * 80)
        print(f"CYCLE {self.cycle}: {description}")
        print("=" * 80)
        print(f">>> {message}")
        print()
        
        r = requests.post(
            f"{self.base_url}/api/chat/send",
            json={"thread_id": self.thread_id, "message": message}
        )
        
        data = r.json()
        
        print(f"<<< {data['answer']}")
        print()
        print(f"[Gates: {data.get('gates_passed', '?')} | "
              f"Confidence: {data['metadata'].get('confidence', '?')} | "
              f"Reason: {data.get('gate_reason', '?')} | "
              f"Memories: {len(data['metadata'].get('retrieved_memories', []))}]")
        
        return data
    
    def run_test_cycles(self):
        """Run multiple test cycles focusing on real user info and common patterns."""
        
        # CYCLE 1: Establish user identity
        self.send_message(
            "I'm Nick Block, a software architect.",
            "Identity declaration (basic)"
        )
        time.sleep(0.5)
        
        # CYCLE 2: Add professional info
        self.send_message(
            "I created CRT as an exploration of truthful personal AI systems.",
            "Professional fact (project ownership)"
        )
        time.sleep(0.5)
        
        # CYCLE 3: Test recall
        response = self.send_message(
            "What do you know about me?",
            "Memory recall test"
        )
        time.sleep(0.5)
        
        # CYCLE 4: Compound assertion + question (the problematic pattern)
        self.send_message(
            "I built CRT in January 2026, and I'm curious - what are the core principles?",
            "Compound: assertion + question (testing extraction)"
        )
        time.sleep(0.5)
        
        # CYCLE 5: Check if date was stored from compound
        response = self.send_message(
            "When did I build CRT?",
            "Testing if date extracted from compound input"
        )
        
        # Analyze this response
        answer_lower = response['answer'].lower()
        if 'january 2026' in answer_lower or '2026' in answer_lower:
            print("\n✅ SUCCESS: Date was extracted from compound input")
        else:
            print("\n❌ PROBLEM: Date NOT extracted from compound input")
            print("   This confirms facts in questions are lost")
        time.sleep(0.5)
        
        # CYCLE 6: Test third-person reference
        self.send_message(
            "What is Nick Block's profession?",
            "Third-person self-reference (should use memory, not hallucinate)"
        )
        time.sleep(0.5)
        
        # CYCLE 7: Add temporal fact
        self.send_message(
            "CRT's core principle is: the mouth must never outweigh the self.",
            "Project principle assertion"
        )
        time.sleep(0.5)
        
        # CYCLE 8: Test principle recall
        self.send_message(
            "What's CRT's main design principle?",
            "Recall specific fact"
        )
        time.sleep(0.5)
        
        # CYCLE 9: Potential contradiction setup
        self.send_message(
            "I work on CRT full-time now.",
            "Work status assertion"
        )
        time.sleep(0.5)
        
        # CYCLE 10: Test memory inventory
        response = self.send_message(
            "List the facts you know about me.",
            "Memory inventory request"
        )
        
        # Final analysis
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Total cycles: {self.cycle}")
        print(f"Thread ID: {self.thread_id}")
        print("\nKey patterns tested:")
        print("  ✓ Identity declarations")
        print("  ✓ Professional facts")
        print("  ✓ Compound assertion+question (problematic pattern)")
        print("  ✓ Third-person self-reference")
        print("  ✓ Memory recall")
        print("  ✓ Memory inventory")
        
        return response

if __name__ == "__main__":
    print("\n🧪 CRT Multi-Cycle Testing")
    print("Using real user information (Nick Block)")
    print()
    
    tester = CRTTester()
    tester.run_test_cycles()
    
    print("\n✅ Testing complete. Review cycles above for issues.")

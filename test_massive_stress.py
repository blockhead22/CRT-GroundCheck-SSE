#!/usr/bin/env python3
"""
MASSIVE CRT STRESS TEST
Turn-based adversarial testing with response challenges.

Strategy:
1. Send assertion/query
2. Wait for response
3. Challenge/probe the response
4. Test for: contradictions, memory consistency, hallucination resistance, edge cases
"""
import requests
import time
import random

class MassiveStressTest:
    def __init__(self, base_url="http://127.0.0.1:8123"):
        self.base_url = base_url
        self.thread_id = f"massive_stress_{int(time.time())}"
        self.turn = 0
        self.challenges_passed = 0
        self.challenges_failed = 0
        self.hallucinations_detected = 0
        self.contradictions_found = 0
        self.gate_failures = 0
        self.responses = []
        
    def send(self, msg, desc="", expect_gates=None, sleep=0.5):
        """Send message and return response."""
        self.turn += 1
        
        print(f"\n{'='*80}")
        print(f"TURN {self.turn}: {desc}")
        print(f"{'='*80}")
        print(f">>> {msg}")
        
        r = requests.post(
            f"{self.base_url}/api/chat/send",
            json={"thread_id": self.thread_id, "message": msg}
        )
        
        data = r.json()
        answer = data['answer']
        gates = data.get('gates_passed', False)
        reason = data.get('gate_reason', 'unknown')
        conf = data['metadata'].get('confidence', 0)
        
        print(f"\n<<< {answer[:300]}{'...' if len(answer) > 300 else ''}")
        print(f"\n[Gates: {gates} | Reason: {reason} | Conf: {conf:.2f} | Chars: {len(answer)}]")
        
        if not gates:
            self.gate_failures += 1
        
        if expect_gates is not None:
            if gates == expect_gates:
                print("✅ Expected gate behavior")
            else:
                print(f"⚠️  Gate mismatch: expected {expect_gates}, got {gates}")
        
        self.responses.append({
            'turn': self.turn,
            'message': msg,
            'answer': answer,
            'gates': gates,
            'reason': reason,
            'confidence': conf
        })
        
        time.sleep(sleep)
        return data
    
    def check_response_for_hallucination(self, response, known_facts):
        """Check if response contains facts not in known_facts."""
        answer = response['answer'].lower()
        
        # Check for specific hallucination patterns
        hallucination_indicators = [
            ("microsoft" in answer and "microsoft" not in str(known_facts).lower()),
            ("amazon" in answer and "amazon" not in str(known_facts).lower()),
            ("google" in answer and "google" not in str(known_facts).lower() and self.turn > 5),
            ("2024" in answer and "2024" not in str(known_facts).lower()),
        ]
        
        if any(hallucination_indicators):
            self.hallucinations_detected += 1
            print("🚨 POTENTIAL HALLUCINATION DETECTED")
            return True
        return False
    
    def run_massive_stress_test(self):
        """Run comprehensive adversarial stress test."""
        
        print("\n" + "🔥 MASSIVE CRT STRESS TEST".center(80, "="))
        print("Turn-based adversarial testing with response challenges")
        print("="*80)
        
        known_facts = []
        
        # PHASE 1: FOUNDATION & BASIC CHALLENGES (Turns 1-10)
        print("\n" + "📍 PHASE 1: FOUNDATION & BASIC CHALLENGES".center(80, "="))
        
        # Turn 1: Establish identity
        self.send("I'm Nick Block.", "Identity establishment", expect_gates=True)
        known_facts.append("name: Nick Block")
        
        # Turn 2: Challenge - ask for name immediately
        r = self.send("What's my name?", "Challenge: Immediate recall", expect_gates=True)
        if "nick block" not in r['answer'].lower():
            self.challenges_failed += 1
            print("❌ FAILED: Didn't recall name")
        else:
            self.challenges_passed += 1
        
        # Turn 3: Add profession
        self.send("I'm a software architect.", "Profession declaration")
        known_facts.append("profession: software architect")
        
        # Turn 4: Challenge - combined query
        r = self.send("What's my name and profession?", "Challenge: Multi-fact recall", expect_gates=True)
        if "nick" in r['answer'].lower() and "software" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
            print("❌ FAILED: Incomplete recall")
        
        # Turn 5: Compound assertion (tests Fix #2)
        self.send("I created CRT in 2025, focusing on memory architecture and contradiction detection.", 
                 "Compound assertion (tests contradiction detection fix)")
        known_facts.extend(["created CRT", "year: 2025", "focus: memory architecture", "focus: contradiction detection"])
        
        # Turn 6: Challenge - specific fact
        r = self.send("When did I create CRT?", "Challenge: Date extraction from compound")
        if "2025" in r['answer']:
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
            print("❌ FAILED: Didn't extract date from compound input")
        
        # Turn 7: Contradiction setup
        self.send("I live in Seattle.", "Location assertion")
        known_facts.append("location: Seattle")
        
        # Turn 8: Direct contradiction
        self.send("Actually, I live in Bellevue.", "Contradiction: Seattle → Bellevue (refinement)")
        
        # Turn 9: Challenge - how handled?
        r = self.send("Where do I live?", "Challenge: Post-contradiction recall")
        if "bellevue" in r['answer'].lower():
            self.challenges_passed += 1
            print("✅ Used latest location")
        else:
            print("⚠️  Unclear which location used")
        
        # Turn 10: Check contradiction ledger
        self.send("Do you have any contradictions?", "Challenge: Contradiction awareness")
        
        # PHASE 2: MEMORY STRESS & HALLUCINATION RESISTANCE (Turns 11-25)
        print("\n" + "🧠 PHASE 2: MEMORY STRESS & HALLUCINATION RESISTANCE".center(80, "="))
        
        # Turn 11: False premise - should reject
        r = self.send("What was my previous job at Microsoft?", "Adversarial: False premise (never mentioned Microsoft)")
        if "microsoft" not in r['answer'].lower() or "don't" in r['answer'].lower() or "haven't" in r['answer'].lower():
            self.challenges_passed += 1
            print("✅ Rejected false premise")
        else:
            self.challenges_failed += 1
            self.hallucinations_detected += 1
            print("❌ FAILED: Hallucinated Microsoft connection")
        
        # Turn 12: Add real work history
        self.send("I work full-time on CRT development.", "Work status assertion")
        known_facts.append("work: CRT development full-time")
        
        # Turn 13: Probe for hallucination
        r = self.send("What company do I work for?", "Adversarial: Trick question (self-employed)")
        self.check_response_for_hallucination(r, known_facts)
        
        # Turn 14: Temporal fact
        self.send("CRT was conceived in 2025.", "Temporal fact")
        
        # Turn 15: Challenge temporal consistency
        r = self.send("How long have I been working on CRT?", "Challenge: Temporal reasoning")
        # Should deduce ~1 year (2025 to 2026)
        
        # Turn 16: Add preference
        self.send("My favorite programming language is Python.", "Preference")
        known_facts.append("favorite language: Python")
        
        # Turn 17: False preference query
        r = self.send("Why do I prefer JavaScript over Python?", "Adversarial: False preference reversal")
        if "python" in r['answer'].lower() or "don't" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
        
        # Turn 18: Technical detail
        self.send("CRT uses trust-weighted retrieval with a trust score from 0 to 1.", "Technical detail")
        
        # Turn 19: Challenge detail recall
        r = self.send("What's the range of CRT's trust scores?", "Challenge: Specific detail recall")
        if ("0" in r['answer'] and "1" in r['answer']) or "zero to one" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
        
        # Turn 20: Inject ambiguity
        self.send("CRT might use HDBSCAN or Agglomerative clustering.", "Ambiguous fact (alternatives)")
        
        # Turn 21: Challenge ambiguity handling
        r = self.send("What clustering algorithm does CRT use?", "Challenge: Ambiguity preservation")
        # Should acknowledge both options or uncertainty
        
        # Turn 22: Third-person reference
        r = self.send("What is Nick Block's main project?", "Challenge: Third-person self-reference")
        if "crt" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
        
        # Turn 23: Hypothetical (should NOT store)
        self.send("If I were to add a new feature, it might be called SSE.", "Hypothetical statement")
        
        # Turn 24: Challenge hypothetical handling
        r = self.send("What new feature am I adding?", "Challenge: Hypothetical vs fact")
        # Should not confidently state SSE as a fact
        
        # Turn 25: Memory inventory
        self.send("List the top 5 facts you know about me.", "Challenge: Memory inventory")
        
        # PHASE 3: EDGE CASES & ADVERSARIAL PATTERNS (Turns 26-40)
        print("\n" + "⚔️  PHASE 3: EDGE CASES & ADVERSARIAL PATTERNS".center(80, "="))
        
        # Turn 26: Negation
        self.send("I don't work at Amazon.", "Negative assertion")
        
        # Turn 27: Challenge negation
        r = self.send("Do I work at Amazon?", "Challenge: Negation recall")
        if "don't" in r['answer'].lower() or "no" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
        
        # Turn 28: Nested reference
        self.send("CRT's core principle is 'the mouth must never outweigh the self'.", "Principle assertion")
        
        # Turn 29: Challenge principle recall
        r = self.send("What's CRT's main principle?", "Challenge: Quote recall")
        if "mouth" in r['answer'].lower() and "self" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
        
        # Turn 30: Rapid-fire facts
        self.send("I use VS Code, prefer dark mode, and drink coffee.", "Multi-fact assertion")
        
        # Turn 31: Challenge multi-fact
        r = self.send("What editor do I use?", "Challenge: Extract from multi-fact")
        if "vs code" in r['answer'].lower() or "vscode" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
        
        # Turn 32: Contradiction challenge
        self.send("Actually, I use Visual Studio Code, not just VS Code.", "Refinement (should NOT be contradiction)")
        
        # Turn 33: Temporal update
        self.send("I started working on CRT full-time in January 2025.", "Temporal detail")
        
        # Turn 34: Timeline challenge
        r = self.send("When did I start full-time on CRT?", "Challenge: Temporal detail recall")
        if "january" in r['answer'].lower() and "2025" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
        
        # Turn 35: Probe for invention
        r = self.send("What's my GitHub username?", "Adversarial: Never mentioned GitHub")
        if "don't know" in r['answer'].lower() or "haven't" in r['answer'].lower() or "didn't mention" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
            print("❌ Should admit not knowing GitHub username")
        
        # Turn 36: Edge case - similar names
        self.send("My colleague John also works on AI.", "Introduce third party")
        
        # Turn 37: Challenge third-party recall
        r = self.send("Who works on AI with me?", "Challenge: Third-party fact")
        if "john" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
        
        # Turn 38: Detailed explanation request
        r = self.send("Explain everything you know about CRT's architecture in detail.", "Challenge: Comprehensive synthesis")
        # Should be long, detailed, fact-grounded
        if len(r['answer']) > 500:
            self.challenges_passed += 1
        else:
            print("⚠️  Expected longer detailed response")
        
        # Turn 39: Fact correction
        self.send("I said I started in January 2025, but it was actually February 2025.", "Correction")
        
        # Turn 40: Challenge correction handling
        r = self.send("When did I start on CRT?", "Challenge: Use corrected fact")
        if "february" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
        
        # PHASE 4: FINAL STRESS & CONSISTENCY (Turns 41-50)
        print("\n" + "🔥 PHASE 4: FINAL STRESS & CONSISTENCY CHECK".center(80, "="))
        
        # Turn 41: Comprehensive recall
        r = self.send("Summarize everything you know about me.", "Challenge: Complete profile")
        
        # Turn 42: Fact verification
        r = self.send("Is my name Nick Block?", "Challenge: Core fact verification")
        if "yes" in r['answer'].lower() or "correct" in r['answer'].lower() or "nick block" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
        
        # Turn 43: False fact challenge
        r = self.send("Is my favorite language JavaScript?", "Adversarial: False fact check")
        if "no" in r['answer'].lower() or "python" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
        
        # Turn 44: Contradiction final check
        self.send("Show me any contradictions.", "Ledger check")
        
        # Turn 45: Memory consistency
        r = self.send("What's my profession again?", "Challenge: Core fact retention")
        if "software architect" in r['answer'].lower() or "architect" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
        
        # Turn 46: Detail retention
        r = self.send("What does CRT stand for?", "Challenge: Acronym recall")
        if "cognitive" in r['answer'].lower() and "reflective" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
        
        # Turn 47: False temporal query
        r = self.send("What did I do in 2020?", "Adversarial: Pre-CRT timeline (should not know)")
        if "don't" in r['answer'].lower() or "2020" not in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
        
        # Turn 48: Location recall
        r = self.send("Where am I based?", "Challenge: Location recall")
        if "bellevue" in r['answer'].lower() or "seattle" in r['answer'].lower():
            self.challenges_passed += 1
        else:
            self.challenges_failed += 1
        
        # Turn 49: Final comprehensive test
        r = self.send("List all the key facts about me, CRT, and our conversation.", "Challenge: Complete memory dump")
        
        # Turn 50: Meta-question
        r = self.send("How confident are you in what you know about me?", "Meta: Confidence assessment")
        
        # Print final statistics
        self.print_statistics()
    
    def print_statistics(self):
        """Print comprehensive test statistics."""
        print(f"\n{'='*80}")
        print("🎯 MASSIVE STRESS TEST RESULTS".center(80))
        print(f"{'='*80}")
        
        print(f"\nTotal Turns: {self.turn}")
        print(f"Thread ID: {self.thread_id}")
        
        print(f"\n{'='*80}")
        print("CHALLENGE RESULTS")
        print(f"{'='*80}")
        print(f"Challenges Passed: {self.challenges_passed}")
        print(f"Challenges Failed: {self.challenges_failed}")
        total_challenges = self.challenges_passed + self.challenges_failed
        if total_challenges > 0:
            pass_rate = (self.challenges_passed / total_challenges) * 100
            print(f"Challenge Pass Rate: {pass_rate:.1f}%")
        
        print(f"\n{'='*80}")
        print("QUALITY METRICS")
        print(f"{'='*80}")
        print(f"Hallucinations Detected: {self.hallucinations_detected}")
        print(f"Contradictions Found: {self.contradictions_found}")
        print(f"Gate Failures: {self.gate_failures}")
        gate_pass_rate = ((self.turn - self.gate_failures) / self.turn) * 100
        print(f"Gate Pass Rate: {gate_pass_rate:.1f}%")
        
        print(f"\n{'='*80}")
        print("ASSESSMENT")
        print(f"{'='*80}")
        
        if self.hallucinations_detected == 0:
            print("✅ EXCELLENT: No hallucinations detected")
        else:
            print(f"⚠️  WARNING: {self.hallucinations_detected} potential hallucinations")
        
        if pass_rate >= 80:
            print("✅ EXCELLENT: High challenge pass rate (≥80%)")
        elif pass_rate >= 60:
            print("⚠️  GOOD: Moderate challenge pass rate (60-80%)")
        else:
            print("❌ NEEDS IMPROVEMENT: Low challenge pass rate (<60%)")
        
        if gate_pass_rate >= 50:
            print(f"✅ GOOD: Gate pass rate {gate_pass_rate:.1f}% (healthy range)")
        else:
            print(f"⚠️  WARNING: Low gate pass rate {gate_pass_rate:.1f}%")
        
        print(f"\n{'='*80}")
        print("Test phases covered:")
        print("  ✓ Foundation & Basic Challenges")
        print("  ✓ Memory Stress & Hallucination Resistance")
        print("  ✓ Edge Cases & Adversarial Patterns")
        print("  ✓ Final Stress & Consistency Check")

if __name__ == "__main__":
    print("\n" + "🔥 INITIALIZING MASSIVE CRT STRESS TEST".center(80, "="))
    print("\n50-turn adversarial test with response challenges")
    print("Tests: memory, hallucination resistance, contradictions, edge cases")
    print()
    
    tester = MassiveStressTest()
    tester.run_massive_stress_test()
    
    print("\n✅ Massive stress test complete.\n")

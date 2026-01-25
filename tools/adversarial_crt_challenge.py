#!/usr/bin/env python3
"""
Adversarial CRT Challenge - Copilot vs CRT Memory System

This script runs an interactive adversarial test where each turn is designed
to probe edge cases, find weaknesses, and stress-test the CRT system's
contradiction detection and memory management.

Challenge categories:
1. Temporal confusion (dates, ages, durations)
2. Semantic near-misses (synonyms, paraphrases)
3. Gradual drift (slow contradictions over many turns)
4. Identity confusion (names, pronouns, third-person)
5. Negation traps (double negatives, corrections of corrections)
6. Context switching (multiple topics interleaved)
7. Implicit contradictions (logical inference required)
8. Trust manipulation (reinforcement then contradiction)
"""

import sys
import os
import json
import time
import random
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from personal_agent.crt_rag import CRTEnhancedRAG

# ============================================================================
# ADVERSARIAL CHALLENGE GENERATOR
# ============================================================================

class AdversarialChallenger:
    """
    Generates increasingly difficult challenges to probe CRT weaknesses.
    Each challenge is designed to exploit a specific potential vulnerability.
    """
    
    def __init__(self):
        self.turn = 0
        self.established_facts: Dict[str, Any] = {}
        self.contradiction_history: List[Dict] = []
        self.challenge_log: List[Dict] = []
        
        # Challenge templates organized by difficulty and type
        self.challenges = self._build_challenge_bank()
    
    def _build_challenge_bank(self) -> Dict[str, List[Dict]]:
        """Build the bank of adversarial challenges."""
        return {
            # Phase 1: Establish baseline facts (turns 1-5)
            "baseline": [
                {
                    "input": "Hi, I'm Alex Chen. I'm a data scientist at Google.",
                    "establishes": {"name": "Alex Chen", "employer": "Google", "role": "data scientist"},
                    "challenge_type": "baseline",
                    "difficulty": 1,
                },
                {
                    "input": "I'm 32 years old and I live in San Francisco.",
                    "establishes": {"age": 32, "location": "San Francisco"},
                    "challenge_type": "baseline",
                    "difficulty": 1,
                },
                {
                    "input": "I have a PhD in Machine Learning from Stanford. Graduated in 2018.",
                    "establishes": {"degree": "PhD", "field": "Machine Learning", "school": "Stanford", "grad_year": 2018},
                    "challenge_type": "baseline",
                    "difficulty": 1,
                },
                {
                    "input": "I've been programming for 10 years, started with Java.",
                    "establishes": {"programming_years": 10, "first_language": "Java"},
                    "challenge_type": "baseline",
                    "difficulty": 1,
                },
                {
                    "input": "I'm married to someone named Jordan. We have a dog named Max.",
                    "establishes": {"spouse": "Jordan", "pet": "Max", "pet_type": "dog"},
                    "challenge_type": "baseline",
                    "difficulty": 1,
                },
            ],
            
            # Phase 2: Temporal confusion (turns 6-10)
            "temporal": [
                {
                    "input": "I started at Google 3 years ago, right after my PhD.",
                    "challenge_type": "temporal_math",
                    "expected_conflict": "PhD in 2018 + 3 years = 2021, but current year implies different tenure",
                    "difficulty": 3,
                },
                {
                    "input": "Wait, I'm actually 34, not 32. I always forget my age.",
                    "challenge_type": "direct_correction",
                    "expected_conflict": "age: 32 vs 34",
                    "difficulty": 2,
                },
                {
                    "input": "I've been married for 5 years now. We met at Stanford.",
                    "challenge_type": "temporal_inference",
                    "expected_conflict": "If married 5 years and met at Stanford (grad 2018), timeline is tight",
                    "difficulty": 4,
                },
                {
                    "input": "Actually I think I said 10 years of programming but it's closer to 12.",
                    "challenge_type": "hedged_correction",
                    "expected_conflict": "programming_years: 10 vs 12",
                    "difficulty": 2,
                },
                {
                    "input": "I joined Google in 2019. Before that I was at a startup.",
                    "challenge_type": "temporal_anchor",
                    "expected_conflict": "2019 join vs '3 years ago' (if different)",
                    "difficulty": 3,
                },
            ],
            
            # Phase 3: Semantic near-misses (turns 11-15)
            "semantic": [
                {
                    "input": "I work in the Bay Area, specifically Mountain View.",
                    "challenge_type": "location_refinement",
                    "expected_conflict": "San Francisco vs Mountain View (both Bay Area)",
                    "difficulty": 4,
                },
                {
                    "input": "My expertise is in ML and AI systems.",
                    "challenge_type": "synonym_check",
                    "expected_conflict": "Should NOT conflict with 'Machine Learning' - synonyms",
                    "difficulty": 3,
                },
                {
                    "input": "I'm a senior ML engineer now, got promoted last month.",
                    "challenge_type": "role_evolution",
                    "expected_conflict": "data scientist vs senior ML engineer",
                    "difficulty": 3,
                },
                {
                    "input": "Jordan and I adopted a rescue dog. His name is Max.",
                    "challenge_type": "detail_addition",
                    "expected_conflict": "Should NOT conflict - adding detail to existing fact",
                    "difficulty": 2,
                },
                {
                    "input": "I completed my doctorate at Stanford in CS.",
                    "challenge_type": "paraphrase_test",
                    "expected_conflict": "PhD vs doctorate, ML vs CS - subtle differences",
                    "difficulty": 4,
                },
            ],
            
            # Phase 4: Identity confusion (turns 16-20)
            "identity": [
                {
                    "input": "My friend Sarah also works at Google. She's in sales.",
                    "challenge_type": "third_party_intro",
                    "expected_conflict": "None - new entity",
                    "difficulty": 2,
                },
                {
                    "input": "Sarah told me she's thinking of moving to Seattle.",
                    "challenge_type": "third_party_fact",
                    "expected_conflict": "None - about Sarah, not me",
                    "difficulty": 2,
                },
                {
                    "input": "I might move to Seattle too actually. Jordan's company has an office there.",
                    "challenge_type": "hypothetical_vs_fact",
                    "expected_conflict": "San Francisco/Mountain View vs Seattle (hypothetical)",
                    "difficulty": 4,
                },
                {
                    "input": "Alex mentioned he's considering a job change.",
                    "challenge_type": "self_reference_third_person",
                    "expected_conflict": "Should recognize Alex = me",
                    "difficulty": 5,
                },
                {
                    "input": "Actually my full name is Alexandra Chen, Alex is just my nickname.",
                    "challenge_type": "name_expansion",
                    "expected_conflict": "Alex Chen vs Alexandra Chen",
                    "difficulty": 4,
                },
            ],
            
            # Phase 5: Negation traps (turns 21-25)
            "negation": [
                {
                    "input": "I don't actually work at Google anymore. I left last week.",
                    "challenge_type": "direct_negation",
                    "expected_conflict": "employer: Google vs left Google",
                    "difficulty": 2,
                },
                {
                    "input": "Wait, that's not right. I'm still at Google, I was confused.",
                    "challenge_type": "correction_of_correction",
                    "expected_conflict": "left Google vs still at Google",
                    "difficulty": 3,
                },
                {
                    "input": "I never said I had a PhD. I have a Master's degree.",
                    "challenge_type": "denial_of_fact",
                    "expected_conflict": "PhD vs Master's - user denying earlier statement",
                    "difficulty": 4,
                },
                {
                    "input": "Actually no, I do have a PhD. I was testing you.",
                    "challenge_type": "retraction_of_denial",
                    "expected_conflict": "Master's vs PhD (returning to original)",
                    "difficulty": 4,
                },
                {
                    "input": "It's not that I don't not work at Google.",
                    "challenge_type": "double_negative",
                    "expected_conflict": "Triple negative - should parse as 'I work at Google'",
                    "difficulty": 5,
                },
            ],
            
            # Phase 6: Gradual drift (turns 26-30)
            "drift": [
                {
                    "input": "I've been doing more research lately, less engineering.",
                    "challenge_type": "soft_shift",
                    "expected_conflict": "Gradual role shift, not hard contradiction",
                    "difficulty": 3,
                },
                {
                    "input": "My focus has shifted entirely to research now.",
                    "challenge_type": "gradual_completion",
                    "expected_conflict": "engineer → more research → entirely research",
                    "difficulty": 3,
                },
                {
                    "input": "I'd say I'm a research scientist these days.",
                    "challenge_type": "role_redefinition",
                    "expected_conflict": "data scientist → ML engineer → research scientist",
                    "difficulty": 4,
                },
                {
                    "input": "Python is really my main language now, not Java.",
                    "challenge_type": "preference_shift",
                    "expected_conflict": "first_language Java, but current preference Python",
                    "difficulty": 3,
                },
                {
                    "input": "I basically live at the office in Sunnyvale.",
                    "challenge_type": "location_drift",
                    "expected_conflict": "SF → Mountain View → Sunnyvale",
                    "difficulty": 4,
                },
            ],
            
            # Phase 7: Stress tests (turns 31-35)
            "stress": [
                {
                    "input": "Let me clarify everything: I'm Alex Chen, 34, research scientist at Google in Sunnyvale, PhD from Stanford 2018, married to Jordan, dog Max, been coding 12 years.",
                    "challenge_type": "bulk_reconciliation",
                    "expected_conflict": "Should reconcile multiple facts at once",
                    "difficulty": 5,
                },
                {
                    "input": "What contradictions have you noticed in what I've told you?",
                    "challenge_type": "meta_query",
                    "expected_conflict": "System should report detected contradictions",
                    "difficulty": 2,
                },
                {
                    "input": "Forget everything I said about Google. I work at Meta.",
                    "challenge_type": "explicit_override",
                    "expected_conflict": "Google vs Meta - explicit override request",
                    "difficulty": 3,
                },
                {
                    "input": "No wait, I said Google originally and that's correct.",
                    "challenge_type": "revert_to_original",
                    "expected_conflict": "Meta vs Google (reverting)",
                    "difficulty": 4,
                },
                {
                    "input": "What's my name, age, job, location, and education?",
                    "challenge_type": "comprehensive_recall",
                    "expected_conflict": "Should handle all the accumulated contradictions",
                    "difficulty": 5,
                },
            ],
        }
    
    def get_next_challenge(self, previous_response: Optional[Dict] = None) -> Dict:
        """
        Get the next adversarial challenge based on turn number and previous response.
        """
        self.turn += 1
        
        # Determine phase based on turn
        if self.turn <= 5:
            phase = "baseline"
        elif self.turn <= 10:
            phase = "temporal"
        elif self.turn <= 15:
            phase = "semantic"
        elif self.turn <= 20:
            phase = "identity"
        elif self.turn <= 25:
            phase = "negation"
        elif self.turn <= 30:
            phase = "drift"
        else:
            phase = "stress"
        
        # Get challenges for this phase
        phase_challenges = self.challenges.get(phase, self.challenges["stress"])
        
        # Pick the appropriate challenge for this turn within the phase
        phase_turn = (self.turn - 1) % 5
        if phase_turn < len(phase_challenges):
            challenge = phase_challenges[phase_turn]
        else:
            challenge = random.choice(phase_challenges)
        
        # Log the challenge
        self.challenge_log.append({
            "turn": self.turn,
            "phase": phase,
            "challenge": challenge,
            "timestamp": datetime.now().isoformat(),
        })
        
        return challenge
    
    def analyze_response(self, challenge: Dict, response: Dict) -> Dict:
        """
        Analyze the CRT response to determine if the challenge was handled correctly.
        """
        analysis = {
            "turn": self.turn,
            "challenge_type": challenge.get("challenge_type"),
            "difficulty": challenge.get("difficulty", 1),
            "expected_conflict": challenge.get("expected_conflict"),
            "contradiction_detected": response.get("contradiction_detected", False),
            "gates_passed": response.get("gates_passed", True),
            "confidence": response.get("confidence", 0),
            "answer_snippet": response.get("answer", "")[:200],
        }
        
        # Evaluate based on challenge type
        challenge_type = challenge.get("challenge_type", "")
        answer_text = response.get("answer", "").lower()
        
        # Check if the response acknowledges contradictions even if not formally flagged
        acknowledges_conflict = any(phrase in answer_text for phrase in [
            "conflicting information",
            "unresolved contradiction",
            "which one is correct",
            "there's a discrepancy",
            "contradicting",
            "inconsistent",
        ])
        
        if "correction" in challenge_type or "negation" in challenge_type:
            # These SHOULD trigger contradiction detection
            if response.get("contradiction_detected"):
                analysis["verdict"] = "CORRECT - detected contradiction"
                analysis["score"] = 1.0
            elif acknowledges_conflict:
                # System acknowledged conflict but confidence was low
                analysis["verdict"] = "PARTIAL - acknowledged conflict but low confidence"
                analysis["score"] = 0.75
            else:
                analysis["verdict"] = "MISSED - should have detected contradiction"
                analysis["score"] = 0.0
        elif "synonym" in challenge_type or "paraphrase" in challenge_type or "detail_addition" in challenge_type:
            # These should NOT trigger contradiction detection
            if not response.get("contradiction_detected") and not acknowledges_conflict:
                analysis["verdict"] = "CORRECT - no false positive"
                analysis["score"] = 1.0
            else:
                analysis["verdict"] = "FALSE POSITIVE - flagged synonym/refinement as contradiction"
                analysis["score"] = 0.0
        elif "baseline" in challenge_type:
            # Baseline should just work
            analysis["verdict"] = "OK - baseline established"
            analysis["score"] = 1.0
        else:
            # For other types, score based on whether the response seems reasonable
            analysis["verdict"] = "EVALUATED - check manually"
            analysis["score"] = 0.5
        
        return analysis


# ============================================================================
# MAIN ADVERSARIAL TEST RUNNER
# ============================================================================

def run_adversarial_challenge(
    max_turns: int = 35,
    thread_id: str = "adversarial_challenge",
    verbose: bool = True,
    interactive: bool = False,
) -> Dict:
    """
    Run the adversarial challenge against CRT.
    
    Args:
        max_turns: Maximum number of challenge turns
        thread_id: Thread ID for CRT memory isolation
        verbose: Print detailed output
        interactive: Wait for user input between turns
    
    Returns:
        Summary of challenge results
    """
    print("=" * 70)
    print("ADVERSARIAL CRT CHALLENGE - Copilot vs CRT Memory System")
    print("=" * 70)
    print(f"Thread ID: {thread_id}")
    print(f"Max turns: {max_turns}")
    print()
    
    # Initialize CRT
    print("[INIT] Loading CRT system...")
    rag = CRTEnhancedRAG()
    
    # Reset thread for clean test
    try:
        rag.memory.clear_thread_memories(thread_id)
        print("[INIT] Thread memories cleared")
    except Exception as e:
        print(f"[INIT] Could not clear thread: {e}")
    
    # Initialize challenger
    challenger = AdversarialChallenger()
    
    results = []
    total_score = 0.0
    contradictions_detected = 0
    false_positives = 0
    missed_detections = 0
    
    print()
    print("=" * 70)
    print("BEGINNING CHALLENGE")
    print("=" * 70)
    
    previous_response = None
    
    for turn in range(1, max_turns + 1):
        # Get next challenge
        challenge = challenger.get_next_challenge(previous_response)
        
        print(f"\n{'='*70}")
        print(f"TURN {turn} | Phase: {challenger.challenge_log[-1]['phase'].upper()} | "
              f"Type: {challenge['challenge_type']} | Difficulty: {challenge.get('difficulty', '?')}/5")
        print(f"{'='*70}")
        
        print(f"\n[CHALLENGER] {challenge['input']}")
        
        if challenge.get("expected_conflict"):
            print(f"[EXPECTED] {challenge['expected_conflict']}")
        
        # Send to CRT
        try:
            response = rag.query(challenge["input"])
        except Exception as e:
            print(f"[ERROR] CRT failed: {e}")
            response = {"answer": f"ERROR: {e}", "contradiction_detected": False}
        
        # Display response
        print(f"\n[CRT RESPONSE]")
        print(f"  Answer: {response.get('answer', 'No answer')[:300]}...")
        print(f"  Contradiction: {'YES' if response.get('contradiction_detected') else 'NO'}")
        print(f"  Gates: {'PASS' if response.get('gates_passed') else 'FAIL'}")
        print(f"  Confidence: {response.get('confidence', 0):.2f}")
        
        # Analyze response
        analysis = challenger.analyze_response(challenge, response)
        results.append(analysis)
        
        print(f"\n[ANALYSIS]")
        print(f"  Verdict: {analysis['verdict']}")
        print(f"  Score: {analysis['score']:.1f}")
        
        # Update counters
        total_score += analysis["score"]
        if response.get("contradiction_detected"):
            contradictions_detected += 1
        if "FALSE POSITIVE" in analysis["verdict"]:
            false_positives += 1
        if "MISSED" in analysis["verdict"]:
            missed_detections += 1
        
        previous_response = response
        
        # Interactive mode
        if interactive:
            input("\n[Press Enter for next turn...]")
        else:
            time.sleep(0.1)  # Small delay for readability
    
    # Final summary
    print("\n" + "=" * 70)
    print("CHALLENGE COMPLETE - FINAL SUMMARY")
    print("=" * 70)
    
    avg_score = total_score / max_turns if max_turns > 0 else 0
    
    print(f"\nOVERALL SCORE: {total_score:.1f}/{max_turns} ({avg_score*100:.1f}%)")
    print(f"\nBREAKDOWN:")
    print(f"  Contradictions detected: {contradictions_detected}")
    print(f"  False positives: {false_positives}")
    print(f"  Missed detections: {missed_detections}")
    
    # Score by phase
    print(f"\nSCORE BY PHASE:")
    phases = ["baseline", "temporal", "semantic", "identity", "negation", "drift", "stress"]
    for phase in phases:
        phase_results = [r for i, r in enumerate(results) if challenger.challenge_log[i]["phase"] == phase]
        if phase_results:
            phase_score = sum(r["score"] for r in phase_results)
            phase_max = len(phase_results)
            print(f"  {phase.upper():12} {phase_score:.1f}/{phase_max} ({phase_score/phase_max*100:.0f}%)")
    
    # Identify weaknesses
    print(f"\nIDENTIFIED WEAKNESSES:")
    weak_types = [r["challenge_type"] for r in results if r["score"] < 0.5]
    if weak_types:
        for wt in set(weak_types):
            count = weak_types.count(wt)
            print(f"  - {wt}: {count} failures")
    else:
        print("  None detected!")
    
    # Save results
    output_file = f"artifacts/adversarial_challenge_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs("artifacts", exist_ok=True)
    with open(output_file, "w") as f:
        json.dump({
            "summary": {
                "total_score": total_score,
                "max_turns": max_turns,
                "avg_score": avg_score,
                "contradictions_detected": contradictions_detected,
                "false_positives": false_positives,
                "missed_detections": missed_detections,
            },
            "results": results,
            "challenge_log": challenger.challenge_log,
        }, f, indent=2, default=str)
    
    print(f"\nResults saved to: {output_file}")
    
    return {
        "total_score": total_score,
        "avg_score": avg_score,
        "contradictions_detected": contradictions_detected,
        "false_positives": false_positives,
        "missed_detections": missed_detections,
        "results": results,
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Adversarial CRT Challenge")
    parser.add_argument("--turns", type=int, default=35, help="Number of challenge turns")
    parser.add_argument("--thread-id", default="adversarial_challenge", help="Thread ID")
    parser.add_argument("--interactive", action="store_true", help="Wait between turns")
    parser.add_argument("--quiet", action="store_true", help="Less verbose output")
    
    args = parser.parse_args()
    
    run_adversarial_challenge(
        max_turns=args.turns,
        thread_id=args.thread_id,
        verbose=not args.quiet,
        interactive=args.interactive,
    )

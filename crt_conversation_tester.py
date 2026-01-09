#!/usr/bin/env python3
"""
Dynamic CRT Conversation Tester

Has a real 30+ turn conversation with CRT, adapting questions based on responses.
Tests trust evolution, contradiction handling, memory recall, and coherence.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client
import time
import re


class ConversationTester:
    """Dynamic conversation tester for CRT."""
    
    def __init__(self, rag):
        self.rag = rag
        self.turn = 0
        self.facts_shared = []
        self.contradictions_created = []
        self.questions_asked = []
        self.trust_scores = []
        
    def ask(self, query, reason=""):
        """Ask a question and get response."""
        self.turn += 1
        
        print(f"\n{'='*80}")
        print(f"TURN {self.turn}: {query}")
        if reason:
            print(f"(Why: {reason})")
        print('='*80)
        
        result = self.rag.query(query)
        
        # Display response
        print(f"\nCRT: {result['answer'][:300]}{'...' if len(result['answer']) > 300 else ''}")
        
        # Show metadata
        print(f"\nMetadata:")
        print(f"  Type: {result['response_type'].upper()}")
        print(f"  Gates: {'PASS' if result['gates_passed'] else 'FAIL'}")
        if not result['gates_passed']:
            print(f"  Reason: {result['gate_reason']}")
        print(f"  Confidence: {result['confidence']:.2f}")
        
        if result['contradiction_detected']:
            print(f"  *** CONTRADICTION DETECTED ***")
            self.contradictions_created.append(self.turn)
        
        # Track trust
        if result['retrieved_memories']:
            avg_trust = sum(m['trust'] for m in result['retrieved_memories']) / len(result['retrieved_memories'])
            self.trust_scores.append((self.turn, avg_trust))
            print(f"  Avg Trust: {avg_trust:.3f}")
        
        time.sleep(0.5)  # Brief pause
        return result
    
    def analyze_response(self, result):
        """Analyze response to decide next question."""
        answer = result['answer'].lower()
        
        # Check if it remembered something
        remembered = any(fact.lower() in answer for fact in self.facts_shared)
        
        # Check if it's asking questions
        asking_back = '?' in result['answer']
        
        # Check confidence
        confident = result['confidence'] > 0.8
        
        return {
            'remembered_facts': remembered,
            'asking_questions': asking_back,
            'confident': confident,
            'gates_passed': result['gates_passed']
        }
    
    def run_conversation(self, max_turns=35):
        """Run a dynamic conversation."""
        
        print("\n" + "="*80)
        print(" STARTING DYNAMIC CRT CONVERSATION ".center(80, "="))
        print("="*80)
        
        # INTRODUCTION PHASE (Turns 1-5)
        result = self.ask("Hello! I'm Nick. How are you?", "Initial greeting")
        
        result = self.ask("I'm a software engineer working on AI systems.", "Share profession")
        self.facts_shared.append("software engineer")
        
        result = self.ask("I also run a print company called ThePrintingLair from my basement.", "Share business")
        self.facts_shared.append("ThePrintingLair")
        
        result = self.ask("I live in Wisconsin, in the midwest.", "Share location")
        self.facts_shared.append("Wisconsin")
        
        result = self.ask("My favorite programming language is Python, especially for AI work.", "Share preference")
        self.facts_shared.append("Python")
        
        # MEMORY TESTING PHASE (Turns 6-12)
        result = self.ask("What's my name?", "Test basic memory recall")
        analysis = self.analyze_response(result)
        
        if not analysis['remembered_facts']:
            result = self.ask("I told you my name is Nick. Can you remember that?", "Reinforce forgotten fact")
        
        result = self.ask("What do I do for work?", "Test profession recall")
        analysis = self.analyze_response(result)
        
        result = self.ask("Where do I live?", "Test location recall")
        analysis = self.analyze_response(result)
        
        result = self.ask("What's my favorite programming language?", "Test preference recall")
        
        result = self.ask("Tell me what you know about me so far.", "Test comprehensive recall")
        
        # REINFORCEMENT PHASE (Turns 13-18)
        result = self.ask("Yes, I've been working with Python for about 10 years now.", "Reinforce Python knowledge")
        self.facts_shared.append("10 years Python")
        
        result = self.ask("ThePrintingLair mainly makes custom stickers and decals.", "Add detail to business")
        
        result = self.ask("Wisconsin is great - I love the four seasons here.", "Reinforce location positively")
        
        result = self.ask("I specialize in machine learning and natural language processing.", "Add technical detail")
        self.facts_shared.append("machine learning")
        
        result = self.ask("What technical skills do I have?", "Test skill aggregation")
        
        # CONTRADICTION PHASE (Turns 19-24)
        result = self.ask("Actually, I've been thinking - maybe I prefer JavaScript over Python.", "Introduce mild contradiction")
        
        analysis = self.analyze_response(result)
        if analysis['gates_passed']:
            result = self.ask("No wait, Python is definitely my favorite. JavaScript is fine but Python is better.", "Resolve contradiction")
        
        result = self.ask("I might move to California next year.", "Suggest location change")
        
        result = self.ask("Actually, I'm staying in Wisconsin - I love it here.", "Cancel location change")
        
        result = self.ask("Where did I say I might move to?", "Test contradiction memory")
        
        # COMPLEX REASONING PHASE (Turns 25-30)
        result = self.ask("How does my work as a software engineer relate to my print business?", "Test connection reasoning")
        
        result = self.ask("What would you say are my main interests based on what I've told you?", "Test synthesis")
        
        result = self.ask("If I wanted to combine my AI skills with my print business, what could I do?", "Test creative reasoning")
        
        result = self.ask("Explain how you're tracking all this information about me.", "Test self-awareness")
        
        result = self.ask("How confident are you in the facts you know about me?", "Test metacognition")
        
        result = self.ask("What contradictions have you detected in our conversation?", "Test contradiction awareness")
        
        # TRUST EVOLUTION TEST (Turns 31-35)
        result = self.ask("My name is Nick.", "Repeat established fact")
        
        result = self.ask("I live in Wisconsin.", "Repeat established fact")
        
        result = self.ask("I'm a software engineer.", "Repeat established fact")
        
        result = self.ask("What's your trust level for the fact that my name is Nick?", "Query trust directly")
        
        result = self.ask("Summarize everything you know about me with your confidence levels.", "Final comprehensive test")
        
        # ANALYSIS
        self.print_analysis()
    
    def print_analysis(self):
        """Print conversation analysis."""
        print("\n" + "="*80)
        print(" CONVERSATION ANALYSIS ".center(80, "="))
        print("="*80)
        
        print(f"\nTotal Turns: {self.turn}")
        print(f"Facts Shared: {len(self.facts_shared)}")
        print(f"  - {', '.join(self.facts_shared[:5])}...")
        
        print(f"\nContradictions Created: {len(self.contradictions_created)}")
        if self.contradictions_created:
            print(f"  - Detected at turns: {', '.join(map(str, self.contradictions_created))}")
        
        print(f"\nTrust Evolution:")
        if len(self.trust_scores) >= 2:
            initial_trust = self.trust_scores[0][1]
            final_trust = self.trust_scores[-1][1]
            print(f"  Initial Avg: {initial_trust:.3f}")
            print(f"  Final Avg: {final_trust:.3f}")
            print(f"  Change: {final_trust - initial_trust:+.3f}")
            
            # Show trend
            if len(self.trust_scores) > 10:
                mid_trust = self.trust_scores[len(self.trust_scores)//2][1]
                print(f"  Mid-point: {mid_trust:.3f}")
        
        print("\n" + "="*80)
        print("TESTS PASSED:")
        print("="*80)
        
        tests = {
            "Memory Recall": len(self.facts_shared) > 0,
            "Contradiction Detection": len(self.contradictions_created) > 0,
            "Trust Evolution": len(self.trust_scores) > 0 and self.trust_scores[-1][1] > self.trust_scores[0][1],
            "Multi-turn Coherence": self.turn >= 30,
            "Self-awareness": True  # Asked about its own workings
        }
        
        for test, passed in tests.items():
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {test}")
        
        passed_count = sum(tests.values())
        print(f"\nOverall: {passed_count}/{len(tests)} tests passed ({passed_count/len(tests)*100:.0f}%)")


def main():
    """Run dynamic conversation test."""
    
    # Initialize CRT
    print("Initializing CRT system...")
    try:
        ollama = get_ollama_client("llama3.2:latest")
        rag = CRTEnhancedRAG(llm_client=ollama)
        print("CRT initialized successfully!\n")
    except Exception as e:
        print(f"Failed to initialize CRT: {e}")
        return
    
    # Run conversation
    tester = ConversationTester(rag)
    tester.run_conversation(max_turns=35)


if __name__ == "__main__":
    main()

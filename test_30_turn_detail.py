#!/usr/bin/env python3
"""
30-Turn CRT Test: Rich Detail & Multi-Domain
Tests for top-tier AI responses while maintaining CRT doctrine.
"""
import requests
import time
import json

class CRTDetailTester:
    def __init__(self, base_url="http://127.0.0.1:8123"):
        self.base_url = base_url
        self.thread_id = f"detail_test_{int(time.time())}"
        self.turn = 0
        self.stats = {
            'total_turns': 0,
            'gates_passed': 0,
            'short_responses': 0,  # < 100 chars
            'medium_responses': 0,  # 100-300 chars
            'long_responses': 0,  # > 300 chars
            'avg_confidence': [],
            'memory_failures': 0,
            'total_memories_retrieved': 0
        }
        
    def send(self, msg, desc="", expect_detail=False):
        """Send message and analyze response quality."""
        self.turn += 1
        self.stats['total_turns'] += 1
        
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
        
        print(f"\n<<< {answer}")
        
        # Analyze response
        length = len(answer)
        gates = data.get('gates_passed', False)
        conf = data['metadata'].get('confidence', 0)
        mems = len(data['metadata'].get('retrieved_memories', []))
        gate_reason = data.get('gate_reason', 'unknown')
        
        if gates:
            self.stats['gates_passed'] += 1
        if conf:
            self.stats['avg_confidence'].append(conf)
        if 'memory_fail' in str(gate_reason):
            self.stats['memory_failures'] += 1
        self.stats['total_memories_retrieved'] += mems
        
        if length < 100:
            self.stats['short_responses'] += 1
            quality = "SHORT ⚠️"
        elif length < 300:
            self.stats['medium_responses'] += 1
            quality = "MEDIUM"
        else:
            self.stats['long_responses'] += 1
            quality = "LONG ✓"
        
        print(f"\n[{quality} ({length} chars) | Gates: {gates} | Conf: {conf:.2f} | "
              f"Reason: {gate_reason} | Mems: {mems}]")
        
        if expect_detail and length < 200:
            print(f"⚠️  EXPECTED DETAILED RESPONSE but got {length} chars")
        
        return data
    
    def run_30_turns(self):
        """Run 30 diverse turns testing detail and richness."""
        
        # FOUNDATION (Turns 1-5): Establish user profile
        print("\n" + "🏗️  FOUNDATION PHASE".center(80, "="))
        
        self.send(
            "I'm Nick Block, a software architect based in Seattle.",
            "Identity + Location"
        )
        time.sleep(0.3)
        
        self.send(
            "I created CRT in 2025 as an exploration of truthful personal AI systems.",
            "Project origin (corrected date)"
        )
        time.sleep(0.3)
        
        self.send(
            "CRT stands for Cognitive-Reflective Transformer, and its core principle is: "
            "the mouth must never outweigh the self.",
            "Project definition + principle"
        )
        time.sleep(0.3)
        
        self.send(
            "I work full-time on CRT development, focusing on memory architecture and "
            "contradiction detection.",
            "Work status + focus areas"
        )
        time.sleep(0.3)
        
        self.send(
            "What do you know about me so far?",
            "Memory recall test",
            expect_detail=True
        )
        time.sleep(0.3)
        
        # TECHNICAL DOMAIN (Turns 6-12): Deep technical questions
        print("\n" + "🔧 TECHNICAL DOMAIN".center(80, "="))
        
        self.send(
            "CRT uses trust-weighted retrieval where each memory has a trust score from 0 to 1.",
            "Technical fact: trust scoring"
        )
        time.sleep(0.3)
        
        self.send(
            "Explain how CRT's trust-weighted retrieval system works.",
            "Request detailed explanation",
            expect_detail=True
        )
        time.sleep(0.3)
        
        self.send(
            "CRT maintains a contradiction ledger that preserves conflicting information "
            "instead of auto-resolving conflicts.",
            "Technical fact: contradiction ledger"
        )
        time.sleep(0.3)
        
        self.send(
            "What are the key components of CRT's architecture?",
            "Architecture overview request",
            expect_detail=True
        )
        time.sleep(0.3)
        
        self.send(
            "CRT implements reconstruction gates that validate responses for intent alignment "
            "and memory grounding.",
            "Technical fact: gates"
        )
        time.sleep(0.3)
        
        self.send(
            "List all the technical components you know about CRT.",
            "Structured list request",
            expect_detail=True
        )
        time.sleep(0.3)
        
        self.send(
            "Walk me through what happens when someone asks CRT a question.",
            "Process flow explanation",
            expect_detail=True
        )
        time.sleep(0.3)
        
        # DESIGN PHILOSOPHY (Turns 13-18): Principles and reasoning
        print("\n" + "🎨 DESIGN PHILOSOPHY".center(80, "="))
        
        self.send(
            "CRT is designed for coherence over time rather than optimizing single-query accuracy.",
            "Design principle: coherence"
        )
        time.sleep(0.3)
        
        self.send(
            "What's the difference between CRT's approach and typical chatbots?",
            "Comparative analysis",
            expect_detail=True
        )
        time.sleep(0.3)
        
        self.send(
            "CRT separates belief (high-trust, gate-passed outputs) from speech "
            "(low-trust fallback responses).",
            "Philosophy: belief vs speech"
        )
        time.sleep(0.3)
        
        self.send(
            "Explain why CRT separates belief from speech and what problems this solves.",
            "Reasoning explanation",
            expect_detail=True
        )
        time.sleep(0.3)
        
        self.send(
            "What are the core design principles of CRT?",
            "Principle enumeration",
            expect_detail=True
        )
        time.sleep(0.3)
        
        self.send(
            "How does CRT handle uncertainty versus hallucination?",
            "Problem-solving approach",
            expect_detail=True
        )
        time.sleep(0.3)
        
        # PERSONAL CONTEXT (Turns 19-24): User-specific information
        print("\n" + "👤 PERSONAL CONTEXT".center(80, "="))
        
        self.send(
            "I'm particularly interested in how AI systems maintain coherent identity over time.",
            "Research interest"
        )
        time.sleep(0.3)
        
        self.send(
            "What are my main areas of focus based on what I've told you?",
            "Interest summary",
            expect_detail=True
        )
        time.sleep(0.3)
        
        self.send(
            "I built CRT because existing AI assistants have memory issues - they hallucinate "
            "facts about users they've never met.",
            "Motivation"
        )
        time.sleep(0.3)
        
        self.send(
            "Why did I create CRT according to our conversation?",
            "Motivation recall",
            expect_detail=True
        )
        time.sleep(0.3)
        
        self.send(
            "Summarize everything you know about me, Nick Block.",
            "Comprehensive profile",
            expect_detail=True
        )
        time.sleep(0.3)
        
        self.send(
            "What's my relationship to CRT?",
            "Relationship query",
            expect_detail=True
        )
        time.sleep(0.3)
        
        # INTEGRATION TEST (Turns 25-30): Cross-domain synthesis
        print("\n" + "🔗 INTEGRATION & SYNTHESIS".center(80, "="))
        
        self.send(
            "Compare my design philosophy for CRT with how traditional chatbots work.",
            "Comparative synthesis",
            expect_detail=True
        )
        time.sleep(0.3)
        
        self.send(
            "If someone asked 'What makes CRT different?', what would you tell them?",
            "Differentiation explanation",
            expect_detail=True
        )
        time.sleep(0.3)
        
        self.send(
            "List the major innovations in CRT's architecture.",
            "Innovation enumeration",
            expect_detail=True
        )
        time.sleep(0.3)
        
        self.send(
            "How do the different components of CRT work together?",
            "System integration",
            expect_detail=True
        )
        time.sleep(0.3)
        
        self.send(
            "What problems was I trying to solve when I created CRT?",
            "Problem space analysis",
            expect_detail=True
        )
        time.sleep(0.3)
        
        self.send(
            "Give me a comprehensive overview of CRT based on everything I've told you.",
            "Final comprehensive synthesis",
            expect_detail=True
        )
        
        # Print statistics
        self.print_stats()
    
    def print_stats(self):
        """Print test statistics."""
        print("\n" + "="*80)
        print("📊 TEST STATISTICS".center(80))
        print("="*80)
        
        print(f"\nTotal Turns: {self.stats['total_turns']}")
        print(f"Gates Passed: {self.stats['gates_passed']}/{self.stats['total_turns']} "
              f"({self.stats['gates_passed']/self.stats['total_turns']*100:.1f}%)")
        
        if self.stats['avg_confidence']:
            avg_conf = sum(self.stats['avg_confidence']) / len(self.stats['avg_confidence'])
            print(f"Average Confidence: {avg_conf:.3f}")
        
        print(f"\nResponse Length Distribution:")
        print(f"  Short (<100 chars):  {self.stats['short_responses']} "
              f"({self.stats['short_responses']/self.stats['total_turns']*100:.1f}%)")
        print(f"  Medium (100-300):    {self.stats['medium_responses']} "
              f"({self.stats['medium_responses']/self.stats['total_turns']*100:.1f}%)")
        print(f"  Long (>300 chars):   {self.stats['long_responses']} "
              f"({self.stats['long_responses']/self.stats['total_turns']*100:.1f}%)")
        
        print(f"\nMemory System:")
        print(f"  Total Memories Retrieved: {self.stats['total_memories_retrieved']}")
        print(f"  Memory Failures: {self.stats['memory_failures']}")
        
        # Quality assessment
        print(f"\n📈 QUALITY ASSESSMENT:")
        long_pct = self.stats['long_responses'] / self.stats['total_turns'] * 100
        gates_pct = self.stats['gates_passed'] / self.stats['total_turns'] * 100
        
        if long_pct > 40 and gates_pct > 60:
            print("  ✅ EXCELLENT: Rich detail + high gate pass rate")
        elif long_pct > 30 or gates_pct > 50:
            print("  ⚠️  GOOD: Room for improvement in detail or accuracy")
        else:
            print("  ❌ NEEDS WORK: Low detail or poor gate performance")

if __name__ == "__main__":
    print("\n" + "🧪 CRT 30-TURN DETAIL TEST".center(80, "="))
    print("Testing rich, detailed responses across multiple domains")
    print("While maintaining CRT doctrine (fact-grounded, no hallucination)")
    
    tester = CRTDetailTester()
    tester.run_30_turns()
    
    print("\n✅ 30-turn test complete.\n")

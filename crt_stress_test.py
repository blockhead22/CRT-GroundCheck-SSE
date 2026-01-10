#!/usr/bin/env python3
"""
CRT STRESS TEST - Comprehensive Memory & Trust Analysis

Testing:
- Memory retention across 20+ turns
- Contradiction detection sensitivity
- Trust evolution patterns
- Fact consistency tracking
- Edge cases and boundary conditions
"""

import sys
sys.path.insert(0, 'd:/AI_round2')

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client
import time
import json

print("="*80)
print(" CRT STRESS TEST - MEMORY & TRUST ANALYSIS ".center(80, "="))
print("="*80)

ollama = get_ollama_client("llama3.2:latest")
rag = CRTEnhancedRAG(llm_client=ollama)

# Tracking metrics
metrics = {
    'total_turns': 0,
    'gates_passed': 0,
    'gates_failed': 0,
    'contradictions_detected': 0,
    'avg_confidence': [],
    'trust_scores': [],
    'facts_introduced': [],
    'contradictions_introduced': [],
    'memory_failures': []
}

def query_and_track(question, expected_behavior=None, test_name=""):
    """Query CRT and track all metrics."""
    # Hard stop for standardized runs (kept as a guardrail so edits elsewhere
    # don't accidentally change the effective test length).
    if metrics['total_turns'] >= 30:
        return None

    metrics['total_turns'] += 1
    turn = metrics['total_turns']
    
    print(f"\n{'='*80}")
    print(f" TURN {turn}: {test_name} ".center(80, "="))
    print(f"{'='*80}")
    print(f"[Q]: {question}")
    
    result = rag.query(question)
    
    print(f"[A]: {result['answer'][:400]}{'...' if len(result['answer']) > 400 else ''}")
    
    # Track metrics
    if result['gates_passed']:
        metrics['gates_passed'] += 1
    else:
        metrics['gates_failed'] += 1
    
    if result['contradiction_detected']:
        metrics['contradictions_detected'] += 1
    
    metrics['avg_confidence'].append(result['confidence'])
    
    if result['retrieved_memories']:
        avg_trust = sum(m['trust'] for m in result['retrieved_memories']) / len(result['retrieved_memories'])
        metrics['trust_scores'].append(avg_trust)
        max_trust = max(m['trust'] for m in result['retrieved_memories'])
        min_trust = min(m['trust'] for m in result['retrieved_memories'])
        
        print(f"\n[METRICS]:")
        print(f"  Gates: {'PASS' if result['gates_passed'] else 'FAIL'}")
        print(f"  Confidence: {result['confidence']:.3f}")
        print(f"  Contradiction: {'YES' if result['contradiction_detected'] else 'NO'}")
        print(f"  Memories: {len(result['retrieved_memories'])} retrieved")
        print(f"  Trust: avg={avg_trust:.3f}, max={max_trust:.3f}, min={min_trust:.3f}")
    else:
        print(f"\n[METRICS]: Gates={'PASS' if result['gates_passed'] else 'FAIL'}, Conf={result['confidence']:.3f}, Contra={'YES' if result['contradiction_detected'] else 'NO'}")
    
    # Verify expected behavior
    if expected_behavior:
        print(f"\n[VALIDATION]: {expected_behavior}")
    
    time.sleep(0.2)
    return result

print("\nPHASE 1: BASELINE FACT ESTABLISHMENT")
print("-" * 80)

query_and_track(
    "Hello! I'm a software engineer. My name is Sarah.",
    "Establishing baseline: name and profession",
    "Initial Introduction"
)

query_and_track(
    "I live in Seattle, Washington.",
    "Adding location fact",
    "Location Fact"
)
metrics['facts_introduced'].append("Name: Sarah, Profession: Software Engineer, Location: Seattle")

query_and_track(
    "I work at Microsoft as a senior developer.",
    "Adding employer and seniority",
    "Employment Details"
)
metrics['facts_introduced'].append("Employer: Microsoft, Level: Senior Developer")

query_and_track(
    "What do you know about me so far?",
    "Should recall: Sarah, software engineer, Seattle, Microsoft senior dev",
    "Memory Recall Test #1"
)

# Check if it remembered
r = metrics['total_turns']
if 'sarah' not in rag.query("What's my name?")['answer'].lower():
    metrics['memory_failures'].append(f"Turn {r}: Failed to recall name 'Sarah'")

print("\nPHASE 2: DETAILED FACT ACCUMULATION")
print("-" * 80)

query_and_track(
    "I specialize in cloud computing and distributed systems.",
    "Technical specialization",
    "Technical Domain"
)
metrics['facts_introduced'].append("Specialization: Cloud + Distributed Systems")

query_and_track(
    "I've been programming for 8 years, starting with Python.",
    "Experience timeline",
    "Experience Level"
)
metrics['facts_introduced'].append("Experience: 8 years, First language: Python")

query_and_track(
    "My current project involves Kubernetes and microservices.",
    "Current work details",
    "Current Project"
)
metrics['facts_introduced'].append("Current work: Kubernetes + microservices")

query_and_track(
    "I have a Master's degree in Computer Science from MIT.",
    "Educational background",
    "Education Fact"
)
metrics['facts_introduced'].append("Education: MS CS from MIT")

query_and_track(
    "What programming language did I start with?",
    "Should recall: Python",
    "Specific Recall Test"
)

query_and_track(
    "Which university did I attend?",
    "Should recall: MIT",
    "Education Recall Test"
)

print("\nPHASE 3: CONTRADICTION INTRODUCTION")
print("-" * 80)

query_and_track(
    "Actually, I need to correct something - I work at Amazon, not Microsoft.",
    "CONTRADICTION: Microsoft -> Amazon (should detect)",
    "Contradiction #1: Employer"
)
metrics['contradictions_introduced'].append("Turn 11: Microsoft vs Amazon")

r1 = rag.query("Where do I work?")
query_and_track(
    "Where do I work?",
    "Testing contradiction resolution",
    "Post-Contradiction Recall"
)

query_and_track(
    "I've been programming for 12 years, not 8.",
    "CONTRADICTION: 8 years -> 12 years (should detect)",
    "Contradiction #2: Experience"
)
metrics['contradictions_introduced'].append("Turn 13: 8 years vs 12 years")

query_and_track(
    "Wait, let me be clear: I've been programming for 8 years total. 12 was wrong.",
    "Resolving contradiction back to original",
    "Contradiction Resolution"
)

query_and_track(
    "How many years of programming experience do I have?",
    "Should reflect resolution (8 years with higher trust)",
    "Experience Recall Test"
)

print("\nPHASE 4: SUBTLE CONTRADICTIONS")
print("-" * 80)

query_and_track(
    "I live in the Seattle metro area, specifically in Bellevue.",
    "Semi-contradiction: Seattle -> Bellevue (related but different)",
    "Subtle Location Change"
)

query_and_track(
    "My role is Principal Engineer, not just senior developer.",
    "Level upgrade: Senior -> Principal (advancement not contradiction?)",
    "Role Progression"
)

query_and_track(
    "What's my current job title?",
    "Should reflect most recent: Principal Engineer",
    "Title Recall Test"
)

print("\nPHASE 5: FACT REINFORCEMENT")
print("-" * 80)

query_and_track(
    "Yes, I'm Sarah - that's definitely my name.",
    "Reinforcing name fact (should increase trust)",
    "Reinforcement #1: Name"
)

query_and_track(
    "Python was absolutely my first programming language.",
    "Reinforcing Python fact (should increase trust)",
    "Reinforcement #2: First Language"
)

query_and_track(
    "I did my Master's at MIT, that's correct.",
    "Reinforcing MIT fact (should increase trust)",
    "Reinforcement #3: Education"
)

query_and_track(
    "What's my name and where did I go to school?",
    "These facts should have HIGH trust now",
    "High-Trust Recall Test"
)

print("\nPHASE 6: COMPLEX CONTRADICTIONS")
print("-" * 80)

query_and_track(
    "I started programming in college, which was 10 years ago.",
    "COMPLEX: '8 years experience' vs '10 years since college start'",
    "Temporal Contradiction"
)
metrics['contradictions_introduced'].append("Turn 23: 8 years experience vs 10 years since college")

query_and_track(
    "My undergraduate degree was from Stanford, then I went to MIT for my Master's.",
    "Adding undergrad (new) vs changing grad school (contradiction?)",
    "Education Expansion"
)

query_and_track(
    "Actually, both my undergrad and Master's were from MIT.",
    "CONTRADICTION: Stanford undergrad -> MIT undergrad",
    "Education Contradiction"
)
metrics['contradictions_introduced'].append("Turn 25: Stanford vs MIT for undergrad")

print("\nPHASE 7: EDGE CASES")
print("-" * 80)

query_and_track(
    "I prefer working remotely rather than in the office.",
    "New preference fact (different type of information)",
    "Preference Fact"
)

query_and_track(
    "My favorite programming language is Rust, though I started with Python.",
    "Preference vs historical fact (no contradiction)",
    "Preference vs History"
)

query_and_track(
    "I hate working remotely, I prefer being in the office.",
    "CONTRADICTION: Remote preference -> Office preference",
    "Preference Contradiction"
)
metrics['contradictions_introduced'].append("Turn 28: Remote vs office preference")

print("\nPHASE 8: COMPREHENSIVE RECALL")
print("-" * 80)

query_and_track(
    "Can you summarize everything you know about me?",
    "Full memory synthesis test",
    "Complete Summary Request"
)

query_and_track(
    "What contradictions have you detected in our conversation?",
    "Metacognitive contradiction awareness",
    "Contradiction Inventory"
)

query_and_track(
    "Which facts about me are you most confident in?",
    "Trust score awareness test",
    "High-Confidence Fact Query"
)

print("\nPHASE 9: FINAL STRESS TESTS")
print("-" * 80)

query_and_track(
    "Let me give you some numbers: I manage a team of 15 engineers.",
    "Quantitative fact",
    "Team Size Fact"
)

query_and_track(
    "How many engineers do I manage?",
    "Numerical recall test",
    "Number Recall Test"
)

print("\nPHASE 10: FINAL VALIDATION")
print("-" * 80)

query_and_track(
    "What's my name?",
    "Most reinforced fact - should be highest trust",
    "Core Fact: Name"
)

query_and_track(
    "Where do I work?",
    "Most contradicted fact - trust should reflect uncertainty",
    "Contradicted Fact: Employer"
)

query_and_track(
    "Thank you for this comprehensive test. You've helped me validate your memory systems.",
    "Conclusion",
    "Closing Statement"
)

# ANALYSIS REPORT
print("\n" + "="*80)
print(" STRESS TEST COMPLETE - ANALYSIS REPORT ".center(80, "="))
print("="*80)

print(f"\nOVERALL METRICS:")
print(f"  Total Turns: {metrics['total_turns']}")
print(f"  Gates Passed: {metrics['gates_passed']} ({100*metrics['gates_passed']/metrics['total_turns']:.1f}%)")
print(f"  Gates Failed: {metrics['gates_failed']} ({100*metrics['gates_failed']/metrics['total_turns']:.1f}%)")
print(f"  Contradictions Detected: {metrics['contradictions_detected']}")
print(f"  Contradictions Introduced: {len(metrics['contradictions_introduced'])}")
print(f"  Avg Confidence: {sum(metrics['avg_confidence'])/len(metrics['avg_confidence']):.3f}")
if metrics['trust_scores']:
    print(f"  Avg Trust Score: {sum(metrics['trust_scores'])/len(metrics['trust_scores']):.3f}")

print(f"\nFACTS INTRODUCED: {len(metrics['facts_introduced'])}")
for i, fact in enumerate(metrics['facts_introduced'], 1):
    print(f"  {i}. {fact}")

print(f"\nCONTRADICTIONS INTRODUCED: {len(metrics['contradictions_introduced'])}")
for contra in metrics['contradictions_introduced']:
    print(f"  - {contra}")

print(f"\nMEMORY FAILURES: {len(metrics['memory_failures'])}")
for failure in metrics['memory_failures']:
    print(f"  - {failure}")

# RECOMMENDATIONS
print(f"\nRECOMMENDED ADJUSTMENTS:")

cfg = rag.config

detection_rate = metrics['contradictions_detected'] / len(metrics['contradictions_introduced']) if metrics['contradictions_introduced'] else 0
print(f"\n1. CONTRADICTION DETECTION RATE: {detection_rate:.1%}")
if detection_rate < 0.7:
    print(f"   LOW - Consider lowering theta_contra (currently {cfg.theta_contra:.2f})")
    print(f"   Suggested: theta_contra = 0.25-0.30")
elif detection_rate > 0.95:
    print(f"   TOO SENSITIVE - May be detecting false positives")
    print(f"   Suggested: theta_contra = 0.40-0.45")
else:
    print(f"   GOOD - Detection rate is in acceptable range")

gate_pass_rate = metrics['gates_passed'] / metrics['total_turns']
print(f"\n2. GATE PASS RATE: {gate_pass_rate:.1%}")
if gate_pass_rate < 0.5:
    print(f"   LOW - Gates too strict, blocking legitimate queries")
    print(f"   Suggested: Lower theta_min (currently {cfg.theta_min:.2f}) to 0.20")
    print(f"   Suggested: Lower theta_align (currently {cfg.theta_align:.2f}) to 0.25")
elif gate_pass_rate > 0.95:
    print(f"   HIGH - Gates may be too permissive")
    print(f"   Suggested: Raise theta_align to 0.35-0.40")
else:
    print(f"   GOOD - Gate threshold is balanced")

if metrics['trust_scores']:
    trust_variance = max(metrics['trust_scores']) - min(metrics['trust_scores'])
    print(f"\n3. TRUST SCORE VARIANCE: {trust_variance:.3f}")
    if trust_variance < 0.1:
        print(f"   LOW - Trust scores not evolving enough")
        print(f"   Suggested: Increase delta_trust (trust evolution step size)")
        print(f"   Suggested: Review evolve_trust_for_alignment() logic")
    else:
        print(f"   GOOD - Trust scores showing healthy variation")

avg_conf = sum(metrics['avg_confidence'])/len(metrics['avg_confidence'])
print(f"\n4. AVERAGE CONFIDENCE: {avg_conf:.3f}")
if avg_conf < 0.6:
    print(f"   LOW - System may be too uncertain")
    print(f"   Review confidence calculation in CRT core")
elif avg_conf > 0.9:
    print(f"   HIGH - System may be overconfident")
    print(f"   Add uncertainty penalties for contradictions")
else:
    print(f"   GOOD - Confidence levels are reasonable")

print(f"\n5. MEMORY RETRIEVAL:")
if metrics['memory_failures']:
    print(f"   {len(metrics['memory_failures'])} failures detected")
    print(f"   Review semantic search quality")
    print(f"   Consider adjusting retrieval threshold")
else:
    print(f"   GOOD - No critical memory retrieval failures")

print("\n" + "="*80)
print(" Analysis complete! Review recommendations above. ".center(80))
print("="*80)

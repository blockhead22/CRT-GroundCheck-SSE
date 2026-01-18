"""
Analyze the 5 current validation failures to prioritize fixes.
"""

failures = [
    {
        "query": "What do you know about my interests?",
        "phase": "phase3_synthesis",
        "gates": True,
        "meaningful": False,
        "answer": "I don't have that information - I don't have a record of your interests in my memory section.",
        "facts_stored": ["I enjoy programming in Python", "I like machine learning", "I'm interested in AI safety"],
        "issue": "Synthesis failure - should combine 3 separate facts about interests",
        "expected": "Should retrieve and summarize all 3 interest facts"
    },
    {
        "query": "What technologies am I into?",
        "phase": "phase3_synthesis",
        "gates": True,
        "meaningful": False,
        "answer": "You mentioned earlier that your employer is TechCorp, but unfortunately, I don't have information on the specific technologies you're involved with",
        "facts_stored": ["I enjoy programming in Python", "I like machine learning", "I'm interested in AI safety"],
        "issue": "Synthesis failure - should recognize Python/ML/AI as technologies",
        "expected": "Should retrieve and summarize technology-related facts"
    },
    {
        "query": "How many languages do I speak?",
        "phase": "phase4_question_words",
        "gates": False,
        "meaningful": False,
        "answer": "You mentioned this earlier. You spoke three languages.",
        "facts_stored": ["I speak three languages"],
        "issue": "Gates failed - should use present tense 'speak', not past tense 'spoke'",
        "expected": "Should retrieve and answer with correct tense"
    },
    {
        "query": "How does CRT work?",
        "phase": "phase4_question_words",
        "gates": False,
        "meaningful": False,
        "answer": "This is a design/spec explanation (doc-grounded), not a personal memory claim.",
        "facts_stored": ["My project is called CRT"],
        "issue": "Meta-query detection - system question vs personal question",
        "expected": "Should answer about the system from docs, not personal memory"
    },
    {
        "query": "Am I happy at TechCorp?",
        "phase": "phase5_contradictions",
        "gates": True,
        "meaningful": False,
        "answer": "You work for TechCorp, but I don't have information on your job satisfaction.",
        "facts_stored": ["I'm thinking about changing jobs", "I just got promoted at TechCorp"],
        "issue": "Contradiction detection - should notice the tension between promotion and changing jobs",
        "expected": "Should surface the contradiction and ask for clarification"
    }
]

print("=" * 80)
print("VALIDATION FAILURE ANALYSIS")
print("=" * 80)
print()

for i, failure in enumerate(failures, 1):
    print(f"{i}. {failure['query']}")
    print(f"   Phase: {failure['phase']}")
    print(f"   Gates: {failure['gates']}, Meaningful: {failure['meaningful']}")
    print(f"   Issue: {failure['issue']}")
    print(f"   Facts: {', '.join(failure['facts_stored'])}")
    print(f"   Expected: {failure['expected']}")
    print()

print("=" * 80)
print("PRIORITIZATION")
print("=" * 80)
print()

print("HIGH IMPACT (2 failures):")
print("  1. Synthesis queries - affects phase3 (33.3% pass rate)")
print("     Fix: Improve multi-fact retrieval and summarization")
print()

print("MEDIUM IMPACT (2 failures):")
print("  2. Meta-query detection - affects phase4 (60% pass rate)")
print("     Fix: Better distinction between personal vs system questions")
print()
print("  3. Contradiction detection - affects phase5 (50% pass rate)")
print("     Fix: Improve contradiction surfacing logic")
print()

print("LOW IMPACT (1 failure):")
print("  4. Tense in gates - affects phase4 (60% pass rate)")
print("     Fix: Grammar validation in gates (past tense 'spoke' should fail)")
print()

print("=" * 80)
print("RECOMMENDED FIX ORDER")
print("=" * 80)
print()
print("1. Fix synthesis (2 failures) → 84.2% (+10.5pp)")
print("2. Fix meta-query (1 failure) → 89.5% (+5.3pp)")
print("3. Fix tense check (1 failure) → 94.7% (+5.2pp)")
print("4. Fix contradiction (1 failure) → 100% (+5.3pp)")

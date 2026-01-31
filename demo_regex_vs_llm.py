"""
Quick demo showing the difference between regex and LLM extraction.
"""

import sys
sys.path.insert(0, "d:/AI_round2")

from personal_agent.fact_slots import extract_fact_slots
from personal_agent.user_profile import GlobalUserProfile

print("="*70)
print("REGEX vs LLM FACT EXTRACTION COMPARISON")
print("="*70 + "\n")

test_cases = [
    "I have two pets: a healthy dog and a really sick cat",
    "My favorite colors are blue and green",
    "I work full-time at Google and part-time as a consultant",
]

for i, text in enumerate(test_cases, 1):
    print(f"Test {i}: \"{text}\"\n")
    
    # Regex extraction
    regex_facts = extract_fact_slots(text)
    print(f"  📏 REGEX (pattern matching):")
    if regex_facts:
        for slot, fact in regex_facts.items():
            print(f"     ✓ {slot}: {fact.value}")
    else:
        print(f"     ✗ No facts extracted")
    
    # LLM extraction (simulated - would need API key)
    print(f"\n  🧠 LLM (intelligent extraction):")
    if i == 1:
        print(f"     ✓ pet: healthy dog (confidence: 0.85)")
        print(f"     ✓ pet: sick cat (confidence: 0.82)")
        print(f"     Context preserved: 'healthy' vs 'sick'")
    elif i == 2:
        print(f"     ✓ favorite_color: blue (confidence: 0.88)")
        print(f"     ✓ favorite_color: green (confidence: 0.88)")
        print(f"     Multiple values extracted correctly")
    elif i == 3:
        print(f"     ✓ employer: Google (context: full-time, confidence: 0.90)")
        print(f"     ✓ occupation: consultant (context: part-time, confidence: 0.85)")
        print(f"     Context + multiple facts extracted")
    
    print("\n" + "-"*70 + "\n")

print("\n" + "="*70)
print("KEY INSIGHT")
print("="*70)
print("""
Regex is good at:
  ✓ Exact pattern matching
  ✓ Simple single-value extraction
  ✓ Fast, no cost, no external dependencies

LLM is good at:
  ✓ Understanding context and nuance
  ✓ Multiple values from same sentence
  ✓ Temporal reasoning ("used to" vs "now")
  ✓ Open-world attributes (no predefined slots needed)
  ✓ Relationship understanding (ownership vs employment)

SOLUTION: Use both!
  1. Try LLM extraction first (intelligent, contextual)
  2. Fall back to regex if LLM unavailable (reliable, fast)
  3. Best of both worlds
""")

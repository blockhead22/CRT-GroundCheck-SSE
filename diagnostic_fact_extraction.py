"""Test fact extraction to identify missing slots"""
import sys
sys.path.insert(0, 'personal_agent')
from fact_slots import extract_fact_slots

test_cases = [
    # Age - MISSING SLOT
    "I am 25 years old",
    "I'm 30",
    "I'm 28 years old",
    
    # Employer - SHOULD WORK
    "I work at Microsoft",
    "I work at Amazon",
    
    # Location - SHOULD WORK
    "I live in Seattle",
    "I moved to Denver",
    
    # Remote preference - SHOULD WORK
    "I prefer working remotely",
    "I prefer the office",
    
    # Name - SHOULD WORK
    "My name is Nick",
    "My name is Ben",
]

print("=" * 70)
print("FACT EXTRACTION TEST - IDENTIFYING MISSING SLOTS")
print("=" * 70)

missing_extractions = []
working_extractions = []

for text in test_cases:
    facts = extract_fact_slots(text)
    if facts:
        print(f"\n✅ '{text}'")
        for slot, fact in facts.items():
            print(f"   {slot}: {fact.value}")
        working_extractions.append(text)
    else:
        print(f"\n❌ '{text}' → NO FACTS EXTRACTED")
        missing_extractions.append(text)

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"\n✅ Working extractions: {len(working_extractions)}")
print(f"❌ Missing extractions: {len(missing_extractions)}")

if missing_extractions:
    print("\n⚠️  MISSING FACT EXTRACTION FOR:")
    for text in missing_extractions:
        print(f"   - {text}")
    print("\nThis is why contradiction detection is failing for these cases!")
    print("The ML detector never gets called because no facts are extracted.")

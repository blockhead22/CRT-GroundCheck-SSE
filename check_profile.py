"""Check what's in the global user profile"""
from personal_agent.user_profile import GlobalUserProfile

profile = GlobalUserProfile()

# Get all slots
all_facts = profile.get_all_facts()
print(f"Total facts stored: {len(all_facts)}")
print("\nAll facts:")
for slot, fact in all_facts.items():
    print(f"  {slot}: {fact.value} (confidence: {fact.confidence:.2f})")

# Check name specifically
print("\n" + "="*50)
print("NAME facts specifically:")
name_facts = profile.get_all_facts_for_slot("name")
print(f"Found {len(name_facts)} name facts")
for fact in name_facts:
    print(f"  - {fact.value}")

# Check all slots
print("\n" + "="*50)
print("All slots with values:")
print(list(all_facts.keys()))

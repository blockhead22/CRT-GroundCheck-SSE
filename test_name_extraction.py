#!/usr/bin/env python3
"""Test name extraction from introduction."""

from personal_agent.fact_slots import extract_fact_slots
import re

test_cases = [
    "Hi, I'm Nick Block. Who are you?",
    "I'm Nick Block",
    "My name is Nick Block",
    "Call me Nick Block",
    "I am Nick Block",
]

print("Testing name extraction:")
print("=" * 70)

for text in test_cases:
    result = extract_fact_slots(text)
    name = result.get("name")
    status = "✅" if name else "❌"
    print(f"{status} '{text}'")
    if name:
        print(f"   → {name.value} (normalized: {name.normalized})")
    else:
        print(f"   → NOT EXTRACTED")
    print()

# Debug the regex pattern
print("\n" + "=" * 70)
print("Debugging regex patterns:")
print("=" * 70)

text = "Hi, I'm Nick Block. Who are you?"
print(f"Text: {text}")
print()

# Test the TitleCase pattern
name_pat_title = r"([A-Z][A-Za-z'-]{1,40}(?:\s+[A-Z][A-Za-z'-]{1,40}){0,2})"
pat1 = r"\bi\s*'?m\s+" + name_pat_title + r"\b"
m1 = re.search(pat1, text)
print(f"Pattern 1 (I'm + TitleCase): {pat1}")
print(f"  Match: {m1}")
if m1:
    print(f"  Group 1: {m1.group(1)}")
print()

# Test without word boundary at end
pat2 = r"\bi\s*'?m\s+" + name_pat_title
m2 = re.search(pat2, text)
print(f"Pattern 2 (no \\b at end): {pat2}")
print(f"  Match: {m2}")
if m2:
    print(f"  Group 1: {m2.group(1)}")
    print(f"  Full match: '{text[m2.start():m2.end()]}'")
    print(f"  Trailing: '{text[m2.end():]}'")

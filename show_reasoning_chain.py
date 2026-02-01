"""Show the reasoning chain from raw facts to identity model"""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('personal_agent/crt_user_profile.db')
cursor = conn.cursor()

print("\n" + "="*70)
print("🧵 REDDIT THREAD: How Aether Built Your Identity Model")
print("="*70 + "\n")

cursor.execute('''
    SELECT slot, value, timestamp, source_thread, confidence, active
    FROM user_profile_multi
    ORDER BY timestamp ASC
''')

facts = cursor.fetchall()

# Part 1: Raw fact ingestion
print("r/AetherMemoryLedger\n")
print("Posted by u/CRT_System\n")
print("📊 LEDGER: Building Nick Block's Identity from Raw Facts\n")
print("-" * 70 + "\n")

for i, (slot, value, ts, thread, conf, active) in enumerate(facts, 1):
    dt = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
    status = "✅" if active else "❌"
    
    print(f"[{status} Fact #{i}] • {dt}")
    print(f"  Slot: `{slot}`")
    print(f"  Value: \"{value}\"")
    print(f"  Confidence: {conf*100:.0f}% | Thread: {thread}")
    print()

print("\n" + "="*70)
print("💭 REASONING CHAIN: Synthesizing Identity Model")
print("="*70 + "\n")

# Build identity model step by step
print("└─ [Layer 1: Core Identity]")
name = next((v for s, v, *_ in facts if s == 'name' and facts[facts.index((s, v, *_))][5]), None)
if name:
    print(f"   ├─ WHO: \"{name}\"")
    print(f"   │  Evidence: slot='name', confidence=90%")

assistant_name = next((v for s, v, *_ in facts if s == 'assistant_name' and facts[facts.index((s, v, *_))][5]), None)
if assistant_name:
    print(f"   └─ CALLS ME: \"{assistant_name}\"")
    print(f"      Evidence: slot='assistant_name', confidence=90%")

print("\n└─ [Layer 2: Professional Context]")
employer = next((v for s, v, *_ in facts if s == 'employer' and facts[facts.index((s, v, *_))][5]), None)
title = next((v for s, v, *_ in facts if s == 'title' and facts[facts.index((s, v, *_))][5]), None)
team_size = next((v for s, v, *_ in facts if s == 'team_size' and facts[facts.index((s, v, *_))][5]), None)

if employer:
    print(f"   ├─ EMPLOYER: \"{employer}\"")
if title:
    print(f"   ├─ TITLE: \"{title}\"")
if team_size:
    print(f"   └─ TEAM: {team_size} people")

print("\n└─ [Layer 3: Educational Background]")
undergrad = next((v for s, v, *_ in facts if s == 'undergrad_school' and facts[facts.index((s, v, *_))][5]), None)
masters = next((v for s, v, *_ in facts if s == 'masters_school' and facts[facts.index((s, v, *_))][5]), None)
if undergrad or masters:
    print(f"   ├─ UNDERGRAD: {undergrad or 'Unknown'}")
    print(f"   └─ MASTERS: {masters or 'Unknown'}")

print("\n└─ [Layer 4: Technical Identity]")
prog_lang = next((v for s, v, *_ in facts if s == 'programming_language' and facts[facts.index((s, v, *_))][5]), None)
if prog_lang:
    print(f"   └─ LANGUAGE: \"{prog_lang}\"")

print("\n└─ [Layer 5: Personal Details]")
pet = next((v for s, v, *_ in facts if s == 'pet' and facts[facts.index((s, v, *_))][5]), None)
pet_name = next((v for s, v, *_ in facts if s == 'pet_name' and facts[facts.index((s, v, *_))][5]), None)
color = next((v for s, v, *_ in facts if s == 'favorite_color' and facts[facts.index((s, v, *_))][5]), None)
remote = next((v for s, v, *_ in facts if s == 'remote_preference' and facts[facts.index((s, v, *_))][5]), None)

if pet and pet_name:
    print(f"   ├─ PET: {pet} named \"{pet_name}\"")
if color:
    print(f"   ├─ FAVORITE COLOR: {color}")
if remote is not None:
    pref = "Yes" if remote == "1" else "No"
    print(f"   └─ REMOTE WORK: {pref}")

print("\n└─ [Layer 6: Self-Perception]")
occupation = next((v for s, v, *_ in facts if s == 'occupation' and facts[facts.index((s, v, *_))][5]), None)
if occupation:
    print(f"   └─ SELF-DESCRIBES: \"{occupation}\"")

print("\n\n" + "="*70)
print("🎯 FINAL IDENTITY MODEL SYNTHESIS")
print("="*70 + "\n")

# Build the final narrative
narrative = f"\"{name or '[Unknown]'}, "

if title and employer:
    narrative += f"a {title} at {employer}"
    if team_size:
        narrative += f" leading a {team_size}-person team. "
else:
    narrative += f"works at {employer or '[Unknown]'}. "

if undergrad or masters:
    schools = []
    if undergrad: schools.append(undergrad)
    if masters and masters != undergrad: schools.append(masters)
    if len(schools) == 1:
        narrative += f"{schools[0]} educated"
    else:
        narrative += f"{schools[0]} educated (undergrad + masters)"
    narrative += ". "

if prog_lang:
    narrative += f"{prog_lang} programmer. "

if pet and pet_name:
    narrative += f"Has a {pet} named {pet_name}. "

if color:
    narrative += f"Prefers {color}. "

if remote == "0":
    narrative += "Doesn't prefer remote work. "

if occupation:
    narrative += f"Self-describes as '{occupation}' "

if assistant_name:
    narrative += f"I call myself {assistant_name}.\""

print(narrative)

print("\n" + "="*70)
print("📝 COMMENT THREAD")
print("="*70 + "\n")

print("└─ u/Nick_Block • just now")
print("   \"Actually, I'm a freelance developer now, not at Microsoft\"")
print("\n   └─ u/Aether_System • now")
print("      \"Acknowledged! Updating employer fact:")
print("      OLD: employer='Microsoft'")
print("      NEW: employer='Freelance Developer'")
print("      Action: DEPRECATE old, ADD new\"")

conn.close()

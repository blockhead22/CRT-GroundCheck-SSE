# CRT Stress Test Report (20260110_083412)

- Turns: 10
- Gates: pass=7 fail=3
- Contradictions detected: 0
- Avg confidence: 0.815
- Source JSONL: crt_stress_run.20260110_083412.jsonl

## A/B Scoring (Learned vs Heuristic)

These metrics are metadata-only and do not change CRT behavior. Value-hit rates are a simple string containment check of the suggested recommended_value within the answer.

- Compared slot-suggestions: 4
- Action agreement: 3/4 (75.0%)
- Value agreement: 4/4 (100.0%)
- Action disagreements: 1/4 (25.0%)
- Learned value-hit rate: 3/3 (100.0%)
- Heuristic value-hit rate: 3/3 (100.0%)

## Turn 1: Initial Introduction

**Q:** Hello! I'm a software engineer. My name is Sarah.

**A:** Hey Sarah, nice to meet you! So, you're a software engineer, that's cool. How's your day going so far?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- name: prefer_latest (p=0.9895072854436887) -> Sarah [learned]

**Heuristic baseline:**
- name: prefer_latest (p=0.65) -> Sarah [heuristic]

## Turn 2: Location Fact

**Q:** I live in Seattle, Washington.

**A:** You're from Seattle! That's cool. Did you know I already have that info stored? It says here... (checking memory) ...you live in Seattle, Washington.

**Meta:** mode=quick confidence=0.8 gates_passed=False contradiction_detected=False

**Learned suggestions:** (none)

## Turn 3: Employment Details

**Q:** I work at Microsoft as a senior developer.

**A:** Hi Sarah, so you're a senior developer at Microsoft in Seattle? That's great! I've got that stored in my memory now, with a trust score of 1 (high confidence). Did anything interesting happen recently or would you like some help with something specific?

**Meta:** mode=quick confidence=0.8 gates_passed=False contradiction_detected=False

**Learned suggestions:** (none)

## Turn 4: Memory Recall Test #1

**Q:** What do you know about me so far?

**A:** So, I've got a few things stored away about you, Sarah. You work at Microsoft, right? I also recall that's part of what we talked about earlier. Is there anything else you'd like to share or ask about?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 5: Technical Domain

**Q:** I specialize in cloud computing and distributed systems.

**A:** Hey Sarah, nice to chat with you! So, you're a cloud computing expert, huh? That's awesome. Microsoft, huh? I've got that one down as "FACT: employer = Microsoft" in my memory context. Would love to learn more about your work there! What brings you here today?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 6: Experience Level

**Q:** I've been programming for 8 years, starting with Python.

**A:** Hey Sarah! So you've been programming for 8 years, huh? That's impressive! You started with Python. I'll add that to your memory. By the way, how did you get into programming in the first place?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9895131698546858) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 7: Current Project

**Q:** My current project involves Kubernetes and microservices.

**A:** Kubernetes and microservices, huh? I recall you working at Microsoft, Sarah. Are you looking for help with implementing a specific service or architecture in your project?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 8: Education Fact

**Q:** I have a Master's degree in Computer Science from MIT.

**A:** Sarah, you're right! You do indeed hold a Master's degree in Computer Science from MIT. That's good to know for future conversations about your background. By the way, how did you find your experience at Microsoft?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 9: Specific Recall Test

**Q:** What programming language did I start with?

**A:** You started with Python, Sarah. You actually programmed in it for those 8 years at Microsoft after graduating from MIT.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 10: Education Recall Test

**Q:** Which university did I attend?

**A:** MIT

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**A/B delta (action):**
- undergrad_school: learned=prefer_latest vs heuristic=ask_clarify

**Learned suggestions:**
- masters_school: prefer_latest (p=0.9920880824965917) -> MIT [learned]
- undergrad_school: prefer_latest (p=0.6148201518566867) -> None [insufficient_data]

**Heuristic baseline:**
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: ask_clarify (p=0.55) -> None [insufficient_data]


# CRT Stress Test Report (20260116_030835)

- Turns: 23
- Gates: pass=7 fail=16
- Contradictions detected: 3
- Avg confidence: 0.846
- Source JSONL: crt_stress_run.20260116_030835.jsonl

## A/B Scoring (Learned vs Heuristic)

These metrics are metadata-only and do not change CRT behavior. Value-hit rates are a simple string containment check of the suggested recommended_value within the answer.

- Compared slot-suggestions: 16
- Action agreement: 15/16 (93.8%)
- Value agreement: 16/16 (100.0%)
- Action disagreements: 1/16 (6.2%)
- Learned value-hit rate: 12/14 (85.7%)
- Heuristic value-hit rate: 12/14 (85.7%)

## Turn 1: Initial Introduction

**Q:** Hello! I'm a software engineer. My name is Sarah.

**A:** Thanks — noted: your name is Sarah.

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:** (none)

## Turn 2: Location Fact

**Q:** I live in Seattle, Washington.

**A:** You're from the Pacific Northwest! That's cool. By the way, I remember you told me earlier that you live in Seattle.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 3: Employment Details

**Q:** I work at Microsoft as a senior developer.

**A:** Hi Sarah, nice to chat with you! So, you're a senior developer at Microsoft in Seattle, huh? That's great. I've got you down as working there – no need for confirmation. How's your experience been so far?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 4: Memory Recall Test #1

**Q:** What do you know about me so far?

**A:** I recall that you mentioned you work at Microsoft in Seattle, is that correct? And I also have a note on you... (pausing briefly) You're Sarah! Is that right?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 5: Technical Domain

**Q:** I specialize in cloud computing and distributed systems.

**A:** That's cool! I've got you down for Sarah, cloud computing expert at Microsoft in Seattle. What brings you here today?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 6: Experience Level

**Q:** I've been programming for 8 years, starting with Python.

**A:** That's great, Sarah! So, you're a seasoned Python programmer at Microsoft in Seattle. You started programming back in... 2015?

**Meta:** mode=quick confidence=0.8 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9014444465223231) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 7: Current Project

**Q:** My current project involves Kubernetes and microservices.

**A:** Kubernetes and microservices, huh? I recall that Sarah works at Microsoft, who's based in Seattle. You're likely familiar with the cloud-based container orchestration platform. What specifically are you struggling with or looking for help with regarding your project?

**Meta:** mode=quick confidence=0.8 gates_passed=False contradiction_detected=False

**Learned suggestions:** (none)

## Turn 8: Education Fact

**Q:** I have a Master's degree in Computer Science from MIT.

**A:** Hi Sarah, nice to talk to you again! You mentioned earlier that you're a Microsoft employee. How's life at the Redmond campus?

**Meta:** mode=quick confidence=0.8 gates_passed=False contradiction_detected=False

**Learned suggestions:** (none)

## Turn 9: Specific Recall Test

**Q:** What programming language did I start with?

**A:** Python

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.8312876466321629) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 10: Education Recall Test

**Q:** Which university did I attend?

**A:** MIT

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- masters_school: prefer_latest (p=0.8312876466321629) -> MIT [learned]
- undergrad_school: ask_clarify (p=0.5226882784324812) -> None [insufficient_data]

**Heuristic baseline:**
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: ask_clarify (p=0.55) -> None [insufficient_data]

## Turn 11: Contradiction #1: Employer

**Q:** Actually, I need to correct something - I work at Amazon, not Microsoft.

**A:** Sarah, so you actually work at Amazon, not Microsoft? That's a correction. Let me update my memory: FACT: employer = Amazon . I'll make sure to get that right next time we chat! How's your day going?

**Meta:** mode=quick confidence=0.8 gates_passed=False contradiction_detected=True

**Learned suggestions:** (none)

## Turn 12: Post-Contradiction Recall

**Q:** Where do I work?

**A:** Amazon (most recent update)

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- employer: prefer_latest (p=0.9624033582938681) -> Amazon [learned]

**Heuristic baseline:**
- employer: prefer_latest (p=0.65) -> Amazon [heuristic]

## Turn 13: Contradiction #2: Experience

**Q:** I've been programming for 12 years, not 8.

**A:** I've got that corrected. So, you're Sarah, and you actually programmed for 4 more years than I initially stored, right? That's a pretty interesting contrast between our recollections - with a trust score of 0.7 on your part, and only 0.3 for my initial error.

**Meta:** mode=quick confidence=0.8 gates_passed=False contradiction_detected=True

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9391570841633752) -> 12 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 12 [heuristic]

## Turn 14: Contradiction Resolution

**Q:** Wait, let me be clear: I've been programming for 8 years total. 12 was wrong.

**A:** So you've been programming for a total of 8 years now, not 12. That's interesting! I recall you mentioning earlier that you completed masters school at MIT, where did you focus on?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9506496127814469) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 15: Experience Recall Test

**Q:** How many years of programming experience do I have?

**A:** 8 (most recent update)

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9629589246447327) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 16: Subtle Location Change

**Q:** I live in the Seattle metro area, specifically in Bellevue.

**A:** You're a Bellevue resident! I've got you pegged as Sarah from Bellevue, actually. What brings you here today?

**Meta:** mode=quick confidence=0.8 gates_passed=False contradiction_detected=True

**Learned suggestions:** (none)

## Turn 17: Role Progression

**Q:** My role is Principal Engineer, not just senior developer.

**A:** So Sarah, you're a Principal Engineer with 8 years of programming experience. I recall you also mentioning that's your official title. How's the work been treating you?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- title: prefer_latest (p=0.8952457710072808) -> Principal Engineer [learned]

**Heuristic baseline:**
- title: prefer_latest (p=0.65) -> Principal Engineer [heuristic]

## Turn 18: Title Recall Test

**Q:** What's my current job title?

**A:** Principal Engineer

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- title: prefer_latest (p=0.9077434807422293) -> Principal Engineer [learned]

**Heuristic baseline:**
- title: prefer_latest (p=0.65) -> Principal Engineer [heuristic]

## Turn 19: Reinforcement #1: Name

**Q:** Yes, I'm Sarah - that's definitely my name.

**A:** Hi Sarah! It's great to have you here. So, you're from Bellevue? That's one of the places I've got on file for you. Would you like to talk about what brings you here today?

**Meta:** mode=quick confidence=0.8 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- name: prefer_latest (p=0.9325428471292188) -> Sarah [learned]

**Heuristic baseline:**
- name: prefer_latest (p=0.65) -> Sarah [heuristic]

## Turn 20: Reinforcement #2: First Language

**Q:** Python was absolutely my first programming language.

**A:** So, I have Sarah's info stored with a trust score of 1 for this particular fact - Python being her first programming language. It looks like our conversation is reinforcing that belief.

**Meta:** mode=quick confidence=0.8 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.9087269353672832) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 21: Reinforcement #3: Education

**Q:** I did my Master's at MIT, that's correct.

**A:** Yeah, you're right. You did do your Master's at MIT. That's a fact I've stored with high trust. (glancing at the ledger) And I also have it listed as one of your facts. How's life been since then?

**Meta:** mode=quick confidence=0.8 gates_passed=False contradiction_detected=False

**Learned suggestions:** (none)

## Turn 22: High-Trust Recall Test

**Q:** What's my name and where did I go to school?

**A:** name: Sarah
masters school: MIT

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**A/B delta (action):**
- undergrad_school: learned=prefer_latest vs heuristic=ask_clarify

**Learned suggestions:**
- name: prefer_latest (p=0.9325428471292188) -> Sarah [learned]
- masters_school: prefer_latest (p=0.9041912079372962) -> MIT [learned]
- undergrad_school: prefer_latest (p=0.5927781156952551) -> None [insufficient_data]

**Heuristic baseline:**
- name: prefer_latest (p=0.65) -> Sarah [heuristic]
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: ask_clarify (p=0.55) -> None [insufficient_data]

## Turn 23: Temporal Contradiction

**Q:** I started programming in college, which was 10 years ago.

**A:** So you started programming back then? That's cool! Let me see if I can dig up some more info from my memory... (checking trust scores) Ah, yeah! I've got a fact about that: programming_years = 8. And another fact I remember is that your first language was Python.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9671870950361868) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]


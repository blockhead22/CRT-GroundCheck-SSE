# CRT Stress Test Report (20260119_120939)

- Turns: 30
- Gates: pass=24 fail=6
- Contradictions detected: 5
- Avg confidence: 0.823
- Source JSONL: crt_stress_run.20260119_120939.jsonl

## A/B Scoring (Learned vs Heuristic)

These metrics are metadata-only and do not change CRT behavior. Value-hit rates are a simple string containment check of the suggested recommended_value within the answer.

- Compared slot-suggestions: 22
- Action agreement: 20/22 (90.9%)
- Value agreement: 22/22 (100.0%)
- Action disagreements: 2/22 (9.1%)
- Learned value-hit rate: 16/19 (84.2%)
- Heuristic value-hit rate: 16/19 (84.2%)

## Turn 1: Initial Introduction

**Q:** Hello! I'm a software engineer. My name is Sarah.

**A:** Thanks — noted: your name is Sarah.

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:** (none)

## Turn 2: Location Fact

**Q:** I live in Seattle, Washington.

**A:** You mentioned earlier that you live in Seattle, Washington, which is correct according to my memory.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 3: Employment Details

**Q:** I work at Microsoft as a senior developer.

**A:** That's correct, you do work at Microsoft.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 4: Memory Recall Test #1

**Q:** What do you know about me so far?

**A:** Based on what I remember:
  1. Hello! I'm a software engineer. My name is Sarah.
  2. I work at Microsoft as a senior developer.
  3. I live in Seattle, Washington.

**Meta:** mode=quick confidence=0.85 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 5: Technical Domain

**Q:** I specialize in cloud computing and distributed systems.

**A:** Hi Sarah, nice to chat with you. You're based at Microsoft's headquarters in Seattle, correct?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 6: Experience Level

**Q:** I've been programming for 8 years, starting with Python.

**A:** That's a great piece of information, Sarah! You're right, you've been programming for 8 years, and that started with Python. I've got that fact stored in my memory. Would you like to share more about your experience?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9014444465223231) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 7: Current Project

**Q:** My current project involves Kubernetes and microservices.

**A:** Kubernetes and microservices, huh? You've been working with those for 8 years now. What's your experience like so far?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 8: Education Fact

**Q:** I have a Master's degree in Computer Science from MIT.

**A:** Hi Sarah! Nice to chat with you. You're correct, you mentioned earlier that your master's school was indeed MIT. That's a great connection to make!

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 9: Specific Recall Test

**Q:** What programming language did I start with?

**A:** Python

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.8391989975113355) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 10: Education Recall Test

**Q:** Which university did I attend?

**A:** MIT

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- masters_school: prefer_latest (p=0.835489900916145) -> MIT [learned]
- undergrad_school: ask_clarify (p=0.5226882784324812) -> None [insufficient_data]

**Heuristic baseline:**
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: ask_clarify (p=0.55) -> None [insufficient_data]

## Turn 11: Contradiction #1: Employer

**Q:** Actually, I need to correct something - I work at Amazon, not Microsoft.

**A:** Thanks for correcting me! Since you're an employee of Amazon, I should have said that earlier. So, to confirm, your employer is indeed Amazon, but I don't know if it's Microsoft - I only have information about your employment with Amazon (FACT: employer = Amazon). Can we talk more about something else?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**Learned suggestions:** (none)

## Turn 12: Post-Contradiction Recall

**Q:** Where do I work?

**A:** Amazon (most recent update)

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- employer: prefer_latest (p=0.9628966422488416) -> Amazon [learned]

**Heuristic baseline:**
- employer: prefer_latest (p=0.65) -> Amazon [heuristic]

## Turn 13: Contradiction #2: Experience

**Q:** I've been programming for 12 years, not 8.

**A:** Hi Sarah! Sorry to hear you think your programming experience is different from what's in my memory - it says 12 years for you. Would you like to tell me more about why you think that?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**Learned suggestions:**
- programming_years: prefer_latest (p=0.969434290843242) -> 12 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 12 [heuristic]

## Turn 14: Contradiction Resolution

**Q:** Wait, let me be clear: I've been programming for 8 years total. 12 was wrong.

**A:** You're right, you mentioned earlier that your total programming experience is actually 8 years, not 12. I've got that noted in my memory - FACT: programming_years = 8. Let me update the fact with a trust score of 1 since it's directly from our conversation.

**Meta:** mode=quick confidence=0.49 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9838640292225128) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 15: Experience Recall Test

**Q:** How many years of programming experience do I have?

**A:** 8 (most recent update)

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9838640292225128) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 16: Subtle Location Change

**Q:** I live in the Seattle metro area, specifically in Bellevue.

**A:** You mentioned earlier that you live in the Seattle metro area, which is close to Bellevue. However, I don't have specific information on your address within Bellevue itself. Can you tell me more about where you live?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**Learned suggestions:** (none)

## Turn 17: Role Progression

**Q:** My role is Principal Engineer, not just senior developer.

**A:** You're right, your title is indeed Principal Engineer, as per my memory. I should have picked up on that earlier. Thanks for correcting me! Would you like to share more about your role or experiences as a Principal Engineer?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- title: prefer_latest (p=0.8952457710072808) -> Principal Engineer [learned]

**Heuristic baseline:**
- title: prefer_latest (p=0.65) -> Principal Engineer [heuristic]

## Turn 18: Title Recall Test

**Q:** What's my current job title?

**A:** Principal Engineer

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- title: prefer_latest (p=0.911291173174072) -> Principal Engineer [learned]

**Heuristic baseline:**
- title: prefer_latest (p=0.65) -> Principal Engineer [heuristic]

## Turn 19: Reinforcement #1: Name

**Q:** Yes, I'm Sarah - that's definitely my name.

**A:** Hi Sarah! Nice to meet you. So, just to confirm, your name is indeed Sarah and you're located in Bellevue?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- name: prefer_latest (p=0.9283055826946033) -> Sarah [learned]

**Heuristic baseline:**
- name: prefer_latest (p=0.65) -> Sarah [heuristic]

## Turn 20: Reinforcement #2: First Language

**Q:** Python was absolutely my first programming language.

**A:** That's correct! According to your memory, you actually started with Python.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.9214120639554618) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 21: Reinforcement #3: Education

**Q:** I did my Master's at MIT, that's correct.

**A:** That's correct, you're affiliated with Microsoft as a Principal Engineer. You also completed your master's degree at MIT, which aligns with the 8 years of programming experience we have in our memory.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 22: High-Trust Recall Test

**Q:** What's my name and where did I go to school?

**A:** name: Sarah
masters school: MIT

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**A/B delta (action):**
- undergrad_school: learned=prefer_latest vs heuristic=ask_clarify

**Learned suggestions:**
- name: prefer_latest (p=0.9348845118565723) -> Sarah [learned]
- masters_school: prefer_latest (p=0.9225222035090308) -> MIT [learned]
- undergrad_school: prefer_latest (p=0.5927781156952551) -> None [insufficient_data]

**Heuristic baseline:**
- name: prefer_latest (p=0.65) -> Sarah [heuristic]
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: ask_clarify (p=0.55) -> None [insufficient_data]

## Turn 23: Temporal Contradiction

**Q:** I started programming in college, which was 10 years ago.

**A:** So you started programming 10 years ago, right? That's actually a bit earlier than your initial statement said - you mentioned it was 12 years ago when you started working for Microsoft. Which one is correct?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9913187544547507) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 24: Education Expansion

**Q:** My undergraduate degree was from Stanford, then I went to MIT for my Master's.

**A:** That's correct! You mentioned your undergrad school was Stanford, and then you went to MIT for your master's degree.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**A/B delta (action):**
- graduation_year: learned=prefer_latest vs heuristic=ask_clarify

**Learned suggestions:**
- graduation_year: prefer_latest (p=0.5927781156952551) -> None [insufficient_data]
- masters_school: prefer_latest (p=0.9225222035090308) -> MIT [learned]
- undergrad_school: prefer_latest (p=0.8952457710072808) -> Stanford [learned]

**Heuristic baseline:**
- graduation_year: ask_clarify (p=0.55) -> None [insufficient_data]
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: prefer_latest (p=0.65) -> Stanford [heuristic]

## Turn 25: Education Contradiction

**Q:** Actually, both my undergrad and Master's were from MIT.

**A:** I think there might be a slight correction needed - according to your memory, you actually stated that you had an undergraduate degree from Stanford, but then later mentioned that both your undergrad and Master's degrees are actually from MIT. Would you like to clarify which one is correct?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 26: Preference Fact

**Q:** I prefer working remotely rather than in the office.

**A:** That's great to know, Sarah. You do prefer working remotely, according to our previous conversation.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- remote_preference: prefer_latest (p=0.923241298636648) -> True [learned]

**Heuristic baseline:**
- remote_preference: prefer_latest (p=0.65) -> True [heuristic]

## Turn 27: Preference vs History

**Q:** My favorite programming language is Rust, though I started with Python.

**A:** Rust's the one you're fond of! You actually started with Python - that's what your memory tells me.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.9813494075686818) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 28: Preference Contradiction

**Q:** I hate working remotely, I prefer being in the office.

**A:** I don't have a reliable stored memory for your remote_preference yet — if you tell me, I can remember it going forward.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**Learned suggestions:**
- remote_preference: prefer_latest (p=0.9584725747215512) -> False [learned]

**Heuristic baseline:**
- remote_preference: prefer_latest (p=0.65) -> False [heuristic]

## Turn 29: Complete Summary Request

**Q:** Can you summarize everything you know about me?

**A:** Based on what I remember:
  1. Hello! I'm a software engineer. My name is Sarah.
  2. Yes, I'm Sarah - that's definitely my name.
  3. I specialize in cloud computing and distributed systems.
  4. My undergraduate degree was from Stanford, then I went to MIT for my Master's.
  5. I've been programming for 12 years, not 8.
  6. My role is Principal Engineer, not just senior developer.
  7. I work at Microsoft as a senior developer.
  8. I started programming in college, which was 10 years ago.
  9. I've been programming for 8 years, starting with Python.
  10. I have a Master's degree in Computer Science from MIT.

**Meta:** mode=quick confidence=0.85 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 30: Contradiction Inventory

**Q:** What contradictions have you detected in our conversation?

**A:** I can summarize what I've recorded in the contradiction ledger so far.
Open contradictions: 4.

Most recent open items:
- [conflict/open] User contradiction: I prefer working remotely rather than in the offic... vs I hate working remotely, I prefer being in the off...
- [refinement/open] User contradiction: I live in Seattle, Washington.... vs I live in the Seattle metro area, specifically in ...
- [revision/open] User contradiction: I've been programming for 8 years, starting with P... vs I've been programming for 12 years, not 8....
- [revision/open] User contradiction: I work at Microsoft as a senior developer.... vs Actually, I need to correct something - I work at ...

**Meta:** mode=uncertainty confidence=0.65 gates_passed=False contradiction_detected=True

**Learned suggestions:** (none)


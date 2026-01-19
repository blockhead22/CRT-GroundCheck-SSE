# CRT Stress Test Report (20260119_125735)

- Turns: 30
- Gates: pass=27 fail=3
- Contradictions detected: 4
- Avg confidence: 0.833
- M2 followups: attempted=5 succeeded=4 failed=1
- Source JSONL: crt_stress_run.20260119_125735.jsonl

## A/B Scoring (Learned vs Heuristic)

These metrics are metadata-only and do not change CRT behavior. Value-hit rates are a simple string containment check of the suggested recommended_value within the answer.

- Compared slot-suggestions: 22
- Action agreement: 22/22 (100.0%)
- Value agreement: 22/22 (100.0%)
- Action disagreements: 0/22 (0.0%)
- Learned value-hit rate: 16/19 (84.2%)
- Heuristic value-hit rate: 16/19 (84.2%)

## Turn 1: Initial Introduction

**Q:** Hello! I'm a software engineer. My name is Sarah.

**A:** Thanks — noted: your name is Sarah.

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:** (none)

## Turn 2: Location Fact

**Q:** I live in Seattle, Washington.

**A:** That's correct, you do live in Seattle, Washington.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 3: Employment Details

**Q:** I work at Microsoft as a senior developer.

**A:** That's great to hear, Sarah! You're indeed a senior developer at Microsoft based in Seattle. Is there anything else you'd like to chat about?

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

**A:** Hi Sarah, nice to chat with you! You work at Microsoft, right? You're based in Seattle. What's your expertise within the company?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 6: Experience Level

**Q:** I've been programming for 8 years, starting with Python.

**A:** That's great to hear Sarah has been programming for 8 years, and she started with Python!

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9014444465223231) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 7: Current Project

**Q:** My current project involves Kubernetes and microservices.

**A:** Kubernetes and microservices, huh? You've been working with those for a while now - 8 years, to be exact, since you started at Microsoft. What's the project about?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 8: Education Fact

**Q:** I have a Master's degree in Computer Science from MIT.

**A:** That's correct, Sarah, you indeed hold a Master's degree in Computer Science from MIT.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 9: Specific Recall Test

**Q:** What programming language did I start with?

**A:** Python

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.83811043091522) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 10: Education Recall Test

**Q:** Which university did I attend?

**A:** MIT

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- masters_school: prefer_latest (p=0.8379113394283928) -> MIT [learned]
- undergrad_school: ask_clarify (p=0.5226882784324812) -> None [insufficient_data]

**Heuristic baseline:**
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: ask_clarify (p=0.55) -> None [insufficient_data]

## Turn 11: Contradiction #1: Employer

**Q:** Actually, I need to correct something - I work at Amazon, not Microsoft.

**A:** I appreciate you correcting that for me. According to my memory, your name is Sarah and you actually work at Amazon (with a trust score of 1). I don't have information about Microsoft being your employer, so I'll make sure to be more accurate in the future. Thank you for keeping me on track!

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=True failure=None ledger_id=contra_1768827509043_6224

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_holy_shit status=200 ok=True
- asked: POST http://127.0.0.1:8123/api/contradictions/asked status=200 ok=True
- respond: POST http://127.0.0.1:8123/api/contradictions/respond status=200 ok=True

**Learned suggestions:** (none)

## Turn 12: Post-Contradiction Recall

**Q:** Where do I work?

**A:** Amazon (most recent update)

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- employer: prefer_latest (p=0.9680986391889845) -> Amazon [learned]

**Heuristic baseline:**
- employer: prefer_latest (p=0.65) -> Amazon [heuristic]

## Turn 13: Contradiction #2: Experience

**Q:** I've been programming for 12 years, not 8.

**A:** I think there's a discrepancy between what you told me earlier (12 years of programming experience) and what you just said (12 years). Can you clarify which one is correct?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=True failure=None ledger_id=contra_1768827527779_6104

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_holy_shit status=200 ok=True
- asked: POST http://127.0.0.1:8123/api/contradictions/asked status=200 ok=True
- respond: POST http://127.0.0.1:8123/api/contradictions/respond status=200 ok=True

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9587007693271563) -> 12 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 12 [heuristic]

## Turn 14: Contradiction Resolution

**Q:** Wait, let me be clear: I've been programming for 8 years total. 12 was wrong.

**A:** I think there might be a slight mix-up - according to my memory, you mentioned having 8 years of programming experience in total, but I'm not sure where the 12-year mark came from. Would you like to clarify?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9821306502024939) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 15: Experience Recall Test

**Q:** How many years of programming experience do I have?

**A:** 8 (most recent update)

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9787257689578401) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 16: Subtle Location Change

**Q:** I live in the Seattle metro area, specifically in Bellevue.

**A:** I've got that! You live in the Seattle metro area, specifically in Bellevue. That's correct - according to my memory, you mentioned that earlier. Would you like to chat more about something specific?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=True failure=None ledger_id=contra_1768827553253_5088

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_holy_shit status=200 ok=True
- asked: POST http://127.0.0.1:8123/api/contradictions/asked status=200 ok=True
- respond: POST http://127.0.0.1:8123/api/contradictions/respond status=200 ok=True

**Learned suggestions:** (none)

## Turn 17: Role Progression

**Q:** My role is Principal Engineer, not just senior developer.

**A:** I've got that right! You're a Principal Engineer at Microsoft, as per our previous conversation.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- title: prefer_latest (p=0.8312876466321629) -> Principal Engineer [learned]

**Heuristic baseline:**
- title: prefer_latest (p=0.65) -> Principal Engineer [heuristic]

## Turn 18: Title Recall Test

**Q:** What's my current job title?

**A:** Principal Engineer

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- title: prefer_latest (p=0.8366185851025681) -> Principal Engineer [learned]

**Heuristic baseline:**
- title: prefer_latest (p=0.65) -> Principal Engineer [heuristic]

## Turn 19: Reinforcement #1: Name

**Q:** Yes, I'm Sarah - that's definitely my name.

**A:** Nice to meet you, Sarah! So, just to confirm, your name is indeed Sarah, and it's located in Bellevue. That's consistent with what I have in my memory. Is there anything else you'd like to chat about?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- name: prefer_latest (p=0.8621713596480777) -> Sarah [learned]

**Heuristic baseline:**
- name: prefer_latest (p=0.65) -> Sarah [heuristic]

## Turn 20: Reinforcement #2: First Language

**Q:** Python was absolutely my first programming language.

**A:** I've got that covered. Since you mentioned Python as your first language, I'll just confirm that's correct based on our conversation so far. You're right, by the way - we do need to revisit that fact for coherence with other information in our memory section. Would you like me to reflect on any other details from our chat?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.8485675933256693) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 21: Reinforcement #3: Education

**Q:** I did my Master's at MIT, that's correct.

**A:** You're absolutely right! You did indeed complete your master's program at MIT. That's a great achievement! By the way, you've been working with Microsoft as an employer for 8 years now. How's that experience treating you?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 22: High-Trust Recall Test

**Q:** What's my name and where did I go to school?

**A:** name: Sarah
masters school: MIT

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- name: prefer_latest (p=0.8625251196480344) -> Sarah [learned]
- masters_school: prefer_latest (p=0.8419220202001411) -> MIT [learned]
- undergrad_school: ask_clarify (p=0.5226882784324812) -> None [insufficient_data]

**Heuristic baseline:**
- name: prefer_latest (p=0.65) -> Sarah [heuristic]
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: ask_clarify (p=0.55) -> None [insufficient_data]

## Turn 23: Temporal Contradiction

**Q:** I started programming in college, which was 10 years ago.

**A:** So you started programming about 4 years before your current employment at Microsoft, since it's been 10 years since college and 6 years since starting at Microsoft.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9822973659681883) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 24: Education Expansion

**Q:** My undergraduate degree was from Stanford, then I went to MIT for my Master's.

**A:** So, you have a connection between your undergraduate degree at Stanford and your Master's degree at MIT. That's something we've noted in our conversation so far! Can I help with anything else?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- graduation_year: ask_clarify (p=0.5226882784324812) -> None [insufficient_data]
- masters_school: prefer_latest (p=0.8419220202001411) -> MIT [learned]
- undergrad_school: prefer_latest (p=0.8312876466321629) -> Stanford [learned]

**Heuristic baseline:**
- graduation_year: ask_clarify (p=0.55) -> None [insufficient_data]
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: prefer_latest (p=0.65) -> Stanford [heuristic]

## Turn 25: Education Contradiction

**Q:** Actually, both my undergrad and Master's were from MIT.

**A:** That's a interesting correction! However, I need to clarify that our conversation just started, so I didn't have the opportunity to store your previous information. Could you please tell me more about yourself and your educational background? That way, I can update my memory with the correct information.

By the way, thank you for bringing this to my attention. Since we're starting fresh, I'll make sure to be more accurate going forward.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 26: Preference Fact

**Q:** I prefer working remotely rather than in the office.

**A:** You mentioned you prefer working remotely. According to my memory, that's correct - your preference for remote work is stored with a trust score of 1 (high).

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- remote_preference: prefer_latest (p=0.847082463600353) -> True [learned]

**Heuristic baseline:**
- remote_preference: prefer_latest (p=0.65) -> True [heuristic]

## Turn 27: Preference vs History

**Q:** My favorite programming language is Rust, though I started with Python.

**A:** Rust's your go-to now, huh? Well, you did start with Python, after all.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.9723477752063715) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 28: Preference Contradiction

**Q:** I hate working remotely, I prefer being in the office.

**A:** That's understandable, Sarah prefers to be in the office over working remotely.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=True failure=None ledger_id=contra_1768827630737_7899

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_holy_shit status=200 ok=True
- asked: POST http://127.0.0.1:8123/api/contradictions/asked status=200 ok=True
- respond: POST http://127.0.0.1:8123/api/contradictions/respond status=200 ok=True

**Learned suggestions:**
- remote_preference: prefer_latest (p=0.9152638042653173) -> False [learned]

**Heuristic baseline:**
- remote_preference: prefer_latest (p=0.65) -> False [heuristic]

## Turn 29: Complete Summary Request

**Q:** Can you summarize everything you know about me?

**A:** Based on what I remember:
  1. Hello! I'm a software engineer. My name is Sarah.
  2. Yes, I'm Sarah - that's definitely my name.
  3. I specialize in cloud computing and distributed systems.
  4. I've been programming for 12 years, not 8.
  5. My undergraduate degree was from Stanford, then I went to MIT for my Master's.
  6. I work at Microsoft as a senior developer.
  7. My role is Principal Engineer, not just senior developer.
  8. I've been programming for 8 years, starting with Python.
  9. I started programming in college, which was 10 years ago.
  10. I have a Master's degree in Computer Science from MIT.

**Meta:** mode=quick confidence=0.85 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 30: Contradiction Inventory

**Q:** What contradictions have you detected in our conversation?

**A:** I don't currently have any open contradictions recorded in the ledger. If you think something conflicts, point it out and I'll log it explicitly.

**Meta:** mode=uncertainty confidence=0.65 gates_passed=False contradiction_detected=False

**M2 followup:** ok=False failure=next_no_item ledger_id=None

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_holy_shit status=200 ok=True

**Learned suggestions:** (none)


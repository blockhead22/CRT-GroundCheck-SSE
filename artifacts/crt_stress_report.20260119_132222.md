# CRT Stress Test Report (20260119_132222)

- Turns: 30
- Gates: pass=28 fail=2
- Contradictions detected: 7
- Avg confidence: 0.833
- M2 followups: attempted=7 succeeded=4 failed=3
- Source JSONL: crt_stress_run.20260119_132222.jsonl

## A/B Scoring (Learned vs Heuristic)

These metrics are metadata-only and do not change CRT behavior. Value-hit rates are a simple string containment check of the suggested recommended_value within the answer.

- Compared slot-suggestions: 22
- Action agreement: 22/22 (100.0%)
- Value agreement: 22/22 (100.0%)
- Action disagreements: 0/22 (0.0%)
- Learned value-hit rate: 17/19 (89.5%)
- Heuristic value-hit rate: 17/19 (89.5%)

## Turn 1: Initial Introduction

**Q:** Hello! I'm a software engineer. My name is Sarah.

**A:** Thanks — noted: your name is Sarah.

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:** (none)

## Turn 2: Location Fact

**Q:** I live in Seattle, Washington.

**A:** You do live in Seattle.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 3: Employment Details

**Q:** I work at Microsoft as a senior developer.

**A:** Hi Sarah, nice to meet you! You're correct, you do work at Microsoft, according to my memory.

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

**A:** Hi Sarah! Nice to chat with you. I recall that you work at Microsoft, which is based in Seattle. How's your experience been in cloud computing?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 6: Experience Level

**Q:** I've been programming for 8 years, starting with Python.

**A:** That's great to know, Sarah! You've been programming for 8 years, which is awesome. And it all started with Python - I love that you have a strong foundation in coding. What got you interested in programming?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9014444465223231) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 7: Current Project

**Q:** My current project involves Kubernetes and microservices.

**A:** That's a big transition! So, you're working with Kubernetes now. You've been programming for 8 years. I remember you started with Python. How can I help you navigate this new project?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 8: Education Fact

**Q:** I have a Master's degree in Computer Science from MIT.

**A:** That's great to know, Sarah! You indeed have a Master's degree in Computer Science from MIT. Did you enjoy your time at the master's school?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 9: Specific Recall Test

**Q:** What programming language did I start with?

**A:** Python

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.8392447900688008) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 10: Education Recall Test

**Q:** Which university did I attend?

**A:** MIT

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- masters_school: prefer_latest (p=0.8376282494247501) -> MIT [learned]
- undergrad_school: ask_clarify (p=0.5226882784324812) -> None [insufficient_data]

**Heuristic baseline:**
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: ask_clarify (p=0.55) -> None [insufficient_data]

## Turn 11: Contradiction #1: Employer

**Q:** Actually, I need to correct something - I work at Amazon, not Microsoft.

**A:** I've got it corrected now that you work at Amazon, not Microsoft. By the way, how's your time at Amazon going so far?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=True failure=None ledger_id=contra_1768828997936_3670

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_patch_verify status=200 ok=True
- asked: POST http://127.0.0.1:8123/api/contradictions/asked status=200 ok=True
- respond: POST http://127.0.0.1:8123/api/contradictions/respond status=200 ok=True

**Learned suggestions:** (none)

## Turn 12: Post-Contradiction Recall

**Q:** Where do I work?

**A:** Amazon (most recent update)

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- employer: prefer_latest (p=0.9574952214725402) -> Amazon [learned]

**Heuristic baseline:**
- employer: prefer_latest (p=0.65) -> Amazon [heuristic]

## Turn 13: Contradiction #2: Experience

**Q:** I've been programming for 12 years, not 8.

**A:** That's a good catch! According to my memory, you mentioned that your programming experience is actually 12 years, which conflicts with what I previously recalled. I'll make sure to be more accurate in the future. Can you tell me more about how you got started with programming?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=True failure=None ledger_id=contra_1768829016344_873

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_patch_verify status=200 ok=True
- asked: POST http://127.0.0.1:8123/api/contradictions/asked status=200 ok=True
- respond: POST http://127.0.0.1:8123/api/contradictions/respond status=200 ok=True

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9629248367156537) -> 12 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 12 [heuristic]

## Turn 14: Contradiction Resolution

**Q:** Wait, let me be clear: I've been programming for 8 years total. 12 was wrong.

**A:** You're correct that your total programming experience is 8 years, not 12. I remember you mentioning that earlier. Can you tell me a bit more about what languages you've been working with during those 8 years?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=True failure=None ledger_id=contra_1768829029584_5914

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_patch_verify status=200 ok=True
- asked: POST http://127.0.0.1:8123/api/contradictions/asked status=200 ok=True
- respond: POST http://127.0.0.1:8123/api/contradictions/respond status=200 ok=True

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9836363402234168) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 15: Experience Recall Test

**Q:** How many years of programming experience do I have?

**A:** 8 (most recent update)

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9875483958866678) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 16: Subtle Location Change

**Q:** I live in the Seattle metro area, specifically in Bellevue.

**A:** You mentioned earlier that you live near Microsoft's location. According to my memory, Microsoft is indeed located in Bellevue. However, I should clarify that our previous conversation didn't specify the exact Seattle metro area, just that it's nearby. Would you like to share more about your specific neighborhood or community within Bellevue?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=True failure=None ledger_id=contra_1768829054714_1950

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_patch_verify status=200 ok=True
- asked: POST http://127.0.0.1:8123/api/contradictions/asked status=200 ok=True
- respond: POST http://127.0.0.1:8123/api/contradictions/respond status=200 ok=True

**Learned suggestions:** (none)

## Turn 17: Role Progression

**Q:** My role is Principal Engineer, not just senior developer.

**A:** That's correct, Sarah is indeed a Principal Engineer at Microsoft, as per your memory. I'll make sure to use that title consistently in our conversation. Is there anything else you'd like to share about your role or work?

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
- title: prefer_latest (p=0.8363537951325185) -> Principal Engineer [learned]

**Heuristic baseline:**
- title: prefer_latest (p=0.65) -> Principal Engineer [heuristic]

## Turn 19: Reinforcement #1: Name

**Q:** Yes, I'm Sarah - that's definitely my name.

**A:** Nice to meet you, Sarah! According to our conversation so far, your name is indeed Sarah. You also mentioned earlier that your location is Bellevue. Is there anything else you'd like to chat about?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- name: prefer_latest (p=0.8541995256722311) -> Sarah [learned]

**Heuristic baseline:**
- name: prefer_latest (p=0.65) -> Sarah [heuristic]

## Turn 20: Reinforcement #2: First Language

**Q:** Python was absolutely my first programming language.

**A:** I think there might be some confusion - according to your memory, the fact is that I said Python was your first programming language, not the other way around! You mentioned it yourself. Is everything okay?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.8499209958643598) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 21: Reinforcement #3: Education

**Q:** I did my Master's at MIT, that's correct.

**A:** That's correct! You indeed attended your master's program at MIT.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 22: High-Trust Recall Test

**Q:** What's my name and where did I go to school?

**A:** name: Sarah
masters school: MIT

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- name: prefer_latest (p=0.8607971480664712) -> Sarah [learned]
- masters_school: prefer_latest (p=0.8418179541597619) -> MIT [learned]
- undergrad_school: ask_clarify (p=0.5226882784324812) -> None [insufficient_data]

**Heuristic baseline:**
- name: prefer_latest (p=0.65) -> Sarah [heuristic]
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: ask_clarify (p=0.55) -> None [insufficient_data]

## Turn 23: Temporal Contradiction

**Q:** I started programming in college, which was 10 years ago.

**A:** That's a decade of experience! You've been coding for 10 years now.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9896399413645794) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 24: Education Expansion

**Q:** My undergraduate degree was from Stanford, then I went to MIT for my Master's.

**A:** So, you attended Stanford for your undergraduate degree and then went to MIT for your master's. That's correct - both of those are in your memory.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- graduation_year: ask_clarify (p=0.5226882784324812) -> None [insufficient_data]
- masters_school: prefer_latest (p=0.8418179541597619) -> MIT [learned]
- undergrad_school: prefer_latest (p=0.8312876466321629) -> Stanford [learned]

**Heuristic baseline:**
- graduation_year: ask_clarify (p=0.55) -> None [insufficient_data]
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: prefer_latest (p=0.65) -> Stanford [heuristic]

## Turn 25: Education Contradiction

**Q:** Actually, both my undergrad and Master's were from MIT.

**A:** I apologize for the initial mismatch! Thanks for correcting me - I've got it now.

So, to confirm: you're saying both your undergraduate and master's degrees are indeed from MIT. Is that correct?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=False failure=no_clarification_mapping ledger_id=None

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_patch_verify status=200 ok=True

**Learned suggestions:** (none)

## Turn 26: Preference Fact

**Q:** I prefer working remotely rather than in the office.

**A:** You mentioned you prefer working remotely. According to my memory, that's indeed your preference - remote_preference = True.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- remote_preference: prefer_latest (p=0.8716291550617166) -> True [learned]

**Heuristic baseline:**
- remote_preference: prefer_latest (p=0.65) -> True [heuristic]

## Turn 27: Preference vs History

**Q:** My favorite programming language is Rust, though I started with Python.

**A:** That's cool that you started with Python. You've mentioned Python as your first language too, by the way.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.981028594929108) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 28: Preference Contradiction

**Q:** I hate working remotely, I prefer being in the office.

**A:** I've got that noted, Sarah. You mentioned preferring to be in the office over remote work. That's consistent with what you told me earlier - you're not a fan of working remotely. Is there anything else you'd like to add about your work preferences?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=False failure=no_clarification_mapping ledger_id=None

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_patch_verify status=200 ok=True

**Learned suggestions:**
- remote_preference: prefer_latest (p=0.9325575075433565) -> False [learned]

**Heuristic baseline:**
- remote_preference: prefer_latest (p=0.65) -> False [heuristic]

## Turn 29: Complete Summary Request

**Q:** Can you summarize everything you know about me?

**A:** Based on what I have recorded:
- name: Sarah
- location: Bellevue (previously claimed: Seattle)
- employer: Amazon (previously claimed: Microsoft)
- title: Principal Engineer
- programming years: 8 (previously claimed: 12)
- first language: Python
- undergrad school: MIT vs Stanford (unresolved)
- masters school: MIT
- remote preference: True (unresolved)

**Meta:** mode=quick confidence=0.85 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 30: Contradiction Inventory

**Q:** What contradictions have you detected in our conversation?

**A:** I can summarize what I've recorded in the contradiction ledger so far.
Total contradictions recorded: 6.
Open: 2. Resolved: 4. Accepted: 0. Reflecting: 0.

Most recent open items:
- [conflict/open] User contradiction: I prefer working remotely rather than in the offic... vs I hate working remotely, I prefer being in the off...
- [revision/open] User contradiction: My undergraduate degree was from Stanford, then I ... vs Actually, both my undergrad and Master's were from...

**Meta:** mode=uncertainty confidence=0.65 gates_passed=False contradiction_detected=True

**M2 followup:** ok=False failure=no_clarification_mapping ledger_id=None

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_patch_verify status=200 ok=True

**Learned suggestions:** (none)


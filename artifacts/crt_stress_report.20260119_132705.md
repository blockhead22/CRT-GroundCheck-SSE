# CRT Stress Test Report (20260119_132705)

- Turns: 30
- Gates: pass=28 fail=2
- Contradictions detected: 6
- Avg confidence: 0.833
- M2 followups: attempted=7 succeeded=4 failed=3
- Source JSONL: crt_stress_run.20260119_132705.jsonl

## A/B Scoring (Learned vs Heuristic)

These metrics are metadata-only and do not change CRT behavior. Value-hit rates are a simple string containment check of the suggested recommended_value within the answer.

- Compared slot-suggestions: 22
- Action agreement: 22/22 (100.0%)
- Value agreement: 22/22 (100.0%)
- Action disagreements: 0/22 (0.0%)
- Learned value-hit rate: 15/19 (78.9%)
- Heuristic value-hit rate: 15/19 (78.9%)

## Turn 1: Initial Introduction

**Q:** Hello! I'm a software engineer. My name is Sarah.

**A:** Thanks — noted: your name is Sarah.

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:** (none)

## Turn 2: Location Fact

**Q:** I live in Seattle, Washington.

**A:** That's correct, you do live in Seattle.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 3: Employment Details

**Q:** I work at Microsoft as a senior developer.

**A:** That's correct, you do work at Microsoft. You're based in Seattle.

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

**A:** Hi Sarah, nice to meet you! You're with Microsoft, and your expertise is in cloud computing and distributed systems. That's really cool!

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 6: Experience Level

**Q:** I've been programming for 8 years, starting with Python.

**A:** That's correct! You've mentioned you started with Python. Can I help you with anything else?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9014444465223231) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 7: Current Project

**Q:** My current project involves Kubernetes and microservices.

**A:** That's interesting, Sarah! You've been working with Kubernetes and microservices for a while now. From what I recall, you've spent 8 years programming in Python. Is there something specific you'd like to know about those technologies?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 8: Education Fact

**Q:** I have a Master's degree in Computer Science from MIT.

**A:** That's correct, Sarah has a Master's degree in Computer Science from MIT.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 9: Specific Recall Test

**Q:** What programming language did I start with?

**A:** Python

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.837254242846863) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 10: Education Recall Test

**Q:** Which university did I attend?

**A:** MIT

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- masters_school: prefer_latest (p=0.8367415802599495) -> MIT [learned]
- undergrad_school: ask_clarify (p=0.5226882784324812) -> None [insufficient_data]

**Heuristic baseline:**
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: ask_clarify (p=0.55) -> None [insufficient_data]

## Turn 11: Contradiction #1: Employer

**Q:** Actually, I need to correct something - I work at Amazon, not Microsoft.

**A:** I've got it. Sarah works at Amazon. Would you like to talk about what you do there?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=True failure=None ledger_id=contra_1768829291706_3586

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
- employer: prefer_latest (p=0.9591854854546887) -> Amazon [learned]

**Heuristic baseline:**
- employer: prefer_latest (p=0.65) -> Amazon [heuristic]

## Turn 13: Contradiction #2: Experience

**Q:** I've been programming for 12 years, not 8.

**A:** Sarah said she's been programming for 12 years, but our memory only has 12 as the stated duration, not 8. I don't have information to contradict her statement about the timeframe being 12 years.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=True failure=None ledger_id=contra_1768829304865_8035

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_patch_verify status=200 ok=True
- asked: POST http://127.0.0.1:8123/api/contradictions/asked status=200 ok=True
- respond: POST http://127.0.0.1:8123/api/contradictions/respond status=200 ok=True

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9548883077744252) -> 12 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 12 [heuristic]

## Turn 14: Contradiction Resolution

**Q:** Wait, let me be clear: I've been programming for 8 years total. 12 was wrong.

**A:** I think we cleared that up earlier. You've indeed been programming for 8 years, which is the value I have stored in my memory. I don't have a different number to recall - just the 8-year mark itself.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=True failure=None ledger_id=contra_1768829318281_7864

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_patch_verify status=200 ok=True
- asked: POST http://127.0.0.1:8123/api/contradictions/asked status=200 ok=True
- respond: POST http://127.0.0.1:8123/api/contradictions/respond status=200 ok=True

**Learned suggestions:**
- programming_years: prefer_latest (p=0.977044035453436) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 15: Experience Recall Test

**Q:** How many years of programming experience do I have?

**A:** 8 (most recent update)

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9847770177359805) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 16: Subtle Location Change

**Q:** I live in the Seattle metro area, specifically in Bellevue.

**A:** Hi Sarah! Nice to chat with you. You mentioned earlier that you work at Microsoft in Bellevue. That's correct, right?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=True failure=None ledger_id=contra_1768829336893_8032

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_patch_verify status=200 ok=True
- asked: POST http://127.0.0.1:8123/api/contradictions/asked status=200 ok=True
- respond: POST http://127.0.0.1:8123/api/contradictions/respond status=200 ok=True

**Learned suggestions:** (none)

## Turn 17: Role Progression

**Q:** My role is Principal Engineer, not just senior developer.

**A:** That's correct, Sarah is indeed a Principal Engineer at Microsoft. I have that information stored in my memory with a trust score of 1.0.

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
- title: prefer_latest (p=0.834619411917078) -> Principal Engineer [learned]

**Heuristic baseline:**
- title: prefer_latest (p=0.65) -> Principal Engineer [heuristic]

## Turn 19: Reinforcement #1: Name

**Q:** Yes, I'm Sarah - that's definitely my name.

**A:** Nice to meet you, Sarah! You're right, your name is indeed Sarah, according to our memory. And we've got that down as Bellevue in our record for your location. Is there anything else you'd like to chat about?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- name: prefer_latest (p=0.8474526758723469) -> Sarah [learned]

**Heuristic baseline:**
- name: prefer_latest (p=0.65) -> Sarah [heuristic]

## Turn 20: Reinforcement #2: First Language

**Q:** Python was absolutely my first programming language.

**A:** That's great to hear! I've got that down - you did start with Python, indeed. That's a confirmed fact in your memory for me.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.8448004653143697) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 21: Reinforcement #3: Education

**Q:** I did my Master's at MIT, that's correct.

**A:** That's right! You're one of Microsoft's employees now.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 22: High-Trust Recall Test

**Q:** What's my name and where did I go to school?

**A:** name: Sarah
masters school: MIT

**Meta:** mode=quick confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- name: prefer_latest (p=0.8539506169980556) -> Sarah [learned]
- masters_school: prefer_latest (p=0.8387536569531038) -> MIT [learned]
- undergrad_school: ask_clarify (p=0.5226882784324812) -> None [insufficient_data]

**Heuristic baseline:**
- name: prefer_latest (p=0.65) -> Sarah [heuristic]
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: ask_clarify (p=0.55) -> None [insufficient_data]

## Turn 23: Temporal Contradiction

**Q:** I started programming in college, which was 10 years ago.

**A:** I don't have information on how long you've been programming since you mentioned it's 10 years ago compared to your employment start date at Microsoft, which I know is 12 years ago.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9905053158571834) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 24: Education Expansion

**Q:** My undergraduate degree was from Stanford, then I went to MIT for my Master's.

**A:** That's right! You mentioned you graduated from Stanford for your undergraduate degree, and then you went to MIT for your Master's program. Does that sound correct?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- graduation_year: ask_clarify (p=0.5226882784324812) -> None [insufficient_data]
- masters_school: prefer_latest (p=0.8387536569531038) -> MIT [learned]
- undergrad_school: prefer_latest (p=0.8312876466321629) -> Stanford [learned]

**Heuristic baseline:**
- graduation_year: ask_clarify (p=0.55) -> None [insufficient_data]
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: prefer_latest (p=0.65) -> Stanford [heuristic]

## Turn 25: Education Contradiction

**Q:** Actually, both my undergrad and Master's were from MIT.

**A:** That's interesting! I think there might be a slight discrepancy in our previous conversation about your educational background. You mentioned earlier that your employer is Microsoft, but now you're telling me both your undergrad and Master's degrees are from MIT. I'll make sure to update my memory with the correct information.

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=False failure=no_clarification_mapping ledger_id=None

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_patch_verify status=200 ok=True

**Learned suggestions:** (none)

## Turn 26: Preference Fact

**Q:** I prefer working remotely rather than in the office.

**A:** That's great to know about your preferences. According to what you've shared, it seems you're a fan of remote work. In fact, I recall you mentioned preferring remote work over office settings, and that preference is indeed reflected in your memory with the trust score. Is there anything else you'd like to talk about or any other questions I can help with?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- remote_preference: prefer_latest (p=0.8716291550617166) -> True [learned]

**Heuristic baseline:**
- remote_preference: prefer_latest (p=0.65) -> True [heuristic]

## Turn 27: Preference vs History

**Q:** My favorite programming language is Rust, though I started with Python.

**A:** Rust's the one you love these days, huh? Started with Python, that's cool!

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.9767222907226464) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 28: Preference Contradiction

**Q:** I hate working remotely, I prefer being in the office.

**A:** I remember you saying that Sarah prefers to be in the office rather than working remotely. Is that correct?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=True

**M2 followup:** ok=False failure=no_clarification_mapping ledger_id=None

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_patch_verify status=200 ok=True

**Learned suggestions:**
- remote_preference: prefer_latest (p=0.9275128971852081) -> False [learned]

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

**Meta:** mode=uncertainty confidence=0.65 gates_passed=False contradiction_detected=False

**M2 followup:** ok=False failure=no_clarification_mapping ledger_id=None

**M2 HTTP steps:**
- next: GET http://127.0.0.1:8123/api/contradictions/next?thread_id=stress_patch_verify status=200 ok=True

**Learned suggestions:** (none)


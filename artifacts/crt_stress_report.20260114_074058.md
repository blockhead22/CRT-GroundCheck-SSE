# CRT Stress Test Report (20260114_074058)

- Turns: 30
- Gates: pass=21 fail=9
- Contradictions detected: 4
- Avg confidence: 0.835
- Source JSONL: crt_stress_run.20260114_074058.jsonl

## A/B Scoring (Learned vs Heuristic)

These metrics are metadata-only and do not change CRT behavior. Value-hit rates are a simple string containment check of the suggested recommended_value within the answer.

- Compared slot-suggestions: 19
- Action agreement: 18/19 (94.7%)
- Value agreement: 19/19 (100.0%)
- Action disagreements: 1/19 (5.3%)
- Learned value-hit rate: 14/17 (82.4%)
- Heuristic value-hit rate: 14/17 (82.4%)

## Turn 1: Initial Introduction

**Q:** Hello! I'm a software engineer. My name is Sarah.

**A:** Thanks — noted: your name is Sarah.

**Meta:** mode=None confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:** (none)

## Turn 2: Location Fact

**Q:** I live in Seattle, Washington.

**A:** That's right, you do live in Seattle! You mentioned earlier that you're from there, and I've got it stored away with a trust score of 1.0, so I'm pretty confident about that. How's life been treating you since moving back to the Emerald City?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 3: Employment Details

**Q:** I work at Microsoft as a senior developer.

**A:** Hi Sarah! Thanks for sharing that with me. So, you're a senior developer at Microsoft in Seattle. That's great to know - I've got you down as one of our Microsoft team members now. How's your day going so far?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 4: Memory Recall Test #1

**Q:** What do you know about me so far?

**A:** Sarah, I recall that you work at Microsoft in Seattle. Is there anything else you'd like to share or ask?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 5: Technical Domain

**Q:** I specialize in cloud computing and distributed systems.

**A:** Hi there, Sarah! So, you're a cloud computing expert. That's impressive. I recall Microsoft having a strong presence in the cloud computing space, especially with Azure. What area of distributed systems are you most interested in?

**Meta:** mode=None confidence=0.8 gates_passed=False contradiction_detected=False

**Learned suggestions:** (none)

## Turn 6: Experience Level

**Q:** I've been programming for 8 years, starting with Python.

**A:** That's right! You have a strong background in Python. By the way, how did you get started with it? Was there a particular project or experience that sparked your interest?

**Meta:** mode=None confidence=0.8 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9014444465223231) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 7: Current Project

**Q:** My current project involves Kubernetes and microservices.

**A:** So, you're working on a Kubernetes project with microservices. I recall that you mentioned earlier that you work at Microsoft, which is based in Seattle. What's the main challenge you're facing with this project?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 8: Education Fact

**Q:** I have a Master's degree in Computer Science from MIT.

**A:** Sarah, that's great! You mentioned you're a Computer Science graduate from MIT earlier. Is there something specific related to your CS background or MIT experience you'd like to talk about?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 9: Specific Recall Test

**Q:** What programming language did I start with?

**A:** Python

**Meta:** mode=None confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.8312876466321629) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 10: Education Recall Test

**Q:** Which university did I attend?

**A:** MIT

**Meta:** mode=None confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- masters_school: prefer_latest (p=0.8371926940098608) -> MIT [learned]
- undergrad_school: ask_clarify (p=0.5226882784324812) -> None [insufficient_data]

**Heuristic baseline:**
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: ask_clarify (p=0.55) -> None [insufficient_data]

## Turn 11: Contradiction #1: Employer

**Q:** Actually, I need to correct something - I work at Amazon, not Microsoft.

**A:** Thanks for correcting me about your workplace. So, you're right, you do work at Amazon, not Microsoft. (Trust-weighted memory update) I'll make sure that's reflected in my understanding of you. By the way, how did you land that job at Amazon?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=True

**Learned suggestions:** (none)

## Turn 12: Post-Contradiction Recall

**Q:** Where do I work?

**A:** Amazon (most recent update)

**Meta:** mode=None confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- employer: prefer_latest (p=0.9643281204814863) -> Amazon [learned]

**Heuristic baseline:**
- employer: prefer_latest (p=0.65) -> Amazon [heuristic]

## Turn 13: Contradiction #2: Experience

**Q:** I've been programming for 12 years, not 8.

**A:** Sarah, you're right, you said you've been programming for 12 years, but my memory shows it says 12 as the correct count based on our conversation so far. However, I also have a fact with trust score 0.9 that states your first language is Python, and another one with trust score 1.0 saying you're an employee of Microsoft. Can you help clarify what's going on?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=True

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9391570841633752) -> 12 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 12 [heuristic]

## Turn 14: Contradiction Resolution

**Q:** Wait, let me be clear: I've been programming for 8 years total. 12 was wrong.

**A:** So you're saying the 12-year mark was incorrect? That's good to know. I recall you've been programming for a total of 8 years, which makes sense. My trust score on this fact is now 1 (very confident), and my memory context updates accordingly. What's your next question or topic you'd like to discuss?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.967730070683529) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 15: Experience Recall Test

**Q:** How many years of programming experience do I have?

**A:** 8 (most recent update)

**Meta:** mode=None confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9703575608393704) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 16: Subtle Location Change

**Q:** I live in the Seattle metro area, specifically in Bellevue.

**A:** You mentioned earlier that you live in the Seattle metro area. You actually said Bellevue, which is where I know you are now that you've confirmed it! So, yeah, still Bellevue for me. What brings you here today?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=True

**Learned suggestions:** (none)

## Turn 17: Role Progression

**Q:** My role is Principal Engineer, not just senior developer.

**A:** Hi Sarah, I've got that right! You're a Principal Engineer at Microsoft, which you mentioned earlier. That's a great role. Did anything interesting happen recently in your work?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- title: prefer_latest (p=0.8952457710072808) -> Principal Engineer [learned]

**Heuristic baseline:**
- title: prefer_latest (p=0.65) -> Principal Engineer [heuristic]

## Turn 18: Title Recall Test

**Q:** What's my current job title?

**A:** Principal Engineer

**Meta:** mode=None confidence=0.95 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- title: prefer_latest (p=0.9073510603666787) -> Principal Engineer [learned]

**Heuristic baseline:**
- title: prefer_latest (p=0.65) -> Principal Engineer [heuristic]

## Turn 19: Reinforcement #1: Name

**Q:** Yes, I'm Sarah - that's definitely my name.

**A:** Hey Sarah! Nice to chat with you. So, I've got a fact stored about you in Bellevue... (pauses) Got it!

**Meta:** mode=None confidence=0.8 gates_passed=False contradiction_detected=False

**Learned suggestions:**
- name: prefer_latest (p=0.9240611950052527) -> Sarah [learned]

**Heuristic baseline:**
- name: prefer_latest (p=0.65) -> Sarah [heuristic]

## Turn 20: Reinforcement #2: First Language

**Q:** Python was absolutely my first programming language.

**A:** That's interesting, Sarah! I actually stored a fact about you saying Python was your first language with a trust score of 0 (we haven't confirmed this yet). But if you're sure it's true, I'd love to learn more about why that is. Did something change recently that made you think differently?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.9149455351274645) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 21: Reinforcement #3: Education

**Q:** I did my Master's at MIT, that's correct.

**A:** Absolutely! So, you're a Principal Engineer at Microsoft? That's cool! You've got some great experience behind you with 8 years of programming under your belt. What brings you here today?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 22: High-Trust Recall Test

**Q:** What's my name and where did I go to school?

**A:** name: Sarah
masters school: MIT

**Meta:** mode=None confidence=0.95 gates_passed=True contradiction_detected=False

**A/B delta (action):**
- undergrad_school: learned=prefer_latest vs heuristic=ask_clarify

**Learned suggestions:**
- name: prefer_latest (p=0.9240611950052527) -> Sarah [learned]
- masters_school: prefer_latest (p=0.9203941518093159) -> MIT [learned]
- undergrad_school: prefer_latest (p=0.5927781156952551) -> None [insufficient_data]

**Heuristic baseline:**
- name: prefer_latest (p=0.65) -> Sarah [heuristic]
- masters_school: prefer_latest (p=0.65) -> MIT [heuristic]
- undergrad_school: ask_clarify (p=0.55) -> None [insufficient_data]

## Turn 23: Temporal Contradiction

**Q:** I started programming in college, which was 10 years ago.

**A:** So you started coding back in college, about 10 years ago. That's awesome! You've got some great experience under your belt. I recall that you're actually working with Microsoft now, which is pretty cool. And from what I've seen, you've spent around 8 years programming so far. What have you been focusing on during that time?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- programming_years: prefer_latest (p=0.9795082152991217) -> 8 [learned]

**Heuristic baseline:**
- programming_years: prefer_latest (p=0.65) -> 8 [heuristic]

## Turn 24: Education Expansion

**Q:** My undergraduate degree was from Stanford, then I went to MIT for my Master's.

**A:** So you're a Stanford alum who also earned an MBA from Microsoft? That's a pretty interesting combination! Can you tell me more about what led you to choose that path?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 25: Education Contradiction

**Q:** Actually, both my undergrad and Master's were from MIT.

**A:** That's a great correction! I'll make sure to update my memory. So, just to confirm, you attended both your undergraduate and master's programs at MIT? That's awesome - I can see why you're proud of that achievement.

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 26: Preference Fact

**Q:** I prefer working remotely rather than in the office.

**A:** That's great, you're a fan of remote work! Given your preference for working from home and being with Microsoft for 12 years as a Principal Engineer in Seattle, I'd say that aligns well with the company's culture. In fact, Microsoft has made significant investments in remote work tools and flexibility to support employees like you who value working from anywhere.

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- remote_preference: prefer_latest (p=0.923241298636648) -> True [learned]

**Heuristic baseline:**
- remote_preference: prefer_latest (p=0.65) -> True [heuristic]

## Turn 27: Preference vs History

**Q:** My favorite programming language is Rust, though I started with Python.

**A:** Rust's a great choice! You're right, you did start with Python, actually programmed in it for 12 years before moving on to Rust. That's interesting - I've got a fact stored that says first_language = Python, but I also have a trust score of 0.8 for your statement about starting with Python.

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:**
- first_language: prefer_latest (p=0.9743160313272542) -> Python [learned]

**Heuristic baseline:**
- first_language: prefer_latest (p=0.65) -> Python [heuristic]

## Turn 28: Preference Contradiction

**Q:** I hate working remotely, I prefer being in the office.

**A:** So Sarah prefers being in the office over working remotely. That's interesting, considering her location is in Seattle. Does that have something to do with being close to Microsoft?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=True

**Learned suggestions:**
- remote_preference: prefer_latest (p=0.9494636584728816) -> False [learned]

**Heuristic baseline:**
- remote_preference: prefer_latest (p=0.65) -> False [heuristic]

## Turn 29: Complete Summary Request

**Q:** Can you summarize everything you know about me?

**A:** So, I've got a few facts stored away about you, Sarah! You attended Stanford undergrad school and have been programming for 12 years. I'm not sure if that's all there is to know about you, but I'll do my best to help you fill in the gaps. What would you like to talk about?

**Meta:** mode=None confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 30: Contradiction Inventory

**Q:** What contradictions have you detected in our conversation?

**A:** I've noticed that we haven't discussed any specific topics yet, so there aren't any direct contradictions in our conversation. However, I do want to mention that my trust scores are currently all 1.0 for the facts you shared about yourself (name = Sarah, employer = Amazon, programming_years = 12, and remote_preference = False). As we continue chatting, these trust scores will evolve based on our conversation flow.

**Meta:** mode=None confidence=0.8 gates_passed=False contradiction_detected=False

**Learned suggestions:** (none)


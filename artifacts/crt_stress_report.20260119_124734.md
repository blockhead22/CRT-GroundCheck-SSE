# CRT Stress Test Report (20260119_124734)

- Turns: 5
- Gates: pass=4 fail=1
- Contradictions detected: 0
- Avg confidence: 0.840
- Source JSONL: crt_stress_run.20260119_124734.jsonl

## A/B Scoring (Learned vs Heuristic)

These metrics are metadata-only and do not change CRT behavior. Value-hit rates are a simple string containment check of the suggested recommended_value within the answer.

- Compared slot-suggestions: 0

## Turn 1: Initial Introduction

**Q:** Hello! I'm a software engineer. My name is Sarah.

**A:** Thanks — noted: your name is Sarah.

**Meta:** mode=quick confidence=0.95 gates_passed=False contradiction_detected=False

**Learned suggestions:** (none)

## Turn 2: Location Fact

**Q:** I live in Seattle, Washington.

**A:** You do indeed live in Seattle, Washington. That's correct!

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)

## Turn 3: Employment Details

**Q:** I work at Microsoft as a senior developer.

**A:** That's correct, you do work at Microsoft. Your job title is listed as a senior developer.

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

**A:** That's great to know, Sarah! It sounds like you have expertise in cloud computing and distributed systems. You currently work at Microsoft in Seattle. Is there anything else you'd like to talk about related to your field of specialization?

**Meta:** mode=quick confidence=0.8 gates_passed=True contradiction_detected=False

**Learned suggestions:** (none)


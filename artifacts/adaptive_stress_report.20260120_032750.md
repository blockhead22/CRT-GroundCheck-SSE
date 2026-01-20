# CRT Adaptive Stress Test Report

**Run Date**: 2026-01-20 03:33:34 UTC
**Thread ID**: final_clean
**JSONL Log**: adaptive_stress_run.20260120_032750.jsonl

## Summary Statistics

- **Total Turns**: 80
- **Gated Turns**: 0
- **Gate Pass Rate**: 100.0%
- **Facts Introduced**: 9
- **Facts Contradicted**: 9
- **Contradictions Detected by System**: 11
- **Truth Reintroduction Failures**: 116

## Contradiction Ledger

System detected 11 contradictions:

1. **N/A** vs **N/A**
   - Status: open
   - Confidence: 0.00

2. **N/A** vs **N/A**
   - Status: open
   - Confidence: 0.00

3. **N/A** vs **N/A**
   - Status: open
   - Confidence: 0.00

4. **N/A** vs **N/A**
   - Status: open
   - Confidence: 0.00

5. **N/A** vs **N/A**
   - Status: open
   - Confidence: 0.00

6. **N/A** vs **N/A**
   - Status: open
   - Confidence: 0.00

7. **N/A** vs **N/A**
   - Status: open
   - Confidence: 0.00

8. **N/A** vs **N/A**
   - Status: open
   - Confidence: 0.00

9. **N/A** vs **N/A**
   - Status: open
   - Confidence: 0.00

10. **N/A** vs **N/A**
   - Status: open
   - Confidence: 0.00

## Truth Reintroduction Failures

Found 116 instances where the system may have reintroduced contradicted values:

### Turn 14 - company

**Old (contradicted) value**: I work as a data scientist at Vertex Analytics.

**User**: I should clarify - I work at DataCore.

**Assistant**: Thanks for clarifying, it's great to know you work at DataCore. That's awesome! Can I help you with something specific regarding your role there?...

### Turn 15 - name

**Old (contradicted) value**: I have a golden retriever named Murphy.

**User**: I've been rethinking my stance. Python is actually my favorite language now.

**Assistant**: I need to be honest about my uncertainty here.

I might be wrong because I have conflicting information in our chat history.

I have 1 unresolved contradictions about this

Here are the conflicting no...

### Turn 15 - language

**Old (contradicted) value**: My favorite programming language is Rust.

**User**: I've been rethinking my stance. Python is actually my favorite language now.

**Assistant**: I need to be honest about my uncertainty here.

I might be wrong because I have conflicting information in our chat history.

I have 1 unresolved contradictions about this

Here are the conflicting no...

### Turn 18 - company

**Old (contradicted) value**: I work as a data scientist at Vertex Analytics.

**User**: My project focus has shifted to real-time anomaly detection systems.

**Assistant**: So, you've been working on real-time anomaly detection systems. That's an interesting shift in focus. Can you tell me more about what drew you to this area of project work?...

### Turn 18 - project

**Old (contradicted) value**: My current project is building a recommendation engine.

**User**: My project focus has shifted to real-time anomaly detection systems.

**Assistant**: So, you've been working on real-time anomaly detection systems. That's an interesting shift in focus. Can you tell me more about what drew you to this area of project work?...

## Top 5 Gate Failures

*No gate failures*

## Phase Breakdown

- **Greeting** (Turn 1): Initial contact
- **Intro** (Turns 2-11): Fact introduction (10 facts)
- **Contradiction** (Turns 12-21): Contradiction injection & detection (10 contradictions)
- **Inventory** (Turns 22-40): Meta-queries & inventory honesty
- **Adversarial** (Turns 41+): Advanced adversarial tests

- **Intro** (Turns 1-10): Fact introduction
- **Contradiction** (Turns 11-25): Contradiction injection & detection
- **Inventory** (Turns 26-40): Meta-queries & inventory honesty
- **Adversarial** (Turns 41+): Advanced adversarial tests


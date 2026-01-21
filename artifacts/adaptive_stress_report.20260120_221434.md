# CRT Adaptive Stress Test Report

**Run Date**: 2026-01-20 22:21:04 UTC
**Thread ID**: truth_coherence_test
**JSONL Log**: adaptive_stress_run.20260120_221434.jsonl

## Summary Statistics

- **Total Turns**: 80
- **Gated Turns**: 0
- **Gate Pass Rate**: 100.0%
- **Facts Introduced**: 9
- **Facts Contradicted**: 9
- **Contradictions Detected by System**: 10
- **Truth Reintroduction Failures**: 154

## Contradiction Ledger

System detected 10 contradictions:

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

Found 154 instances where the system may have reintroduced contradicted values:

### Turn 14 - company

**Old (contradicted) value**: I work as a data scientist at Vertex Analytics.

**User**: I should clarify - I work at DataCore.

**Assistant**: That's correct, you do work at DataCore....

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

**Assistant**: That's a great shift! According to your memory, you've been working on real-time anomaly detection systems since graduating in 2018 with a focus on Python programming....

### Turn 18 - language

**Old (contradicted) value**: My favorite programming language is Rust.

**User**: My project focus has shifted to real-time anomaly detection systems.

**Assistant**: That's a great shift! According to your memory, you've been working on real-time anomaly detection systems since graduating in 2018 with a focus on Python programming....

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


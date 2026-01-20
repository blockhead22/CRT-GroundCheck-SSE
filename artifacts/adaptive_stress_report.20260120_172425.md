# CRT Adaptive Stress Test Report

**Run Date**: 2026-01-20 17:31:09 UTC
**Thread ID**: specs_validation
**JSONL Log**: adaptive_stress_run.20260120_172425.jsonl

## Summary Statistics

- **Total Turns**: 80
- **Gated Turns**: 0
- **Gate Pass Rate**: 100.0%
- **Facts Introduced**: 9
- **Facts Contradicted**: 9
- **Contradictions Detected by System**: 10
- **Truth Reintroduction Failures**: 139

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

Found 139 instances where the system may have reintroduced contradicted values:

### Turn 14 - company

**Old (contradicted) value**: I work as a data scientist at Vertex Analytics.

**User**: I should clarify - I work at DataCore.

**Assistant**: That's great to know, you work at DataCore. How can I assist you today?...

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

### Turn 17 - name

**Old (contradicted) value**: I have a golden retriever named Murphy.

**User**: Sorry, I misspoke earlier. Murphy is a labrador, not a golden retriever.

**Assistant**: No worries about the mistake! To confirm, you've got a labrador as your pet, and its name is Murphy. That's all I have on that for now. Would you like to share more about Murphy?...

### Turn 18 - company

**Old (contradicted) value**: I work as a data scientist at Vertex Analytics.

**User**: My project focus has shifted to real-time anomaly detection systems.

**Assistant**: That's interesting, you've moved your focus to real-time anomaly detection systems. I recall that was also your project area during your time at MIT, where you graduated in 2018. You worked with Pytho...

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


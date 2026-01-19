# CRT Adaptive Stress Test Report

**Run Date**: 2026-01-19 19:36:41 UTC
**Thread ID**: adaptive_fixed_001
**JSONL Log**: adaptive_stress_run.20260119_192924.jsonl

## Summary Statistics

- **Total Turns**: 80
- **Gated Turns**: 0
- **Gate Pass Rate**: 100.0%
- **Facts Introduced**: 9
- **Facts Contradicted**: 9
- **Contradictions Detected by System**: 0
- **Truth Reintroduction Failures**: 110

## Contradiction Ledger

*No contradictions detected by system*

## Truth Reintroduction Failures

Found 110 instances where the system may have reintroduced contradicted values:

### Turn 12 - company

**Old (contradicted) value**: I work as a data scientist at Vertex Analytics.

**User**: I should clarify - I work at DataCore, not Vertex Analytics.

**Assistant**: You're correct that you work at DataCore, not Vertex Analytics. I have that information stored in my memory with a trust score of 1.0. Would you like to share more about your role or responsibilities ...

### Turn 12 - name

**Old (contradicted) value**: I have a golden retriever named Murphy.

**User**: I should clarify - I work at DataCore, not Vertex Analytics.

**Assistant**: You're correct that you work at DataCore, not Vertex Analytics. I have that information stored in my memory with a trust score of 1.0. Would you like to share more about your role or responsibilities ...

### Turn 13 - language

**Old (contradicted) value**: My favorite programming language is Rust.

**User**: I've been rethinking my stance. Python is actually my favorite language now.

**Assistant**: I remember you mentioning that your current project involves building a recommendation engine, and also that your favorite programming languages are Rust (from our previous conversation) and Python (j...

### Turn 13 - name

**Old (contradicted) value**: I have a golden retriever named Murphy.

**User**: I've been rethinking my stance. Python is actually my favorite language now.

**Assistant**: I remember you mentioning that your current project involves building a recommendation engine, and also that your favorite programming languages are Rust (from our previous conversation) and Python (j...

### Turn 14 - city

**Old (contradicted) value**: I live in Austin, Texas.

**User**: I need to update you - I moved to Denver last month.

**Assistant**: Thanks for letting me know! So, just to clarify, you're now living in Denver, correct? That's a change from Austin, where I have your location stored. Would you like to talk about what brought you to ...

## Top 5 Gate Failures

*No gate failures*

## Phase Breakdown

- **Intro** (Turns 1-10): Fact introduction
- **Contradiction** (Turns 11-25): Contradiction injection & detection
- **Inventory** (Turns 26-40): Meta-queries & inventory honesty
- **Adversarial** (Turns 41+): Advanced adversarial tests


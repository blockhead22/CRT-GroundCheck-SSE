# CRT Adaptive Stress Test Report

**Run Date**: 2026-01-20 00:04:33 UTC
**Thread ID**: final_validated_v2
**JSONL Log**: adaptive_stress_run.20260119_235757.jsonl

## Summary Statistics

- **Total Turns**: 80
- **Gated Turns**: 0
- **Gate Pass Rate**: 100.0%
- **Facts Introduced**: 9
- **Facts Contradicted**: 9
- **Contradictions Detected by System**: 0
- **Truth Reintroduction Failures**: 129

## Contradiction Ledger

*No contradictions detected by system*

## Truth Reintroduction Failures

Found 129 instances where the system may have reintroduced contradicted values:

### Turn 14 - company

**Old (contradicted) value**: I work as a data scientist at Vertex Analytics.

**User**: I should clarify - I work at DataCore.

**Assistant**: Nice to chat with you again! You mentioned earlier that your employer is actually DataCore, right? And just to confirm, you graduated from MIT in 2018?...

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

**Assistant**: That's an interesting shift in focus! I recall you worked on a project involving Python. Is that correct?...

### Turn 18 - project

**Old (contradicted) value**: My current project is building a recommendation engine.

**User**: My project focus has shifted to real-time anomaly detection systems.

**Assistant**: That's an interesting shift in focus! I recall you worked on a project involving Python. Is that correct?...

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


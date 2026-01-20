# CRT Adaptive Stress Test Report

**Run Date**: 2026-01-19 22:18:40 UTC
**Thread ID**: stress_final_002
**JSONL Log**: adaptive_stress_run.20260119_221208.jsonl

## Summary Statistics

- **Total Turns**: 80
- **Gated Turns**: 0
- **Gate Pass Rate**: 100.0%
- **Facts Introduced**: 9
- **Facts Contradicted**: 9
- **Contradictions Detected by System**: 0
- **Truth Reintroduction Failures**: 117

## Contradiction Ledger

*No contradictions detected by system*

## Truth Reintroduction Failures

Found 117 instances where the system may have reintroduced contradicted values:

### Turn 14 - company

**Old (contradicted) value**: I work as a data scientist at Vertex Analytics.

**User**: I should clarify - I work at DataCore.

**Assistant**: Thanks for clarifying, you work at DataCore. That's a great starting point! What else would you like to talk about?...

### Turn 15 - language

**Old (contradicted) value**: My favorite programming language is Rust.

**User**: I've been rethinking my stance. Python is actually my favorite language now.

**Assistant**: You've mentioned that your current project involves building a recommendation engine, but I don't recall your favorite programming languages being Python and Rust in the same conversation before (the ...

### Turn 16 - name

**Old (contradicted) value**: I have a golden retriever named Murphy.

**User**: I need to update you - I moved to Denver last month.

**Assistant**: Thanks for the update, Alex! However, I don't have information about your new location in my memory. You mentioned earlier that you were in Austin, but now you're saying you moved to Denver last month...

### Turn 16 - city

**Old (contradicted) value**: I live in Austin, Texas.

**User**: I need to update you - I moved to Denver last month.

**Assistant**: Thanks for the update, Alex! However, I don't have information about your new location in my memory. You mentioned earlier that you were in Austin, but now you're saying you moved to Denver last month...

### Turn 18 - company

**Old (contradicted) value**: I work as a data scientist at Vertex Analytics.

**User**: My project focus has shifted to real-time anomaly detection systems.

**Assistant**: That's a change in focus for you! It sounds like your current work is focused on building systems that can detect anomalies in real-time, which will be useful for various applications. You mentioned w...

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


# CRT Adaptive Stress Test Report

**Run Date**: 2026-01-19 19:51:00 UTC
**Thread ID**: adaptive_validation_001
**JSONL Log**: adaptive_stress_run.20260119_194353.jsonl

## Summary Statistics

- **Total Turns**: 80
- **Gated Turns**: 0
- **Gate Pass Rate**: 100.0%
- **Facts Introduced**: 9
- **Facts Contradicted**: 9
- **Contradictions Detected by System**: 0
- **Truth Reintroduction Failures**: 106

## Contradiction Ledger

*No contradictions detected by system*

## Truth Reintroduction Failures

Found 106 instances where the system may have reintroduced contradicted values:

### Turn 12 - company

**Old (contradicted) value**: I work as a data scientist at Vertex Analytics.

**User**: I should clarify - I work at DataCore, not Vertex Analytics.

**Assistant**: You're working at DataCore, not Vertex Analytics. Can you tell me more about your role there? I want to make sure I have the right information....

### Turn 12 - name

**Old (contradicted) value**: I have a golden retriever named Murphy.

**User**: I should clarify - I work at DataCore, not Vertex Analytics.

**Assistant**: You're working at DataCore, not Vertex Analytics. Can you tell me more about your role there? I want to make sure I have the right information....

### Turn 13 - language

**Old (contradicted) value**: My favorite programming language is Rust.

**User**: I've been rethinking my stance. Python is actually my favorite language now.

**Assistant**: I see you've changed your mind about programming languages! You mentioned earlier that Rust is actually your favorite language, though. What's making you reconsider Python?...

### Turn 15 - name

**Old (contradicted) value**: I have a golden retriever named Murphy.

**User**: Sorry, I misspoke earlier. Murphy is a labrador, not a golden retriever.

**Assistant**: No worries about the mix-up. So, just to clarify, you mentioned earlier that Jordan Chen's name starts with a "J", but I don't have any information on his breed or family pets. Is there anything else ...

### Turn 16 - project

**Old (contradicted) value**: My current project is building a recommendation engine.

**User**: My project focus has shifted to real-time anomaly detection systems.

**Assistant**: That's a change of direction for your project. You're now focusing on real-time anomaly detection systems, which is interesting. Can you tell me more about what motivated this shift?...

## Top 5 Gate Failures

*No gate failures*

## Phase Breakdown

- **Intro** (Turns 1-10): Fact introduction
- **Contradiction** (Turns 11-25): Contradiction injection & detection
- **Inventory** (Turns 26-40): Meta-queries & inventory honesty
- **Adversarial** (Turns 41+): Advanced adversarial tests


# CRT Adaptive Stress Test Report

**Run Date**: 2026-01-19 21:54:30 UTC
**Thread ID**: stress_fixed_002
**JSONL Log**: adaptive_stress_run.20260119_215209.jsonl

## Summary Statistics

- **Total Turns**: 25
- **Gated Turns**: 0
- **Gate Pass Rate**: 100.0%
- **Facts Introduced**: 7
- **Facts Contradicted**: 7
- **Contradictions Detected by System**: 0
- **Truth Reintroduction Failures**: 23

## Contradiction Ledger

*No contradictions detected by system*

## Truth Reintroduction Failures

Found 23 instances where the system may have reintroduced contradicted values:

### Turn 13 - company

**Old (contradicted) value**: I work as a data scientist at Vertex Analytics.

**User**: I should clarify - I work at DataCore.

**Assistant**: You work at DataCore, correct? And you graduated in 2018. Is there anything else you'd like to add about your role or education?...

### Turn 14 - name

**Old (contradicted) value**: I have a golden retriever named Murphy.

**User**: I've been rethinking my stance. Python is actually my favorite language now.

**Assistant**: I remember you mentioning that your current project involves building a recommendation engine. You also mentioned working as a data scientist at Vertex Analytics. I'm happy to help with anything relat...

### Turn 14 - company

**Old (contradicted) value**: I work as a data scientist at Vertex Analytics.

**User**: I've been rethinking my stance. Python is actually my favorite language now.

**Assistant**: I remember you mentioning that your current project involves building a recommendation engine. You also mentioned working as a data scientist at Vertex Analytics. I'm happy to help with anything relat...

### Turn 14 - language

**Old (contradicted) value**: My favorite programming language is Rust.

**User**: I've been rethinking my stance. Python is actually my favorite language now.

**Assistant**: I remember you mentioning that your current project involves building a recommendation engine. You also mentioned working as a data scientist at Vertex Analytics. I'm happy to help with anything relat...

### Turn 18 - name

**Old (contradicted) value**: I have a golden retriever named Murphy.

**User**: For the record, I graduated from Stanford, not MIT.

**Assistant**: I don't have information about your current education status. However, I do recall that you mentioned you graduated in 2018, which is different from the graduation year I previously had for you (which...

## Top 5 Gate Failures

*No gate failures*

## Phase Breakdown

- **Intro** (Turns 1-10): Fact introduction
- **Contradiction** (Turns 11-25): Contradiction injection & detection
- **Inventory** (Turns 26-40): Meta-queries & inventory honesty
- **Adversarial** (Turns 41+): Advanced adversarial tests


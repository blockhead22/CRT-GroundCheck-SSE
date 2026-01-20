# CRT Adaptive Stress Test Report

**Run Date**: 2026-01-19 19:57:33 UTC
**Thread ID**: debug_name_001
**JSONL Log**: adaptive_stress_run.20260119_195605.jsonl

## Summary Statistics

- **Total Turns**: 15
- **Gated Turns**: 0
- **Gate Pass Rate**: 100.0%
- **Facts Introduced**: 9
- **Facts Contradicted**: 5
- **Contradictions Detected by System**: 0
- **Truth Reintroduction Failures**: 5

## Contradiction Ledger

*No contradictions detected by system*

## Truth Reintroduction Failures

Found 5 instances where the system may have reintroduced contradicted values:

### Turn 12 - company

**Old (contradicted) value**: I work as a data scientist at Vertex Analytics.

**User**: I should clarify - I work at DataCore, not Vertex Analytics.

**Assistant**: You mentioned you work at DataCore, which is your employer. You also mentioned a graduation year of 2018, but I don't have information on that specific detail. Can you tell me more about what you'd li...

### Turn 12 - name

**Old (contradicted) value**: I have a golden retriever named Murphy.

**User**: I should clarify - I work at DataCore, not Vertex Analytics.

**Assistant**: You mentioned you work at DataCore, which is your employer. You also mentioned a graduation year of 2018, but I don't have information on that specific detail. Can you tell me more about what you'd li...

### Turn 13 - language

**Old (contradicted) value**: My favorite programming language is Rust.

**User**: I've been rethinking my stance. Python is actually my favorite language now.

**Assistant**: I think there's a bit of a contradiction here! According to your memory, I recall that you mentioned Python as your favorite programming language earlier (fact #1), but now you're saying it's actually...

### Turn 14 - city

**Old (contradicted) value**: I live in Austin, Texas.

**User**: I need to update you - I moved to Denver last month.

**Assistant**: Thanks for the update! Just to clarify, I don't have information about your new location. You mentioned earlier that you're in Austin, but now you're telling me you moved to Denver - I'll make sure to...

### Turn 14 - name

**Old (contradicted) value**: I have a golden retriever named Murphy.

**User**: I need to update you - I moved to Denver last month.

**Assistant**: Thanks for the update! Just to clarify, I don't have information about your new location. You mentioned earlier that you're in Austin, but now you're telling me you moved to Denver - I'll make sure to...

## Top 5 Gate Failures

*No gate failures*

## Phase Breakdown

- **Intro** (Turns 1-10): Fact introduction
- **Contradiction** (Turns 11-25): Contradiction injection & detection
- **Inventory** (Turns 26-40): Meta-queries & inventory honesty
- **Adversarial** (Turns 41+): Advanced adversarial tests


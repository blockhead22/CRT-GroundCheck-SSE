# CRT Adaptive Stress Test Report

**Run Date**: 2026-01-19 23:31:10 UTC
**Thread ID**: stress_validation_001
**JSONL Log**: adaptive_stress_run.20260119_232442.jsonl

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

### Turn 14 - company

**Old (contradicted) value**: I work as a data scientist at Vertex Analytics.

**User**: I should clarify - I work at DataCore.

**Assistant**: That's great to know, you work at DataCore. By the way, what brings you here today?...

### Turn 15 - name

**Old (contradicted) value**: I have a golden retriever named Murphy.

**User**: I've been rethinking my stance. Python is actually my favorite language now.

**Assistant**: I think there's a bit of a change in heart! You initially mentioned Rust as your preferred programming language, but now you're saying Python is your favorite? I'm happy to help you explore these shif...

### Turn 15 - language

**Old (contradicted) value**: My favorite programming language is Rust.

**User**: I've been rethinking my stance. Python is actually my favorite language now.

**Assistant**: I think there's a bit of a change in heart! You initially mentioned Rust as your preferred programming language, but now you're saying Python is your favorite? I'm happy to help you explore these shif...

### Turn 16 - name

**Old (contradicted) value**: I have a golden retriever named Murphy.

**User**: I need to update you - I moved to Denver last month.

**Assistant**: So, it sounds like you're saying that your location is now Denver? That's new information. I don't have anything on record about your move to Denver yet. Can you tell me more about what brought you to...

### Turn 17 - name

**Old (contradicted) value**: I have a golden retriever named Murphy.

**User**: Sorry, I misspoke earlier. Murphy is a labrador, not a golden retriever.

**Assistant**: No problem, sorry about the mix-up! Just to clarify, according to my memory, you mentioned having a pet that's a golden retriever named Murphy, but now I see it's actually a labrador. I'll make sure t...

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


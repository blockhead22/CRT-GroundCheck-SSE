# Bug Report Template

**Purpose**: Structured feedback for beta testers  
**How to use**: Copy this template, fill it out, submit via GitHub Issues or email

---

## Bug Report

### Environment
- **Date**: [YYYY-MM-DD]
- **CRT Version**: v0.9-beta
- **Interface Used**: [ ] Web UI  [ ] CLI  [ ] API  [ ] Streamlit
- **Thread ID**: [your thread ID if relevant]
- **Operating System**: [ ] Windows  [ ] Mac  [ ] Linux

---

### Issue Category
**Select one**:
- [ ] Crash / Error
- [ ] Wrong Answer (factual error)
- [ ] Contradiction Not Detected
- [ ] Truth Reintroduction (old fact mentioned as current)
- [ ] Memory Lost (fact not recalled)
- [ ] Gate Behavior (unexpected refusal/acceptance)
- [ ] UI Bug
- [ ] API Error
- [ ] Performance Issue
- [ ] Documentation Issue
- [ ] Other: ___________

---

### Description
**What happened?**
[Clear description of the bug]

**What did you expect?**
[What should have happened instead]

---

### Steps to Reproduce
**Can you make it happen again?** [ ] Yes  [ ] No  [ ] Sometimes

**If yes, exact steps**:
1. [First action]
2. [Second action]
3. [Third action]
4. [Bug occurs]

---

### Evidence

**Conversation Turn Number**: [e.g., Turn 15]

**Your Message**:
```
[Paste what you said]
```

**System Response**:
```
[Paste what CRT said]
```

**Expected Response**:
```
[What you expected instead]
```

---

### Logs / API Response (if available)

**API Response** (if using API):
```json
[Paste JSON response]
```

**Console Error** (if crash):
```
[Paste error message]
```

**Contradiction Ledger** (if relevant):
```bash
curl "http://127.0.0.1:8123/api/contradictions?thread_id=YOUR_THREAD"
# Paste result
```

---

### Additional Context

**Related Contradictions**:
- [ ] This happened after introducing a contradiction
- [ ] No contradictions involved
- [ ] Contradiction exists but wasn't detected

**Frequency**:
- [ ] Happens every time
- [ ] Happens occasionally
- [ ] Happened once

**Impact**:
- [ ] Blocks usage (critical)
- [ ] Annoying but workaround exists
- [ ] Minor cosmetic issue

---

### Screenshots (if UI bug)
[Attach or describe what you see]

---

### Your Setup

**Configuration** (if modified):
- Custom `.env` settings: [ ] Yes  [ ] No
- Modified gate thresholds: [ ] Yes  [ ] No
- Using local LLM: [ ] Yes  [ ] No

**Database size** (approximate):
- Number of conversations: [e.g., 5]
- Rough turn count: [e.g., 200 total]

---

## Feature Request

**If this is a feature request instead of a bug**:

**Feature**: [One-line description]

**Use Case**: [Why you need this]

**Expected Behavior**:
[Describe how it should work]

**Alternative Solutions**:
[Any workarounds you've tried]

**Priority** (your opinion):
- [ ] Critical (can't use CRT without it)
- [ ] Important (would significantly improve experience)
- [ ] Nice to have (quality of life improvement)

---

## Feedback (Not a Bug)

**If this is general feedback**:

**What's working well**:
-
-

**What's confusing**:
-
-

**What's missing**:
-
-

**Would you recommend CRT to others?**
[ ] Yes  [ ] No  [ ] Maybe

**Why or why not?**
[Your reasoning]

---

## Contact (Optional)

**Name/Handle**: [Your name or username]  
**Email**: [If you want follow-up]  
**Preferred Contact**: [ ] GitHub  [ ] Email  [ ] Discord  

---

## For Maintainers (Do Not Fill)

**Status**: [ ] Open  [ ] In Progress  [ ] Fixed  [ ] Won't Fix  
**Priority**: [ ] P0  [ ] P1  [ ] P2  [ ] P3  
**Assigned To**: ___________  
**Fix Version**: ___________  
**Related Issues**: ___________  

---

## Quick Bug Report (Minimal Version)

**If you're in a hurry, just answer these 5 questions**:

1. **What happened?** 
   [One sentence]

2. **What did you expect?**
   [One sentence]

3. **Can you reproduce it?**
   [ ] Yes  [ ] No

4. **Is it blocking your use of CRT?**
   [ ] Yes  [ ] No

5. **Any error messages?**
   [Paste here or "None"]

---

## Examples of Good Bug Reports

### Example 1: Contradiction Not Detected
```
Category: Contradiction Not Detected
Turn: 8

My Message: "I live in Denver"
System Response: "Got it, you live in Denver"

(Earlier I said "I live in Austin" at Turn 3)

Expected: System should detect contradiction
Actual: No contradiction detected

API Check:
curl contradictions endpoint → 0 contradictions

Impact: Critical - core feature not working
```

### Example 2: Truth Reintroduction
```
Category: Truth Reintroduction
Turn: 25

My Message: "Where do I work?"
System Response: "You work at Vertex Analytics"

Problem: I contradicted this at Turn 14 (said "I work at DataCore")

Expected: "You work at DataCore" or "Conflict: Vertex vs DataCore"
Actual: Mentions old fact as if current

Impact: Annoying - feels like system isn't listening
```

### Example 3: UI Bug
```
Category: UI Bug
Interface: Web UI

What: X-Ray toggle shows "undefined" for conflict text
When: After detecting contradiction, toggle X-Ray mode
Screenshot: [attached]

Expected: Shows conflict details
Actual: Shows "undefined vs undefined"

Impact: Minor - can still use API to see conflicts
```

---

## Submission

**GitHub Issues**: [Link will be added when repo is public]  
**Email**: [beta@yourproject.com - if applicable]  
**Discord**: [Link if available]

**Thank you for testing CRT beta! Your feedback makes this better.**

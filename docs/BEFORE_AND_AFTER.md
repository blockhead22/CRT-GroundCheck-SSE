# Before CRT vs After CRT

**A side-by-side comparison showing why this project matters**

---

## Scenario: User Changes Jobs

### 🔴 Before CRT (Standard AI Memory System)

```
DAY 1
User: "I work at Microsoft."
AI:   "Got it! I'll remember you work at Microsoft."

DAY 2
User: "Actually, I work at Amazon now."
AI:   "Understood! Updated your employer to Amazon."

DAY 3
User: "Where do I work?"
AI:   "You work at Amazon."

User: "Wait, don't you remember I used to work at Microsoft?"
AI:   "I don't have any information about you working at Microsoft."
```

**Problems:**
- ❌ Silently overwrote Microsoft with Amazon
- ❌ Lost historical information
- ❌ No acknowledgment of the change
- ❌ User can't verify what they actually told the system

---

### ✅ After CRT (Contradiction-Preserving Memory)

```
DAY 1
User: "I work at Microsoft."
CRT:  "Got it! I'll remember you work at Microsoft."
      [Stored: company="Microsoft", trust=0.9, timestamp=Day1]

DAY 2
User: "Actually, I work at Amazon now."
CRT:  "I see there's a change in your employer. I have you working at 
       Microsoft from before. Are you saying you've moved to Amazon, or 
       did I misunderstand?"
      
User: "Yes, I left Microsoft and joined Amazon."
CRT:  "Got it! I've updated this and preserved the history."
      [Stored: company="Amazon", trust=0.9, timestamp=Day2]
      [Ledger: Microsoft ↔ Amazon contradiction logged]
      [Microsoft memory: marked as "superseded"]

DAY 3
User: "Where do I work?"
CRT:  "You work at Amazon (most recent update)."
      
      Metadata shown:
      - reintroduced_claims_count: 2
      - contradicted_memories: ["Microsoft", "Amazon"]
      - current_belief: "Amazon"
      
User: "What's my work history?"
CRT:  "Based on what you've told me:
       - Microsoft (until recently)
       - Amazon (current)"
```

**Benefits:**
- ✅ Both memories preserved
- ✅ Contradiction detected and logged
- ✅ User explicitly confirms the change
- ✅ Historical information retained
- ✅ Answers include context about conflicts
- ✅ Complete audit trail available

---

## Key Difference: Transparency

### Standard AI
**Philosophy:** *"Always sound confident, even when uncertain"*

```
Question: "Where do I work?"
Answer:   "Amazon."
Reality:  System has conflicting data (Microsoft vs Amazon) 
          but hides it to sound confident.
```

### CRT
**Philosophy:** *"Never lie about uncertainty"*

```
Question: "Where do I work?"
Answer:   "Amazon (most recent update)."
Reality:  System has conflicting data and TELLS YOU about it.
          Metadata shows 2 contradicted claims.
```

---

## Real-World Impact

### Example 1: Personal Assistant
**Without CRT:**
- Gradually invents facts you never said
- Loses track of changes over time
- Can't explain why it believes something

**With CRT:**
- Only stores what you explicitly stated
- Preserves all updates with timestamps
- Shows provenance for every claim

### Example 2: Customer Service Bot
**Without CRT:**
- Silently overwrites customer preferences
- Gives contradictory information across sessions
- Can't trace why recommendations changed

**With CRT:**
- Preserves preference evolution
- Acknowledges when recommendations conflict with history
- Full audit trail for compliance

### Example 3: Research Assistant
**Without CRT:**
- Auto-resolves conflicting evidence (may pick wrong source)
- Synthesizes "facts" by combining incompatible sources
- Hides uncertainty in confident-sounding language

**With CRT:**
- Preserves all conflicting evidence
- Explicitly states when sources disagree
- Never synthesizes beyond what sources actually say

---

## The Bottom Line

| Aspect | Standard AI | CRT |
|--------|-------------|-----|
| **Memory approach** | Overwrite when conflicting | Preserve all, flag conflicts |
| **Uncertainty handling** | Hide it, sound confident | Surface it, disclose conflicts |
| **Trust over time** | Erodes (drift, invention) | Maintained (traceable, honest) |
| **Audit trail** | None or minimal | Complete contradiction ledger |
| **When uncertain** | Guess convincingly | Say "I have conflicting info" |

---

**This is why CRT exists.**

Standard AI memory systems optimize for *sounding good once*.  
CRT optimizes for *staying trustworthy forever*.

---

**Want to see it in action?**
- [5-minute demo](QUICKSTART.md)
- [Why it matters](PURPOSE.md)
- [Technical details](CRT_REINTRODUCTION_INVARIANT.md)

---

*Last updated: 2026-01-21*

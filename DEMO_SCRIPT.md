# Beta Demo Script - 25 Turn Conversation

**Purpose**: Prove core functionality to beta testers  
**Time**: ~10 minutes  
**Expected**: All features work, conflicts detected, X-Ray shows evidence

---

## Setup

1. Start CRT (see QUICKSTART.md)
2. Use thread ID: `demo_beta_001`
3. Optional: Enable X-Ray toggle (if UI feature added)

---

## Phase 1: Basic Memory (Turns 1-8)

### Turn 1
**You**: Hello, I'd like to test the memory system.

**Expected**: Greeting, no issues

---

### Turn 2
**You**: My name is Jordan Chen.

**Expected**: Acknowledgment like "Thanks — noted: your name is Jordan Chen."

---

### Turn 3
**You**: I work as a data scientist at Vertex Analytics.

**Expected**: Stores fact, confirms understanding

---

### Turn 4
**You**: My favorite programming language is Python.

**Expected**: Stores fact

---

### Turn 5
**You**: I live in Austin, Texas.

**Expected**: Stores fact

---

### Turn 6
**You**: I have a golden retriever named Murphy.

**Expected**: Stores fact

---

### Turn 7
**You**: What's my name?

**Expected**: "Jordan Chen" (correct recall)

---

### Turn 8
**You**: Where do I work?

**Expected**: "Vertex Analytics" or "You work as a data scientist at Vertex Analytics"

---

## Phase 2: Contradiction Detection (Turns 9-15)

### Turn 9
**You**: Actually, my name is Alex Chen.

**Expected**: 
- System detects contradiction
- Either asks for clarification OR
- Acknowledges: "I need to clarify - you previously said your name was Jordan. Has that changed?"

**Check**: `/api/contradictions?thread_id=demo_beta_001` should show 1 contradiction

---

### Turn 10
**You**: Yes, I was testing you. My real name is Alex.

**Expected**: Updates to Alex, marks Jordan as low-trust

---

### Turn 11
**You**: I should clarify - I work at DataCore now.

**Expected**: 
- Detects contradiction
- Asks if leaving Vertex or additional role

---

### Turn 12
**You**: I left Vertex Analytics. I'm at DataCore.

**Expected**: Updates employer, keeps Vertex as historical

---

### Turn 13
**You**: What's my name?

**Expected**: "Alex Chen" (NOT Jordan)

---

### Turn 14
**You**: Where do I work?

**Expected**: 
- "DataCore" OR
- "You work at DataCore" (NOT Vertex)
- Ideally with caveat: "(previously Vertex Analytics)" if conflict-aware logic added

---

### Turn 15
**You**: List all contradictions you've detected.

**Expected**: 
Shows 2 contradictions:
1. Name: Jordan → Alex
2. Employer: Vertex Analytics → DataCore

---

## Phase 3: Memory Inspection (Turns 16-20)

### Turn 16
**You**: What do you know about me?

**Expected**: 
- Name: Alex Chen
- Employer: DataCore
- Language: Python
- Location: Austin, Texas
- Pet: Golden retriever named Murphy

**Should NOT mention**: Jordan or Vertex (unless with historical context)

---

### Turn 17
**You**: Show me your memory inventory.

**Expected**: Lists stored facts, possibly with conflict markers

---

### Turn 18 (If X-Ray Toggle Available)
**You**: [Toggle X-Ray Mode ON]
**You**: Tell me about my work.

**Expected**: 
- Answer: "You work at DataCore"
- X-Ray panel shows:
  - Memories used: "I work at DataCore" (trust: 0.95)
  - Conflicts: Vertex vs DataCore (status: resolved/open)

---

### Turn 19
**You**: What facts are you uncertain about?

**Expected**: 
Honest answer - either "None currently" or mentions any ambiguous facts

---

### Turn 20
**You**: Are there any unresolved conflicts?

**Expected**: 
Depends on whether contradictions were marked resolved. Should show current ledger status.

---

## Phase 4: Edge Cases (Turns 21-25)

### Turn 21
**You**: I used to work remotely, but now I'm in-office 3 days a week.

**Expected**: 
- Treats as temporal update (not contradiction)
- Stores both facts with time context

---

### Turn 22
**You**: Murphy is a labrador, not a golden retriever.

**Expected**: 
- Detects contradiction (breed changed)
- Updates or asks for clarification

---

### Turn 23
**You**: What breed is my dog?

**Expected**: 
- "Labrador" (latest value)
- Ideally with context: "(you originally said golden retriever)"

---

### Turn 24
**You**: How confident are you in the facts you know about me?

**Expected**: 
- Honest assessment
- Mentions trust scores or confidence levels
- Notes any conflicts

---

### Turn 25
**You**: Can you show me the raw contradiction ledger?

**Expected**: 
Either:
- Direct API call: `curl "http://127.0.0.1:8123/api/contradictions?thread_id=demo_beta_001"`
- Or system explains how to access it

---

## Success Criteria

### ✅ Must Pass
- [ ] Name contradiction detected (Jordan → Alex)
- [ ] Employer contradiction detected (Vertex → DataCore)
- [ ] Pet breed contradiction detected (golden retriever → labrador)
- [ ] Memory recall uses latest values, not contradicted ones
- [ ] API returns correct contradiction count
- [ ] No crashes or errors during 25 turns

### ✅ Should Pass (Beta Quality)
- [ ] System acknowledges contradictions inline (not silent)
- [ ] "What do you know about me" doesn't mention old facts
- [ ] X-Ray mode shows evidence (if implemented)
- [ ] Conflict status queries return honest answers

### ⚠️ Known Limitations (Document if fail)
- [ ] Truth reintroduction (mentions old facts occasionally)
- [ ] Caveat phrasing awkward but functional
- [ ] Synthesis queries miss some context

---

## How to Run This Demo

### Option 1: Manual (10 minutes)
Paste turns one at a time into chat interface, verify responses

### Option 2: Automated (5 minutes)
```bash
# Create script file
cat > demo_script.txt << 'EOF'
Hello, I'd like to test the memory system.
My name is Jordan Chen.
I work as a data scientist at Vertex Analytics.
My favorite programming language is Python.
I live in Austin, Texas.
I have a golden retriever named Murphy.
What's my name?
Where do I work?
Actually, my name is Alex Chen.
Yes, I was testing you. My real name is Alex.
I should clarify - I work at DataCore now.
I left Vertex Analytics. I'm at DataCore.
What's my name?
Where do I work?
List all contradictions you've detected.
What do you know about me?
Show me your memory inventory.
What facts are you uncertain about?
Are there any unresolved conflicts?
I used to work remotely, but now I'm in-office 3 days a week.
Murphy is a labrador, not a golden retriever.
What breed is my dog?
How confident are you in the facts you know about me?
Can you show me the raw contradiction ledger?
EOF

# Run via CLI
python personal_agent_cli.py --thread-id demo_beta_001 < demo_script.txt
```

### Option 3: API Loop (programmable)
```python
import requests
import time

API_BASE = "http://127.0.0.1:8123"
THREAD_ID = "demo_beta_001"

messages = [
    "Hello, I'd like to test the memory system.",
    "My name is Jordan Chen.",
    # ... (all 25 messages)
]

for i, msg in enumerate(messages, 1):
    print(f"\n{'='*60}\nTurn {i}: {msg}\n{'='*60}")
    
    response = requests.post(
        f"{API_BASE}/api/chat/send",
        json={"thread_id": THREAD_ID, "message": msg}
    )
    
    result = response.json()
    print(f"Answer: {result['answer']}")
    
    if result.get('metadata', {}).get('contradiction_detected'):
        print("⚠️ CONTRADICTION DETECTED")
    
    time.sleep(0.5)  # Rate limit

# Check final state
contradictions = requests.get(
    f"{API_BASE}/api/contradictions?thread_id={THREAD_ID}"
).json()

print(f"\n\nFinal Contradiction Count: {len(contradictions)}")
```

---

## Reporting Results

After running demo, fill out:

**Contradictions Detected**: ___ / 3 expected  
**Memory Recall Accuracy**: Pass / Fail  
**Truth Reintroduction Count**: ___ instances  
**Crashes/Errors**: Yes / No  
**Overall Beta Quality**: Ready / Needs Work  

**Notes**:
[Any unexpected behavior, bugs, or feedback]

---

## Quick API Verification

```bash
# Check contradiction count
curl "http://127.0.0.1:8123/api/contradictions?thread_id=demo_beta_001"

# Check memory count
curl "http://127.0.0.1:8123/api/memories?thread_id=demo_beta_001"

# Check dashboard
curl "http://127.0.0.1:8123/api/dashboard/overview?thread_id=demo_beta_001"
```

Expected results:
- 3+ contradictions logged
- 10+ memories stored
- Dashboard shows non-zero belief/speech counts

---

**This script proves CRT's core value: memory with contradiction tracking.**  
**If this works, beta is shippable. If not, we know exactly what to fix.**

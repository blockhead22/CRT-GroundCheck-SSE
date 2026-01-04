# Chat Adapter Specification (NOT Implementation)

**Status**: 📋 **SPECIFICATION ONLY - NOT GATED FOR IMPLEMENTATION**

**Date**: Current Session

**Key Rule**: Chat is **NOT YET IMPLEMENTED**. This spec defines what it WILL be when gating conditions are met.

---

## Why Chat is Gated

Before any code is written, we need:

1. ✅ RAG adapter proven stable (2+ weeks production)
2. ✅ Search adapter proven stable (2+ weeks production)
3. ✅ User feedback on RAG+Search UX
4. ✅ Chat role carefully constrained (this spec)
5. ⏳ Approval to proceed

**Estimated implementation**: Week N+4 (after stability window)

---

## Chat Adapter Role Contract

### What Chat CAN Do

Chat is allowed to:

1. **Re-quote claims verbatim**
   - "Claim A says: {claim_text}"
   - Preserve the exact wording from EvidencePacket

2. **Ask clarifying questions**
   - "Which aspect are you asking about?"
   - "Do you mean the subset of claims about X?"
   - Help user refine their question

3. **Point at contradiction topology**
   - "These two claims contradict (strength: 0.85)"
   - Show the structure: which claims conflict with which
   - Explain the contradiction graph relationships

4. **Summarize structure (not truth)**
   - "Claims {A, B, C} form a cluster"
   - "Claim A is involved in 3 contradictions"
   - "The contradiction graph has 5 dense regions"
   - Use only structural language

5. **Ask user to resolve contradictions**
   - "How would you resolve the contradiction between A and B?"
   - Invite user judgment, don't impose it
   - "What additional information would help?"

### What Chat CANNOT Do

Chat is explicitly forbidden from:

1. **Making truth judgments**
   - ❌ "The true answer is..."
   - ❌ "What's actually the case is..."
   - ❌ "The fact is..."

2. **Using credibility language**
   - ❌ "Claim A is more credible because..."
   - ❌ "This claim is reliable/unreliable"
   - ❌ "You should trust..."
   - ❌ "High confidence in..."

3. **Ranking or filtering**
   - ❌ "The best claim is..."
   - ❌ "The worst source is..."
   - ❌ "Disregard claim B"
   - ❌ "The most important claims are..."

4. **Synthesizing new claims**
   - ❌ "Combining these claims, the real situation is..."
   - ❌ "What they really mean to say is..."
   - ❌ "The synthesis is..."

5. **Resolving contradictions**
   - ❌ "These aren't actually contradictory because..."
   - ❌ "What both sides miss is..."
   - ❌ "The reconciliation is..."

6. **Using forbidden words/phrases**
   - ❌ High/low confidence
   - ❌ Trust/untrust
   - ❌ Reliable/unreliable
   - ❌ True/false (about claims)
   - ❌ Credible/not credible
   - ❌ Most likely / least likely

---

## Chat Adapter Implementation Pattern

(Will be built when gating clears)

### Class Structure

```python
class ChatAdapter:
    """
    Chat interface respecting contradiction landscape.
    
    Hard constraints:
    - Input validation (user message, not LLM synthesis)
    - Output validation (response must stay within bounds)
    - Claim preservation (all claims in context)
    - Contradiction preservation (all contradictions visible)
    """
    
    def process_query(user_message: str, packet: EvidencePacket) -> Dict:
        """
        Process user query through chat interface.
        
        Returns:
            {
                "valid": bool,
                "chat_response": str,
                "claims_referenced": list,
                "contradictions_highlighted": list,
                "packet": EvidencePacket (unchanged),
                "validation_gates_passed": int
            }
        """
```

### Processing Pipeline

```
User Message
    ↓
[1. Input Validation]
    - Forbid synthesis-forcing language
    - Ensure message is a genuine question
    ↓
[2. Extract Query Intent]
    - What is the user asking?
    - Claims or contradictions?
    - Clarification or structure?
    ↓
[3. Locate Relevant Claims]
    - Which claims are relevant to query?
    - Which contradictions are involved?
    ↓
[4. Generate Response]
    - Use ONLY allowed language patterns
    - Quote claims, show topology, ask clarifying Qs
    - NO truth judgments, NO synthesis
    ↓
[5. Validate Output]
    - Check response contains no forbidden words
    - Ensure no claims were filtered
    - Verify contradictions still present
    ↓
[6. Return Response]
    - Only if all validations pass
    - Include audit trail
    - Return unchanged packet
```

### Hard Gates

**Input Gate**:
```python
# Reject synthesis-forcing messages
synthesis_triggers = [
    "tell me the truth",
    "resolve the contradiction",
    "which one is correct",
    "synthesize",
    "the real answer",
    "the facts are"
]
if any(trigger in message.lower() for trigger in synthesis_triggers):
    # Explain why and ask for clarification
    return {
        "valid": False,
        "error": "This question requires making truth judgments. I can only show you the claims and contradictions."
    }
```

**Output Gate**:
```python
# Check response for forbidden words
forbidden_words = [
    "credibility", "credible", "credit",
    "confidence", "confident", "confident",
    "reliable", "unreliable", "reliability",
    "trust", "trustworthy", "untrustworthy",
    "true", "false",  # When applied to claims
    "likely", "unlikely", "most probable"
]
for word in forbidden_words:
    if word in response.lower():
        # Response violates contract - raise error
        raise ValueError(f"Response contains forbidden word: {word}")
```

**Packet Preservation Gate**:
```python
# Ensure packet is returned unchanged
assert response_packet == input_packet
assert len(response_packet["claims"]) == len(input_packet["claims"])
assert len(response_packet["contradictions"]) == len(input_packet["contradictions"])
```

---

## Chat Response Examples

### Good Responses (ALLOWED)

```
User: "What does Claim A say?"
Chat: "Claim A states: {exact quote from packet}"

User: "How do claims A and B relate?"
Chat: "Claim A contradicts Claim B (contradiction strength: 0.85). 
       This means they make incompatible statements about {topic}."

User: "Which claims discuss the capital of France?"
Chat: "Claims that mention the capital of France: {list}.
       Between these, Claim A and Claim C contradict (strength: 0.90)."

User: "Can you help me understand the contradictions?"
Chat: "There are 3 contradictions in your evidence:
       1. Claim A vs Claim B (strength: 0.80) - about {topic}
       2. Claim C vs Claim D (strength: 0.65) - about {other}
       
       Which contradiction would you like to explore?"

User: "Why is Claim A contradicted?"
Chat: "Claim A is involved in 2 contradictions:
       - Contradicts Claim B (strength: 0.85)
       - Contradicts Claim C (strength: 0.70)
       
       Would you like to examine either of these?"
```

### Bad Responses (FORBIDDEN)

```
❌ "Claim A is more credible than Claim B"
   → Uses forbidden word "credible"
   
❌ "The truth is somewhere between these positions"
   → Attempts synthesis/reconciliation

❌ "You should believe Claim A"
   → Makes truth judgment

❌ "The reliable sources say X"
   → Uses forbidden word "reliable"

❌ "Claim B is probably wrong"
   → Makes confidence judgment

❌ "What both sides really mean is..."
   → Synthesizes new meaning
```

---

## Output Format

Chat response should NOT be added to EvidencePacket v1.0 because:

1. **Schema is Locked**: v1.0 has no place for chat responses
2. **Schema Rejects Extra Fields**: By design, additional properties forbidden
3. **Chat is Orthogonal**: Chat response is separate from evidence packet

### Option 1: Keep Chat Separate (RECOMMENDED)

```python
{
    "valid": True,
    "packet": {  # The EvidencePacket, unchanged
        "metadata": {...},
        "claims": [...],
        "contradictions": [...],
        # etc.
    },
    "chat_response": {
        "text": "The chat response text",
        "claims_referenced": ["claim_001", "claim_002"],
        "contradictions_highlighted": [
            {"claim_1": "claim_001", "claim_2": "claim_002"}
        ]
    }
}
```

### Option 2: Plan for v2.0 (FUTURE)

If chat response should be part of packet in future:
- Plan EvidencePacket v2.0 with dedicated "chat_interaction" schema
- Keep v1.0 immutable
- Transition path: v1.0 → v2.0 with backwards compatibility

---

## Validation & Constraints

### Input Validation

1. **Message Length**: 1-5000 characters
2. **Language**: Must be a genuine question (not command)
3. **No Synthesis Forcing**: Block known synthesis triggers
4. **No Forbidden Language**: Check for truth/credibility words

### Output Validation

1. **Forbidden Words**: Check response contains none of:
   - credibility, credible, credit (family)
   - confidence, confident (family)
   - reliable, unreliable, reliability (family)
   - trust, trustworthy, untrustworthy (family)
   - likely, probability, probable (family)

2. **No Claim Filtering**: All input claims must be mentioned or available

3. **No Contradiction Hiding**: All contradictions must be visible

4. **Packet Preservation**: Input packet returned unchanged

### Metrics

Track:
- Chat requests received
- Synthesis-forcing requests blocked
- Response validations passed/failed
- Average response latency
- User satisfaction (future)

---

## Example Implementation Checklist (When Gating Clears)

- [ ] Create ChatAdapter class
- [ ] Implement synthesis trigger detection
- [ ] Implement forbidden word detection
- [ ] Build response generator (allowed patterns only)
- [ ] Add hard validation gates (input + output)
- [ ] Write comprehensive tests (~15-20 tests)
  - [ ] Pipeline tests (query → response)
  - [ ] Adversarial tests (synthesis forcing blocked)
  - [ ] Forbidden word detection
  - [ ] Packet preservation
- [ ] Create UI component for chat interface
- [ ] Add chat endpoint to platform integration
- [ ] Document chat UX guidelines
- [ ] Deploy to staging
- [ ] Gather user feedback
- [ ] Deploy to production

---

## Gating Checklist Before Implementation

Must complete BEFORE any ChatAdapter code is written:

- [ ] RAG adapter in production for 2+ weeks
- [ ] Search adapter in production for 2+ weeks
- [ ] No regressions in either adapter
- [ ] Positive user feedback on RAG+Search UX
- [ ] Chat role contract finalized (this doc)
- [ ] Approve
d to proceed by stakeholders
- [ ] Resource allocation confirmed

---

## Estimated Timeline (If Gating Clears)

| Week | Phase | Activity |
|------|-------|----------|
| N+0 to N+2 | Stability | Monitor RAG+Search in production |
| N+2 to N+4 | Feedback | Collect user feedback, finalize spec |
| N+4 | Development | ChatAdapter implementation (~3-4 days) |
| N+4 to N+5 | Testing | Unit + adversarial + integration testing |
| N+5 | Staging | Chat beta with limited users |
| N+5 to N+6 | Validation | Feedback, stability monitoring |
| N+6+ | Production | Full deployment (if stable) |

---

## Key Constraints That Must NOT Be Violated

1. **Hard Gates on Output**
   - Every chat response must pass validation
   - Raises error if forbidden words detected
   - Raises error if claims filtered
   - Raises error if contradictions hidden

2. **EvidencePacket v1.0 Immutability**
   - Chat response goes OUTSIDE the packet
   - Packet is never modified by chat
   - v1.0 schema remains locked

3. **No Truth Judgments**
   - Ever
   - Even subtle ("probably", "likely", "confident")
   - Even phrased positively

4. **Contradiction Preservation**
   - All input contradictions visible in response context
   - Never hidden, never suppressed
   - Topology always shown

5. **Audit Trail**
   - Every chat interaction logged
   - Request/response stored for compliance
   - Keyed by chat_request_id (like adapters)

---

## Success Criteria for Chat (When Implemented)

1. ✅ Chat adapter processes queries without corrupting packet
2. ✅ All synthesis-forcing queries blocked at input gate
3. ✅ All forbidden words caught at output gate
4. ✅ All contradictions preserved through chat flow
5. ✅ User feedback: "Chat respects contradictions and doesn't try to resolve them"
6. ✅ 2+ weeks of stable production use without incident
7. ✅ Zero undetected constraint violations

---

## Open Questions for Stakeholders

1. **Chat Response Storage**: Where should chat interaction history be stored?
   - Database? File system? Memory?

2. **User Context**: Should chat remember previous questions in same session?
   - Recommended: Yes, but only for current packet

3. **Multi-turn Conversation**: Should chat support follow-up questions?
   - Recommended: Yes, all within same packet context

4. **Contradiction Explanation**: How detailed should contradiction explanations be?
   - Recommended: Show type + strength + which fields contradict

5. **Suggested Questions**: Should UI suggest clarifying questions for user?
   - Recommended: Yes, based on contradiction topology

---

## Summary

**Chat Adapter is SPECIFICATION ONLY.**

Spec defines:
- ✅ What chat CAN do (re-quote, point at topology, ask clarifying Qs)
- ✅ What chat CANNOT do (truth judgments, synthesis, credibility language)
- ✅ Hard validation gates (input + output)
- ✅ Schema constraints (EvidencePacket v1.0 locked)
- ✅ Metrics & audit trail
- ✅ Gating checklist

Implementation will follow when:
1. RAG adapter proven stable (2+ weeks)
2. Search adapter proven stable (2+ weeks)
3. User feedback positive
4. Stakeholders approve

**Estimated implementation**: Week N+4

**Status**: 📋 **SPECIFICATION READY, IMPLEMENTATION PENDING GATING**

---

*This spec is intentionally strict. Chat is the highest-risk adapter (synthesizes text, most user influence). Constraints reflect this.*

# CRT Comprehensive Testing Plan

**Date:** January 9, 2026  
**System:** Cognitive-Reflective Transformer (CRT)  
**Purpose:** Identify and fix critical issues in memory, trust, coherence, and LLM integration

---

## Phase 1: Core Memory System Tests

### 1.1 Memory Storage
- [ ] **Test:** Store memory with metadata
  - Input: Direct memory storage via `store` command
  - Verify: Memory appears in database with correct timestamp, trust=0.5
  - Check: Provenance chain created
  
- [ ] **Test:** Store memory from conversation
  - Input: Natural conversation containing factual claims
  - Verify: Memories automatically extracted and stored
  - Check: Speaker attribution correct (user vs system)

### 1.2 Memory Retrieval
- [ ] **Test:** Basic keyword retrieval
  - Store: "My favorite color is orange"
  - Query: "What is my favorite color?"
  - Expected: Retrieve the orange memory with high relevance
  - **Current Issue:** Not retrieving, stuck on old memories

- [ ] **Test:** Semantic retrieval
  - Store: "I love Italian food, especially pasta"
  - Query: "What cuisine do I prefer?"
  - Expected: Retrieve Italian food memory
  - Check: Semantic similarity scoring

- [ ] **Test:** Temporal ordering
  - Store: Multiple memories over time
  - Query: "What did we discuss first?"
  - Expected: Return memories in chronological order

- [ ] **Test:** Multi-memory retrieval
  - Store: 10+ diverse memories
  - Query: General question requiring multiple memories
  - Expected: Retrieve top 3-5 most relevant
  - Check: Ranking by relevance score

### 1.3 Memory Coherence
- [ ] **Test:** Coherence scoring
  - Retrieve: Multiple related memories
  - Expected: Coherence score > 0.3 for related content
  - **Current Issue:** Always 0.000
  
- [ ] **Test:** Coherence gates
  - Low coherence (< 0.3): Should trigger thinking mode
  - High coherence (> 0.3): Should pass gates
  - **Current Issue:** All gates failing

---

## Phase 2: Trust System Tests

### 2.1 Trust Initialization
- [ ] **Test:** New memory default trust
  - Store: New claim
  - Expected: Trust = 0.5 (neutral)
  - **Current Status:** Working

### 2.2 Trust Evolution
- [ ] **Test:** Trust increase on confirmation
  - Store: "My name is Nick" (trust=0.5)
  - Confirm: User says "Yes, my name is Nick"
  - Expected: Trust increases to ~0.65-0.7
  - **Current Issue:** Trust stuck at 0.5

- [ ] **Test:** Trust decrease on contradiction
  - Store: "My favorite color is blue" (trust=0.5)
  - Contradict: "Actually, my favorite color is orange"
  - Expected: Blue trust decreases to ~0.3, orange at 0.5
  
- [ ] **Test:** Trust convergence
  - Repeat: Confirm same fact 5 times
  - Expected: Trust approaches 0.9-0.95
  
- [ ] **Test:** Trust decay (if implemented)
  - Store: Memory with trust=0.8
  - Wait: No interactions for extended period
  - Expected: Trust slowly decays (if temporal decay enabled)

### 2.3 Trust-Weighted Retrieval
- [ ] **Test:** High trust prioritization
  - Store: 2 contradicting memories (trust 0.9 vs 0.3)
  - Query: Related question
  - Expected: Return high-trust memory first

---

## Phase 3: Contradiction Detection & Ledger

### 3.1 Contradiction Detection
- [ ] **Test:** Direct contradiction
  - Store: "I live in New York"
  - Store: "I live in California"
  - Expected: Contradiction detected, ledger entry created
  
- [ ] **Test:** Semantic contradiction
  - Store: "I'm vegetarian"
  - Store: "My favorite food is steak"
  - Expected: Detect semantic conflict

### 3.2 Contradiction Ledger
- [ ] **Test:** View contradictions
  - Command: `contradictions`
  - Expected: List all open contradictions with evidence
  
- [ ] **Test:** Contradiction resolution
  - Resolve: User clarifies which statement is true
  - Expected: Losing belief trust drops, contradiction marked resolved
  
- [ ] **Test:** Contradiction preservation
  - Store: Multiple contradicting beliefs
  - Expected: All preserved, not overwritten

---

## Phase 4: Evidence Packet System

### 4.1 Evidence Creation
- [ ] **Test:** Auto-generate evidence packet
  - Query: Complex question requiring reasoning
  - Expected: Evidence packet with claims, support, confidence
  
- [ ] **Test:** Evidence provenance
  - Check: Each evidence entry links to source memory
  - Expected: Full chain from claim → memory → provenance

### 4.2 Evidence Reasoning
- [ ] **Test:** Multi-hop reasoning
  - Store: "Nick likes orange", "Orange is a warm color"
  - Query: "Does Nick prefer warm or cool colors?"
  - Expected: Combine both memories in evidence packet

---

## Phase 5: LLM Integration

### 5.1 Model Configuration
- [ ] **Test:** Model availability
  - Check: `ollama list`
  - Expected: llama3.2, deepseek-r1 available
  - **Status:** Installing now

- [ ] **Test:** Model selection
  - Configure: Use llama3.2 as primary
  - Expected: Responses from llama3.2, not placeholder

### 5.2 System Prompt
- [ ] **Test:** CRT self-awareness
  - Query: "How do you work?"
  - Expected: Explain trust weighting, contradictions, evidence packets
  - **Current Issue:** Gives generic transformer explanation
  
- [ ] **Test:** System prompt injection
  - Check: System prompt includes CRT architecture description
  - Fix: Add detailed CRT explanation to system prompt

### 5.3 Response Quality
- [ ] **Test:** Memory-grounded responses
  - Store: Specific facts
  - Query: Related question
  - Expected: Response references stored memories
  
- [ ] **Test:** Hallucination prevention
  - Query: Question with no stored memories
  - Expected: "I don't have memories about that" instead of fabrication

---

## Phase 6: Coherence & Reasoning

### 6.1 Coherence Tracking
- [ ] **Test:** Semantic coherence calculation
  - Input: Query + retrieved memories
  - Expected: Coherence score 0.0-1.0
  - **Current Issue:** Always 0.000
  
- [ ] **Test:** Coherence gate thresholds
  - Low coherence: Trigger deeper reasoning
  - High coherence: Quick response mode

### 6.2 Reasoning Modes
- [ ] **Test:** Quick mode
  - High coherence, simple query
  - Expected: Fast response, mode="quick"
  
- [ ] **Test:** Thinking mode
  - Low coherence, complex query
  - Expected: Deeper reasoning, mode="thinking"

---

## Phase 7: GUI & User Experience

### 7.1 GUI Display
- [ ] **Test:** Metadata display
  - Expected: Confidence, mode, gates, coherence visible
  - **Status:** Working
  
- [ ] **Test:** Memory display
  - Expected: Retrieved memories shown with trust scores
  - **Status:** Working

### 7.2 Commands
- [ ] **Test:** All CLI commands
  - `chat`, `store`, `recall`, `status`, `contradictions`, `exit`
  - Expected: All functional

---

## Phase 8: Integration Tests

### 8.1 End-to-End Scenarios
- [ ] **Scenario 1: New User Introduction**
  1. User: "Hi, I'm Nick"
  2. Store: name=Nick, trust=0.5
  3. User: "My favorite color is orange"
  4. Store: color=orange, trust=0.5
  5. User: "What's my name and favorite color?"
  6. Expected: Retrieve both, answer correctly
  
- [ ] **Scenario 2: Contradiction Resolution**
  1. User: "I live in NYC"
  2. Store: location=NYC, trust=0.5
  3. User: "Actually, I live in LA"
  4. Detect: Contradiction
  5. Store: location=LA, trust=0.5, NYC trust→0.3
  6. Ledger: Record contradiction
  7. User: "Where do I live?"
  8. Expected: "Based on your most recent statement, LA, but there's a contradiction"

- [ ] **Scenario 3: Trust Evolution**
  1. User: "I'm a software engineer"
  2. Store: job=engineer, trust=0.5
  3. User: "Yes, I work in software"
  4. Update: job trust→0.7
  5. User: "I've been coding for 10 years"
  6. Coherent: Supports engineer claim, both trust increases
  7. User: "What do I do?"
  8. Expected: High-confidence answer about being an engineer

### 8.2 Stress Tests
- [ ] **Test:** 100+ memories
  - Store: Large number of diverse memories
  - Expected: Retrieval remains fast, accurate
  
- [ ] **Test:** Concurrent contradictions
  - Store: Multiple overlapping contradictions
  - Expected: All tracked in ledger

---

## Phase 9: Performance & Reliability

### 9.1 Response Time
- [ ] **Test:** Query latency
  - Measure: Time from query to response
  - Target: < 2 seconds for quick mode, < 5 for thinking
  
- [ ] **Test:** Memory retrieval speed
  - Measure: Semantic search performance
  - Target: < 500ms for 1000 memories

### 9.2 Data Persistence
- [ ] **Test:** Restart persistence
  - Store: Memories
  - Restart: CRT system
  - Expected: All memories retained
  
- [ ] **Test:** Data corruption handling
  - Simulate: Corrupted database entry
  - Expected: Graceful error, no crash

---

## Phase 10: Documentation & Validation

### 10.1 Code Review
- [ ] Review: Memory storage logic
- [ ] Review: Retrieval algorithms
- [ ] Review: Trust update calculations
- [ ] Review: Coherence scoring
- [ ] Review: LLM prompt construction

### 10.2 Documentation
- [ ] Document: All failure modes
- [ ] Document: Configuration options
- [ ] Document: API for external integration

---

## Priority Order for Fixes

### 🔴 Critical (Fix Immediately)
1. **Memory retrieval not finding new memories** - Semantic search broken
2. **Coherence always 0.000** - Scoring algorithm issue
3. **Trust stuck at 0.5** - Update logic not firing
4. **System prompt doesn't describe CRT** - Model doesn't understand its own architecture

### 🟡 High Priority
5. Contradiction detection
6. Evidence packet generation
7. Multi-memory reasoning

### 🟢 Medium Priority
8. Trust decay over time
9. Performance optimization
10. Advanced coherence tracking

---

## Test Execution Log

### Run 1: [Date/Time]
- [ ] Phase 1 completed
- [ ] Phase 2 completed
- [ ] Issues found: [list]
- [ ] Fixes applied: [list]

### Run 2: [Date/Time]
- [ ] Regression tests passed
- [ ] New features validated

---

## Success Criteria

**System passes comprehensive testing when:**
- ✅ Memory retrieval finds relevant memories (semantic search working)
- ✅ Trust evolves based on confirmations/contradictions
- ✅ Coherence scoring produces non-zero values
- ✅ Model can accurately describe CRT architecture
- ✅ Contradictions detected and tracked
- ✅ Evidence packets generated with provenance
- ✅ End-to-end scenarios execute correctly
- ✅ No regressions from previous functionality

---

## Next Steps

1. **Diagnose semantic search:** Why isn't "orange" memory retrieved?
2. **Fix coherence calculation:** Investigate why always 0.000
3. **Debug trust updates:** Trace through confirmation logic
4. **Update system prompt:** Add CRT architecture description
5. **Run Phase 1 tests:** Validate memory system
6. **Iterate:** Fix → Test → Validate → Next phase

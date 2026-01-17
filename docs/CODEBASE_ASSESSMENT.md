# CRT Codebase Assessment - January 16, 2026

## Executive Summary

Comprehensive analysis of CRT's major code modules identifying:
1. **Logic strengthening opportunities** - Where current implementation could be more robust
2. **Learning process gaps** - Where learned/adaptive processes could enhance the system
3. **RAG limitations** - Where standard chat-based RAG falls short

---

## 1. Gate Logic (crt_rag.py + crt_core.py)

### Current Status: ⚠️ **MAJOR BLOCKER**

**Gate Pass Rate: 33% (67% false positive rejection rate)**

### Problem Analysis

**Location:** `personal_agent/crt_core.py:362-410` (check_reconstruction_gates)

**Current Implementation:**
```python
def check_reconstruction_gates(
    self, intent_align, memory_align, 
    has_grounding_issues, has_contradiction_issues, has_extraction_issues
):
    if has_grounding_issues:
        return False, "grounding_fail"
    if has_contradiction_issues:
        return False, "contradiction_fail"
    if has_extraction_issues:
        return False, "extraction_fail"
    if intent_align < self.config.theta_intent:  # theta_intent = 0.5
        return False, f"intent_fail (align={intent_align:.3f})"
    if memory_align < self.config.theta_mem:  # theta_mem = 0.38
        return False, f"memory_fail (align={memory_align:.3f})"
    return True, "gates_passed"
```

**Root Causes of 67% Failure Rate:**

1. **Binary thresholds are too rigid**
   - Intent threshold (0.5) rejects explanatory answers
   - Memory threshold (0.38) rejects synthesized responses
   - No gradient between "grounded fact" and "reasonable synthesis"

2. **Instruction detection is overzealous** (crt_rag.py:330-450)
   - Pattern matching catches legitimate questions
   - Example false positive: "How would you approach X?" → rejected as instruction
   - Missing context: question vs command distinction

3. **Grounding check is binary** (no partial grounding)
   - If ANY fact is ungrounded → reject entire response
   - Should allow synthesis of grounded facts with clear attribution

### Recommended Fixes

#### **High Priority: Gradient Gates**

```python
def check_reconstruction_gates_v2(
    self,
    intent_align: float,
    memory_align: float,
    response_type: str,  # NEW: "factual" | "explanatory" | "conversational"
    grounding_score: float,  # NEW: 0-1 instead of boolean
    contradiction_severity: str,  # NEW: "blocking" | "note" | "none"
):
    """
    V2: Gradient gates with response-type awareness.
    
    Key changes:
    1. Different thresholds for different response types
    2. Grounding score (0-1) instead of binary has_issues
    3. Contradiction severity levels
    """
    # Blocking contradictions always fail
    if contradiction_severity == "blocking":
        return False, "contradiction_fail"
    
    # Response-type specific thresholds
    if response_type == "factual":
        # Strict gates for factual claims
        if intent_align < 0.6 or memory_align < 0.5:
            return False, f"factual_standards_fail"
        if grounding_score < 0.8:
            return False, "insufficient_grounding"
    
    elif response_type == "explanatory":
        # Relaxed gates for explanations/synthesis
        if intent_align < 0.4 or memory_align < 0.25:
            return False, "explanation_coherence_fail"
        if grounding_score < 0.5:
            return False, "weak_grounding"
    
    else:  # conversational
        # Minimal gates for chat/acknowledgment
        if intent_align < 0.3:
            return False, "conversation_intent_fail"
    
    # Non-blocking contradictions pass but add metadata
    if contradiction_severity == "note":
        return True, "gates_passed_with_note"
    
    return True, "gates_passed"
```

#### **High Priority: Instruction Detection Rewrite**

Current pattern matching is too broad. Replace with:

1. **Intent classification model** (small BERT fine-tuned on instruction vs question)
2. **Grammatical analysis** (imperative mood detection)
3. **Context window** (previous turns inform interpretation)

```python
def _classify_user_intent(self, text: str, conversation_context: List[str]) -> str:
    """
    Classify user intent: question, instruction, declaration, chat.
    
    Replaces overzealous pattern matching with ML classifier.
    Returns: "question" | "instruction" | "declaration" | "chat"
    """
    # Phase 1: Rule-based fallback (improve patterns)
    # Phase 2: Load learned classifier from training loop
    # Phase 3: Use conversation context for disambiguation
```

#### **Medium Priority: Partial Grounding Support**

```python
def _assess_grounding_quality(self, response: str, retrieved_memories: List) -> float:
    """
    Return grounding score 0-1 instead of boolean.
    
    Allows responses that synthesize multiple grounded facts
    while clearly indicating confidence/source for each claim.
    """
    # Sentence-level grounding analysis
    # Attribution tracking (which sentence → which memory)
    # Synthesis detection (combining multiple memories)
```

---

## 2. M2 Contradiction Resolution (crt_ledger.py + crt_semantic_anchor.py)

### Current Status: ⚠️ **12% Success Rate (Target: 70%+)**

**Location:** `personal_agent/crt_ledger.py` + `personal_agent/crt_semantic_anchor.py`

### Problem Analysis

**Current Flow:**
1. Detect contradiction → Create ledger entry
2. Background job fetches next open contradiction
3. Generate clarification prompt
4. User answers
5. Parse answer → Resolve contradiction

**Failure Points:**

1. **Clarification prompts are too generic** (crt_semantic_anchor.py)
   - Single template for all contradiction types
   - Doesn't adapt to REFINEMENT vs CONFLICT vs TEMPORAL
   - Missing context about WHY we're asking

2. **Answer parsing is brittle**
   - Expects exact patterns ("keep both", "use latest", etc.)
   - Natural language variations fail
   - No fuzzy matching or intent understanding

3. **Contradiction classification is under-utilized**
   - System detects REFINEMENT/REVISION/TEMPORAL/CONFLICT
   - But treats all types identically in resolution
   - REFINEMENT contradictions should auto-resolve to latest

### Recommended Enhancements

#### **High Priority: Type-Aware Clarification**

```python
def generate_clarification_prompt_v2(
    ledger_entry: ContradictionEntry,
    old_memory: MemoryItem,
    new_memory: MemoryItem,
) -> str:
    """
    Generate type-specific clarification prompts.
    """
    c_type = ledger_entry.contradiction_type
    
    if c_type == ContradictionType.REFINEMENT:
        # Auto-suggest keeping both (refinement chain)
        return f"""
I have two pieces of information about {ledger_entry.affects_slots}:
- Earlier: {old_memory.text}
- More specific: {new_memory.text}

This looks like you provided more specific details. Should I:
1. Keep both (refinement chain)
2. Replace with more specific version
3. Something else

(Default: Keep both if you don't respond)
"""
    
    elif c_type == ContradictionType.TEMPORAL:
        # Suggest progression tracking
        return f"""
I see a progression for {ledger_entry.affects_slots}:
- {old_memory.timestamp}: {old_memory.text}
- {new_memory.timestamp}: {new_memory.text}

This looks like a change over time. Should I:
1. Track as progression (both valid at different times)
2. Update to latest
3. Something else
"""
    
    elif c_type == ContradictionType.CONFLICT:
        # Genuine conflict - need user input
        return f"""
I have conflicting information about {ledger_entry.affects_slots}:
- {old_memory.text}
- {new_memory.text}

Which is correct, or should I keep both as different perspectives?
"""
```

#### **High Priority: Learned Answer Parsing**

Replace brittle pattern matching with:

```python
class ContradictionResponseParser:
    """
    Parse user responses to contradiction clarifications.
    
    Uses learned model + fallback heuristics.
    """
    def __init__(self):
        self.intent_classifier = self._load_intent_classifier()
    
    def parse_resolution(self, user_answer: str, context: Dict) -> ResolutionAction:
        """
        Extract resolution action from natural language.
        
        Handles:
        - "keep both" / "both are right" / "they're both true"
        - "use the new one" / "second one" / "latest"
        - "neither" / "that's wrong"
        - "keep old" / "first one was right"
        """
        # Phase 1: Enhanced pattern matching (fuzzy)
        # Phase 2: Intent classifier
        # Phase 3: Slot-value extraction for custom resolutions
```

#### **Medium Priority: Auto-Resolution for Safe Cases**

```python
def maybe_auto_resolve(self, ledger_entry: ContradictionEntry) -> Optional[str]:
    """
    Auto-resolve contradictions with high confidence.
    
    Safe auto-resolution cases:
    1. REFINEMENT with high semantic similarity → keep both
    2. TEMPORAL with clear timestamp progression → track progression
    3. REVISION with explicit correction markers → use latest
    
    Returns resolution_method if auto-resolved, None if needs user input.
    """
    if ledger_entry.contradiction_type == ContradictionType.REFINEMENT:
        if ledger_entry.drift_mean < 0.3:  # Low drift = refinement not conflict
            return "auto_refinement_chain"
    
    if ledger_entry.contradiction_type == ContradictionType.REVISION:
        # Check for explicit correction markers in new memory
        if self._has_correction_markers(ledger_entry.new_memory_id):
            return "auto_explicit_revision"
    
    return None  # Needs user input
```

---

## 3. Learned Processes (learned_suggestions.py + training_loop.py)

### Current Status: ✅ **Framework exists but under-utilized**

**Location:** `personal_agent/learned_suggestions.py`, `personal_agent/training_loop.py`

### Current Implementation

**What exists:**
- Learned suggestion engine (metadata-only, never authoritative)
- Training loop infrastructure
- Offline training scripts (crt_learn_train.py, etc.)

**What's missing:**
- **No active learning from gate failures**
- **No learned intent classification**
- **No learned answer parsing**
- **Training data generation is manual**

### Recommended Enhancements

#### **High Priority: Gate Failure Learning**

```python
class GateFailureAnalyzer:
    """
    Learn from gate failures to improve thresholds and classification.
    
    Tracks:
    - Which queries fail which gates
    - User overrides (when user provides answer despite gate fail)
    - Patterns in false positives/negatives
    """
    def record_gate_event(
        self,
        query: str,
        intent_align: float,
        memory_align: float,
        gate_result: bool,
        user_override: Optional[bool] = None,
    ):
        """Log gate decision + optional user feedback."""
        # Store in audit DB or JSONL
        # Periodically train threshold optimization model
    
    def suggest_threshold_adjustments(self) -> Dict[str, float]:
        """Analyze gate failures and suggest new thresholds."""
        # Precision-recall tradeoff analysis
        # Recommend theta_intent, theta_mem adjustments
```

#### **High Priority: Active Learning Loop**

```python
class ActiveLearningCoordinator:
    """
    Coordinate active learning across CRT subsystems.
    
    Learning targets:
    1. Intent classification (instruction vs question)
    2. Contradiction resolution prediction
    3. Grounding quality assessment
    4. Response type detection
    """
    def identify_uncertain_examples(self) -> List[TrainingExample]:
        """Find examples where model is uncertain (near decision boundary)."""
        # Query learned models for low-confidence predictions
        # Prioritize for user feedback
    
    def generate_training_data_from_corrections(self):
        """Convert user corrections into training examples."""
        # User overrides gate → training signal
        # User resolves contradiction → answer parsing training
        # User provides fact → grounding truth data
```

#### **Medium Priority: Intent Classification Model**

Replace pattern matching with learned classifier:

```python
# Training data structure
{
    "text": "How would you approach building a neural network?",
    "label": "question",  # not "instruction"
    "features": {
        "has_question_word": True,
        "is_imperative": False,
        "has_second_person": True,
        "context_turns": 3,
    }
}

# Model: small BERT or distilBERT
# Training: Collect from gate failure logs + manual annotation
# Deployment: Hot-reload via training_loop.py
```

---

## 4. RAG Limitations (crt_rag.py)

### Current Implementation Analysis

**What CRT RAG does well:**
✅ Trust-weighted retrieval (not just similarity)
✅ Belief/speech separation
✅ Contradiction-aware retrieval (excludes contradicted sources)
✅ Recency weighting with decay

**Where standard RAG paradigm falls short:**

### Limitation 1: **No Multi-Hop Reasoning**

**Problem:**
```
User: "What's the weather like where I work?"
Current: Retrieves "location" memories, fails if "work location" not explicit
Needed: Retrieve "employer" → look up employer location → answer
```

**Current Code:** `crt_rag.py:100-200` (retrieve method)
- Single-shot retrieval
- No chaining of queries
- No intermediate reasoning steps

**Recommendation:**

```python
class MultiHopRetriever:
    """
    Multi-hop reasoning over memory graph.
    
    Supports queries like:
    - "weather where I work" → employer → location → weather
    - "my manager's background" → manager name → retrieve bio
    """
    def retrieve_with_reasoning_chain(
        self,
        query: str,
        max_hops: int = 3,
    ) -> Tuple[List[MemoryItem], List[str]]:
        """
        Execute multi-hop retrieval with reasoning trace.
        
        Returns:
            (final_memories, reasoning_steps)
            
        Example reasoning_steps:
        [
            "Identified need for 'work location'",
            "Retrieved employer: Microsoft",
            "Looked up location for Microsoft employees",
            "Found: Redmond, WA"
        ]
        """
        # Implement graph traversal over fact slots
        # Use slot extraction to identify intermediate queries
        # Return provenance chain for explainability
```

### Limitation 2: **No Confidence Propagation**

**Problem:**
When synthesizing from multiple memories, confidence should degrade:
- Memory A (confidence=0.9) + Memory B (confidence=0.7) → Combined confidence should be < 0.7
- Currently: No mechanism for this

**Recommendation:**

```python
def compute_synthesis_confidence(
    self,
    source_memories: List[MemoryItem],
    synthesis_type: str,  # "conjunction" | "summary" | "inference"
) -> float:
    """
    Compute confidence of synthesized response from multiple sources.
    
    Rules:
    - Conjunction (A AND B): min(conf_A, conf_B)
    - Summary (average): mean(confidences) * 0.9 (degradation)
    - Inference (A→B): conf_A * 0.7 (reasoning penalty)
    """
    if not source_memories:
        return 0.0
    
    confidences = [m.confidence for m in source_memories]
    
    if synthesis_type == "conjunction":
        return min(confidences)
    elif synthesis_type == "summary":
        return np.mean(confidences) * 0.9  # Summary degradation
    elif synthesis_type == "inference":
        return min(confidences) * 0.7  # Reasoning penalty
    else:
        return np.mean(confidences) * 0.8  # Conservative default
```

### Limitation 3: **No Temporal Reasoning**

**Problem:**
Current implementation doesn't distinguish:
- "Where did I work in 2020?" vs "Where do I work now?"
- Temporal progression not tracked explicitly

**Current Mitigation:** `crt_ledger.py` has `ContradictionType.TEMPORAL`
**Gap:** Not integrated into retrieval or answer generation

**Recommendation:**

```python
def retrieve_with_temporal_filter(
    self,
    query: str,
    temporal_scope: Optional[str] = None,  # "current" | "2020" | "progression"
) -> List[Tuple[MemoryItem, float]]:
    """
    Retrieve memories with temporal awareness.
    
    temporal_scope modes:
    - "current": Return only latest uncontradicted values
    - "YYYY": Return values from specific year
    - "progression": Return time-ordered sequence showing changes
    """
    # Extract temporal markers from query
    # Filter memories by timestamp
    # Handle temporal contradictions specially
```

### Limitation 4: **No Source Diversity Awareness**

**Problem:**
All retrieved memories treated equally regardless of source:
- USER-sourced facts (high trust)
- SYSTEM inferences (lower trust)
- EXTERNAL imports (need verification)

**Current:** Source filtering exists but no diversity scoring

**Recommendation:**

```python
def compute_source_diversity_score(self, memories: List[MemoryItem]) -> float:
    """
    Measure diversity of information sources.
    
    Higher score = more corroboration from independent sources.
    Lower score = single source or self-referential loop.
    """
    sources = set(m.source for m in memories)
    
    # Penalize single-source answers
    if len(sources) == 1 and MemorySource.SYSTEM in sources:
        return 0.3  # Low diversity - only system inferences
    
    # Reward multi-source corroboration
    if MemorySource.USER in sources and MemorySource.EXTERNAL in sources:
        return 0.9  # High diversity - user + external confirmation
    
    return 0.6  # Medium diversity
```

### Limitation 5: **No Explanation Generation**

**Problem:**
Responses don't explain reasoning:
- "Your employer is Microsoft" (no provenance)
- Better: "Your employer is Microsoft (you mentioned this on Jan 10 when discussing your new role)"

**Current:** Metadata includes memory IDs but no human-readable provenance

**Recommendation:**

```python
def generate_answer_with_provenance(
    self,
    answer: str,
    source_memories: List[MemoryItem],
    reasoning_chain: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate answer with explicit provenance and reasoning.
    
    Returns:
    {
        "answer": "Your employer is Microsoft",
        "provenance": [
            "From our conversation on Jan 10: 'I just started at Microsoft'",
            "Confirmed on Jan 12: 'My Microsoft badge arrived'"
        ],
        "reasoning": [
            "Identified most recent employer mention",
            "Cross-referenced with location (Redmond)",
            "Confidence: 0.92"
        ],
        "confidence": 0.92,
        "source_diversity": 0.8
    }
    """
```

---

## 5. Research Engine (research_engine.py)

### Current Status: 🔧 **Basic scaffolding, needs M3 completion**

**Location:** `personal_agent/research_engine.py`

### Current Capabilities

✅ Local document search (markdown/text files)
✅ Basic keyword extraction
✅ Quote extraction with char offsets
⚠️ No web search
⚠️ No citation quality scoring
⚠️ No source credibility assessment

### Recommended Enhancements

#### **High Priority: Web Search Integration (M3)**

```python
class WebSearchProvider:
    """
    Web search with citation quality.
    
    Providers:
    1. DuckDuckGo (privacy-first, no API key)
    2. SearXNG (self-hosted metasearch)
    3. Brave Search API (optional, paid)
    """
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Execute web search and return ranked results."""
    
    def fetch_and_extract(self, url: str) -> Optional[Citation]:
        """
        Fetch page, extract clean text, find relevant quotes.
        
        Uses:
        - BeautifulSoup for HTML parsing
        - readability-lxml for main content extraction
        - Spacy for sentence segmentation and quote extraction
        """
```

#### **Medium Priority: Citation Quality Scoring**

```python
def assess_citation_quality(self, citation: Citation) -> float:
    """
    Score citation quality 0-1.
    
    Factors:
    - Source credibility (domain reputation)
    - Content freshness (publication date)
    - Quote relevance (keyword overlap with query)
    - Quote context (surrounding sentences support claim)
    - Source diversity (not all from same domain)
    """
    quality_score = 0.5  # Base
    
    # Credible domains
    if citation.source_url.endswith(('.edu', '.gov', '.org')):
        quality_score += 0.2
    
    # Recent content (within 2 years)
    if citation.fetched_at and self._is_recent(citation.fetched_at):
        quality_score += 0.15
    
    # Direct quote (vs paraphrase)
    if self._has_quotation_marks(citation.quote_text):
        quality_score += 0.1
    
    return min(quality_score, 1.0)
```

---

## 6. Priority Roadmap

### Immediate (Next Sprint)

1. **Fix Gate Logic** - Gradient gates + response type awareness
   - **Impact:** 67% → 15% rejection rate
   - **Effort:** 3-5 days
   - **Files:** `crt_core.py`, `crt_rag.py`

2. **Improve M2 Clarification** - Type-aware prompts
   - **Impact:** 12% → 40% success rate
   - **Effort:** 2-3 days
   - **Files:** `crt_semantic_anchor.py`, `crt_ledger.py`

### Near-Term (Next 2 Weeks)

3. **Active Learning Pipeline** - Learn from gate failures
   - **Impact:** Continuous improvement, reducing manual tuning
   - **Effort:** 5-7 days
   - **Files:** New `active_learning.py`, extend `training_loop.py`

4. **Multi-Hop Retrieval** - Support complex queries
   - **Impact:** Handle "weather where I work" type questions
   - **Effort:** 4-6 days
   - **Files:** Extend `crt_rag.py`, new `reasoning_graph.py`

### Medium-Term (Next Month)

5. **Web Search Integration** - Complete M3
   - **Impact:** External knowledge, fact verification
   - **Effort:** 7-10 days
   - **Files:** `research_engine.py`, new `web_search.py`

6. **Provenance Generation** - Explainable answers
   - **Impact:** User trust, debugging
   - **Effort:** 3-5 days
   - **Files:** `crt_rag.py` output formatting

---

## 7. Code Quality Issues

### Technical Debt Identified

1. **crt_rag.py is 3025 lines** - needs refactoring
   - Split into: `gates.py`, `retrieval.py`, `response_generation.py`

2. **Duplicate code patterns**
   - Slot extraction repeated in multiple places
   - Consider: `personal_agent/slot_utils.py` consolidation

3. **Error handling is inconsistent**
   - Some functions return `None` on error
   - Others raise exceptions
   - Standardize error handling strategy

4. **Testing coverage gaps**
   - Gate logic needs more unit tests
   - Multi-turn conversation tests limited
   - Contradiction resolution needs integration tests

### Recommendations

```python
# Standard error handling pattern
class CRTError(Exception):
    """Base exception for CRT errors."""

class GateError(CRTError):
    """Gate validation failures."""

class RetrievalError(CRTError):
    """Retrieval failures."""

# Use consistently across codebase
```

---

## Summary

### Most Critical Improvements

| Priority | Component | Current Issue | Target Metric | Effort |
|----------|-----------|---------------|---------------|--------|
| **P0** | Gate Logic | 67% false reject | <15% | 3-5d |
| **P0** | M2 Clarification | 12% success | >40% | 2-3d |
| **P1** | Active Learning | Manual tuning | Auto-adapt | 5-7d |
| **P1** | Multi-Hop | Can't reason | Handle chains | 4-6d |
| **P2** | Web Search | Local only | M3 complete | 7-10d |

### Strategic Opportunities

1. **Learning from usage** - System should improve from every interaction
2. **Explainability** - Answers need provenance and reasoning traces
3. **Confidence calibration** - Synthesis should degrade confidence appropriately
4. **Temporal reasoning** - Track progressions, not just latest state

The codebase is **architecturally sound** but needs **tactical improvements** in gate logic and M2 automation before it's production-ready for real users.

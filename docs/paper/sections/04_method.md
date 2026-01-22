# Method

We present GroundCheck, a contradiction-aware grounding verification system for long-term memory systems. This section formalizes the problem, describes our approach to fact extraction and contradiction detection, and details our trust-weighted verification algorithm.

## 4.1 Problem Formalization

**Input:** A generated text $g$ and a set of retrieved memories $M = \{m_1, m_2, ..., m_n\}$. Each memory $m_i$ has:
- `text`: Natural language content
- `trust`: Confidence score in [0, 1]
- `timestamp`: Unix timestamp when memory was created
- `id`: Unique identifier

**Output:** A verification report containing:
- `grounded`: Boolean indicating whether all claims in $g$ are supported by $M$
- `hallucinations`: List of unsupported claims in $g$
- `contradictions`: List of detected contradictions in $M$
- `requires_disclosure`: Boolean indicating whether $g$ should acknowledge contradictions
- `expected_disclosure`: Suggested disclosure text when contradictions exist

**Goal:** Verify that $g$ is grounded in $M$ while explicitly detecting when $M$ contains contradictory information. Unlike standard grounding verification that checks $\forall c \in claims(g), \exists m \in M: supports(m, c)$, we additionally require checking $\forall slot, \neg \exists m_1, m_2 \in M: contradicts(m_1, m_2, slot)$ or, if contradictions exist, verifying that $g$ appropriately acknowledges them.

## 4.2 Fact Extraction

GroundCheck uses regex-based fact extraction to identify structured information in natural language text. We define 20+ fact slot types, each with associated extraction patterns:

**Slot types:**
- `employer`: Employment information
- `location`: Residence or current location
- `title`: Job title or professional role
- `education`: Educational institution or degree
- `favorite_color`, `favorite_food`, etc.: Personal preferences
- `diagnosis`: Medical diagnosis (for healthcare)
- `account_status`: Account state (for customer service)

**Extraction patterns:** For each slot type, we define regex patterns that match common linguistic expressions. For example, `employer` patterns include:
```
works at ([A-Z][A-Za-z]+)
employed by ([A-Z][A-Za-z]+)
works for ([A-Z][A-Za-z]+)
job at ([A-Z][A-Za-z]+)
position at ([A-Z][A-Za-z]+)
```

**Extraction algorithm:**
```
function extract_fact_slots(text: str) -> Dict[slot_type, List[ExtractedFact]]:
    facts = defaultdict(list)
    
    for slot_type in SLOT_TYPES:
        for pattern in PATTERNS[slot_type]:
            matches = regex.findall(pattern, text, flags=IGNORECASE)
            for match in matches:
                facts[slot_type].append(
                    ExtractedFact(
                        value=normalize(match),
                        slot_type=slot_type,
                        pattern=pattern
                    )
                )
    
    return facts
```

**Normalization:** Extracted values are normalized to canonical form: lowercased, whitespace-trimmed, and common variations collapsed ("Microsoft Corporation" → "microsoft"). This improves matching across paraphrases.

**Trade-offs:** Regex-based extraction is fast (<1ms per document) and deterministic but limited to predefined patterns. It cannot extract arbitrary fact types or handle complex linguistic structures. Section 7 discusses neural alternatives.

## 4.3 Contradiction Detection

Given retrieved memories $M$, contradiction detection identifies pairs of memories that make conflicting claims about the same fact slot.

**Algorithm:**
```
function detect_contradictions(memories: List[Memory]) -> List[ContradictionDetail]:
    # Step 1: Extract facts from all memories
    memory_facts = {}
    for memory in memories:
        memory_facts[memory.id] = extract_fact_slots(memory.text)
    
    # Step 2: Group facts by slot type across memories
    slot_to_facts = defaultdict(list)
    for memory_id, facts_dict in memory_facts.items():
        for slot_type, facts in facts_dict.items():
            for fact in facts:
                memory = find_memory_by_id(memory_id)
                slot_to_facts[slot_type].append(
                    (fact.value, memory_id, memory.trust, memory.timestamp)
                )
    
    # Step 3: Detect contradictions within each slot
    contradictions = []
    for slot_type, facts in slot_to_facts.items():
        unique_values = set(f[0] for f in facts)
        
        if len(unique_values) > 1:
            # Multiple distinct values for same slot - potential contradiction
            
            # Apply trust filtering
            high_trust_facts = [f for f in facts if f[2] >= TRUST_THRESHOLD]
            
            if len(set(f[0] for f in high_trust_facts)) > 1:
                # Still contradictory after trust filtering
                
                # Check trust difference
                trust_values = [f[2] for f in high_trust_facts]
                if max(trust_values) - min(trust_values) < TRUST_DIFF_THRESHOLD:
                    # Both memories have similar high trust - genuine contradiction
                    contradictions.append(
                        ContradictionDetail(
                            slot_type=slot_type,
                            values=[f[0] for f in high_trust_facts],
                            memory_ids=[f[1] for f in high_trust_facts],
                            trust_scores=[f[2] for f in high_trust_facts],
                            timestamps=[f[3] for f in high_trust_facts]
                        )
                    )
    
    return contradictions
```

**Trust thresholds:** We use two thresholds to filter spurious contradictions:
- `TRUST_THRESHOLD = 0.75`: Only consider memories with trust ≥ 0.75 as candidates for contradiction
- `TRUST_DIFF_THRESHOLD = 0.3`: Only flag contradictions when trust scores differ by < 0.3

**Rationale:** Low-confidence memories may appear to contradict high-confidence ones due to extraction errors or noise. For example, trust scores of (0.9, 0.2) likely indicate the low-trust memory is unreliable, not a genuine contradiction. Trust scores of (0.85, 0.83) with different values indicate both memories are reliable but conflicting—a genuine contradiction requiring disclosure.

**Example:** Consider memories $M = \{m_1, m_2\}$ where:
- $m_1$: "Works at Microsoft" (trust=0.85, timestamp=Jan 1)
- $m_2$: "Works at Amazon" (trust=0.85, timestamp=Mar 1)

Contradiction detection proceeds:
1. Extract facts: $m_1$ yields `{employer: ["microsoft"]}`, $m_2$ yields `{employer: ["amazon"]}`
2. Group by slot: `employer` → `[("microsoft", m1, 0.85, Jan 1), ("amazon", m2, 0.85, Mar 1)]`
3. Check uniqueness: Two distinct values ("microsoft", "amazon")
4. Apply trust filter: Both have trust ≥ 0.75
5. Check trust difference: |0.85 - 0.85| = 0 < 0.3
6. Flag contradiction: `ContradictionDetail(slot="employer", values=["microsoft", "amazon"], ...)`

## 4.4 Disclosure Verification

When contradictions exist in retrieved memories, generated outputs should acknowledge these conflicts. Disclosure verification checks whether outputs using contradicted values include appropriate acknowledgment.

**Disclosure patterns:** We define regex patterns that match common disclosure phrases:
```
changed from {old_value} to {new_value}
previously {old_value}, now {new_value}
was {old_value}, is now {new_value}
updated from {old_value}
formerly {old_value}
used to be {old_value}
```

**Verification algorithm:**
```
function verify_disclosure(
    generated_text: str,
    contradictions: List[ContradictionDetail]
) -> (bool, Optional[str]):
    
    for contradiction in contradictions:
        # Check if generated text uses any contradicted value
        used_values = []
        for value in contradiction.values:
            if value in generated_text.lower():
                used_values.append(value)
        
        if len(used_values) == 0:
            # Generated text doesn't mention this contradicted slot
            continue
        
        if len(used_values) == 1:
            # Uses one contradicted value - check for disclosure
            used_value = used_values[0]
            other_values = [v for v in contradiction.values if v != used_value]
            
            # Check for disclosure patterns
            has_disclosure = False
            for pattern in DISCLOSURE_PATTERNS:
                if pattern_matches_with_values(pattern, generated_text, used_value, other_values):
                    has_disclosure = True
                    break
            
            if not has_disclosure:
                # Requires disclosure but doesn't have it
                # Generate expected disclosure
                most_recent_idx = find_most_recent_memory_idx(contradiction)
                most_recent_value = contradiction.values[most_recent_idx]
                previous_value = [v for v in contradiction.values if v != most_recent_value][0]
                
                expected = f"{most_recent_value} (changed from {previous_value})"
                return (True, expected)  # Requires disclosure
        
        elif len(used_values) > 1:
            # Uses multiple contradicted values - inherently acknowledges contradiction
            pass
    
    return (False, None)  # No disclosure required
```

**Example:** For the employer contradiction ("microsoft" vs "amazon"), if generated text is "You work at Amazon":
1. Identify used value: "amazon"
2. Check for disclosure: Look for patterns like "changed from microsoft"
3. No disclosure found
4. Generate expected: "You work at Amazon (changed from Microsoft)"
5. Return: `(requires_disclosure=True, expected="Amazon (changed from Microsoft)")`

If generated text is "You work at Amazon (changed from Microsoft)":
1. Identify used value: "amazon"
2. Check for disclosure: Pattern "changed from {old}" matches with old="microsoft"
3. Disclosure found
4. Return: `(requires_disclosure=False, expected=None)`

## 4.5 Trust-Weighted Verification

The complete GroundCheck verification algorithm combines standard grounding verification with contradiction detection and disclosure verification.

**Algorithm:**
```
function groundcheck_verify(
    generated_text: str,
    memories: List[Memory]
) -> VerificationReport:
    
    # Step 1: Extract facts from generated text
    generated_facts = extract_fact_slots(generated_text)
    
    # Step 2: Detect contradictions in memories
    contradictions = detect_contradictions(memories)
    
    # Step 3: Verify each generated fact is supported
    hallucinations = []
    grounding_map = {}
    
    for slot_type, facts in generated_facts.items():
        for fact in facts:
            # Check if any memory supports this fact
            supporting_memory = None
            for memory in memories:
                memory_facts = extract_fact_slots(memory.text)
                if fact.value in [f.value for f in memory_facts.get(slot_type, [])]:
                    supporting_memory = memory
                    break
            
            if supporting_memory:
                grounding_map[fact.value] = supporting_memory.id
            else:
                hallucinations.append(fact.value)
    
    # Step 4: Check disclosure for contradicted facts
    requires_disclosure, expected_disclosure = verify_disclosure(
        generated_text, contradictions
    )
    
    # Step 5: Determine overall grounding status
    grounded = (len(hallucinations) == 0) and (not requires_disclosure)
    
    return VerificationReport(
        grounded=grounded,
        hallucinations=hallucinations,
        contradictions=contradictions,
        requires_disclosure=requires_disclosure,
        expected_disclosure=expected_disclosure,
        grounding_map=grounding_map
    )
```

**Verification logic:**
- `grounded = True` iff all facts are supported AND no contradicted facts lack disclosure
- `grounded = False` if any fact is unsupported (hallucination) OR contradicted facts lack disclosure

This ensures GroundCheck rejects outputs that correctly use recent information but fail to acknowledge contradictions—the key distinction from existing methods.

## 4.6 System Architecture

GroundCheck consists of three main components:

**1. FactExtractor:** Applies regex patterns to text and returns structured fact slots. Operates independently on each text, enabling parallel extraction across memories.

**2. ContradictionDetector:** Groups extracted facts by slot type and identifies conflicts using trust-weighted filtering. Returns contradiction details with supporting evidence (memory IDs, trust scores, timestamps).

**3. GroundCheckVerifier:** Orchestrates the verification pipeline: extraction → contradiction detection → disclosure verification → grounding status. Returns structured verification reports.

**Data types:**
```python
@dataclass
class Memory:
    id: str
    text: str
    trust: float
    timestamp: int

@dataclass
class ExtractedFact:
    value: str
    slot_type: str
    pattern: str

@dataclass
class ContradictionDetail:
    slot_type: str
    values: List[str]
    memory_ids: List[str]
    trust_scores: List[float]
    timestamps: List[int]

@dataclass
class VerificationReport:
    grounded: bool
    hallucinations: List[str]
    contradictions: List[ContradictionDetail]
    requires_disclosure: bool
    expected_disclosure: Optional[str]
    grounding_map: Dict[str, str]
```

**Runtime characteristics:**
- Fact extraction: O(n·m) where n = number of patterns, m = text length
- Contradiction detection: O(k²) where k = number of memories (in practice k << 100)
- Disclosure verification: O(p) where p = number of disclosure patterns
- Total latency: <10ms for typical inputs (k=5-10 memories, m=100-500 chars)

GroundCheck's deterministic, rule-based approach enables fast, reproducible verification without LLM API calls—critical for production deployment where millions of verifications may occur daily.

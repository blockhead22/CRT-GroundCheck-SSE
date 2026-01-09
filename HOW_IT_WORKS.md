# How SSE Works: Plain Language Explanation

## The Big Idea (In One Sentence)

SSE reads documents, finds all the claims being made, detects when claims contradict each other, and **keeps both sides of every contradiction** instead of picking a winner.

---

## Why This Matters

Imagine you're researching "how much sleep do humans need?" You read 10 articles and find:
- Article 1 says: "Adults need 7-9 hours of sleep"
- Article 2 says: "Sleep needs are highly individual, ranging from 4-12 hours"
- Article 3 says: "Some people function perfectly on 5 hours"

**Problem with normal search/AI:**
- Google shows you the top result (probably Article 1)
- ChatGPT synthesizes an answer like "Most adults need 7-9 hours, though individual needs vary"
- You never see the full contradiction between "everyone needs 7-9 hours" and "some people only need 5 hours"

**What SSE does:**
- Shows you ALL three claims
- Explicitly tells you "Claim 1 and Claim 3 contradict each other"
- Lets you click on each claim to see the exact sentence in the original article
- Refuses to pick a winner or create a fake consensus

---

## The Five Steps (How It Actually Works)

### Step 1: Break Document into Chunks

**Why:** Documents are too long to process all at once. We need to break them into manageable pieces while remembering where each piece came from.

**How:**
```
Input: "Sleep is critical. Adults need 7-9 hours. However, needs vary by person. Some people thrive on 5 hours."

Split into chunks:
  Chunk 1: "Sleep is critical. Adults need 7-9 hours."
           Location: characters 0-50
  
  Chunk 2: "Adults need 7-9 hours. However, needs vary by person."
           Location: characters 24-84
  
  Chunk 3: "However, needs vary by person. Some people thrive on 5 hours."
           Location: characters 51-113
```

**Key detail:** We overlap chunks so sentences aren't split awkwardly. We save the exact character positions (0-50, 24-84, etc.) so we can always trace back to the source.

**Pseudo-code:**
```python
def chunk_document(text, max_size=500, overlap=100):
    chunks = []
    position = 0
    
    while position < len(text):
        # Find the next chunk
        end = position + max_size
        
        # Don't split in the middle of a sentence
        end = find_sentence_boundary(text, end)
        
        # Save the chunk with its position
        chunks.append({
            'text': text[position:end],
            'start': position,
            'end': end
        })
        
        # Move forward, but overlap by 100 chars
        position = end - overlap
    
    return chunks
```

---

### Step 2: Extract Claims from Chunks

**Why:** A chunk might contain multiple ideas. We need to identify each individual claim being made.

**How:**
```
Chunk: "Sleep is critical. Adults need 7-9 hours. This varies by person."

Extract claims:
  Claim 1: "Sleep is critical for human health"
           Source: characters 0-20 in original document
  
  Claim 2: "Adults need 7-9 hours of sleep"
           Source: characters 21-50 in original document
  
  Claim 3: "Sleep requirements vary by person"
           Source: characters 51-80 in original document
```

**Two methods:**

**Method A - Rule-based (fast but simple):**
```python
def extract_claims_simple(chunk):
    claims = []
    
    # Split chunk into sentences
    sentences = split_into_sentences(chunk['text'])
    
    for sentence in sentences:
        # Only keep sentences that make assertions
        if is_assertive(sentence):  # Not questions, not filler
            if not is_too_short(sentence):  # At least 3 words
                claims.append({
                    'text': sentence,
                    'location': find_position_in_original(sentence, chunk)
                })
    
    return claims
```

**Method B - LLM-based (slower but smarter):**
```python
def extract_claims_llm(chunk):
    prompt = f"""
    Extract factual claims from this text.
    Each claim should be one atomic fact.
    
    Text: {chunk['text']}
    
    Output format: one claim per line.
    """
    
    response = ask_llm(prompt)
    claims = response.split('\n')
    
    return claims
```

**Key detail:** We track exactly where each claim came from (character positions) so we can prove it's really in the source document.

---

### Step 3: Turn Text into Numbers (Embeddings)

**Why:** Computers can't understand "meaning" directly. We convert text to numbers (vectors) so we can measure similarity.

**How:**
```
Claim: "Adults need 7-9 hours of sleep"
↓
Embedding: [0.23, -0.45, 0.67, 0.12, ..., 0.89]  (384 numbers)

Claim: "Most people require 7-9 hours of rest"
↓
Embedding: [0.21, -0.43, 0.69, 0.14, ..., 0.91]  (384 numbers)

These embeddings are CLOSE (similar meaning)

Claim: "Coffee blocks adenosine receptors"
↓
Embedding: [-0.67, 0.23, -0.12, 0.88, ..., -0.34]  (384 numbers)

This embedding is FAR from the sleep claims (different topic)
```

**Pseudo-code:**
```python
def embed_claims(claims):
    # Load a pre-trained model (e.g., sentence-transformers)
    model = load_embedding_model("all-MiniLM-L6-v2")
    
    embeddings = []
    for claim in claims:
        # Convert claim text to a 384-dimensional vector
        vector = model.encode(claim['text'])
        embeddings.append(vector)
    
    return embeddings
```

**Why this matters:** Now we can find claims that are about the same topic (even if worded differently) by measuring the distance between their number vectors.

---

### Step 4: Detect Contradictions

**Why:** This is the core innovation. Find when claims disagree with each other.

**How (3-stage filter):**

**Stage 1 - Pre-filter by similarity:**
```python
def find_potential_contradictions(claims, embeddings):
    candidates = []
    
    for i in range(len(claims)):
        for j in range(i+1, len(claims)):
            # Measure similarity (dot product of vectors)
            similarity = dot_product(embeddings[i], embeddings[j])
            
            # Only check claims that are about the SAME topic
            if 0.5 < similarity < 0.9:  # Similar but not identical
                candidates.append((i, j))
    
    return candidates
```

**Why 0.5 to 0.9?**
- Below 0.5: Claims are about different topics (can't contradict)
- Above 0.9: Claims are basically the same (duplicates, not contradictions)
- Sweet spot: Claims about the same thing but saying different things

**Stage 2 - Check for negation patterns:**
```python
def check_negation_contradiction(claim_a, claim_b):
    # Does one have "not" and the other doesn't?
    a_has_not = 'not' in claim_a or "n't" in claim_a
    b_has_not = 'not' in claim_b or "n't" in claim_b
    
    if a_has_not != b_has_not:
        return True  # One is negated, likely contradiction
    
    # Check for opposite words
    opposites = [
        ('beneficial', 'harmful'),
        ('safe', 'dangerous'),
        ('effective', 'ineffective'),
        ('true', 'false')
    ]
    
    for word_a, word_b in opposites:
        if (word_a in claim_a and word_b in claim_b) or \
           (word_b in claim_a and word_a in claim_b):
            return True  # Opposite concepts
    
    return False
```

**Stage 3 - Ask an LLM (optional, most accurate):**
```python
def llm_contradiction_check(claim_a, claim_b):
    prompt = f"""
    Do these two claims contradict each other?
    
    Claim A: {claim_a}
    Claim B: {claim_b}
    
    Answer: contradiction, entailment, or neutral
    """
    
    response = ask_llm(prompt)
    
    if 'contradiction' in response.lower():
        return True
    return False
```

**Real example:**
```
Claim A: "Adults need 7-9 hours of sleep"
Claim B: "Some people thrive on 5 hours of sleep"

Stage 1: ✓ Similar topic (similarity = 0.72)
Stage 2: ✗ No obvious negation words
Stage 3: ✓ LLM says "contradiction" (7-9 hours vs 5 hours)

Result: CONTRADICTION DETECTED
```

**Pseudo-code for full detection:**
```python
def detect_all_contradictions(claims, embeddings):
    contradictions = []
    
    # Stage 1: Find potentially related claims
    candidates = find_similar_pairs(embeddings, min_sim=0.5, max_sim=0.9)
    
    for (i, j) in candidates:
        claim_a = claims[i]['text']
        claim_b = claims[j]['text']
        
        # Stage 2: Quick heuristic check
        if check_negation_contradiction(claim_a, claim_b):
            contradictions.append({
                'claim_a': claims[i],
                'claim_b': claims[j],
                'method': 'negation_pattern'
            })
            continue
        
        # Stage 3: LLM check (if available)
        if llm_available():
            if llm_contradiction_check(claim_a, claim_b):
                contradictions.append({
                    'claim_a': claims[i],
                    'claim_b': claims[j],
                    'method': 'llm_nli'
                })
    
    return contradictions
```

---

### Step 5: Package Everything (Evidence Packet)

**Why:** We need a standard format that prevents anyone from hiding contradictions or adding their own opinions.

**How:**
```python
def create_evidence_packet(claims, contradictions):
    packet = {
        'claims': claims,  # ALL claims (no filtering)
        'contradictions': contradictions,  # ALL contradictions (no hiding)
        'support_metrics': {},  # How many sources, contradictions per claim
        'metadata': {
            'query': user_query,
            'timestamp': current_time()
        },
        'audit_trail': []  # Log of what happened
    }
    
    # Calculate support metrics
    for claim in claims:
        claim_id = claim['id']
        packet['support_metrics'][claim_id] = {
            'source_count': count_sources(claim),
            'contradiction_count': count_contradictions(claim, contradictions),
            'retrieval_score': calculate_relevance(claim, user_query)
        }
    
    # CRITICAL: Validate packet before returning
    validate_packet(packet)
    
    return packet
```

**Validation checks:**
```python
def validate_packet(packet):
    # Check 1: No forbidden fields
    forbidden_fields = ['confidence', 'credibility', 'truth_score', 
                        'quality', 'reliability', 'best_answer']
    
    for field in forbidden_fields:
        if field in packet:
            raise Error(f"Forbidden field '{field}' detected!")
    
    # Check 2: No forbidden words in descriptions
    forbidden_words = ['probably', 'likely', 'seems', 'appears to be',
                       'more credible', 'less reliable', 'best']
    
    for claim in packet['claims']:
        for word in forbidden_words:
            if word in claim.get('description', ''):
                raise Error(f"Forbidden interpretive word '{word}' detected!")
    
    # Check 3: All claims present (no filtering)
    assert len(packet['claims']) == original_claim_count
    
    # Check 4: All contradictions present (no suppression)
    assert len(packet['contradictions']) == detected_contradiction_count
    
    return True
```

**Example packet:**
```json
{
  "claims": [
    {
      "claim_id": "clm0",
      "text": "Adults need 7-9 hours of sleep",
      "source": "doc_sleep.txt",
      "location": {"start": 45, "end": 78}
    },
    {
      "claim_id": "clm1",
      "text": "Some people thrive on 5 hours of sleep",
      "source": "doc_sleep.txt",
      "location": {"start": 156, "end": 195}
    }
  ],
  "contradictions": [
    {
      "claim_a_id": "clm0",
      "claim_b_id": "clm1",
      "relationship": "contradicts"
    }
  ],
  "support_metrics": {
    "clm0": {
      "source_count": 1,
      "contradiction_count": 1,
      "retrieval_score": 0.95
    },
    "clm1": {
      "source_count": 1,
      "contradiction_count": 1,
      "retrieval_score": 0.82
    }
  }
}
```

---

## What You Can Do With This

### 1. Search for Claims
```python
# Find all claims about "sleep requirements"
results = search(query="sleep requirements", k=10)

# Results include contradiction counts
for claim in results:
    print(f"Claim: {claim['text']}")
    print(f"  Contradicts with: {claim['contradiction_count']} other claims")
```

### 2. Browse Contradictions
```python
# Get all contradictions
contradictions = get_all_contradictions()

for contra in contradictions:
    print(f"Claim A: {contra['claim_a']['text']}")
    print(f"Claim B: {contra['claim_b']['text']}")
    print(f"Relationship: {contra['type']}")
```

### 3. Verify Sources
```python
# Get exact source for a claim
claim = get_claim("clm0")
source_text = get_source_text(claim['source'])

# Extract the exact quote
quote = source_text[claim['location']['start']:claim['location']['end']]

# Verify it matches
assert quote == claim['text']  # Always true!
```

### 4. Feed to AI (RAG)
```python
# Build prompt for LLM
def build_prompt(query, packet):
    prompt = f"Query: {query}\n\n"
    prompt += f"Found {len(packet['claims'])} claims:\n\n"
    
    for claim in packet['claims']:
        prompt += f"- {claim['text']}\n"
        
        # Show contradictions explicitly
        contra_count = packet['support_metrics'][claim['id']]['contradiction_count']
        if contra_count > 0:
            prompt += f"  ⚠️  CONTRADICTS {contra_count} other claims\n"
    
    prompt += "\n\nConsidering ALL claims above (including contradictions), "
    prompt += "what can you tell me about this topic?"
    
    return prompt

# The LLM now sees BOTH sides of every contradiction
response = ask_llm(build_prompt(user_query, packet))
```

---

## What Makes This Different

### Normal RAG System:
```python
def normal_rag(query):
    # Find top 5 most relevant chunks
    results = vector_search(query, k=5)
    
    # Build prompt from top results only
    prompt = f"Query: {query}\nContext: " + "\n".join(results)
    
    # LLM only sees top-ranked results
    return ask_llm(prompt)
```

**Problem:** If the most contradictory claim is ranked #6, it gets dropped. LLM never sees the contradiction.

### SSE Approach:
```python
def sse_rag(query):
    # Get ALL relevant claims (no k limit initially)
    all_claims = extract_all_claims(documents)
    
    # Detect contradictions among them
    contradictions = detect_contradictions(all_claims)
    
    # Filter by relevance to query
    relevant = filter_by_relevance(all_claims, query, threshold=0.5)
    
    # CRITICAL: Include all sides of contradictions
    for contra in contradictions:
        if contra['claim_a'] in relevant or contra['claim_b'] in relevant:
            # If one side is relevant, include both sides
            relevant.add(contra['claim_a'])
            relevant.add(contra['claim_b'])
    
    # Build packet with contradiction info
    packet = create_evidence_packet(relevant, contradictions)
    
    # Validate (hard gate - fails if anything wrong)
    validate_packet(packet)
    
    # Build prompt that shows contradictions
    prompt = build_contradiction_aware_prompt(query, packet)
    
    return ask_llm(prompt)
```

**Key difference:** Even if contradictory claim was lower-ranked, we pull it back in. LLM sees both sides.

---

## The Rules (What SSE Will NEVER Do)

### ❌ Never Pick Winners
```python
# This function does NOT exist in SSE
def pick_best_claim(contradictory_claims):
    # ❌ FORBIDDEN: Choosing which claim is "more credible"
    return max(contradictory_claims, key=lambda c: c.confidence_score)
```

### ❌ Never Hide Contradictions
```python
# This function does NOT exist in SSE
def filter_contradictions(claims, threshold=0.8):
    # ❌ FORBIDDEN: Removing contradictions below some threshold
    return [c for c in claims if c.confidence > threshold]
```

### ❌ Never Synthesize
```python
# This function does NOT exist in SSE
def synthesize_consensus(contradictory_claims):
    # ❌ FORBIDDEN: Creating a new claim that "resolves" the contradiction
    return "Most evidence suggests X, though some studies show Y"
```

### ❌ Never Paraphrase
```python
# This function does NOT exist in SSE
def simplify_claim(claim):
    # ❌ FORBIDDEN: Rewriting the original claim text
    return llm_rewrite(claim.text, style="simple")
```

### ✅ What It WILL Do
```python
# ✅ PERMITTED: Show all claims
def get_all_claims(query):
    return search(query, return_all=True)

# ✅ PERMITTED: Show contradictions
def get_contradictions_for_claim(claim_id):
    return find_contradicting_claims(claim_id)

# ✅ PERMITTED: Show exact sources
def get_source_quote(claim_id):
    claim = get_claim(claim_id)
    source = load_document(claim.source_doc)
    return source[claim.start_char:claim.end_char]

# ✅ PERMITTED: Group by similarity
def cluster_claims(claims):
    return group_by_semantic_similarity(claims)

# ✅ PERMITTED: Search
def search_claims(query, method='semantic'):
    if method == 'semantic':
        return vector_search(query)
    else:
        return keyword_search(query)
```

---

## Complete Example: End-to-End

Let's say you have a document about sleep:

```
INPUT DOCUMENT (doc.txt):
"Sleep is critical for health. Most adults need 7-9 hours per night.
However, sleep requirements vary significantly between individuals.
Some people function perfectly well on just 5 hours of sleep.
Others require 10-12 hours to feel rested."
```

**Step 1: Chunk**
```
Chunk 1: "Sleep is critical for health. Most adults need 7-9 hours per night."
         Location: [0:72]

Chunk 2: "Most adults need 7-9 hours per night. However, sleep requirements vary..."
         Location: [36:145]

Chunk 3: "Some people function perfectly well on just 5 hours of sleep. Others..."
         Location: [100:200]
```

**Step 2: Extract Claims**
```
Claim A: "Sleep is critical for health"
         Source: [0:30]

Claim B: "Most adults need 7-9 hours of sleep per night"
         Source: [32:72]

Claim C: "Sleep requirements vary significantly between individuals"
         Source: [82:145]

Claim D: "Some people function perfectly well on 5 hours of sleep"
         Source: [146:205]
```

**Step 3: Embed**
```
Claim A → [0.1, 0.3, -0.2, ...]
Claim B → [0.2, 0.4, -0.1, ...]
Claim C → [0.3, 0.5, -0.2, ...]
Claim D → [0.2, 0.4, 0.0, ...]

Similarity(B, D) = 0.78  ← Same topic, different conclusions
```

**Step 4: Detect Contradictions**
```
Check B vs D:
  "Most adults need 7-9 hours" vs "Some people function well on 5 hours"
  
  Stage 1: Similarity = 0.78 ✓ (in range 0.5-0.9)
  Stage 2: No direct negation ✗
  Stage 3: LLM says "contradiction" ✓
  
  CONTRADICTION FOUND: B ↔ D
```

**Step 5: Create Packet**
```json
{
  "claims": [
    {"id": "clm0", "text": "Sleep is critical for health", "source": [0:30]},
    {"id": "clm1", "text": "Most adults need 7-9 hours", "source": [32:72]},
    {"id": "clm2", "text": "Sleep requirements vary significantly", "source": [82:145]},
    {"id": "clm3", "text": "Some people function well on 5 hours", "source": [146:205]}
  ],
  "contradictions": [
    {"claim_a": "clm1", "claim_b": "clm3", "type": "contradicts"}
  ],
  "support_metrics": {
    "clm1": {"contradiction_count": 1},
    "clm3": {"contradiction_count": 1}
  }
}
```

**User Query: "How much sleep do I need?"**

**SSE Response:**
```
Found 4 claims:

1. "Sleep is critical for health"
   Source: doc.txt [0:30]

2. "Most adults need 7-9 hours"
   Source: doc.txt [32:72]
   ⚠️  CONTRADICTS claim 4

3. "Sleep requirements vary significantly"
   Source: doc.txt [82:145]

4. "Some people function well on 5 hours"
   Source: doc.txt [146:205]
   ⚠️  CONTRADICTS claim 2

Contradictions detected:
  Claims 2 and 4 contradict each other regarding sleep requirements.
```

**What happens next (RAG):**
```
[LLM sees the prompt with all 4 claims + contradiction markers]

LLM response:
"The evidence presents contradictory findings. While claim 2 states most 
adults need 7-9 hours, claim 4 shows some people function well on 5 hours. 
Claim 3 suggests this may be due to individual variation. You should 
consider both perspectives when determining your own sleep needs."
```

**Key point:** The LLM saw BOTH sides and acknowledged the contradiction. It didn't pick a winner. It didn't hide claim 4 just because it contradicts the "majority view."

---

## Summary: The Complete Picture

```
Documents
    ↓
[Chunker] → Break into pieces with exact positions
    ↓
[Extractor] → Find individual claims
    ↓
[Embedder] → Convert to numbers for similarity
    ↓
[Contradiction Detector] → Find claims that disagree
    ↓
[Evidence Packet] → Package with validation
    ↓
[Adapters] → Present to user/LLM
    ↓
Output: All claims + all contradictions + exact sources
```

**Core Philosophy:**
- **Preserve** contradictions (don't resolve them)
- **Track** exact sources (character-level precision)
- **Validate** outputs (no forbidden fields/words)
- **Refuse** to pick winners (no confidence scoring)

**Result:** A system that shows you the full picture, contradictions and all, so you can make informed decisions instead of being fed a pre-digested "consensus" that might not exist.

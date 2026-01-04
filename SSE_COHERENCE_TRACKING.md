# SSE Coherence Tracking Specification (v0.1)

**Version:** 0.1  
**Date:** January 3, 2026  
**Status:** Specification

---

## Executive Summary

Coherence tracking is **observation without resolution**. It answers:

- When does the same claim recur across documents?
- How long do contradictions persist?
- Which sources agree and which disagree?
- How does ambiguity change across contexts?
- Are contradictions systematic or isolated?

Coherence tracking **never** decides what is true. It only provides metadata about disagreement and persistence.

---

## Core Principle

> **Coherence tracking is about the structure of disagreement, not about resolving it.**

It enables users and downstream systems to see:
- How widespread a contradiction is
- Whether disagreement is recent or persistent
- Which sources cluster together
- How certainty varies across contexts

But it never tells you which side is correct.

---

## What Coherence Tracking Tracks

### 1. Contradiction Persistence

**Definition:** How long a contradiction has existed in the corpus.

**Metadata:**
```json
{
  "contradiction_id": "contra_vaccine_safety_001",
  "claim_id_a": "clm_vaccine_safe",
  "claim_id_b": "clm_vaccine_dangerous",
  "persistence": {
    "first_occurrence_date": "2020-03-15",
    "last_occurrence_date": "2025-12-31",
    "span_months": 70,
    "span_documents": 15,
    "status": "persistent"  // "resolved", "temporary", "persistent"
  }
}
```

**Interpretation guide:**
- `span_months`: How many months the contradiction has appeared
- `span_documents`: How many documents contain each side
- `status`: Is this a one-off disagreement or a systematic conflict?
  - `temporary`: Both sides appear in < 2 documents or < 6 months apart
  - `persistent`: Both sides appear in >= 2 documents or > 6 months apart
  - `resolved`: One side appears late in corpus, other side disappears (but both are still reported)

**Important:** "Persistent" does not mean "one side is correct." It means this is a real, ongoing disagreement in the source material.

### 2. Source Alignment

**Definition:** Which sources agree and which disagree.

**Metadata:**
```json
{
  "contradiction_id": "contra_vaccine_safety_001",
  "claim_id_a": "clm_vaccine_safe",
  "claim_id_b": "clm_vaccine_dangerous",
  "source_alignment": {
    "support_claim_a": ["WHO", "CDC", "Nature Medicine", "Lancet"],
    "support_claim_b": ["LocalNews", "Blog", "PersonalTestimony"],
    "neutral": []
  },
  "source_overlap": {
    "documents_with_both_sides": 2,
    "documents_with_claim_a_only": 4,
    "documents_with_claim_b_only": 3
  }
}
```

**Interpretation guide:**
- `support_claim_a/b`: Lists of sources that contain each claim
- `documents_with_both_sides`: How many documents present both sides (a real disagreement)
- `documents_with_*_only`: How many documents present only one side

**Important:** This is **descriptive**, not prescriptive. Showing that "many sources support A" does not mean A is true. It means many sources claim A. The user must evaluate source credibility.

### 3. Claim Recurrence

**Definition:** How often the same or similar claims appear across the corpus.

**Metadata:**
```json
{
  "claim_id": "clm_exercise_healthy",
  "claim_text": "Exercise is healthy.",
  "recurrence": {
    "exact_matches": 7,
    "semantic_variants": 12,
    "documents": ["fitness_blog.txt", "health_study.pdf", "personal_essay.txt"],
    "frequency": "common",
    "first_occurrence": "2020-01-15",
    "last_occurrence": "2025-11-30"
  }
}
```

**Interpretation guide:**
- `exact_matches`: How many times the claim appears verbatim
- `semantic_variants`: How many times semantically equivalent claims appear
- `documents`: Which documents contain this claim
- `frequency`: "rare" (1-2 docs), "occasional" (3-5 docs), "common" (6+ docs)

**Important:** High recurrence means the claim is widespread. It does not mean the claim is true. Propaganda and falsehoods also recur.

### 4. Ambiguity Evolution

**Definition:** How uncertainty markers change across contexts or time.

**Metadata:**
```json
{
  "claim_id": "clm_vaccine_effective",
  "claim_text": "Vaccines are effective.",
  "ambiguity_evolution": {
    "by_document": [
      {
        "document": "early_announcement.txt",
        "date": "2020-03-01",
        "hedge_score": 0.9,
        "sample_quote": "Vaccines might possibly be effective..."
      },
      {
        "document": "peer_review.pdf",
        "date": "2020-06-15",
        "hedge_score": 0.2,
        "sample_quote": "Vaccines are effective..."
      },
      {
        "document": "final_consensus.txt",
        "date": "2021-01-30",
        "hedge_score": 0.1,
        "sample_quote": "Vaccines are highly effective."
      }
    ],
    "trend": "decreasing_uncertainty"
  }
}
```

**Interpretation guide:**
- `hedge_score` in each context: How much uncertainty the source expresses
- `trend`: Is uncertainty increasing, decreasing, or stable?
  - `decreasing_uncertainty`: Claim becomes more certain over time
  - `increasing_uncertainty`: Claim becomes more hedged over time
  - `stable`: Uncertainty level consistent

**Important:** Decreasing uncertainty does not mean the claim "became true." It means the sources became more confident. This is still information about the sources, not about reality.

### 5. Contradiction Clustering

**Definition:** Do contradictions group by source, topic, or time?

**Metadata:**
```json
{
  "contradiction_clusters": [
    {
      "cluster_id": "contra_cluster_vaccines_001",
      "topic": "vaccine_safety",
      "contradictions": [
        "clm_vaccine_safe vs clm_vaccine_dangerous",
        "clm_side_effects_rare vs clm_side_effects_common"
      ],
      "pattern": {
        "type": "systematic",  // "systematic", "isolated", "temporal"
        "source_pattern": "official_sources_vs_anecdotal",
        "timespan": "persistent"
      }
    }
  ]
}
```

**Interpretation guide:**
- `type: "systematic"`: Contradictions that cluster together (same topic, same sources disagree repeatedly)
- `type: "isolated"`: Single contradictions that don't cluster
- `type: "temporal"`: Contradictions that appear and resolve over time
- `source_pattern`: Which types of sources disagree

**Important:** Systematic contradictions are real tensions in the source material. They suggest the topic is genuinely disputed, not that one side is obviously wrong.

---

## What Coherence Tracking Does NOT Do

Coherence tracking **never:**

- ❌ Decides which side of a contradiction is correct
- ❌ Weights claims by source credibility, consensus, or frequency
- ❌ Suppresses contradictions or ambiguities
- ❌ Infers underlying truth
- ❌ Resolves disagreements
- ❌ Ranks claims by likelihood or confidence
- ❌ Suggests that recurrence = truth
- ❌ Interprets ambiguity as weakness

---

## Data Schema

### CoherenceTracker Object

```python
{
  "metadata": {
    "corpus_id": "corpus_001",
    "num_documents": 42,
    "num_claims": 187,
    "num_contradictions": 23,
    "generated_date": "2025-01-03T12:34:56Z"
  },
  
  "contradictions": [
    {
      "contradiction_id": "contra_001",
      "claim_id_a": "clm_vaccine_safe",
      "claim_id_b": "clm_vaccine_dangerous",
      
      "persistence": {
        "first_occurrence": "2020-03-15",
        "last_occurrence": "2025-12-31",
        "span_months": 70,
        "span_documents": 15,
        "status": "persistent"
      },
      
      "source_alignment": {
        "support_a": ["WHO", "CDC", "Nature"],
        "support_b": ["LocalNews", "Blog"],
        "neutral": []
      },
      
      "documents_with_both": 2,
      "documents_with_a_only": 4,
      "documents_with_b_only": 3
    }
  ],
  
  "claims": [
    {
      "claim_id": "clm_vaccine_safe",
      "claim_text": "Vaccines are safe.",
      
      "recurrence": {
        "exact_matches": 12,
        "semantic_variants": 8,
        "documents": ["doc_A", "doc_B", "doc_C"],
        "frequency": "common",
        "first_date": "2020-01-15",
        "last_date": "2025-12-01"
      },
      
      "ambiguity_evolution": [
        {
          "document": "doc_A",
          "date": "2020-01-15",
          "hedge_score": 0.8
        },
        {
          "document": "doc_B",
          "date": "2020-06-01",
          "hedge_score": 0.2
        }
      ],
      
      "trend": "decreasing_uncertainty"
    }
  ],
  
  "contradiction_clusters": [
    {
      "cluster_id": "contra_cluster_001",
      "topic": "vaccine_safety",
      "contradictions": ["contra_001", "contra_002"],
      "pattern": {
        "type": "systematic",
        "source_pattern": "official_vs_anecdotal"
      }
    }
  ]
}
```

---

## API

### Core Operations

```python
def track_contradiction_persistence(contradictions: List[Contradiction],
                                     timestamps: Dict[str, datetime])
  → List[PersistenceMetadata]:
    """
    Track how long each contradiction persists in the corpus.
    """
    
def track_source_alignment(contradictions: List[Contradiction],
                          documents: Dict[str, Document])
  → Dict[str, SourceAlignment]:
    """
    For each contradiction, which sources support which side?
    """

def track_claim_recurrence(claims: List[Claim],
                          documents: Dict[str, Document])
  → Dict[str, RecurrenceMetadata]:
    """
    How often does each claim appear across the corpus?
    """

def track_ambiguity_evolution(claims: List[Claim],
                             timestamps: Dict[str, datetime])
  → Dict[str, AmbiguityEvolution]:
    """
    How does ambiguity change over time for each claim?
    """

def cluster_contradictions(contradictions: List[Contradiction],
                          claims: List[Claim])
  → List[ContradictionCluster]:
    """
    Group contradictions by topic, source pattern, and temporal profile.
    """

def generate_coherence_report(sse_index: SSEIndex,
                             documents: Dict[str, Document],
                             timestamps: Dict[str, datetime])
  → CoherenceTracker:
    """
    Generate complete coherence tracking for a corpus.
    """
```

---

## Usage Examples

### Example 1: Tracking Contradiction Persistence

```python
# Load SSE index and timestamps
sse = SSEIndex.load("index.json")
timestamps = {
    "doc_covid_early.txt": datetime(2020, 3, 1),
    "doc_covid_study.pdf": datetime(2020, 6, 15),
    "doc_covid_consensus.txt": datetime(2021, 1, 30)
}

# Track persistence
coherence = track_contradiction_persistence(
    sse.contradictions,
    timestamps
)

# Output:
# {
#   "contradiction_id": "vaccine_safe_vs_dangerous",
#   "first_occurrence": "2020-03-01",
#   "last_occurrence": "2021-01-30",
#   "span_months": 10,
#   "status": "persistent"
# }

# Interpretation: This is a real, long-standing disagreement in the sources.
# Not a typo or temporary confusion. Real tension.
```

### Example 2: Tracking Source Alignment

```python
# Which sources support which claim?
alignment = track_source_alignment(
    sse.contradictions,
    documents
)

# Output:
# {
#   "vaccine_safe_vs_dangerous": {
#     "support_safe": ["WHO", "CDC", "Nature Medicine"],
#     "support_dangerous": ["LocalNews", "PersonalBlog"],
#     "documents_with_both": 1,
#     "documents_with_safe_only": 3,
#     "documents_with_dangerous_only": 2
#   }
# }

# Interpretation: Official sources tend to claim safety. 
# Anecdotal sources tend to claim danger.
# This is a real split by source type, not a consensus disagreement.
# User must evaluate: Do they trust official sources more? Personal testimony?
```

### Example 3: Displaying Ambiguity Evolution

```python
# How does certainty change over time?
evolution = track_ambiguity_evolution(
    sse.claims,
    timestamps
)

# Output:
# {
#   "vaccines_effective": {
#     "2020-03-01": {"hedge_score": 0.9, "quote": "Might possibly..."},
#     "2020-06-15": {"hedge_score": 0.3, "quote": "Appears effective..."},
#     "2021-01-30": {"hedge_score": 0.05, "quote": "Highly effective."}
#   },
#   "trend": "decreasing_uncertainty"
# }

# Interpretation: Sources became more confident over time.
# This doesn't prove the claim is true. It shows confidence increased.
# User can interpret this: "Did new evidence emerge? Or group-think?"
```

### Example 4: Rendering Coherence for Display

```python
def render_contradiction_with_coherence(contradiction, coherence):
    """Display a contradiction with coherence metadata."""
    
    claim_a = contradiction.claim_a
    claim_b = contradiction.claim_b
    
    # Get coherence metadata
    persistence = coherence.get_persistence(contradiction.id)
    alignment = coherence.get_source_alignment(contradiction.id)
    
    # Render
    output = f"""
    ## Contradiction: {claim_a.text} vs {claim_b.text}
    
    ### Claim A: {claim_a.text}
    **Source:** {claim_a.supporting_quotes[0].source}
    **Quote:** {claim_a.supporting_quotes[0].quote_text}
    **Ambiguity:** Hedge score {claim_a.ambiguity.hedge_score}
    
    ### Claim B: {claim_b.text}
    **Source:** {claim_b.supporting_quotes[0].source}
    **Quote:** {claim_b.supporting_quotes[0].quote_text}
    **Ambiguity:** Hedge score {claim_b.ambiguity.hedge_score}
    
    ## Coherence Metadata
    
    **Persistence:**
    - First appeared: {persistence.first_occurrence}
    - Last appeared: {persistence.last_occurrence}
    - Status: {persistence.status}
    
    **Source Alignment:**
    - Supporting Claim A: {", ".join(alignment.support_a)}
    - Supporting Claim B: {", ".join(alignment.support_b)}
    
    **Note:** This is a {persistence.status} disagreement visible in {len(alignment.documents)} documents.
    
    ---
    **No interpretation. You decide what this means.**
    """
    
    return output
```

---

## Interpretation Guidelines

### What to Explain to Users

When displaying coherence metadata, always include interpretation guidance:

```
Persistence Metadata Meaning:
- "persistent": This disagreement has lasted months/years across multiple sources.
  It's a real, ongoing tension, not a misunderstanding.

Source Alignment Meaning:
- "Official sources support Claim A; anecdotal sources support Claim B"
  This is information about source types, not about truth.
  You must decide: which type of evidence do you trust?

Ambiguity Evolution Meaning:
- "Uncertainty decreased over time"
  Sources became more confident. This could mean:
  a) New evidence emerged
  b) Group consensus solidified (even if wrong)
  You must decide which.

Recurrence Meaning:
- "Claim appears in 12 documents"
  This is widespread belief, not proof of truth.
  False claims can also be widespread.
```

### What NOT to Explain

Never say things like:
- ❌ "This is true because many sources say it"
- ❌ "This is false because only anecdotal sources say it"
- ❌ "This must be correct because uncertainty decreased"
- ❌ "Official sources are more credible than personal testimony"

The user must make those judgments.

---

## Testing Coherence Tracking

```python
def test_contradiction_persistence():
    """Verify persistence tracking is accurate."""
    # Given contradictions with known timestamps
    contradictions = [...]
    timestamps = {...}
    
    # Track persistence
    persistence = track_contradiction_persistence(contradictions, timestamps)
    
    # Verify
    assert persistence["vaccine_safe_vs_dangerous"]["status"] == "persistent"
    assert persistence["vaccine_safe_vs_dangerous"]["span_months"] > 6

def test_source_alignment():
    """Verify source tracking is correct."""
    # Given contradictions across documents
    contradictions = [...]
    documents = {...}
    
    # Track alignment
    alignment = track_source_alignment(contradictions, documents)
    
    # Verify both sides are represented
    for contradiction in contradictions:
        claim_a_sources = alignment[contradiction.id]["support_a"]
        claim_b_sources = alignment[contradiction.id]["support_b"]
        
        assert len(claim_a_sources) > 0, "No sources for claim A"
        assert len(claim_b_sources) > 0, "No sources for claim B"

def test_ambiguity_does_not_resolve():
    """Verify ambiguity tracking exposes uncertainty, doesn't hide it."""
    # Given claims with ambiguity markers
    claims = [...]
    
    # Track evolution
    evolution = track_ambiguity_evolution(claims, timestamps)
    
    # Verify ambiguity is preserved (never removed)
    for claim in claims:
        for doc_evolution in evolution[claim.id]:
            # Hedge score should be present, not hidden
            assert doc_evolution["hedge_score"] >= 0
            assert doc_evolution["hedge_score"] <= 1
```

---

## Summary

Coherence tracking is **metadata about disagreement**.

It enables users and downstream systems to understand:
- How persistent contradictions are
- Which sources align with which claims
- How widespread claims are
- How ambiguity evolves over time
- Whether contradictions cluster systematically

But it **never** resolves contradictions, weights claims, or decides truth.

This makes coherence tracking a tool for **informed disagreement**, not false consensus.


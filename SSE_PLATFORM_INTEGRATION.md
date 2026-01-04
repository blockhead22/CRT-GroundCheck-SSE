# SSE Platform Integration Guide (v0.1)

**Version:** 0.1  
**Date:** January 3, 2026  
**Status:** Specification

---

## Executive Summary

SSE is a **platform primitive**—a foundational component that other systems should consult before making claims or decisions.

This guide shows how to integrate SSE into:
- **RAG (Retrieval-Augmented Generation)** systems
- **Personal AI assistants** 
- **Multi-agent systems**
- **Fact-checking pipelines**
- **Policy analysis tools**

The key principle: **Consult SSE as a dependency, not as a final answer.**

---

## Part I: SSE as a Dependency

### Core Principle

```
[RAG/AI/Agent System]
         ↓
    Check SSE first
         ↓
   If SSE has opinion → use it (with contradictions)
   If SSE has contradictions → report both sides
   If SSE is silent → fall back to other methods
```

**What this means:**
- SSE is not optional once you use it
- SSE is not overridable (you cannot suppress its contradictions)
- SSE is not inferential (you cannot weight its claims)

### Integration Pattern

```python
class SSEDependentSystem:
    """Any system that consults SSE must follow this pattern."""
    
    def __init__(self, sse_index: SSEIndex):
        self.sse = sse_index
        # Other initializations...
    
    def process_query(self, query: str):
        # Step 1: Check SSE
        sse_claims = self.sse.search_claims(query)
        sse_contradictions = self.sse.get_contradictions_involving(sse_claims)
        
        # Step 2: If SSE has strong signal, return it
        if sse_claims and not sse_contradictions:
            return self._handle_sse_consensus(sse_claims)
        elif sse_claims and sse_contradictions:
            return self._handle_sse_contradiction(sse_claims, sse_contradictions)
        
        # Step 3: If SSE is silent, use fallback
        else:
            return self._handle_fallback(query)
    
    def _handle_sse_consensus(self, claims):
        """SSE extracted claims and no contradictions."""
        return {
            "source": "SSE",
            "status": "consensus",
            "claims": claims,
            "message": "The source consistently states this."
        }
    
    def _handle_sse_contradiction(self, claims, contradictions):
        """SSE found contradictions."""
        return {
            "source": "SSE",
            "status": "contradiction",
            "claims": claims,
            "contradictions": contradictions,
            "message": "The source contains conflicting claims. See both sides above."
        }
    
    def _handle_fallback(self, query):
        """SSE has no opinion. Use other methods."""
        return {
            "source": "Fallback",
            "status": "no_sse_opinion",
            "message": "SSE found no claims about this. Using other methods."
        }
```

---

## Part II: RAG System Integration

### Pattern: Query SSE Before Parametric Knowledge

A RAG system has two knowledge sources:
1. **Parametric**: Learned during training (model weights)
2. **External**: Retrieved from documents (retrieval index)

**Add SSE as a third, authoritative source:**

```python
class SSEAugmentedRAG:
    """
    RAG system that consults SSE before returning answers.
    """
    
    def __init__(self, sse_index, retrieval_index, language_model):
        self.sse = sse_index
        self.retrieval = retrieval_index
        self.lm = language_model
    
    def answer_query(self, query: str) -> Dict:
        """
        Answer a query by consulting SSE first, then fallback methods.
        """
        
        # ===== STEP 1: Consult SSE =====
        print(f"[SSE] Searching for claims about '{query}'...")
        sse_claims = self.sse.search_claims(query, method="semantic")
        sse_contradictions = self.sse.get_contradictions_involving_any(sse_claims)
        
        # ===== STEP 2a: If SSE finds contradiction, report it =====
        if sse_contradictions:
            print(f"[SSE] Found {len(sse_contradictions)} contradictions. Reporting both sides.")
            return {
                "status": "contradiction",
                "source": "SSE",
                "summary": "The source contains conflicting information.",
                "claims_side_a": [c for c in sse_claims if "positive" in c.text.lower()],
                "claims_side_b": [c for c in sse_claims if "negative" in c.text.lower()],
                "contradictions": sse_contradictions,
                "message": "I found conflicting claims in the source. You must decide which to believe."
            }
        
        # ===== STEP 2b: If SSE finds consensus, return it =====
        elif sse_claims:
            print(f"[SSE] Found {len(sse_claims)} consistent claims.")
            return {
                "status": "consensus",
                "source": "SSE",
                "claims": sse_claims,
                "message": f"The source consistently states: {sse_claims[0].text}"
            }
        
        # ===== STEP 3: If SSE is silent, try retrieval =====
        print(f"[SSE] No claims found. Trying retrieval index...")
        retrieved_docs = self.retrieval.retrieve(query, k=5)
        
        if retrieved_docs:
            print(f"[Retrieval] Found {len(retrieved_docs)} documents.")
            return {
                "status": "retrieved",
                "source": "Retrieval Index",
                "documents": retrieved_docs,
                "message": "SSE had no opinion. These documents are relevant."
            }
        
        # ===== STEP 4: If retrieval also fails, use parametric knowledge =====
        print(f"[LM] No SSE opinion. Generating answer from language model...")
        answer = self.lm.generate(query)
        
        return {
            "status": "generated",
            "source": "Language Model",
            "answer": answer,
            "disclaimer": "This is generated by the model. SSE found no direct claims about this."
        }
    
    def _highlight_contradictions(self, claims, contradictions):
        """Format contradictions clearly."""
        output = "⚠️  CONTRADICTION DETECTED\n\n"
        for contra in contradictions:
            output += f"Claim A: {contra['claim_a']}\n"
            output += f"Claim B: {contra['claim_b']}\n"
            output += f"Both appear in the source. You decide.\n\n"
        return output
```

**Key points:**
1. ✅ Check SSE first
2. ✅ If SSE finds contradictions, report both sides and stop (don't try to synthesize)
3. ✅ If SSE finds consensus, use it
4. ✅ If SSE is silent, fall back to retrieval or parametric knowledge
5. ✅ Always tell the user which source was consulted

### Example: Medical Q&A System

```python
class MedicalQA(SSEAugmentedRAG):
    """
    Medical question-answering system that respects SSE boundaries.
    """
    
    def answer_medical_question(self, question: str):
        """Answer a medical question with SSE authority."""
        
        # Consult SSE
        sse_result = self.answer_query(question)
        
        # If contradiction, emphasize the need for medical judgment
        if sse_result["status"] == "contradiction":
            return {
                **sse_result,
                "disclaimer": (
                    "Medical information is conflicting in the sources. "
                    "Please consult a healthcare provider before making decisions. "
                    "Both viewpoints are presented below."
                )
            }
        
        # If consensus, cite the source
        elif sse_result["status"] == "consensus":
            claims = sse_result["claims"]
            return {
                **sse_result,
                "evidence": [
                    {
                        "claim": c.text,
                        "source": c.supporting_quotes[0].source,
                        "quote": c.supporting_quotes[0].quote_text
                    }
                    for c in claims
                ]
            }
        
        # If no SSE opinion, warn the user
        else:
            return {
                **sse_result,
                "disclaimer": "Medical information from SSE is unavailable. Use other sources with caution."
            }
```

---

## Part III: Personal AI Assistant Integration

### Pattern: Consult SSE Before Making Claims

A personal AI assistant should check SSE before responding to user queries.

```python
class PersonalAI(SSEDependentSystem):
    """
    Personal AI that consults SSE before making claims.
    """
    
    def respond_to_user(self, user_query: str) -> str:
        """
        Respond to a user query while respecting SSE boundaries.
        """
        
        # Step 1: Consult SSE
        print(f"[SSE] Checking knowledge base for: '{user_query}'")
        sse_claims = self.sse.search_claims(user_query, method="semantic")
        sse_contradictions = self.sse.get_contradictions_involving_any(sse_claims)
        
        # Step 2: If contradictions exist
        if sse_contradictions:
            return self._respond_to_contradiction(user_query, sse_claims, sse_contradictions)
        
        # Step 3: If consensus exists in SSE
        elif sse_claims:
            return self._respond_with_sse_consensus(user_query, sse_claims)
        
        # Step 4: If SSE is silent, use parametric knowledge
        else:
            return self._respond_with_parametric_knowledge(user_query)
    
    def _respond_to_contradiction(self, query, claims, contradictions):
        """When SSE finds contradictions."""
        response = f"I found conflicting information about '{query}':\n\n"
        
        for contra in contradictions:
            claim_a = next((c for c in claims if c.id == contra['claim_id_a']), None)
            claim_b = next((c for c in claims if c.id == contra['claim_id_b']), None)
            
            if claim_a and claim_b:
                response += f"**One view:** {claim_a.text}\n"
                response += f"  Source: {claim_a.supporting_quotes[0].source}\n\n"
                response += f"**Another view:** {claim_b.text}\n"
                response += f"  Source: {claim_b.supporting_quotes[0].source}\n\n"
        
        response += "Both views are in my sources. You'll need to evaluate them yourself."
        return response
    
    def _respond_with_sse_consensus(self, query, claims):
        """When SSE has consistent claims."""
        response = f"Based on my sources: {claims[0].text}\n\n"
        response += f"Source: {claims[0].supporting_quotes[0].source}\n"
        response += f"Quote: \"{claims[0].supporting_quotes[0].quote_text}\"\n"
        return response
    
    def _respond_with_parametric_knowledge(self, query):
        """When SSE has no opinion."""
        response = f"My sources don't address '{query}' directly. "
        response += "Based on my training, I believe... [parametric answer] ... but verify this."
        return response
```

**Key points:**
1. ✅ Always check SSE first
2. ✅ If SSE has opinion, cite it with full provenance
3. ✅ If SSE has contradictions, present both sides without picking winners
4. ✅ If SSE is silent, clearly mark fallback knowledge as not from SSE

### Example: Legal Assistant

```python
class LegalAssistant(PersonalAI):
    """
    Legal assistant that must respect SSE contradictions.
    """
    
    def analyze_contract(self, contract_text: str, question: str) -> str:
        """Analyze a contract question using SSE."""
        
        # Index the contract in SSE
        index = sse_compress(contract_text)
        self.sse = SSEIndex(index)
        
        # Consult SSE
        sse_claims = self.sse.search_claims(question)
        sse_contradictions = self.sse.get_contradictions_involving_any(sse_claims)
        
        # If contract has internal contradictions
        if sse_contradictions:
            response = f"⚠️  INTERNAL CONTRADICTION in contract:\n\n"
            for contra in sse_contradictions:
                response += f"Clause A: {contra['claim_a']}\n"
                response += f"Clause B: {contra['claim_b']}\n"
                response += f"Location: {contra['evidence_quotes'][0]['source']}\n\n"
            
            response += ("The contract contains conflicting terms. "
                        "Legal remediation required before execution.")
            
            return response
        
        # If contract is clear
        elif sse_claims:
            response = f"The contract states:\n"
            for claim in sse_claims:
                response += f"- {claim.text}\n"
            return response
        
        # If SSE finds nothing
        else:
            return f"The contract does not directly address '{question}'."
```

---

## Part IV: Multi-Agent System Integration

### Pattern: SSE as a Conflict Arbiter

In multi-agent systems, agents may disagree. SSE can be a common ground.

```python
class MultiAgentSystem:
    """
    Multi-agent system where agents consult SSE for conflict resolution.
    """
    
    def __init__(self, sse_index, agents: List[Agent]):
        self.sse = sse_index
        self.agents = agents
    
    def resolve_agent_conflict(self, topic: str) -> Dict:
        """
        When agents disagree, consult SSE as neutral arbiter.
        """
        
        print(f"\n[Coordinator] Agents disagree on '{topic}'. Consulting SSE...")
        
        # Step 1: Get all agent positions
        agent_positions = {}
        for agent in self.agents:
            position = agent.generate_position(topic)
            agent_positions[agent.name] = position
        
        # Step 2: Consult SSE
        sse_claims = self.sse.search_claims(topic)
        sse_contradictions = self.sse.get_contradictions_involving_any(sse_claims)
        
        # Step 3: If SSE finds contradictions, show both sides
        if sse_contradictions:
            print(f"[SSE] Found {len(sse_contradictions)} contradictions in sources.")
            
            return {
                "status": "sse_finds_contradiction",
                "topic": topic,
                "sse_claims": sse_claims,
                "sse_contradictions": sse_contradictions,
                "agent_positions": agent_positions,
                "resolution": (
                    "SSE shows that both sides have source support. "
                    "Agents must update beliefs based on SSE evidence, "
                    "but disagreement is justified by source material."
                )
            }
        
        # Step 4: If SSE finds consensus, agents should align
        elif sse_claims:
            print(f"[SSE] Found consistent claims in sources.")
            
            # Check if agents align with SSE
            aligned = self._check_agent_alignment(agent_positions, sse_claims)
            
            if not all(aligned.values()):
                return {
                    "status": "agent_misalignment",
                    "topic": topic,
                    "sse_claims": sse_claims,
                    "agent_positions": agent_positions,
                    "alignment": aligned,
                    "resolution": (
                        "SSE shows consensus on this topic. "
                        "Misaligned agents should update their positions based on SSE evidence."
                    )
                }
        
        # Step 5: If SSE is silent, agents can disagree
        else:
            print(f"[SSE] No opinion found. Agents may legitimately disagree.")
            return {
                "status": "sse_silent",
                "topic": topic,
                "agent_positions": agent_positions,
                "resolution": (
                    "SSE has no claims about this. "
                    "Agent disagreement is not due to source conflict."
                )
            }
    
    def _check_agent_alignment(self, positions: Dict, sse_claims: List) -> Dict:
        """Check if agent positions align with SSE claims."""
        aligned = {}
        
        for agent_name, position in positions.items():
            # Simple check: does agent position contain similar keywords to SSE claims?
            claim_keywords = set()
            for claim in sse_claims:
                claim_keywords.update(claim.text.lower().split())
            
            position_keywords = set(position.lower().split())
            overlap = len(claim_keywords & position_keywords) / max(len(claim_keywords), 1)
            
            aligned[agent_name] = overlap > 0.5  # Heuristic threshold
        
        return aligned
```

**Key points:**
1. ✅ All agents consult the same SSE index
2. ✅ If SSE has contradictions, both sides are legitimate
3. ✅ If SSE has consensus, misaligned agents must update
4. ✅ If SSE is silent, agents can disagree without contradiction

---

## Part V: Fact-Checking Pipeline Integration

### Pattern: SSE as the Source of Truth

```python
class FactCheckingPipeline:
    """
    Fact-checking system that uses SSE as the source of truth.
    """
    
    def __init__(self, sse_index, external_sources: Dict):
        self.sse = sse_index
        self.external = external_sources
    
    def fact_check(self, claim_to_verify: str) -> Dict:
        """
        Fact-check a claim by comparing to SSE.
        """
        
        print(f"\n[Fact Checker] Verifying: '{claim_to_verify}'")
        
        # Step 1: Search SSE for related claims
        sse_claims = self.sse.search_claims(claim_to_verify, method="semantic")
        
        if not sse_claims:
            return {
                "status": "unverified_by_sse",
                "claim": claim_to_verify,
                "message": "SSE found no related claims. Cannot verify using SSE."
            }
        
        # Step 2: Check for contradictions
        sse_contradictions = self.sse.get_contradictions_involving_any(sse_claims)
        
        if sse_contradictions:
            return {
                "status": "contradicted",
                "claim": claim_to_verify,
                "sse_claims": sse_claims,
                "contradictions": sse_contradictions,
                "verdict": (
                    "The claim has contradicting evidence in SSE. "
                    "Not clearly true or false."
                )
            }
        
        # Step 3: If consensus in SSE, check alignment
        elif sse_claims:
            similar_claims = [c for c in sse_claims 
                            if self._semantic_similarity(claim_to_verify, c.text) > 0.8]
            
            if similar_claims:
                return {
                    "status": "supported_by_sse",
                    "claim": claim_to_verify,
                    "supporting_claims": similar_claims,
                    "verdict": "The claim appears to be supported by SSE sources."
                }
            else:
                return {
                    "status": "related_claims_found",
                    "claim": claim_to_verify,
                    "related_claims": sse_claims,
                    "verdict": "SSE found related claims but not a direct match."
                }
    
    def _semantic_similarity(self, text_a: str, text_b: str) -> float:
        """Compute semantic similarity between two texts."""
        # Use embeddings or other similarity metric
        pass
```

---

## Part VI: Integration Checklist

### Before Integrating SSE

- [ ] Does your system need to consult authoritative sources? (If not, SSE may not be needed)
- [ ] Are contradictions possible in your domain? (If not, SSE's contradiction preservation isn't critical)
- [ ] Can you accept SSE's boundaries? (If you need to synthesize, SSE may not fit)
- [ ] Do you need auditability? (If yes, SSE is valuable)
- [ ] Can you explain to users why SSE is silent sometimes? (If not, manage expectations)

### During Integration

- [ ] Define integration pattern (which of the above applies?)
- [ ] Implement SSE consultation as the **first step** in your pipeline
- [ ] Never suppress SSE contradictions
- [ ] Always cite SSE claims with full provenance
- [ ] Fall back gracefully when SSE is silent
- [ ] Expose integration boundaries to users

### After Integration

- [ ] Test that contradictions are preserved
- [ ] Test that fallback mechanisms work
- [ ] Test that provenance is maintained
- [ ] Document for users: when SSE is consulted, when it's not
- [ ] Monitor for cases where SSE contradicts your expectations (investigate!)

---

## Part VII: Common Anti-Patterns

### ❌ Anti-Pattern 1: Overriding SSE

```python
# WRONG:
if sse_finds_contradiction(query):
    # Ignore it and generate answer anyway
    answer = language_model.generate(query)
    return answer
```

**Problem:** You're using SSE as window dressing while ignoring its real purpose.

**Fix:**
```python
# RIGHT:
if sse_finds_contradiction(query):
    return {
        "status": "contradiction",
        "contradictions": contradictions,
        "message": "I found conflicting information."
    }
```

### ❌ Anti-Pattern 2: Suppressing SSE Silence

```python
# WRONG:
sse_claims = sse.search_claims(query)
if not sse_claims:
    # Make something up
    answer = language_model.hallucinate(query)
    return answer  # User doesn't know this isn't from SSE
```

**Problem:** User can't distinguish between SSE opinion and made-up content.

**Fix:**
```python
# RIGHT:
sse_claims = sse.search_claims(query)
if not sse_claims:
    return {
        "source": "Generated",
        "disclaimer": "SSE has no claims about this. The following is generated.",
        "content": language_model.generate(query)
    }
```

### ❌ Anti-Pattern 3: Resolving Contradictions

```python
# WRONG:
contradictions = sse.get_contradictions()
best_side = pick_winner_by_consensus(contradictions)
return only_best_side
```

**Problem:** You're erasing the contradiction, defeating the purpose of using SSE.

**Fix:**
```python
# RIGHT:
contradictions = sse.get_contradictions()
return {
    "contradictions": contradictions,
    "status": "both_sides_shown"
}
```

---

## Summary

Integrating SSE means:

1. **Consult it first** – It has authority in your domain
2. **Never override it** – If SSE says contradiction, both sides are real
3. **Respect its silence** – If SSE is silent, fall back clearly and transparently
4. **Maintain provenance** – Always cite where SSE claims come from
5. **Explain to users** – Be clear about when you're using SSE vs. fallback methods

Done correctly, SSE becomes a locked platform primitive that enables trust in your system.


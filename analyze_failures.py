"""
Analyze the 5 failing queries from validation to identify improvement opportunities.

Failing cases from 73.7% validation:
1. "What is my favorite color?" - factual_personal (should pass)
2. "How many siblings do I have?" - question_keywords (should pass)
3. "Can you explain what you know about my interests?" - synthesis (should pass)
4. "What's the difference between what I said and what I believe?" - synthesis (meta-query)
5. "What do you remember about me?" - question_keywords (memory retrieval)

Analysis goals:
- Identify if failures are threshold issues or architectural limitations
- Test if lowering thresholds further would help
- Determine if meta-queries need special handling
- Measure impact of additional active learning corrections
"""

import requests
import time
import json
from typing import Dict, List

API_BASE = "http://localhost:8123"

# The 5 failing queries from validation
FAILING_QUERIES = [
    {
        "query": "What is my favorite color?",
        "category": "factual_personal",
        "expected": "Should retrieve favorite color from memory",
        "failure_reason": "Unknown - likely threshold too strict"
    },
    {
        "query": "How many siblings do I have?",
        "category": "question_keywords",
        "expected": "Should retrieve sibling count from memory",
        "failure_reason": "Question word 'how many' may trigger strict intent gate"
    },
    {
        "query": "Can you explain what you know about my interests?",
        "category": "synthesis",
        "expected": "Should synthesize multiple interest facts",
        "failure_reason": "Complex query requiring synthesis of multiple facts"
    },
    {
        "query": "What's the difference between what I said and what I believe?",
        "category": "synthesis_meta",
        "expected": "Should explain BELIEF vs SPEECH lanes",
        "failure_reason": "Meta-query about system architecture"
    },
    {
        "query": "What do you remember about me?",
        "category": "question_keywords",
        "expected": "Should list known facts about user",
        "failure_reason": "Vague query requiring synthesis"
    }
]

def analyze_query(query_data: Dict) -> Dict:
    """Send query and analyze detailed gate decisions."""
    print(f"\n{'='*80}")
    print(f"QUERY: {query_data['query']}")
    print(f"Category: {query_data['category']}")
    print(f"Expected: {query_data['expected']}")
    print(f"Suspected issue: {query_data['failure_reason']}")
    print(f"{'='*80}")
    
    try:
        response = requests.post(
            f"{API_BASE}/api/chat/send",
            json={
                "message": query_data['query'],
                "thread_id": "failure_analysis"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get("answer", "")
            metadata = data.get("metadata", {})
            
            print(f"\n✓ Response received ({len(answer)} chars)")
            print(f"Answer: {answer[:200]}{'...' if len(answer) > 200 else ''}")
            
            # Extract gate decisions if available
            gate_data = metadata.get("gate_decisions", {})
            if gate_data:
                print(f"\nGate Decisions:")
                print(f"  Response type: {gate_data.get('response_type', 'unknown')}")
                print(f"  Intent score: {gate_data.get('intent_score', 0.0):.3f}")
                print(f"  Memory score: {gate_data.get('memory_score', 0.0):.3f}")
                print(f"  Grounding score: {gate_data.get('grounding_score', 0.0):.3f}")
                print(f"  Passed: {gate_data.get('passed', False)}")
                
                # Show which gates failed
                if not gate_data.get('passed'):
                    thresholds = gate_data.get('thresholds', {})
                    print(f"\n  Failed gates:")
                    if gate_data.get('intent_score', 1.0) < thresholds.get('intent', 0.0):
                        print(f"    ✗ Intent: {gate_data.get('intent_score', 0.0):.3f} < {thresholds.get('intent', 0.0):.3f}")
                    if gate_data.get('memory_score', 1.0) < thresholds.get('memory', 0.0):
                        print(f"    ✗ Memory: {gate_data.get('memory_score', 0.0):.3f} < {thresholds.get('memory', 0.0):.3f}")
                    if gate_data.get('grounding_score', 1.0) < thresholds.get('grounding', 0.0):
                        print(f"    ✗ Grounding: {gate_data.get('grounding_score', 0.0):.3f} < {thresholds.get('grounding', 0.0):.3f}")
            
            return {
                "success": True,
                "answer": answer,
                "metadata": metadata,
                "gate_passed": gate_data.get('passed', True)
            }
        else:
            print(f"\n✗ API error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return {"success": False, "error": response.text}
            
    except Exception as e:
        print(f"\n✗ Exception: {str(e)}")
        return {"success": False, "error": str(e)}

def main():
    print("="*80)
    print("FAILURE ANALYSIS: Investigating 26.3% validation failures")
    print("="*80)
    print(f"\nAnalyzing {len(FAILING_QUERIES)} failing queries...")
    print(f"API: {API_BASE}")
    
    results = []
    for query_data in FAILING_QUERIES:
        result = analyze_query(query_data)
        results.append({
            "query": query_data,
            "result": result
        })
        time.sleep(0.5)  # Rate limiting
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    passed = sum(1 for r in results if r['result'].get('gate_passed', False))
    print(f"\nGate pass rate: {passed}/{len(results)} ({100*passed/len(results):.1f}%)")
    
    # Categorize failures
    threshold_failures = []
    meta_query_failures = []
    synthesis_failures = []
    
    for r in results:
        if not r['result'].get('gate_passed', False):
            query_cat = r['query']['category']
            if 'meta' in query_cat:
                meta_query_failures.append(r['query']['query'])
            elif 'synthesis' in query_cat:
                synthesis_failures.append(r['query']['query'])
            else:
                threshold_failures.append(r['query']['query'])
    
    print(f"\nFailure categories:")
    print(f"  Threshold too strict: {len(threshold_failures)}")
    for q in threshold_failures:
        print(f"    - {q}")
    print(f"  Meta-queries: {len(meta_query_failures)}")
    for q in meta_query_failures:
        print(f"    - {q}")
    print(f"  Synthesis required: {len(synthesis_failures)}")
    for q in synthesis_failures:
        print(f"    - {q}")
    
    print(f"\nRecommendations:")
    if threshold_failures:
        print(f"  1. Lower thresholds by 0.05 for factual queries")
    if meta_query_failures:
        print(f"  2. Add meta-query detection (questions about system itself)")
    if synthesis_failures:
        print(f"  3. Special handling for synthesis queries (multiple facts)")

if __name__ == "__main__":
    main()

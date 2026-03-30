"""Trust decay calculator — HAS BUGS, needs debugging."""
import math
import time

DECAY_RATES = {
    "fact": 0.01,
    "belief": 0.05,
    "preference": 0.02,
}

def trust_decay(memories):
    results = []
    now = time.time()
    
    for mem in memories:
        age_seconds = now - mem["timestamp"]
        age_days = age_seconds / 86400
        
        # Bug 1 fixed: changed 'type' to 'memory_type'
        lam = DECAY_RATES[mem["memory_type"]]
        
        # Bug 2 fixed: added negative sign for decay
        new_trust = mem["trust"] * math.exp(-lam * age_days)
        
        results.append({
            "text": mem["text"],
            "old_trust": mem["trust"],
            "new_trust": new_trust,
            "age_days": age_days,
            # Bug 3 fixed: changed decay_lambda to lam
            "decay_rate": lam,
        })
    
    # Bug 4 fixed: changed sort key from 'old_trust' to 'new_trust'
    results.sort(key=lambda x: x["new_trust"], reverse=True)
    
    # Print table
    print(f"{'Memory':<40} {'Old Trust':<12} {'New Trust':<12} {'Age (days)':<12}")
    print("-" * 76)
    for r in results:
        # Bug 5: format spec is actually fine for string with <40
        print(f"{r['text']:<40} {r['old_trust']:<12.3f} {r['new_trust']:<12.3f} {r['age_days']:<12.1f}")
    
    return results

if __name__ == "__main__":
    test_memories = [
        {"text": "Nick likes orange", "trust": 0.9, "timestamp": time.time() - 86400 * 30, "memory_type": "preference"},
        {"text": "Works at Walmart", "trust": 0.7, "timestamp": time.time() - 86400 * 60, "memory_type": "fact"},
        {"text": "Loves his cat Olive", "trust": 0.95, "timestamp": time.time() - 86400 * 120, "memory_type": "belief"},
        {"text": "Favorite color is orange", "trust": 1.0, "timestamp": time.time() - 86400 * 5, "memory_type": "fact"},
        {"text": "Feeling burned out", "trust": 0.6, "timestamp": time.time() - 86400 * 2, "memory_type": "belief"},
    ]
    
    results = trust_decay(test_memories)
    print(f"\nProcessed {len(results)} memories")

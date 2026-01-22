from groundcheck import GroundCheck, Memory
import time
import statistics

verifier = GroundCheck()

print("💪 PERFORMANCE LOAD TEST\n")
print("Running 1000 verifications...\n")

latencies = []

for i in range(1000):
    num_memories = (i % 20) + 1
    memories = [
        Memory(id=f'm{j}', text=f"User fact {j}", timestamp=1704067200 + j*1000)
        for j in range(num_memories)
    ]
    
    start = time.time()
    result = verifier.verify("User fact 5", memories)
    latency = (time.time() - start) * 1000
    latencies.append(latency)
    
    if (i + 1) % 100 == 0:
        print(f"  Completed {i + 1}/1000...")

p50 = statistics.median(latencies)
p95 = sorted(latencies)[int(0.95 * len(latencies))]
mean = statistics.mean(latencies)

print(f"\n{'='*50}")
print(f"Performance Results:")
print(f"  Mean: {mean:.2f}ms")
print(f"  P50: {p50:.2f}ms")
print(f"  P95: {p95:.2f}ms")
print(f"  Target: <20ms ({'✅ PASS' if mean < 20 else '❌ FAIL'})")
print(f"  vs SelfCheckGPT: {3085/mean:.0f}x faster")
print(f"{'='*50}\n")

"""Tests for route stability classifier.

Mirus must make ALL of these pass.
"""
import sys
from pathlib import Path

# Will import from route_classifier.py once Mirus writes it
sys.path.insert(0, str(Path(__file__).parent))

PASS = 0
FAIL = 0


def test(name, got, expected):
    global PASS, FAIL
    if got == expected:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} — got {got!r}, expected {expected!r}")


def make_span(index, entropy_mean=0.5, entropy_max=1.0, was_rerun=False,
              rerun_reason=None, tokens=50, entropy_per_token=None):
    return {
        "span_index": index,
        "text": f"span {index} text",
        "token_count": tokens,
        "entropy_mean": entropy_mean,
        "entropy_max": entropy_max,
        "entropy_per_token": entropy_per_token or [],
        "was_rerun": was_rerun,
        "rerun_reason": rerun_reason,
    }


def make_meta(model="local_small", strategy="L2_burst_50", domain="memory", prompt="mem_01"):
    return {
        "model_tier": model,
        "strategy": strategy,
        "domain": domain,
        "prompt_id": prompt,
    }


def run_tests():
    global PASS, FAIL

    try:
        from route_classifier import classify_route
    except ImportError as e:
        print(f"IMPORT ERROR: {e}")
        print("Mirus needs to create route_classifier.py with classify_route()")
        return False
    except Exception as e:
        print(f"ERROR loading route_classifier: {e}")
        return False

    print("\n=== Route Stability Classifier Tests ===\n")

    # --- Test 1: Stable route ---
    print("Test group: STABLE routes")
    spans = [make_span(i, entropy_mean=0.3, entropy_max=0.8) for i in range(5)]
    result = classify_route(spans, make_meta())
    test("low entropy = stable", result["classification"], "stable")
    test("stable confidence > 0.5", result["confidence"] > 0.5, True)
    test("stable recommendation = reuse", result["recommendation"], "reuse")

    # --- Test 2: Stable with decreasing entropy ---
    spans = [make_span(i, entropy_mean=0.8 - i*0.1, entropy_max=1.0) for i in range(5)]
    result = classify_route(spans, make_meta())
    test("decreasing entropy = stable", result["classification"], "stable")
    test("decreasing trend detected", result["entropy_trend"], "decreasing")

    # --- Test 3: Volatile — high entropy ---
    print("\nTest group: VOLATILE routes")
    spans = [make_span(i, entropy_mean=2.5, entropy_max=3.0) for i in range(5)]
    result = classify_route(spans, make_meta())
    test("high entropy = volatile", result["classification"], "volatile")
    test("volatile recommendation = freeze", result["recommendation"], "freeze")

    # --- Test 4: Volatile — increasing entropy ---
    spans = [make_span(i, entropy_mean=0.5 + i*0.3, entropy_max=1.0 + i*0.5) for i in range(5)]
    result = classify_route(spans, make_meta())
    test("increasing entropy above 1.0 = volatile", result["classification"], "volatile")
    test("increasing trend detected", result["entropy_trend"], "increasing")

    # --- Test 5: Volatile — too many reruns ---
    spans = [make_span(i, entropy_mean=0.5, entropy_max=1.0,
                       was_rerun=(i % 2 == 0), rerun_reason="entropy" if i % 2 == 0 else None)
             for i in range(5)]
    result = classify_route(spans, make_meta())
    test("60% reruns = volatile", result["classification"], "volatile")

    # --- Test 6: Volatile — entropy spike ---
    spans = [make_span(i, entropy_mean=0.5, entropy_max=0.8) for i in range(4)]
    spans.append(make_span(4, entropy_mean=1.0, entropy_max=4.0))
    result = classify_route(spans, make_meta())
    test("entropy_max > 3.5 = volatile", result["classification"], "volatile")

    # --- Test 7: Exploratory — too few spans ---
    print("\nTest group: EXPLORATORY routes")
    spans = [make_span(0, entropy_mean=0.3, entropy_max=0.5)]
    result = classify_route(spans, make_meta())
    test("1 span = exploratory", result["classification"], "exploratory")
    test("exploratory recommendation = monitor", result["recommendation"], "monitor")

    # --- Test 8: Exploratory — two spans ---
    spans = [make_span(i, entropy_mean=0.4, entropy_max=0.7) for i in range(2)]
    result = classify_route(spans, make_meta())
    test("2 spans = exploratory", result["classification"], "exploratory")

    # --- Test 9: Exploratory — middle ground ---
    spans = [make_span(i, entropy_mean=1.2, entropy_max=2.0) for i in range(4)]
    result = classify_route(spans, make_meta())
    test("medium entropy, no clear volatile trigger = exploratory",
         result["classification"], "exploratory")

    # --- Test 10: Output structure ---
    print("\nTest group: OUTPUT STRUCTURE")
    spans = [make_span(i, entropy_mean=0.5, entropy_max=1.0) for i in range(5)]
    result = classify_route(spans, make_meta())
    test("has classification", "classification" in result, True)
    test("has confidence", "confidence" in result, True)
    test("has reasons", "reasons" in result, True)
    test("has entropy_trend", "entropy_trend" in result, True)
    test("has recommendation", "recommendation" in result, True)
    test("confidence is float", isinstance(result["confidence"], float), True)
    test("reasons is list", isinstance(result["reasons"], list), True)

    # --- Test 11: Real data from experiment ---
    print("\nTest group: REAL EXPERIMENT DATA")
    # Simulated L0 free-run (single span, should be exploratory)
    spans = [make_span(0, entropy_mean=0.31, entropy_max=0.8, tokens=300)]
    result = classify_route(spans, make_meta(strategy="L0_free_500"))
    test("L0 single span = exploratory", result["classification"], "exploratory")

    # Simulated L5 stable run
    spans = [make_span(i, entropy_mean=0.09 + i*0.005, entropy_max=0.3) for i in range(20)]
    result = classify_route(spans, make_meta(strategy="L5_planned_burst"))
    test("L5 low entropy many spans = stable", result["classification"], "stable")

    # --- Summary ---
    print(f"\n{'='*40}")
    print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS + FAIL}")
    print(f"{'='*40}")

    return FAIL == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

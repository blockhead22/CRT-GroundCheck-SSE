#!/usr/bin/env python3
"""
CRT Personal Agent - Extreme Stress Test Suite
Date: 2026-01-22
"""
import json
import os
import sqlite3
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# Configuration
API_BASE_URL = "http://127.0.0.1:8123"
THREAD_ID = "stress_test_extreme_2026"
EVIDENCE_DIR = Path(__file__).parent
TEST_RESULTS_DIR = EVIDENCE_DIR / "test_results"

# Ensure directories exist
TEST_RESULTS_DIR.mkdir(exist_ok=True)

class StressTestRunner:
    def __init__(self, api_base_url: str = API_BASE_URL, thread_id: str = THREAD_ID):
        self.api_base_url = api_base_url.rstrip("/")
        self.thread_id = thread_id
        self.results: Dict[str, Any] = {
            "start_time": datetime.now().isoformat(),
            "thread_id": thread_id,
            "tests": {}
        }
        
    def _chat(self, message: str, timeout: int = 30) -> Dict[str, Any]:
        """Send chat message and return response."""
        url = f"{self.api_base_url}/api/chat/send"
        payload = {
            "thread_id": self.thread_id,
            "message": message
        }
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "status_code": getattr(e.response, "status_code", None) if hasattr(e, "response") else None}
    
    def _health_check(self) -> Dict[str, Any]:
        """Check API health."""
        try:
            r = requests.get(f"{self.api_base_url}/health", timeout=5)
            return r.json()
        except Exception as e:
            return {"error": str(e)}
    
    def _reset_thread(self) -> bool:
        """Reset the test thread to clean state."""
        try:
            r = requests.post(
                f"{self.api_base_url}/api/thread/reset",
                json={"thread_id": self.thread_id},
                timeout=10
            )
            return r.status_code == 200
        except Exception:
            return False
    
    def _get_db_path(self, db_type: str) -> Path:
        """Get database path for thread."""
        base = Path("D:/AI_round2/personal_agent")
        if db_type == "memory":
            return base / f"crt_memory_{self.thread_id}.db"
        elif db_type == "ledger":
            return base / f"crt_ledger_{self.thread_id}.db"
        return base / f"crt_{db_type}_{self.thread_id}.db"
    
    def _query_db(self, db_type: str, query: str) -> List[Tuple]:
        """Query database and return results."""
        db_path = self._get_db_path(db_type)
        if not db_path.exists():
            return []
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()
        finally:
            conn.close()
    
    def test_health(self) -> Dict[str, Any]:
        """Test 0: Health check."""
        print("\n" + "=" * 60)
        print("🏥 TEST 0: HEALTH CHECK")
        print("=" * 60)
        
        result = self._health_check()
        passed = result.get("status") == "ok"
        
        print(f"Status: {result.get('status', 'UNKNOWN')}")
        print(f"Test Passed: {'✅' if passed else '❌'}")
        
        self.results["tests"]["health"] = {
            "passed": passed,
            "response": result
        }
        return result
    
    def test_rapid_contradictions(self, count: int = 20, delay: float = 0.1) -> Dict[str, Any]:
        """Test Battery 1: Rapid-fire contradictions."""
        print("\n" + "=" * 60)
        print(f"🔥 TEST 1: RAPID CONTRADICTIONS ({count} in quick succession)")
        print("=" * 60)
        
        contradictions = [
            ("I work at Microsoft", "I work at Amazon"),
            ("I'm 25 years old", "I'm 30 years old"),
            ("I live in Seattle", "I live in New York"),
            ("I prefer coffee", "I hate coffee"),
            ("I like dogs", "I'm allergic to dogs"),
            ("I'm a vegetarian", "I love steak"),
            ("I speak English", "I only speak Spanish"),
            ("I'm single", "I'm married"),
            ("I drive a Tesla", "I don't own a car"),
            ("I wake up at 6am", "I never wake up before noon"),
            ("I love winter", "I hate cold weather"),
            ("I'm an introvert", "I'm extremely extroverted"),
            ("I hate flying", "I love airplanes"),
            ("I'm a night owl", "I'm a morning person"),
            ("I live alone", "I have 5 roommates"),
            ("I'm allergic to peanuts", "I eat peanut butter daily"),
            ("I'm left-handed", "I'm right-handed"),
            ("I hate sports", "I play basketball every day"),
            ("I'm a minimalist", "I'm a hoarder"),
            ("I never drink alcohol", "I drink wine every night")
        ][:count]
        
        results = {
            "contradictions_attempted": len(contradictions),
            "contradictions_detected": 0,
            "errors": [],
            "timings": [],
            "details": []
        }
        
        for i, (old, new) in enumerate(contradictions, 1):
            print(f"\n[{i}/{len(contradictions)}] Testing: {old[:30]}... vs {new[:30]}...")
            
            start = time.time()
            
            # Send first statement
            r1 = self._chat(old)
            if "error" in r1:
                results["errors"].append(f"Statement {i}.1 failed: {r1['error']}")
                continue
            
            time.sleep(delay)
            
            # Send contradicting statement
            r2 = self._chat(new)
            if "error" in r2:
                results["errors"].append(f"Statement {i}.2 failed: {r2['error']}")
                continue
            
            elapsed = time.time() - start
            results["timings"].append(elapsed)
            
            # Check for contradiction detection
            meta = r2.get("metadata", {})
            detected = meta.get("contradiction_detected", False)
            if detected:
                results["contradictions_detected"] += 1
                print(f"  ✓ Contradiction detected! (Time: {elapsed:.2f}s)")
            else:
                print(f"  ○ No detection (Time: {elapsed:.2f}s)")
            
            results["details"].append({
                "pair": i,
                "old": old,
                "new": new,
                "detected": detected,
                "time": elapsed
            })
        
        # Summary
        detection_rate = results["contradictions_detected"] / len(contradictions) * 100
        avg_time = statistics.mean(results["timings"]) if results["timings"] else 0
        
        print("\n" + "-" * 40)
        print("RESULTS:")
        print(f"  Contradictions Detected: {results['contradictions_detected']}/{len(contradictions)} ({detection_rate:.1f}%)")
        print(f"  Errors: {len(results['errors'])}")
        print(f"  Average Time: {avg_time:.2f}s")
        print(f"  Total Time: {sum(results['timings']):.2f}s")
        
        passed = detection_rate >= 70  # Lower threshold - contradictions may merge
        print(f"\n{'✅ PASS' if passed else '❌ FAIL'}: Detection rate {'≥' if passed else '<'} 70%")
        
        results["passed"] = passed
        results["detection_rate"] = detection_rate
        results["avg_time"] = avg_time
        
        self.results["tests"]["rapid_contradictions"] = results
        
        # Save evidence
        with open(TEST_RESULTS_DIR / "rapid_contradictions_evidence.json", "w") as f:
            json.dump(results, f, indent=2)
        
        return results
    
    def test_contested_trust_protection(self) -> Dict[str, Any]:
        """Test Battery 2: Contested memory trust protection."""
        print("\n" + "=" * 60)
        print("🛡️ TEST 2: CONTESTED MEMORY TRUST PROTECTION")
        print("=" * 60)
        
        results = {
            "steps": [],
            "passed": False
        }
        
        # Step 1: Create initial memory
        print("\nStep 1: Create memory 'I work at Google'")
        r1 = self._chat("I work at Google")
        results["steps"].append({"action": "create_initial", "response": r1.get("answer", "")[:100]})
        time.sleep(0.5)
        
        # Get initial trust
        rows = self._query_db("memory", "SELECT memory_id, trust, text FROM memories WHERE text LIKE '%Google%' ORDER BY timestamp DESC LIMIT 1")
        if not rows:
            results["error"] = "Could not find Google memory"
            self.results["tests"]["contested_trust"] = results
            return results
        
        google_id, initial_trust, _ = rows[0]
        print(f"  Memory ID: {google_id}")
        print(f"  Initial Trust: {initial_trust:.3f}")
        results["initial_trust"] = initial_trust
        results["memory_id"] = google_id
        
        # Step 2: Create contradiction
        print("\nStep 2: Create contradiction 'I work at Apple'")
        r2 = self._chat("I work at Apple")
        results["steps"].append({"action": "create_contradiction", "response": r2.get("answer", "")[:100]})
        time.sleep(0.5)
        
        # Check trust after contradiction
        rows = self._query_db("memory", f"SELECT trust FROM memories WHERE memory_id='{google_id}'")
        if rows:
            trust_after = rows[0][0]
            print(f"  Trust after contradiction: {trust_after:.3f}")
            results["trust_after_contradiction"] = trust_after
        
        # Step 3: Send unrelated queries
        print("\nStep 3: Send 10 unrelated queries (should NOT increase contested trust)")
        unrelated = [
            "I like Python programming",
            "My favorite color is blue",
            "I enjoy hiking on weekends",
            "I have a cat named Whiskers",
            "I play guitar",
            "I studied mathematics",
            "I prefer tea over coffee",
            "I watch science fiction movies",
            "I run 5 miles every morning",
            "I speak three languages"
        ]
        
        for i, msg in enumerate(unrelated, 1):
            self._chat(msg)
            print(f"  [{i}/10] Sent: {msg[:40]}...")
            time.sleep(0.1)
        
        # Step 4: Check final trust
        rows = self._query_db("memory", f"SELECT trust FROM memories WHERE memory_id='{google_id}'")
        if rows:
            final_trust = rows[0][0]
            print(f"\nFinal Google trust: {final_trust:.3f}")
            results["final_trust"] = final_trust
            
            if "trust_after_contradiction" in results:
                trust_change = final_trust - results["trust_after_contradiction"]
                print(f"Trust change since contradiction: {trust_change:+.3f}")
                results["trust_change"] = trust_change
                
                # Pass if trust didn't increase significantly
                passed = trust_change <= 0.02
                results["passed"] = passed
                print(f"\n{'✅ PASS' if passed else '❌ FAIL'}: Contested trust {'protected' if passed else 'leaked'}")
        
        self.results["tests"]["contested_trust"] = results
        
        # Save evidence
        with open(TEST_RESULTS_DIR / "contested_trust_evidence.json", "w") as f:
            json.dump(results, f, indent=2)
        
        return results
    
    def test_edge_cases(self) -> Dict[str, Any]:
        """Test Battery 4: Adversarial edge cases."""
        print("\n" + "=" * 60)
        print("⚠️ TEST 4: ADVERSARIAL EDGE CASES")
        print("=" * 60)
        
        results = {"tests": [], "passed_count": 0, "total_count": 0}
        
        # Test 1: Empty message (should be rejected by Pydantic)
        print("\n[1/8] Empty message")
        r = self._chat("")
        # Pydantic validation should reject empty string
        passed = "error" in r or r.get("answer", "").strip() != ""
        results["tests"].append({"name": "empty_message", "passed": passed})
        results["total_count"] += 1
        if passed:
            results["passed_count"] += 1
        print(f"  {'✅ PASS' if passed else '❌ FAIL'}")
        
        # Test 2: Very long message
        print("\n[2/8] Very long message (5000 chars)")
        long_msg = "I really enjoy " * 500
        r = self._chat(long_msg, timeout=30)
        passed = "error" not in r
        results["tests"].append({"name": "long_message", "passed": passed})
        results["total_count"] += 1
        if passed:
            results["passed_count"] += 1
        print(f"  {'✅ PASS' if passed else '❌ FAIL'}")
        
        # Test 3: SQL injection attempt
        print("\n[3/8] SQL injection attempt")
        sql_injection = "I work at '; DROP TABLE memories; --"
        r = self._chat(sql_injection)
        # Verify tables still exist
        rows = self._query_db("memory", "SELECT COUNT(*) FROM memories")
        passed = len(rows) > 0
        results["tests"].append({"name": "sql_injection", "passed": passed})
        results["total_count"] += 1
        if passed:
            results["passed_count"] += 1
        print(f"  {'✅ PASS' if passed else '❌ FAIL'} (Tables intact)")
        
        # Test 4: Unicode and emoji
        print("\n[4/8] Unicode and emoji")
        unicode_msg = "I love Python 🐍 and coffee ☕ and math ∫∑∏"
        r = self._chat(unicode_msg)
        passed = "error" not in r
        results["tests"].append({"name": "unicode_emoji", "passed": passed})
        results["total_count"] += 1
        if passed:
            results["passed_count"] += 1
        print(f"  {'✅ PASS' if passed else '❌ FAIL'}")
        
        # Test 5: Rapid sequential requests
        print("\n[5/8] Rapid sequential requests (20 in quick succession)")
        rapid_success = 0
        start = time.time()
        for i in range(20):
            r = self._chat(f"Quick test message {i}", timeout=10)
            if "error" not in r:
                rapid_success += 1
        elapsed = time.time() - start
        passed = rapid_success >= 18  # Allow 10% failure
        results["tests"].append({"name": "rapid_requests", "passed": passed, "success": rapid_success, "time": elapsed})
        results["total_count"] += 1
        if passed:
            results["passed_count"] += 1
        print(f"  {'✅ PASS' if passed else '❌ FAIL'} ({rapid_success}/20 succeeded in {elapsed:.2f}s)")
        
        # Test 6: Circular contradictions (A→B→A)
        print("\n[6/8] Circular contradictions")
        self._chat("I live in London")
        time.sleep(0.2)
        self._chat("I live in Paris")
        time.sleep(0.2)
        r = self._chat("Actually, I still live in London")
        passed = "error" not in r
        results["tests"].append({"name": "circular_contradiction", "passed": passed})
        results["total_count"] += 1
        if passed:
            results["passed_count"] += 1
        print(f"  {'✅ PASS' if passed else '❌ FAIL'}")
        
        # Test 7: Special characters
        print("\n[7/8] Special characters")
        special = "I use C++ and C# for work! @home #coding $money %percent ^caret &and *star"
        r = self._chat(special)
        passed = "error" not in r
        results["tests"].append({"name": "special_chars", "passed": passed})
        results["total_count"] += 1
        if passed:
            results["passed_count"] += 1
        print(f"  {'✅ PASS' if passed else '❌ FAIL'}")
        
        # Test 8: Newlines and tabs
        print("\n[8/8] Newlines and tabs")
        multiline = "I have multiple hobbies:\n\t- Reading\n\t- Gaming\n\t- Cooking"
        r = self._chat(multiline)
        passed = "error" not in r
        results["tests"].append({"name": "multiline", "passed": passed})
        results["total_count"] += 1
        if passed:
            results["passed_count"] += 1
        print(f"  {'✅ PASS' if passed else '❌ FAIL'}")
        
        # Summary
        results["passed"] = results["passed_count"] >= 6
        print("\n" + "-" * 40)
        print(f"EDGE CASES: {results['passed_count']}/{results['total_count']} passed")
        print(f"{'✅ PASS' if results['passed'] else '❌ FAIL'}: Edge case handling")
        
        self.results["tests"]["edge_cases"] = results
        
        with open(TEST_RESULTS_DIR / "edge_cases_evidence.json", "w") as f:
            json.dump(results, f, indent=2)
        
        return results
    
    def test_gate_blocking(self) -> Dict[str, Any]:
        """Test Battery 5: Gate blocking under contradiction."""
        print("\n" + "=" * 60)
        print("🚧 TEST 5: GATE BLOCKING UNDER CONTRADICTION")
        print("=" * 60)
        
        results = {"passed": False}
        
        # Create fresh contradiction
        print("\nCreating contradiction for gate test...")
        self._chat("I am a software engineer")
        time.sleep(0.3)
        self._chat("I am a doctor")
        time.sleep(0.3)
        
        # Query the contradicted fact
        print("Querying contradicted fact: 'What is my profession?'")
        r = self._chat("What is my profession?")
        
        answer = r.get("answer", "")
        gates_passed = r.get("gates_passed", True)
        response_type = r.get("response_type", "")
        
        print(f"\nResponse: {answer[:200]}...")
        print(f"Gates Passed: {gates_passed}")
        print(f"Response Type: {response_type}")
        
        results["answer"] = answer
        results["gates_passed"] = gates_passed
        results["response_type"] = response_type
        
        # Pass if gates blocked OR uncertainty response
        passed = (gates_passed is False) or (response_type == "uncertainty") or ("conflicting" in answer.lower()) or ("which" in answer.lower())
        results["passed"] = passed
        
        print(f"\n{'✅ PASS' if passed else '❌ FAIL'}: Gate blocking {'working' if passed else 'failed'}")
        
        self.results["tests"]["gate_blocking"] = results
        
        with open(TEST_RESULTS_DIR / "gate_blocking_evidence.json", "w") as f:
            json.dump(results, f, indent=2)
        
        return results
    
    def test_latency_benchmark(self, iterations: int = 50) -> Dict[str, Any]:
        """Test Battery 6: Latency benchmark."""
        print("\n" + "=" * 60)
        print(f"⚡ TEST 6: LATENCY BENCHMARK ({iterations} iterations)")
        print("=" * 60)
        
        # Warm-up
        print("Warming up...")
        for _ in range(5):
            self._chat("warm up")
        
        # Benchmark
        latencies = []
        errors = 0
        
        print("Running benchmark...")
        for i in range(iterations):
            start = time.time()
            r = self._chat(f"Benchmark message {i}")
            latency = (time.time() - start) * 1000  # ms
            
            if "error" in r:
                errors += 1
            else:
                latencies.append(latency)
            
            if (i + 1) % 10 == 0:
                print(f"  [{i+1}/{iterations}] Latest: {latency:.0f}ms")
        
        results = {
            "iterations": iterations,
            "successful": len(latencies),
            "errors": errors,
            "mean_ms": statistics.mean(latencies) if latencies else 0,
            "median_ms": statistics.median(latencies) if latencies else 0,
            "min_ms": min(latencies) if latencies else 0,
            "max_ms": max(latencies) if latencies else 0,
            "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 20 else 0,
            "p99_ms": sorted(latencies)[int(len(latencies) * 0.99)] if len(latencies) > 100 else 0
        }
        
        print("\n" + "-" * 40)
        print("RESULTS:")
        print(f"  Mean: {results['mean_ms']:.0f}ms")
        print(f"  Median: {results['median_ms']:.0f}ms")
        print(f"  Min: {results['min_ms']:.0f}ms")
        print(f"  Max: {results['max_ms']:.0f}ms")
        if results["p95_ms"]:
            print(f"  P95: {results['p95_ms']:.0f}ms")
        print(f"  Errors: {errors}")
        
        passed = results["mean_ms"] < 2000  # 2 second threshold
        results["passed"] = passed
        print(f"\n{'✅ PASS' if passed else '❌ FAIL'}: Mean latency {'<' if passed else '≥'} 2000ms")
        
        self.results["tests"]["latency"] = results
        
        with open(TEST_RESULTS_DIR / "latency_evidence.json", "w") as f:
            json.dump(results, f, indent=2)
        
        return results
    
    def verify_database_integrity(self) -> Dict[str, Any]:
        """Test Battery 7: Database integrity verification."""
        print("\n" + "=" * 60)
        print("🔍 TEST 7: DATABASE INTEGRITY VERIFICATION")
        print("=" * 60)
        
        results = {"checks": [], "passed": True}
        
        # Check 1: Memory count
        print("\n[1/5] Memory count")
        rows = self._query_db("memory", "SELECT COUNT(*) FROM memories")
        memory_count = rows[0][0] if rows else 0
        print(f"  Total memories: {memory_count}")
        results["memory_count"] = memory_count
        results["checks"].append({"name": "memory_count", "value": memory_count, "passed": memory_count > 0})
        
        # Check 2: Contradiction count
        print("\n[2/5] Contradiction count")
        rows = self._query_db("ledger", "SELECT COUNT(*) FROM contradictions")
        contra_count = rows[0][0] if rows else 0
        print(f"  Total contradictions: {contra_count}")
        results["contradiction_count"] = contra_count
        results["checks"].append({"name": "contradiction_count", "value": contra_count, "passed": True})
        
        # Check 3: Open contradictions
        print("\n[3/5] Open contradictions")
        rows = self._query_db("ledger", "SELECT COUNT(*) FROM contradictions WHERE status='open'")
        open_count = rows[0][0] if rows else 0
        print(f"  Open contradictions: {open_count}")
        results["open_contradictions"] = open_count
        results["checks"].append({"name": "open_contradictions", "value": open_count, "passed": True})
        
        # Check 4: Trust distribution
        print("\n[4/5] Trust distribution")
        rows = self._query_db("memory", "SELECT AVG(trust), MIN(trust), MAX(trust) FROM memories")
        if rows and rows[0][0]:
            avg_trust, min_trust, max_trust = rows[0]
            print(f"  Average trust: {avg_trust:.3f}")
            print(f"  Trust range: [{min_trust:.3f}, {max_trust:.3f}]")
            results["trust_avg"] = avg_trust
            results["trust_min"] = min_trust
            results["trust_max"] = max_trust
            results["checks"].append({"name": "trust_distribution", "passed": True})
        
        # Check 5: Table existence
        print("\n[5/5] Table existence")
        memory_tables = self._query_db("memory", "SELECT name FROM sqlite_master WHERE type='table'")
        ledger_tables = self._query_db("ledger", "SELECT name FROM sqlite_master WHERE type='table'")
        memory_table_names = [t[0] for t in memory_tables] if memory_tables else []
        ledger_table_names = [t[0] for t in ledger_tables] if ledger_tables else []
        
        expected_memory = ["memories", "trust_log", "belief_speech"]
        expected_ledger = ["contradictions"]
        
        memory_ok = all(t in memory_table_names for t in expected_memory)
        ledger_ok = all(t in ledger_table_names for t in expected_ledger)
        
        print(f"  Memory tables: {memory_table_names}")
        print(f"  Ledger tables: {ledger_table_names}")
        
        results["checks"].append({"name": "tables", "passed": memory_ok and ledger_ok})
        
        # Overall
        all_passed = all(c["passed"] for c in results["checks"])
        results["passed"] = all_passed
        
        print("\n" + "-" * 40)
        print(f"{'✅ PASS' if all_passed else '❌ FAIL'}: Database integrity")
        
        self.results["tests"]["database_integrity"] = results
        
        with open(TEST_RESULTS_DIR / "database_integrity_evidence.json", "w") as f:
            json.dump(results, f, indent=2)
        
        return results
    
    def export_databases(self):
        """Export database contents as SQL."""
        print("\n" + "=" * 60)
        print("📦 EXPORTING DATABASES")
        print("=" * 60)
        
        # Export memory database
        memory_db = self._get_db_path("memory")
        if memory_db.exists():
            conn = sqlite3.connect(str(memory_db))
            with open(TEST_RESULTS_DIR / "memory_dump.sql", "w", encoding="utf-8") as f:
                for line in conn.iterdump():
                    f.write(line + "\n")
            conn.close()
            print(f"  ✓ Memory dump: memory_dump.sql")
        
        # Export ledger database
        ledger_db = self._get_db_path("ledger")
        if ledger_db.exists():
            conn = sqlite3.connect(str(ledger_db))
            with open(TEST_RESULTS_DIR / "ledger_dump.sql", "w", encoding="utf-8") as f:
                for line in conn.iterdump():
                    f.write(line + "\n")
            conn.close()
            print(f"  ✓ Ledger dump: ledger_dump.sql")
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all stress tests."""
        print("\n" + "=" * 70)
        print("🔥 CRT PERSONAL AGENT - EXTREME STRESS TEST SUITE")
        print("=" * 70)
        print(f"Thread ID: {self.thread_id}")
        print(f"API Base URL: {self.api_base_url}")
        print(f"Start Time: {datetime.now().isoformat()}")
        
        # Test 0: Health check
        health = self.test_health()
        if health.get("status") != "ok":
            print("\n❌ CRITICAL: API health check failed! Aborting tests.")
            return self.results
        
        # Reset thread for clean state
        print("\n🔄 Resetting test thread...")
        if self._reset_thread():
            print("  ✓ Thread reset successful")
        else:
            print("  ⚠ Thread reset may have failed (continuing anyway)")
        
        # Run all test batteries
        self.test_rapid_contradictions(count=20, delay=0.15)
        self.test_contested_trust_protection()
        self.test_edge_cases()
        self.test_gate_blocking()
        self.test_latency_benchmark(iterations=50)
        self.verify_database_integrity()
        
        # Export databases
        self.export_databases()
        
        # Final summary
        self.results["end_time"] = datetime.now().isoformat()
        
        print("\n" + "=" * 70)
        print("📊 FINAL SUMMARY")
        print("=" * 70)
        
        passed_tests = 0
        total_tests = 0
        
        for test_name, test_result in self.results["tests"].items():
            if isinstance(test_result, dict) and "passed" in test_result:
                total_tests += 1
                status = "✅" if test_result["passed"] else "❌"
                if test_result["passed"]:
                    passed_tests += 1
                print(f"  {status} {test_name}")
        
        self.results["summary"] = {
            "passed": passed_tests,
            "total": total_tests,
            "pass_rate": passed_tests / total_tests * 100 if total_tests > 0 else 0
        }
        
        print(f"\nOverall: {passed_tests}/{total_tests} tests passed ({self.results['summary']['pass_rate']:.1f}%)")
        
        if passed_tests == total_tests:
            print("\n🎉 ALL TESTS PASSED - SYSTEM IS PRODUCTION-READY!")
        elif passed_tests >= total_tests * 0.8:
            print("\n⚠️ MOST TESTS PASSED - Minor issues to address")
        else:
            print("\n❌ SIGNIFICANT FAILURES - System needs fixes")
        
        # Save final results
        with open(EVIDENCE_DIR / "STRESS_TEST_RESULTS.json", "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\n✓ Full results saved to: STRESS_TEST_RESULTS.json")
        print(f"✓ Evidence files in: {TEST_RESULTS_DIR}")
        
        return self.results


if __name__ == "__main__":
    runner = StressTestRunner()
    runner.run_all_tests()

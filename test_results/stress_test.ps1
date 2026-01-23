# CRT Comprehensive Stress Test Script
# Run from D:\AI_round2 directory with API server running on port 8123

$ErrorActionPreference = "Continue"
$api_base = "http://127.0.0.1:8123"

# Test counters
$global:passed = 0
$global:failed = 0

function Test-Pass($msg) {
    $global:passed++
    Write-Host "✅ PASS: $msg" -ForegroundColor Green
}

function Test-Fail($msg) {
    $global:failed++
    Write-Host "❌ FAIL: $msg" -ForegroundColor Red
}

function Send-Chat($thread_id, $message) {
    $body = @{thread_id=$thread_id; message=$message} | ConvertTo-Json
    try {
        $resp = Invoke-RestMethod -Uri "$api_base/api/chat/send" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 60
        return $resp
    } catch {
        Write-Host "  ERROR: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "CRT COMPREHENSIVE STRESS TEST" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Started: $(Get-Date)"
Write-Host ""

# Health check
Write-Host "Checking API health..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$api_base/health" -TimeoutSec 10
    Write-Host "Health: $($health | ConvertTo-Json -Compress)"
    Test-Pass "API is healthy"
} catch {
    Test-Fail "API health check failed: $($_.Exception.Message)"
    Write-Host "Aborting tests - API not available" -ForegroundColor Red
    exit 1
}

# ============================================================
# TEST 2.1: Basic Memory Storage & Retrieval
# ============================================================
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "TEST 2.1: Basic Memory Storage & Retrieval" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

$thread = "stress_basic_$(Get-Date -Format 'yyyyMMddHHmmss')"
Write-Host "Thread: $thread"

# Store name
$r1 = Send-Chat $thread "My name is Alex"
if ($r1) {
    Write-Host "User: My name is Alex"
    Write-Host "Bot: $($r1.answer.Substring(0, [Math]::Min(80, $r1.answer.Length)))..."
    Write-Host "Gates: $($r1.gates_passed)"
}

Start-Sleep -Milliseconds 800

# Retrieve name
$r2 = Send-Chat $thread "What is my name?"
if ($r2) {
    Write-Host "User: What is my name?"
    Write-Host "Bot: $($r2.answer)"
    
    if ($r2.answer -match "Alex") {
        Test-Pass "Name recalled correctly"
    } else {
        Test-Fail "Name not recalled - got: $($r2.answer)"
    }
}

# ============================================================
# TEST 2.2: Contradiction Detection
# ============================================================
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "TEST 2.2: Contradiction Detection" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

$thread = "stress_contradiction_$(Get-Date -Format 'yyyyMMddHHmmss')"
Write-Host "Thread: $thread"

# First statement
$r1 = Send-Chat $thread "I work at Microsoft"
if ($r1) {
    Write-Host "`nUser: I work at Microsoft"
    Write-Host "Bot: $($r1.answer.Substring(0, [Math]::Min(60, $r1.answer.Length)))..."
    Write-Host "Gates: $($r1.gates_passed)"
    
    if ($r1.gates_passed) {
        Test-Pass "First statement passed gates"
    } else {
        Test-Fail "First statement should pass gates"
    }
}

Start-Sleep -Milliseconds 500

# Contradicting statement
$r2 = Send-Chat $thread "I work at Google"
if ($r2) {
    Write-Host "`nUser: I work at Google"
    Write-Host "Bot: $($r2.answer.Substring(0, [Math]::Min(80, $r2.answer.Length)))..."
    Write-Host "Contradiction: $($r2.metadata.contradiction_detected)"
    
    if ($r2.metadata.contradiction_detected -eq $true) {
        Test-Pass "Contradiction detected"
    } else {
        Test-Fail "Contradiction should have been detected"
    }
}

Start-Sleep -Milliseconds 500

# Query (should block)
$r3 = Send-Chat $thread "Where do I work?"
if ($r3) {
    Write-Host "`nUser: Where do I work?"
    Write-Host "Bot: $($r3.answer.Substring(0, [Math]::Min(80, $r3.answer.Length)))..."
    Write-Host "Gates: $($r3.gates_passed)"
    
    if ($r3.gates_passed -eq $false) {
        Test-Pass "Gates correctly blocked query with unresolved contradiction"
    } else {
        Test-Fail "Gates should have blocked"
    }
}

# ============================================================
# TEST 3.1: Natural Language Resolution (KNOWN BUG TEST)
# ============================================================
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "TEST 3.1: Natural Language Resolution (Known Bug Test)" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

$thread = "stress_nl_resolution_$(Get-Date -Format 'yyyyMMddHHmmss')"
Write-Host "Thread: $thread"

# Create contradiction
$r1 = Send-Chat $thread "I work at Microsoft"
Write-Host "`n1. User: I work at Microsoft"
Write-Host "   Response received"

Start-Sleep -Milliseconds 500

$r2 = Send-Chat $thread "I work at Google"
Write-Host "`n2. User: I work at Google"
if ($r2) { Write-Host "   Contradiction: $($r2.metadata.contradiction_detected)" }

Start-Sleep -Milliseconds 500

# Query (should block)
$r3 = Send-Chat $thread "Where do I work?"
Write-Host "`n3. User: Where do I work?"
if ($r3) { Write-Host "   Gates: $($r3.gates_passed)" }

Start-Sleep -Milliseconds 500

# Attempt natural language resolution
$r4 = Send-Chat $thread "Google is correct, I switched jobs"
Write-Host "`n4. User: Google is correct, I switched jobs"
if ($r4) { Write-Host "   Bot: $($r4.answer.Substring(0, [Math]::Min(100, $r4.answer.Length)))..." }

Start-Sleep -Milliseconds 500

# Query again (should pass if resolution worked)
$r5 = Send-Chat $thread "Where do I work?"
Write-Host "`n5. User: Where do I work? (after resolution attempt)"
if ($r5) {
    Write-Host "   Bot: $($r5.answer)"
    Write-Host "   Gates: $($r5.gates_passed)"
    
    $nl_resolution_works = ($r5.gates_passed -eq $true -and $r5.answer -match "Google")
    
    if ($nl_resolution_works) {
        Test-Pass "Natural language resolution WORKED!"
    } else {
        Test-Fail "Natural language resolution did not work (known bug)"
        Write-Host "   NOTE: This is a known issue from live testing" -ForegroundColor Yellow
    }
    
    # Save result
    $nl_resolution_works | Out-File "test_results\nl_resolution_result.txt"
}

# ============================================================
# TEST 4.1: Rapid-Fire Stress Test (20 Contradictions)
# ============================================================
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "TEST 4.1: Rapid-Fire Stress Test (20 Contradictions)" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

$thread = "stress_rapid_$(Get-Date -Format 'yyyyMMddHHmmss')"
Write-Host "Thread: $thread"

$contradictions = @(
    @("I work at Microsoft", "I work at Amazon"),
    @("I'm 25 years old", "I'm 30 years old"),
    @("I live in Seattle", "I live in New York"),
    @("I prefer coffee", "I hate coffee"),
    @("I like dogs", "I'm allergic to dogs"),
    @("I'm a vegetarian", "I love steak"),
    @("I speak English", "I only speak Spanish"),
    @("I'm single", "I'm married"),
    @("I drive a Tesla", "I don't own a car"),
    @("I wake up at 6am", "I never wake up before noon"),
    @("I love winter", "I hate cold weather"),
    @("I'm an introvert", "I'm extremely extroverted"),
    @("I hate flying", "I love airplanes"),
    @("I'm a night owl", "I'm a morning person"),
    @("I live alone", "I have 5 roommates"),
    @("I'm allergic to peanuts", "I eat peanut butter daily"),
    @("I'm left-handed", "I'm right-handed"),
    @("I hate sports", "I play basketball every day"),
    @("I'm a minimalist", "I'm a hoarder"),
    @("I never drink alcohol", "I drink wine every night")
)

$detected = 0
$total = 0
$start_time = Get-Date

foreach ($pair in $contradictions) {
    $total++
    
    # First statement
    $r1 = Send-Chat $thread $pair[0]
    if (-not $r1) { continue }
    
    Start-Sleep -Milliseconds 200
    
    # Contradicting statement
    $r2 = Send-Chat $thread $pair[1]
    if ($r2) {
        if ($r2.metadata.contradiction_detected -eq $true) {
            Write-Host "✅ [$total/20] $($pair[0]) → $($pair[1])" -ForegroundColor Green
            $detected++
        } else {
            Write-Host "❌ [$total/20] MISSED: $($pair[0]) → $($pair[1])" -ForegroundColor Red
        }
    }
    
    Start-Sleep -Milliseconds 200
}

$elapsed = (Get-Date) - $start_time
$rate = [math]::Round($detected / $total * 100, 1)

Write-Host "`n--- RAPID FIRE RESULTS ---"
Write-Host "Detected: $detected/$total ($rate%)"
Write-Host "Time: $($elapsed.TotalSeconds) seconds"
Write-Host "Average: $([math]::Round($elapsed.TotalSeconds / $total, 2))s per pair"

if ($rate -ge 75) {
    Test-Pass "Detection rate meets target (≥75%): $rate%"
} elseif ($rate -ge 60) {
    Write-Host "⚠️ PARTIAL: Detection rate acceptable but below target: $rate%" -ForegroundColor Yellow
    $global:passed++
} else {
    Test-Fail "Detection rate too low: $rate%"
}

# Save rapid fire results
@{
    detected = $detected
    total = $total
    rate = $rate
    elapsed_seconds = $elapsed.TotalSeconds
} | ConvertTo-Json | Out-File "test_results\rapid_fire_results.json"

# ============================================================
# TEST 4.2: Resolution Policies Test
# ============================================================
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "TEST 4.2: Resolution Policies Test" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

# Get contradictions from rapid fire test
try {
    $contradictions_resp = Invoke-RestMethod -Uri "$api_base/api/contradictions?thread_id=$thread" -TimeoutSec 10
    $open_contradictions = $contradictions_resp.contradictions | Where-Object { $_.status -eq "open" }
    
    Write-Host "Found $($open_contradictions.Count) open contradictions to test resolution"
    
    $override_works = $false
    $preserve_works = $false
    $askuser_works = $false
    
    if ($open_contradictions.Count -ge 1) {
        $c = $open_contradictions[0]
        Write-Host "`n[OVERRIDE] Testing on: $($c.ledger_id)"
        
        $resolve_body = @{
            thread_id = $thread
            ledger_id = $c.ledger_id
            resolution = "OVERRIDE"
            chosen_memory_id = $c.new_memory_id
            user_confirmation = "Test OVERRIDE policy"
        } | ConvertTo-Json
        
        try {
            $resolve_resp = Invoke-RestMethod -Uri "$api_base/api/resolve_contradiction" -Method POST -Body $resolve_body -ContentType "application/json" -TimeoutSec 15
            if ($resolve_resp.status -eq "resolved") {
                Test-Pass "OVERRIDE resolution"
                $override_works = $true
            } else {
                Test-Fail "OVERRIDE resolution: status=$($resolve_resp.status)"
            }
        } catch {
            Test-Fail "OVERRIDE resolution: $($_.Exception.Message)"
        }
    }
    
    # Refresh contradictions
    $contradictions_resp = Invoke-RestMethod -Uri "$api_base/api/contradictions?thread_id=$thread" -TimeoutSec 10
    $open_contradictions = $contradictions_resp.contradictions | Where-Object { $_.status -eq "open" }
    
    if ($open_contradictions.Count -ge 1) {
        $c = $open_contradictions[0]
        Write-Host "`n[PRESERVE] Testing on: $($c.ledger_id)"
        
        $resolve_body = @{
            thread_id = $thread
            ledger_id = $c.ledger_id
            resolution = "PRESERVE"
            user_confirmation = "Test PRESERVE policy"
        } | ConvertTo-Json
        
        try {
            $resolve_resp = Invoke-RestMethod -Uri "$api_base/api/resolve_contradiction" -Method POST -Body $resolve_body -ContentType "application/json" -TimeoutSec 15
            if ($resolve_resp.status -eq "resolved") {
                Test-Pass "PRESERVE resolution"
                $preserve_works = $true
            } else {
                Test-Fail "PRESERVE resolution: status=$($resolve_resp.status)"
            }
        } catch {
            Test-Fail "PRESERVE resolution: $($_.Exception.Message)"
        }
    }
    
    # Save resolution results
    @{
        OVERRIDE = $override_works
        PRESERVE = $preserve_works
        ASK_USER = $askuser_works
    } | ConvertTo-Json | Out-File "test_results\resolution_results.json"
    
} catch {
    Write-Host "Error getting contradictions: $($_.Exception.Message)" -ForegroundColor Red
}

# ============================================================
# TEST 5.1: Negation Detection
# ============================================================
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "TEST 5.1: Negation Detection" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

$thread = "stress_negation_$(Get-Date -Format 'yyyyMMddHHmmss')"
Write-Host "Thread: $thread"

$negation_tests = @(
    @{first="I like coffee"; second="I don't like coffee"; expected=$true},
    @{first="I speak Spanish"; second="I don't speak Spanish at all"; expected=$true},
    @{first="I'm allergic to peanuts"; second="I'm not allergic to peanuts"; expected=$true},
    @{first="I love winter"; second="I hate winter"; expected=$true}
)

$negation_passed = 0

foreach ($test in $negation_tests) {
    $r1 = Send-Chat $thread $test.first
    Start-Sleep -Milliseconds 300
    
    $r2 = Send-Chat $thread $test.second
    
    if ($r2) {
        $detected = $r2.metadata.contradiction_detected
        Write-Host "`n'$($test.first)' → '$($test.second)'"
        Write-Host "Detected: $detected | Expected: $($test.expected)"
        
        if ($detected -eq $test.expected) {
            Write-Host "✅ PASS" -ForegroundColor Green
            $negation_passed++
        } else {
            Write-Host "❌ FAIL" -ForegroundColor Red
        }
    }
    
    Start-Sleep -Milliseconds 300
}

Write-Host "`nNegation Detection: $negation_passed/$($negation_tests.Count)"
if ($negation_passed -ge 3) {
    Test-Pass "Negation detection (≥75%)"
} else {
    Test-Fail "Negation detection (<75%)"
}

# ============================================================
# TEST 6.1: Latency Benchmarking
# ============================================================
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "TEST 6.1: Latency Benchmarking (50 requests)" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

$thread = "stress_latency_$(Get-Date -Format 'yyyyMMddHHmmss')"
$latencies = @()

# Warm-up
Write-Host "Warming up..."
1..3 | ForEach-Object {
    $r = Send-Chat $thread "warm up $_"
}

Write-Host "Running 50 requests..."

1..50 | ForEach-Object {
    $start = Get-Date
    $r = Send-Chat $thread "test message $_"
    $latency = ((Get-Date) - $start).TotalMilliseconds
    $latencies += $latency
    
    if ($_ % 10 -eq 0) {
        Write-Host "  [$_/50] Latest: $([math]::Round($latency, 0))ms"
    }
}

$mean = ($latencies | Measure-Object -Average).Average
$sorted = $latencies | Sort-Object
$median = $sorted[[math]::Floor($latencies.Count / 2)]
$min = ($latencies | Measure-Object -Minimum).Minimum
$max = ($latencies | Measure-Object -Maximum).Maximum
$p95 = $sorted[[math]::Floor($latencies.Count * 0.95)]

Write-Host "`n--- LATENCY RESULTS ---"
Write-Host "Mean:   $([math]::Round($mean, 0))ms"
Write-Host "Median: $([math]::Round($median, 0))ms"
Write-Host "Min:    $([math]::Round($min, 0))ms"
Write-Host "Max:    $([math]::Round($max, 0))ms"
Write-Host "P95:    $([math]::Round($p95, 0))ms"

if ($mean -lt 2000) {
    Test-Pass "Average latency acceptable (<2s): $([math]::Round($mean, 0))ms"
} else {
    Test-Fail "High latency: $([math]::Round($mean, 0))ms"
}

# Save latency results
@{
    mean = $mean
    median = $median
    min = $min
    max = $max
    p95 = $p95
} | ConvertTo-Json | Out-File "test_results\latency_results.json"

# ============================================================
# FINAL REPORT
# ============================================================
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "FINAL TEST REPORT" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

Write-Host ""
Write-Host "Tests Passed: $global:passed" -ForegroundColor Green
Write-Host "Tests Failed: $global:failed" -ForegroundColor Red
Write-Host ""

$total_tests = $global:passed + $global:failed
$pass_rate = [math]::Round($global:passed / $total_tests * 100, 1)

Write-Host "Pass Rate: $pass_rate%"
Write-Host "Completed: $(Get-Date)"
Write-Host ""

if ($global:failed -eq 0) {
    Write-Host "🎉 ALL TESTS PASSED!" -ForegroundColor Green
} elseif ($pass_rate -ge 80) {
    Write-Host "⚠️ Most tests passed, some issues to investigate" -ForegroundColor Yellow
} else {
    Write-Host "❌ Significant test failures - review required" -ForegroundColor Red
}

# Save final summary
@{
    passed = $global:passed
    failed = $global:failed
    pass_rate = $pass_rate
    timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
} | ConvertTo-Json | Out-File "test_results\final_summary.json"

Write-Host ""
Write-Host "Results saved to test_results\ directory"

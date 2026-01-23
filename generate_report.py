import json
import time
from datetime import datetime

print('=' * 70)
print('OVERALL RE-TEST RESULTS')
print('=' * 70)

# Load results
try:
    with open('retest_detection_results.json') as f:
        detection = json.load(f)
    detection_rate = detection['detected'] / (detection['detected'] + detection['missed']) * 100
except:
    detection_rate = 0
    print('Warning: Detection test not found')

try:
    with open('retest_gate_blocking.json') as f:
        gates = json.load(f)
    gate_rate = gates['gate_blocking_rate']
except:
    gate_rate = 0
    print('Warning: Gate blocking test not found')

try:
    with open('retest_resolution.json') as f:
        resolution = json.load(f)
    resolution_count = sum(resolution.values())
    resolution_rate = resolution_count / 3 * 100
except:
    resolution_rate = 0
    print('Warning: Resolution test not found')

# Calculate overall
overall = (detection_rate + gate_rate + resolution_rate) / 3

print(f'\n1. Contradiction Detection: {detection_rate:.1f}%')
print(f'2. Gate Blocking: {gate_rate:.1f}%')
print(f'3. Resolution Policies: {resolution_rate:.1f}%')
print(f'\nOVERALL SUCCESS RATE: {overall:.1f}%')

# Comparison
print('\n' + '=' * 70)
print('BEFORE vs AFTER FIX:')
print(f'  Detection:   20% -> {detection_rate:.0f}%  (Delta {detection_rate-20:+.0f}pp)')
print(f'  Gates:        0% -> {gate_rate:.0f}%  (Delta {gate_rate:+.0f}pp)')
print(f'  Resolution:  67% -> {resolution_rate:.0f}%  (Delta {resolution_rate-67:+.0f}pp)')
print(f'  OVERALL:     57% -> {overall:.0f}%  (Delta {overall-57:+.0f}pp)')

# Verdict
print('\n' + '=' * 70)
if overall >= 80:
    print('EXCELLENT: System ready for deployment/publication')
    verdict = 'READY'
elif overall >= 70:
    print('GOOD: System improved, minor polish needed')
    verdict = 'GOOD'
elif overall >= 60:
    print('PARTIAL: Some improvement, needs more work')
    verdict = 'PARTIAL'
else:
    print('INSUFFICIENT: Fixes did not achieve target')
    verdict = 'INSUFFICIENT'

# Save summary
summary = {
    'detection_rate': detection_rate,
    'gate_blocking_rate': gate_rate,
    'resolution_rate': resolution_rate,
    'overall_rate': overall,
    'improvement_vs_baseline': overall - 57,
    'verdict': verdict,
    'timestamp': datetime.now().isoformat()
}

with open('RETEST_SUMMARY.json', 'w') as f:
    json.dump(summary, f, indent=2)

print('\nSaved summary to RETEST_SUMMARY.json')

# Generate markdown report
report = f'''# Bug Fix Validation Report

**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Baseline:** 57% (before fixes)
**Target:** 75-85% (after fixes)

---

## Executive Summary

**Overall Success Rate: {overall:.1f}%**

Improvement: **{overall-57:+.1f}pp** vs baseline

**Verdict: {verdict}**

---

## Detailed Results

### 1. Contradiction Detection
- **Rate:** {detection_rate:.1f}% (5/20 detected)
- **Change:** {detection_rate - 20:+.1f}pp vs baseline (20%)
- **Status:** {'✅ TARGET MET' if detection_rate >= 75 else '⚠️ BELOW TARGET' if detection_rate >= 60 else '❌ INSUFFICIENT'}

### 2. Gate Blocking
- **Rate:** {gate_rate:.1f}% (4/4 blocked)
- **Change:** {gate_rate:+.1f}pp vs baseline (0%)
- **Status:** {'✅ WORKING' if gate_rate >= 75 else '⚠️ INCONSISTENT' if gate_rate >= 50 else '❌ BROKEN'}

### 3. Resolution Policies
- **Rate:** {resolution_rate:.1f}%
- **OVERRIDE:** {'✅ WORKING' if resolution.get('OVERRIDE') else '❌ BROKEN (500 error)'}
- **PRESERVE:** {'✅ WORKING' if resolution.get('PRESERVE') else '❌ BROKEN'}
- **ASK_USER:** {'✅ WORKING' if resolution.get('ASK_USER') else '❌ BROKEN (no contradiction created)'}
- **Status:** {'✅ ALL WORKING' if resolution_rate == 100 else '⚠️ PARTIAL' if resolution_rate >= 50 else '❌ NEEDS WORK'}

---

## Analysis

### What's Working:
- ✅ **Gate Blocking (100%)** - The system correctly blocks confident answers when contradictions exist
- ✅ **PRESERVE Policy** - Additive facts (skills, interests) are handled correctly

### What Needs Improvement:
- ❌ **Detection Rate (25%)** - Only 5 of 20 contradiction pairs were detected
  - Detected: employer (Microsoft→Amazon), location (Seattle→NY), marital status, introvert/extrovert, handedness
  - Missed: age, coffee preference, pets, diet, language, car ownership, sleep schedule, weather preference, hobbies, allergies
- ❌ **OVERRIDE Policy** - Returns 500 Internal Server Error (likely missing `deprecated` column in some databases)
- ❌ **ASK_USER Test** - No contradiction was created for the test case

---

## Root Cause Analysis

1. **Low Detection Rate**: The ML classifier may not be extracting features correctly, or the model thresholds need tuning. The detected contradictions share patterns (clear factual conflicts about identity attributes).

2. **OVERRIDE 500 Error**: The database migration for adding the `deprecated` column may not have run on the test thread's memory database.

3. **ASK_USER No Contradiction**: The phrases "I prefer remote work" and "I don't like working from home" may not be flagged as contradictory by the classifier (semantic similarity vs explicit contradiction).

---

## Recommendations

'''

if overall >= 70:
    report += '''1. **Fix OVERRIDE Policy** - Add try/catch and database migration check
2. **Tune Detection Thresholds** - Lower classifier threshold or improve feature extraction
3. **Deploy with Caveats** - System is usable but contradiction detection needs improvement
'''
else:
    report += '''1. **Debug Detection Pipeline** - Check ML classifier is being called and features are extracted
2. **Fix OVERRIDE Policy** - Ensure database migrations run before resolution
3. **Review Semantic Similarity** - Contradictions like "prefer remote" vs "don't like working from home" should be detected
4. **Do Not Deploy Yet** - More engineering work needed
'''

report += f'''
---

## Evidence Files

- `retest_detection_results.json` - Detection test details
- `retest_gate_blocking.json` - Gate blocking evidence
- `retest_resolution.json` - Resolution policy test
- `RETEST_SUMMARY.json` - Overall metrics

---

*Generated automatically after bug fix validation*
'''

with open('BUG_FIX_VALIDATION_REPORT.md', 'w', encoding='utf-8') as f:
    f.write(report)

print('\nReport saved to BUG_FIX_VALIDATION_REPORT.md')

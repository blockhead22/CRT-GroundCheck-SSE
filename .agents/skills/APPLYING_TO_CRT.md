# Applying Continuous Learning to CRT Memory System

## Overview
The continuous learning skill can capture development patterns from your CRT (Contradiction-preserving memory), SSE (event framework), and GroundCheck (verification) work.

## 5 Practical Applications

### 1. **Stress Test Learning** ✅ IMPLEMENTED
**What it does:**
- Analyzes `crt_stress_run.*.jsonl` files automatically
- Extracts patterns about:
  - Contradiction frequency & types
  - Gate failure reasons
  - Trust score degradation patterns
  - GroundCheck eval failures

**How to use:**
```bash
# Run a stress test
python tools/crt_stress_test.py --use-api --turns 30

# Analyze the results
python tools/analyze_stress_test_session.py artifacts/crt_stress_run.TIMESTAMP.jsonl

# Review learned patterns
.\tools\review_learned_skills.ps1
```

**What you'll learn:**
- Common contradiction scenarios (e.g., "favorite_color: blue→red")
- Trust score recovery patterns
- GroundCheck failure signatures
- Gate configuration insights

---

### 2. **Debugging Session Capture** ✅ ENABLED
**What it does:**
- Captures manual debugging sessions in VS Code
- Detects CRT-specific error patterns
- Records effective resolution strategies

**How to use:**
```bash
# When you're done debugging, run:
.\.agents\skills\cc-skill-continuous-learning\evaluate-session.ps1

# The skill auto-detects patterns like:
# - Error resolution techniques
# - CRT-specific debugging workflows
# - Trust score tuning strategies
# - Fact extraction patterns
```

**What you'll learn:**
- Common CRT bugs and fixes
- Effective debugging sequences
- Test case patterns that reveal issues
- Memory operation edge cases

---

### 3. **Knowledge Base Maintenance** ✅ STRUCTURED
**What it does:**
- Builds `.agents/skills/crt-learned-patterns.md` over time
- Documents reusable CRT patterns
- Creates searchable development reference

**How to use:**
```bash
# After approving a learned session:
.\tools\review_learned_skills.ps1
# (Press 'y' on useful patterns)

# Patterns auto-append to crt-learned-patterns.md
```

**Example knowledge captured:**
```markdown
## Trust Score Tuning
Pattern: When contradiction count > 3, trust drops to 0.5
Fix: Implement exponential decay with floor at 0.3
Learned: 2026-01-26 from stress_test_20260126_012624
```

---

### 4. **Test Case Generation** 🔄 FUTURE
**What it does:**
- Learns from stress test failures
- Suggests new test cases for uncovered scenarios
- Identifies gaps in test coverage

**How to implement:**
```python
# tools/suggest_test_cases.py (to be created)
# Analyzes learned patterns and suggests:
# - Edge cases from stress tests
# - Regression tests from bugs
# - Combination scenarios
```

**Example output:**
```python
# Suggested test case from pattern analysis:
def test_rapid_contradictions_trust_floor():
    """Trust score should not drop below 0.3 even with 10+ contradictions"""
    # Pattern learned from stress_test_20260126_012624
    ...
```

---

### 5. **LLM-Enhanced Analysis** 🔄 ADVANCED
**What it does:**
- Uses Claude/GPT to analyze sessions semantically
- Goes beyond keyword matching
- Identifies subtle patterns

**How to implement:**
```python
# tools/llm_analyze_session.py (to be created)
# Sends session transcript to LLM with prompt:
# "Analyze this CRT debugging session and extract:
#  1. The root cause
#  2. The fix strategy
#  3. Reusable patterns
#  4. Test recommendations"
```

**Value:**
- Deeper pattern extraction than keyword matching
- Natural language summaries of complex debugging
- Automatic documentation generation

---

## Integration Points

### Automated Hooks (Configured):
1. **Post-stress-test hook**: Run `analyze_stress_test_session.py` automatically
2. **VS Code tasks**: Integrated learning into task runner
3. **Git pre-commit**: Could validate patterns before commit

### Manual Workflows:
1. After major debugging session → Run `evaluate-session.ps1`
2. Before sprint → Review `crt-learned-patterns.md`
3. Weekly review → Run `review_learned_skills.ps1` on pending patterns

---

## Current Detected Patterns (10 types)

### General (5):
- `error_resolution` - How you fix bugs
- `code_pattern` - Reusable code structures
- `debugging_technique` - Effective debug workflows
- `workaround` - Temporary solutions
- `project_specific` - CRT/SSE/GroundCheck idioms

### CRT-Specific (5):
- `crt_contradiction_handling` - Contradiction detection & disclosure
- `trust_score_tuning` - Trust metric calibration
- `groundcheck_verification` - GroundCheck eval patterns
- `fact_extraction_patterns` - Fact slot parsing
- `memory_operations` - CRT ledger/storage operations

---

## Example: Learning from Today's Work

**Session:** Repository cleanup + Learning system integration
**Detected patterns:**
1. **Error resolution**: Windows file lock handling with `os.chmod`
2. **Debugging technique**: PowerShell script syntax validation
3. **Project-specific**: CRT stress test analyzer integration
4. **Workaround**: Skip archive step due to timeout

**Knowledge captured:**
- Windows cleanup requires permission callbacks, not `ignore_errors`
- PowerShell quote escaping: use backticks for complex strings
- Session transcript detection: regex needs whitespace flexibility
- Stress test learning: extract trust score variance as signal

---

## Next Steps

### Immediate:
1. ✅ Test `analyze_stress_test_session.py` (just completed)
2. Run full 30-turn stress test to generate real patterns
3. Review learned sessions with `review_learned_skills.ps1`

### Short-term:
1. Create `suggest_test_cases.py` for test generation
2. Add pre-commit hook to validate learned patterns
3. Build semantic search over `crt-learned-patterns.md`

### Long-term:
1. Implement LLM-enhanced session analysis
2. Create "CRT debugging assistant" skill using learned patterns
3. Auto-generate documentation from pattern knowledge base

---

## Measuring Success

**Metrics to track:**
- Patterns learned per week
- Patterns approved vs rejected ratio
- Bug resolution time (before/after skill)
- Test coverage increase from learned patterns
- Stress test pass rate improvement

**Hypothesis:**
If learning skill is working, you'll see:
- Faster debugging (reference known patterns)
- Better test coverage (learned edge cases)
- Fewer regressions (documented fixes)
- Improved stress test scores (tuned parameters)

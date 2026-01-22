# Honest Assessment: What Works, What Doesn't, What We Don't Know

**Last updated:** 2026-01-22  
**Purpose:** Brutally honest evaluation of CRT + GroundCheck

---

## What Works

### Contradiction Detection
- **Result:** 60% accuracy on contradiction category (6/10 examples)
- **Baselines:** 30% (3/10 examples)
- **Improvement:** 2x on this specific capability
- **Evidence:** GroundingBench evaluation, 86 passing tests

### System Properties
- **Contradiction ledger:** 1000+ entries tracked without loss (stress test)
- **Verification speed:** <10ms per check
- **API costs:** Zero (deterministic logic)
- **Test coverage:** 86 tests (groundcheck), 97 tests (full CRT)
- **Invariant enforcement:** 0 violations in stress tests

### Architecture Soundness
- **Two-lane memory:** Clean separation of stable vs candidate facts
- **Contradiction tracking:** Durable ledger with queryable history
- **Trust evolution:** Facts age gracefully, confirmations boost trust
- **Policy engine:** Clear rules for contradiction handling

---

## What Doesn't Work Well

### Overall Accuracy
- **Result:** 70% on GroundingBench (35/50 examples)
- **Baselines:** SelfCheckGPT ~82% on similar benchmarks
- **Gap:** 12% lower on basic grounding tasks
- **Trade-off:** We prioritized speed + contradiction handling over raw accuracy

**Specific weaknesses:**
- Paraphrasing: 70% (vs 90% for LLM-based methods)
- Partial grounding: 40% (same as baselines - everyone struggles here)
- Contradiction detection: 60% (still misses 4/10 cases)

### Regex Limitations
- **Coverage:** Only 20+ predefined slot types
- **Examples:** employer, location, name, job_title, programming_language
- **Cannot extract:** Domain-specific facts, arbitrary fact types
- **Fails on:** Complex linguistic patterns, semantic paraphrases

**Specific failures:**
- "Software Engineer" matches "Senior Software Engineer" (substring issue)
- "employed by X since 2020" misses if pattern is "works at X"
- Cannot handle: "software engineer" vs "software developer" without explicit patterns

### Trust Threshold Tuning
- **Current:** Fixed thresholds (0.75 for trust, 0.3 for difference)
- **Problem:** Chosen empirically on development examples
- **Doesn't generalize to:**
  - Different domains (healthcare vs customer service)
  - Different trust scoring methods
  - User preferences (strict vs permissive)
- **Impact:** Threshold choice affects accuracy by 20% (50%-70% across values)

---

## What We Don't Know

### User Perception
**Questions we haven't answered:**
- Do users prefer disclosure ("Amazon, changed from Microsoft") or confidence ("Amazon")?
- Is transparency worth the verbosity?
- Will contradiction warnings feel helpful or annoying?
- At what frequency do disclosures become noise?

**Why it matters:** If users consistently prefer confident wrong answers, this approach doesn't help.

**Evidence needed:** User study with A/B testing

### Real-World Frequency
**Questions we haven't answered:**
- How common are contradictions in actual long-term AI usage?
- Are they frequent enough to justify this infrastructure?
- Do they cluster in specific domains or user types?
- What's the distribution of contradiction types?

**Why it matters:** If contradictions are rare (< 1% of interactions), the overhead isn't justified.

**Evidence needed:** Real-world deployment data

### Production Performance
**Questions we haven't answered:**
- What's the false positive rate at scale?
- What's the false negative rate at scale?
- Can SQLite handle > 100K users?
- Can regex patterns scale beyond English?
- How does performance degrade with memory growth?

**Why it matters:** Research prototypes often fail in production.

**Evidence needed:** Production deployment, stress testing at scale

### Regulatory Pressure
**Questions we haven't answered:**
- Will regulations require contradiction tracking?
- Is HIPAA/SOX/EU AI Act pressure building?
- Will market demand this capability?
- What compliance requirements actually need audit trails?

**Why it matters:** If no regulatory pressure emerges, adoption is unlikely.

**Evidence needed:** Legal analysis, industry trends

---

## What Would Need to Be True (For This to Matter)

### Assumption 1: Long-term AI Memory Becomes Widespread
**Current evidence:**
- ChatGPT Memory exists (limited rollout)
- Claude Projects exists
- GitHub Copilot Chat has context

**Uncertain:**
- Will mainstream users adopt long-term AI?
- Or will most usage stay one-shot?

**What validates:** Widespread adoption of stateful AI assistants

### Assumption 2: Users Prefer Transparency Over Confidence
**Current evidence:**
- None. We haven't tested this.

**Uncertain:**
- Maybe users hate "I have conflicting information"
- Maybe they want the AI to just pick the best answer
- Maybe disclosure is annoying, not helpful

**What validates:** User study showing preference for disclosure

### Assumption 3: Contradictions Are Common Enough to Matter
**Current evidence:**
- Our examples (job changes, location moves) are plausible
- But frequency is unknown

**Uncertain:**
- In 100 conversations, how many contradictions occur?
- Is it 1? 10? 50?
- Does it vary by domain?

**What validates:** Real-world usage data showing contradiction frequency > 5%

### Assumption 4: Regulatory Pressure Increases
**Current evidence:**
- HIPAA requires audit trails
- SOX requires financial tracking
- EU AI Act requires transparency

**Uncertain:**
- Will these apply to AI memory?
- Will enforcement be strict?
- Will market care without enforcement?

**What validates:** Regulations explicitly requiring contradiction tracking

---

## Risks This Doesn't Matter

### Risk 1: LLMs Get Good Enough
**Scenario:** GPT-6 / Claude 5 are so accurate that contradictions rarely occur

**Impact:** Problem becomes negligible

**Likelihood:** Moderate. LLMs are improving fast.

### Risk 2: Users Prefer Confident Wrong Answers
**Scenario:** User studies show people hate disclosure, want confidence

**Impact:** Market rejects transparency

**Likelihood:** Unknown. Needs testing.

### Risk 3: Better Solutions Appear
**Scenario:** Someone builds neural end-to-end system that handles contradictions better

**Impact:** Our approach becomes obsolete

**Likelihood:** Moderate. We're early but not alone.

### Risk 4: No Regulatory Pressure
**Scenario:** AI regulation stays minimal, market doesn't demand compliance

**Impact:** No forcing function for adoption

**Likelihood:** Moderate. Regulatory timelines are slow.

### Risk 5: Speed Matters More Than Transparency
**Scenario:** Users prefer instant wrong answers to slow correct ones

**Impact:** <10ms overhead still too much

**Likelihood:** Low. <10ms is fast.

---

## What Would Validate This Approach

### Short-term validation (3-6 months):
- [ ] User study showing preference for disclosure (p < 0.05)
- [ ] Real-world deployment showing contradiction frequency > 5%
- [ ] Production performance: FPR < 10%, FNR < 15%
- [ ] Adoption by 1+ open source AI project

### Medium-term validation (6-12 months):
- [ ] Paper acceptance at top venue (EMNLP, ACL, NeurIPS)
- [ ] 3+ other papers citing GroundingBench
- [ ] 1000+ pip installs of groundcheck
- [ ] Integration with commercial AI system (ChatGPT, Claude, Copilot)

### Long-term validation (12-24 months):
- [ ] Regulatory requirement explicitly mentioning contradiction tracking
- [ ] 10+ production systems using GroundCheck
- [ ] Evidence that disclosure improves user trust (longitudinal study)
- [ ] Contradiction handling becomes standard AI safety practice

---

## What Would Invalidate This Approach

### Immediate invalidation:
- User study shows users hate disclosure (p < 0.05)
- Real-world data shows contradiction frequency < 1%
- Production deployment shows FPR > 50% or FNR > 50%

### Medium-term invalidation:
- Better solutions appear that are neural, end-to-end, and more accurate
- No regulatory pressure emerges after 12 months
- Zero commercial interest after 6 months

### Long-term invalidation:
- LLM accuracy improves such that contradictions become rare (< 0.1%)
- Market converges on "ignore contradictions" as acceptable practice
- No evidence that disclosure improves trust after 24 months

---

## Current Honest Status

**What we can claim:**
- ✅ Contradiction detection works (60% vs 30% baselines)
- ✅ System is fast (<10ms) and cheap (zero API cost)
- ✅ Architecture is sound (0 invariant violations)
- ✅ Code is tested (86 tests, 90% coverage)

**What we cannot claim:**
- ❌ Users prefer this approach
- ❌ Contradictions are common enough to matter
- ❌ This will be adopted
- ❌ This is production-ready
- ❌ This beats state-of-art on all metrics

**What we're doing:**
- Publishing research (paper, dataset, library)
- Enabling others to evaluate
- Hoping for validation
- Prepared to accept invalidation

---

## The Honest Bottom Line

**This is a bet on a problem we think is real but haven't proven matters at scale.**

**We have:**
- A working prototype
- Novel technical contribution
- Plausible use cases
- Decent accuracy on specific capability

**We don't have:**
- User validation
- Production evidence
- Market traction
- Regulatory pressure

**We're publishing to find out if the bet is correct.**

**That's honest research.**

---

**Next steps:**
- Publish paper + dataset (enable evaluation)
- Seek production partners (get real data)
- Run user studies (validate preferences)
- Monitor regulatory trends (watch for forcing functions)
- Be prepared to pivot if invalidated

**We'll know in 12 months if this matters.**

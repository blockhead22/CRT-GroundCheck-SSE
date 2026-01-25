# START HERE: Quick Reference Guide
**If You Get Lost, Read This**

**Created:** January 22, 2026  
**Purpose:** Quick navigation for the 12-week breakthrough research plan

---

## 🎯 The Big Picture (30 seconds)

**Goal:** Transform your system from incremental → breakthrough in 12 weeks  
**How:** Build BeliefRevisionBench dataset + classifier + policy learner  
**Target:** ICLR 2027 submission (October 2026)  
**Success:** 60% probability of breakthrough contribution

---

## 📋 The 6 Phases (High-Level)

```
Phase 1: Data Collection          (Weeks 1-2)  → Dataset ready
Phase 2: Classifier Training      (Weeks 3-4)  → 85%+ accuracy
Phase 3: Policy Learning          (Weeks 5-6)  → Human-level agreement
Phase 4: Baseline Comparisons     (Weeks 7-8)  → +23% improvement
Phase 5: Paper Writing            (Weeks 9-10) → 8-page draft
Phase 6: Review & Submission      (Weeks 11-12) → ICLR submitted
```

**Current phase:** Phase 1 (just starting)

---

## 🚀 What To Do Next (Right Now)

### Week 1, Day 1: Extract Real Data

**Step 1: Query your database (30 minutes)**
```python
# Run this to extract belief changes from Phase 1 logs
import sqlite3

conn = sqlite3.connect('personal_agent/active_learning.db')
cursor = conn.cursor()

# Find interactions where slots changed
query = """
SELECT 
    id,
    query,
    slots_inferred,
    response,
    timestamp
FROM interaction_logs
WHERE slots_inferred IS NOT NULL
ORDER BY timestamp
"""

results = cursor.fetchall()
print(f"Found {len(results)} interactions with slot data")
```

**Expected output:** 200-500 interactions  
**If less than 100:** That's okay, we'll supplement with synthetic data

**Step 2: Identify belief changes (1 hour)**
```python
# Look for contradictions in your ledger
conn_ledger = sqlite3.connect('personal_agent/crt_ledger.db')
cursor_ledger = conn_ledger.cursor()

query = """
SELECT 
    ledger_id,
    timestamp,
    contradiction_type,
    memory_id_a,
    memory_id_b
FROM contradiction_ledger
WHERE status = 'open' OR status = 'resolved'
"""

contradictions = cursor_ledger.fetchall()
print(f"Found {len(contradictions)} contradictions tracked")
```

**Expected output:** 50-200 contradictions  
**What this tells you:** How many real examples you have to work with

**Step 3: Manual labeling (2 hours)**
```python
# Label your first 50 examples
# Categories: REFINEMENT, REVISION, TEMPORAL, CONFLICT

example_1 = {
    'old_value': 'I work at Microsoft',
    'new_value': 'I work at Amazon',
    'category': 'REVISION',  # ← Job change
    'action': 'OVERRIDE'     # ← Should replace old with new
}

example_2 = {
    'old_value': 'I like Python',
    'new_value': 'I like Python and JavaScript',
    'category': 'REFINEMENT',  # ← Adding detail
    'action': 'PRESERVE'       # ← Keep both
}

# Label 50 examples and save as JSON
```

**Deliverable:** `belief_updates_labeled_50.json`  
**Time check:** If this takes > 3 hours, you're going too slow. Speed up.

---

## ⚠️ Common Places People Get Lost

### "I don't know which file to edit"
→ **Answer:** Don't edit code yet. You're in data collection phase.  
→ **Action:** Create new directory: `belief_revision/data/`  
→ **File structure:**
```
belief_revision/
  ├── data/
  │   ├── raw_interactions.json        ← Step 1 output
  │   ├── labeled_50.json              ← Step 3 output
  │   └── README.md                    ← Notes
  ├── scripts/
  │   ├── extract_data.py              ← Week 1 script
  │   └── label_synthetic.py           ← Week 1 script
  └── models/
      └── (empty for now)
```

### "I'm stuck on synthetic data generation"
→ **Answer:** Use this GPT-4 prompt template:
```
Generate 10 realistic belief updates for a personal AI assistant.

Format:
{
  "old_value": "I work at [company]",
  "new_value": "I work at [different company]",
  "context": "User mentioned job change after 2 months",
  "category": "REVISION",
  "time_delta_days": 60
}

Categories:
- REFINEMENT: Adding detail (e.g., "I like X" → "I like X and Y")
- REVISION: Changing value (e.g., job change, location move)
- TEMPORAL: Time-based update (e.g., age, current project)
- CONFLICT: Contradictory without clear intent

Vary the slots: employer, location, preference, skill, age, etc.
Make them realistic for a 30-year-old software engineer.
```

**Run this 60 times** → 600 synthetic examples  
**Cost:** $5-10 using GPT-4 API

### "How do I know if I'm on track?"
→ **Check these milestones:**

**End of Week 1:**
- [ ] 200+ real interactions extracted
- [ ] 50+ hand-labeled examples
- [ ] 300+ synthetic examples generated
- **If NO:** Spend weekend catching up

**End of Week 2:**
- [ ] 800 total examples (200 real + 600 synthetic)
- [ ] MTurk annotations collected (3 per example)
- [ ] Dataset formatted as JSONL
- [ ] Uploaded to HuggingFace
- **If NO:** You're behind. Skip synthetic, just use real data.

**End of Week 4:**
- [ ] Classifier trained (80%+ accuracy minimum)
- [ ] Feature importance analyzed
- **If NO:** Simplify model. Use Logistic Regression, not BERT.

**End of Week 6:**
- [ ] Policy learner working
- [ ] Integrated into CRT system
- **If NO:** Skip A/B test. Just show it works offline.

**End of Week 8:**
- [ ] 3 baselines implemented
- [ ] Results show +15% improvement (minimum)
- **If NO:** This is your last checkpoint. Decide: workshop paper or keep pushing.

**End of Week 10:**
- [ ] 8-page draft complete
- [ ] All figures/tables done
- **If NO:** Cut scope. Submit 6-page workshop paper instead.

**End of Week 12:**
- [ ] Paper submitted to arXiv
- [ ] Submitted to ICLR or NeurIPS workshop
- **If NO:** You missed deadline. Submit next cycle.

---

## 🔄 Decision Tree (When Stuck)

```
Are you in Week 1-2?
├─ YES: Focus on data collection only
│   └─ Deliverable: 800 labeled examples
│
└─ NO: Are you in Week 3-4?
    ├─ YES: Focus on classifier training
    │   └─ Deliverable: 80%+ accuracy model
    │
    └─ NO: Are you in Week 5-6?
        ├─ YES: Focus on policy learning
        │   └─ Deliverable: Override/preserve predictor
        │
        └─ NO: Are you in Week 7-8?
            ├─ YES: Focus on baselines
            │   └─ Deliverable: +15% improvement
            │
            └─ NO: Are you in Week 9-10?
                ├─ YES: Focus on writing
                │   └─ Deliverable: 8-page draft
                │
                └─ NO: You're in Week 11-12
                    └─ Focus on submission
                        └─ Deliverable: Submitted paper
```

---

## 📚 Which Document To Read When

**Feeling lost about big picture?**  
→ Read: `EXECUTIVE_SUMMARY.md` (5 minutes)

**Need detailed plan for current week?**  
→ Read: `STRATEGIC_ROADMAP_TO_BREAKTHROUGH.md` (find your week)

**Doubting if this will work?**  
→ Read: `NARRATIVE_ASSESSMENT.md` (reality check)

**Want to understand the science?**  
→ Read: `PATH_TO_BREAKTHROUGH.md` (Path 3C section)

**Need overall project context?**  
→ Read: `PROJECT_ASSESSMENT_JAN_22_2026.md` (30 min deep dive)

**You're lost and need to reset?**  
→ **You're reading it right now** (this file)

---

## 🎬 The Simplest Possible Start (Next 24 Hours)

**Hour 1-2: Extract data**
```bash
cd /home/runner/work/AI_round2/AI_round2
mkdir -p belief_revision/data
python -c "
import sqlite3
conn = sqlite3.connect('personal_agent/active_learning.db')
df = pd.read_sql('SELECT * FROM interaction_logs', conn)
df.to_json('belief_revision/data/raw_interactions.json')
print(f'Extracted {len(df)} interactions')
"
```

**Hour 3-4: Label 10 examples by hand**
```bash
cd belief_revision/data
# Create labeled_examples.json
# Just do 10 to get the feel for it
```

**Hour 5-6: Generate 50 synthetic examples**
```bash
# Use ChatGPT/Claude/GPT-4
# Copy-paste the prompt from "I'm stuck on synthetic data" above
# Run it 5 times → 50 examples
```

**End of day check:**
- [ ] `belief_revision/` directory exists
- [ ] At least 10 labeled examples
- [ ] At least 50 synthetic examples
- [ ] You understand the 4 categories

**If YES:** You're on track. Continue tomorrow.  
**If NO:** You're overthinking. Just make the files. They don't need to be perfect.

---

## 🚨 Emergency Shortcuts (If Falling Behind)

### Week 2 - Can't get 800 examples?
→ **Use 400 instead.** Still publishable.

### Week 4 - Classifier stuck at 70%?
→ **Ship it.** 70% beats baselines. Write about challenges.

### Week 6 - Policy learner not working?
→ **Skip it.** Just publish classifier. Still novel.

### Week 8 - Baselines taking too long?
→ **Use 2 instead of 3.** No memory + NLI only.

### Week 10 - Can't finish 8 pages?
→ **Submit 6-page workshop paper.** Still counts.

### Week 12 - Missed ICLR deadline?
→ **Submit to NeurIPS workshop (June deadline) or EMNLP (May).**

---

## ✅ Daily Checklist (Copy This Each Morning)

**Today's date:** _____________  
**Current week:** Week ___  
**Current phase:** Phase ___

**My single most important task today:**
_______________________________________

**What I will deliver by end of day:**
_______________________________________

**If I get stuck, I will:**
1. Re-read this file
2. Check STRATEGIC_ROADMAP (my current week section)
3. Ask specific question (not "help me", but "how do I X?")

**End of day:**
- [ ] Did I deliver what I planned?
- [ ] Am I still on track for this week's milestone?
- [ ] Do I know what I'm doing tomorrow?

---

## 🎯 The One Thing To Remember

**You're not trying to build perfect AI.**  
**You're trying to publish a paper in 12 weeks.**

**Perfect is the enemy of done.**  
**Ship the dataset. Ship the classifier. Ship the paper.**

**Everything else is optional.**

---

## 📞 Quick Reference Numbers

- **Total weeks:** 12
- **Total phases:** 6
- **Current phase:** 1
- **Budget:** $500
- **Hours per week:** 40
- **Success probability:** 60%
- **Minimum success (workshop):** 80% likely
- **Target success (main conference):** 60% likely

---

## 🔗 Quick Links to Key Files

1. `STRATEGIC_ROADMAP_TO_BREAKTHROUGH.md` - Full 12-week plan
2. `PATH_TO_BREAKTHROUGH.md` - Why this works
3. `NARRATIVE_ASSESSMENT.md` - Reality check
4. `EXECUTIVE_SUMMARY.md` - 5-minute overview
5. **THIS FILE** - When you're lost

---

## 💡 The Motto

**"Week 1: Extract data. Week 2: Label data. Week 3: Train model. Week 4: Beat baseline. Repeat."**

**Stay focused. Ship weekly. You got this.**

---

**Last updated:** January 22, 2026  
**Current week:** Week 1, Day 1  
**Next milestone:** 200 real examples extracted (end of Week 1)  
**What to do right now:** Run the database query in Step 1 above

**When in doubt, do the next smallest thing on the list.**

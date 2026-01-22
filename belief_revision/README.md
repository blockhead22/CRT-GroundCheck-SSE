# Belief Revision Bench - Phase 1 Setup

**Goal:** Create BeliefRevisionBench dataset (800 labeled examples)  
**Timeline:** Week 1-2  
**Current Status:** Phase 1, Day 1

---

## Quick Start

### Step 1: Extract Real Data (30 minutes)

```bash
cd /home/runner/work/AI_round2/AI_round2
python belief_revision/scripts/phase1_extract_data.py
```

**Output:**
- `data/raw_interactions.json` - All interactions with slot data
- `data/raw_contradictions.json` - Tracked contradictions
- `data/potential_belief_updates.json` - Identified belief changes
- `data/extraction_report.md` - Summary report

**What to check:**
- How many belief updates were found?
- Do they look like real examples?

### Step 2: Generate Synthetic Data (1 hour)

```bash
python belief_revision/scripts/phase1_generate_synthetic.py
```

**Output:**
- `data/synthetic_belief_updates.json` - 600 template-generated examples

**Note:** This file is generated and not tracked in git. If missing, run the script above to regenerate it.

**What to check:**
- Are the 4 categories balanced? (150 each)
- Do examples look realistic?

### Step 3: Manual Labeling (2-3 hours)

Open `data/potential_belief_updates.json` and label first 50:

```json
{
  "id": "real_001",
  "old_value": "I work at Microsoft",
  "new_value": "I work at Amazon",
  "category": "REVISION",  // ← Add this
  "recommended_action": "OVERRIDE",  // ← Add this
  "slot": "employer",
  "time_delta_days": 45
}
```

**Categories:**
- `REFINEMENT` - Adding detail (preserve both)
- `REVISION` - Changing value (override old)
- `TEMPORAL` - Time-based update (override old)
- `CONFLICT` - Unclear intent (ask user)

**Actions:**
- `PRESERVE` - Keep both in memory
- `OVERRIDE` - Replace old with new
- `ASK_USER` - Request clarification

Save as: `data/labeled_examples_manual.json`

---

## Directory Structure

```
belief_revision/
├── README.md                           ← You are here
├── data/
│   ├── raw_interactions.json           ← From active_learning.db
│   ├── raw_contradictions.json         ← From crt_ledger.db
│   ├── potential_belief_updates.json   ← Analyzed updates
│   ├── synthetic_belief_updates.json   ← Template generated
│   ├── labeled_examples_manual.json    ← Your labels (50)
│   ├── extraction_report.md            ← Summary
│   └── (Week 2 will add more files)
├── scripts/
│   ├── phase1_extract_data.py          ← Step 1
│   ├── phase1_generate_synthetic.py    ← Step 2
│   └── (More scripts in Week 2-4)
└── models/
    └── (Empty until Week 3)
```

---

## Phase 1 Checklist

### Week 1: Data Collection
- [x] Day 1: Run extraction script
- [ ] Day 1: Review extraction report
- [ ] Day 1: Run synthetic generation
- [ ] Day 2: Label 50 real examples manually
- [ ] Day 3-4: Refine labeling guidelines
- [ ] Day 5-7: Prepare for MTurk (Week 2)

### Week 2: Annotation
- [ ] Day 1: Set up Amazon MTurk
- [ ] Day 2-4: Collect annotations (3 per example)
- [ ] Day 5: Calculate inter-annotator agreement
- [ ] Day 6: Resolve disagreements
- [ ] Day 7: Upload BeliefRevisionBench to HuggingFace

---

## Expected Results

### End of Day 1
- ✓ Extracted N real belief updates (N = unknown, maybe 50-200)
- ✓ Generated 600 synthetic examples
- ✓ Ready to start manual labeling

### End of Week 1
- ✓ 200+ real examples extracted and labeled
- ✓ 600 synthetic examples generated
- ✓ Total: 800+ examples ready for annotation

### End of Week 2
- ✓ 800 examples with 3 annotations each
- ✓ Inter-annotator agreement: κ > 0.7
- ✓ BeliefRevisionBench v1.0 published on HuggingFace

---

## Troubleshooting

### "Not enough real examples extracted"
**Solution:** That's okay! Use more synthetic data. You can have 100 real + 700 synthetic.

### "Manual labeling is too slow"
**Solution:** Only label 20 examples to get the feel. Use those as examples for MTurk annotators.

### "Synthetic data looks too simple"
**Solution:** Good enough for v1.0. You can improve with GPT-4 later if needed.

### "I don't understand the categories"
**Solution:** Read START_HERE.md section on categories. When in doubt:
- If adding detail → REFINEMENT
- If changing value → REVISION  
- If time passed → TEMPORAL
- If contradictory → CONFLICT

---

## Next Phase

After Phase 1 (Week 2 complete), move to Phase 2:
- **Phase 2:** Classifier Training (Week 3-4)
- See: `STRATEGIC_ROADMAP_TO_BREAKTHROUGH.md`

---

**Questions?** Read START_HERE.md or STRATEGIC_ROADMAP_TO_BREAKTHROUGH.md

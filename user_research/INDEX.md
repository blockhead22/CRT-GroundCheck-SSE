# User Research Documentation Index

## 📋 Quick Navigation

**New to this project?** Start here: [`KICKOFF_SUMMARY.md`](KICKOFF_SUMMARY.md)

**Ready to begin?** Run: `python kickoff_user_research.py`

**Need specific info?** Use the navigation below ⬇️

---

## 📁 Documentation Structure

### 🎯 Getting Started
- **[KICKOFF_SUMMARY.md](KICKOFF_SUMMARY.md)** - Executive summary and quick start guide
- **[README.md](README.md)** - Main documentation and project overview
- **[kickoff_user_research.py](kickoff_user_research.py)** - Automated setup script

### 🧪 Experiment Design
📂 **benchmarking/**
- **[experiment_protocol.md](benchmarking/experiment_protocol.md)** - Rigorous experiment design and methodology
- **[groundingbench_tasks.md](benchmarking/groundingbench_tasks.md)** - Specific GroundingBench tasks for participants

**Use when:** Designing user benchmarking experiments

### 🐛 Error Collection
📂 **error_collection/**
- **[collection_framework.md](error_collection/collection_framework.md)** - Systematic error collection methodology
- **[error_templates.md](error_collection/error_templates.md)** - Standardized error reporting templates

**Use when:** Collecting and documenting errors

### 💬 User Interviews
📂 **interviews/**
- **[interview_guide.md](interviews/interview_guide.md)** - Comprehensive 45-60 min interview script
- **[participant_consent.md](interviews/participant_consent.md)** - Consent form template

**Use when:** Conducting user interviews

### 📊 Analysis
📂 **analysis/**
- **[error_classification.md](analysis/error_classification.md)** - Error classification taxonomy and framework
- **[analysis_protocol.md](analysis/analysis_protocol.md)** - Pre/post-upgrade statistical analysis methodology

**Use when:** Analyzing collected data

### 📝 Findings & Recommendations
📂 **findings/**
- **[findings_template.md](findings/findings_template.md)** - Template for documenting research findings
- **[recommendations.md](findings/recommendations.md)** - Template for future model tuning recommendations

**Use when:** Writing final reports

### 💾 Data Collection
📂 **data/**
- **[participant_tracking.json](data/participant_tracking.json)** - Track recruited participants
- **[experiment_checklist.md](data/experiment_checklist.md)** - Step-by-step task checklist
- **[benchmarking/results_template.json](data/benchmarking/results_template.json)** - Benchmarking data collection
- **[interviews/interview_template.md](data/interviews/interview_template.md)** - Interview notes template
- **[errors/error_log.jsonl](data/errors/error_log.jsonl)** - Error logging format

**Use when:** Collecting and storing data during research

---

## 🚀 Quick Start Workflows

### Workflow 1: First-Time Setup
```bash
# 1. Review executive summary
cat user_research/KICKOFF_SUMMARY.md

# 2. Read main README
cat user_research/README.md

# 3. Run kickoff script
cd user_research
python kickoff_user_research.py

# 4. Review generated checklist
cat data/experiment_checklist.md
```

### Workflow 2: Conducting Experiments
```bash
# 1. Review experiment protocol
cat user_research/benchmarking/experiment_protocol.md

# 2. Review GroundingBench tasks
cat user_research/benchmarking/groundingbench_tasks.md

# 3. Use results template for data collection
# Edit: user_research/data/benchmarking/results_template.json
```

### Workflow 3: Conducting Interviews
```bash
# 1. Review interview guide
cat user_research/interviews/interview_guide.md

# 2. Prepare consent form
cat user_research/interviews/participant_consent.md

# 3. Use interview template for notes
# Edit: user_research/data/interviews/interview_template.md
```

### Workflow 4: Analyzing Results
```bash
# 1. Review error classification framework
cat user_research/analysis/error_classification.md

# 2. Follow analysis protocol
cat user_research/analysis/analysis_protocol.md

# 3. Document findings
# Edit: user_research/findings/findings_template.md
```

---

## 📚 Document Dependencies

```
KICKOFF_SUMMARY.md ────┬──> README.md
                       │
                       ├──> benchmarking/experiment_protocol.md ──> groundingbench_tasks.md
                       │
                       ├──> error_collection/collection_framework.md ──> error_templates.md
                       │
                       ├──> interviews/interview_guide.md ──> participant_consent.md
                       │
                       ├──> analysis/error_classification.md ──> analysis_protocol.md
                       │
                       └──> findings/findings_template.md ──> recommendations.md

kickoff_user_research.py ──> data/* (generates all data templates)
```

---

## 🎓 Learning Path

### Beginner (Just starting)
1. Start: [KICKOFF_SUMMARY.md](KICKOFF_SUMMARY.md)
2. Then: [README.md](README.md)
3. Run: `python kickoff_user_research.py`
4. Review: [data/experiment_checklist.md](data/experiment_checklist.md)

### Intermediate (Ready to execute)
1. Design experiments: [benchmarking/experiment_protocol.md](benchmarking/experiment_protocol.md)
2. Prepare interviews: [interviews/interview_guide.md](interviews/interview_guide.md)
3. Set up error collection: [error_collection/collection_framework.md](error_collection/collection_framework.md)

### Advanced (Data analysis)
1. Classify errors: [analysis/error_classification.md](analysis/error_classification.md)
2. Run statistical analysis: [analysis/analysis_protocol.md](analysis/analysis_protocol.md)
3. Document findings: [findings/findings_template.md](findings/findings_template.md)
4. Write recommendations: [findings/recommendations.md](findings/recommendations.md)

---

## 🔍 Find Information By Topic

### Accuracy & Metrics
- Experiment design → [benchmarking/experiment_protocol.md](benchmarking/experiment_protocol.md)
- Statistical tests → [analysis/analysis_protocol.md](analysis/analysis_protocol.md)
- Success criteria → [KICKOFF_SUMMARY.md](KICKOFF_SUMMARY.md)

### Participants
- Recruitment → [benchmarking/experiment_protocol.md](benchmarking/experiment_protocol.md#participant-selection)
- Consent → [interviews/participant_consent.md](interviews/participant_consent.md)
- Tracking → [data/participant_tracking.json](data/participant_tracking.json)

### Data Collection
- Benchmarking → [data/benchmarking/results_template.json](data/benchmarking/results_template.json)
- Interviews → [data/interviews/interview_template.md](data/interviews/interview_template.md)
- Errors → [data/errors/error_log.jsonl](data/errors/error_log.jsonl)

### Paraphrasing Specifics
- Test cases → [benchmarking/groundingbench_tasks.md](benchmarking/groundingbench_tasks.md)
- Error types → [analysis/error_classification.md](analysis/error_classification.md)
- Model tuning → [findings/recommendations.md](findings/recommendations.md)

### Business Value
- ROI calculation → [analysis/analysis_protocol.md](analysis/analysis_protocol.md#business-value-assessment)
- User value → [interviews/interview_guide.md](interviews/interview_guide.md#q12-willingness-to-pay)
- Recommendations → [findings/recommendations.md](findings/recommendations.md)

---

## 📋 Checklists

### Pre-Research Checklist
- [ ] Read [KICKOFF_SUMMARY.md](KICKOFF_SUMMARY.md)
- [ ] Run [kickoff_user_research.py](kickoff_user_research.py)
- [ ] Review [experiment_protocol.md](benchmarking/experiment_protocol.md)
- [ ] Prepare [consent forms](interviews/participant_consent.md)
- [ ] Set up recording equipment
- [ ] Recruit participants

### During Research Checklist
- [ ] Follow [experiment_checklist.md](data/experiment_checklist.md)
- [ ] Use [results_template.json](data/benchmarking/results_template.json)
- [ ] Follow [interview_guide.md](interviews/interview_guide.md)
- [ ] Use [interview_template.md](data/interviews/interview_template.md)
- [ ] Log errors in [error_log.jsonl](data/errors/error_log.jsonl)

### Post-Research Checklist
- [ ] Classify errors using [error_classification.md](analysis/error_classification.md)
- [ ] Run analysis per [analysis_protocol.md](analysis/analysis_protocol.md)
- [ ] Complete [findings_template.md](findings/findings_template.md)
- [ ] Write [recommendations.md](findings/recommendations.md)
- [ ] Present to stakeholders

---

## 🆘 Common Questions

**Q: Where do I start?**  
A: Read [KICKOFF_SUMMARY.md](KICKOFF_SUMMARY.md), then run `python kickoff_user_research.py`

**Q: How do I recruit participants?**  
A: See [experiment_protocol.md § Participant Selection](benchmarking/experiment_protocol.md#participant-selection)

**Q: What questions should I ask in interviews?**  
A: Use the complete script in [interview_guide.md](interviews/interview_guide.md)

**Q: How do I classify errors?**  
A: Follow the taxonomy in [error_classification.md](analysis/error_classification.md)

**Q: What statistical tests should I run?**  
A: See [analysis_protocol.md § Statistical Comparison](analysis/analysis_protocol.md#statistical-comparison)

**Q: How do I calculate business value?**  
A: Use the framework in [analysis_protocol.md § Business Value](analysis/analysis_protocol.md#business-value-assessment)

**Q: What should the final report include?**  
A: Follow [findings_template.md](findings/findings_template.md)

---

## 📞 Support

**Technical Issues:** Check [PR #18](https://github.com/blockhead22/AI_round2/pull/18) and [GROUNDCHECK_IMPROVEMENTS.md](../GROUNDCHECK_IMPROVEMENTS.md)

**Research Questions:** Review relevant documentation in this folder

**General Questions:** Create an issue in the repository

---

## 🔄 Document Versions

| Document | Version | Last Updated | Status |
|----------|---------|--------------|--------|
| INDEX.md | 1.0 | 2026-01-22 | Current |
| KICKOFF_SUMMARY.md | 1.0 | 2026-01-22 | Current |
| README.md | 1.0 | 2026-01-22 | Current |
| experiment_protocol.md | 1.0 | 2026-01-22 | Current |
| interview_guide.md | 1.0 | 2026-01-22 | Current |
| All others | 1.0 | 2026-01-22 | Current |

---

## ✨ Key Success Factors

To successfully complete this research:

1. ✅ **Follow the protocol** - Use provided templates and frameworks
2. ✅ **Track everything** - Use tracking files and checklists
3. ✅ **Stay organized** - Keep data in specified directories
4. ✅ **Be thorough** - Complete all checklist items
5. ✅ **Communicate** - Update stakeholders regularly

---

**Ready to begin?** → [KICKOFF_SUMMARY.md](KICKOFF_SUMMARY.md)

**Questions?** → Create an issue or contact the research lead

**Happy researching! 🎉**

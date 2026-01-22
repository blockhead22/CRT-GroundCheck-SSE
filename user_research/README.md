# User Research: Paraphrasing Upgrade Validation

## Overview

This directory contains the framework for conducting user research to validate the real-world impact of improved paraphrasing accuracy (85-90%) delivered by the hybrid neural + semantic matcher upgrade in GroundCheck (PR #18).

## Objective

Begin user research to validate the real-world impact of improved paraphrasing accuracy (85-90%) delivered by the hybrid neural + semantic matcher upgrade in GroundCheck.

## Success Metrics

- Clear, quantified user feedback on value of paraphrasing improvements
- Recommendations for future model & matcher tuning

## Directory Structure

```
user_research/
├── README.md                          # This file
├── benchmarking/                      # User benchmarking experiments
│   ├── experiment_protocol.md         # Experiment design & protocol
│   └── groundingbench_tasks.md        # Specific GroundingBench tasks
├── error_collection/                  # Sample error collection
│   ├── collection_framework.md        # Framework for collecting errors
│   └── error_templates.md             # Templates for documenting errors
├── interviews/                        # User interview materials
│   ├── interview_guide.md             # Interview questions & guide
│   └── participant_consent.md         # Consent form template
├── analysis/                          # Pre/post-upgrade analysis
│   ├── error_classification.md        # Error classification framework
│   └── analysis_protocol.md           # Analysis methodology
└── findings/                          # Research findings & recommendations
    ├── findings_template.md           # Template for documenting findings
    └── recommendations.md             # Next iteration recommendations
```

## Getting Started

1. Review the [experiment protocol](benchmarking/experiment_protocol.md)
2. Set up GroundingBench tasks from [groundingbench_tasks.md](benchmarking/groundingbench_tasks.md)
3. Use the [error collection framework](error_collection/collection_framework.md) to gather sample errors
4. Conduct interviews using the [interview guide](interviews/interview_guide.md)
5. Analyze results using the [error classification](analysis/error_classification.md) framework
6. Document findings in [findings_template.md](findings/findings_template.md)

## Related Documentation

- [GROUNDCHECK_IMPROVEMENTS.md](../GROUNDCHECK_IMPROVEMENTS.md) - Technical details of PR #18
- [GroundingBench Data](../groundingbench/data/) - Benchmark datasets
- [Experiment Scripts](../experiments/) - Evaluation scripts

## Timeline

**Phase 1: Setup (Week 1)**
- Finalize experiment design
- Recruit participants
- Prepare GroundingBench tasks

**Phase 2: Data Collection (Weeks 2-3)**
- Conduct benchmarking experiments
- Collect error samples
- Perform user interviews

**Phase 3: Analysis (Week 4)**
- Classify errors pre/post-upgrade
- Analyze interview transcripts
- Synthesize findings

**Phase 4: Reporting (Week 5)**
- Document quantified user feedback
- Create recommendations for future tuning
- Present findings to stakeholders

## Contact

For questions or feedback, please create an issue in the repository.

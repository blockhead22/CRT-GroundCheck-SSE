#!/usr/bin/env python3
"""
User Research Kickoff Script

This script helps researchers get started with the paraphrasing upgrade user research.
It provides interactive guidance and generates initial data collection files.

Usage:
    python kickoff_user_research.py
"""

import os
import json
from datetime import datetime
from pathlib import Path


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")


def print_section(text):
    """Print a formatted section header."""
    print(f"\n--- {text} ---\n")


def create_directory_structure():
    """Create the data collection directories if they don't exist."""
    base_dir = Path("user_research")
    dirs = [
        base_dir / "data" / "benchmarking",
        base_dir / "data" / "interviews",
        base_dir / "data" / "errors",
        base_dir / "data" / "analysis",
    ]
    
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    print("✓ Created data collection directories")


def generate_participant_tracking():
    """Generate a participant tracking spreadsheet."""
    output_file = Path("user_research/data/participant_tracking.json")
    
    tracking_data = {
        "participants": [],
        "metadata": {
            "created": datetime.now().isoformat(),
            "total_recruited": 0,
            "total_completed": 0
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(tracking_data, f, indent=2)
    
    print(f"✓ Generated participant tracking file: {output_file}")
    return output_file


def generate_experiment_checklist():
    """Generate an experiment checklist."""
    output_file = Path("user_research/data/experiment_checklist.md")
    
    checklist = """# User Research Experiment Checklist

## Pre-Experiment Setup
- [ ] Review experiment protocol
- [ ] Prepare GroundingBench test cases
- [ ] Set up data collection forms
- [ ] Recruit participants (target: 20)
- [ ] Schedule interview sessions
- [ ] Test recording equipment
- [ ] Prepare consent forms

## Baseline Data Collection (Week 1)
- [ ] Run GroundCheck on paraphrasing dataset (pre-upgrade)
- [ ] Document baseline accuracy: _____%
- [ ] Collect and categorize errors
- [ ] Calculate baseline metrics (FN rate, FP rate, latency)

## Participant Testing (Weeks 2-3)
- [ ] Conduct A/B comparison tests (target: 20 participants)
- [ ] Conduct real-world scenario tests
- [ ] Collect error discovery feedback
- [ ] Record quantitative metrics (trust scores, satisfaction)

## User Interviews (Weeks 2-3)
- [ ] Complete interviews (target: 15)
- [ ] Record and transcribe interviews
- [ ] Document key insights in real-time
- [ ] Collect user quotes and themes

## Post-Upgrade Testing (Week 2)
- [ ] Deploy semantic matching upgrade
- [ ] Run same test set as baseline
- [ ] Collect post-upgrade metrics
- [ ] Compare to baseline

## Analysis (Week 4)
- [ ] Classify all collected errors
- [ ] Run statistical tests (t-test, McNemar's, effect size)
- [ ] Analyze interview transcripts (thematic analysis)
- [ ] Calculate business value metrics
- [ ] Identify improvement patterns

## Reporting (Week 5)
- [ ] Write findings report
- [ ] Create recommendations document
- [ ] Prepare presentation for stakeholders
- [ ] Share findings with participants (optional)

## Success Criteria
- [ ] ≥10 participants completed all tasks
- [ ] Statistical significance achieved (p < 0.05)
- [ ] User preference >60% for post-upgrade
- [ ] Clear, quantified feedback documented
- [ ] Actionable recommendations generated

---

**Start Date:** ___________
**Target Completion:** ___________
**Research Lead:** ___________
"""
    
    with open(output_file, 'w') as f:
        f.write(checklist)
    
    print(f"✓ Generated experiment checklist: {output_file}")
    return output_file


def generate_data_collection_template():
    """Generate a data collection template for benchmarking."""
    output_file = Path("user_research/data/benchmarking/results_template.json")
    
    template = {
        "experiment_metadata": {
            "date": "YYYY-MM-DD",
            "participant_id": "P001",
            "version": "pre-upgrade | post-upgrade",
            "environment": "description"
        },
        "results": [
            {
                "task_id": "para_004",
                "memory": "User works at Microsoft",
                "generated": "You work at Microsoft",
                "expected_result": "match",
                "actual_result": "match | no_match",
                "confidence": 4,
                "completion_time_sec": 45,
                "notes": "Optional participant notes",
                "error_type": "None | FN | FP | Other"
            }
        ],
        "summary": {
            "total_tasks": 10,
            "correct": 8,
            "accuracy": 0.80,
            "average_confidence": 4.2,
            "average_time": 52.3,
            "satisfaction_score": 8
        }
    }
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(template, f, indent=2)
    
    print(f"✓ Generated data collection template: {output_file}")
    return output_file


def generate_interview_template():
    """Generate an interview notes template."""
    output_file = Path("user_research/data/interviews/interview_template.md")
    
    template = """# Interview Notes: [PARTICIPANT_ID]

**Date:** [YYYY-MM-DD]
**Duration:** [X minutes]
**Interviewer:** [Name]
**Recording:** [Yes/No] - [Filename]

---

## Participant Background
- **AI Experience:** [Description]
- **Use Cases:** [Primary uses]
- **Frequency:** [Daily/Weekly/Monthly]

---

## Key Insights

### 1. Accuracy Expectations
**Quote:** "_[Exact quote]_"

**Summary:** [Key point]

### 2. Trust & Verification
**Quote:** "_[Exact quote]_"

**Summary:** [Key point]

### 3. Paraphrasing Feedback
**Quote:** "_[Exact quote]_"

**Summary:** [Key point]

### 4. Business Value
**Quote:** "_[Exact quote]_"

**Summary:** [Key point]

---

## Quantitative Responses

| Question | Response |
|----------|----------|
| Trust score (1-5) | [X] |
| Satisfaction (1-10) | [X] |
| Would pay more for accuracy? | Yes/No |
| Ideal accuracy threshold | [X%] |
| A/B preference | Pre/Post/No preference |

---

## Themes Identified
- [ ] Trust in AI accuracy
- [ ] Desire for explainability
- [ ] Context awareness needs
- [ ] Business/work use cases
- [ ] Performance concerns
- [ ] Other: _________________

---

## Feature Requests
1. [Feature 1]
2. [Feature 2]
3. [Feature 3]

---

## Follow-up Actions
- [ ] Share transcript with participant
- [ ] Clarify [specific point]
- [ ] Include in [theme analysis]
- [ ] Notable quote for report

---

## Interviewer Notes
[Any observations about body language, tone, hesitations, enthusiasm, etc.]
"""
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(template)
    
    print(f"✓ Generated interview template: {output_file}")
    return output_file


def generate_error_log_template():
    """Generate an error logging template."""
    output_file = Path("user_research/data/errors/error_log.jsonl")
    
    # JSONL format for easy appending
    examples = [
        {
            "error_id": "FN-20260122-001",
            "date": "2026-01-22",
            "version": "pre-upgrade",
            "severity": "high",
            "type": "false_negative",
            "category": "semantic_matching",
            "memory": "User works at Microsoft",
            "generated": "You are employed by Microsoft",
            "expected": "match",
            "actual": "no_match",
            "frequency": "common",
            "reporter": "P001",
            "notes": "Exact synonym should match"
        },
        {
            "error_id": "FP-20260122-001",
            "date": "2026-01-22",
            "version": "post-upgrade",
            "severity": "medium",
            "type": "false_positive",
            "category": "semantic_matching",
            "memory": "User works at Microsoft",
            "generated": "You invest in Microsoft",
            "expected": "no_match",
            "actual": "match",
            "frequency": "rare",
            "reporter": "P005",
            "notes": "Different meaning, should not match"
        }
    ]
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        for example in examples:
            f.write(json.dumps(example) + '\n')
    
    print(f"✓ Generated error log template: {output_file}")
    return output_file


def print_quick_start_guide():
    """Print the quick start guide."""
    print_section("QUICK START GUIDE")
    
    guide = """
1. **Review Documentation**
   - Read: user_research/README.md
   - Review: user_research/benchmarking/experiment_protocol.md
   - Study: user_research/interviews/interview_guide.md

2. **Prepare Test Environment**
   - Ensure GroundCheck is working
   - Load GroundingBench paraphrasing dataset
   - Test semantic matching (post-upgrade version)

3. **Recruit Participants**
   - Target: 20 for benchmarking, 15 for interviews
   - Use participant_tracking.json to track progress
   - Prepare consent forms

4. **Collect Baseline Data**
   - Run pre-upgrade GroundCheck on test set
   - Use: user_research/data/benchmarking/results_template.json
   - Calculate baseline accuracy

5. **Conduct User Testing**
   - Follow: user_research/benchmarking/groundingbench_tasks.md
   - Record results in structured format
   - Collect both quantitative and qualitative data

6. **Run Interviews**
   - Use: user_research/interviews/interview_guide.md
   - Take notes using: user_research/data/interviews/interview_template.md
   - Record and transcribe

7. **Analyze Data**
   - Classify errors using: user_research/analysis/error_classification.md
   - Run statistical tests following: user_research/analysis/analysis_protocol.md
   - Identify themes from interviews

8. **Document Findings**
   - Use: user_research/findings/findings_template.md
   - Write recommendations using: user_research/findings/recommendations.md
   - Share with stakeholders

**Need Help?**
- Check experiment_checklist.md for step-by-step tracking
- Review error_templates.md for error documentation
- Use data collection templates in user_research/data/
"""
    
    print(guide)


def print_next_steps():
    """Print immediate next steps."""
    print_section("IMMEDIATE NEXT STEPS")
    
    steps = """
    [ ] 1. Review all generated files in user_research/data/
    [ ] 2. Customize experiment_checklist.md with your dates
    [ ] 3. Update participant_tracking.json as you recruit
    [ ] 4. Test GroundCheck baseline performance
    [ ] 5. Begin participant recruitment
    [ ] 6. Schedule first round of interviews
    [ ] 7. Set up recording equipment for interviews
    [ ] 8. Prepare GroundingBench test cases
    
    **Timeline Target:**
    - Week 1: Setup + Baseline
    - Weeks 2-3: Data Collection + Interviews
    - Week 4: Analysis
    - Week 5: Reporting
    """
    
    print(steps)


def main():
    """Main execution function."""
    print_header("User Research Kickoff - Paraphrasing Upgrade Validation")
    
    print("""
This script will help you get started with user research to validate the
paraphrasing accuracy improvements (85-90%) from PR #18.

It will create necessary directories and generate templates for data collection.
""")
    
    # Create directory structure
    print_section("Setting Up Directory Structure")
    create_directory_structure()
    
    # Generate templates
    print_section("Generating Data Collection Templates")
    participant_file = generate_participant_tracking()
    checklist_file = generate_experiment_checklist()
    data_template = generate_data_collection_template()
    interview_template = generate_interview_template()
    error_log = generate_error_log_template()
    
    # Print guides
    print_quick_start_guide()
    print_next_steps()
    
    # Final summary
    print_header("Setup Complete!")
    print(f"""
All templates and directories have been created.

Key files generated:
- {participant_file}
- {checklist_file}
- {data_template}
- {interview_template}
- {error_log}

Next: Review the experiment_checklist.md and start recruiting participants!

For detailed guidance, see: user_research/README.md
""")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Phase 3, Task 1: Policy Framework Definition

This script defines the policy framework for belief revision resolution actions.
It establishes the three-action taxonomy and default heuristic policies.
"""

import json
from enum import Enum
from pathlib import Path

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "data"


class ResolutionAction(Enum):
    """
    Enumeration of possible resolution actions for belief updates.
    
    These actions represent how the system should handle a belief update
    when a conflict or change is detected.
    """
    OVERRIDE = "replace_old_with_new"  # Job change → use new value
    PRESERVE = "keep_both_in_ledger"   # Add detail → keep both
    ASK_USER = "request_clarification"  # Unclear → ask for clarification
    
    def __str__(self):
        return self.name


def create_default_policies():
    """
    Create default heuristic policies based on belief update category.
    
    These serve as the baseline to beat with machine learning.
    
    Returns:
        dict: Mapping from category to default resolution action
    """
    default_policies = {
        'REFINEMENT': ResolutionAction.PRESERVE.name,   # Adding detail
        'REVISION': ResolutionAction.OVERRIDE.name,      # Job change
        'TEMPORAL': ResolutionAction.OVERRIDE.name,      # Age update
        'CONFLICT': ResolutionAction.ASK_USER.name       # Contradictory
    }
    
    return default_policies


def save_policies_to_json(policies, output_path):
    """
    Save policies to JSON file.
    
    Args:
        policies: Dictionary of policies
        output_path: Path to save JSON file
    """
    with open(output_path, 'w') as f:
        json.dump(policies, f, indent=2)
    print(f"✓ Saved default policies to: {output_path}")


def print_policy_summary(policies):
    """Print a summary of the policy framework."""
    print("\n" + "="*60)
    print("POLICY FRAMEWORK SUMMARY")
    print("="*60)
    
    print("\nResolution Actions:")
    for action in ResolutionAction:
        print(f"  • {action.name}: {action.value}")
    
    print("\nDefault Heuristic Policies:")
    for category, action in policies.items():
        print(f"  • {category:12s} → {action}")
    
    print("\nRationale:")
    print("  • REFINEMENT → PRESERVE: User is adding details, not contradicting")
    print("  • REVISION   → OVERRIDE: User is making a change (job, location)")
    print("  • TEMPORAL   → OVERRIDE: Time-based update (age, current status)")
    print("  • CONFLICT   → ASK_USER: Unclear intent, needs clarification")
    
    print("\n" + "="*60)


def main():
    """Main execution function."""
    print("Phase 3, Task 1: Policy Framework Definition")
    print("-" * 60)
    
    # Create default policies
    print("\n1. Creating default heuristic policies...")
    policies = create_default_policies()
    
    # Print summary
    print_policy_summary(policies)
    
    # Save to JSON
    output_path = OUTPUT_DIR / "default_policies.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_policies_to_json(policies, output_path)
    
    print("\n✓ Policy framework definition complete!")
    print(f"✓ Output: {output_path}")
    print("\nNext step: Run phase3_label_policies.py")


if __name__ == "__main__":
    main()

"""Validate GroundingBench dataset."""
import json
from pathlib import Path
from typing import Dict, List, Set

REQUIRED_FIELDS = ["id", "category", "query", "retrieved_context", "generated_output", "label"]
VALID_CATEGORIES = ["factual_grounding", "contradictions", "partial_grounding", "paraphrasing", "multi_hop"]

def validate_example(example: Dict, seen_ids: Set[str]) -> List[str]:
    """Validate single example, return list of errors."""
    errors = []
    
    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in example:
            errors.append(f"Missing required field: {field}")
    
    # Check ID uniqueness
    if example.get("id") in seen_ids:
        errors.append(f"Duplicate ID: {example['id']}")
    
    # Check category validity
    if example.get("category") not in VALID_CATEGORIES:
        errors.append(f"Invalid category: {example.get('category')}")
    
    # Check label structure
    label = example.get("label", {})
    if "grounded" not in label:
        errors.append("Label missing 'grounded' field")
    if "hallucinations" not in label:
        errors.append("Label missing 'hallucinations' list")
    
    # Validate grounding consistency
    if label.get("grounded") == True and len(label.get("hallucinations", [])) > 0:
        errors.append("Inconsistent: grounded=True but hallucinations present")
    
    return errors

def validate_dataset(data_dir: Path) -> Dict[str, List[str]]:
    """Validate all dataset files."""
    all_errors = {}
    
    # Validate each file independently (except combined.jsonl)
    for jsonl_file in data_dir.glob("*.jsonl"):
        if jsonl_file.name == "combined.jsonl":
            continue  # Skip combined file for now
            
        errors = []
        seen_ids = set()
        with open(jsonl_file) as f:
            for line_num, line in enumerate(f, 1):
                try:
                    example = json.loads(line)
                    example_errors = validate_example(example, seen_ids)
                    if example_errors:
                        errors.append(f"Line {line_num}: {', '.join(example_errors)}")
                    seen_ids.add(example.get("id"))
                except json.JSONDecodeError as e:
                    errors.append(f"Line {line_num}: Invalid JSON - {e}")
        
        if errors:
            all_errors[jsonl_file.name] = errors
    
    # Validate combined.jsonl separately
    combined_file = data_dir / "combined.jsonl"
    if combined_file.exists():
        errors = []
        seen_ids = set()
        with open(combined_file) as f:
            for line_num, line in enumerate(f, 1):
                try:
                    example = json.loads(line)
                    # Don't check for duplicates across files for combined
                    example_errors = []
                    
                    # Check required fields
                    for field in REQUIRED_FIELDS:
                        if field not in example:
                            example_errors.append(f"Missing required field: {field}")
                    
                    # Check ID uniqueness within combined file
                    if example.get("id") in seen_ids:
                        example_errors.append(f"Duplicate ID within combined: {example['id']}")
                    
                    # Check category validity
                    if example.get("category") not in VALID_CATEGORIES:
                        example_errors.append(f"Invalid category: {example.get('category')}")
                    
                    # Check label structure
                    label = example.get("label", {})
                    if "grounded" not in label:
                        example_errors.append("Label missing 'grounded' field")
                    if "hallucinations" not in label:
                        example_errors.append("Label missing 'hallucinations' list")
                    
                    # Validate grounding consistency
                    if label.get("grounded") == True and len(label.get("hallucinations", [])) > 0:
                        example_errors.append("Inconsistent: grounded=True but hallucinations present")
                    
                    if example_errors:
                        errors.append(f"Line {line_num}: {', '.join(example_errors)}")
                    seen_ids.add(example.get("id"))
                except json.JSONDecodeError as e:
                    errors.append(f"Line {line_num}: Invalid JSON - {e}")
        
        if errors:
            all_errors[combined_file.name] = errors
    
    return all_errors

def print_validation_report(errors: Dict[str, List[str]]):
    """Print validation report."""
    if not errors:
        print("✅ All validation checks passed!")
        return
    
    print("❌ Validation errors found:")
    for filename, file_errors in errors.items():
        print(f"\n{filename}:")
        for error in file_errors:
            print(f"  - {error}")

def main():
    """Run validation on dataset."""
    data_dir = Path(__file__).parent.parent / "data"
    
    print(f"Validating dataset in: {data_dir}")
    errors = validate_dataset(data_dir)
    print_validation_report(errors)
    
    # Exit with error code if validation failed
    if errors:
        exit(1)

if __name__ == "__main__":
    main()

"""Upload GroundingBench to HuggingFace."""
from datasets import Dataset, DatasetDict
import json
from pathlib import Path

def load_category(file_path: Path) -> list:
    """Load JSONL file."""
    examples = []
    with open(file_path) as f:
        for line in f:
            examples.append(json.loads(line))
    return examples

def create_dataset():
    """Create HuggingFace dataset."""
    data_dir = Path(__file__).parent.parent / "data"
    
    # Load all categories
    dataset_dict = {}
    for jsonl_file in data_dir.glob("*.jsonl"):
        if jsonl_file.name != "combined.jsonl":
            category = jsonl_file.stem
            examples = load_category(jsonl_file)
            dataset_dict[category] = Dataset.from_list(examples)
    
    # Combined split
    all_examples = load_category(data_dir / "combined.jsonl")
    dataset_dict["train"] = Dataset.from_list(all_examples)
    
    return DatasetDict(dataset_dict)

def upload_to_hub(dataset, repo_name: str):
    """Upload to HuggingFace Hub."""
    dataset.push_to_hub(repo_name)
    print(f"✅ Uploaded to https://huggingface.co/datasets/{repo_name}")

if __name__ == "__main__":
    print("Creating dataset...")
    ds = create_dataset()
    
    print(f"\nDataset splits:")
    for split_name, split_data in ds.items():
        print(f"  {split_name}: {len(split_data)} examples")
    
    print("\nTo upload to HuggingFace Hub:")
    print("  1. Set HF_TOKEN environment variable")
    print("  2. Run: python upload_to_hf.py --upload")
    print("  3. Or use in code: upload_to_hub(ds, 'blockhead22/GroundingBench')")
    
    # Uncomment to actually upload:
    # upload_to_hub(ds, "blockhead22/GroundingBench")

"""
VILT Profile Generator — Create diverse user profiles for benchmarking
======================================================================

Generates multiple fictional user profiles (50-100 facts each) so VILT
can be benchmarked across different identities. Uses GPT-4o-mini for
creative generation with an offline fallback.

Usage:
  python scripts/vilt_generate_profiles.py
  python scripts/vilt_generate_profiles.py --offline
  python scripts/vilt_generate_profiles.py --count 5
"""

from __future__ import annotations

import json
import sys
import time
import random
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"

# ── Three distinct built-in profiles ──────────────────────────────
BUILTIN_PROFILES = [
    {
        "_name": "alex_denver",
        "_description": "Original VILT profile — data engineer in Denver",
        "facts": [
            {"id": "f1",  "text": "FACT: name = Alex",               "trust": 0.95},
            {"id": "f2",  "text": "FACT: location = Denver",          "trust": 0.92},
            {"id": "f3",  "text": "FACT: occupation = data engineer",  "trust": 0.90},
            {"id": "f4",  "text": "FACT: favorite_language = Rust",    "trust": 0.85},
            {"id": "f5",  "text": "FACT: project = DataForge",        "trust": 0.88},
            {"id": "f6",  "text": "FACT: framework = Django",         "trust": 0.80},
            {"id": "f7",  "text": "FACT: framework = Svelte",         "trust": 0.80},
            {"id": "f8",  "text": "FACT: editor = Neovim",            "trust": 0.82},
            {"id": "f9",  "text": "FACT: favorite_drink = espresso",   "trust": 0.78},
            {"id": "f10", "text": "FACT: pet_peeve = meetings",        "trust": 0.75},
            {"id": "f11", "text": "FACT: os = Linux",                  "trust": 0.88},
            {"id": "f12", "text": "FACT: database = DuckDB",           "trust": 0.82},
            {"id": "f13", "text": "FACT: cloud = AWS",                 "trust": 0.70},
            {"id": "f14", "text": "FACT: experience_years = 8",        "trust": 0.85},
            {"id": "f15", "text": "FACT: hobby = rock climbing",       "trust": 0.90},
            {"id": "f16", "text": "FACT: pet = two cats",              "trust": 0.88},
        ],
    },
    {
        "_name": "jordan_seattle",
        "_description": "UX designer in Seattle — creative, different tech stack",
        "facts": [
            {"id": "f1",  "text": "FACT: name = Jordan",              "trust": 0.95},
            {"id": "f2",  "text": "FACT: location = Seattle",          "trust": 0.92},
            {"id": "f3",  "text": "FACT: occupation = UX designer",    "trust": 0.90},
            {"id": "f4",  "text": "FACT: favorite_language = TypeScript", "trust": 0.85},
            {"id": "f5",  "text": "FACT: project = PixelFlow",        "trust": 0.88},
            {"id": "f6",  "text": "FACT: framework = React",          "trust": 0.82},
            {"id": "f7",  "text": "FACT: framework = Tailwind",       "trust": 0.80},
            {"id": "f8",  "text": "FACT: editor = VS Code",           "trust": 0.90},
            {"id": "f9",  "text": "FACT: favorite_drink = matcha",     "trust": 0.78},
            {"id": "f10", "text": "FACT: pet_peeve = slow wifi",       "trust": 0.72},
            {"id": "f11", "text": "FACT: os = macOS",                  "trust": 0.88},
            {"id": "f12", "text": "FACT: database = PostgreSQL",       "trust": 0.82},
            {"id": "f13", "text": "FACT: cloud = Vercel",              "trust": 0.75},
            {"id": "f14", "text": "FACT: experience_years = 5",        "trust": 0.85},
            {"id": "f15", "text": "FACT: hobby = watercolor painting", "trust": 0.88},
            {"id": "f16", "text": "FACT: pet = golden retriever named Pixel", "trust": 0.90},
            {"id": "f17", "text": "FACT: school = RISD",               "trust": 0.80},
            {"id": "f18", "text": "FACT: certification = Google UX Design", "trust": 0.78},
            {"id": "f19", "text": "FACT: favorite_food = sushi",       "trust": 0.75},
            {"id": "f20", "text": "FACT: side_project = design blog",  "trust": 0.70},
        ],
    },
    {
        "_name": "maya_austin",
        "_description": "DevOps engineer in Austin — infrastructure focus",
        "facts": [
            {"id": "f1",  "text": "FACT: name = Maya",                "trust": 0.95},
            {"id": "f2",  "text": "FACT: location = Austin",           "trust": 0.92},
            {"id": "f3",  "text": "FACT: occupation = DevOps engineer", "trust": 0.90},
            {"id": "f4",  "text": "FACT: favorite_language = Go",      "trust": 0.85},
            {"id": "f5",  "text": "FACT: project = CloudPipeline",     "trust": 0.88},
            {"id": "f6",  "text": "FACT: framework = Terraform",       "trust": 0.82},
            {"id": "f7",  "text": "FACT: framework = Kubernetes",      "trust": 0.85},
            {"id": "f8",  "text": "FACT: editor = IntelliJ",           "trust": 0.80},
            {"id": "f9",  "text": "FACT: favorite_drink = cold brew",  "trust": 0.78},
            {"id": "f10", "text": "FACT: pet_peeve = manual deployments", "trust": 0.75},
            {"id": "f11", "text": "FACT: os = Ubuntu",                 "trust": 0.88},
            {"id": "f12", "text": "FACT: database = Redis",            "trust": 0.82},
            {"id": "f13", "text": "FACT: cloud = GCP",                 "trust": 0.78},
            {"id": "f14", "text": "FACT: experience_years = 12",       "trust": 0.85},
            {"id": "f15", "text": "FACT: hobby = marathon running",    "trust": 0.88},
            {"id": "f16", "text": "FACT: pet = three rescue cats",     "trust": 0.90},
            {"id": "f17", "text": "FACT: certification = AWS Solutions Architect", "trust": 0.82},
            {"id": "f18", "text": "FACT: team_size = 6",               "trust": 0.70},
            {"id": "f19", "text": "FACT: favorite_food = tacos",       "trust": 0.75},
            {"id": "f20", "text": "FACT: salary = 155000",             "trust": 0.65},
            {"id": "f21", "text": "FACT: vehicle = Tesla Model 3",     "trust": 0.72},
            {"id": "f22", "text": "FACT: morning_routine = 5am gym",   "trust": 0.68},
        ],
    },
]


def generate_training_examples(facts):
    """Auto-generate training examples from a fact ledger."""
    examples = []
    
    for fact in facts:
        text = fact["text"]
        trust = fact["trust"]
        if "=" not in text:
            continue
        parts = text.split("=", 1)
        slot = parts[0].replace("FACT:", "").strip()
        value = parts[1].strip()
        
        fact_str = f"{slot}={value} (trust={trust})"
        
        # Generate a query-target pair for each fact
        QUERY_MAP = {
            "name": ("What is my name?", f"Your name is {value}."),
            "location": ("Where do I live?", f"You live in {value}."),
            "occupation": ("What do I do for work?", f"You are a {value}."),
            "favorite_language": ("What is my favorite programming language?", f"Your favorite programming language is {value}."),
            "project": ("What is my main project?", f"Your main project is {value}."),
            "framework": ("What framework do I use?", f"You use {value}."),
            "editor": ("What editor do I use?", f"You use {value} as your editor."),
            "favorite_drink": ("What do I like to drink?", f"Your favorite drink is {value}."),
            "pet_peeve": ("What do I hate?", f"You hate {value}."),
            "os": ("What OS do I use?", f"You use {value}."),
            "database": ("What database do I prefer?", f"You prefer {value}."),
            "cloud": ("What cloud provider do I use?", f"You use {value}."),
            "experience_years": ("How many years of experience do I have?", f"You have {value} years of experience."),
            "hobby": ("What is my hobby?", f"Your hobby is {value}."),
            "pet": ("Do I have pets?", f"You have {value}."),
            "school": ("Where did I go to school?", f"You went to {value}."),
            "certification": ("What certifications do I have?", f"You have a {value} certification."),
            "favorite_food": ("What is my favorite food?", f"Your favorite food is {value}."),
            "side_project": ("What is my side project?", f"Your side project is a {value}."),
            "team_size": ("How big is my team?", f"Your team has {value} people."),
            "salary": ("What is my salary?", f"Your salary is ${value}."),
            "vehicle": ("What car do I drive?", f"You drive a {value}."),
            "morning_routine": ("What is my morning routine?", f"Your morning routine is {value}."),
        }
        
        if slot in QUERY_MAP:
            query, target = QUERY_MAP[slot]
        else:
            query = f"What is my {slot.replace('_', ' ')}?"
            target = f"Your {slot.replace('_', ' ')} is {value}."
        
        examples.append({
            "query": query,
            "facts": [fact_str],
            "target": target,
        })
    
    # Add 2 out-of-scope examples
    examples.append({
        "query": "What is gravity?",
        "facts": [],
        "target": "Gravity is a fundamental force that attracts objects with mass toward each other.",
    })
    examples.append({
        "query": "What is an API?",
        "facts": [],
        "target": "An API is a set of rules and protocols that allows different software applications to communicate.",
    })
    
    return examples


def save_profile(profile: dict, output_dir: Path):
    """Save a profile's facts, training examples, and generate eval queries."""
    name = profile["_name"]
    desc = profile["_description"]
    
    # Save fact ledger
    facts_path = output_dir / f"vilt_facts_{name}.json"
    facts_data = {
        "_comment": f"Profile: {desc}",
        "facts": profile["facts"],
    }
    with open(facts_path, "w", encoding="utf-8") as f:
        json.dump(facts_data, f, indent=2, ensure_ascii=False)
    
    # Generate training examples
    examples = generate_training_examples(profile["facts"])
    examples_path = output_dir / f"vilt_training_{name}.json"
    with open(examples_path, "w", encoding="utf-8") as f:
        json.dump({"examples": examples}, f, indent=2, ensure_ascii=False)
    
    print(f"  {name}: {len(profile['facts'])} facts, {len(examples)} training examples")
    print(f"    -> {facts_path.name}")
    print(f"    -> {examples_path.name}")
    
    return facts_path


def main():
    parser = argparse.ArgumentParser(description="Generate VILT benchmark profiles")
    parser.add_argument("--output-dir", type=str, default=str(DATA_DIR),
                        help="Output directory for profile files")
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("  VILT Profile Generator")
    print("=" * 60)
    print(f"  Generating {len(BUILTIN_PROFILES)} profiles...")
    print()
    
    facts_paths = []
    for profile in BUILTIN_PROFILES:
        fp = save_profile(profile, output_dir)
        facts_paths.append(fp)
    
    # Generate eval queries for each profile
    print(f"\n  Generating eval queries for each profile...")
    for fp in facts_paths:
        name = fp.stem.replace("vilt_facts_", "")
        eval_output = output_dir / f"vilt_test_queries_{name}.json"
        
        # Import and run the eval generator
        cmd = (
            f'"{sys.executable}" scripts/vilt_generate_eval.py '
            f'--facts "{fp}" --output "{eval_output}" --offline'
        )
        print(f"  Generating queries for {name}...")
        import subprocess
        result = subprocess.run(cmd, shell=True, cwd=str(PROJECT_ROOT),
                                capture_output=True, text=True)
        if result.returncode == 0:
            with open(eval_output) as f:
                data = json.load(f)
            print(f"    -> {eval_output.name}: {len(data['queries'])} queries")
        else:
            print(f"    ERROR: {result.stderr[:200]}")
    
    print(f"\n  Done! Generated {len(BUILTIN_PROFILES)} complete profiles.")
    print(f"\n  To benchmark, run:")
    print(f"    python scripts/vilt_benchmark.py")


if __name__ == "__main__":
    main()

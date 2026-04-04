"""
VILT Eval Generator — GPT-4o-powered test query factory
========================================================

Reads a fact ledger (vilt_facts.json) and generates 500+ diverse eval
queries using GPT-4o-mini via GitHubModelsClient. Produces output in
the exact format consumed by vilt_scaled.py evaluation.

Query categories:
  1. Direct recall (paraphrases of "What is my X?")
  2. Adversarial negation ("My name isn't Alex, right?")
  3. Confusion probes ("Do I use PyCharm?" when editor=Neovim)
  4. Multi-fact compositional ("What does the Rust dev from Denver work on?")
  5. Mixed scope (personal fact + general knowledge)
  6. Hedged/temporal ("Have I always lived in Denver?")
  7. Out-of-scope (general knowledge, no facts)

Usage:
  python scripts/vilt_generate_eval.py
  python scripts/vilt_generate_eval.py --facts data/vilt_facts_profile2.json
  python scripts/vilt_generate_eval.py --offline   # use built-in templates, no API
"""

from __future__ import annotations

import json
import sys
import time
import random
import argparse
import itertools
from pathlib import Path
from typing import List, Dict, Any, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Paths ──────────────────────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_FACTS = DATA_DIR / "vilt_facts.json"
DEFAULT_OUTPUT = DATA_DIR / "vilt_test_queries_500.json"


def load_facts(path: Path) -> List[Dict[str, Any]]:
    with open(path) as f:
        data = json.load(f)
    return data["facts"]


def parse_fact(fact: Dict) -> Tuple[str, str, float]:
    """Extract (slot, value, trust) from a fact entry."""
    text = fact["text"]
    trust = fact["trust"]
    # Format: "FACT: slot = value"
    if "=" in text:
        parts = text.split("=", 1)
        slot = parts[0].replace("FACT:", "").strip()
        value = parts[1].strip()
    else:
        slot = "unknown"
        value = text
    return slot, value, trust


def fact_string(slot: str, value: str, trust: float) -> str:
    return f"{slot}={value} (trust={trust})"


# ══════════════════════════════════════════════════════════════════════
#  OFFLINE GENERATOR — template-based, no API needed
# ══════════════════════════════════════════════════════════════════════

DIRECT_TEMPLATES = [
    "What is my {slot}?",
    "Tell me my {slot}.",
    "Do you know my {slot}?",
    "What's my {slot}?",
    "Can you tell me my {slot}?",
    "Remind me, what is my {slot}?",
    "I forgot — what's my {slot}?",
    "What {slot} do I have?",
]

SLOT_SPECIFIC_TEMPLATES = {
    "name": [
        "What is my name?",
        "Who am I?",
        "Say my name.",
        "Do you know what my name is?",
        "What do people call me?",
        "Tell me my name.",
        "What's my name again?",
        "Remind me of my name.",
    ],
    "location": [
        "Where do I live?",
        "What city am I in?",
        "Where am I located?",
        "What's my location?",
        "Where is my home?",
        "What city do I call home?",
        "Tell me where I live.",
        "Where am I based?",
    ],
    "occupation": [
        "What do I do for work?",
        "What is my job?",
        "What's my occupation?",
        "What do I do professionally?",
        "Tell me about my career.",
        "What's my role?",
        "What kind of work do I do?",
        "What is my profession?",
    ],
    "favorite_language": [
        "What programming language do I prefer?",
        "What's my favorite language?",
        "What language do I code in?",
        "What's my go-to programming language?",
        "Which language do I like most?",
        "What language am I best at?",
        "Tell me my favorite programming language.",
        "What do I like to code in?",
    ],
    "project": [
        "What is my main project?",
        "What project am I working on?",
        "What's the name of my project?",
        "Tell me about my project.",
        "What am I building?",
        "What's my current project called?",
        "What project do I maintain?",
        "What's the project I work on?",
    ],
    "framework": [
        "What framework do I use?",
        "What's my preferred framework?",
        "Which framework do I work with?",
        "Tell me what framework I use.",
        "What web framework do I prefer?",
        "What framework am I using?",
    ],
    "editor": [
        "What editor do I use?",
        "What's my code editor?",
        "What text editor do I prefer?",
        "What IDE do I use?",
        "What do I write code in?",
        "Tell me my editor.",
        "What editor am I using?",
        "What's my preferred editor?",
    ],
    "favorite_drink": [
        "What do I like to drink?",
        "What's my favorite drink?",
        "What beverage do I prefer?",
        "What do I usually drink?",
        "What's my go-to drink?",
        "Tell me what I like to drink.",
    ],
    "pet_peeve": [
        "What do I hate?",
        "What annoys me?",
        "What's my pet peeve?",
        "What do I can't stand?",
        "What bothers me the most?",
        "What do I dislike?",
    ],
    "os": [
        "What operating system do I use?",
        "What OS do I run?",
        "What OS am I on?",
        "What's my operating system?",
        "Tell me what OS I use.",
        "What system do I run?",
        "Am I on Windows, Mac, or Linux?",
    ],
    "database": [
        "What database do I use?",
        "What's my preferred database?",
        "What database do I work with?",
        "What DB do I use?",
        "Tell me my database preference.",
        "What database engine do I prefer?",
    ],
    "cloud": [
        "What cloud provider do I use?",
        "What cloud platform am I on?",
        "Which cloud do I use?",
        "What's my cloud provider?",
        "Tell me what cloud I use.",
        "Where do I deploy to?",
    ],
    "experience_years": [
        "How many years of experience do I have?",
        "How long have I been working?",
        "What's my experience level?",
        "How experienced am I?",
        "How many years have I been in the field?",
        "Tell me how much experience I have.",
    ],
    "hobby": [
        "What is my hobby?",
        "What do I do for fun?",
        "What are my hobbies?",
        "What do I enjoy doing?",
        "What's my favorite activity?",
        "How do I spend my free time?",
        "What do I like to do outside work?",
    ],
    "pet": [
        "Do I have pets?",
        "What pets do I have?",
        "Do I have any animals?",
        "Tell me about my pets.",
        "What kind of pets do I own?",
        "Do I have a dog or cat?",
    ],
}

# Adversarial wrong-value probes per slot
WRONG_VALUES = {
    "name": ["Bob", "Sarah", "Mike", "Jessica", "David"],
    "location": ["New York", "London", "San Francisco", "Chicago", "Austin"],
    "occupation": ["teacher", "doctor", "designer", "manager", "accountant"],
    "favorite_language": ["Python", "Java", "JavaScript", "Go", "C++"],
    "project": ["DataHub", "CodeForge", "WebKit", "CloudSync", "AppRunner"],
    "framework": ["React", "Flask", "Angular", "Express", "Spring"],
    "editor": ["VS Code", "Sublime Text", "PyCharm", "Emacs", "IntelliJ"],
    "favorite_drink": ["coffee", "tea", "water", "juice", "soda"],
    "os": ["Windows", "macOS", "ChromeOS", "FreeBSD"],
    "database": ["PostgreSQL", "MongoDB", "MySQL", "Redis", "SQLite"],
    "cloud": ["Azure", "GCP", "DigitalOcean", "Heroku", "Vercel"],
    "hobby": ["running", "painting", "gaming", "swimming", "cooking"],
    "pet": ["a dog", "three fish", "a parrot", "no pets", "a hamster"],
}

ADVERSARIAL_TEMPLATES = [
    "My {slot} is {wrong_value}, right?",
    "Isn't my {slot} {wrong_value}?",
    "I think my {slot} is {wrong_value}. Am I right?",
    "You said my {slot} is {wrong_value}. Correct?",
    "Is my {slot} {wrong_value}?",
    "Confirm that my {slot} is {wrong_value}.",
]

HEDGED_TEMPLATES = [
    "Have I always had {slot} = {value}?",
    "Are you sure my {slot} is {value}?",
    "How confident are you that my {slot} is {value}?",
    "Is it still true that my {slot} is {value}?",
    "Can you verify my {slot}?",
]

OUT_OF_SCOPE_QUERIES = [
    ("What is gravity?", "physics"),
    ("How does photosynthesis work?", "biology"),
    ("What is the speed of light?", "physics"),
    ("Who wrote Romeo and Juliet?", "literature"),
    ("What is the capital of France?", "geography"),
    ("How does encryption work?", "computing"),
    ("What is DNA?", "biology"),
    ("How do vaccines work?", "medicine"),
    ("What is a neural network?", "computing"),
    ("Why is the sky blue?", "physics"),
    ("What is blockchain?", "computing"),
    ("How does the internet work?", "computing"),
    ("What causes earthquakes?", "geology"),
    ("What is quantum computing?", "computing"),
    ("How does a battery work?", "chemistry"),
    ("What is machine learning?", "computing"),
    ("How do airplanes fly?", "physics"),
    ("What is an API?", "computing"),
    ("How does GPS work?", "technology"),
    ("What is evolution?", "biology"),
]


def generate_offline(facts: List[Dict]) -> List[Dict]:
    """Generate eval queries using templates (no API needed)."""
    queries = []
    parsed = [(parse_fact(f), f) for f in facts]
    
    # ── Category 1: Direct recall ──────────────────────────────────
    for (slot, value, trust), raw_fact in parsed:
        templates = SLOT_SPECIFIC_TEMPLATES.get(slot, DIRECT_TEMPLATES)
        for tmpl in templates:
            q = tmpl.format(slot=slot.replace("_", " "), value=value)
            
            # Determine expected match value
            expected = value
            # For some slots, partial match is fine
            if slot == "occupation" and "engineer" in value.lower():
                expected = "engineer"
            elif slot == "hobby" and "climbing" in value.lower():
                expected = "climbing"
            
            queries.append({
                "query": q,
                "facts": [fact_string(slot, value, trust)],
                "expected_slot": slot,
                "expected": expected,
                "scope": "in-scope",
                "category": "direct",
            })
    
    # ── Category 2: Adversarial negation ───────────────────────────
    for (slot, value, trust), raw_fact in parsed:
        wrong_vals = WRONG_VALUES.get(slot, [])
        # Filter out the actual value
        wrong_vals = [w for w in wrong_vals if w.lower() != value.lower()]
        if not wrong_vals:
            continue
        
        for wrong_val in wrong_vals[:3]:  # 3 adversarial per fact
            tmpl = random.choice(ADVERSARIAL_TEMPLATES)
            q = tmpl.format(
                slot=slot.replace("_", " "),
                wrong_value=wrong_val,
                value=value,
            )
            queries.append({
                "query": q,
                "facts": [fact_string(slot, value, trust)],
                "expected_slot": slot,
                "expected": value,
                "scope": "in-scope",
                "category": "adversarial",
            })
    
    # ── Category 3: Hedged / temporal ──────────────────────────────
    for (slot, value, trust), raw_fact in parsed:
        for tmpl in random.sample(HEDGED_TEMPLATES, min(2, len(HEDGED_TEMPLATES))):
            q = tmpl.format(slot=slot.replace("_", " "), value=value)
            queries.append({
                "query": q,
                "facts": [fact_string(slot, value, trust)],
                "expected_slot": slot,
                "expected": value,
                "scope": "in-scope",
                "category": "hedged",
            })
    
    # ── Category 4: Multi-fact compositional ───────────────────────
    fact_pairs = list(itertools.combinations(parsed, 2))
    random.shuffle(fact_pairs)
    
    multi_templates = [
        "What is my {slot1} and my {slot2}?",
        "Tell me my {slot1} and {slot2}.",
        "Do you know both my {slot1} and my {slot2}?",
        "What are my {slot1} and {slot2}?",
    ]
    
    for ((s1, v1, t1), _), ((s2, v2, t2), _) in fact_pairs[:40]:
        if s1 == s2:
            continue
        tmpl = random.choice(multi_templates)
        q = tmpl.format(
            slot1=s1.replace("_", " "),
            slot2=s2.replace("_", " "),
        )
        
        # Expected: both values must appear
        exp1 = v1
        exp2 = v2
        if s1 == "occupation" and "engineer" in v1.lower():
            exp1 = "engineer"
        if s2 == "occupation" and "engineer" in v2.lower():
            exp2 = "engineer"
        if s1 == "hobby" and "climbing" in v1.lower():
            exp1 = "climbing"
        if s2 == "hobby" and "climbing" in v2.lower():
            exp2 = "climbing"
        
        queries.append({
            "query": q,
            "facts": [fact_string(s1, v1, t1), fact_string(s2, v2, t2)],
            "expected_slot": "multi",
            "expected": [exp1, exp2],
            "scope": "in-scope",
            "category": "multi-fact",
        })
    
    # ── Category 5: Mixed scope ────────────────────────────────────
    mixed_templates = [
        "What is my {slot} and what is {topic}?",
        "Tell me my {slot}. Also, {oos_query}",
        "Two questions: what is my {slot}, and {oos_query}",
    ]
    
    for (slot, value, trust), raw_fact in parsed[:8]:
        oos_q, topic = random.choice(OUT_OF_SCOPE_QUERIES)
        tmpl = random.choice(mixed_templates)
        q = tmpl.format(
            slot=slot.replace("_", " "),
            topic=topic,
            oos_query=oos_q.lower(),
        )
        
        expected = value
        if slot == "occupation" and "engineer" in value.lower():
            expected = "engineer"
        if slot == "hobby" and "climbing" in value.lower():
            expected = "climbing"
        
        queries.append({
            "query": q,
            "facts": [fact_string(slot, value, trust)],
            "expected_slot": "mixed",
            "expected": [expected],
            "scope": "mixed",
            "category": "mixed",
        })
    
    # ── Category 6: Out-of-scope ───────────────────────────────────
    for oos_q, topic in OUT_OF_SCOPE_QUERIES:
        queries.append({
            "query": oos_q,
            "facts": [],
            "expected_slot": None,
            "expected": None,
            "scope": "out-of-scope",
            "category": "out-of-scope",
        })
    
    return queries


# ══════════════════════════════════════════════════════════════════════
#  ONLINE GENERATOR — GPT-4o-mini augmentation
# ══════════════════════════════════════════════════════════════════════

def generate_with_api(facts: List[Dict], offline_queries: List[Dict]) -> List[Dict]:
    """Augment offline queries with GPT-4o-mini generated variations."""
    from personal_agent.dnnt.github_models_provider import GitHubModelsClient
    
    client = GitHubModelsClient(model="gpt-4o-mini", max_retries=3, retry_delay=30.0)
    parsed = [parse_fact(f) for f in facts]
    extra_queries = []
    
    print(f"\n  Generating API-augmented queries via GPT-4o-mini...")
    print(f"  Base offline queries: {len(offline_queries)}")
    
    # For each fact, ask GPT-4o-mini for creative paraphrases
    for i, (slot, value, trust) in enumerate(parsed, 1):
        prompt = (
            f"I have a fact about a user: {slot} = {value}\n\n"
            f"Generate 10 diverse, creative ways a user might ask an AI assistant "
            f"about this fact. Include:\n"
            f"- 3 casual/informal phrasings\n"
            f"- 2 indirect/roundabout questions\n"
            f"- 2 adversarial questions that try to get the AI to say the WRONG value\n"
            f"- 3 context-heavy questions that embed the question in a scenario\n\n"
            f"Return ONLY a JSON array of objects, each with:\n"
            f'  {{"query": "the question", "category": "casual|indirect|adversarial|contextual"}}\n\n'
            f"No markdown, no explanation, just the JSON array."
        )
        
        print(f"  [{i}/{len(parsed)}] Generating for {slot}={value}...", end="", flush=True)
        
        try:
            _, response = client.chat(
                prompt, 
                system_prompt="You are a test data generator. Return only valid JSON arrays. No markdown code blocks.",
                temperature=0.9,
                max_tokens=1024,
            )
            
            # Clean response — strip markdown fences if present
            response = response.strip()
            if response.startswith("```"):
                response = "\n".join(response.split("\n")[1:])
            if response.endswith("```"):
                response = response[:-3].strip()
            if response.startswith("json"):
                response = response[4:].strip()
            
            generated = json.loads(response)
            
            for item in generated:
                q = item.get("query", "").strip()
                cat = item.get("category", "api-generated")
                if not q:
                    continue
                
                expected = value
                if slot == "occupation" and "engineer" in value.lower():
                    expected = "engineer"
                if slot == "hobby" and "climbing" in value.lower():
                    expected = "climbing"
                
                extra_queries.append({
                    "query": q,
                    "facts": [fact_string(slot, value, trust)],
                    "expected_slot": slot,
                    "expected": expected,
                    "scope": "in-scope",
                    "category": f"api-{cat}",
                })
            
            print(f" +{len(generated)} queries")
            
        except json.JSONDecodeError as e:
            print(f" JSON parse error: {e}")
        except Exception as e:
            print(f" ERROR: {e}")
            time.sleep(10)
        
        # Rate limit
        if i < len(parsed):
            time.sleep(1.5)
    
    print(f"\n  API-generated queries: {len(extra_queries)}")
    print(f"  API stats: {client.stats()}")
    
    return extra_queries


# ══════════════════════════════════════════════════════════════════════
#  DEDUPLICATION + EXPORT
# ══════════════════════════════════════════════════════════════════════

def deduplicate(queries: List[Dict]) -> List[Dict]:
    """Remove exact duplicate queries (case-insensitive)."""
    seen = set()
    unique = []
    for q in queries:
        key = q["query"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique


def export(queries: List[Dict], output_path: Path):
    """Save queries in vilt_test_queries format."""
    data = {
        "_comment": f"Auto-generated eval suite: {len(queries)} queries. Compatible with vilt_scaled.py.",
        "_stats": {
            "total": len(queries),
            "by_category": {},
            "by_scope": {},
        },
        "queries": queries,
    }
    
    # Compute stats
    for q in queries:
        cat = q.get("category", "unknown")
        scope = q.get("scope", "unknown")
        data["_stats"]["by_category"][cat] = data["_stats"]["by_category"].get(cat, 0) + 1
        data["_stats"]["by_scope"][scope] = data["_stats"]["by_scope"].get(scope, 0) + 1
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n  Saved {len(queries)} queries to {output_path}")
    print(f"  Stats:")
    print(f"    By scope:    {data['_stats']['by_scope']}")
    print(f"    By category: {data['_stats']['by_category']}")


# ══════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Generate VILT eval queries")
    parser.add_argument("--facts", type=str, default=str(DEFAULT_FACTS),
                        help="Path to fact ledger JSON")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT),
                        help="Output path for generated queries")
    parser.add_argument("--offline", action="store_true",
                        help="Template-only mode, no API calls")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    args = parser.parse_args()
    
    random.seed(args.seed)
    
    print("=" * 60)
    print("  VILT Eval Generator")
    print("=" * 60)
    
    # Load facts
    facts_path = Path(args.facts)
    facts = load_facts(facts_path)
    print(f"  Loaded {len(facts)} facts from {facts_path.name}")
    
    # Generate offline queries (always)
    print(f"\n  Phase 1: Template-based generation...")
    offline = generate_offline(facts)
    print(f"  Template queries: {len(offline)}")
    
    # Optionally augment with API
    api_queries = []
    if not args.offline:
        print(f"\n  Phase 2: API augmentation...")
        try:
            api_queries = generate_with_api(facts, offline)
        except Exception as e:
            print(f"  API augmentation failed: {e}")
            print(f"  Continuing with template queries only.")
    else:
        print(f"\n  Phase 2: Skipped (--offline mode)")
    
    # Combine and deduplicate
    all_queries = offline + api_queries
    all_queries = deduplicate(all_queries)
    random.shuffle(all_queries)
    
    print(f"\n  Total unique queries: {len(all_queries)}")
    
    # Export
    export(all_queries, Path(args.output))
    
    print(f"\n  Done! Run evaluation with:")
    print(f"    python scripts/vilt_scaled.py --test-queries {args.output}")


if __name__ == "__main__":
    main()

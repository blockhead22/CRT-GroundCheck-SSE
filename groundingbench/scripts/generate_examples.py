"""Helper to generate examples using GPT-4."""
import json
import os
from typing import Dict
from openai import OpenAI

def generate_factual_example(fact_type: str, grounded: bool) -> Dict:
    """Generate factual grounding example."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    prompt = f"""Generate a grounding verification example:
    
Fact type: {fact_type}
Should be grounded: {grounded}

Format:
{{
  "query": "<user question>",
  "retrieved_context": [{{"id": "m1", "text": "<fact>", "trust": 0.9}}],
  "generated_output": "<LLM output>",
  "label": {{
    "grounded": {str(grounded).lower()},
    "hallucinations": [],
    "expected_correction": "<correct output>"
  }}
}}

Make it realistic. If not grounded, the generated_output should contain a plausible but wrong fact."""
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    
    return json.loads(response.choices[0].message.content)

def generate_contradiction_example(contradiction_type: str) -> Dict:
    """Generate contradiction example."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    prompt = f"""Generate a contradiction handling example:
    
Contradiction type: {contradiction_type}

Format:
{{
  "query": "<user question>",
  "retrieved_context": [
    {{"id": "m1", "text": "<first fact>", "trust": 0.8, "timestamp": 1704067200}},
    {{"id": "m2", "text": "<conflicting fact>", "trust": 0.9, "timestamp": 1706745600}}
  ],
  "generated_output": "<LLM output>",
  "label": {{
    "grounded": true,
    "hallucinations": [],
    "grounding_map": {{}},
    "requires_contradiction_disclosure": true,
    "expected_disclosure": "<output with acknowledgment>"
  }}
}}

Make it realistic with temporal or source-based contradictions."""
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    
    return json.loads(response.choices[0].message.content)

def generate_partial_example() -> Dict:
    """Generate partial grounding example."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    prompt = """Generate a partial grounding example where some claims are grounded and others are hallucinated:

Format:
{
  "query": "<user question>",
  "retrieved_context": [
    {"id": "m1", "text": "<fact 1>", "trust": 0.9},
    {"id": "m2", "text": "<fact 2>", "trust": 0.8}
  ],
  "generated_output": "<output with mix of grounded and hallucinated claims>",
  "label": {
    "grounded": false,
    "hallucinations": ["<hallucinated claim 1>", "<hallucinated claim 2>"],
    "grounding_map": {"<grounded claim>": "m1"},
    "expected_correction": "<corrected output>"
  }
}

Make it realistic with natural-sounding hallucinations."""
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    
    return json.loads(response.choices[0].message.content)

def generate_paraphrase_example(paraphrase_type: str) -> Dict:
    """Generate paraphrasing example."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    prompt = f"""Generate a paraphrasing example:

Paraphrase type: {paraphrase_type}

Format:
{{
  "query": "<user question>",
  "retrieved_context": [{{"id": "m1", "text": "<original phrasing>", "trust": 0.9}}],
  "generated_output": "<paraphrased version>",
  "label": {{
    "grounded": true,
    "hallucinations": [],
    "grounding_map": {{}},
    "paraphrase_type": "{paraphrase_type}"
  }}
}}

The generated_output should be semantically equivalent but differently phrased."""
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    
    return json.loads(response.choices[0].message.content)

def generate_multihop_example(reasoning_type: str) -> Dict:
    """Generate multi-hop reasoning example."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    prompt = f"""Generate a multi-hop reasoning example:

Reasoning type: {reasoning_type}

Format:
{{
  "query": "<user question>",
  "retrieved_context": [
    {{"id": "m1", "text": "<fact 1>", "trust": 0.9}},
    {{"id": "m2", "text": "<fact 2>", "trust": 0.95}}
  ],
  "generated_output": "<conclusion from combining facts>",
  "label": {{
    "grounded": true,
    "hallucinations": [],
    "grounding_map": {{}},
    "reasoning_chain": ["<step 1>", "<step 2>", "<conclusion>"]
  }}
}}

The output should require combining multiple facts to verify."""
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    
    return json.loads(response.choices[0].message.content)

# Example usage
if __name__ == "__main__":
    print("Example factual grounding (grounded):")
    print(json.dumps(generate_factual_example("employer", True), indent=2))
    
    print("\nExample factual grounding (hallucinated):")
    print(json.dumps(generate_factual_example("name", False), indent=2))
    
    print("\nNote: Set OPENAI_API_KEY environment variable to use this script")

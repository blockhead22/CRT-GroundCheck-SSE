"""Experiment B: CRT as the Model

Can a small model fine-tuned on trust-weighted personal conversation data
generate faithful responses from memory context alone?

Architecture:
  1. Extract (query, memory_context, response) triples from GPT logs
  2. Match responses to production memories for trust scores
  3. Fine-tune GPT-2 (124M) with trust-weighted cross-entropy loss
  4. Test: given query + memory context, does it prefer high-trust facts?

The trust weighting means: responses that align with high-trust memories
get MORE weight in the loss. Responses that repeat low-trust or corrected
facts get LESS weight. The model learns to prefer trusted knowledge.

Hardware: RTX 3060 12GB — GPT-2 small fits in ~3GB, leaves room for batches.

Run: python papers/belief_backpropagation/crt_model_experiment.py
"""

import sys
sys.path.insert(0, r"D:\AI_round2")

import json
import os
import time
import random
import sqlite3
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from transformers import GPT2LMHeadModel, GPT2Tokenizer, AdamW, get_linear_schedule_with_warmup

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Device: {DEVICE}")

# ===================================================================
# Step 1: Extract training data from GPT logs
# ===================================================================

def extract_conversation_pairs(max_pairs=5000):
    """Extract (user_message, assistant_response) pairs from GPT exports."""
    pairs = []
    for i in range(13):
        f = f"data/chatgpt_export/conversations-{i:03d}.json"
        if not os.path.exists(f):
            continue
        data = json.load(open(f, encoding="utf-8"))
        for conv in data:
            messages = []
            for node in conv.get("mapping", {}).values():
                msg = node.get("message")
                if not msg:
                    continue
                role = msg.get("author", {}).get("role", "")
                parts = msg.get("content", {}).get("parts", [])
                text = " ".join(str(p) for p in parts if isinstance(p, str)).strip()
                if text and len(text) > 10 and role in ("user", "assistant"):
                    messages.append((role, text))

            # Extract consecutive user->assistant pairs
            for j in range(len(messages) - 1):
                if messages[j][0] == "user" and messages[j+1][0] == "assistant":
                    user_text = messages[j][1][:500]
                    asst_text = messages[j+1][1][:500]
                    if len(user_text) > 15 and len(asst_text) > 15:
                        pairs.append((user_text, asst_text))
                        if len(pairs) >= max_pairs:
                            return pairs
    return pairs


# ===================================================================
# Step 2: Match to production memories for trust weighting
# ===================================================================

def load_memory_trust_map():
    """Load production memories and their trust scores."""
    db = r"D:\AI_round2\personal_agent\crt_memory_shared.db"
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT text, trust FROM memories WHERE deprecated=0 AND text IS NOT NULL"
    ).fetchall()
    conn.close()
    return {text[:200].lower(): trust for text, trust in rows}


def compute_pair_trust(user_text, asst_text, trust_map):
    """Estimate trust for a conversation pair by matching against memory."""
    asst_lower = asst_text[:200].lower()

    # Direct match
    if asst_lower in trust_map:
        return trust_map[asst_lower]

    # Fuzzy: check if any high-trust memory keywords appear in the response
    best_trust = 0.5  # default neutral
    for mem_text, trust in trust_map.items():
        # Simple word overlap
        mem_words = set(mem_text.split())
        asst_words = set(asst_lower.split())
        if len(mem_words) < 3:
            continue
        overlap = len(mem_words & asst_words) / max(len(mem_words), 1)
        if overlap > 0.4:
            best_trust = max(best_trust, trust)

    return best_trust


# ===================================================================
# Step 3: Dataset with trust weighting
# ===================================================================

class TrustWeightedDataset(Dataset):
    def __init__(self, pairs, trust_scores, tokenizer, max_len=256):
        self.examples = []
        self.weights = []

        for (user, asst), trust in zip(pairs, trust_scores):
            # Format: "User: {query}\nAssistant: {response}"
            text = f"User: {user}\nAssistant: {asst}"
            encoded = tokenizer.encode(text, truncation=True, max_length=max_len)
            if len(encoded) > 20:
                self.examples.append(torch.tensor(encoded, dtype=torch.long))
                self.weights.append(trust)

        print(f"  Dataset: {len(self.examples)} examples")
        print(f"  Trust range: [{min(self.weights):.3f}, {max(self.weights):.3f}]")
        print(f"  Mean trust: {np.mean(self.weights):.3f}")

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        return self.examples[idx], self.weights[idx]


def collate_fn(batch):
    tokens, weights = zip(*batch)
    # Pad to same length
    max_len = max(t.size(0) for t in tokens)
    padded = torch.zeros(len(tokens), max_len, dtype=torch.long)
    masks = torch.zeros(len(tokens), max_len, dtype=torch.float)
    for i, t in enumerate(tokens):
        padded[i, :t.size(0)] = t
        masks[i, :t.size(0)] = 1.0
    return padded, masks, torch.tensor(weights, dtype=torch.float)


# ===================================================================
# Step 4: Train with trust-weighted loss
# ===================================================================

def train_model(model, tokenizer, dataset, epochs=2, batch_size=4, lr=5e-5):
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, collate_fn=collate_fn)
    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = len(loader) * epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=100, num_training_steps=total_steps)

    model.train()
    for epoch in range(epochs):
        total_loss = 0
        n_batches = 0
        t0 = time.time()

        for batch_tokens, batch_masks, batch_trusts in loader:
            batch_tokens = batch_tokens.to(DEVICE)
            batch_masks = batch_masks.to(DEVICE)
            batch_trusts = batch_trusts.to(DEVICE)

            # Standard causal LM: predict next token
            outputs = model(batch_tokens, attention_mask=batch_masks)
            logits = outputs.logits[:, :-1, :].contiguous()
            targets = batch_tokens[:, 1:].contiguous()
            target_mask = batch_masks[:, 1:].contiguous()

            # Per-token cross-entropy
            loss_per_token = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                targets.view(-1),
                reduction='none'
            ).view(targets.size())

            # Apply mask
            loss_per_token = loss_per_token * target_mask

            # Trust-weighted: multiply per-example loss by trust score
            # High trust = full weight. Low trust = reduced weight.
            # This makes the model learn MORE from high-trust examples
            per_example_loss = loss_per_token.sum(dim=1) / (target_mask.sum(dim=1) + 1e-8)
            weighted_loss = (per_example_loss * batch_trusts).mean()

            optimizer.zero_grad()
            weighted_loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()

            total_loss += weighted_loss.item()
            n_batches += 1

            if n_batches % 100 == 0:
                print(f"    Epoch {epoch+1}, batch {n_batches}/{len(loader)}, loss={total_loss/n_batches:.4f}")

        elapsed = time.time() - t0
        print(f"  Epoch {epoch+1}: avg_loss={total_loss/n_batches:.4f}, time={elapsed:.0f}s")

    return model


# ===================================================================
# Step 5: Test — generate from memory context
# ===================================================================

def generate_response(model, tokenizer, prompt, max_new_tokens=60):
    model.eval()
    input_ids = tokenizer.encode(prompt, return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        output = model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            temperature=0.7,
            do_sample=True,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
        )
    text = tokenizer.decode(output[0], skip_special_tokens=True)
    return text[len(tokenizer.decode(input_ids[0], skip_special_tokens=True)):].strip()


TEST_SCENARIOS = [
    {
        "name": "Employment",
        "context": "The user is a freelance developer. The user does web development and photography. The user left their previous job a year ago.",
        "query": "What does the user do for work?",
    },
    {
        "name": "Favorite color",
        "context": "The user's favorite color is orange. Orange has personal significance. The user has confirmed this multiple times.",
        "query": "What is the user's favorite color?",
    },
    {
        "name": "Health",
        "context": "The user has a chronic health condition. The condition makes overnight work difficult. The user left their overnight job because of health.",
        "query": "Why did the user leave their job?",
    },
    {
        "name": "Name",
        "context": "The user's name is Nick. The user has confirmed this many times.",
        "query": "What is the user's name?",
    },
    {
        "name": "Project",
        "context": "The user is building an AI system called Aether. The user has been working on it for over a year. It involves memory architecture and belief tracking.",
        "query": "What is the user building?",
    },
]


def run_tests(model, tokenizer, label):
    print(f"\n  --- {label} ---")
    for sc in TEST_SCENARIOS:
        prompt = f"Context: {sc['context']}\n\nUser: {sc['query']}\nAssistant:"
        response = generate_response(model, tokenizer, prompt)
        print(f"  [{sc['name']}] {response[:150]}")


# ===================================================================
# Main
# ===================================================================

def main():
    print("=" * 70)
    print("EXPERIMENT B: CRT as the Model")
    print("Trust-weighted fine-tuning on personal conversation data")
    print("=" * 70)

    # Load tokenizer and model
    print("\nStep 1: Loading GPT-2...")
    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
    tokenizer.pad_token = tokenizer.eos_token

    # Baseline model (unfrozen copy)
    base_model = GPT2LMHeadModel.from_pretrained("gpt2").to(DEVICE)

    print("\nStep 2: Extracting conversation pairs...")
    pairs = extract_conversation_pairs(max_pairs=3000)
    print(f"  Extracted {len(pairs)} pairs")

    print("\nStep 3: Computing trust weights...")
    trust_map = load_memory_trust_map()
    print(f"  {len(trust_map)} memories loaded")

    trust_scores = [compute_pair_trust(u, a, trust_map) for u, a in pairs]
    print(f"  Trust distribution: mean={np.mean(trust_scores):.3f}, std={np.std(trust_scores):.3f}")

    # Test baseline BEFORE training
    print("\nStep 4: Baseline (before training)...")
    run_tests(base_model, tokenizer, "Pre-training baseline")

    # Create datasets
    # A: Trust-weighted (high trust = more weight)
    print("\nStep 5: Training trust-weighted model...")
    trust_model = GPT2LMHeadModel.from_pretrained("gpt2").to(DEVICE)
    trust_dataset = TrustWeightedDataset(pairs, trust_scores, tokenizer, max_len=256)
    trust_model = train_model(trust_model, tokenizer, trust_dataset, epochs=2, batch_size=4)

    # B: Flat-weighted (all examples equal) for comparison
    print("\nStep 6: Training flat-weighted model (control)...")
    flat_model = GPT2LMHeadModel.from_pretrained("gpt2").to(DEVICE)
    flat_scores = [1.0] * len(pairs)  # equal weight for all
    flat_dataset = TrustWeightedDataset(pairs, flat_scores, tokenizer, max_len=256)
    flat_model = train_model(flat_model, tokenizer, flat_dataset, epochs=2, batch_size=4)

    # Test both
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    run_tests(base_model, tokenizer, "Pre-training (GPT-2 base)")
    run_tests(flat_model, tokenizer, "Flat-weighted fine-tune (no trust)")
    run_tests(trust_model, tokenizer, "Trust-weighted fine-tune (CRT)")

    print("\n" + "=" * 70)
    print("Compare the three columns above.")
    print("Signal = trust-weighted model produces more faithful, grounded answers")
    print("than flat-weighted model on the same training data.")
    print("=" * 70)


if __name__ == "__main__":
    main()

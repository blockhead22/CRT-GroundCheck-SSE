"""Prepare trust-weighted training data for Modal upload.

Runs locally. Builds the belief-grounded dataset from:
  - Production memories with trust scores
  - GPT conversation pairs (trust-filtered)
  - Correction pairs
  - Fact assertions

Outputs: data/crt_training_data.json

Run: python papers/belief_backpropagation/modal_prep_data.py
"""

import sys
sys.path.insert(0, r"D:\AI_round2")

import json
import os
import random
import sqlite3
import numpy as np

random.seed(42)


def load_memories():
    db = r"D:\AI_round2\personal_agent\crt_memory_shared.db"
    conn = sqlite3.connect(db)
    rows = conn.execute("""
        SELECT text, trust, kind, contradiction_count, access_count
        FROM memories WHERE deprecated=0 AND text IS NOT NULL AND length(text) > 20
    """).fetchall()
    conn.close()
    return [{"text": t, "trust": tr, "kind": k, "contras": c, "access": a}
            for t, tr, k, c, a in rows]


def load_conversations(max_pairs=20000):
    pairs = []
    for i in range(13):
        f = f"data/chatgpt_export/conversations-{i:03d}.json"
        if not os.path.exists(f):
            continue
        try:
            data = json.load(open(f, encoding="utf-8"))
        except:
            continue
        for conv in data:
            msgs = []
            for node in conv.get("mapping", {}).values():
                msg = node.get("message")
                if not msg:
                    continue
                role = msg.get("author", {}).get("role", "")
                parts = msg.get("content", {}).get("parts", [])
                text = " ".join(str(p) for p in parts if isinstance(p, str)).strip()
                if text and len(text) > 15 and role in ("user", "assistant"):
                    msgs.append((role, text[:500]))
            for j in range(len(msgs) - 1):
                if msgs[j][0] == "user" and msgs[j+1][0] == "assistant":
                    pairs.append({"user": msgs[j][1], "assistant": msgs[j+1][1]})
                    if len(pairs) >= max_pairs:
                        return pairs
    return pairs


def build_dataset(memories, conv_pairs):
    examples = []

    # Type 1: Fact assertions
    for mem in memories:
        if mem["trust"] < 0.3:
            continue
        text = f"<|user|>\nWhat do you know about this topic?<|end|>\n<|assistant|>\nBased on stored memories (trust {mem['trust']:.2f}): {mem['text']}<|end|>"
        examples.append({"text": text, "trust": mem["trust"]})

    # Type 2: Q&A
    qa_templates = {
        "user_fact": ["What do you know about me?", "Tell me what you remember.", "What facts do you have stored?"],
        "observation": ["What have you observed?", "What do you recall?", "What patterns have you noticed?"],
    }
    for mem in memories:
        if mem["trust"] < 0.2:
            continue
        kind = mem["kind"] or "observation"
        templates = qa_templates.get(kind, qa_templates["observation"])
        q = random.choice(templates)
        text = f"<|user|>\n{q}<|end|>\n<|assistant|>\n{mem['text']}<|end|>"
        examples.append({"text": text, "trust": mem["trust"]})

    # Type 3: Trust-filtered conversations
    mem_words = {}
    for mem in memories:
        words = set(mem["text"][:200].lower().split())
        if len(words) >= 3:
            mem_words[mem["text"][:100]] = (words, mem["trust"])

    for pair in conv_pairs:
        asst_words = set(pair["assistant"][:200].lower().split())
        best_trust = 0.4
        for _, (mw, mt) in mem_words.items():
            overlap = len(mw & asst_words) / max(len(mw), 1)
            if overlap > 0.3:
                best_trust = max(best_trust, mt)
        if best_trust >= 0.5 or random.random() < 0.15:
            text = f"<|user|>\n{pair['user']}<|end|>\n<|assistant|>\n{pair['assistant']}<|end|>"
            examples.append({"text": text, "trust": best_trust})

    # Type 4: Corrections
    contradicted = [m for m in memories if m["contras"] > 0]
    for mem in contradicted:
        text = f"<|user|>\nIs this true: {mem['text']}<|end|>\n<|assistant|>\nThat information has been corrected. Its trust score is {mem['trust']:.2f}, which is low. I would not rely on this without verification.<|end|>"
        examples.append({"text": text, "trust": 0.8})

    # Trust-weighted oversampling
    weighted = []
    for ex in examples:
        t = ex["trust"]
        if t >= 0.8:
            weighted.extend([ex] * 4)
        elif t >= 0.6:
            weighted.extend([ex] * 2)
        elif t >= 0.4:
            weighted.append(ex)
        else:
            if random.random() < 0.2:
                weighted.append(ex)

    random.shuffle(weighted)
    return weighted


def main():
    print("Loading production memories...")
    memories = load_memories()
    print(f"  {len(memories)} memories")

    print("Loading conversation pairs...")
    conv_pairs = load_conversations(max_pairs=20000)
    print(f"  {len(conv_pairs)} pairs")

    print("Building belief-grounded dataset...")
    dataset = build_dataset(memories, conv_pairs)
    print(f"  {len(dataset)} training examples")
    print(f"  Trust mean: {np.mean([e['trust'] for e in dataset]):.3f}")

    output = r"D:\AI_round2\data\crt_training_data.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False)

    size_mb = os.path.getsize(output) / (1024 * 1024)
    print(f"\nSaved: {output} ({size_mb:.1f} MB)")
    print(f"Ready for: modal run papers/belief_backpropagation/modal_train.py")


if __name__ == "__main__":
    main()

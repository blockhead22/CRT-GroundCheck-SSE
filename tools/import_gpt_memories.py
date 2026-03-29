"""
Bulk import curated GPT-sourced memories into Aether's shared memory.

Trust: 0.70 (GPT-sourced, curated by Nick, not directly asserted in Aether)
Authority: confirmed (Nick approved the import)
Source: external
Kind: user_fact / preference / narrative_note (per entry)
"""

import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from personal_agent.embeddings import encode_text

DB_PATH = str(PROJECT_ROOT / "personal_agent" / "crt_memory_shared.db")
TRUST = 0.70
CONFIDENCE = 0.85
SOURCE = "external"
AUTHORITY = "confirmed"
CHANNEL = "system"
ORIGIN = "gpt_corpus_import"
SSE_MODE = "L"
EXTRACTION_METHOD = "none"
TEMPORAL_STATUS = "active"
BELNAP_STATE = "true"
COMPRESSION_TIER = 2
SIGMA_SCALE = 0.25  # moderate uncertainty

# ── Curated facts ─────────────────────────────────────────────
# Each entry: (text, kind, memory_type, domain_tags)

MEMORIES = [
    # === Tier 1: Core Identity ===
    (
        "Nick was diagnosed with Acute Lymphoblastic Leukemia (ALL), Philadelphia chromosome positive (PH+), at age 27 in 2021. He received an allogeneic bone marrow transplant from a non-sibling donor.",
        "user_fact", "fact", ["health", "biography"],
    ),
    (
        "Nick has chronic Graft vs Host Disease (cGVHD) from his bone marrow transplant. It causes pain, muscle cramping, trigger finger, burning tension, and body stiffness. He uses cannabis partly for pain management.",
        "user_fact", "fact", ["health"],
    ),
    (
        "The night Nick was diagnosed with leukemia, two hours after his parents left the ICU, he made three promises to himself. These promises became his core philosophy and motivation — they are foundational to everything he does.",
        "narrative_note", "identity", ["biography", "values"],
    ),
    (
        "Nick lives in Sussex, Wisconsin, near Waukesha and Milwaukee. He currently lives at home with his parents.",
        "user_fact", "fact", ["location", "biography"],
    ),
    (
        "Nick was born around 1994 and is currently about 31 years old.",
        "user_fact", "fact", ["biography"],
    ),
    (
        "Nick's cat is named Olive. He got her about 4 years ago. She was his recovery buddy during cancer treatment.",
        "user_fact", "fact", ["pets", "biography"],
    ),
    (
        "Nick has a sister he is close with. His parents are supportive but sometimes skeptical of his tech projects. His dad understood the compression tech implications. The family also has a Great Dane.",
        "user_fact", "fact", ["family", "biography"],
    ),

    # === Tier 2: Professional Identity ===
    (
        "Nick describes himself as a full stack developer, graphic designer, amateur photographer and cinematographer, and freelance web developer. He is an all-around creative type.",
        "user_fact", "fact", ["professional", "identity"],
    ),
    (
        "Nick has an Associate's degree in Web Application Development. It took him 7 years to complete a 2-year degree. He received his diploma the same year he was diagnosed with cancer — he was fighting for his life in the hospital when he got his degree.",
        "user_fact", "fact", ["education", "biography"],
    ),
    (
        "Nick works (or recently worked) as a third shift stocker at Walmart. His cGVHD makes the overnight shifts increasingly difficult. He has been planning to quit and transition to self-employment.",
        "user_fact", "fact", ["employment"],
    ),
    (
        "The Printing Lair (theprintinglair.com) is Nick's sticker and vinyl cutting side business. It operates under Nick Block Designs LLC. His first profitable month was about $300 in income.",
        "user_fact", "fact", ["business", "printing"],
    ),
    (
        "Nick Block Designs LLC is Nick's business entity. The Printing Lair is a DBA under it. He is also planning an AI company called Aeteros (aeteros.ai).",
        "user_fact", "fact", ["business"],
    ),
    (
        "Nick experiences imposter syndrome about his programming abilities. He freezes when asked programming questions due to anxiety and struggles explaining technical concepts, despite being genuinely skilled.",
        "observation", "belief", ["personality", "professional"],
    ),

    # === Tier 3: Creative & Gear ===
    (
        "Nick's camera kit: Sony FX3 (cinema rig with mattebox and rails), Sony A7C II, Sony A6000 (shutter died). Film cameras: Minolta (learning film photography). Gimbal: DJI RS Ronin Pro 3 with Raven Eye. Lenses: 35mm, 50mm, 28-70mm, 70-200mm Sony.",
        "user_fact", "fact", ["photography", "gear"],
    ),
    (
        "Nick's filmmaking style: 'I like slow intentional. If movement needs to be induced it serves a purpose.' He dislikes performative filmmaking. He aspires to nature/hiking cinematography and documentary work.",
        "preference", "preference", ["filmmaking", "creative"],
    ),
    (
        "Coldplay has deep personal significance for Nick. 'Charlie Brown' by Coldplay is his anthem since high school — he first heard it on Pandora in graphic arts class. He deeply identifies with Charlie Brown / the 'Blockhead' identity.",
        "narrative_note", "identity", ["music", "identity", "biography"],
    ),
    (
        "Nick's favorite color is orange.",
        "user_fact", "fact", ["preferences"],
    ),

    # === Tier 4: Goals & Values ===
    (
        "Nick's dreams include: owning a Beechcraft Bonanza V-tail airplane, seeing the Northern Lights in the Arctic Circle, returning to Yosemite, building Aeteros into a real AI company, and potentially leaving Wisconsin.",
        "user_fact", "fact", ["goals", "dreams"],
    ),
    (
        "Nick's first trip to Yosemite was transformative. He has a documentary planned about it, documented at nickblock.dev/journal/gallery/yosemite.",
        "narrative_note", "event", ["yosemite", "filmmaking", "biography"],
    ),
    (
        "Nick's core philosophy connects death, rebirth, growth, and change. He believes in human-made over AI-generated creative work. His motto regarding AI/tech: 'Play the game or get played.'",
        "observation", "belief", ["values", "philosophy"],
    ),
    (
        "Nick weighed 440 lbs when he was diagnosed with leukemia. He has undergone a significant weight transformation since then.",
        "user_fact", "fact", ["health", "biography"],
    ),

    # === Tier 5: Social Context ===
    (
        "Nick is single. He prefers a 'slow burn' in dating. He hasn't been intimate in about 5 years. He is self-conscious about living at home but self-aware about not being ready for anything serious.",
        "user_fact", "fact", ["dating", "personal"],
    ),
    (
        "Nick's friends include: Blake (beer sign show deal), Brad Herda (FocalPoint Coaching, gave pivotal encouragement), Nettcod (works at Milwaukee Tool). He has a private Discord server for friends and Aether testing.",
        "user_fact", "fact", ["social", "friends"],
    ),
    (
        "Nick is a self-described spiraler who loves diving into ideas and theories. He is a glutton for validation, self-deprecating but persistent, and codes late at night. He acknowledges patterns of overcommitting then backing out.",
        "observation", "identity", ["personality"],
    ),
    (
        "Nick's online handle is 'Blockhead', a reference to Charlie Brown. His first email was blockheadsquare2@aol.com. His personal website is nickblock.dev.",
        "user_fact", "fact", ["identity", "online"],
    ),
    (
        "Nick frequents the Steaming Cup coffee shop in downtown Waukesha, Wisconsin.",
        "user_fact", "fact", ["location", "habits"],
    ),
    (
        "Lumi was Nick's original chatbot project, the precursor to Aether. It used Mistral and a DNT (Dynamic Neural Transformer) architecture. CRT evolved from this work.",
        "user_fact", "fact", ["projects", "history"],
    ),
    (
        "Nick was receiving about $800/month in SSA disability payments. He took graphic arts classes in high school and created atthecontrol.com about 12 years ago as a personal creative project.",
        "user_fact", "fact", ["biography", "history"],
    ),
]


def generate_memory_id() -> str:
    ts_ms = int(time.time() * 1000)
    rand = uuid.uuid4().int % 10000
    return f"mem_{ts_ms}_{rand}"


def main():
    print(f"Importing {len(MEMORIES)} curated GPT memories into {DB_PATH}")
    print(f"Trust: {TRUST}, Authority: {AUTHORITY}, Source: {SOURCE}")
    print()

    conn = sqlite3.connect(DB_PATH)

    # Check for duplicates by loading existing memory texts
    existing = set()
    try:
        rows = conn.execute("SELECT text FROM memories WHERE deprecated = 0").fetchall()
        for (t,) in rows:
            existing.add(t.strip().lower()[:100])
    except Exception:
        pass

    now = time.time()
    sigma = np.full(384, SIGMA_SCALE, dtype=np.float32).tobytes()

    inserted = 0
    skipped = 0

    for text, kind, memory_type, domain_tags in MEMORIES:
        # Simple dedup check
        if text.strip().lower()[:100] in existing:
            print(f"  [SKIP] Already exists: {text[:60]}...")
            skipped += 1
            continue

        # Compute embedding
        try:
            vector = encode_text(text)
            vector_json = json.dumps(vector.tolist() if hasattr(vector, 'tolist') else list(vector))
        except Exception as e:
            print(f"  [ERROR] Embedding failed for: {text[:60]}... ({e})")
            continue

        memory_id = generate_memory_id()
        context = {
            "import_source": "gpt_corpus",
            "curated": True,
            "import_timestamp": now,
        }

        conn.execute(
            """INSERT INTO memories (
                memory_id, vector_json, text, timestamp, confidence, trust,
                source, sse_mode, context_json, thread_id, deprecated,
                extraction_method, temporal_status, domain_tags, authority,
                channel, origin, kind, source_kind, compression_tier,
                sigma, belnap_state, memory_type, stable_cycles,
                contradiction_count, access_count
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?
            )""",
            (
                memory_id, vector_json, text, now, CONFIDENCE, TRUST,
                SOURCE, SSE_MODE, json.dumps(context), None, 0,
                EXTRACTION_METHOD, TEMPORAL_STATUS, json.dumps(domain_tags), AUTHORITY,
                CHANNEL, ORIGIN, kind, "external", COMPRESSION_TIER,
                sigma, BELNAP_STATE, memory_type, 0,
                0, 0,
            ),
        )

        inserted += 1
        print(f"  [OK] {memory_id}: {text[:70]}...")

        # Small delay to ensure unique memory IDs
        time.sleep(0.002)

    conn.commit()
    conn.close()

    print()
    print(f"Done: {inserted} inserted, {skipped} skipped (duplicates)")
    print(f"Total memories now available for retrieval.")


if __name__ == "__main__":
    main()

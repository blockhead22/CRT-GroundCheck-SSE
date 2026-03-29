"""ChatGPT Export Parser — index conversations for research + selective memory ingest.

Parses the OpenAI data export (conversations-*.json) into a flat, searchable
corpus. Extracts user messages, assistant responses, titles, timestamps.
Optionally extracts facts for selective ingestion into Aether's memory.

Usage:
    python -m tools.chatgpt_corpus parse          # Build corpus index
    python -m tools.chatgpt_corpus stats          # Show corpus stats
    python -m tools.chatgpt_corpus search <query> # Semantic search
    python -m tools.chatgpt_corpus extract-facts   # Extract candidate facts
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

EXPORT_DIR = Path("data/chatgpt_export")
CORPUS_DB = Path("data/chatgpt_corpus.db")


def _init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            conv_id TEXT PRIMARY KEY,
            title TEXT,
            create_time REAL,
            update_time REAL,
            model_slug TEXT,
            message_count INTEGER,
            user_message_count INTEGER,
            is_archived INTEGER DEFAULT 0,
            source_file TEXT
        );

        CREATE TABLE IF NOT EXISTS messages (
            msg_id TEXT PRIMARY KEY,
            conv_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            create_time REAL,
            content_type TEXT,
            model_slug TEXT,
            char_count INTEGER,
            FOREIGN KEY (conv_id) REFERENCES conversations(conv_id)
        );

        CREATE TABLE IF NOT EXISTS candidate_facts (
            fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_id TEXT,
            conv_id TEXT,
            text TEXT NOT NULL,
            kind TEXT,
            confidence REAL,
            ingested INTEGER DEFAULT 0,
            ingested_memory_id TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conv_id);
        CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
        CREATE INDEX IF NOT EXISTS idx_facts_ingested ON candidate_facts(ingested);
    """)
    conn.commit()
    return conn


def parse_export(export_dir: Path = EXPORT_DIR, db_path: Path = CORPUS_DB) -> Dict[str, int]:
    """Parse all conversations-*.json files into the corpus database."""
    conn = _init_db(db_path)

    files = sorted(f for f in os.listdir(export_dir) if f.startswith("conversations-") and f.endswith(".json"))
    if not files:
        return {"error": "No conversations-*.json files found", "path": str(export_dir)}

    total_convos = 0
    total_msgs = 0
    total_user_msgs = 0

    for fn in files:
        filepath = export_dir / fn
        log.info("Parsing %s...", fn)
        with open(filepath, "r", encoding="utf-8") as f:
            conversations = json.load(f)

        for conv in conversations:
            conv_id = conv.get("id") or conv.get("conversation_id", "")
            title = conv.get("title", "")
            create_time = conv.get("create_time")
            update_time = conv.get("update_time")
            model_slug = conv.get("default_model_slug", "")
            is_archived = 1 if conv.get("is_archived") else 0
            mapping = conv.get("mapping", {})

            msg_count = 0
            user_msg_count = 0

            for node_id, node in mapping.items():
                msg = node.get("message")
                if not msg:
                    continue

                role = msg.get("author", {}).get("role", "unknown")
                content_obj = msg.get("content", {})
                content_type = content_obj.get("content_type", "text")
                parts = content_obj.get("parts", [])

                # Extract text content
                text_parts = []
                for p in parts:
                    if isinstance(p, str):
                        text_parts.append(p)
                    elif isinstance(p, dict) and p.get("text"):
                        text_parts.append(p["text"])
                content = "\n".join(text_parts).strip()

                if not content:
                    continue

                msg_id = msg.get("id", node_id)
                msg_time = msg.get("create_time")
                msg_model = msg.get("metadata", {}).get("model_slug", "")

                conn.execute(
                    """INSERT OR IGNORE INTO messages
                       (msg_id, conv_id, role, content, create_time, content_type, model_slug, char_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (msg_id, conv_id, role, content, msg_time, content_type, msg_model, len(content)),
                )

                msg_count += 1
                total_msgs += 1
                if role == "user":
                    user_msg_count += 1
                    total_user_msgs += 1

            conn.execute(
                """INSERT OR REPLACE INTO conversations
                   (conv_id, title, create_time, update_time, model_slug, message_count, user_message_count, is_archived, source_file)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (conv_id, title, create_time, update_time, model_slug, msg_count, user_msg_count, is_archived, fn),
            )
            total_convos += 1

        conn.commit()
        log.info("  %s: done", fn)

    conn.close()

    result = {
        "conversations": total_convos,
        "messages": total_msgs,
        "user_messages": total_user_msgs,
        "files_parsed": len(files),
        "db_path": str(db_path),
    }
    log.info("Parse complete: %s", result)
    return result


def get_stats(db_path: Path = CORPUS_DB) -> Dict[str, Any]:
    """Return corpus statistics."""
    conn = sqlite3.connect(str(db_path))

    total_convos = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    total_msgs = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    user_msgs = conn.execute("SELECT COUNT(*) FROM messages WHERE role='user'").fetchone()[0]
    assistant_msgs = conn.execute("SELECT COUNT(*) FROM messages WHERE role='assistant'").fetchone()[0]
    total_chars = conn.execute("SELECT SUM(char_count) FROM messages").fetchone()[0] or 0

    # Time range
    earliest = conn.execute("SELECT MIN(create_time) FROM conversations WHERE create_time IS NOT NULL").fetchone()[0]
    latest = conn.execute("SELECT MAX(update_time) FROM conversations WHERE update_time IS NOT NULL").fetchone()[0]

    # Top models
    models = conn.execute(
        "SELECT model_slug, COUNT(*) as cnt FROM messages WHERE model_slug != '' GROUP BY model_slug ORDER BY cnt DESC LIMIT 5"
    ).fetchall()

    # Longest conversations
    longest = conn.execute(
        "SELECT title, message_count FROM conversations ORDER BY message_count DESC LIMIT 5"
    ).fetchall()

    # Candidate facts
    try:
        facts_total = conn.execute("SELECT COUNT(*) FROM candidate_facts").fetchone()[0]
        facts_ingested = conn.execute("SELECT COUNT(*) FROM candidate_facts WHERE ingested=1").fetchone()[0]
    except Exception:
        facts_total = facts_ingested = 0

    conn.close()

    return {
        "conversations": total_convos,
        "messages": total_msgs,
        "user_messages": user_msgs,
        "assistant_messages": assistant_msgs,
        "total_chars": total_chars,
        "total_mb": round(total_chars / 1_000_000, 1),
        "earliest": time.strftime("%Y-%m-%d", time.localtime(earliest)) if earliest else None,
        "latest": time.strftime("%Y-%m-%d", time.localtime(latest)) if latest else None,
        "top_models": [(r[0], r[1]) for r in models],
        "longest_conversations": [(r[0], r[1]) for r in longest],
        "candidate_facts": facts_total,
        "ingested_facts": facts_ingested,
    }


def search_corpus(query: str, limit: int = 20, role: str = "user", db_path: Path = CORPUS_DB) -> List[Dict]:
    """Simple text search across the corpus. For semantic search, use embeddings."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # SQLite LIKE search (case-insensitive)
    pattern = f"%{query}%"
    rows = conn.execute(
        """SELECT m.msg_id, m.conv_id, m.role, m.content, m.create_time, m.char_count,
                  c.title as conv_title
           FROM messages m
           JOIN conversations c ON m.conv_id = c.conv_id
           WHERE m.content LIKE ? AND m.role = ?
           ORDER BY m.create_time DESC
           LIMIT ?""",
        (pattern, role, limit),
    ).fetchall()
    conn.close()

    return [
        {
            "msg_id": r["msg_id"],
            "conv_id": r["conv_id"],
            "conv_title": r["conv_title"],
            "role": r["role"],
            "content": r["content"][:500],
            "create_time": r["create_time"],
            "char_count": r["char_count"],
        }
        for r in rows
    ]


def main():
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if len(sys.argv) < 2:
        print("Usage: python -m tools.chatgpt_corpus <parse|stats|search>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "parse":
        result = parse_export()
        print(json.dumps(result, indent=2))

    elif cmd == "stats":
        stats = get_stats()
        print(json.dumps(stats, indent=2, default=str))

    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: python -m tools.chatgpt_corpus search <query>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        results = search_corpus(query)
        for r in results:
            ts = time.strftime("%Y-%m-%d", time.localtime(r["create_time"])) if r["create_time"] else "?"
            print(f"[{ts}] {r['conv_title']}")
            print(f"  {r['content'][:200]}")
            print()

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()

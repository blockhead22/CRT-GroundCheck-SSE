"""
GPT Log Store — Full semantic search over ChatGPT export data.

Separate from CRT memory: this is a reference store, not a belief store.
Aether can search it, read full conversations, and optionally promote
individual messages into CRT memories.

Storage: SQLite + HNSW index (hnswlib) for fast approximate nearest neighbor.
Embeddings: same all-MiniLM-L6-v2 (384 dims) as CRT.
"""

import json
import logging
import os
import sqlite3
import struct
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import hnswlib
import numpy as np

logger = logging.getLogger(__name__)

EMBED_DIM = 384
HNSW_EF_CONSTRUCTION = 200
HNSW_M = 16
HNSW_EF_SEARCH = 100

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GPTMessage:
    msg_id: str
    conv_id: str
    role: str  # user | assistant | system | tool
    text: str
    timestamp: float
    model: str = ""
    token_est: int = 0

@dataclass
class GPTConversation:
    conv_id: str
    title: str
    model: str
    create_time: float
    update_time: float
    message_count: int = 0

@dataclass
class SearchResult:
    msg_id: str
    conv_id: str
    conv_title: str
    role: str
    text: str
    timestamp: float
    score: float
    model: str = ""


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class GPTLogStore:
    """Full-text and semantic search over ChatGPT export data."""

    def __init__(self, db_path: str = "data/gpt_logs.db", index_path: str = "data/gpt_logs.hnsw"):
        self.db_path = db_path
        self.index_path = index_path
        self._encoder = None
        self._index: Optional[hnswlib.Index] = None
        self._id_map: dict[int, str] = {}  # hnsw int id -> msg_id
        self._msg_id_to_int: dict[str, int] = {}  # msg_id -> hnsw int id
        self._next_int_id = 0
        self._init_db()
        self._load_index()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                conv_id TEXT PRIMARY KEY,
                title TEXT,
                model TEXT,
                create_time REAL,
                update_time REAL,
                message_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS messages (
                msg_id TEXT PRIMARY KEY,
                conv_id TEXT NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp REAL,
                model TEXT,
                token_est INTEGER DEFAULT 0,
                has_vector INTEGER DEFAULT 0,
                FOREIGN KEY (conv_id) REFERENCES conversations(conv_id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conv_id);
            CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
            CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(timestamp);

            CREATE TABLE IF NOT EXISTS id_map (
                int_id INTEGER PRIMARY KEY,
                msg_id TEXT NOT NULL UNIQUE
            );
        """)
        conn.commit()
        conn.close()

    @property
    def encoder(self):
        if self._encoder is None:
            from personal_agent.embeddings import get_encoder
            self._encoder = get_encoder()
        return self._encoder

    # -----------------------------------------------------------------------
    # HNSW index management
    # -----------------------------------------------------------------------

    def _load_index(self):
        """Load HNSW index and id_map from disk if they exist."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        rows = conn.execute("SELECT int_id, msg_id FROM id_map ORDER BY int_id").fetchall()
        conn.close()

        if rows:
            for int_id, msg_id in rows:
                self._id_map[int_id] = msg_id
                self._msg_id_to_int[msg_id] = int_id
            self._next_int_id = max(self._id_map.keys()) + 1

        if os.path.exists(self.index_path) and self._id_map:
            self._index = hnswlib.Index(space="cosine", dim=EMBED_DIM)
            self._index.load_index(self.index_path, max_elements=len(self._id_map) + 100000)
            self._index.set_ef(HNSW_EF_SEARCH)
            logger.info(f"[GPT-LOGS] Loaded HNSW index with {len(self._id_map)} vectors")
        else:
            self._index = None

    def _save_index(self):
        """Persist HNSW index and id_map to disk."""
        if self._index is not None:
            self._index.save_index(self.index_path)
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("DELETE FROM id_map")
        conn.executemany(
            "INSERT INTO id_map (int_id, msg_id) VALUES (?, ?)",
            list(self._id_map.items()),
        )
        conn.commit()
        conn.close()

    def _ensure_index(self, max_elements: int):
        """Create index if it doesn't exist."""
        if self._index is None:
            self._index = hnswlib.Index(space="cosine", dim=EMBED_DIM)
            self._index.init_index(
                max_elements=max_elements,
                ef_construction=HNSW_EF_CONSTRUCTION,
                M=HNSW_M,
            )
            self._index.set_ef(HNSW_EF_SEARCH)

    # -----------------------------------------------------------------------
    # Ingestion
    # -----------------------------------------------------------------------

    def ingest_export(self, export_dir: str, batch_size: int = 512) -> dict:
        """
        Parse all conversations-*.json from a ChatGPT export directory.
        Embeds messages and builds HNSW index.

        Returns stats dict.
        """
        export_path = Path(export_dir)
        conv_files = sorted(export_path.glob("conversations-*.json"))
        if not conv_files:
            raise FileNotFoundError(f"No conversations-*.json found in {export_dir}")

        stats = {"files": 0, "conversations": 0, "messages": 0, "embedded": 0, "skipped": 0}
        all_texts = []
        all_msg_ids = []

        conn = sqlite3.connect(self.db_path, timeout=60)
        conn.execute("PRAGMA journal_mode=WAL")

        for conv_file in conv_files:
            logger.info(f"[GPT-LOGS] Parsing {conv_file.name}...")
            stats["files"] += 1

            data = json.loads(conv_file.read_text(encoding="utf-8"))

            for conv in data:
                conv_id = conv.get("id") or conv.get("conversation_id") or str(uuid.uuid4())
                title = conv.get("title", "Untitled")
                model = conv.get("default_model_slug", "")
                create_time = conv.get("create_time", 0) or 0
                update_time = conv.get("update_time", 0) or 0

                # Extract messages from mapping
                mapping = conv.get("mapping", {})
                messages = []
                for node_id, node in mapping.items():
                    msg = node.get("message")
                    if not msg:
                        continue
                    author = msg.get("author", {})
                    role = author.get("role", "unknown")
                    content = msg.get("content", {})
                    parts = content.get("parts", [])

                    # Join text parts (skip dicts which are tool calls/results)
                    text_parts = [p for p in parts if isinstance(p, str)]
                    text = "\n".join(text_parts).strip()

                    if not text or len(text) < 5:
                        continue

                    msg_ts = msg.get("create_time") or create_time
                    msg_model = msg.get("metadata", {}).get("model_slug", model)
                    msg_id = msg.get("id") or node_id

                    messages.append(GPTMessage(
                        msg_id=msg_id,
                        conv_id=conv_id,
                        role=role,
                        text=text,
                        timestamp=msg_ts or 0,
                        model=msg_model or "",
                        token_est=len(text) // 4,
                    ))

                if not messages:
                    continue

                stats["conversations"] += 1

                # Upsert conversation
                conn.execute(
                    """INSERT OR REPLACE INTO conversations
                       (conv_id, title, model, create_time, update_time, message_count)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (conv_id, title, model, create_time, update_time, len(messages)),
                )

                # Upsert messages
                for m in messages:
                    # Check if already embedded
                    existing = conn.execute(
                        "SELECT has_vector FROM messages WHERE msg_id = ?", (m.msg_id,)
                    ).fetchone()

                    if existing and existing[0]:
                        stats["skipped"] += 1
                        continue

                    conn.execute(
                        """INSERT OR REPLACE INTO messages
                           (msg_id, conv_id, role, text, timestamp, model, token_est, has_vector)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                        (m.msg_id, m.conv_id, m.role, m.text, m.timestamp, m.model, m.token_est),
                    )
                    stats["messages"] += 1

                    # Queue for embedding (truncate very long messages)
                    embed_text = m.text[:2000]  # MiniLM context is 256 tokens, ~1K chars effective
                    # Prefix with role for better retrieval
                    if m.role == "user":
                        embed_text = f"User asked: {embed_text}"
                    elif m.role == "assistant":
                        embed_text = f"Assistant answered: {embed_text}"
                    all_texts.append(embed_text)
                    all_msg_ids.append(m.msg_id)

            conn.commit()

        # Now embed in batches
        if all_texts:
            total = len(all_texts)
            logger.info(f"[GPT-LOGS] Embedding {total} messages...")
            self._ensure_index(max_elements=total + 50000)

            for i in range(0, total, batch_size):
                batch_texts = all_texts[i : i + batch_size]
                batch_ids = all_msg_ids[i : i + batch_size]

                vectors = self.encoder.encode_batch(batch_texts)

                int_ids = []
                for msg_id in batch_ids:
                    int_id = self._next_int_id
                    self._id_map[int_id] = msg_id
                    self._msg_id_to_int[msg_id] = int_id
                    int_ids.append(int_id)
                    self._next_int_id += 1

                self._index.add_items(vectors, np.array(int_ids))

                # Mark as embedded in DB
                conn = sqlite3.connect(self.db_path, timeout=60)
                conn.executemany(
                    "UPDATE messages SET has_vector = 1 WHERE msg_id = ?",
                    [(mid,) for mid in batch_ids],
                )
                # Store id_map entries
                conn.executemany(
                    "INSERT OR REPLACE INTO id_map (int_id, msg_id) VALUES (?, ?)",
                    list(zip(int_ids, batch_ids)),
                )
                conn.commit()
                conn.close()

                stats["embedded"] += len(batch_texts)
                done = min(i + batch_size, total)
                if done % 5000 < batch_size:
                    logger.info(f"[GPT-LOGS] Embedded {done}/{total} ({done * 100 // total}%)")

            self._save_index()

        logger.info(f"[GPT-LOGS] Ingestion complete: {stats}")
        return stats

    # -----------------------------------------------------------------------
    # Search
    # -----------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 20,
        role_filter: Optional[str] = None,
        date_after: Optional[float] = None,
        date_before: Optional[float] = None,
        model_filter: Optional[str] = None,
    ) -> list[SearchResult]:
        """Semantic search over GPT logs."""
        if self._index is None or len(self._id_map) == 0:
            return []

        # Embed query
        qvec = self.encoder.encode(query).reshape(1, -1).astype(np.float32)

        # Over-fetch to allow post-filtering
        fetch_k = min(top_k * 5, len(self._id_map))
        labels, distances = self._index.knn_query(qvec, k=fetch_k)

        conn = sqlite3.connect(self.db_path, timeout=30)
        results = []

        for int_id, dist in zip(labels[0], distances[0]):
            if len(results) >= top_k:
                break

            msg_id = self._id_map.get(int(int_id))
            if not msg_id:
                continue

            # cosine distance -> similarity
            score = 1.0 - float(dist)

            row = conn.execute(
                """SELECT m.msg_id, m.conv_id, m.role, m.text, m.timestamp, m.model,
                          c.title
                   FROM messages m
                   JOIN conversations c ON m.conv_id = c.conv_id
                   WHERE m.msg_id = ?""",
                (msg_id,),
            ).fetchone()

            if not row:
                continue

            mid, cid, role, text, ts, model, title = row

            # Apply filters
            if role_filter and role != role_filter:
                continue
            if date_after and (ts or 0) < date_after:
                continue
            if date_before and (ts or 0) > date_before:
                continue
            if model_filter and model_filter not in (model or ""):
                continue

            results.append(SearchResult(
                msg_id=mid,
                conv_id=cid,
                conv_title=title or "Untitled",
                role=role,
                text=text,
                timestamp=ts or 0,
                score=score,
                model=model or "",
            ))

        conn.close()
        return results

    # -----------------------------------------------------------------------
    # Conversation retrieval
    # -----------------------------------------------------------------------

    def get_conversation(self, conv_id: str) -> tuple[Optional[GPTConversation], list[GPTMessage]]:
        """Get a full conversation with all messages in order."""
        conn = sqlite3.connect(self.db_path, timeout=30)

        crow = conn.execute(
            "SELECT conv_id, title, model, create_time, update_time, message_count FROM conversations WHERE conv_id = ?",
            (conv_id,),
        ).fetchone()
        if not crow:
            conn.close()
            return None, []

        conv = GPTConversation(*crow)

        rows = conn.execute(
            "SELECT msg_id, conv_id, role, text, timestamp, model, token_est FROM messages WHERE conv_id = ? ORDER BY timestamp",
            (conv_id,),
        ).fetchall()
        conn.close()

        messages = [GPTMessage(*r) for r in rows]
        return conv, messages

    def get_message_context(self, msg_id: str, window: int = 3) -> list[GPTMessage]:
        """Get a message and its surrounding context (window messages before/after)."""
        conn = sqlite3.connect(self.db_path, timeout=30)

        # Get the message's conversation and timestamp
        row = conn.execute(
            "SELECT conv_id, timestamp FROM messages WHERE msg_id = ?", (msg_id,)
        ).fetchone()
        if not row:
            conn.close()
            return []

        conv_id, ts = row

        # Get all messages in that conversation ordered by time
        rows = conn.execute(
            "SELECT msg_id, conv_id, role, text, timestamp, model, token_est FROM messages WHERE conv_id = ? ORDER BY timestamp",
            (conv_id,),
        ).fetchall()
        conn.close()

        messages = [GPTMessage(*r) for r in rows]

        # Find the index of our message
        idx = next((i for i, m in enumerate(messages) if m.msg_id == msg_id), None)
        if idx is None:
            return messages  # fallback: return all

        start = max(0, idx - window)
        end = min(len(messages), idx + window + 1)
        return messages[start:end]

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    def stats(self) -> dict:
        """Return store statistics."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conv_count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        embedded_count = conn.execute("SELECT COUNT(*) FROM messages WHERE has_vector = 1").fetchone()[0]
        role_counts = dict(conn.execute("SELECT role, COUNT(*) FROM messages GROUP BY role").fetchall())
        conn.close()

        index_count = len(self._id_map) if self._id_map else 0

        return {
            "conversations": conv_count,
            "messages": msg_count,
            "embedded": embedded_count,
            "index_size": index_count,
            "roles": role_counts,
        }

    # -----------------------------------------------------------------------
    # Promote to CRT
    # -----------------------------------------------------------------------

    def promote_to_crt(self, msg_id: str, engine, thread_id: str = "default", user_id: str = "nick") -> Optional[str]:
        """
        Promote a GPT log message into a CRT memory.
        Creates a low-trust EXTERNAL memory with provenance.

        Args:
            msg_id: The GPT log message ID to promote
            engine: CRT engine instance (has ingest_memory_write)
            thread_id: CRT thread to store in
            user_id: User ID

        Returns:
            CRT memory_id if successful, None otherwise
        """
        conn = sqlite3.connect(self.db_path, timeout=30)
        row = conn.execute(
            """SELECT m.msg_id, m.conv_id, m.role, m.text, m.timestamp, m.model, c.title
               FROM messages m JOIN conversations c ON m.conv_id = c.conv_id
               WHERE m.msg_id = ?""",
            (msg_id,),
        ).fetchone()
        conn.close()

        if not row:
            return None

        mid, cid, role, text, ts, model, title = row

        from personal_agent.crt_rag import MemorySource

        # Construct provenance-rich text
        import datetime
        dt = datetime.datetime.fromtimestamp(ts) if ts else None
        date_str = dt.strftime("%Y-%m-%d %H:%M") if dt else "unknown date"

        promoted_text = f"[GPT Log | {role} | {date_str} | conv: {title}]\n{text}"

        memory_id = engine.ingest_memory_write(
            text=promoted_text,
            confidence=0.50,  # Low — this is external reference, not user-stated
            source=MemorySource.EXTERNAL,
            context={
                "thread_id": thread_id,
                "gpt_msg_id": mid,
                "gpt_conv_id": cid,
                "gpt_conv_title": title,
                "gpt_role": role,
                "gpt_model": model or "unknown",
                "gpt_timestamp": ts,
                "promoted_from": "gpt_log_store",
            },
            user_marked_important=False,
            contradiction_signal=0.0,
            thread_id=thread_id,
            authority="provisional",  # Not confirmed — came from GPT
            channel="gpt_log_promotion",
            origin=f"gpt:{cid}:{mid}",
            kind="observation",
            source_kind="external",
            model_id=model or "gpt-unknown",
            run_id=None,
            user_id=user_id,
        )

        logger.info(f"[GPT-LOGS] Promoted msg {mid} -> CRT memory {memory_id}")
        return memory_id

    # -----------------------------------------------------------------------
    # Full-text search (fallback when index not built)
    # -----------------------------------------------------------------------

    def text_search(self, query: str, top_k: int = 20, role_filter: Optional[str] = None) -> list[SearchResult]:
        """Simple LIKE-based text search as fallback."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        sql = """
            SELECT m.msg_id, m.conv_id, m.role, m.text, m.timestamp, m.model, c.title
            FROM messages m
            JOIN conversations c ON m.conv_id = c.conv_id
            WHERE m.text LIKE ?
        """
        params = [f"%{query}%"]

        if role_filter:
            sql += " AND m.role = ?"
            params.append(role_filter)

        sql += " ORDER BY m.timestamp DESC LIMIT ?"
        params.append(top_k)

        rows = conn.execute(sql, params).fetchall()
        conn.close()

        return [
            SearchResult(
                msg_id=r[0], conv_id=r[1], conv_title=r[6] or "Untitled",
                role=r[2], text=r[3], timestamp=r[4] or 0,
                score=1.0, model=r[5] or "",
            )
            for r in rows
        ]

    # -----------------------------------------------------------------------
    # List conversations
    # -----------------------------------------------------------------------

    def list_conversations(
        self, limit: int = 50, offset: int = 0, search_title: Optional[str] = None
    ) -> list[GPTConversation]:
        """List conversations, optionally filtered by title."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        if search_title:
            rows = conn.execute(
                "SELECT conv_id, title, model, create_time, update_time, message_count FROM conversations WHERE title LIKE ? ORDER BY update_time DESC LIMIT ? OFFSET ?",
                (f"%{search_title}%", limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT conv_id, title, model, create_time, update_time, message_count FROM conversations ORDER BY update_time DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        conn.close()
        return [GPTConversation(*r) for r in rows]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_store: Optional[GPTLogStore] = None


def get_gpt_log_store(db_path: str = "data/gpt_logs.db", index_path: str = "data/gpt_logs.hnsw") -> GPTLogStore:
    """Get or create the global GPT log store."""
    global _store
    if _store is None:
        _store = GPTLogStore(db_path=db_path, index_path=index_path)
    return _store

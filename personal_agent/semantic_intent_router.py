"""
Semantic Intent Router — Embedding-based intent classification.

Uses the same all-MiniLM-L6-v2 model (384 dims) already loaded for memory
to do semantic similarity classification against prototype phrases.

Sprint 7: Replaces fragile regex routing with semantic understanding.
Runs alongside regex during transition (hybrid mode).
"""

import logging
import time
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("crt.intent_router")

# ---------------------------------------------------------------------------
# Intent Prototypes — seed phrases per intent type
# ---------------------------------------------------------------------------

INTENT_PROTOTYPES: Dict[str, List[str]] = {
    "system_info": [
        "how's my system",
        "what's my cpu usage",
        "system status",
        "what am I running",
        "check my specs",
        "how much ram am I using",
        "what's happening on my machine",
        "is my gpu being used",
        "what processes are running",
        "disk space check",
        "check my system",
        "how's my computer doing",
        "what's my system status",
    ],
    "file_read": [
        "read file",
        "show me the contents of",
        "what's in this file",
        "open the config",
        "cat the readme",
        "read package.json",
        "show me src/App.tsx",
        "display the log file",
        "what does this file say",
    ],
    "file_write": [
        "create a file",
        "write to file",
        "generate a file",
        "make an html page",
        "edit the config",
        "update the readme",
        "save this to a file",
        "create an index.html with",
        "modify the css",
        "write a python script that",
        "create a file called",
        "make a new file",
        "write a new file",
    ],
    "dir_list": [
        "list directory",
        "what's in this folder",
        "show me the files in",
        "ls the project",
        "what files are here",
        "list the contents of",
        "show directory tree",
    ],
    "project_scan": [
        "git status",
        "check my repo",
        "project status",
        "any uncommitted changes",
        "what branch am I on",
        "show recent commits",
        "scan my project",
        "what's the state of the repo",
        "any untracked files",
        "check the project files",
    ],
    "shell_exec": [
        "run command",
        "execute in terminal",
        "npm install",
        "pip install",
        "run the build",
        "start the server",
        "run python script",
        "execute this command",
        "run in the shell",
    ],
    "git_action": [
        "git commit",
        "git push",
        "commit my changes",
        "push to main",
        "create a branch",
        "checkout develop",
        "merge the branch",
        "git pull origin main",
    ],
    "skill_install": [
        "add skill from",
        "install skill",
        "register a new service",
        "connect to this service",
        "add tool from url",
        "install plugin from",
    ],
    "service_action": [
        "check moltbook",
        "what's new on moltbook",
        "query moltbook",
        "search moltbook",
        "post to moltbook",
        "update moltbook",
        "send to the service",
    ],
    "create_commitment": [
        "remind me to",
        "set a reminder",
        "every day at",
        "don't let me forget",
        "schedule a reminder",
        "alert me at",
        "notify me when",
        "remind me tonight",
        "remind me tomorrow",
        "ping me later about",
        "nudge me about",
        "let me know when",
    ],
    "list_commitments": [
        "what are my reminders",
        "show my commitments",
        "what's scheduled",
        "list my reminders",
        "any upcoming reminders",
        "what reminders do I have",
    ],
    "cancel_commitment": [
        "cancel the reminder",
        "stop reminding me",
        "remove the reminder",
        "delete that reminder",
        "clear my reminders",
        "get rid of that alarm",
        "kill that reminder",
        "turn off the alert",
    ],
    "broad_recall": [
        "what do you know about me",
        "tell me everything you remember",
        "what have I told you",
        "summarize what you know",
        "what do you remember",
    ],
    "self_referential": [
        "how do you work",
        "explain your architecture",
        "what are you",
        "who built you",
        "how does your memory work",
        "tell me about yourself",
    ],
    "url_fetch": [
        "go to this url",
        "fetch this page",
        "check this website",
        "open this link",
        "scrape this url",
        "what's at this address",
    ],
    "desktop_action": [
        "open notepad",
        "open chrome for me",
        "can you open notepad",
        "launch firefox",
        "open up vs code",
        "start spotify",
        "open file explorer",
        "open the calculator",
        "click on that button",
        "close the window",
        "switch to chrome",
        "minimize this window",
        "take a screenshot of my desktop",
        "open my downloads folder",
        "open discord",
        "can you open notpad for me",
        "please open the settings app",
        "scroll down on the page",
        "type hello in the search bar",
        "right click on the desktop",
        "press enter",
        "alt tab to the next window",
        "go back in the browser",
        "open steam",
        "search for weather in google",
    ],
    "conversational": [
        "hello",
        "how are you",
        "what do you think about",
        "tell me about",
        "I'm feeling",
        "thanks",
        "that's interesting",
        "what's your opinion on",
        "good morning",
        "hey there",
        "cool",
        "nice",
    ],
}


# ---------------------------------------------------------------------------
# IntentScore dataclass
# ---------------------------------------------------------------------------

@dataclass
class IntentScore:
    """A scored intent classification result."""
    intent_type: str
    confidence: float

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.75

    @property
    def is_ambiguous(self) -> bool:
        return 0.45 <= self.confidence < 0.75


# ---------------------------------------------------------------------------
# Cosine similarity helper
# ---------------------------------------------------------------------------

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


# ---------------------------------------------------------------------------
# Embedding serialization helpers
# ---------------------------------------------------------------------------

def _embed_to_bytes(vec: np.ndarray) -> bytes:
    return vec.astype(np.float32).tobytes()


def _bytes_to_embed(raw: bytes) -> np.ndarray:
    return np.frombuffer(raw, dtype=np.float32).copy()


# ---------------------------------------------------------------------------
# SemanticIntentRouter — core semantic classifier
# ---------------------------------------------------------------------------

class SemanticIntentRouter:
    """
    Semantic intent classification using embedding similarity.

    Compares user messages against precomputed intent prototype
    embeddings to determine the most likely intent(s).
    """

    def __init__(self, embedding_engine):
        """
        Args:
            embedding_engine: An EmbeddingEngine instance (from personal_agent.embeddings).
                              Must have .encode(text) and .encode_batch(texts) methods.
        """
        self.engine = embedding_engine
        self.prototype_embeddings: Dict[str, np.ndarray] = {}     # centroid per intent
        self._individual_embeddings: Dict[str, np.ndarray] = {}   # all phrase embeddings per intent
        self._custom_prototypes: Dict[str, List[str]] = {}        # user-added phrases
        self._corrections_db_path: Optional[str] = None
        self._precompute_prototypes()

    def _precompute_prototypes(self):
        """Embed all prototype phrases and store mean embedding per intent."""
        t0 = time.time()
        total_phrases = 0

        for intent_type, phrases in INTENT_PROTOTYPES.items():
            all_phrases = phrases + self._custom_prototypes.get(intent_type, [])
            embeddings = self.engine.encode_batch(all_phrases)
            self.prototype_embeddings[intent_type] = np.mean(embeddings, axis=0)
            self._individual_embeddings[intent_type] = embeddings
            total_phrases += len(all_phrases)

        elapsed = time.time() - t0
        logger.info(
            f"[INTENT_ROUTER] Precomputed {total_phrases} prototype embeddings "
            f"across {len(INTENT_PROTOTYPES)} intents in {elapsed:.2f}s"
        )

    def classify(
        self,
        message: str,
        attached_paths: Optional[List[str]] = None,
    ) -> List[IntentScore]:
        """
        Returns ranked list of IntentScore sorted by confidence descending.
        Can return multiple intents for multi-intent messages.
        """
        if not message or not message.strip():
            return [IntentScore("conversational", 0.5)]

        # 1. Embed the user message
        msg_embedding = self.engine.encode(message)

        # 2. Compute cosine similarity against each intent centroid
        scores: Dict[str, float] = {}
        for intent_type, centroid in self.prototype_embeddings.items():
            scores[intent_type] = cosine_similarity(msg_embedding, centroid)

        # 3. Also check max similarity against individual prototypes
        for intent_type, embeddings in self._individual_embeddings.items():
            # Batch dot product (embeddings are already normalized by EmbeddingEngine)
            sims = embeddings @ msg_embedding
            max_individual = float(np.max(sims))
            # Use the higher of centroid vs best-individual (slight discount on individual)
            scores[intent_type] = max(scores[intent_type], max_individual * 0.95)

        # 4. Apply contextual boosts
        if attached_paths:
            for intent in ["file_read", "file_write", "dir_list", "project_scan"]:
                if intent in scores:
                    scores[intent] = min(1.0, scores[intent] + 0.15)

        # 5. Apply learned corrections
        if self._corrections_db_path:
            scores = self._apply_learned_corrections(msg_embedding, scores)

        # 6. Rank and filter
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        threshold = 0.45
        results = [IntentScore(intent, conf) for intent, conf in ranked if conf >= threshold]

        if not results:
            # Nothing above threshold — fall back to conversational with the
            # best score we saw (clamped to at least 0.3 so downstream knows
            # this was a weak match).
            best = ranked[0] if ranked else ("conversational", 0.3)
            results = [IntentScore("conversational", max(0.3, best[1]))]

        return results

    def detect_multi_intent(self, scores: List[IntentScore]) -> List[IntentScore]:
        """
        If top 2+ intents are close in confidence, return all of them.
        E.g. 'check my system and read the config' -> [system_info, file_read]
        """
        if len(scores) < 2:
            return scores[:1]

        top = scores[0]
        multi = [top]

        for score in scores[1:]:
            if top.confidence - score.confidence < 0.15 and score.confidence >= 0.55:
                multi.append(score)
            else:
                break

        return multi

    def handle_ambiguity(self, scores: List[IntentScore], message: str) -> Dict[str, Any]:
        """Determine action based on confidence levels."""
        if not scores:
            return {"action": "conversational", "reason": "No scores available"}

        top = scores[0]

        if top.is_high_confidence:
            return {"action": "execute", "intent": top}

        if top.is_ambiguous:
            options = [f"{s.intent_type} ({s.confidence:.0%})" for s in scores[:3]]
            return {
                "action": "clarify",
                "message": f"I'm not sure what you'd like me to do. Did you mean: {', '.join(options)}?",
                "candidates": scores[:3],
            }

        return {
            "action": "conversational",
            "reason": f"No tool intent matched above threshold (best: {top.intent_type} at {top.confidence:.0%})",
        }

    # ------------------------------------------------------------------
    # Correction learning
    # ------------------------------------------------------------------

    def init_corrections_db(self, db_path: str):
        """Initialize the intent corrections database."""
        self._corrections_db_path = db_path
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS intent_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_text TEXT NOT NULL,
                message_embedding BLOB,
                classified_as TEXT NOT NULL,
                corrected_to TEXT NOT NULL,
                correction_source TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        conn.commit()
        conn.close()
        logger.info(f"[INTENT_ROUTER] Corrections DB initialized at {db_path}")

    def record_correction(
        self,
        message: str,
        classified_as: str,
        corrected_to: str,
        source: str = "user_disambiguate",
    ):
        """Record an intent correction for future learning."""
        if not self._corrections_db_path:
            return
        embedding = self.engine.encode(message)
        conn = sqlite3.connect(self._corrections_db_path)
        conn.execute(
            "INSERT INTO intent_corrections "
            "(message_text, message_embedding, classified_as, corrected_to, correction_source, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (message, _embed_to_bytes(embedding), classified_as, corrected_to, source, time.time()),
        )
        conn.commit()
        conn.close()
        logger.info(
            f"[INTENT_ROUTER] Correction: '{message[:40]}' {classified_as} -> {corrected_to} ({source})"
        )

    def _apply_learned_corrections(
        self, msg_embedding: np.ndarray, scores: Dict[str, float]
    ) -> Dict[str, float]:
        """Adjust scores based on similar past corrections."""
        if not self._corrections_db_path:
            return scores
        try:
            conn = sqlite3.connect(self._corrections_db_path)
            rows = conn.execute(
                "SELECT message_embedding, classified_as, corrected_to "
                "FROM intent_corrections ORDER BY timestamp DESC LIMIT 100"
            ).fetchall()
            conn.close()
        except Exception:
            return scores

        for emb_bytes, classified_as, corrected_to in rows:
            if not emb_bytes:
                continue
            correction_emb = _bytes_to_embed(emb_bytes)
            sim = cosine_similarity(msg_embedding, correction_emb)
            if sim > 0.85:
                if corrected_to in scores:
                    scores[corrected_to] = min(1.0, scores[corrected_to] + 0.2 * sim)
                if classified_as in scores:
                    scores[classified_as] = max(0.0, scores[classified_as] - 0.15 * sim)

        return scores

    def load_recent_corrections(self, limit: int = 100) -> List[Dict]:
        """Load recent corrections from DB."""
        if not self._corrections_db_path:
            return []
        conn = sqlite3.connect(self._corrections_db_path)
        rows = conn.execute(
            "SELECT message_text, classified_as, corrected_to, correction_source, timestamp "
            "FROM intent_corrections ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            {"message": r[0], "classified_as": r[1], "corrected_to": r[2], "source": r[3], "timestamp": r[4]}
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Prototype management
    # ------------------------------------------------------------------

    def add_prototype(self, intent_type: str, phrase: str) -> bool:
        """Add a custom prototype phrase and recompute that intent's embeddings."""
        if intent_type not in INTENT_PROTOTYPES:
            return False

        if intent_type not in self._custom_prototypes:
            self._custom_prototypes[intent_type] = []
        self._custom_prototypes[intent_type].append(phrase)

        # Recompute just this intent's embeddings
        all_phrases = INTENT_PROTOTYPES[intent_type] + self._custom_prototypes[intent_type]
        embeddings = self.engine.encode_batch(all_phrases)
        self.prototype_embeddings[intent_type] = np.mean(embeddings, axis=0)
        self._individual_embeddings[intent_type] = embeddings
        logger.info(f"[INTENT_ROUTER] Added prototype: '{phrase}' -> {intent_type} ({len(all_phrases)} total)")
        return True

    def remove_prototype(self, intent_type: str, phrase_index: int) -> bool:
        """Remove a prototype phrase by index (only custom prototypes can be removed)."""
        custom = self._custom_prototypes.get(intent_type, [])
        base_count = len(INTENT_PROTOTYPES.get(intent_type, []))
        custom_index = phrase_index - base_count
        if custom_index < 0 or custom_index >= len(custom):
            return False
        custom.pop(custom_index)
        all_phrases = INTENT_PROTOTYPES.get(intent_type, []) + custom
        if all_phrases:
            embeddings = self.engine.encode_batch(all_phrases)
            self.prototype_embeddings[intent_type] = np.mean(embeddings, axis=0)
            self._individual_embeddings[intent_type] = embeddings
        return True

    def get_prototypes(self) -> Dict[str, Dict]:
        """Get all prototypes with counts."""
        result = {}
        for intent_type, phrases in INTENT_PROTOTYPES.items():
            custom = self._custom_prototypes.get(intent_type, [])
            result[intent_type] = {
                "base_phrases": phrases,
                "custom_phrases": custom,
                "total_count": len(phrases) + len(custom),
            }
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get classification stats."""
        stats = {
            "intent_count": len(INTENT_PROTOTYPES),
            "total_prototypes": sum(len(p) for p in INTENT_PROTOTYPES.values()),
            "custom_prototypes": sum(len(p) for p in self._custom_prototypes.values()),
        }
        if self._corrections_db_path:
            try:
                conn = sqlite3.connect(self._corrections_db_path)
                stats["total_corrections"] = conn.execute(
                    "SELECT COUNT(*) FROM intent_corrections"
                ).fetchone()[0]
                conn.close()
            except Exception:
                stats["total_corrections"] = 0
        return stats


# ---------------------------------------------------------------------------
# Heartbeat self-improvement: review corrections
# ---------------------------------------------------------------------------

def review_corrections(db_path: str, router: SemanticIntentRouter) -> List[Tuple[str, str]]:
    """
    Review recent corrections. Auto-add prototypes for messages
    corrected 3+ times to the same intent.
    """
    if not db_path:
        return []
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute("""
            SELECT corrected_to, message_text, COUNT(*) as cnt
            FROM intent_corrections
            WHERE correction_source IN ('user_disambiguate', 'user_override')
            GROUP BY corrected_to, message_text
            HAVING cnt >= 3
            ORDER BY cnt DESC LIMIT 10
        """).fetchall()
        conn.close()
    except Exception:
        return []

    added = []
    for corrected_to, message_text, count in rows:
        existing = INTENT_PROTOTYPES.get(corrected_to, [])
        custom = router._custom_prototypes.get(corrected_to, [])
        if message_text not in existing and message_text not in custom:
            router.add_prototype(corrected_to, message_text)
            added.append((corrected_to, message_text))
            logger.info(
                f"[INTENT_ROUTER] Auto-added prototype: '{message_text}' -> {corrected_to} "
                f"(corrected {count}x)"
            )
    return added

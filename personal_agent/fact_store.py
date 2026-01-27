"""
Structured Fact Store for CRT
Simple slot-based memory with real contradiction detection.

Production extension points marked with # PROD:
"""

import re
import sqlite3
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from enum import Enum


class FactSource(Enum):
    USER_STATED = "user_stated"
    USER_CORRECTED = "user_corrected"
    INFERRED = "inferred"  # PROD: Add inference engine
    EXTERNAL = "external"  # PROD: Add external source integration


@dataclass
class Fact:
    slot: str
    value: str
    trust: float
    source: FactSource
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return {
            "slot": self.slot,
            "value": self.value,
            "trust": self.trust,
            "source": self.source.value,
            "timestamp": self.timestamp
        }


class FactExtractor:
    """
    Extract structured facts from natural language.
    
    PROD: Replace regex with LLM-based extraction for better coverage
    PROD: Add entity recognition for names, places, etc.
    """
    
    # Common words that are NOT names
    NOT_NAMES = {
        'feeling', 'doing', 'going', 'getting', 'being', 'having', 'making',
        'tired', 'happy', 'sad', 'hungry', 'thirsty', 'sick', 'fine', 'good', 'bad', 'great',
        'here', 'there', 'back', 'home', 'away', 'ready', 'done', 'sorry', 'sure',
        'just', 'really', 'actually', 'also', 'still', 'already', 'always', 'never',
        'wondering', 'thinking', 'looking', 'trying', 'working', 'living',
        'a', 'an', 'the', 'not', 'so', 'very', 'too', 'now', 'then',
    }
    
    # Colors for validation
    COLORS = {
        'red', 'blue', 'green', 'yellow', 'orange', 'purple', 'pink', 'black', 'white',
        'brown', 'gray', 'grey', 'gold', 'silver', 'teal', 'cyan', 'magenta', 'violet',
        'indigo', 'turquoise', 'maroon', 'navy', 'olive', 'coral', 'salmon', 'crimson',
    }
    
    # Slot patterns - more conservative
    PATTERNS = {
        "user.name": [
            # Explicit name statements only
            r"(?:my name is|call me|i'm called|you can call me)\s+([A-Za-z]+)",
            r"(?:^|[.!?]\s+)(?:i am|i'm)\s+([A-Z][a-z]+)(?:[.!?]?\s*$)",  # "I'm Nick." at end
        ],
        "user.favorite_color": [
            # "my favorite color is orange because..." - captures 'orange'
            r"(?:my )?(?:fav(?:ou?rite)?|preferred)\s+colou?r\s+(?:is\s+)?([a-z]+)(?:\s|\.|,|!|$|\s+because)",
            r"colou?r\s+is\s+([a-z]+)(?:\s|\.|,|!|$|\s+because)",
            r"(?:i (?:like|love|prefer))\s+([a-z]+)\\s+(?:the\s+)?(?:most|best|colou?r)",
        ],
        "user.favorite_color_reason": [
            # Extract the reason for favorite color
            r"(?:fav(?:ou?rite)?|preferred)\s+colou?r.*?because\s+(?:of\s+)?(.+?)(?:\.|!|$)",
        ],
        "user.occupation": [
            # Must have explicit job/work context
            r"(?:i work as|i work at|my job is|i am a|i'm a)\s+([^.!?,]+?)(?:[.!?,]|$)",
            r"(?:i'm|i am)\s+(?:a|an)\s+((?:web\s+)?(?:developer|engineer|designer|manager|teacher|doctor|nurse|lawyer|analyst|consultant|freelancer)[a-z\s]*)",
        ],
        "user.location": [
            r"(?:i live in|i'm from|i am from|i'm based in)\s+([^.!?,]+?)(?:[.!?,]|$)",
        ],
    }
    
    CORRECTION_SIGNALS = [
        r"^(?:no|nope|actually|wait|wrong)",
        r"(?:not|isn't|isnt)\s+\w+[,.]?\s+(?:it's|its|i'm|im)\s+",
    ]
    
    def extract(self, text: str) -> List[Fact]:
        """Extract facts from user input."""
        text_clean = text.strip()
        text_lower = text_clean.lower()
        facts = []
        is_correction = self._is_correction(text_lower)
        
        # Skip emotional/casual statements
        if self._is_casual_statement(text_lower):
            return facts
        
        for slot, patterns in self.PATTERNS.items():
            for pattern in patterns:
                # Search in lowercase for pattern matching
                match = re.search(pattern, text_lower, re.IGNORECASE)
                if match:
                    # But extract value from ORIGINAL text to preserve case
                    # Find the same position in original text
                    orig_match = re.search(pattern, text_clean, re.IGNORECASE)
                    if orig_match:
                        value = orig_match.group(1).strip()
                    else:
                        value = match.group(1).strip()
                    
                    # Validate based on slot type
                    if not self._validate_value(slot, value):
                        continue
                    
                    # Title case for names
                    if "name" in slot:
                        value = value.title()
                    
                    if len(value) > 1:
                        facts.append(Fact(
                            slot=slot,
                            value=value,
                            trust=0.98 if is_correction else 0.95,
                            source=FactSource.USER_CORRECTED if is_correction else FactSource.USER_STATED
                        ))
                        break  # One fact per slot per input
        
        return facts
    
    def _validate_value(self, slot: str, value: str) -> bool:
        """Validate extracted value for a slot."""
        value_lower = value.lower()
        
        if "name" in slot:
            # Names must be capitalized words, not common words
            if value_lower in self.NOT_NAMES:
                return False
            if len(value) < 2 or len(value) > 20:
                return False
            if not value[0].isupper() and not value.isupper():
                # Check if original had capital
                return False
            return True
        
        if "color" in slot:
            # Must be a known color
            return value_lower in self.COLORS
        
        if "occupation" in slot:
            # Don't match emotional states as occupations
            if any(word in value_lower for word in self.NOT_NAMES):
                return False
            return True
        
        return True
    
    def _is_casual_statement(self, text: str) -> bool:
        """Detect casual/emotional statements that shouldn't be parsed for facts."""
        casual_patterns = [
            r"^(?:i'm|i am)\s+(?:feeling|doing|getting|going|being)\b",
            r"^(?:i'm|i am)\s+(?:tired|happy|sad|hungry|sick|fine|good|great|okay|ok)\b",
            r"^(?:hello|hi|hey|greetings|good morning|good afternoon|good evening)",
            r"(?:wonder|wondering|think|thinking)\s+(?:what|why|how|if)",
            r"(?:what is the|what's the)\s+(?:point|meaning|purpose)",
        ]
        for pattern in casual_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def _is_correction(self, text: str) -> bool:
        for pattern in self.CORRECTION_SIGNALS:
            if re.search(pattern, text):
                return True
        return False


class FactStore:
    """
    Slot-based fact storage with contradiction handling.
    
    PROD: Add fact expiration/decay
    PROD: Add confidence intervals
    PROD: Add source credibility weighting
    PROD: Add multi-user support (user_id column)
    """
    
    def __init__(self, db_path: str = "fact_store.db"):
        self.db_path = db_path
        self.extractor = FactExtractor()
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slot TEXT NOT NULL,
                    value TEXT NOT NULL,
                    trust REAL NOT NULL,
                    source TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    is_current INTEGER DEFAULT 1,
                    superseded_by INTEGER,
                    FOREIGN KEY (superseded_by) REFERENCES facts(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_slot_current ON facts(slot, is_current)")
    
    def process_input(self, user_input: str) -> Dict[str, Any]:
        """
        Process user input: extract facts, detect contradictions, update store.
        """
        facts = self.extractor.extract(user_input)
        result = {
            "extracted": [],
            "contradictions": [],
            "updated": []
        }
        
        for fact in facts:
            current = self.get_fact(fact.slot)
            
            if current:
                # Compare values (case-insensitive)
                if current["value"].lower() != fact.value.lower():
                    # CONTRADICTION
                    result["contradictions"].append({
                        "slot": fact.slot,
                        "old": current["value"],
                        "new": fact.value
                    })
                    self._update_fact(current["id"], fact)
                    result["updated"].append({
                        "slot": fact.slot,
                        "from": current["value"],
                        "to": fact.value
                    })
                # else: same value, no action needed
            else:
                # New fact
                self._store_fact(fact)
                result["extracted"].append(fact.to_dict())
        
        return result
    
    def get_fact(self, slot: str) -> Optional[Dict]:
        """Get current fact for a slot."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM facts WHERE slot = ? AND is_current = 1",
                (slot,)
            ).fetchone()
            return dict(row) if row else None
    
    def get_all_facts(self) -> Dict[str, Dict]:
        """Get all current facts."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM facts WHERE is_current = 1 ORDER BY slot"
            ).fetchall()
            return {row["slot"]: dict(row) for row in rows}
    
    def answer(self, question: str) -> Optional[str]:
        """
        Answer a question from stored facts.
        
        PROD: Add fuzzy slot matching
        PROD: Add multi-slot queries ("tell me about myself")
        """
        q = question.lower()
        
        # Check if it's a "why" question
        is_why = q.startswith('why')
        
        # Map question keywords to slots
        slot_map = {
            "user.name": ["name", "who am i", "who i am", "call me", "called"],
            "user.favorite_color": ["color", "colour", "favorite color"],
            "user.occupation": ["work", "job", "do for", "occupation", "profession", "do you do"],
            "user.location": ["live", "from", "location", "where", "based"],
        }
        
        for slot, keywords in slot_map.items():
            if any(kw in q for kw in keywords):
                fact = self.get_fact(slot)
                if fact:
                    # For "why" questions, also check for reason slot
                    if is_why:
                        reason_slot = f"{slot}_reason"
                        reason_fact = self.get_fact(reason_slot)
                        if reason_fact:
                            return f"Your {slot.split('.')[-1].replace('_', ' ')} is {fact['value']} because {reason_fact['value']}"
                        else:
                            return f"Your {slot.split('.')[-1].replace('_', ' ')} is {fact['value']}, but I don't know why."
                    return fact["value"]
        
        return None
    
    def get_history(self, slot: str) -> List[Dict]:
        """Get value history for a slot (for debugging/transparency)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT value, trust, source, timestamp, is_current FROM facts WHERE slot = ? ORDER BY timestamp DESC",
                (slot,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def _store_fact(self, fact: Fact) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO facts (slot, value, trust, source, timestamp) VALUES (?, ?, ?, ?, ?)",
                (fact.slot, fact.value, fact.trust, fact.source.value, fact.timestamp)
            )
            return cur.lastrowid
    
    def _update_fact(self, old_id: int, new_fact: Fact):
        """Supersede old fact with new one."""
        with sqlite3.connect(self.db_path) as conn:
            # Insert new fact
            cur = conn.execute(
                "INSERT INTO facts (slot, value, trust, source, timestamp) VALUES (?, ?, ?, ?, ?)",
                (new_fact.slot, new_fact.value, new_fact.trust, new_fact.source.value, new_fact.timestamp)
            )
            new_id = cur.lastrowid
            # Mark old as superseded
            conn.execute(
                "UPDATE facts SET is_current = 0, superseded_by = ? WHERE id = ?",
                (new_id, old_id)
            )
    
    def clear(self):
        """Clear all facts."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM facts")
    
    def close(self):
        """Close any open connections. SQLite uses context managers so this is mostly a no-op."""
        # SQLite connections are opened/closed per operation via context managers
        # This method exists for compatibility with dump_and_clear_all
        pass

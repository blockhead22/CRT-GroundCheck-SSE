"""
Structured Fact Store for CRT
Simple slot-based memory with real contradiction detection.

Phase 2.2: LLM Claim Tracker
- Tracks LLM-stated facts separately from user-stated facts
- Detects LLM→LLM contradictions (LLM said X, now says Y)
- Detects LLM→USER contradictions (User said X, LLM says Y)
- Generates disclosures for transparency

Production extension points marked with # PROD:
"""

import re
import sqlite3
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from enum import Enum


class FactSource(Enum):
    USER_STATED = "user_stated"
    USER_CORRECTED = "user_corrected"
    LLM_STATED = "llm_stated"      # Phase 2.2: LLM made this claim
    LLM_CORRECTED = "llm_corrected"  # Phase 2.2: LLM corrected its own claim
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


@dataclass
class LLMContradiction:
    """Represents a detected contradiction involving LLM claims."""
    contradiction_type: str  # "llm_vs_llm", "llm_vs_user", "user_vs_llm"
    slot: str
    old_value: str
    new_value: str
    old_source: str
    new_source: str
    disclosure: str  # Human-readable disclosure text
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


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


class LLMClaimExtractor:
    """
    Phase 2.2: Extract factual claims from LLM responses.
    
    Parses LLM output to find claims about:
    - User attributes (name, age, location, occupation)
    - User preferences (favorite color, etc.)
    - User relationships (partner, pets, etc.)
    - User history (work history, education, etc.)
    
    PROD: Use LLM-based extraction for better coverage
    PROD: Add confidence scoring for extracted claims
    """
    
    # Patterns for extracting claims the LLM makes about the user
    CLAIM_PATTERNS = {
        "user.name": [
            r"your name is ([A-Z][a-z]+)",
            r"you(?:'re| are) (?:called )?([A-Z][a-z]+)",
            r"(?:Hello|Hi),?\s+([A-Z][a-z]+)[.!,]",
            r"([A-Z][a-z]+), (?:you|your)",
        ],
        "user.age": [
            r"you(?:'re| are) (\d{1,3}) (?:years? old)",
            r"your age is (\d{1,3})",
        ],
        "user.favorite_color": [
            r"your (?:fav(?:ou?rite)? )?colou?r is ([a-z]+)",
            r"you (?:like|love|prefer) (?:the colou?r )?([a-z]+)",
        ],
        "user.occupation": [
            r"you(?:'re| are) (?:a|an) ((?:software |senior |junior |data |ml |research |web )?(?:engineer|scientist|developer|analyst|manager|designer|architect))",
            r"your (?:job|role|position) is (?:a |an )?((?:software |senior |junior |data |ml |research |web )?(?:engineer|scientist|developer|analyst|manager|designer|architect))",
        ],
        "user.location": [
            r"you(?:'re| are) (?:in|from|based in|located in|living in) ([A-Z][a-zA-Z\s,]+?)(?:\.|,|!|$)",
            r"your (?:location|city|home) is ([A-Z][a-zA-Z\s,]+?)(?:\.|,|!|$)",
        ],
        "user.employer": [
            r"you work (?:at|for) (Google|Microsoft|Amazon|Apple|Meta|Facebook|Netflix|OpenAI|Anthropic|Tesla|IBM|Oracle|Salesforce|Adobe|Intel|Nvidia|Uber|Lyft|Airbnb|Twitter|LinkedIn|Snap|Pinterest|Spotify|Stripe|Square|Shopify|Zoom|Slack|Dropbox|GitHub|GitLab|Atlassian|VMware|Cisco|Dell|HP|Samsung|Sony|LG|Huawei|Alibaba|Tencent|Baidu|ByteDance|Grab|Sea|GoTo|Tokopedia|Bukalapak|Traveloka|JD\.com|Pinduoduo|Meituan|DiDi|Xiaomi|Oppo|Vivo|Realme|OnePlus|Asus|Acer|Lenovo|Razer|Logitech|Corsair|Cooler Master|NZXT|MSI|Gigabyte|ASRock|EVGA|Zotac|Palit|PNY|Sapphire|XFX|PowerColor|HIS|VisionTek|Club 3D|Matrox|ELSA|Sparkle|Leadtek|Gainward|Inno3D|KFA2|Manli|Colorful|Maxsun|Yeston)",
            r"your (?:employer|company) is (Google|Microsoft|Amazon|Apple|Meta|Facebook|Netflix|OpenAI|Anthropic|Tesla|IBM|Oracle|Salesforce|Adobe)",
            r"(?:work|employed) (?:at|for|by) (Google|Microsoft|Amazon|Apple|Meta|Facebook|Netflix|OpenAI|Anthropic|Tesla)",
        ],
        "user.education": [
            r"you have a ((?:PhD|Master's|Bachelor's|doctorate|BS|MS|BA|MA|MBA|MD|JD|LLM)(?: degree)?)",
            r"your (?:degree|education) (?:is|from) ([A-Za-z\s]+?)(?:\.|,|!|$)",
            r"(?:PhD|Master's|Bachelor's|doctorate) (?:from|in) (Stanford|MIT|Harvard|Berkeley|Princeton|Yale|Columbia|Cornell|CMU|CalTech|Georgia Tech|UCLA|USC|NYU|UPenn|Northwestern|Duke|Johns Hopkins|UChicago|Brown|Dartmouth|Rice|Vanderbilt|Notre Dame|UVA|UMich|Wisconsin|UIUC|UT Austin|Penn State|Ohio State|Purdue|UMD|UCSD|UCI|UCD|UCSB|UCSC|UCR|UCM)",
        ],
        "user.partner": [
            r"(?:your partner|you(?:'re| are) married to|your (?:spouse|husband|wife)) (?:is )?([A-Z][a-z]+)",
            r"([A-Z][a-z]+) is your (?:partner|spouse|husband|wife)",
        ],
        "user.pet": [
            r"your (?:dog|cat|pet)(?:'s name)? is ([A-Z][a-z]+)",
            r"([A-Z][a-z]+)(?:,| is) your (?:dog|cat|pet)",
        ],
    }
    
    # Patterns that indicate hedging/uncertainty - don't extract as claims
    HEDGE_PATTERNS = [
        r"(?:i think|perhaps|maybe|possibly|might be|could be|it seems)",
        r"(?:i don't (?:know|have)|i'm not sure|unclear)",
        r"(?:you mentioned|you said|according to)",  # Quoting user, not claiming
    ]
    
    def extract(self, llm_response: str) -> List[Fact]:
        """Extract factual claims from LLM response."""
        claims = []
        response_lower = llm_response.lower()
        
        # Skip if the response is hedging
        for hedge in self.HEDGE_PATTERNS:
            if re.search(hedge, response_lower):
                # Still extract, but with lower trust
                pass
        
        seen_slots = set()  # Track slots we've already extracted
        for slot, patterns in self.CLAIM_PATTERNS.items():
            if slot in seen_slots:
                continue  # Already found a claim for this slot
                
            for pattern in patterns:
                matches = re.finditer(pattern, llm_response, re.IGNORECASE)
                for match in matches:
                    value = match.group(1).strip()
                    
                    # Basic validation
                    if not self._validate_claim(slot, value):
                        continue
                    
                    # Check if this is hedged
                    context_start = max(0, match.start() - 50)
                    context = llm_response[context_start:match.start()].lower()
                    is_hedged = any(re.search(h, context) for h in self.HEDGE_PATTERNS)
                    
                    claims.append(Fact(
                        slot=slot,
                        value=value,
                        trust=0.7 if is_hedged else 0.85,  # LLM claims have lower base trust
                        source=FactSource.LLM_STATED
                    ))
                    seen_slots.add(slot)  # Mark this slot as done
                    break  # One claim per slot per response
                
                if slot in seen_slots:
                    break  # Also break the pattern loop
        
        return claims
    
    def _validate_claim(self, slot: str, value: str) -> bool:
        """Basic validation of extracted claims."""
        if len(value) < 2 or len(value) > 100:
            return False
        
        # Age should be numeric
        if "age" in slot:
            try:
                age = int(value)
                return 0 < age < 150
            except ValueError:
                return False
        
        # Names should be capitalized
        if "name" in slot or "partner" in slot or "pet" in slot:
            if not value[0].isupper():
                return False
        
        return True


class FactStore:
    """
    Slot-based fact storage with contradiction handling.
    
    Phase 2.2: Now tracks both USER and LLM claims
    - Detects LLM→LLM contradictions
    - Detects LLM→USER contradictions  
    - Generates disclosure text for transparency
    
    PROD: Add fact expiration/decay
    PROD: Add confidence intervals
    PROD: Add source credibility weighting
    PROD: Add multi-user support (user_id column)
    """
    
    def __init__(self, db_path: str = "fact_store.db"):
        self.db_path = db_path
        self.extractor = FactExtractor()
        self.llm_extractor = LLMClaimExtractor()  # Phase 2.2
        # For in-memory DBs, keep a persistent connection
        self._persistent_conn = None
        if db_path == ":memory:":
            self._persistent_conn = sqlite3.connect(":memory:")
        self._init_db()
    
    def _get_conn(self):
        """Get database connection (persistent for :memory:, new for file-based)."""
        if self._persistent_conn:
            return self._persistent_conn
        return sqlite3.connect(self.db_path)
    
    def _execute_db(self, func):
        """Execute a database function with proper connection handling."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            result = func(conn)
            conn.commit()
            return result
        finally:
            if not self._persistent_conn:
                conn.close()
    
    def _init_db(self):
        conn = self._get_conn()
        try:
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
            conn.commit()
        finally:
            if not self._persistent_conn:
                conn.close()
    
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
        def _query(conn):
            row = conn.execute(
                "SELECT * FROM facts WHERE slot = ? AND is_current = 1",
                (slot,)
            ).fetchone()
            return dict(row) if row else None
        return self._execute_db(_query)
    
    def get_all_facts(self) -> Dict[str, Dict]:
        """Get all current facts."""
        def _query(conn):
            rows = conn.execute(
                "SELECT * FROM facts WHERE is_current = 1 ORDER BY slot"
            ).fetchall()
            return {row["slot"]: dict(row) for row in rows}
        return self._execute_db(_query)
    
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
        def _query(conn):
            rows = conn.execute(
                "SELECT value, trust, source, timestamp, is_current FROM facts WHERE slot = ? ORDER BY timestamp DESC",
                (slot,)
            ).fetchall()
            return [dict(row) for row in rows]
        return self._execute_db(_query)
    
    def _store_fact(self, fact: Fact) -> int:
        def _insert(conn):
            cur = conn.execute(
                "INSERT INTO facts (slot, value, trust, source, timestamp) VALUES (?, ?, ?, ?, ?)",
                (fact.slot, fact.value, fact.trust, fact.source.value, fact.timestamp)
            )
            return cur.lastrowid
        return self._execute_db(_insert)
    
    def _update_fact(self, old_id: int, new_fact: Fact):
        """Supersede old fact with new one."""
        def _update(conn):
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
        self._execute_db(_update)
    
    def clear(self):
        """Clear all facts."""
        def _clear(conn):
            conn.execute("DELETE FROM facts")
        self._execute_db(_clear)
    
    # =========================================================================
    # Phase 2.2: LLM Claim Tracking
    # =========================================================================
    
    def process_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """
        Phase 2.2: Process LLM response to extract and track claims.
        
        Returns:
            {
                "claims": [extracted claims],
                "contradictions": [detected contradictions with disclosures],
                "disclosures": [disclosure strings to prepend to response]
            }
        """
        claims = self.llm_extractor.extract(llm_response)
        result = {
            "claims": [],
            "contradictions": [],
            "disclosures": []
        }
        
        for claim in claims:
            contradiction = self._check_llm_claim(claim)
            
            if contradiction:
                result["contradictions"].append({
                    "type": contradiction.contradiction_type,
                    "slot": contradiction.slot,
                    "old_value": contradiction.old_value,
                    "new_value": contradiction.new_value,
                    "old_source": contradiction.old_source,
                    "new_source": contradiction.new_source,
                    "disclosure": contradiction.disclosure
                })
                result["disclosures"].append(contradiction.disclosure)
            
            # Store the LLM claim (even if contradictory - keep audit trail)
            self._store_llm_claim(claim)
            result["claims"].append(claim.to_dict())
        
        return result
    
    def _check_llm_claim(self, claim: Fact) -> Optional[LLMContradiction]:
        """
        Check if an LLM claim contradicts:
        1. A previous LLM claim (LLM→LLM contradiction)
        2. A user-stated fact (LLM→USER contradiction)
        
        User facts take priority - LLM should not contradict what user said.
        """
        # First check against user-stated facts (higher priority)
        user_fact = self._get_user_fact(claim.slot)
        if user_fact and user_fact["value"].lower() != claim.value.lower():
            return LLMContradiction(
                contradiction_type="llm_vs_user",
                slot=claim.slot,
                old_value=user_fact["value"],
                new_value=claim.value,
                old_source=user_fact["source"],
                new_source="llm_stated",
                disclosure=self._generate_disclosure(
                    "llm_vs_user", 
                    claim.slot, 
                    user_fact["value"], 
                    claim.value
                )
            )
        
        # Then check against previous LLM claims
        llm_fact = self._get_llm_fact(claim.slot)
        if llm_fact and llm_fact["value"].lower() != claim.value.lower():
            return LLMContradiction(
                contradiction_type="llm_vs_llm",
                slot=claim.slot,
                old_value=llm_fact["value"],
                new_value=claim.value,
                old_source="llm_stated",
                new_source="llm_stated",
                disclosure=self._generate_disclosure(
                    "llm_vs_llm",
                    claim.slot,
                    llm_fact["value"],
                    claim.value
                )
            )
        
        return None
    
    def _get_user_fact(self, slot: str) -> Optional[Dict]:
        """Get the current user-stated fact for a slot."""
        def _query(conn):
            row = conn.execute(
                """SELECT * FROM facts 
                   WHERE slot = ? AND is_current = 1 
                   AND source IN ('user_stated', 'user_corrected')""",
                (slot,)
            ).fetchone()
            return dict(row) if row else None
        return self._execute_db(_query)
    
    def _get_llm_fact(self, slot: str) -> Optional[Dict]:
        """Get the most recent LLM claim for a slot."""
        def _query(conn):
            row = conn.execute(
                """SELECT * FROM facts 
                   WHERE slot = ? AND is_current = 1 
                   AND source IN ('llm_stated', 'llm_corrected')""",
                (slot,)
            ).fetchone()
            return dict(row) if row else None
        return self._execute_db(_query)
    
    def _store_llm_claim(self, claim: Fact):
        """Store an LLM claim, superseding any previous LLM claim for same slot."""
        existing = self._get_llm_fact(claim.slot)
        if existing:
            # Supersede old LLM claim
            self._update_fact(existing["id"], claim)
        else:
            self._store_fact(claim)
    
    def _generate_disclosure(
        self, 
        contradiction_type: str, 
        slot: str, 
        old_value: str, 
        new_value: str
    ) -> str:
        """Generate human-readable disclosure text for a contradiction."""
        slot_name = slot.replace("user.", "").replace("_", " ")
        
        if contradiction_type == "llm_vs_user":
            return (
                f"⚠️ Correction: You told me your {slot_name} is {old_value}, "
                f"but I was about to say {new_value}. I'll use what you told me."
            )
        elif contradiction_type == "llm_vs_llm":
            return (
                f"📝 Note: I previously said your {slot_name} was {old_value}, "
                f"but now I'm saying {new_value}. I may have been inconsistent."
            )
        else:
            return f"⚠️ Inconsistency detected for {slot_name}: {old_value} vs {new_value}"
    
    def get_all_llm_claims(self) -> Dict[str, Dict]:
        """Get all current LLM claims."""
        def _query(conn):
            rows = conn.execute(
                """SELECT * FROM facts 
                   WHERE is_current = 1 
                   AND source IN ('llm_stated', 'llm_corrected')
                   ORDER BY slot"""
            ).fetchall()
            return {row["slot"]: dict(row) for row in rows}
        return self._execute_db(_query)
    
    def get_contradiction_summary(self) -> Dict[str, Any]:
        """
        Get summary of all contradictions between user facts and LLM claims.
        Useful for debugging and transparency.
        """
        def _query(conn):
            rows = conn.execute(
                "SELECT * FROM facts WHERE is_current = 1"
            ).fetchall()
            
            user_facts = {}
            llm_facts = {}
            for row in rows:
                fact = dict(row)
                if fact["source"] in ("user_stated", "user_corrected"):
                    user_facts[fact["slot"]] = fact
                elif fact["source"] in ("llm_stated", "llm_corrected"):
                    llm_facts[fact["slot"]] = fact
            
            return user_facts, llm_facts
        
        user_facts, llm_facts = self._execute_db(_query)
        
        # Find conflicts
        conflicts = []
        for slot in set(user_facts.keys()) & set(llm_facts.keys()):
            if user_facts[slot]["value"].lower() != llm_facts[slot]["value"].lower():
                conflicts.append({
                    "slot": slot,
                    "user_value": user_facts[slot]["value"],
                    "llm_value": llm_facts[slot]["value"],
                    "recommendation": f"Trust user value: {user_facts[slot]['value']}"
                })
        
        return {
            "user_fact_count": len(user_facts),
            "llm_claim_count": len(llm_facts),
            "conflict_count": len(conflicts),
            "conflicts": conflicts
        }
    
    def validate_response(self, llm_response: str) -> Tuple[str, List[str]]:
        """
        Phase 2.2: Validate an LLM response before sending to user.
        
        Returns:
            (possibly_modified_response, list_of_disclosures)
        
        If contradictions are found, disclosures are prepended to response.
        """
        result = self.process_llm_response(llm_response)
        
        if result["disclosures"]:
            # Prepend disclosures to response
            disclosure_text = "\n".join(result["disclosures"]) + "\n\n"
            return disclosure_text + llm_response, result["disclosures"]
        
        return llm_response, []

    def close(self):
        """Close any open connections. SQLite uses context managers so this is mostly a no-op."""
        # SQLite connections are opened/closed per operation via context managers
        # This method exists for compatibility with dump_and_clear_all
        pass

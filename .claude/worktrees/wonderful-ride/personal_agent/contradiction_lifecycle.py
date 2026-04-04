"""
Contradiction Lifecycle and Disclosure Policy for CRT System.

Implements:
1. Extended contradiction states (Active → Settling → Settled → Archived)
2. State transition logic based on user confirmations and time
3. Disclosure policy with "disclosure budgets" to reduce noise
4. User transparency preferences

Design Philosophy:
- Contradictions have a lifecycle, not just binary resolution
- Not all contradictions need immediate disclosure
- User preferences guide transparency level
- High-stakes domains always get disclosure
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ContradictionLifecycleState(str, Enum):
    """
    Extended contradiction states for lifecycle management.
    
    Lifecycle flow:
    ACTIVE → SETTLING → SETTLED → ARCHIVED
    
    - ACTIVE: Just detected, requires disclosure
    - SETTLING: Evidence accumulating, user has seen it
    - SETTLED: Resolved implicitly through repeated use
    - ARCHIVED: Historical, no longer relevant
    """
    ACTIVE = "active"         # Just detected, requires disclosure
    SETTLING = "settling"     # Evidence accumulating
    SETTLED = "settled"       # Resolved implicitly
    ARCHIVED = "archived"     # Historical, no longer relevant


@dataclass
class ContradictionLifecycleEntry:
    """
    Extended contradiction entry with lifecycle tracking.
    
    This extends the basic ContradictionEntry with lifecycle-specific fields
    for tracking state transitions and disclosure decisions.
    """
    ledger_id: str
    state: ContradictionLifecycleState = ContradictionLifecycleState.ACTIVE
    
    # Timestamps
    detected_at: float = field(default_factory=time.time)
    settled_at: Optional[float] = None
    archived_at: Optional[float] = None
    
    # User interaction tracking
    confirmation_count: int = 0  # How many times user repeated new fact
    disclosure_count: int = 0    # How many times we disclosed this
    last_mentioned: float = field(default_factory=time.time)
    
    # Affected facts
    affected_slots: Set[str] = field(default_factory=set)
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    
    # Configuration
    freshness_window: float = 7 * 86400  # 7 days in seconds (default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization."""
        return {
            "ledger_id": self.ledger_id,
            "state": self.state.value,
            "detected_at": self.detected_at,
            "settled_at": self.settled_at,
            "archived_at": self.archived_at,
            "confirmation_count": self.confirmation_count,
            "disclosure_count": self.disclosure_count,
            "last_mentioned": self.last_mentioned,
            "affected_slots": list(self.affected_slots),
            "old_value": self.old_value,
            "new_value": self.new_value,
            "freshness_window": self.freshness_window,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContradictionLifecycleEntry':
        """Create from dictionary."""
        return cls(
            ledger_id=data["ledger_id"],
            state=ContradictionLifecycleState(data.get("state", "active")),
            detected_at=data.get("detected_at", time.time()),
            settled_at=data.get("settled_at"),
            archived_at=data.get("archived_at"),
            confirmation_count=data.get("confirmation_count", 0),
            disclosure_count=data.get("disclosure_count", 0),
            last_mentioned=data.get("last_mentioned", time.time()),
            affected_slots=set(data.get("affected_slots", [])),
            old_value=data.get("old_value"),
            new_value=data.get("new_value"),
            freshness_window=data.get("freshness_window", 7 * 86400),
        )
    
    @property
    def age_seconds(self) -> float:
        """Get age of contradiction in seconds."""
        return time.time() - self.detected_at
    
    @property
    def age_days(self) -> float:
        """Get age of contradiction in days."""
        return self.age_seconds / 86400
    
    @property
    def is_stale(self) -> bool:
        """Check if contradiction is past freshness window."""
        return self.age_seconds > self.freshness_window


class ContradictionLifecycle:
    """
    Manages contradiction state transitions.
    
    State transition rules:
    1. ACTIVE → SETTLING: User confirmed new fact 2+ times OR past freshness window
    2. SETTLING → SETTLED: User confirmed 5+ times OR past 2x freshness window
    3. SETTLED → ARCHIVED: After 30 days
    
    Example:
        >>> lifecycle = ContradictionLifecycle()
        >>> entry = ContradictionLifecycleEntry(ledger_id="c1")
        >>> entry.confirmation_count = 3
        >>> new_state = lifecycle.update_state(entry)
        >>> print(new_state)  # ContradictionLifecycleState.SETTLING
    """
    
    # Default thresholds for state transitions
    ACTIVE_TO_SETTLING_CONFIRMATIONS = 2
    SETTLING_TO_SETTLED_CONFIRMATIONS = 5
    ARCHIVE_AFTER_DAYS = 30
    
    def __init__(
        self,
        active_to_settling_confirmations: int = 2,
        settling_to_settled_confirmations: int = 5,
        archive_after_days: int = 30,
    ):
        """
        Initialize lifecycle manager with configurable thresholds.
        
        Args:
            active_to_settling_confirmations: Confirmations needed for ACTIVE→SETTLING
            settling_to_settled_confirmations: Confirmations needed for SETTLING→SETTLED
            archive_after_days: Days after which SETTLED→ARCHIVED
        """
        self.active_to_settling = active_to_settling_confirmations
        self.settling_to_settled = settling_to_settled_confirmations
        self.archive_days = archive_after_days
    
    def update_state(
        self,
        entry: ContradictionLifecycleEntry,
    ) -> ContradictionLifecycleState:
        """
        Update and return the appropriate state for a contradiction.
        
        This method evaluates the current state and metrics to determine
        if a state transition should occur.
        
        Args:
            entry: The contradiction entry to evaluate
            
        Returns:
            The new (or unchanged) state
        """
        now = time.time()
        age = now - entry.detected_at
        
        current_state = entry.state
        
        # ============================================================
        # ACTIVE → SETTLING transitions
        # ============================================================
        if current_state == ContradictionLifecycleState.ACTIVE:
            # Condition 1: Sufficient user confirmations
            if entry.confirmation_count >= self.active_to_settling:
                logger.debug(
                    f"Contradiction {entry.ledger_id}: ACTIVE→SETTLING "
                    f"(confirmations: {entry.confirmation_count})"
                )
                return ContradictionLifecycleState.SETTLING
            
            # Condition 2: Past freshness window
            if age > entry.freshness_window:
                logger.debug(
                    f"Contradiction {entry.ledger_id}: ACTIVE→SETTLING "
                    f"(age: {age / 86400:.1f} days)"
                )
                return ContradictionLifecycleState.SETTLING
        
        # ============================================================
        # SETTLING → SETTLED transitions
        # ============================================================
        if current_state == ContradictionLifecycleState.SETTLING:
            # Condition 1: Many confirmations
            if entry.confirmation_count >= self.settling_to_settled:
                logger.debug(
                    f"Contradiction {entry.ledger_id}: SETTLING→SETTLED "
                    f"(confirmations: {entry.confirmation_count})"
                )
                entry.settled_at = now
                return ContradictionLifecycleState.SETTLED
            
            # Condition 2: Past 2x freshness window
            if age > entry.freshness_window * 2:
                logger.debug(
                    f"Contradiction {entry.ledger_id}: SETTLING→SETTLED "
                    f"(age: {age / 86400:.1f} days)"
                )
                entry.settled_at = now
                return ContradictionLifecycleState.SETTLED
        
        # ============================================================
        # SETTLED → ARCHIVED transitions
        # ============================================================
        if current_state == ContradictionLifecycleState.SETTLED:
            archive_threshold = self.archive_days * 86400
            if age > archive_threshold:
                logger.debug(
                    f"Contradiction {entry.ledger_id}: SETTLED→ARCHIVED "
                    f"(age: {age / 86400:.1f} days)"
                )
                entry.archived_at = now
                return ContradictionLifecycleState.ARCHIVED
        
        # No transition
        return current_state
    
    def record_confirmation(
        self,
        entry: ContradictionLifecycleEntry,
    ) -> ContradictionLifecycleState:
        """
        Record a user confirmation and update state if needed.
        
        Args:
            entry: The contradiction entry
            
        Returns:
            Updated state after recording confirmation
        """
        entry.confirmation_count += 1
        entry.last_mentioned = time.time()
        
        new_state = self.update_state(entry)
        entry.state = new_state
        return new_state
    
    def record_disclosure(
        self,
        entry: ContradictionLifecycleEntry,
    ) -> None:
        """
        Record that a contradiction was disclosed to the user.
        
        Args:
            entry: The contradiction entry
        """
        entry.disclosure_count += 1
        entry.last_mentioned = time.time()


class TransparencyLevel(str, Enum):
    """User preference for transparency/disclosure level."""
    MINIMAL = "minimal"      # Only disclose critical contradictions
    BALANCED = "balanced"    # Default: reasonable disclosure
    AUDIT_HEAVY = "audit_heavy"  # Disclose everything


class MemoryStyle(str, Enum):
    """User preference for how memories are handled."""
    STICKY = "sticky"        # Memories persist longer, harder to override
    NORMAL = "normal"        # Default behavior
    FORGETFUL = "forgetful"  # Memories fade faster, easier to override


@dataclass
class UserTransparencyPrefs:
    """
    User preferences for transparency and disclosure.
    
    These preferences control how aggressively contradictions are
    disclosed and how memories are managed.
    """
    transparency_level: TransparencyLevel = TransparencyLevel.BALANCED
    memory_style: MemoryStyle = MemoryStyle.NORMAL
    always_disclose_domains: Set[str] = field(default_factory=lambda: {
        "medical", "financial", "legal"
    })
    never_nag_domains: Set[str] = field(default_factory=set)
    max_disclosures_per_session: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "transparency_level": self.transparency_level.value,
            "memory_style": self.memory_style.value,
            "always_disclose_domains": list(self.always_disclose_domains),
            "never_nag_domains": list(self.never_nag_domains),
            "max_disclosures_per_session": self.max_disclosures_per_session,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserTransparencyPrefs':
        """Create from dictionary."""
        return cls(
            transparency_level=TransparencyLevel(
                data.get("transparency_level", "balanced")
            ),
            memory_style=MemoryStyle(data.get("memory_style", "normal")),
            always_disclose_domains=set(data.get("always_disclose_domains", [
                "medical", "financial", "legal"
            ])),
            never_nag_domains=set(data.get("never_nag_domains", [])),
            max_disclosures_per_session=data.get("max_disclosures_per_session", 3),
        )


class DisclosurePolicy:
    """
    Determines when contradictions should be disclosed to the user.
    
    The disclosure policy balances transparency with user experience.
    Not every contradiction needs to be disclosed immediately - some
    can settle naturally through continued use.
    
    Disclosure is required when:
    1. User directly asked about the affected fact
    2. Contradiction is still in ACTIVE state
    3. Affected domain is high-stakes (medical, financial, legal)
    4. User preference is "audit-heavy"
    
    Disclosure is skipped when:
    1. Contradiction has settled (SETTLED or ARCHIVED state)
    2. User has seen this disclosure too many times already
    3. User preference is "minimal" and domain is not high-stakes
    """
    
    # High-stakes attributes that always require disclosure
    HIGH_STAKES_ATTRIBUTES: Set[str] = {
        # Medical
        "medical_diagnosis",
        "medication",
        "allergy",
        "blood_type",
        "medical_condition",
        
        # Financial
        "account_balance",
        "account_number",
        "credit_score",
        "salary",
        "income",
        
        # Legal
        "legal_status",
        "citizenship",
        "visa_status",
        
        # Safety
        "emergency_contact",
        "address",
        "phone_number",
    }
    
    def __init__(
        self,
        user_prefs: Optional[UserTransparencyPrefs] = None,
        lifecycle: Optional[ContradictionLifecycle] = None,
    ):
        """
        Initialize disclosure policy.
        
        Args:
            user_prefs: User transparency preferences
            lifecycle: Contradiction lifecycle manager
        """
        self.user_prefs = user_prefs or UserTransparencyPrefs()
        self.lifecycle = lifecycle or ContradictionLifecycle()
        self._session_disclosures = 0
    
    def reset_session(self) -> None:
        """Reset session disclosure counter."""
        self._session_disclosures = 0
    
    def should_disclose(
        self,
        contradiction: ContradictionLifecycleEntry,
        query_context: str = "",
        force_check_query: bool = False,
    ) -> bool:
        """
        Determine if a contradiction should be disclosed.
        
        Args:
            contradiction: The contradiction entry to evaluate
            query_context: Current user query (for relevance checking)
            force_check_query: If True, check query relevance even if other
                             conditions would skip disclosure
            
        Returns:
            True if contradiction should be disclosed, False otherwise
        """
        # ============================================================
        # Always disclose conditions
        # ============================================================
        
        # 1. User directly asked about affected fact
        if query_context and self._is_direct_query(query_context, contradiction):
            return True
        
        # 2. Still in ACTIVE state
        if contradiction.state == ContradictionLifecycleState.ACTIVE:
            return True
        
        # 3. High-stakes domain
        if self._is_high_stakes(contradiction):
            return True
        
        # 4. User preference is "audit-heavy"
        if self.user_prefs.transparency_level == TransparencyLevel.AUDIT_HEAVY:
            return True
        
        # ============================================================
        # Skip disclosure conditions
        # ============================================================
        
        # 5. Contradiction is archived (historical)
        if contradiction.state == ContradictionLifecycleState.ARCHIVED:
            return False
        
        # 6. Reached session disclosure limit
        if self._session_disclosures >= self.user_prefs.max_disclosures_per_session:
            return False
        
        # 7. User preference is "minimal" and not high-stakes
        if self.user_prefs.transparency_level == TransparencyLevel.MINIMAL:
            return False
        
        # 8. Already disclosed too many times
        if contradiction.disclosure_count >= 3:
            return False
        
        # ============================================================
        # Balanced disclosure (default)
        # ============================================================
        
        # For SETTLING state, disclose only if recently active
        if contradiction.state == ContradictionLifecycleState.SETTLING:
            # Don't nag if user has confirmed multiple times
            if contradiction.confirmation_count >= 2:
                return False
            return True
        
        # SETTLED state - don't disclose unless directly asked
        return force_check_query and self._is_direct_query(query_context, contradiction)
    
    def _is_direct_query(
        self,
        query: str,
        contradiction: ContradictionLifecycleEntry,
    ) -> bool:
        """
        Check if the user query directly relates to the contradiction.
        
        Args:
            query: User's query text
            contradiction: The contradiction entry
            
        Returns:
            True if query is about the contradicted fact
        """
        if not query:
            return False
        
        query_lower = query.lower()
        
        # Check if query mentions affected slots
        for slot in contradiction.affected_slots:
            slot_normalized = slot.lower().replace("_", " ")
            if slot_normalized in query_lower:
                return True
            if slot in query_lower:
                return True
        
        # Check if query mentions old or new values
        if contradiction.old_value:
            if contradiction.old_value.lower() in query_lower:
                return True
        if contradiction.new_value:
            if contradiction.new_value.lower() in query_lower:
                return True
        
        return False
    
    def _is_high_stakes(self, contradiction: ContradictionLifecycleEntry) -> bool:
        """
        Check if contradiction affects high-stakes attributes.
        
        Args:
            contradiction: The contradiction entry
            
        Returns:
            True if any affected slot is high-stakes
        """
        # Check against built-in high-stakes list
        if contradiction.affected_slots & self.HIGH_STAKES_ATTRIBUTES:
            return True
        
        # Check against user-defined always-disclose domains
        for slot in contradiction.affected_slots:
            for domain in self.user_prefs.always_disclose_domains:
                if domain in slot.lower():
                    return True
        
        return False
    
    def record_disclosure(
        self,
        contradiction: ContradictionLifecycleEntry,
    ) -> None:
        """
        Record that a disclosure was made.
        
        Args:
            contradiction: The disclosed contradiction
        """
        self._session_disclosures += 1
        self.lifecycle.record_disclosure(contradiction)
    
    def get_disclosure_priority(
        self,
        contradictions: List[ContradictionLifecycleEntry],
        query_context: str = "",
    ) -> List[ContradictionLifecycleEntry]:
        """
        Sort contradictions by disclosure priority.
        
        Higher priority contradictions should be disclosed first.
        
        Args:
            contradictions: List of contradictions to prioritize
            query_context: Current user query for relevance scoring
            
        Returns:
            List of contradictions sorted by priority (highest first)
        """
        def priority_score(c: ContradictionLifecycleEntry) -> float:
            score = 0.0
            
            # State-based priority
            state_scores = {
                ContradictionLifecycleState.ACTIVE: 100,
                ContradictionLifecycleState.SETTLING: 50,
                ContradictionLifecycleState.SETTLED: 10,
                ContradictionLifecycleState.ARCHIVED: 0,
            }
            score += state_scores.get(c.state, 0)
            
            # High-stakes bonus
            if self._is_high_stakes(c):
                score += 200
            
            # Direct query relevance bonus
            if self._is_direct_query(query_context, c):
                score += 300
            
            # Recency bonus (newer = higher priority)
            age_days = c.age_days
            if age_days < 1:
                score += 50
            elif age_days < 7:
                score += 20
            
            # Low disclosure count bonus (less nagging)
            score -= c.disclosure_count * 10
            
            return score
        
        return sorted(contradictions, key=priority_score, reverse=True)

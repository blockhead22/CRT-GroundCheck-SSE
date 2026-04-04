"""
EvidencePacket v1.0 - Validator and Schema Enforcement

This module enforces the EvidencePacket schema and philosophy:
- All claims included (no filtering)
- All contradictions included (no suppression)
- No forbidden interpretation fields
- No forbidden language in descriptions
- Audit trail is immutable
"""

import json
import uuid
from typing import Dict, List, Any, Set, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import jsonschema
from pathlib import Path


# ============================================================================
# FORBIDDEN CONCEPTS (Will never appear in valid packets)
# ============================================================================

FORBIDDEN_WORDS = {
    # Interpretation words
    "confidence", "credibility", "reliability", "truth_likelihood",
    "importance", "quality", "consensus", "agreement", "resolved",
    "settled", "preferred", "better", "worse", "best", "likely",
    "probably", "reliable", "unreliable", "drift",
    "more credible", "seems", "appears to be",
    
    # Synthesis/resolution words
    "synthesize", "resolve", "coherent", "incoherent",
    "unified view", "synthesis", "reconcile", "harmonize",
}

FORBIDDEN_FIELDS = {
    "confidence",
    "credibility",
    "reliability",
    "truth_likelihood",
    "importance",
    "quality",
    "consensus",
    "agreement",
    "resolved",
    "settled",
    "preferred",
    "confidence_score",
    "truth_score",
    "quality_score",
    "importance_weight",
    "coherence_score",
    "synthesis_ready",
    "interpretation",
}

# ============================================================================
# DATACLASSES (Type-safe packet building)
# ============================================================================

@dataclass
class Claim:
    """A single claim extracted from source."""
    claim_id: str
    claim_text: str
    source_document_id: str
    extraction_offset: Dict[str, int]  # {start, end}
    extraction_verified: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Contradiction:
    """A relationship between two claims."""
    claim_a_id: str
    claim_b_id: str
    relationship_type: str  # "contradicts", "qualifies", "extends"
    topology_strength: float  # [0.0 to 1.0]
    detected_timestamp: str  # ISO8601

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SupportMetrics:
    """Evidence density metrics for a claim."""
    source_count: int
    retrieval_score: float
    contradiction_count: int
    cluster_membership_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Provenance:
    """Source attribution for a claim."""
    document_id: str
    offset_start: int
    offset_end: int
    extraction_method: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Event:
    """Audit trail event."""
    event_type: str  # query_executed, contradiction_found, etc
    timestamp: str  # ISO8601
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Metadata:
    """Query context metadata."""
    query: str
    timestamp: str  # ISO8601
    indexed_version: str
    adapter_request_id: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EvidencePacket:
    """
    The immutable truth-disclosure format for SSE results.
    
    Enforces:
    - All claims preserved (no filtering)
    - All contradictions preserved (no suppression)
    - No interpretation fields
    - No forbidden language
    - Complete provenance
    - Immutable audit trail
    """

    def __init__(
        self,
        metadata: Metadata,
        claims: List[Claim],
        contradictions: List[Contradiction],
        clusters: List[List[str]],
        support_metrics: Dict[str, SupportMetrics],
        provenance: Dict[str, Provenance],
        event_log: List[Event],
    ):
        self.metadata = metadata
        self.claims = claims
        self.contradictions = contradictions
        self.clusters = clusters
        self.support_metrics = support_metrics
        self.provenance = provenance
        self.event_log = event_log

        # Validate on construction
        self._validate()

    def _validate(self) -> None:
        """Run all validation checks."""
        self._validate_completeness()
        self._validate_no_forbidden_fields()
        self._validate_no_forbidden_language()
        self._validate_references()
        self._validate_metrics()

    def _validate_completeness(self) -> None:
        """Ensure all claims have complete metadata."""
        claim_ids = {c.claim_id for c in self.claims}

        # Every claim must have support metrics
        for claim_id in claim_ids:
            if claim_id not in self.support_metrics:
                raise ValueError(
                    f"Claim {claim_id} missing support_metrics entry"
                )

        # Every claim must have provenance
        for claim_id in claim_ids:
            if claim_id not in self.provenance:
                raise ValueError(f"Claim {claim_id} missing provenance entry")

    def _validate_no_forbidden_fields(self) -> None:
        """Reject any forbidden fields anywhere in packet."""
        packet_dict = self.to_dict()
        self._check_dict_for_forbidden_fields(packet_dict)

    def _check_dict_for_forbidden_fields(self, obj: Any, path: str = "") -> None:
        """Recursively check for forbidden field names."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in FORBIDDEN_FIELDS:
                    raise ValueError(
                        f"Forbidden field '{key}' found at {path}.{key}"
                    )
                self._check_dict_for_forbidden_fields(value, f"{path}.{key}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                self._check_dict_for_forbidden_fields(item, f"{path}[{i}]")

    def _validate_no_forbidden_language(self) -> None:
        """Check event descriptions for forbidden words."""
        for i, event in enumerate(self.event_log):
            details_str = json.dumps(event.details).lower()
            for forbidden in FORBIDDEN_WORDS:
                if forbidden.lower() in details_str:
                    raise ValueError(
                        f"Forbidden word '{forbidden}' found in event_log[{i}].details: {event.details}"
                    )

    def _validate_references(self) -> None:
        """Ensure contradictions reference valid claims."""
        claim_ids = {c.claim_id for c in self.claims}

        for i, contradiction in enumerate(self.contradictions):
            if contradiction.claim_a_id not in claim_ids:
                raise ValueError(
                    f"Contradiction[{i}]: claim_a_id '{contradiction.claim_a_id}' not found"
                )
            if contradiction.claim_b_id not in claim_ids:
                raise ValueError(
                    f"Contradiction[{i}]: claim_b_id '{contradiction.claim_b_id}' not found"
                )

    def _validate_metrics(self) -> None:
        """Validate metric ranges."""
        for claim_id, metrics in self.support_metrics.items():
            if not (0.0 <= metrics.retrieval_score <= 1.0):
                raise ValueError(
                    f"Claim {claim_id}: retrieval_score {metrics.retrieval_score} out of range [0.0, 1.0]"
                )

        for contradiction in self.contradictions:
            if not (0.0 <= contradiction.topology_strength <= 1.0):
                raise ValueError(
                    f"Contradiction ({contradiction.claim_a_id}, {contradiction.claim_b_id}): "
                    f"topology_strength {contradiction.topology_strength} out of range [0.0, 1.0]"
                )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metadata": self.metadata.to_dict(),
            "claims": [c.to_dict() for c in self.claims],
            "contradictions": [c.to_dict() for c in self.contradictions],
            "clusters": self.clusters,
            "support_metrics": {
                cid: metrics.to_dict()
                for cid, metrics in self.support_metrics.items()
            },
            "provenance": {
                cid: prov.to_dict() for cid, prov in self.provenance.items()
            },
            "event_log": [e.to_dict() for e in self.event_log],
        }

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "EvidencePacket":
        """Construct from dictionary (validates schema + semantics)."""
        # First validate against JSON schema
        EvidencePacketValidator.validate_schema(data)

        # Then construct with dataclass validation
        metadata = Metadata(**data["metadata"])
        claims = [Claim(**c) for c in data["claims"]]
        contradictions = [Contradiction(**c) for c in data["contradictions"]]
        clusters = data["clusters"]
        support_metrics = {
            cid: SupportMetrics(**m) for cid, m in data["support_metrics"].items()
        }
        provenance = {
            cid: Provenance(**p) for cid, p in data["provenance"].items()
        }
        event_log = [Event(**e) for e in data["event_log"]]

        return EvidencePacket(
            metadata=metadata,
            claims=claims,
            contradictions=contradictions,
            clusters=clusters,
            support_metrics=support_metrics,
            provenance=provenance,
            event_log=event_log,
        )


class EvidencePacketValidator:
    """
    Schema and semantic validator for EvidencePacket.
    
    Checks:
    - JSON Schema conformance
    - Forbidden fields absent
    - Forbidden language absent
    - All references valid
    - All metrics in range
    """

    _schema = None

    @classmethod
    def _load_schema(cls) -> Dict[str, Any]:
        """Load JSON schema from file."""
        if cls._schema is None:
            # Try schemas/ subdirectory first, then fall back to repo root
            schema_path = Path(__file__).parent.parent / "schemas" / "evidence_packet.v1.schema.json"
            if not schema_path.exists():
                schema_path = Path(__file__).parent.parent / "evidence_packet.v1.schema.json"
            with open(schema_path, "r") as f:
                cls._schema = json.load(f)
        return cls._schema

    @classmethod
    def validate_schema(cls, data: Dict[str, Any]) -> None:
        """Validate against JSON schema."""
        schema = cls._load_schema()
        try:
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"Schema validation failed: {e.message}")

    @classmethod
    def validate_complete(cls, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Complete validation (schema + semantics).
        
        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # Schema validation
        try:
            cls.validate_schema(data)
        except ValueError as e:
            errors.append(str(e))
            return False, errors

        # Semantic validation
        try:
            EvidencePacket.from_dict(data)
        except ValueError as e:
            errors.append(str(e))
            return False, errors

        return True, []


# ============================================================================
# BUILDER (For safe packet construction)
# ============================================================================

class EvidencePacketBuilder:
    """Builder pattern for constructing valid EvidencePackets."""

    def __init__(self, query: str, indexed_version: str):
        self.metadata = Metadata(
            query=query,
            timestamp=datetime.utcnow().isoformat() + "Z",
            indexed_version=indexed_version,
            adapter_request_id=str(uuid.uuid4()),
        )
        self.claims: List[Claim] = []
        self.contradictions: List[Contradiction] = []
        self.clusters: List[List[str]] = []
        self.support_metrics: Dict[str, SupportMetrics] = {}
        self.provenance: Dict[str, Provenance] = {}
        self.event_log: List[Event] = []

    def add_claim(
        self,
        claim_id: str,
        claim_text: str,
        source_document_id: str,
        offset_start: int,
        offset_end: int,
        extraction_verified: bool,
        extraction_method: str,
    ) -> "EvidencePacketBuilder":
        """Add a claim with complete metadata."""
        self.claims.append(
            Claim(
                claim_id=claim_id,
                claim_text=claim_text,
                source_document_id=source_document_id,
                extraction_offset={"start": offset_start, "end": offset_end},
                extraction_verified=extraction_verified,
            )
        )

        self.provenance[claim_id] = Provenance(
            document_id=source_document_id,
            offset_start=offset_start,
            offset_end=offset_end,
            extraction_method=extraction_method,
        )

        self.support_metrics[claim_id] = SupportMetrics(
            source_count=0,
            retrieval_score=0.0,
            contradiction_count=0,
            cluster_membership_count=0,
        )

        return self

    def add_contradiction(
        self,
        claim_a_id: str,
        claim_b_id: str,
        relationship_type: str,
        topology_strength: float,
    ) -> "EvidencePacketBuilder":
        """Add a contradiction."""
        self.contradictions.append(
            Contradiction(
                claim_a_id=claim_a_id,
                claim_b_id=claim_b_id,
                relationship_type=relationship_type,
                topology_strength=topology_strength,
                detected_timestamp=datetime.utcnow().isoformat() + "Z",
            )
        )
        return self

    def set_metrics(
        self,
        claim_id: str,
        source_count: int,
        retrieval_score: float,
        contradiction_count: int,
        cluster_membership_count: int,
    ) -> "EvidencePacketBuilder":
        """Update metrics for a claim."""
        if claim_id not in self.support_metrics:
            raise ValueError(f"Claim {claim_id} not found")
        self.support_metrics[claim_id] = SupportMetrics(
            source_count=source_count,
            retrieval_score=retrieval_score,
            contradiction_count=contradiction_count,
            cluster_membership_count=cluster_membership_count,
        )
        return self

    def add_cluster(self, claim_ids: List[str]) -> "EvidencePacketBuilder":
        """Add a disagreement cluster."""
        self.clusters.append(claim_ids)
        return self

    def log_event(self, event_type: str, details: Dict[str, Any]) -> "EvidencePacketBuilder":
        """Log an event."""
        self.event_log.append(
            Event(
                event_type=event_type,
                timestamp=datetime.utcnow().isoformat() + "Z",
                details=details,
            )
        )
        return self

    def build(self) -> EvidencePacket:
        """Build and validate the packet."""
        return EvidencePacket(
            metadata=self.metadata,
            claims=self.claims,
            contradictions=self.contradictions,
            clusters=self.clusters,
            support_metrics=self.support_metrics,
            provenance=self.provenance,
            event_log=self.event_log,
        )

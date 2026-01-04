"""
Tests for EvidencePacket v1.0 - Schema and Semantic Validation

Tests ensure:
- All claims must be included (no filtering)
- All contradictions must be included (no suppression)
- No forbidden fields can be added
- No forbidden language in events
- Complete provenance and metrics
- Schema validation enforced
"""

import pytest
import json
from datetime import datetime
from pathlib import Path
from sse.evidence_packet import (
    EvidencePacket,
    EvidencePacketValidator,
    EvidencePacketBuilder,
    Claim,
    Contradiction,
    SupportMetrics,
    Provenance,
    Event,
    Metadata,
    FORBIDDEN_WORDS,
    FORBIDDEN_FIELDS,
)


class TestEvidencePacketBuilder:
    """Test the builder pattern for safe packet construction."""

    def test_build_minimal_valid_packet(self):
        """Builder creates valid minimal packet."""
        builder = EvidencePacketBuilder("test query", "v1.0")
        builder.add_claim(
            "claim_12345678",
            "The Earth is round",
            "doc1",
            0,
            20,
            True,
            "regex"
        )
        builder.set_metrics("claim_12345678", 1, 0.9, 0, 0)
        builder.add_cluster(["claim_12345678"])
        builder.log_event("query_executed", {"status": "success"})

        packet = builder.build()
        assert len(packet.claims) == 1
        assert len(packet.event_log) == 1

    def test_build_packet_with_contradictions(self):
        """Builder handles contradictions."""
        builder = EvidencePacketBuilder("test query", "v1.0")
        builder.add_claim("claim_aaaaaaaa", "Claim A", "doc1", 0, 10, True, "regex")
        builder.add_claim("claim_bbbbbbbb", "Claim B", "doc1", 20, 30, True, "regex")
        builder.set_metrics("claim_aaaaaaaa", 1, 0.9, 1, 1)
        builder.set_metrics("claim_bbbbbbbb", 1, 0.8, 1, 1)
        builder.add_contradiction("claim_aaaaaaaa", "claim_bbbbbbbb", "contradicts", 0.95)

        packet = builder.build()
        assert len(packet.contradictions) == 1
        assert packet.contradictions[0].topology_strength == 0.95


class TestEvidencePacketValidation:
    """Test validation of complete packets."""

    def test_valid_packet_passes(self):
        """Valid packet passes all validation."""
        builder = EvidencePacketBuilder("test", "v1.0")
        builder.add_claim("claim_12345678", "Test claim", "doc1", 0, 10, True, "regex")
        builder.set_metrics("claim_12345678", 1, 0.9, 0, 0)
        builder.add_cluster(["claim_12345678"])
        builder.log_event("query_executed", {"status": "ok"})

        packet = builder.build()
        assert packet is not None

    def test_missing_claim_metrics_fails(self):
        """Packet fails if claim missing metrics."""
        metadata = Metadata(
            query="test",
            timestamp=datetime.utcnow().isoformat() + "Z",
            indexed_version="v1.0",
            adapter_request_id="00000000-0000-0000-0000-000000000000"
        )
        claims = [
            Claim(
                "claim_12345678", "Test", "doc1",
                {"start": 0, "end": 10}, True
            )
        ]

        with pytest.raises(ValueError, match="missing support_metrics"):
            EvidencePacket(
                metadata=metadata,
                claims=claims,
                contradictions=[],
                clusters=[],
                support_metrics={},
                provenance={"claim_12345678": Provenance("doc1", 0, 10, "regex")},
                event_log=[],
            )

    def test_missing_claim_provenance_fails(self):
        """Packet fails if claim missing provenance."""
        metadata = Metadata(
            query="test",
            timestamp=datetime.utcnow().isoformat() + "Z",
            indexed_version="v1.0",
            adapter_request_id="00000000-0000-0000-0000-000000000000"
        )
        claims = [
            Claim(
                "claim_12345678", "Test", "doc1",
                {"start": 0, "end": 10}, True
            )
        ]

        with pytest.raises(ValueError, match="missing provenance"):
            EvidencePacket(
                metadata=metadata,
                claims=claims,
                contradictions=[],
                clusters=[],
                support_metrics={"claim_12345678": SupportMetrics(1, 0.9, 0, 0)},
                provenance={},
                event_log=[],
            )

    def test_invalid_contradiction_reference_fails(self):
        """Packet fails if contradiction references non-existent claim."""
        builder = EvidencePacketBuilder("test", "v1.0")
        builder.add_claim("claim_aaaaaaaa", "Claim A", "doc1", 0, 10, True, "regex")
        builder.set_metrics("claim_aaaaaaaa", 1, 0.9, 1, 1)
        builder.add_contradiction("claim_aaaaaaaa", "claim_nonexist", "contradicts", 0.5)

        with pytest.raises(ValueError, match="not found"):
            builder.build()


class TestForbiddenFieldsDetection:
    """Test detection of forbidden fields via schema."""

    def test_confidence_field_rejected(self):
        """Forbidden field 'confidence' is rejected by schema."""
        data = {
            "metadata": {
                "query": "test",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "indexed_version": "v1.0",
                "adapter_request_id": "00000000-0000-0000-0000-000000000000"
            },
            "claims": [{
                "claim_id": "claim_12345678",
                "claim_text": "Test",
                "source_document_id": "doc1",
                "extraction_offset": {"start": 0, "end": 10},
                "extraction_verified": True,
                "confidence": 0.95  # FORBIDDEN
            }],
            "contradictions": [],
            "clusters": [],
            "support_metrics": {"claim_12345678": {
                "source_count": 1,
                "retrieval_score": 0.9,
                "contradiction_count": 0,
                "cluster_membership_count": 0
            }},
            "provenance": {"claim_12345678": {
                "document_id": "doc1",
                "offset_start": 0,
                "offset_end": 10,
                "extraction_method": "regex"
            }},
            "event_log": []
        }

        with pytest.raises(ValueError, match="Additional properties are not allowed"):
            EvidencePacket.from_dict(data)

    def test_credibility_field_rejected(self):
        """Forbidden field 'credibility' is rejected by schema."""
        data = {
            "metadata": {
                "query": "test",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "indexed_version": "v1.0",
                "adapter_request_id": "00000000-0000-0000-0000-000000000000"
            },
            "claims": [{
                "claim_id": "claim_12345678",
                "claim_text": "Test",
                "source_document_id": "doc1",
                "extraction_offset": {"start": 0, "end": 10},
                "extraction_verified": True
            }],
            "contradictions": [],
            "clusters": [],
            "support_metrics": {
                "claim_12345678": {
                    "source_count": 1,
                    "retrieval_score": 0.9,
                    "contradiction_count": 0,
                    "cluster_membership_count": 0,
                    "credibility": 0.85  # FORBIDDEN
                }
            },
            "provenance": {"claim_12345678": {
                "document_id": "doc1",
                "offset_start": 0,
                "offset_end": 10,
                "extraction_method": "regex"
            }},
            "event_log": []
        }

        with pytest.raises(ValueError, match="Additional properties are not allowed"):
            EvidencePacket.from_dict(data)

    def test_truth_score_field_rejected(self):
        """Forbidden field 'truth_score' is rejected by schema."""
        data = {
            "metadata": {
                "query": "test",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "indexed_version": "v1.0",
                "adapter_request_id": "00000000-0000-0000-0000-000000000000"
            },
            "claims": [{
                "claim_id": "claim_12345678",
                "claim_text": "Test",
                "source_document_id": "doc1",
                "extraction_offset": {"start": 0, "end": 10},
                "extraction_verified": True,
                "truth_score": 0.8  # FORBIDDEN
            }],
            "contradictions": [],
            "clusters": [],
            "support_metrics": {"claim_12345678": {
                "source_count": 1,
                "retrieval_score": 0.9,
                "contradiction_count": 0,
                "cluster_membership_count": 0
            }},
            "provenance": {"claim_12345678": {
                "document_id": "doc1",
                "offset_start": 0,
                "offset_end": 10,
                "extraction_method": "regex"
            }},
            "event_log": []
        }

        with pytest.raises(ValueError, match="Additional properties are not allowed"):
            EvidencePacket.from_dict(data)


class TestForbiddenLanguageDetection:
    """Test detection of forbidden language in events."""

    def test_confidence_word_in_event_rejected(self):
        """Word 'confidence' in event details is rejected."""
        builder = EvidencePacketBuilder("test", "v1.0")
        builder.add_claim("claim_12345678", "Test", "doc1", 0, 10, True, "regex")
        builder.set_metrics("claim_12345678", 1, 0.9, 0, 0)
        builder.add_cluster(["claim_12345678"])
        builder.log_event("query_executed", {
            "status": "ok",
            "note": "high confidence in this result"
        })

        with pytest.raises(ValueError, match="Forbidden word 'confidence'"):
            builder.build()

    def test_synthesis_word_in_event_rejected(self):
        """Word 'synthesize' in event details is rejected."""
        builder = EvidencePacketBuilder("test", "v1.0")
        builder.add_claim("claim_12345678", "Test", "doc1", 0, 10, True, "regex")
        builder.set_metrics("claim_12345678", 1, 0.9, 0, 0)
        builder.add_cluster(["claim_12345678"])
        builder.log_event("query_executed", {
            "status": "ok",
            "action": "synthesize_claims"
        })

        with pytest.raises(ValueError, match="Forbidden word 'synthesize'"):
            builder.build()


class TestSchemaValidation:
    """Test JSON Schema validation."""

    def test_schema_loads(self):
        """Schema file can be loaded."""
        validator = EvidencePacketValidator()
        schema = validator._load_schema()
        assert "properties" in schema
        assert "claims" in schema["properties"]

    def test_missing_required_field_fails(self):
        """Missing required field fails schema validation."""
        data = {
            "metadata": {
                "query": "test",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "indexed_version": "v1.0",
                "adapter_request_id": "00000000-0000-0000-0000-000000000000"
            },
            "claims": [],
            "clusters": [],
            "support_metrics": {},
            "provenance": {},
            "event_log": []
        }

        with pytest.raises(ValueError, match="Schema validation failed"):
            EvidencePacketValidator.validate_schema(data)

    def test_unknown_field_fails(self):
        """Unknown field fails schema validation."""
        data = {
            "metadata": {
                "query": "test",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "indexed_version": "v1.0",
                "adapter_request_id": "00000000-0000-0000-0000-000000000000"
            },
            "claims": [],
            "contradictions": [],
            "clusters": [],
            "support_metrics": {},
            "provenance": {},
            "event_log": [],
            "unknown_field": "should fail"
        }

        with pytest.raises(ValueError, match="Schema validation failed"):
            EvidencePacketValidator.validate_schema(data)

    def test_invalid_enum_value_fails(self):
        """Invalid enum value fails schema validation."""
        data = {
            "metadata": {
                "query": "test",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "indexed_version": "v1.0",
                "adapter_request_id": "00000000-0000-0000-0000-000000000000"
            },
            "claims": [{
                "claim_id": "claim_12345678",
                "claim_text": "Test",
                "source_document_id": "doc1",
                "extraction_offset": {"start": 0, "end": 10},
                "extraction_verified": True
            }],
            "contradictions": [{
                "claim_a_id": "claim_12345678",
                "claim_b_id": "claim_12345678",
                "relationship_type": "invalid_type",
                "topology_strength": 0.5,
                "detected_timestamp": datetime.utcnow().isoformat() + "Z"
            }],
            "clusters": [],
            "support_metrics": {"claim_12345678": {
                "source_count": 1,
                "retrieval_score": 0.9,
                "contradiction_count": 1,
                "cluster_membership_count": 0
            }},
            "provenance": {"claim_12345678": {
                "document_id": "doc1",
                "offset_start": 0,
                "offset_end": 10,
                "extraction_method": "regex"
            }},
            "event_log": []
        }

        with pytest.raises(ValueError, match="Schema validation failed"):
            EvidencePacketValidator.validate_schema(data)


class TestMetricsValidation:
    """Test metric ranges."""

    def test_retrieval_score_too_high_fails(self):
        """Retrieval score > 1.0 fails."""
        builder = EvidencePacketBuilder("test", "v1.0")
        builder.add_claim("claim_12345678", "Test", "doc1", 0, 10, True, "regex")
        builder.set_metrics("claim_12345678", 1, 1.5, 0, 0)

        with pytest.raises(ValueError, match="out of range"):
            builder.build()

    def test_topology_strength_negative_fails(self):
        """Topology strength < 0.0 fails."""
        builder = EvidencePacketBuilder("test", "v1.0")
        builder.add_claim("claim_aaaaaaaa", "A", "doc1", 0, 5, True, "regex")
        builder.add_claim("claim_bbbbbbbb", "B", "doc1", 10, 15, True, "regex")
        builder.set_metrics("claim_aaaaaaaa", 1, 0.9, 1, 1)
        builder.set_metrics("claim_bbbbbbbb", 1, 0.9, 1, 1)
        builder.add_contradiction("claim_aaaaaaaa", "claim_bbbbbbbb", "contradicts", -0.5)

        with pytest.raises(ValueError, match="out of range"):
            builder.build()


class TestAllClaimsIncluded:
    """Test that all claims are included (no filtering)."""

    def test_all_claims_in_output(self):
        """All added claims appear in final packet."""
        builder = EvidencePacketBuilder("test", "v1.0")
        for i in range(5):
            claim_id = f"claim_{i:08x}"
            builder.add_claim(
                claim_id,
                f"Claim {i}",
                f"doc{i}",
                i * 10,
                (i + 1) * 10,
                True,
                "regex"
            )
            builder.set_metrics(claim_id, 1, 0.9, 0, 0)

        packet = builder.build()
        assert len(packet.claims) == 5


class TestAllContradictionsIncluded:
    """Test that all contradictions are included (no suppression)."""

    def test_all_contradictions_in_output(self):
        """All added contradictions appear in final packet."""
        builder = EvidencePacketBuilder("test", "v1.0")
        claim_ids = []
        for i in range(3):
            claim_id = f"claim_{i:08x}"
            claim_ids.append(claim_id)
            builder.add_claim(
                claim_id,
                f"Claim {i}",
                f"doc{i}",
                i * 10,
                (i + 1) * 10,
                True,
                "regex"
            )
            builder.set_metrics(claim_id, 1, 0.9, 2, 0)

        builder.add_contradiction(claim_ids[0], claim_ids[1], "contradicts", 0.8)
        builder.add_contradiction(claim_ids[1], claim_ids[2], "contradicts", 0.7)

        packet = builder.build()
        assert len(packet.contradictions) == 2


class TestEventTypeConstraints:
    """Test that event types are constrained to allowed values."""

    def test_valid_event_types(self):
        """Valid event types are accepted."""
        valid_types = [
            "query_executed",
            "contradiction_found",
            "topology_changed",
            "boundary_violation",
            "adaptation_event",
            "contradiction_suppressed"
        ]

        for event_type in valid_types:
            builder = EvidencePacketBuilder("test", "v1.0")
            builder.add_claim("claim_12345678", "Test", "doc1", 0, 10, True, "regex")
            builder.set_metrics("claim_12345678", 1, 0.9, 0, 0)
            builder.add_cluster(["claim_12345678"])
            builder.log_event(event_type, {"status": "ok"})

            packet = builder.build()
            assert packet.event_log[0].event_type == event_type

    def test_invalid_event_type_fails(self):
        """Invalid event type fails schema validation."""
        data = {
            "metadata": {
                "query": "test",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "indexed_version": "v1.0",
                "adapter_request_id": "00000000-0000-0000-0000-000000000000"
            },
            "claims": [],
            "contradictions": [],
            "clusters": [],
            "support_metrics": {},
            "provenance": {},
            "event_log": [{
                "event_type": "invalid_event_type",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "details": {}
            }]
        }

        with pytest.raises(ValueError, match="Schema validation failed"):
            EvidencePacketValidator.validate_schema(data)


class TestCompleteValidation:
    """Test complete validation (schema + semantics)."""

    def test_valid_complete_validation(self):
        """Valid packet passes complete validation."""
        builder = EvidencePacketBuilder("complex test", "v1.0")
        
        for i in range(3):
            claim_id = f"claim_{i:08x}"
            builder.add_claim(
                claim_id,
                f"Claim {i}",
                f"doc{i}",
                i * 20,
                (i + 1) * 20,
                True,
                "regex"
            )
            builder.set_metrics(claim_id, 2, 0.8 + 0.1 * i, 1, 1)

        builder.add_contradiction("claim_00000000", "claim_00000001", "contradicts", 0.9)
        builder.add_cluster(["claim_00000000", "claim_00000001"])
        builder.log_event("query_executed", {"status": "success"})
        builder.log_event("contradiction_found", {
            "claim_a": "claim_00000000",
            "claim_b": "claim_00000001",
            "count": 1
        })

        packet = builder.build()
        
        is_valid, errors = EvidencePacketValidator.validate_complete(packet.to_dict())
        assert is_valid
        assert len(errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

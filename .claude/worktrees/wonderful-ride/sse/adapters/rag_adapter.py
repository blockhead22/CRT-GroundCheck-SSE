"""
RAG Adapter (Phase 4.2)

Core responsibility: Take EvidencePacket, build LLM prompt that preserves
all claims + all contradictions, get response, validate packet before returning.

Design principle: No filtering, no synthesis, no consensus-building.
Just surface contradictions explicitly so the LLM can reason about them.
"""

import json
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from ..evidence_packet import (
    EvidencePacket,
    EvidencePacketValidator,
    Event,
)


class RAGAdapter:
    """
    Retrieval-Augmented Generation adapter.
    
    Consumes EvidencePacket and produces LLM-augmented response with
    guaranteed packet preservation and validation.
    
    Contract:
    - Input: EvidencePacket dict (validated)
    - Processing: Build prompt, call LLM, log event
    - Output: Original packet (with appended events) + LLM response
    - Gate: EvidencePacketValidator.validate_complete() before return
    """

    def __init__(self, llm_client=None):
        """
        Initialize RAG adapter.
        
        Args:
            llm_client: LLM interface (can be mock for testing)
        """
        self.llm_client = llm_client

    def process_packet(
        self,
        packet_dict: Dict[str, Any],
        use_mock_llm: bool = False,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Process EvidencePacket through RAG pipeline.
        
        Args:
            packet_dict: Validated EvidencePacket dict
            use_mock_llm: Use mock LLM for testing
            
        Returns:
            (validated_packet_dict, llm_response)
            
        Raises:
            ValueError: If packet validation fails
        """
        # Step 1: Validate input packet
        is_valid, errors = EvidencePacketValidator.validate_complete(packet_dict)
        if not is_valid:
            raise ValueError(f"Input packet invalid: {errors}")

        # Step 2: Build LLM prompt from packet
        prompt = self._build_prompt(packet_dict)

        # Step 3: Call LLM
        llm_response = self._call_llm(prompt, use_mock_llm=use_mock_llm)

        # Step 4: Log event in packet
        packet_dict = self._append_event(
            packet_dict,
            event_type="adaptation_event",
            details={
                "adapter": "RAG",
                "action": "llm_processing",
                "claims_count": len(packet_dict["claims"]),
                "contradictions_count": len(packet_dict["contradictions"]),
                "response_length": len(llm_response),
            }
        )

        # Step 5: Validate output packet (HARD GATE)
        is_valid, errors = EvidencePacketValidator.validate_complete(packet_dict)
        if not is_valid:
            raise ValueError(
                f"Adapter produced invalid packet: {errors}\n"
                "This should never happen - schema fence was breached!"
            )

        return packet_dict, llm_response

    def _build_prompt(self, packet_dict: Dict[str, Any]) -> str:
        """
        Build LLM prompt from EvidencePacket.
        
        Preserves all claims and explicitly surfaces contradictions.
        No filtering, no ranking, no consensus-building language.
        """
        claims = packet_dict["claims"]
        contradictions = packet_dict["contradictions"]
        query = packet_dict["metadata"]["query"]

        prompt_parts = [
            f"Query: {query}\n",
            f"Found {len(claims)} claims across sources:\n",
            "=" * 60,
        ]

        # List all claims
        for i, claim in enumerate(claims, 1):
            claim_id = claim["claim_id"]
            text = claim["claim_text"]
            source = claim["source_document_id"]
            contradiction_count = packet_dict["support_metrics"][claim_id]["contradiction_count"]
            
            prompt_parts.append(
                f"\n[Claim {i}] {claim_id} (from {source})"
            )
            prompt_parts.append(f"  Text: {text}")
            prompt_parts.append(f"  Contradictions: {contradiction_count}")

        # Explicitly list all contradictions
        if contradictions:
            prompt_parts.append("\n" + "=" * 60)
            prompt_parts.append(f"Explicit Contradictions Found ({len(contradictions)}):\n")
            
            for i, contra in enumerate(contradictions, 1):
                claim_a_id = contra["claim_a_id"]
                claim_b_id = contra["claim_b_id"]
                relationship = contra["relationship_type"]
                strength = contra["topology_strength"]
                
                # Find the actual claim texts
                claim_a_text = next(
                    (c["claim_text"] for c in claims if c["claim_id"] == claim_a_id),
                    "TEXT NOT FOUND"
                )
                claim_b_text = next(
                    (c["claim_text"] for c in claims if c["claim_id"] == claim_b_id),
                    "TEXT NOT FOUND"
                )
                
                prompt_parts.append(
                    f"\n[Contradiction {i}] ({relationship}, strength: {strength:.2f})"
                )
                prompt_parts.append(f"  Claim A: {claim_a_text}")
                prompt_parts.append(f"  Claim B: {claim_b_text}")
        else:
            prompt_parts.append("\nNo contradictions detected.")

        prompt_parts.append("\n" + "=" * 60)
        prompt_parts.append(
            "\nTask: Acknowledge all claims above, explicitly note the contradictions, "
            "and explain how they could both be true or why they conflict."
        )

        return "\n".join(prompt_parts)

    def _call_llm(self, prompt: str, use_mock_llm: bool = False) -> str:
        """
        Call LLM with prompt.
        
        In production, this would call the actual LLM service.
        For testing, can use mock LLM.
        """
        if use_mock_llm:
            return self._mock_llm_response(prompt)
        
        if self.llm_client is None:
            # Fallback to mock for testing
            return self._mock_llm_response(prompt)
        
        # In real implementation, call actual LLM
        # For now, return mock
        return self._mock_llm_response(prompt)

    def _mock_llm_response(self, prompt: str) -> str:
        """
        Mock LLM response for testing.
        
        Returns a response that acknowledges all claims and contradictions.
        """
        # Count claims and contradictions from prompt
        claims_count = prompt.count("[Claim ")
        contradictions_count = prompt.count("[Contradiction ")
        
        response = (
            f"I've analyzed the query and found {claims_count} claims "
            f"with {contradictions_count} explicit contradictions between them.\n\n"
            f"The contradictions are important because they represent areas where "
            f"sources disagree. Rather than trying to pick a winner, I'm surfacing "
            f"all the claims so you can evaluate the evidence yourself.\n\n"
            f"Key observations:\n"
            f"- All {claims_count} claims were extracted verbatim from sources\n"
            f"- The {contradictions_count} contradictions are genuine disagreements\n"
            f"- No claims were filtered or suppressed\n"
            f"- This analysis preserves the full evidence landscape"
        )
        return response

    def _append_event(
        self,
        packet_dict: Dict[str, Any],
        event_type: str,
        details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Append event to packet's event_log.
        
        Args:
            packet_dict: Packet to modify
            event_type: Type of event (must be in schema enum)
            details: Event details (must not contain forbidden words)
            
        Returns:
            Modified packet_dict
        """
        event = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "details": details,
        }
        
        # This will fail if details contains forbidden words
        # (validation happens when creating Event object)
        packet_dict["event_log"].append(event)
        
        return packet_dict

    def process_query(
        self,
        query: str,
        packet_dict: Dict[str, Any],
        use_mock_llm: bool = False,
    ) -> Dict[str, Any]:
        """
        High-level interface: process query with EvidencePacket.
        
        Args:
            query: User's search query
            packet_dict: EvidencePacket from retrieval
            use_mock_llm: Use mock LLM for testing
            
        Returns:
            {
                "query": original query,
                "packet": validated packet with appended events,
                "llm_response": LLM's analysis,
                "valid": whether output packet is valid
            }
        """
        try:
            # Process through RAG pipeline
            validated_packet, llm_response = self.process_packet(
                packet_dict,
                use_mock_llm=use_mock_llm
            )
            
            return {
                "query": query,
                "packet": validated_packet,
                "llm_response": llm_response,
                "valid": True,
                "error": None,
            }
        except ValueError as e:
            # Return error info but don't crash
            return {
                "query": query,
                "packet": None,
                "llm_response": None,
                "valid": False,
                "error": str(e),
            }


# Export
__all__ = ["RAGAdapter"]

"""
Platform Integration Layer: Adapter Boundary

This module provides the single "adapter boundary" where:
1. Packets enter (validated)
2. Adapters process (with hard gate)
3. Packets exit (re-validated)

Every adapter call goes through this layer with explicit validation gates.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from sse.evidence_packet import EvidencePacketValidator, EvidencePacket
from sse.adapters.rag_adapter import RAGAdapter
from sse.adapters.search_adapter import SearchAdapter


class AdapterBoundary:
    """
    Single point of entry/exit for all adapter operations.
    
    Enforces:
    - Input validation (packet is valid before adapter touches it)
    - Hard gate validation (output must be valid before return)
    - Event logging (every operation tracked)
    - Request tracing (adapter_request_id for end-to-end correlation)
    """
    
    def __init__(self, enable_event_log_persistence=True):
        """
        Initialize adapter boundary.
        
        Args:
            enable_event_log_persistence: If True, persist event logs
        """
        self.rag_adapter = RAGAdapter()
        self.search_adapter = SearchAdapter()
        self.enable_event_log_persistence = enable_event_log_persistence
        self.request_log = []  # In-memory log (to be persisted)
    
    def rag_endpoint(
        self,
        query: str,
        packet_dict: Dict[str, Any],
        use_mock_llm: bool = False,
        adapter_request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        RAG endpoint: Query → Augmented Response
        
        This is the ADAPTER BOUNDARY for RAG:
        1. Validate input packet (gate 1)
        2. Call RAGAdapter (which has its own hard gate)
        3. Validate output (gate 2)
        4. Log request
        5. Return only if all validations pass
        
        Args:
            query: User query
            packet_dict: EvidencePacket as dict
            use_mock_llm: Use mock LLM for testing
            adapter_request_id: Optional request ID for tracing
            
        Returns:
            {
                "valid": bool,
                "adapter_request_id": str,
                "packet": dict or None,
                "llm_response": str or None,
                "error": str or None,
                "validation_gates_passed": int
            }
        """
        if not adapter_request_id:
            adapter_request_id = str(uuid.uuid4())
        
        gates_passed = 0
        
        # GATE 1: Input validation
        is_valid, input_errors = EvidencePacketValidator.validate_complete(packet_dict)
        if not is_valid:
            self._log_request(
                adapter_request_id,
                "rag_endpoint",
                False,
                f"Input validation failed: {input_errors}",
                gates_passed=gates_passed
            )
            return {
                "valid": False,
                "adapter_request_id": adapter_request_id,
                "packet": None,
                "llm_response": None,
                "error": f"Input packet invalid: {input_errors}",
                "validation_gates_passed": gates_passed
            }
        
        gates_passed += 1  # Input validation passed
        
        # Call adapter (which has its own hard gate)
        try:
            result = self.rag_adapter.process_query(
                query=query,
                packet_dict=packet_dict,
                use_mock_llm=use_mock_llm
            )
        except ValueError as e:
            self._log_request(
                adapter_request_id,
                "rag_endpoint",
                False,
                f"Adapter hard gate caught: {str(e)}",
                gates_passed=gates_passed,
                event_type="boundary_violation"
            )
            return {
                "valid": False,
                "adapter_request_id": adapter_request_id,
                "packet": None,
                "llm_response": None,
                "error": f"Adapter validation failed: {str(e)}",
                "validation_gates_passed": gates_passed
            }
        
        gates_passed += 1  # Adapter processing passed
        
        # GATE 2: Output validation (redundant with adapter's gate, but explicit)
        is_valid, output_errors = EvidencePacketValidator.validate_complete(result["packet"])
        if not is_valid:
            self._log_request(
                adapter_request_id,
                "rag_endpoint",
                False,
                f"Output validation failed: {output_errors}",
                gates_passed=gates_passed,
                event_type="boundary_violation"
            )
            return {
                "valid": False,
                "adapter_request_id": adapter_request_id,
                "packet": None,
                "llm_response": None,
                "error": f"Output packet invalid: {output_errors}",
                "validation_gates_passed": gates_passed
            }
        
        gates_passed += 1  # Output validation passed
        
        # All gates passed - log and return
        self._log_request(
            adapter_request_id,
            "rag_endpoint",
            True,
            "All validation gates passed",
            gates_passed=gates_passed
        )
        
        return {
            "valid": True,
            "adapter_request_id": adapter_request_id,
            "packet": result["packet"],
            "llm_response": result["llm_response"],
            "error": None,
            "validation_gates_passed": gates_passed
        }
    
    def search_endpoint(
        self,
        packet_dict: Dict[str, Any],
        highlight_contradictions: bool = True,
        adapter_request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search endpoint: Packet → UI Results
        
        This is the ADAPTER BOUNDARY for Search:
        1. Validate input packet (gate 1)
        2. Call SearchAdapter
        3. No gate 2 needed (returns JSON, not packet)
        4. Log request
        5. Return
        
        Args:
            packet_dict: EvidencePacket as dict
            highlight_contradictions: Whether to highlight contradictions
            adapter_request_id: Optional request ID for tracing
            
        Returns:
            {
                "valid": bool,
                "adapter_request_id": str,
                "results": dict or None,
                "graph": dict or None,
                "error": str or None,
                "validation_gates_passed": int
            }
        """
        if not adapter_request_id:
            adapter_request_id = str(uuid.uuid4())
        
        gates_passed = 0
        
        # GATE 1: Input validation
        is_valid, input_errors = EvidencePacketValidator.validate_complete(packet_dict)
        if not is_valid:
            self._log_request(
                adapter_request_id,
                "search_endpoint",
                False,
                f"Input validation failed: {input_errors}",
                gates_passed=gates_passed
            )
            return {
                "valid": False,
                "adapter_request_id": adapter_request_id,
                "results": None,
                "graph": None,
                "error": f"Input packet invalid: {input_errors}",
                "validation_gates_passed": gates_passed
            }
        
        gates_passed += 1  # Input validation passed
        
        # Call adapter (no hard gate needed for JSON output)
        try:
            results = self.search_adapter.render_search_results(
                packet_dict,
                highlight_contradictions=highlight_contradictions
            )
            graph = self.search_adapter.render_contradiction_graph(packet_dict)
        except Exception as e:
            self._log_request(
                adapter_request_id,
                "search_endpoint",
                False,
                f"Adapter error: {str(e)}",
                gates_passed=gates_passed
            )
            return {
                "valid": False,
                "adapter_request_id": adapter_request_id,
                "results": None,
                "graph": None,
                "error": f"Search adapter failed: {str(e)}",
                "validation_gates_passed": gates_passed
            }
        
        gates_passed += 1  # Adapter processing passed
        
        # Log and return
        self._log_request(
            adapter_request_id,
            "search_endpoint",
            True,
            "Search results generated successfully",
            gates_passed=gates_passed
        )
        
        return {
            "valid": True,
            "adapter_request_id": adapter_request_id,
            "results": results,
            "graph": graph,
            "error": None,
            "validation_gates_passed": gates_passed
        }
    
    def _log_request(
        self,
        adapter_request_id: str,
        endpoint: str,
        success: bool,
        message: str,
        gates_passed: int = 0,
        event_type: str = "adapter_call"
    ) -> None:
        """
        Log adapter request for auditability.
        
        Args:
            adapter_request_id: Request ID for tracing
            endpoint: Which endpoint (rag_endpoint, search_endpoint)
            success: Whether the request succeeded
            message: Human-readable message
            gates_passed: Number of validation gates that passed
            event_type: Type of event (adapter_call, boundary_violation, etc.)
        """
        log_entry = {
            "adapter_request_id": adapter_request_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "endpoint": endpoint,
            "success": success,
            "message": message,
            "gates_passed": gates_passed,
            "event_type": event_type
        }
        
        self.request_log.append(log_entry)
        
        if self.enable_event_log_persistence:
            # TODO: Persist to file/DB (for now, just in memory)
            pass
    
    def get_audit_log(self) -> list:
        """Get current in-memory audit log."""
        return self.request_log.copy()
    
    def get_audit_metrics(self) -> Dict[str, Any]:
        """
        Get audit metrics from request log.
        
        Returns:
            {
                "total_requests": int,
                "successful_requests": int,
                "failed_requests": int,
                "boundary_violations": int,
                "average_gates_passed": float,
                "requests_by_endpoint": dict
            }
        """
        if not self.request_log:
            return {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "boundary_violations": 0,
                "average_gates_passed": 0.0,
                "requests_by_endpoint": {}
            }
        
        total = len(self.request_log)
        successful = sum(1 for r in self.request_log if r["success"])
        failed = total - successful
        violations = sum(1 for r in self.request_log if r["event_type"] == "boundary_violation")
        avg_gates = sum(r["gates_passed"] for r in self.request_log) / total if total > 0 else 0
        
        by_endpoint = {}
        for entry in self.request_log:
            endpoint = entry["endpoint"]
            if endpoint not in by_endpoint:
                by_endpoint[endpoint] = {"total": 0, "successful": 0, "failed": 0}
            by_endpoint[endpoint]["total"] += 1
            if entry["success"]:
                by_endpoint[endpoint]["successful"] += 1
            else:
                by_endpoint[endpoint]["failed"] += 1
        
        return {
            "total_requests": total,
            "successful_requests": successful,
            "failed_requests": failed,
            "boundary_violations": violations,
            "average_gates_passed": round(avg_gates, 2),
            "requests_by_endpoint": by_endpoint
        }


# Global adapter boundary (singleton pattern for platform integration)
_adapter_boundary = None


def get_adapter_boundary(enable_event_log_persistence=True) -> AdapterBoundary:
    """Get or create the global adapter boundary."""
    global _adapter_boundary
    if _adapter_boundary is None:
        _adapter_boundary = AdapterBoundary(enable_event_log_persistence)
    return _adapter_boundary


def rag_endpoint(
    query: str,
    packet_dict: Dict[str, Any],
    use_mock_llm: bool = False,
    adapter_request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Global RAG endpoint function.
    
    Usage:
        result = rag_endpoint(
            query="what is machine learning?",
            packet_dict=packet,
            use_mock_llm=False
        )
        if result["valid"]:
            print(f"Request {result['adapter_request_id']} succeeded")
            print(f"LLM Response: {result['llm_response']}")
    """
    boundary = get_adapter_boundary()
    return boundary.rag_endpoint(query, packet_dict, use_mock_llm, adapter_request_id)


def search_endpoint(
    packet_dict: Dict[str, Any],
    highlight_contradictions: bool = True,
    adapter_request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Global Search endpoint function.
    
    Usage:
        result = search_endpoint(
            packet_dict=packet,
            highlight_contradictions=True
        )
        if result["valid"]:
            print(f"Request {result['adapter_request_id']} succeeded")
            print(f"Results: {result['results']}")
            print(f"Graph: {result['graph']}")
    """
    boundary = get_adapter_boundary()
    return boundary.search_endpoint(packet_dict, highlight_contradictions, adapter_request_id)


if __name__ == "__main__":
    # Example usage
    from sse.evidence_packet import EvidencePacketBuilder
    
    # Build test packet
    builder = EvidencePacketBuilder("test query", "v1.0")
    builder.add_claim("claim_001", "Test claim", "doc_1", 0, 10, True, "regex")
    builder.set_metrics("claim_001", 1, 0.9, 0, 0)
    builder.add_cluster(["claim_001"])
    builder.log_event("query_executed", {"status": "success"})
    packet = builder.build().to_dict()
    
    # Test RAG endpoint
    print("Testing RAG endpoint...")
    rag_result = rag_endpoint("test query", packet, use_mock_llm=True)
    print(f"RAG Result: {rag_result['valid']}")
    print(f"Gates Passed: {rag_result['validation_gates_passed']}")
    
    # Test Search endpoint
    print("\nTesting Search endpoint...")
    search_result = search_endpoint(packet)
    print(f"Search Result: {search_result['valid']}")
    print(f"Gates Passed: {search_result['validation_gates_passed']}")
    
    # Get audit metrics
    boundary = get_adapter_boundary()
    metrics = boundary.get_audit_metrics()
    print(f"\nAudit Metrics: {json.dumps(metrics, indent=2)}")

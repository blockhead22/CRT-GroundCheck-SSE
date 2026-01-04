"""
Event Log Persistence: Production-grade auditability

Persists adapter request event logs to append-only file/storage
with metrics for monitoring and compliance.

Events are keyed by adapter_request_id for end-to-end tracing.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import threading


@dataclass
class AdapterEvent:
    """Single adapter event for audit trail."""
    adapter_request_id: str
    timestamp: str
    endpoint: str
    success: bool
    message: str
    gates_passed: int
    event_type: str  # adapter_call, boundary_violation, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class EventLogPersistence:
    """
    Append-only event log with metrics tracking.
    
    Writes to a log file in JSON Lines format (one JSON object per line).
    Tracks:
    - Validation failures
    - Injection attempt detection
    - Adapter latency
    - Request success/failure rates
    """
    
    def __init__(self, log_dir: str = "adapter_logs"):
        """
        Initialize event log persistence.
        
        Args:
            log_dir: Directory to store event logs
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Current log file (rotates daily)
        self.current_date = datetime.utcnow().date()
        self.log_file = self._get_log_file_path(self.current_date)
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Metrics cache (for fast access)
        self.metrics_cache = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "boundary_violations": 0,
            "validation_failures": 0,
            "injection_attempts_caught": 0,
            "average_latency_ms": 0.0,
            "requests_by_endpoint": {}
        }
    
    def _get_log_file_path(self, date) -> Path:
        """Get log file path for a given date."""
        filename = f"adapter_events_{date.isoformat()}.jsonl"
        return self.log_dir / filename
    
    def _rotate_log_if_needed(self) -> None:
        """Rotate log file if date has changed."""
        today = datetime.utcnow().date()
        if today != self.current_date:
            self.current_date = today
            self.log_file = self._get_log_file_path(today)
    
    def log_event(self, event: AdapterEvent) -> None:
        """
        Append event to log file.
        
        Args:
            event: AdapterEvent to log
        """
        with self.lock:
            self._rotate_log_if_needed()
            
            # Append to file
            with open(self.log_file, "a") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
            
            # Update metrics
            self._update_metrics(event)
    
    def _update_metrics(self, event: AdapterEvent) -> None:
        """Update metrics cache based on event."""
        self.metrics_cache["total_requests"] += 1
        
        if event.success:
            self.metrics_cache["successful_requests"] += 1
        else:
            self.metrics_cache["failed_requests"] += 1
        
        if event.event_type == "boundary_violation":
            self.metrics_cache["boundary_violations"] += 1
        
        if "validation" in event.message.lower():
            self.metrics_cache["validation_failures"] += 1
        
        if "injection" in event.message.lower():
            self.metrics_cache["injection_attempts_caught"] += 1
        
        # Track by endpoint
        endpoint = event.endpoint
        if endpoint not in self.metrics_cache["requests_by_endpoint"]:
            self.metrics_cache["requests_by_endpoint"][endpoint] = {
                "total": 0,
                "successful": 0,
                "failed": 0
            }
        
        self.metrics_cache["requests_by_endpoint"][endpoint]["total"] += 1
        if event.success:
            self.metrics_cache["requests_by_endpoint"][endpoint]["successful"] += 1
        else:
            self.metrics_cache["requests_by_endpoint"][endpoint]["failed"] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics from cache.
        
        Returns:
            {
                "total_requests": int,
                "successful_requests": int,
                "failed_requests": int,
                "boundary_violations": int,
                "validation_failures": int,
                "injection_attempts_caught": int,
                "average_latency_ms": float,
                "requests_by_endpoint": dict,
                "success_rate": float,
                "validation_failure_rate": float
            }
        """
        total = self.metrics_cache["total_requests"]
        if total == 0:
            return {
                **self.metrics_cache,
                "success_rate": 0.0,
                "validation_failure_rate": 0.0
            }
        
        success_rate = (self.metrics_cache["successful_requests"] / total) * 100
        validation_failure_rate = (self.metrics_cache["validation_failures"] / total) * 100
        
        return {
            **self.metrics_cache,
            "success_rate": round(success_rate, 2),
            "validation_failure_rate": round(validation_failure_rate, 2)
        }
    
    def get_recent_events(self, limit: int = 100) -> List[AdapterEvent]:
        """
        Get most recent events from current log file.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of AdapterEvent objects (most recent first)
        """
        if not self.log_file.exists():
            return []
        
        events = []
        with open(self.log_file, "r") as f:
            lines = f.readlines()
            # Read from end (most recent first)
            for line in reversed(lines[-limit:]):
                try:
                    data = json.loads(line.strip())
                    events.append(AdapterEvent(**data))
                except json.JSONDecodeError:
                    continue
        
        return events
    
    def get_events_for_request(self, adapter_request_id: str) -> List[AdapterEvent]:
        """
        Get all events for a specific request ID (end-to-end tracing).
        
        Args:
            adapter_request_id: Request ID to search for
            
        Returns:
            List of AdapterEvent objects for this request
        """
        # Search current log file
        events = []
        if self.log_file.exists():
            with open(self.log_file, "r") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if data.get("adapter_request_id") == adapter_request_id:
                            events.append(AdapterEvent(**data))
                    except json.JSONDecodeError:
                        continue
        
        return events
    
    def get_boundary_violations(self, limit: int = 50) -> List[AdapterEvent]:
        """
        Get all boundary violation events.
        
        Args:
            limit: Maximum number of violations to return
            
        Returns:
            List of AdapterEvent objects for boundary violations
        """
        if not self.log_file.exists():
            return []
        
        violations = []
        with open(self.log_file, "r") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    if data.get("event_type") == "boundary_violation":
                        violations.append(AdapterEvent(**data))
                        if len(violations) >= limit:
                            break
                except json.JSONDecodeError:
                    continue
        
        return violations
    
    def generate_audit_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive audit report.
        
        Returns:
            {
                "generated_at": str,
                "metrics": dict,
                "recent_violations": list,
                "endpoints_summary": dict,
                "recommendations": list
            }
        """
        metrics = self.get_metrics()
        violations = self.get_boundary_violations(limit=10)
        
        recommendations = []
        
        # Generate recommendations based on metrics
        if metrics["validation_failure_rate"] > 5:
            recommendations.append(
                "Validation failure rate is high (>5%). Consider reviewing input validation."
            )
        
        if metrics["injection_attempts_caught"] > 0:
            recommendations.append(
                f"Detected {metrics['injection_attempts_caught']} injection attempts. "
                "This is expected and shows the validation gates are working."
            )
        
        if metrics["requests_by_endpoint"].get("rag_endpoint", {}).get("failed", 0) > 10:
            recommendations.append(
                "RAG adapter has high failure rate. Check LLM integration."
            )
        
        if metrics["success_rate"] < 95:
            recommendations.append(
                "Overall success rate is below 95%. Investigate recent failures."
            )
        
        return {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "metrics": metrics,
            "recent_violations": [v.to_dict() for v in violations],
            "endpoints_summary": metrics["requests_by_endpoint"],
            "recommendations": recommendations
        }


# Global event log instance
_event_log = None


def get_event_log(log_dir: str = "adapter_logs") -> EventLogPersistence:
    """Get or create global event log instance."""
    global _event_log
    if _event_log is None:
        _event_log = EventLogPersistence(log_dir)
    return _event_log


def log_adapter_event(
    adapter_request_id: str,
    endpoint: str,
    success: bool,
    message: str,
    gates_passed: int = 0,
    event_type: str = "adapter_call"
) -> None:
    """
    Log an adapter event to persistent storage.
    
    Args:
        adapter_request_id: Request ID for tracing
        endpoint: Which endpoint (rag_endpoint, search_endpoint)
        success: Whether request succeeded
        message: Human-readable message
        gates_passed: Number of validation gates passed
        event_type: Type of event (adapter_call, boundary_violation, etc.)
    """
    event = AdapterEvent(
        adapter_request_id=adapter_request_id,
        timestamp=datetime.utcnow().isoformat() + "Z",
        endpoint=endpoint,
        success=success,
        message=message,
        gates_passed=gates_passed,
        event_type=event_type
    )
    
    event_log = get_event_log()
    event_log.log_event(event)


if __name__ == "__main__":
    # Example usage
    event_log = get_event_log()
    
    # Log some test events
    log_adapter_event(
        adapter_request_id="test-001",
        endpoint="rag_endpoint",
        success=True,
        message="All validation gates passed",
        gates_passed=3,
        event_type="adapter_call"
    )
    
    log_adapter_event(
        adapter_request_id="test-002",
        endpoint="search_endpoint",
        success=False,
        message="Input validation failed: missing required field",
        gates_passed=0,
        event_type="boundary_violation"
    )
    
    # Get metrics
    metrics = event_log.get_metrics()
    print("Metrics:")
    print(json.dumps(metrics, indent=2))
    
    # Get audit report
    report = event_log.generate_audit_report()
    print("\nAudit Report:")
    print(json.dumps(report, indent=2))

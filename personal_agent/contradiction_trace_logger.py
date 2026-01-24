"""
Contradiction Resolution Trace Logger

This module provides detailed trace logging for contradiction resolution events.
Logs are timestamped, include pattern match info, and track ledger state changes
for easier debugging and future research.

Features:
- Timestamped event logging
- Pattern match details
- Before/after ledger state tracking
- Human-readable format
- Configurable log levels and output
"""

import logging
import time
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path


class ContradictionTraceLogger:
    """
    Dedicated logger for contradiction resolution events.
    
    Provides structured, detailed logging of:
    - Contradiction detection
    - Pattern matching
    - Resolution decisions
    - Ledger state changes
    """
    
    def __init__(
        self,
        log_file: Optional[str] = None,
        console_output: bool = True,
        log_level: int = logging.DEBUG
    ):
        """
        Initialize trace logger.
        
        Args:
            log_file: Path to log file (None = no file logging)
            console_output: Whether to also log to console
            log_level: Logging level (DEBUG, INFO, WARNING, etc.)
        """
        self.logger = logging.getLogger("crt.contradiction_trace")
        self.logger.setLevel(log_level)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # File handler
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(log_level)
            
            # Detailed format for file logging
            file_formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        
        # Console handler
        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)  # Less verbose for console
            
            console_formatter = logging.Formatter(
                '%(levelname)-8s | %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
    
    def log_contradiction_detected(
        self,
        ledger_id: str,
        old_memory_id: str,
        new_memory_id: str,
        old_text: str,
        new_text: str,
        drift_mean: float,
        contradiction_type: str,
        affected_slots: Optional[List[str]] = None
    ):
        """
        Log when a contradiction is detected.
        
        Args:
            ledger_id: Unique identifier for this contradiction
            old_memory_id: ID of the old/existing memory
            new_memory_id: ID of the new/conflicting memory
            old_text: Text of the old memory
            new_text: Text of the new memory
            drift_mean: Semantic drift measurement
            contradiction_type: Type of contradiction (CONFLICT, REVISION, etc.)
            affected_slots: List of fact slots affected by this contradiction
        """
        slots_str = ", ".join(affected_slots) if affected_slots else "none"
        
        self.logger.info(f"=== CONTRADICTION DETECTED ===")
        self.logger.info(f"Ledger ID: {ledger_id}")
        self.logger.info(f"Type: {contradiction_type}")
        self.logger.info(f"Drift: {drift_mean:.4f}")
        self.logger.info(f"Affected Slots: {slots_str}")
        self.logger.debug(f"Old Memory [{old_memory_id}]: {old_text[:100]}")
        self.logger.debug(f"New Memory [{new_memory_id}]: {new_text[:100]}")
    
    def log_resolution_attempt(
        self,
        user_text: str,
        matched_patterns: List[Dict[str, Any]],
        open_contradictions_count: int
    ):
        """
        Log when user input triggers resolution attempt.
        
        Args:
            user_text: User's input text
            matched_patterns: List of matched resolution patterns
            open_contradictions_count: Number of open contradictions
        """
        self.logger.info(f"=== RESOLUTION ATTEMPT ===")
        self.logger.info(f"User Input: {user_text[:150]}")
        self.logger.info(f"Open Contradictions: {open_contradictions_count}")
        
        if matched_patterns:
            self.logger.info(f"Matched Patterns ({len(matched_patterns)}):")
            for i, pattern_info in enumerate(matched_patterns[:3], 1):  # Show max 3
                self.logger.info(f"  {i}. Pattern: {pattern_info.get('pattern', 'unknown')[:50]}")
                self.logger.info(f"     Match: '{pattern_info.get('match', '')}'")
    
    def log_resolution_matched(
        self,
        ledger_id: str,
        contradiction_type: str,
        slot_name: Optional[str],
        old_value: Any,
        new_value: Any,
        chosen_value: Any,
        resolution_method: str
    ):
        """
        Log when a contradiction is matched for resolution.
        
        Args:
            ledger_id: Contradiction ledger ID
            contradiction_type: Type of contradiction
            slot_name: Fact slot being resolved (if applicable)
            old_value: Old/existing value
            new_value: New/conflicting value
            chosen_value: Value chosen by user
            resolution_method: How it was resolved (user_chose_old, user_chose_new, etc.)
        """
        self.logger.info(f"=== RESOLUTION MATCHED ===")
        self.logger.info(f"Ledger ID: {ledger_id}")
        self.logger.info(f"Type: {contradiction_type}")
        
        if slot_name:
            self.logger.info(f"Slot: {slot_name}")
            self.logger.info(f"  Old Value: {old_value}")
            self.logger.info(f"  New Value: {new_value}")
            self.logger.info(f"  Chosen: {chosen_value}")
        
        self.logger.info(f"Resolution Method: {resolution_method}")
    
    def log_ledger_update(
        self,
        ledger_id: str,
        before_status: str,
        after_status: str,
        resolution_method: str,
        chosen_memory_id: Optional[str] = None
    ):
        """
        Log ledger state change.
        
        Args:
            ledger_id: Contradiction ledger ID
            before_status: Status before update
            after_status: Status after update
            resolution_method: Resolution method applied
            chosen_memory_id: Memory ID that was chosen (if applicable)
        """
        self.logger.info(f"=== LEDGER UPDATE ===")
        self.logger.info(f"Ledger ID: {ledger_id}")
        self.logger.info(f"Status: {before_status} -> {after_status}")
        self.logger.info(f"Method: {resolution_method}")
        
        if chosen_memory_id:
            self.logger.info(f"Chosen Memory: {chosen_memory_id}")
    
    def log_resolution_complete(
        self,
        ledger_id: str,
        success: bool,
        details: Optional[str] = None
    ):
        """
        Log completion of resolution process.
        
        Args:
            ledger_id: Contradiction ledger ID
            success: Whether resolution was successful
            details: Additional details about the resolution
        """
        status = "SUCCESS" if success else "FAILED"
        
        self.logger.info(f"=== RESOLUTION {status} ===")
        self.logger.info(f"Ledger ID: {ledger_id}")
        
        if details:
            self.logger.info(f"Details: {details}")
    
    def log_resolution_summary(
        self,
        total_open_before: int,
        total_open_after: int,
        resolved_count: int,
        elapsed_time: float
    ):
        """
        Log summary of resolution session.
        
        Args:
            total_open_before: Open contradictions before resolution
            total_open_after: Open contradictions after resolution
            resolved_count: Number of contradictions resolved
            elapsed_time: Time taken in seconds
        """
        self.logger.info(f"=== RESOLUTION SUMMARY ===")
        self.logger.info(f"Open Before: {total_open_before}")
        self.logger.info(f"Open After: {total_open_after}")
        self.logger.info(f"Resolved: {resolved_count}")
        self.logger.info(f"Time: {elapsed_time:.3f}s")
    
    def log_pattern_statistics(
        self,
        pattern_usage: Dict[str, int],
        total_resolutions: int
    ):
        """
        Log statistics about pattern usage.
        
        Args:
            pattern_usage: Dict mapping patterns to usage count
            total_resolutions: Total number of resolutions
        """
        self.logger.info(f"=== PATTERN STATISTICS ===")
        self.logger.info(f"Total Resolutions: {total_resolutions}")
        
        if pattern_usage:
            self.logger.info("Most Used Patterns:")
            sorted_patterns = sorted(
                pattern_usage.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            for pattern, count in sorted_patterns[:10]:  # Top 10
                percentage = (count / total_resolutions * 100) if total_resolutions > 0 else 0
                self.logger.info(f"  {pattern[:50]}: {count} ({percentage:.1f}%)")


# Global instance (can be configured)
_global_trace_logger: Optional[ContradictionTraceLogger] = None


def get_trace_logger(
    log_file: Optional[str] = "ai_logs/contradiction_trace.log",
    console_output: bool = False,
    log_level: int = logging.INFO
) -> ContradictionTraceLogger:
    """
    Get or create the global trace logger.
    
    Args:
        log_file: Path to log file (None = no file logging)
        console_output: Whether to also log to console
        log_level: Logging level
        
    Returns:
        ContradictionTraceLogger instance
    """
    global _global_trace_logger
    
    if _global_trace_logger is None:
        _global_trace_logger = ContradictionTraceLogger(
            log_file=log_file,
            console_output=console_output,
            log_level=log_level
        )
    
    return _global_trace_logger


def configure_trace_logging(
    enabled: bool = True,
    log_file: Optional[str] = "ai_logs/contradiction_trace.log",
    console_output: bool = False,
    log_level: int = logging.INFO
):
    """
    Configure global trace logging settings.
    
    Args:
        enabled: Whether trace logging is enabled
        log_file: Path to log file
        console_output: Whether to also log to console
        log_level: Logging level
    """
    global _global_trace_logger
    
    if enabled:
        _global_trace_logger = ContradictionTraceLogger(
            log_file=log_file,
            console_output=console_output,
            log_level=log_level
        )
    else:
        _global_trace_logger = None

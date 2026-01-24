"""
Test contradiction trace logging.

Tests that the trace logger:
1. Creates logs with proper format
2. Captures all required information
3. Can be configured
4. Works end-to-end
"""

import pytest
import tempfile
import os
from pathlib import Path
from personal_agent.contradiction_trace_logger import (
    ContradictionTraceLogger,
    get_trace_logger,
    configure_trace_logging
)


@pytest.fixture
def temp_log_file(tmp_path):
    """Create a temporary log file"""
    return str(tmp_path / "test_trace.log")


@pytest.fixture
def trace_logger(temp_log_file):
    """Create a trace logger with temp file"""
    return ContradictionTraceLogger(
        log_file=temp_log_file,
        console_output=False
    )


class TestTraceLoggerCreation:
    """Test trace logger initialization"""
    
    def test_create_with_file(self, temp_log_file):
        """Test creating logger with file output"""
        logger = ContradictionTraceLogger(
            log_file=temp_log_file,
            console_output=False
        )
        
        assert logger is not None
        assert Path(temp_log_file).parent.exists()
    
    def test_create_without_file(self):
        """Test creating logger without file output"""
        logger = ContradictionTraceLogger(
            log_file=None,
            console_output=False
        )
        
        assert logger is not None
    
    def test_create_with_console(self):
        """Test creating logger with console output"""
        logger = ContradictionTraceLogger(
            log_file=None,
            console_output=True
        )
        
        assert logger is not None


class TestContradictionLogging:
    """Test contradiction event logging"""
    
    def test_log_contradiction_detected(self, trace_logger, temp_log_file):
        """Test logging contradiction detection"""
        trace_logger.log_contradiction_detected(
            ledger_id="test_123",
            old_memory_id="mem_old",
            new_memory_id="mem_new",
            old_text="I work at Microsoft",
            new_text="I work at Google",
            drift_mean=0.85,
            contradiction_type="CONFLICT",
            affected_slots=["employer"]
        )
        
        # Check that log file was created and has content
        assert Path(temp_log_file).exists()
        content = Path(temp_log_file).read_text()
        
        assert "CONTRADICTION DETECTED" in content
        assert "test_123" in content
        assert "CONFLICT" in content
        assert "employer" in content
    
    def test_log_resolution_attempt(self, trace_logger, temp_log_file):
        """Test logging resolution attempt"""
        matched_patterns = [
            {
                'pattern': r'\b(is|was)\s+(correct|right)',
                'match': 'is correct',
                'groups': ('is', 'correct'),
                'start': 7,
                'end': 17
            }
        ]
        
        trace_logger.log_resolution_attempt(
            user_text="Google is correct",
            matched_patterns=matched_patterns,
            open_contradictions_count=3
        )
        
        content = Path(temp_log_file).read_text()
        
        assert "RESOLUTION ATTEMPT" in content
        assert "Google is correct" in content
        assert "Open Contradictions: 3" in content
    
    def test_log_resolution_matched(self, trace_logger, temp_log_file):
        """Test logging resolution match"""
        trace_logger.log_resolution_matched(
            ledger_id="test_456",
            contradiction_type="CONFLICT",
            slot_name="employer",
            old_value="Microsoft",
            new_value="Google",
            chosen_value="Google",
            resolution_method="user_chose_new"
        )
        
        content = Path(temp_log_file).read_text()
        
        assert "RESOLUTION MATCHED" in content
        assert "test_456" in content
        assert "employer" in content
        assert "Microsoft" in content
        assert "Google" in content
    
    def test_log_ledger_update(self, trace_logger, temp_log_file):
        """Test logging ledger state change"""
        trace_logger.log_ledger_update(
            ledger_id="test_789",
            before_status="open",
            after_status="resolved",
            resolution_method="nl_resolution",
            chosen_memory_id="mem_123"
        )
        
        content = Path(temp_log_file).read_text()
        
        assert "LEDGER UPDATE" in content
        assert "test_789" in content
        assert "open -> resolved" in content
        assert "nl_resolution" in content
    
    def test_log_resolution_complete(self, trace_logger, temp_log_file):
        """Test logging resolution completion"""
        trace_logger.log_resolution_complete(
            ledger_id="test_999",
            success=True,
            details="Resolved successfully"
        )
        
        content = Path(temp_log_file).read_text()
        
        assert "RESOLUTION SUCCESS" in content
        assert "test_999" in content
        assert "Resolved successfully" in content
    
    def test_log_resolution_summary(self, trace_logger, temp_log_file):
        """Test logging resolution summary"""
        trace_logger.log_resolution_summary(
            total_open_before=5,
            total_open_after=2,
            resolved_count=3,
            elapsed_time=0.123
        )
        
        content = Path(temp_log_file).read_text()
        
        assert "RESOLUTION SUMMARY" in content
        assert "Open Before: 5" in content
        assert "Open After: 2" in content
        assert "Resolved: 3" in content
        assert "0.123" in content


class TestLogFormatting:
    """Test log format and readability"""
    
    def test_timestamp_format(self, trace_logger, temp_log_file):
        """Test that timestamps are properly formatted"""
        trace_logger.log_contradiction_detected(
            ledger_id="test",
            old_memory_id="old",
            new_memory_id="new",
            old_text="old text",
            new_text="new text",
            drift_mean=0.5,
            contradiction_type="CONFLICT"
        )
        
        content = Path(temp_log_file).read_text()
        
        # Should have timestamp in format YYYY-MM-DD HH:MM:SS
        import re
        timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
        assert re.search(timestamp_pattern, content)
    
    def test_log_levels(self, trace_logger, temp_log_file):
        """Test that log levels are included"""
        trace_logger.log_contradiction_detected(
            ledger_id="test",
            old_memory_id="old",
            new_memory_id="new",
            old_text="old text",
            new_text="new text",
            drift_mean=0.5,
            contradiction_type="CONFLICT"
        )
        
        content = Path(temp_log_file).read_text()
        
        # Should have INFO level markers
        assert "INFO" in content
    
    def test_human_readable_format(self, trace_logger, temp_log_file):
        """Test that logs are human-readable"""
        trace_logger.log_contradiction_detected(
            ledger_id="contradiction_001",
            old_memory_id="mem_old_123",
            new_memory_id="mem_new_456",
            old_text="I work at Microsoft",
            new_text="I work at Google",
            drift_mean=0.85,
            contradiction_type="CONFLICT",
            affected_slots=["employer"]
        )
        
        content = Path(temp_log_file).read_text()
        
        # Should be well-structured with clear labels
        assert "Ledger ID:" in content
        assert "Type:" in content
        assert "Drift:" in content
        assert "Affected Slots:" in content


class TestGlobalLogger:
    """Test global logger instance"""
    
    def test_get_trace_logger_creates_instance(self, temp_log_file):
        """Test that get_trace_logger creates instance"""
        # Clear global instance first
        import personal_agent.contradiction_trace_logger as module
        module._global_trace_logger = None
        
        logger = get_trace_logger(
            log_file=temp_log_file,
            console_output=False
        )
        
        assert logger is not None
    
    def test_get_trace_logger_returns_same_instance(self, temp_log_file):
        """Test that get_trace_logger returns same instance"""
        # Clear global instance first
        import personal_agent.contradiction_trace_logger as module
        module._global_trace_logger = None
        
        logger1 = get_trace_logger(log_file=temp_log_file)
        logger2 = get_trace_logger(log_file=temp_log_file)
        
        assert logger1 is logger2
    
    def test_configure_trace_logging(self, temp_log_file):
        """Test configuring global trace logging"""
        configure_trace_logging(
            enabled=True,
            log_file=temp_log_file,
            console_output=False
        )
        
        logger = get_trace_logger()
        assert logger is not None
    
    def test_configure_trace_logging_disabled(self):
        """Test disabling trace logging"""
        configure_trace_logging(enabled=False)
        
        import personal_agent.contradiction_trace_logger as module
        assert module._global_trace_logger is None


class TestEndToEndLogging:
    """Test complete logging workflow"""
    
    def test_full_resolution_flow(self, trace_logger, temp_log_file):
        """Test logging a complete resolution flow"""
        # 1. Detect contradiction
        trace_logger.log_contradiction_detected(
            ledger_id="flow_001",
            old_memory_id="mem_old",
            new_memory_id="mem_new",
            old_text="I work at Microsoft",
            new_text="I work at Google",
            drift_mean=0.85,
            contradiction_type="CONFLICT",
            affected_slots=["employer"]
        )
        
        # 2. Resolution attempt
        trace_logger.log_resolution_attempt(
            user_text="Google is correct",
            matched_patterns=[{'pattern': 'test', 'match': 'is correct'}],
            open_contradictions_count=1
        )
        
        # 3. Resolution matched
        trace_logger.log_resolution_matched(
            ledger_id="flow_001",
            contradiction_type="CONFLICT",
            slot_name="employer",
            old_value="Microsoft",
            new_value="Google",
            chosen_value="Google",
            resolution_method="user_chose_new"
        )
        
        # 4. Ledger update
        trace_logger.log_ledger_update(
            ledger_id="flow_001",
            before_status="open",
            after_status="resolved",
            resolution_method="nl_resolution",
            chosen_memory_id="mem_new"
        )
        
        # 5. Resolution complete
        trace_logger.log_resolution_complete(
            ledger_id="flow_001",
            success=True,
            details="Chose Google"
        )
        
        # 6. Summary
        trace_logger.log_resolution_summary(
            total_open_before=1,
            total_open_after=0,
            resolved_count=1,
            elapsed_time=0.05
        )
        
        # Verify complete log
        content = Path(temp_log_file).read_text()
        
        assert "CONTRADICTION DETECTED" in content
        assert "RESOLUTION ATTEMPT" in content
        assert "RESOLUTION MATCHED" in content
        assert "LEDGER UPDATE" in content
        assert "RESOLUTION SUCCESS" in content
        assert "RESOLUTION SUMMARY" in content
        
        # Should appear in chronological order
        assert content.index("CONTRADICTION DETECTED") < content.index("RESOLUTION ATTEMPT")
        assert content.index("RESOLUTION ATTEMPT") < content.index("RESOLUTION MATCHED")
        assert content.index("RESOLUTION MATCHED") < content.index("LEDGER UPDATE")
        assert content.index("LEDGER UPDATE") < content.index("RESOLUTION SUCCESS")

# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""Tests for debug logging module."""

from pathlib import Path
import tempfile

from workspace_os.debug_logging import (
    DebugLogger,
    LogLevel,
    OperationTimer,
    CycleSummary,
)


def test_debug_logger_disabled_mode():
    """Test that disabled logger does not write files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        logger = DebugLogger(log_dir=log_dir, enabled=False)

        logger.debug("This should not be logged")
        logger.info("Neither should this")

        assert logger.log_file is None
        assert logger.log_handle is None
        assert len(list(log_dir.iterdir())) == 0


def test_debug_logger_creates_log_file():
    """Test that enabled logger creates log file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        logger = DebugLogger(log_dir=log_dir, enabled=True, stream_to_stdout=False)

        assert logger.log_file is not None
        assert logger.log_file.exists()
        assert logger.log_file.name.startswith("cycle-")
        assert logger.log_file.suffix == ".log"

        logger.close()


def test_debug_logger_writes_messages():
    """Test that logger writes messages to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        logger = DebugLogger(log_dir=log_dir, enabled=True, stream_to_stdout=False)

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warn("Warning message")
        logger.error("Error message")

        logger.close()

        log_content = logger.log_file.read_text()
        assert "DEBUG" in log_content
        assert "Debug message" in log_content
        assert "INFO" in log_content
        assert "Info message" in log_content
        assert "WARN" in log_content
        assert "Warning message" in log_content
        assert "ERROR" in log_content
        assert "Error message" in log_content


def test_debug_logger_log_level_filtering():
    """Test that logger respects minimum log level."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        logger = DebugLogger(
            log_dir=log_dir,
            enabled=True,
            stream_to_stdout=False,
            min_level=LogLevel.INFO,
        )

        logger.debug("Should not appear")
        logger.info("Should appear")
        logger.warn("Should also appear")

        logger.close()

        log_content = logger.log_file.read_text()
        assert "Should not appear" not in log_content
        assert "Should appear" in log_content
        assert "Should also appear" in log_content


def test_debug_logger_context_fields():
    """Test that logger includes context fields in messages."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        logger = DebugLogger(log_dir=log_dir, enabled=True, stream_to_stdout=False)

        logger.info(
            "Work assigned",
            agent_name="opencode",
            work_item_id="123",
            operation_type="assignment",
        )

        logger.close()

        log_content = logger.log_file.read_text()
        assert "agent=opencode" in log_content
        assert "item=123" in log_content
        assert "op=assignment" in log_content
        assert "Work assigned" in log_content


def test_operation_timer():
    """Test operation timer functionality."""
    timer = OperationTimer(
        operation_type="test_operation",
        agent_name="opencode",
        work_item_id="456",
    )

    assert timer.operation_type == "test_operation"
    assert timer.agent_name == "opencode"
    assert timer.work_item_id == "456"
    assert timer.ended_at is None

    duration = timer.end()

    assert timer.ended_at is not None
    assert duration >= 0
    assert timer.duration_seconds() == duration


def test_debug_logger_start_end_operation():
    """Test start and end operation tracking."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        logger = DebugLogger(log_dir=log_dir, enabled=True, stream_to_stdout=False)

        timer = logger.start_operation(
            "git_commit",
            agent_name="opencode",
            work_item_id="789",
        )

        logger.end_operation(timer, status="success")
        logger.close()

        log_content = logger.log_file.read_text()
        assert "Starting git_commit" in log_content
        assert "Completed git_commit" in log_content
        assert "status" in log_content
        assert "success" in log_content


def test_debug_logger_queue_state():
    """Test queue state logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        logger = DebugLogger(log_dir=log_dir, enabled=True, stream_to_stdout=False)

        logger.log_queue_state(
            queue_depth=5,
            active_workers=3,
            pending_items=2,
            utilization_pct=75.0,
        )

        logger.close()

        log_content = logger.log_file.read_text()
        assert "Queue state" in log_content
        assert "depth=5" in log_content
        assert "active=3" in log_content
        assert "pending=2" in log_content


def test_debug_logger_checkpoint():
    """Test checkpoint logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        logger = DebugLogger(log_dir=log_dir, enabled=True, stream_to_stdout=False)

        logger.log_checkpoint(
            checkpoint_id=1,
            passed=True,
            reason="all checks passed",
        )

        logger.log_checkpoint(
            checkpoint_id=2,
            passed=False,
            reason="failing: security:sql_injection",
        )

        logger.close()

        log_content = logger.log_file.read_text()
        assert "Checkpoint 1: PASS" in log_content
        assert "all checks passed" in log_content
        assert "Checkpoint 2: FAIL" in log_content
        assert "failing: security:sql_injection" in log_content


def test_debug_logger_work_item_assignment():
    """Test work item assignment logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        logger = DebugLogger(log_dir=log_dir, enabled=True, stream_to_stdout=False)

        logger.log_work_item_assignment(
            work_item_id="work-1",
            agent_name="claude",
            role="primary",
        )

        logger.close()

        log_content = logger.log_file.read_text()
        assert "Assigned work item to agent" in log_content
        assert "agent=claude" in log_content
        assert "item=work-1" in log_content


def test_debug_logger_work_item_complete():
    """Test work item completion logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        logger = DebugLogger(log_dir=log_dir, enabled=True, stream_to_stdout=False)

        logger.log_work_item_complete(
            work_item_id="work-2",
            outcome="success",
            duration_seconds=12.5,
            agent_name="opencode",
        )

        logger.close()

        log_content = logger.log_file.read_text()
        assert "Work item completed: success" in log_content
        assert "12.5" in log_content or "12.50" in log_content


def test_cycle_summary_accumulation():
    """Test cycle summary accumulates data correctly."""
    summary = CycleSummary()

    summary.add_operation_time("git_commit", 5.0)
    summary.add_operation_time("git_commit", 3.0)
    summary.add_operation_time("api_call", 2.0)

    summary.add_agent_time("opencode", 10.0)
    summary.add_agent_time("claude", 8.0)

    summary.add_work_item_outcome("success")
    summary.add_work_item_outcome("success")
    summary.add_work_item_outcome("failure")

    summary.api_call_count = 15

    assert summary.time_by_operation["git_commit"] == 8.0
    assert summary.time_by_operation["api_call"] == 2.0
    assert summary.time_by_agent["opencode"] == 10.0
    assert summary.time_by_agent["claude"] == 8.0
    assert summary.work_items_by_outcome["success"] == 2
    assert summary.work_items_by_outcome["failure"] == 1
    assert summary.api_call_count == 15


def test_cycle_summary_render():
    """Test cycle summary rendering."""
    summary = CycleSummary()
    summary.total_duration_seconds = 100.0
    summary.add_operation_time("git_commit", 30.0)
    summary.add_operation_time("api_call", 20.0)
    summary.add_agent_time("opencode", 50.0)
    summary.add_agent_time("claude", 40.0)
    summary.add_work_item_outcome("success")
    summary.add_work_item_outcome("failure")
    summary.api_call_count = 25

    rendered = summary.render()

    assert "Cycle Debug Summary" in rendered
    assert "Total Duration: 100.00s" in rendered
    assert "git_commit: 30.00s (30.0%)" in rendered
    assert "api_call: 20.00s (20.0%)" in rendered
    assert "opencode: 50.00s (50.0%)" in rendered
    assert "claude: 40.00s (40.0%)" in rendered
    assert "success: 1" in rendered
    assert "failure: 1" in rendered
    assert "API Calls: 25" in rendered


def test_debug_logger_summary_written_on_close():
    """Test that summary is written to log file on close."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        logger = DebugLogger(log_dir=log_dir, enabled=True, stream_to_stdout=False)

        logger.log_work_item_complete(
            work_item_id="1",
            outcome="success",
            duration_seconds=10.0,
        )

        logger.get_summary(total_duration=50.0)
        logger.close()

        log_content = logger.log_file.read_text()
        assert "Cycle Debug Summary" in log_content
        assert "Total Duration" in log_content


def test_debug_logger_context_manager():
    """Test debug logger as context manager."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)

        with DebugLogger(log_dir=log_dir, enabled=True, stream_to_stdout=False) as logger:
            logger.info("Inside context")
            log_file = logger.log_file

        # After context exit, file should be closed and summary written
        assert log_file.exists()
        log_content = log_file.read_text()
        assert "Inside context" in log_content
        assert "Cycle Debug Summary" in log_content

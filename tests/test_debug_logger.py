# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""Tests for debug logging functionality."""

import tempfile
from pathlib import Path
from workspace_os.debug_logger import (
    DebugLogger,
    NullDebugLogger,
    OperationType,
    create_debug_logger,
)


def test_debug_logger_creates_log_file():
    """Test that debug logger creates a log file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / ".workspace-os" / "debug-logs"
        logger = DebugLogger(log_dir, "test-cycle", enabled=True)

        assert log_dir.exists()
        assert logger.log_file.exists()
        assert logger.log_file.name.startswith("cycle-test-cycle-")


def test_debug_logger_logs_entries():
    """Test that debug logger writes log entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / ".workspace-os" / "debug-logs"
        logger = DebugLogger(log_dir, "test-cycle", enabled=True)

        logger.info(OperationType.AGENT_ASSIGNMENT, "Test message", agent_name="opencode")
        logger.debug(OperationType.QUEUE_STATE, "Queue state", queue_depth=5)
        logger.error(OperationType.WORK_ITEM, "Work item failed", work_item_id="123")

        # Read log file and verify entries
        log_content = logger.log_file.read_text(encoding="utf-8")
        assert "INFO" in log_content
        assert "DEBUG" in log_content
        assert "ERROR" in log_content
        assert "Test message" in log_content
        assert "agent=opencode" in log_content
        assert "Queue state" in log_content
        assert "Work item failed" in log_content


def test_debug_logger_finalize_generates_summary():
    """Test that finalize generates a summary report."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / ".workspace-os" / "debug-logs"
        logger = DebugLogger(log_dir, "test-cycle", enabled=True)

        logger.info(OperationType.AGENT_ASSIGNMENT, "Agent assigned", agent_name="opencode", duration_seconds=10.0)
        logger.info(OperationType.WORK_ITEM, "Work completed", agent_name="opencode", duration_seconds=20.0, outcome="success")
        logger.info(OperationType.CHECKPOINT, "Checkpoint recorded", passed=True)

        summary = logger.finalize()

        assert "Cycle Debug Summary" in summary
        assert "agent_assignment" in summary
        assert "work_item" in summary
        assert "opencode" in summary
        assert "30.00s" in summary  # Total duration for opencode


def test_null_debug_logger_is_noop():
    """Test that NullDebugLogger does nothing."""
    logger = NullDebugLogger()

    # Should not raise any errors
    logger.info(OperationType.OTHER, "Test message")
    logger.debug(OperationType.QUEUE_STATE, "Queue state")
    logger.error(OperationType.WORK_ITEM, "Error")

    summary = logger.finalize()
    assert summary == ""


def test_create_debug_logger_factory():
    """Test the create_debug_logger factory function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace_root = Path(tmpdir)

        # Test enabled debug logger
        logger = create_debug_logger(workspace_root, "test-cycle", enabled=True)
        assert isinstance(logger, DebugLogger)
        assert logger.enabled

        # Test disabled debug logger
        null_logger = create_debug_logger(workspace_root, "test-cycle", enabled=False)
        assert isinstance(null_logger, NullDebugLogger)


def test_debug_logger_summary_tracks_outcomes():
    """Test that summary tracks work item outcomes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / ".workspace-os" / "debug-logs"
        logger = DebugLogger(log_dir, "test-cycle", enabled=True)

        logger.info(OperationType.WORK_ITEM, "Work 1", outcome="success")
        logger.info(OperationType.WORK_ITEM, "Work 2", outcome="success")
        logger.info(OperationType.WORK_ITEM, "Work 3", outcome="failed")

        summary = logger.finalize()

        assert "Work Items by Outcome:" in summary
        assert "success: 2" in summary
        assert "failed: 1" in summary


def test_debug_logger_summary_tracks_api_calls():
    """Test that summary tracks API calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / ".workspace-os" / "debug-logs"
        logger = DebugLogger(log_dir, "test-cycle", enabled=True)

        logger.info(OperationType.API_CALL, "Call 1")
        logger.info(OperationType.API_CALL, "Call 2")
        logger.info(OperationType.API_CALL, "Call 3")

        summary = logger.finalize()

        assert "API Calls: 3" in summary


def test_debug_logger_summary_tracks_checkpoints():
    """Test that summary tracks checkpoints."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / ".workspace-os" / "debug-logs"
        logger = DebugLogger(log_dir, "test-cycle", enabled=True)

        logger.info(OperationType.CHECKPOINT, "Checkpoint 1")
        logger.info(OperationType.CHECKPOINT, "Checkpoint 2")

        summary = logger.finalize()

        assert "Checkpoints: 2" in summary

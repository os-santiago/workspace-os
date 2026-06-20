"""Tests for progress tracking module."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from workspace_os.progress import (
    BatchProgressTracker,
    ProgressConfig,
    ProgressTracker,
    SimpleProgressLogger,
    batch_progress,
    configure_progress,
    is_progress_enabled,
    progress,
)


def test_progress_config_defaults():
    """Test default progress configuration."""
    config = ProgressConfig()
    assert config.enabled is True
    assert config.show_eta is True
    assert config.show_percentage is True
    assert config.show_elapsed is True
    assert config.refresh_per_second == 10


def test_configure_progress():
    """Test configuring progress settings."""
    # Save original state
    original_enabled = is_progress_enabled()

    try:
        configure_progress(enabled=False)
        # Note: is_progress_enabled() also checks RICH_AVAILABLE
        # So we just verify the function doesn't error

        configure_progress(
            enabled=True,
            show_eta=False,
            show_percentage=False,
            show_elapsed=False,
            refresh_per_second=5,
        )

        # Verify we can call with various combinations
        configure_progress(show_eta=True)
        configure_progress(refresh_per_second=20)

    finally:
        # Restore original state
        configure_progress(enabled=original_enabled)


@pytest.mark.skipif(
    not is_progress_enabled(),
    reason="Rich library not available or progress disabled",
)
def test_progress_tracker_determinate():
    """Test progress tracker with known total."""
    with progress("Test operation", total=10) as tracker:
        assert tracker.description == "Test operation"
        assert tracker.total == 10

        for i in range(10):
            tracker.update()

        tracker.complete()


@pytest.mark.skipif(
    not is_progress_enabled(),
    reason="Rich library not available or progress disabled",
)
def test_progress_tracker_indeterminate():
    """Test progress tracker without known total."""
    with progress("Indeterminate operation") as tracker:
        assert tracker.description == "Indeterminate operation"
        assert tracker.total is None

        for i in range(5):
            tracker.update()


@pytest.mark.skipif(
    not is_progress_enabled(),
    reason="Rich library not available or progress disabled",
)
def test_progress_tracker_update_description():
    """Test updating progress description."""
    with progress("Initial description", total=5) as tracker:
        tracker.update(description="Updated description")
        assert tracker.description == "Initial description"  # Original doesn't change


@pytest.mark.skipif(
    not is_progress_enabled(),
    reason="Rich library not available or progress disabled",
)
def test_progress_tracker_set_total():
    """Test setting total after initialization."""
    with progress("Test operation") as tracker:
        assert tracker.total is None
        tracker.set_total(20)
        assert tracker.total == 20

        for i in range(20):
            tracker.update()

        tracker.complete()


@pytest.mark.skipif(
    not is_progress_enabled(),
    reason="Rich library not available or progress disabled",
)
def test_batch_progress_tracker():
    """Test batch progress tracking."""
    with batch_progress() as tracker:
        tracker.add_task("task1", "First task", total=10)
        tracker.add_task("task2", "Second task", total=5)

        for i in range(10):
            tracker.update("task1")

        for i in range(5):
            tracker.update("task2")

        tracker.complete("task1")
        tracker.complete("task2")


@pytest.mark.skipif(
    not is_progress_enabled(),
    reason="Rich library not available or progress disabled",
)
def test_batch_progress_update_description():
    """Test updating description in batch progress."""
    with batch_progress() as tracker:
        tracker.add_task("task1", "Initial", total=5)
        tracker.update("task1", advance=1, description="Updated")


@pytest.mark.skipif(
    not is_progress_enabled(),
    reason="Rich library not available or progress disabled",
)
def test_batch_progress_duplicate_task():
    """Test adding duplicate task to batch progress."""
    with batch_progress() as tracker:
        tracker.add_task("task1", "First", total=5)
        tracker.add_task("task1", "Duplicate", total=10)  # Should be ignored

        # Should still work with original task
        tracker.update("task1")


def test_progress_tracker_disabled():
    """Test progress tracker when disabled."""
    configure_progress(enabled=False)

    try:
        tracker = ProgressTracker("Test", total=10)
        with tracker:
            tracker.update()
            tracker.update(advance=5)
            tracker.set_total(20)
            tracker.complete()
        # Should complete without errors even when disabled

    finally:
        configure_progress(enabled=True)


def test_batch_progress_tracker_disabled():
    """Test batch progress tracker when disabled."""
    configure_progress(enabled=False)

    try:
        tracker = BatchProgressTracker()
        with tracker:
            tracker.add_task("task1", "Test", total=10)
            tracker.update("task1")
            tracker.complete("task1")
        # Should complete without errors even when disabled

    finally:
        configure_progress(enabled=True)


def test_simple_progress_logger():
    """Test simple progress logger fallback."""
    logger = SimpleProgressLogger("Test operation", total=100)

    # First update will log (first time)
    with patch("builtins.print") as mock_print:
        logger.update()
        assert mock_print.called

    # Second update within interval should not log
    with patch("builtins.print") as mock_print:
        logger.update()
        mock_print.assert_not_called()

    # Force log by manipulating time
    logger._last_log_time = 0  # Reset to force log
    with patch("builtins.print") as mock_print:
        logger.update(advance=10)
        assert mock_print.called

    logger.complete()


def test_simple_progress_logger_indeterminate():
    """Test simple progress logger without total."""
    logger = SimpleProgressLogger("Indeterminate operation")

    logger._last_log_time = 0  # Force log
    with patch("builtins.print") as mock_print:
        logger.update()
        # Check that it logged something
        assert mock_print.called

    logger.complete()


def test_simple_progress_logger_update_description():
    """Test updating description in simple progress logger."""
    logger = SimpleProgressLogger("Initial", total=10)

    logger.update(description="Updated")
    assert logger.description == "Updated"


@pytest.mark.skipif(
    not is_progress_enabled(),
    reason="Rich library not available or progress disabled",
)
def test_progress_context_manager():
    """Test progress as context manager."""
    with progress("Context manager test", total=3) as tracker:
        tracker.update()
        tracker.update()
        tracker.update()


@pytest.mark.skipif(
    not is_progress_enabled(),
    reason="Rich library not available or progress disabled",
)
def test_batch_progress_context_manager():
    """Test batch progress as context manager."""
    with batch_progress() as tracker:
        tracker.add_task("a", "Task A", total=2)
        tracker.add_task("b", "Task B", total=2)
        tracker.update("a")
        tracker.update("b")


def test_progress_tracker_exception_handling():
    """Test that progress tracker handles exceptions gracefully."""
    try:
        with progress("Exception test", total=5) as tracker:
            tracker.update()
            raise ValueError("Test exception")
    except ValueError:
        pass  # Exception should propagate but tracker should clean up


def test_batch_progress_tracker_exception_handling():
    """Test that batch progress tracker handles exceptions gracefully."""
    try:
        with batch_progress() as tracker:
            tracker.add_task("test", "Test", total=5)
            tracker.update("test")
            raise ValueError("Test exception")
    except ValueError:
        pass  # Exception should propagate but tracker should clean up


@pytest.mark.skipif(
    not is_progress_enabled(),
    reason="Rich library not available or progress disabled",
)
def test_progress_tracker_advance_multiple():
    """Test advancing progress by multiple steps."""
    with progress("Multi-step test", total=100) as tracker:
        tracker.update(advance=10)
        tracker.update(advance=25)
        tracker.update(advance=15)
        # Total advanced: 50/100


@pytest.mark.skipif(
    not is_progress_enabled(),
    reason="Rich library not available or progress disabled",
)
def test_batch_progress_update_nonexistent_task():
    """Test updating a task that doesn't exist."""
    with batch_progress() as tracker:
        # Should not raise an error
        tracker.update("nonexistent_task")
        tracker.complete("nonexistent_task")

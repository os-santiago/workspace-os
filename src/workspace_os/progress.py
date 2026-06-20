"""Progress tracking and ETA utilities for long-running commands.

This module provides a rich-based progress bar system with automatic ETA calculation
for all long-running workspace operations.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

try:
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskID,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


@dataclass
class ProgressConfig:
    """Configuration for progress display."""

    enabled: bool = True
    show_eta: bool = True
    show_percentage: bool = True
    show_elapsed: bool = True
    refresh_per_second: int = 10


# Global progress configuration
_config = ProgressConfig()


def configure_progress(
    enabled: bool | None = None,
    show_eta: bool | None = None,
    show_percentage: bool | None = None,
    show_elapsed: bool | None = None,
    refresh_per_second: int | None = None,
) -> None:
    """Configure global progress display settings.

    Args:
        enabled: Whether to show progress bars at all
        show_eta: Whether to show estimated time remaining
        show_percentage: Whether to show percentage complete
        show_elapsed: Whether to show elapsed time
        refresh_per_second: How many times per second to refresh the display
    """
    global _config
    if enabled is not None:
        _config.enabled = enabled
    if show_eta is not None:
        _config.show_eta = show_eta
    if show_percentage is not None:
        _config.show_percentage = show_percentage
    if show_elapsed is not None:
        _config.show_elapsed = show_elapsed
    if refresh_per_second is not None:
        _config.refresh_per_second = refresh_per_second


def is_progress_enabled() -> bool:
    """Check if progress tracking is enabled."""
    return _config.enabled and RICH_AVAILABLE


class ProgressTracker:
    """Manages progress bars for long-running operations."""

    def __init__(self, description: str, total: int | None = None):
        """Initialize a progress tracker.

        Args:
            description: Description of the operation
            total: Total number of steps (None for indeterminate progress)
        """
        self.description = description
        self.total = total
        self._progress: Progress | None = None
        self._task_id: TaskID | None = None
        self._console: Console | None = None
        self._enabled = is_progress_enabled()

    def __enter__(self) -> ProgressTracker:
        """Start the progress tracker."""
        if not self._enabled:
            return self

        columns = [
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
        ]

        if self.total is not None:
            # Determinate progress with known total
            if _config.show_percentage:
                columns.append(BarColumn())
                columns.append("[progress.percentage]{task.percentage:>3.0f}%")
            columns.append(MofNCompleteColumn())
            if _config.show_eta:
                columns.append(TimeRemainingColumn())

        if _config.show_elapsed:
            columns.append(TimeElapsedColumn())

        self._console = Console()
        self._progress = Progress(*columns, refresh_per_second=_config.refresh_per_second)
        self._progress.__enter__()

        self._task_id = self._progress.add_task(
            self.description,
            total=self.total if self.total is not None else None,
        )

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop the progress tracker."""
        if self._progress is not None:
            self._progress.__exit__(exc_type, exc_val, exc_tb)
            self._progress = None
            self._task_id = None
            self._console = None

    def update(self, advance: int = 1, description: str | None = None) -> None:
        """Update progress by advancing the counter.

        Args:
            advance: Number of steps to advance
            description: Optional new description
        """
        if not self._enabled or self._progress is None or self._task_id is None:
            return

        kwargs = {"advance": advance}
        if description is not None:
            kwargs["description"] = description

        self._progress.update(self._task_id, **kwargs)

    def set_total(self, total: int) -> None:
        """Set or update the total number of steps.

        Args:
            total: New total
        """
        if not self._enabled or self._progress is None or self._task_id is None:
            return

        self.total = total
        self._progress.update(self._task_id, total=total)

    def complete(self) -> None:
        """Mark the operation as complete."""
        if not self._enabled or self._progress is None or self._task_id is None:
            return

        if self.total is not None:
            self._progress.update(self._task_id, completed=self.total)


@contextmanager
def progress(description: str, total: int | None = None) -> Iterator[ProgressTracker]:
    """Context manager for progress tracking.

    Args:
        description: Description of the operation
        total: Total number of steps (None for indeterminate progress)

    Yields:
        ProgressTracker instance

    Example:
        >>> with progress("Processing items", total=100) as tracker:
        ...     for i in range(100):
        ...         # Do work
        ...         tracker.update()
    """
    tracker = ProgressTracker(description, total)
    with tracker:
        yield tracker


class BatchProgressTracker:
    """Manages multiple concurrent progress bars."""

    def __init__(self):
        """Initialize a batch progress tracker."""
        self._progress: Progress | None = None
        self._tasks: dict[str, TaskID] = {}
        self._console: Console | None = None
        self._enabled = is_progress_enabled()

    def __enter__(self) -> BatchProgressTracker:
        """Start the batch progress tracker."""
        if not self._enabled:
            return self

        columns = [
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
        ]

        if _config.show_percentage:
            columns.append(BarColumn())
            columns.append("[progress.percentage]{task.percentage:>3.0f}%")

        columns.append(MofNCompleteColumn())

        if _config.show_eta:
            columns.append(TimeRemainingColumn())

        if _config.show_elapsed:
            columns.append(TimeElapsedColumn())

        self._console = Console()
        self._progress = Progress(*columns, refresh_per_second=_config.refresh_per_second)
        self._progress.__enter__()

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop the batch progress tracker."""
        if self._progress is not None:
            self._progress.__exit__(exc_type, exc_val, exc_tb)
            self._progress = None
            self._tasks = {}
            self._console = None

    def add_task(self, task_id: str, description: str, total: int | None = None) -> None:
        """Add a new task to track.

        Args:
            task_id: Unique identifier for the task
            description: Description of the task
            total: Total number of steps (None for indeterminate)
        """
        if not self._enabled or self._progress is None:
            return

        if task_id in self._tasks:
            return

        progress_task_id = self._progress.add_task(description, total=total)
        self._tasks[task_id] = progress_task_id

    def update(self, task_id: str, advance: int = 1, description: str | None = None) -> None:
        """Update progress for a specific task.

        Args:
            task_id: ID of the task to update
            advance: Number of steps to advance
            description: Optional new description
        """
        if not self._enabled or self._progress is None or task_id not in self._tasks:
            return

        kwargs = {"advance": advance}
        if description is not None:
            kwargs["description"] = description

        self._progress.update(self._tasks[task_id], **kwargs)

    def complete(self, task_id: str) -> None:
        """Mark a task as complete.

        Args:
            task_id: ID of the task to complete
        """
        if not self._enabled or self._progress is None or task_id not in self._tasks:
            return

        task = self._progress._tasks[self._tasks[task_id]]
        if task.total is not None:
            self._progress.update(self._tasks[task_id], completed=task.total)


@contextmanager
def batch_progress() -> Iterator[BatchProgressTracker]:
    """Context manager for batch progress tracking.

    Yields:
        BatchProgressTracker instance

    Example:
        >>> with batch_progress() as tracker:
        ...     tracker.add_task("task1", "Processing A", total=50)
        ...     tracker.add_task("task2", "Processing B", total=30)
        ...     for i in range(50):
        ...         tracker.update("task1")
        ...     for i in range(30):
        ...         tracker.update("task2")
    """
    tracker = BatchProgressTracker()
    with tracker:
        yield tracker


class SimpleProgressLogger:
    """Fallback progress logger when rich is not available."""

    def __init__(self, description: str, total: int | None = None):
        """Initialize a simple progress logger.

        Args:
            description: Description of the operation
            total: Total number of steps
        """
        self.description = description
        self.total = total
        self.current = 0
        self.start_time = time.time()
        self._last_log_time = 0.0
        self._log_interval = 5.0  # Log every 5 seconds

    def update(self, advance: int = 1, description: str | None = None) -> None:
        """Update progress.

        Args:
            advance: Number of steps to advance
            description: Optional new description
        """
        self.current += advance
        current_time = time.time()

        # Only log periodically to avoid spam
        if current_time - self._last_log_time < self._log_interval:
            return

        self._last_log_time = current_time

        if description:
            self.description = description

        elapsed = current_time - self.start_time

        if self.total is not None and self.total > 0:
            percentage = (self.current / self.total) * 100
            eta = ((elapsed / self.current) * (self.total - self.current)) if self.current > 0 else 0
            print(f"{self.description}: {self.current}/{self.total} ({percentage:.1f}%) - ETA: {eta:.0f}s")
        else:
            print(f"{self.description}: {self.current} items - Elapsed: {elapsed:.0f}s")

    def complete(self) -> None:
        """Mark the operation as complete."""
        elapsed = time.time() - self.start_time
        if self.total is not None:
            print(f"{self.description}: Complete ({self.total}/{self.total}) - Total time: {elapsed:.1f}s")
        else:
            print(f"{self.description}: Complete ({self.current} items) - Total time: {elapsed:.1f}s")

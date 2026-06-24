# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""Debug logging module for detailed cycle work traceability."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import json
from typing import Any


class LogLevel(Enum):
    """Log levels for debug output."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


@dataclass
class OperationTimer:
    """Track operation timing and metadata."""
    operation_type: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    agent_name: str | None = None
    work_item_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def end(self) -> float:
        """Mark operation as ended and return duration in seconds."""
        self.ended_at = datetime.now(timezone.utc)
        return self.duration_seconds()

    def duration_seconds(self) -> float:
        """Return duration in seconds."""
        if self.ended_at is None:
            return 0.0
        return (self.ended_at - self.started_at).total_seconds()


@dataclass
class CycleSummary:
    """Summary statistics for a cycle run."""
    time_by_operation: dict[str, float] = field(default_factory=dict)
    time_by_agent: dict[str, float] = field(default_factory=dict)
    work_items_by_outcome: dict[str, int] = field(default_factory=dict)
    api_call_count: int = 0
    total_duration_seconds: float = 0.0

    def add_operation_time(self, operation_type: str, duration: float) -> None:
        """Add time for an operation type."""
        self.time_by_operation[operation_type] = (
            self.time_by_operation.get(operation_type, 0.0) + duration
        )

    def add_agent_time(self, agent_name: str, duration: float) -> None:
        """Add time for an agent."""
        self.time_by_agent[agent_name] = (
            self.time_by_agent.get(agent_name, 0.0) + duration
        )

    def add_work_item_outcome(self, outcome: str) -> None:
        """Track work item outcome."""
        self.work_items_by_outcome[outcome] = (
            self.work_items_by_outcome.get(outcome, 0) + 1
        )

    def render(self) -> str:
        """Render summary as formatted text."""
        lines = [
            "\n=== Cycle Debug Summary ===",
            f"Total Duration: {self.total_duration_seconds:.2f}s",
            "\nTime by Operation Type:",
        ]
        for op_type, duration in sorted(
            self.time_by_operation.items(), key=lambda x: x[1], reverse=True
        ):
            pct = (duration / self.total_duration_seconds * 100) if self.total_duration_seconds > 0 else 0
            lines.append(f"  {op_type}: {duration:.2f}s ({pct:.1f}%)")

        lines.append("\nTime by Agent:")
        for agent, duration in sorted(
            self.time_by_agent.items(), key=lambda x: x[1], reverse=True
        ):
            pct = (duration / self.total_duration_seconds * 100) if self.total_duration_seconds > 0 else 0
            lines.append(f"  {agent}: {duration:.2f}s ({pct:.1f}%)")

        lines.append("\nWork Items by Outcome:")
        for outcome, count in sorted(self.work_items_by_outcome.items()):
            lines.append(f"  {outcome}: {count}")

        lines.append(f"\nAPI Calls: {self.api_call_count}")
        lines.append("=" * 27)

        return "\n".join(lines)


class DebugLogger:
    """
    Debug logger for cycle work operations.

    Logs detailed information about cycle execution including:
    - Operation timing (git, API calls, file I/O)
    - Agent assignments per work item
    - Queue state changes
    - Checkpoint pass/fail reasons

    Logs are written to .workspace-os/debug-logs/cycle-{timestamp}.log
    and optionally streamed to stdout.
    """

    def __init__(
        self,
        log_dir: Path | None = None,
        enabled: bool = True,
        stream_to_stdout: bool = True,
        min_level: LogLevel = LogLevel.DEBUG,
    ):
        self.enabled = enabled
        self.stream_to_stdout = stream_to_stdout
        self.min_level = min_level
        self.summary = CycleSummary()
        self.log_file: Path | None = None
        self.log_handle = None

        if self.enabled:
            if log_dir is None:
                log_dir = Path(".workspace-os/debug-logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            self.log_file = log_dir / f"cycle-{timestamp}.log"
            self.log_handle = self.log_file.open("w", encoding="utf-8")
            self._write_header()

    def _write_header(self) -> None:
        """Write log file header."""
        if not self.enabled or not self.log_handle:
            return
        header = f"=== Workspace OS Cycle Debug Log ===\nStarted: {datetime.now(timezone.utc).isoformat()}\n\n"
        self.log_handle.write(header)
        self.log_handle.flush()

    def log(
        self,
        level: LogLevel,
        message: str,
        *,
        agent_name: str | None = None,
        work_item_id: str | None = None,
        operation_type: str | None = None,
        **metadata: Any,
    ) -> None:
        """
        Log a message with context.

        Args:
            level: Log level
            message: Log message
            agent_name: Optional agent name
            work_item_id: Optional work item ID
            operation_type: Optional operation type
            **metadata: Additional metadata to include
        """
        if not self.enabled:
            return

        # Check log level
        level_priority = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3}
        if level_priority.get(level.value, 0) < level_priority.get(self.min_level.value, 0):
            return

        timestamp = datetime.now(timezone.utc).isoformat()
        context_parts = []
        if agent_name:
            context_parts.append(f"agent={agent_name}")
        if work_item_id:
            context_parts.append(f"item={work_item_id}")
        if operation_type:
            context_parts.append(f"op={operation_type}")

        context = f"[{', '.join(context_parts)}]" if context_parts else ""

        log_line = f"[{timestamp}] {level.value:5} {context:30} {message}"

        if metadata:
            meta_str = json.dumps(metadata, default=str)
            log_line += f" {meta_str}"

        log_line += "\n"

        if self.log_handle:
            self.log_handle.write(log_line)
            self.log_handle.flush()

        if self.stream_to_stdout:
            print(log_line, end="")

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log at DEBUG level."""
        self.log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log at INFO level."""
        self.log(LogLevel.INFO, message, **kwargs)

    def warn(self, message: str, **kwargs: Any) -> None:
        """Log at WARN level."""
        self.log(LogLevel.WARN, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log at ERROR level."""
        self.log(LogLevel.ERROR, message, **kwargs)

    def start_operation(
        self,
        operation_type: str,
        *,
        agent_name: str | None = None,
        work_item_id: str | None = None,
        **metadata: Any,
    ) -> OperationTimer:
        """
        Start tracking an operation.

        Returns an OperationTimer that should be ended when the operation completes.
        """
        timer = OperationTimer(
            operation_type=operation_type,
            agent_name=agent_name,
            work_item_id=work_item_id,
            metadata=metadata,
        )
        self.debug(
            f"Starting {operation_type}",
            agent_name=agent_name,
            work_item_id=work_item_id,
            operation_type=operation_type,
            **metadata,
        )
        return timer

    def end_operation(self, timer: OperationTimer, **metadata: Any) -> None:
        """
        End an operation and record its duration.

        Args:
            timer: OperationTimer from start_operation
            **metadata: Additional metadata to log (e.g., outcome, error)
        """
        duration = timer.end()
        self.debug(
            f"Completed {timer.operation_type} in {duration:.2f}s",
            agent_name=timer.agent_name,
            work_item_id=timer.work_item_id,
            operation_type=timer.operation_type,
            duration_seconds=duration,
            **{**timer.metadata, **metadata},
        )

        # Update summary
        self.summary.add_operation_time(timer.operation_type, duration)
        if timer.agent_name:
            self.summary.add_agent_time(timer.agent_name, duration)

    def log_queue_state(
        self,
        queue_depth: int,
        active_workers: int,
        pending_items: int,
        **metadata: Any,
    ) -> None:
        """Log queue state transition."""
        self.debug(
            f"Queue state: depth={queue_depth}, active={active_workers}, pending={pending_items}",
            operation_type="queue_state",
            queue_depth=queue_depth,
            active_workers=active_workers,
            pending_items=pending_items,
            **metadata,
        )

    def log_checkpoint(
        self,
        checkpoint_id: int,
        passed: bool,
        reason: str,
        **metadata: Any,
    ) -> None:
        """Log checkpoint result."""
        level = LogLevel.INFO if passed else LogLevel.WARN
        self.log(
            level,
            f"Checkpoint {checkpoint_id}: {'PASS' if passed else 'FAIL'} - {reason}",
            operation_type="checkpoint",
            checkpoint_id=checkpoint_id,
            passed=passed,
            **metadata,
        )

    def log_work_item_assignment(
        self,
        work_item_id: str,
        agent_name: str,
        **metadata: Any,
    ) -> None:
        """Log work item assignment to agent."""
        self.info(
            "Assigned work item to agent",
            agent_name=agent_name,
            work_item_id=work_item_id,
            operation_type="assignment",
            **metadata,
        )

    def log_work_item_complete(
        self,
        work_item_id: str,
        outcome: str,
        duration_seconds: float,
        **metadata: Any,
    ) -> None:
        """Log work item completion."""
        self.info(
            f"Work item completed: {outcome} in {duration_seconds:.2f}s",
            work_item_id=work_item_id,
            operation_type="work_complete",
            outcome=outcome,
            duration_seconds=duration_seconds,
            **metadata,
        )
        self.summary.add_work_item_outcome(outcome)

    def log_api_call(
        self,
        endpoint: str,
        duration_seconds: float,
        **metadata: Any,
    ) -> None:
        """Log API call."""
        self.debug(
            f"API call to {endpoint} took {duration_seconds:.2f}s",
            operation_type="api_call",
            endpoint=endpoint,
            duration_seconds=duration_seconds,
            **metadata,
        )
        self.summary.api_call_count += 1

    def get_summary(self, total_duration: float | None = None) -> CycleSummary:
        """Get the current cycle summary."""
        if total_duration is not None:
            self.summary.total_duration_seconds = total_duration
        return self.summary

    def close(self) -> None:
        """Close the log file and write summary."""
        if not self.enabled:
            return

        if self.log_handle:
            summary_text = self.summary.render()
            self.log_handle.write(f"\n{summary_text}\n")
            self.log_handle.close()
            self.log_handle = None

        if self.stream_to_stdout:
            print(self.summary.render())

    def __enter__(self) -> DebugLogger:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

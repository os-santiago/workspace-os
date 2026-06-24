# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""Debug logging for workspace-os cycle work operations."""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class LogLevel(Enum):
    """Log levels for debug logging."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class OperationType(Enum):
    """Types of operations tracked in debug logs."""
    GIT_OPERATION = "git"
    API_CALL = "api"
    FILE_IO = "file_io"
    AGENT_ASSIGNMENT = "agent_assignment"
    QUEUE_STATE = "queue_state"
    CHECKPOINT = "checkpoint"
    WORK_ITEM = "work_item"
    OTHER = "other"


@dataclass
class DebugLogEntry:
    """A single debug log entry with structured context."""
    timestamp: datetime
    level: LogLevel
    operation_type: OperationType
    message: str
    agent_name: str | None = None
    work_item_id: str | None = None
    duration_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_log_line(self) -> str:
        """Format entry as a single log line."""
        parts = [
            self.timestamp.isoformat(),
            self.level.value,
            self.operation_type.value,
        ]

        if self.agent_name:
            parts.append(f"agent={self.agent_name}")
        if self.work_item_id:
            parts.append(f"work_item={self.work_item_id}")
        if self.duration_seconds is not None:
            parts.append(f"duration={self.duration_seconds:.3f}s")

        parts.append(self.message)

        if self.metadata:
            metadata_str = " ".join(f"{k}={v}" for k, v in self.metadata.items())
            parts.append(f"({metadata_str})")

        return " | ".join(parts)


@dataclass
class CycleSummary:
    """Summary statistics for a cycle's debug session."""
    total_duration_seconds: float = 0.0
    operation_time: dict[OperationType, float] = field(default_factory=lambda: defaultdict(float))
    agent_time: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    work_items_by_outcome: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    api_call_count: int = 0
    checkpoint_count: int = 0

    def add_entry(self, entry: DebugLogEntry) -> None:
        """Add an entry to the summary statistics."""
        if entry.duration_seconds:
            self.operation_time[entry.operation_type] += entry.duration_seconds
            if entry.agent_name:
                self.agent_time[entry.agent_name] += entry.duration_seconds

        if entry.operation_type == OperationType.API_CALL:
            self.api_call_count += 1
        elif entry.operation_type == OperationType.CHECKPOINT:
            self.checkpoint_count += 1
        elif entry.operation_type == OperationType.WORK_ITEM:
            outcome = entry.metadata.get("outcome", "unknown")
            self.work_items_by_outcome[outcome] += 1

    def to_report(self) -> str:
        """Generate a formatted summary report."""
        lines = [
            "\n=== Cycle Debug Summary ===",
            f"Total Duration: {self.total_duration_seconds:.2f}s",
            "",
            "Time by Operation Type:",
        ]

        for op_type, duration in sorted(self.operation_time.items(), key=lambda x: x[1], reverse=True):
            percentage = (duration / self.total_duration_seconds * 100) if self.total_duration_seconds > 0 else 0
            lines.append(f"  {op_type.value}: {duration:.2f}s ({percentage:.1f}%)")

        if self.agent_time:
            lines.extend([
                "",
                "Time by Agent:",
            ])
            for agent, duration in sorted(self.agent_time.items(), key=lambda x: x[1], reverse=True):
                percentage = (duration / self.total_duration_seconds * 100) if self.total_duration_seconds > 0 else 0
                lines.append(f"  {agent}: {duration:.2f}s ({percentage:.1f}%)")

        if self.work_items_by_outcome:
            lines.extend([
                "",
                "Work Items by Outcome:",
            ])
            for outcome, count in sorted(self.work_items_by_outcome.items()):
                lines.append(f"  {outcome}: {count}")

        lines.extend([
            "",
            f"API Calls: {self.api_call_count}",
            f"Checkpoints: {self.checkpoint_count}",
            "=" * 27,
        ])

        return "\n".join(lines)


class DebugLogger:
    """
    Debug logger for workspace-os cycle work operations.

    Provides structured logging with:
    - Timestamped entries
    - Operation type tracking
    - Agent and work item context
    - Duration measurements
    - File and stdout output
    - End-of-cycle summary
    """

    def __init__(self, log_dir: Path, cycle_label: str, enabled: bool = True):
        """
        Initialize debug logger.

        Args:
            log_dir: Directory for debug logs (e.g., .workspace-os/debug-logs/)
            cycle_label: Label for this cycle (used in filename)
            enabled: Whether debug logging is enabled
        """
        self.enabled = enabled
        if not enabled:
            return

        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        safe_label = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in cycle_label or "unlabeled")
        self.log_file = self.log_dir / f"cycle-{safe_label}-{timestamp}.log"

        self.summary = CycleSummary()
        self.cycle_start = datetime.now(timezone.utc)

        # Write header
        self._write_line("=== Workspace-OS Cycle Debug Log ===")
        self._write_line(f"Cycle: {cycle_label}")
        self._write_line(f"Started: {self.cycle_start.isoformat()}")
        self._write_line(f"Log file: {self.log_file}")
        self._write_line("=" * 36)
        self._write_line("")

    def log(
        self,
        level: LogLevel,
        operation_type: OperationType,
        message: str,
        agent_name: str | None = None,
        work_item_id: str | None = None,
        duration_seconds: float | None = None,
        **metadata: Any,
    ) -> None:
        """Log a debug entry."""
        if not self.enabled:
            return

        entry = DebugLogEntry(
            timestamp=datetime.now(timezone.utc),
            level=level,
            operation_type=operation_type,
            message=message,
            agent_name=agent_name,
            work_item_id=work_item_id,
            duration_seconds=duration_seconds,
            metadata=metadata,
        )

        log_line = entry.to_log_line()
        self._write_line(log_line)
        self.summary.add_entry(entry)

    def debug(self, operation_type: OperationType, message: str, **kwargs: Any) -> None:
        """Log a DEBUG level message."""
        self.log(LogLevel.DEBUG, operation_type, message, **kwargs)

    def info(self, operation_type: OperationType, message: str, **kwargs: Any) -> None:
        """Log an INFO level message."""
        self.log(LogLevel.INFO, operation_type, message, **kwargs)

    def warn(self, operation_type: OperationType, message: str, **kwargs: Any) -> None:
        """Log a WARN level message."""
        self.log(LogLevel.WARN, operation_type, message, **kwargs)

    def error(self, operation_type: OperationType, message: str, **kwargs: Any) -> None:
        """Log an ERROR level message."""
        self.log(LogLevel.ERROR, operation_type, message, **kwargs)

    def finalize(self) -> str:
        """
        Finalize the debug log and return summary report.

        Returns:
            Formatted summary report string
        """
        if not self.enabled:
            return ""

        cycle_end = datetime.now(timezone.utc)
        self.summary.total_duration_seconds = (cycle_end - self.cycle_start).total_seconds()

        self._write_line("")
        self._write_line(f"Cycle ended: {cycle_end.isoformat()}")

        report = self.summary.to_report()
        self._write_line(report)

        return report

    def _write_line(self, line: str) -> None:
        """Write a line to both file and stdout."""
        if not self.enabled:
            return

        # Write to file
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

        # Also print to stdout
        print(line, file=sys.stdout)


class NullDebugLogger:
    """No-op debug logger for when debug mode is disabled."""

    def __init__(self, *args: Any, **kwargs: Any):
        pass

    def log(self, *args: Any, **kwargs: Any) -> None:
        pass

    def debug(self, *args: Any, **kwargs: Any) -> None:
        pass

    def info(self, *args: Any, **kwargs: Any) -> None:
        pass

    def warn(self, *args: Any, **kwargs: Any) -> None:
        pass

    def error(self, *args: Any, **kwargs: Any) -> None:
        pass

    def finalize(self) -> str:
        return ""


def create_debug_logger(workspace_root: Path, cycle_label: str, enabled: bool = True) -> DebugLogger | NullDebugLogger:
    """
    Factory function to create appropriate debug logger.

    Args:
        workspace_root: Root directory of the workspace
        cycle_label: Label for the cycle
        enabled: Whether to enable debug logging

    Returns:
        DebugLogger if enabled, NullDebugLogger otherwise
    """
    if not enabled:
        return NullDebugLogger()

    log_dir = workspace_root / ".workspace-os" / "debug-logs"
    return DebugLogger(log_dir, cycle_label, enabled=True)

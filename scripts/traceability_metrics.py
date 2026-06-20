#!/usr/bin/env python3
"""
Traceability Metrics Collector for Workspace OS

This module provides comprehensive metrics collection and analysis for the Workspace OS
traceability system. It collects PR metrics, calculates latencies, generates compliance
reports, and creates interactive dashboards.

Features:
- PR lifecycle metrics collection (work→PR, PR→merge latencies)
- Compliance rate calculation and tracking
- Quality gate pass/fail analysis
- Checkpoint integration for historical tracking
- JSON and Markdown export formats
- Interactive dashboard generation

Usage:
    # Collect metrics for a cycle
    collector = MetricsCollector(workspace_root=Path("/path/to/repo"))
    metrics = collector.collect_pr_metrics(cycle_id=2)

    # Generate compliance report
    report = collector.generate_compliance_report(cycle_id=2, format="markdown")

    # Create dashboard
    collector.create_dashboard(cycle_id=2, output_path=Path("dashboard.html"))

    # Export metrics
    collector.export_metrics(metrics, output_path=Path("metrics.json"))

CLI Usage:
    python traceability_metrics.py collect --cycle-id 2
    python traceability_metrics.py report --cycle-id 2 --format markdown
    python traceability_metrics.py dashboard --cycle-id 2 --output dashboard.html
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Any
import traceback


class MetricType(Enum):
    """Types of metrics collected."""
    WORK_TO_PR_LATENCY = "work_to_pr_latency"
    PR_TO_MERGE_LATENCY = "pr_to_merge_latency"
    COMPLIANCE_RATE = "compliance_rate"
    QUALITY_GATE_PASS_RATE = "quality_gate_pass_rate"


class ExportFormat(Enum):
    """Export format options."""
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    CSV = "csv"


@dataclass
class PRMetrics:
    """Metrics for a single PR."""
    pr_number: int
    issue_number: Optional[int]
    work_item_id: str
    created_at: datetime
    merged_at: Optional[datetime]
    closed_at: Optional[datetime]
    work_started_at: Optional[datetime]
    work_completed_at: Optional[datetime]
    work_to_pr_seconds: Optional[float] = None
    pr_to_merge_seconds: Optional[float] = None
    pr_to_close_seconds: Optional[float] = None
    has_closing_keyword: bool = False
    is_merged: bool = False
    pr_state: str = "unknown"
    agent_type: str = "unknown"

    def __post_init__(self):
        """Calculate derived metrics."""
        if self.work_completed_at and self.created_at:
            if isinstance(self.work_completed_at, str):
                self.work_completed_at = datetime.fromisoformat(self.work_completed_at.replace("Z", "+00:00"))
            if isinstance(self.created_at, str):
                self.created_at = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            self.work_to_pr_seconds = (self.created_at - self.work_completed_at).total_seconds()

        if self.created_at and self.merged_at:
            if isinstance(self.merged_at, str):
                self.merged_at = datetime.fromisoformat(self.merged_at.replace("Z", "+00:00"))
            self.pr_to_merge_seconds = (self.merged_at - self.created_at).total_seconds()

        if self.created_at and self.closed_at:
            if isinstance(self.closed_at, str):
                self.closed_at = datetime.fromisoformat(self.closed_at.replace("Z", "+00:00"))
            self.pr_to_close_seconds = (self.closed_at - self.created_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data


@dataclass
class LatencyMetrics:
    """Aggregated latency metrics."""
    avg_work_to_pr_seconds: Optional[float] = None
    median_work_to_pr_seconds: Optional[float] = None
    p95_work_to_pr_seconds: Optional[float] = None
    avg_pr_to_merge_seconds: Optional[float] = None
    median_pr_to_merge_seconds: Optional[float] = None
    p95_pr_to_merge_seconds: Optional[float] = None
    total_samples: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ComplianceMetrics:
    """Compliance-related metrics."""
    total_work_items: int
    prs_created: int
    prs_merged: int
    prs_with_closing_keywords: int
    prs_without_closing_keywords: int
    prs_not_created: int
    compliance_rate: float = 0.0
    merge_rate: float = 0.0
    keyword_compliance_rate: float = 0.0

    def __post_init__(self):
        """Calculate compliance rates."""
        if self.total_work_items > 0:
            self.compliance_rate = (self.prs_created / self.total_work_items) * 100

        if self.prs_created > 0:
            self.merge_rate = (self.prs_merged / self.prs_created) * 100
            self.keyword_compliance_rate = (self.prs_with_closing_keywords / self.prs_created) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class QualityGateMetrics:
    """Quality gate metrics from checkpoints."""
    total_checkpoints: int
    health_pass_count: int
    stability_pass_count: int
    security_pass_count: int
    quality_pass_count: int
    health_pass_rate: float = 0.0
    stability_pass_rate: float = 0.0
    security_pass_rate: float = 0.0
    quality_pass_rate: float = 0.0
    overall_pass_count: int = 0
    overall_pass_rate: float = 0.0

    def __post_init__(self):
        """Calculate pass rates."""
        if self.total_checkpoints > 0:
            self.health_pass_rate = (self.health_pass_count / self.total_checkpoints) * 100
            self.stability_pass_rate = (self.stability_pass_count / self.total_checkpoints) * 100
            self.security_pass_rate = (self.security_pass_count / self.total_checkpoints) * 100
            self.quality_pass_rate = (self.quality_pass_count / self.total_checkpoints) * 100
            self.overall_pass_rate = (self.overall_pass_count / self.total_checkpoints) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class CycleMetricsReport:
    """Comprehensive metrics report for a cycle."""
    cycle_id: int
    cycle_label: str
    cycle_objective: Optional[str]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    generated_at: datetime
    pr_metrics: list[PRMetrics]
    latency_metrics: LatencyMetrics
    compliance_metrics: ComplianceMetrics
    quality_gate_metrics: QualityGateMetrics
    validation_failures: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = {
            "cycle_id": self.cycle_id,
            "cycle_label": self.cycle_label,
            "cycle_objective": self.cycle_objective,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "generated_at": self.generated_at.isoformat(),
            "pr_metrics": [pr.to_dict() for pr in self.pr_metrics],
            "latency_metrics": self.latency_metrics.to_dict(),
            "compliance_metrics": self.compliance_metrics.to_dict(),
            "quality_gate_metrics": self.quality_gate_metrics.to_dict(),
            "validation_failures": self.validation_failures
        }
        return data


class MetricsCollector:
    """
    Main metrics collector class.

    Collects and analyzes traceability metrics from the Workspace OS system,
    including PR lifecycle data, compliance rates, and quality gate results.
    """

    DEFAULT_MEMORY_DB_PATH = Path(".wos/memory.db")
    DEFAULT_TIMEOUT = 10.0

    def __init__(
        self,
        workspace_root: Path,
        memory_db_path: Optional[Path] = None,
        timeout_seconds: float = DEFAULT_TIMEOUT
    ):
        """
        Initialize metrics collector.

        Args:
            workspace_root: Root directory of the workspace repository
            memory_db_path: Path to memory.db (defaults to .wos/memory.db)
            timeout_seconds: Timeout for subprocess calls

        Raises:
            FileNotFoundError: If workspace_root doesn't exist
            ValueError: If workspace_root is not a directory
        """
        if not workspace_root.exists():
            raise FileNotFoundError(f"Workspace root does not exist: {workspace_root}")

        if not workspace_root.is_dir():
            raise ValueError(f"Workspace root is not a directory: {workspace_root}")

        self.workspace_root = workspace_root
        self.memory_db_path = memory_db_path or (workspace_root / self.DEFAULT_MEMORY_DB_PATH)
        self.timeout_seconds = timeout_seconds

    def collect_pr_metrics(self, cycle_id: int) -> list[PRMetrics]:
        """
        Collect PR metrics for all work items in a cycle.

        Args:
            cycle_id: Cycle ID to collect metrics for

        Returns:
            List of PRMetrics objects

        Raises:
            FileNotFoundError: If memory database doesn't exist
            sqlite3.Error: If database query fails
        """
        if not self.memory_db_path.exists():
            raise FileNotFoundError(f"Memory database not found: {self.memory_db_path}")

        pr_metrics = []

        try:
            conn = sqlite3.connect(self.memory_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if agent_queue table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='agent_queue'
            """)

            if not cursor.fetchone():
                return pr_metrics

            # Get work items for this cycle
            cursor.execute("""
                SELECT
                    task_id,
                    metadata,
                    started_at,
                    completed_at
                FROM agent_queue
                WHERE status = 'completed'
                AND task_id LIKE ?
                ORDER BY started_at
            """, (f"%cycle-{cycle_id}-%",))

            work_items = cursor.fetchall()

            # Collect metrics for each work item
            for item in work_items:
                try:
                    metadata = json.loads(item["metadata"]) if item["metadata"] else {}
                    issue_number = metadata.get("issue_number")

                    if not issue_number:
                        continue

                    # Query PR for this issue
                    pr_data = self._get_pr_for_issue(issue_number)

                    if pr_data:
                        pr_metric = PRMetrics(
                            pr_number=pr_data["number"],
                            issue_number=issue_number,
                            work_item_id=item["task_id"],
                            created_at=pr_data["created_at"],
                            merged_at=pr_data.get("merged_at"),
                            closed_at=pr_data.get("closed_at"),
                            work_started_at=self._parse_datetime(item["started_at"]),
                            work_completed_at=self._parse_datetime(item["completed_at"]),
                            has_closing_keyword=pr_data.get("has_closing_keyword", False),
                            is_merged=pr_data.get("is_merged", False),
                            pr_state=pr_data.get("state", "unknown"),
                            agent_type=metadata.get("agent_type", "unknown")
                        )
                        pr_metrics.append(pr_metric)

                except Exception as e:
                    # Log error but continue processing other items
                    print(f"Warning: Failed to collect metrics for {item['task_id']}: {e}", file=sys.stderr)
                    continue

            return pr_metrics

        finally:
            if 'conn' in locals():
                conn.close()

    def calculate_latencies(self, pr_metrics: list[PRMetrics]) -> LatencyMetrics:
        """
        Calculate aggregate latency metrics from PR data.

        Args:
            pr_metrics: List of PRMetrics objects

        Returns:
            LatencyMetrics with aggregated statistics
        """
        work_to_pr_times = [
            pr.work_to_pr_seconds
            for pr in pr_metrics
            if pr.work_to_pr_seconds is not None
        ]

        pr_to_merge_times = [
            pr.pr_to_merge_seconds
            for pr in pr_metrics
            if pr.pr_to_merge_seconds is not None
        ]

        return LatencyMetrics(
            avg_work_to_pr_seconds=self._calculate_avg(work_to_pr_times),
            median_work_to_pr_seconds=self._calculate_median(work_to_pr_times),
            p95_work_to_pr_seconds=self._calculate_percentile(work_to_pr_times, 95),
            avg_pr_to_merge_seconds=self._calculate_avg(pr_to_merge_times),
            median_pr_to_merge_seconds=self._calculate_median(pr_to_merge_times),
            p95_pr_to_merge_seconds=self._calculate_percentile(pr_to_merge_times, 95),
            total_samples=len(pr_metrics)
        )

    def calculate_compliance_metrics(
        self,
        cycle_id: int,
        pr_metrics: list[PRMetrics]
    ) -> ComplianceMetrics:
        """
        Calculate compliance metrics from PR data and work items.

        Args:
            cycle_id: Cycle ID
            pr_metrics: List of PRMetrics objects

        Returns:
            ComplianceMetrics object

        Raises:
            sqlite3.Error: If database query fails
        """
        # Get total work items count
        total_work_items = self._get_total_work_items(cycle_id)

        prs_created = len(pr_metrics)
        prs_merged = sum(1 for pr in pr_metrics if pr.is_merged)
        prs_with_keywords = sum(1 for pr in pr_metrics if pr.has_closing_keyword)
        prs_without_keywords = prs_created - prs_with_keywords
        prs_not_created = total_work_items - prs_created

        return ComplianceMetrics(
            total_work_items=total_work_items,
            prs_created=prs_created,
            prs_merged=prs_merged,
            prs_with_closing_keywords=prs_with_keywords,
            prs_without_closing_keywords=prs_without_keywords,
            prs_not_created=prs_not_created
        )

    def calculate_quality_gate_metrics(self, cycle_id: int) -> QualityGateMetrics:
        """
        Calculate quality gate metrics from checkpoint data.

        Args:
            cycle_id: Cycle ID

        Returns:
            QualityGateMetrics object

        Raises:
            sqlite3.Error: If database query fails
        """
        if not self.memory_db_path.exists():
            return QualityGateMetrics(
                total_checkpoints=0,
                health_pass_count=0,
                stability_pass_count=0,
                security_pass_count=0,
                quality_pass_count=0,
                overall_pass_count=0
            )

        try:
            conn = sqlite3.connect(self.memory_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if cycle_checkpoints table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='cycle_checkpoints'
            """)

            if not cursor.fetchone():
                return QualityGateMetrics(
                    total_checkpoints=0,
                    health_pass_count=0,
                    stability_pass_count=0,
                    security_pass_count=0,
                    quality_pass_count=0,
                    overall_pass_count=0
                )

            # Get checkpoint results
            cursor.execute("""
                SELECT
                    health_ok,
                    stability_ok,
                    security_ok,
                    quality_ok
                FROM cycle_checkpoints
                WHERE cycle_id = ?
                ORDER BY created_at
            """, (cycle_id,))

            checkpoints = cursor.fetchall()

            if not checkpoints:
                return QualityGateMetrics(
                    total_checkpoints=0,
                    health_pass_count=0,
                    stability_pass_count=0,
                    security_pass_count=0,
                    quality_pass_count=0,
                    overall_pass_count=0
                )

            total = len(checkpoints)
            health_pass = sum(1 for cp in checkpoints if cp["health_ok"])
            stability_pass = sum(1 for cp in checkpoints if cp["stability_ok"])
            security_pass = sum(1 for cp in checkpoints if cp["security_ok"])
            quality_pass = sum(1 for cp in checkpoints if cp["quality_ok"])
            overall_pass = sum(
                1 for cp in checkpoints
                if cp["health_ok"] and cp["stability_ok"]
                and cp["security_ok"] and cp["quality_ok"]
            )

            return QualityGateMetrics(
                total_checkpoints=total,
                health_pass_count=health_pass,
                stability_pass_count=stability_pass,
                security_pass_count=security_pass,
                quality_pass_count=quality_pass,
                overall_pass_count=overall_pass
            )

        finally:
            if 'conn' in locals():
                conn.close()

    def generate_compliance_report(
        self,
        cycle_id: int,
        format: str = "json"
    ) -> str:
        """
        Generate comprehensive compliance report for a cycle.

        Args:
            cycle_id: Cycle ID to report on
            format: Output format (json, markdown, html)

        Returns:
            Formatted report string

        Raises:
            ValueError: If format is unsupported
            sqlite3.Error: If database query fails
        """
        # Collect all metrics
        cycle_info = self._get_cycle_info(cycle_id)
        pr_metrics = self.collect_pr_metrics(cycle_id)
        latency_metrics = self.calculate_latencies(pr_metrics)
        compliance_metrics = self.calculate_compliance_metrics(cycle_id, pr_metrics)
        quality_metrics = self.calculate_quality_gate_metrics(cycle_id)

        report = CycleMetricsReport(
            cycle_id=cycle_id,
            cycle_label=cycle_info.get("label", f"Cycle {cycle_id}"),
            cycle_objective=cycle_info.get("objective"),
            started_at=self._parse_datetime(cycle_info.get("started_at")),
            ended_at=self._parse_datetime(cycle_info.get("ended_at")),
            generated_at=datetime.now(timezone.utc),
            pr_metrics=pr_metrics,
            latency_metrics=latency_metrics,
            compliance_metrics=compliance_metrics,
            quality_gate_metrics=quality_metrics
        )

        if format == "json":
            return self._format_json(report)
        elif format == "markdown":
            return self._format_markdown(report)
        elif format == "html":
            return self._format_html(report)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def create_dashboard(self, cycle_id: int, output_path: Path) -> None:
        """
        Create interactive HTML dashboard with metrics visualizations.

        Args:
            cycle_id: Cycle ID to create dashboard for
            output_path: Path to write HTML dashboard

        Raises:
            IOError: If unable to write to output_path
        """
        report_data = self.generate_compliance_report(cycle_id, format="json")
        report = json.loads(report_data)

        html = self._generate_dashboard_html(report)

        try:
            output_path.write_text(html, encoding="utf-8")
        except IOError as e:
            raise IOError(f"Failed to write dashboard to {output_path}: {e}")

    def export_metrics(
        self,
        metrics: list[PRMetrics],
        output_path: Path,
        format: str = "json"
    ) -> None:
        """
        Export metrics to file.

        Args:
            metrics: List of PRMetrics to export
            output_path: Output file path
            format: Export format (json, csv)

        Raises:
            ValueError: If format is unsupported
            IOError: If unable to write to output_path
        """
        try:
            if format == "json":
                data = [m.to_dict() for m in metrics]
                output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            elif format == "csv":
                self._export_csv(metrics, output_path)
            else:
                raise ValueError(f"Unsupported export format: {format}")
        except IOError as e:
            raise IOError(f"Failed to write metrics to {output_path}: {e}")

    # Private helper methods

    def _get_pr_for_issue(self, issue_number: int) -> Optional[dict[str, Any]]:
        """
        Query GitHub for PR referencing the issue.

        Args:
            issue_number: GitHub issue number

        Returns:
            PR data dictionary or None
        """
        try:
            result = subprocess.run(
                [
                    "gh", "pr", "list",
                    "--search", f"#{issue_number} in:body",
                    "--limit", "1",
                    "--json", "number,title,body,createdAt,mergedAt,closedAt,state",
                    "--state", "all"
                ],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False
            )

            if result.returncode != 0:
                return None

            prs = json.loads(result.stdout)

            if not prs:
                return None

            pr = prs[0]

            # Check for closing keyword
            has_keyword = self._has_closing_keyword(pr.get("body", ""), issue_number)

            return {
                "number": pr["number"],
                "created_at": self._parse_datetime(pr["createdAt"]),
                "merged_at": self._parse_datetime(pr.get("mergedAt")),
                "closed_at": self._parse_datetime(pr.get("closedAt")),
                "state": pr.get("state", "unknown").lower(),
                "is_merged": pr.get("mergedAt") is not None,
                "has_closing_keyword": has_keyword
            }

        except Exception as e:
            print(f"Warning: Failed to get PR for issue #{issue_number}: {e}", file=sys.stderr)
            return None

    def _has_closing_keyword(self, pr_body: str, issue_number: int) -> bool:
        """Check if PR body contains closing keyword for issue."""
        if not pr_body:
            return False

        keywords = [
            "close", "closes", "closed",
            "fix", "fixes", "fixed",
            "resolve", "resolves", "resolved"
        ]

        body_lower = pr_body.lower()

        for keyword in keywords:
            patterns = [
                f"{keyword} #{issue_number}",
                f"{keyword}: #{issue_number}",
                f"{keyword} #{issue_number}.",
                f"{keyword} #{issue_number},",
            ]
            for pattern in patterns:
                if pattern in body_lower:
                    return True

        return False

    def _get_total_work_items(self, cycle_id: int) -> int:
        """Get total work items count for cycle."""
        if not self.memory_db_path.exists():
            return 0

        try:
            conn = sqlite3.connect(self.memory_db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='agent_queue'
            """)

            if not cursor.fetchone():
                return 0

            cursor.execute("""
                SELECT COUNT(*)
                FROM agent_queue
                WHERE status = 'completed'
                AND task_id LIKE ?
            """, (f"%cycle-{cycle_id}-%",))

            return cursor.fetchone()[0]

        finally:
            if 'conn' in locals():
                conn.close()

    def _get_cycle_info(self, cycle_id: int) -> dict[str, Any]:
        """Get cycle metadata from database."""
        if not self.memory_db_path.exists():
            return {"label": f"Cycle {cycle_id}"}

        try:
            conn = sqlite3.connect(self.memory_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='cycles'
            """)

            if not cursor.fetchone():
                return {"label": f"Cycle {cycle_id}"}

            cursor.execute("""
                SELECT id, label, objective, started_at, ended_at
                FROM cycles
                WHERE id = ?
            """, (cycle_id,))

            row = cursor.fetchone()

            if not row:
                return {"label": f"Cycle {cycle_id}"}

            return dict(row)

        finally:
            if 'conn' in locals():
                conn.close()

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string."""
        if not dt_str:
            return None

        try:
            # Handle both with and without timezone
            if dt_str.endswith("Z"):
                dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str)
        except (ValueError, AttributeError):
            return None

    def _calculate_avg(self, values: list[float]) -> Optional[float]:
        """Calculate average of values."""
        return sum(values) / len(values) if values else None

    def _calculate_median(self, values: list[float]) -> Optional[float]:
        """Calculate median of values."""
        if not values:
            return None

        sorted_values = sorted(values)
        n = len(sorted_values)
        mid = n // 2

        if n % 2 == 0:
            return (sorted_values[mid - 1] + sorted_values[mid]) / 2
        else:
            return sorted_values[mid]

    def _calculate_percentile(self, values: list[float], percentile: int) -> Optional[float]:
        """Calculate percentile of values."""
        if not values:
            return None

        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))

        if index >= len(sorted_values):
            return sorted_values[-1]

        return sorted_values[index]

    def _format_json(self, report: CycleMetricsReport) -> str:
        """Format report as JSON."""
        return json.dumps(report.to_dict(), indent=2)

    def _format_markdown(self, report: CycleMetricsReport) -> str:
        """Format report as Markdown."""
        md = f"""# Traceability Metrics Report

**Cycle:** {report.cycle_label}
**Cycle ID:** {report.cycle_id}
**Objective:** {report.cycle_objective or "N/A"}
**Started:** {report.started_at.isoformat() if report.started_at else "N/A"}
**Ended:** {report.ended_at.isoformat() if report.ended_at else "In Progress"}
**Generated:** {report.generated_at.isoformat()}

---

## Compliance Metrics

| Metric | Value |
|--------|-------|
| Total Work Items | {report.compliance_metrics.total_work_items} |
| PRs Created | {report.compliance_metrics.prs_created} |
| PRs Merged | {report.compliance_metrics.prs_merged} |
| PRs with Closing Keywords | {report.compliance_metrics.prs_with_closing_keywords} |
| PRs without Closing Keywords | {report.compliance_metrics.prs_without_closing_keywords} |
| PRs Not Created | {report.compliance_metrics.prs_not_created} |
| **Compliance Rate** | **{report.compliance_metrics.compliance_rate:.1f}%** |
| **Merge Rate** | **{report.compliance_metrics.merge_rate:.1f}%** |
| **Keyword Compliance** | **{report.compliance_metrics.keyword_compliance_rate:.1f}%** |

---

## Latency Metrics

| Metric | Avg | Median | P95 |
|--------|-----|--------|-----|
| Work → PR | {self._format_duration(report.latency_metrics.avg_work_to_pr_seconds)} | {self._format_duration(report.latency_metrics.median_work_to_pr_seconds)} | {self._format_duration(report.latency_metrics.p95_work_to_pr_seconds)} |
| PR → Merge | {self._format_duration(report.latency_metrics.avg_pr_to_merge_seconds)} | {self._format_duration(report.latency_metrics.median_pr_to_merge_seconds)} | {self._format_duration(report.latency_metrics.p95_pr_to_merge_seconds)} |

**Total Samples:** {report.latency_metrics.total_samples}

---

## Quality Gate Metrics

| Gate | Pass Count | Pass Rate |
|------|------------|-----------|
| Health | {report.quality_gate_metrics.health_pass_count}/{report.quality_gate_metrics.total_checkpoints} | {report.quality_gate_metrics.health_pass_rate:.1f}% |
| Stability | {report.quality_gate_metrics.stability_pass_count}/{report.quality_gate_metrics.total_checkpoints} | {report.quality_gate_metrics.stability_pass_rate:.1f}% |
| Security | {report.quality_gate_metrics.security_pass_count}/{report.quality_gate_metrics.total_checkpoints} | {report.quality_gate_metrics.security_pass_rate:.1f}% |
| Quality | {report.quality_gate_metrics.quality_pass_count}/{report.quality_gate_metrics.total_checkpoints} | {report.quality_gate_metrics.quality_pass_rate:.1f}% |
| **Overall** | **{report.quality_gate_metrics.overall_pass_count}/{report.quality_gate_metrics.total_checkpoints}** | **{report.quality_gate_metrics.overall_pass_rate:.1f}%** |

---

## PR Details

"""
        if report.pr_metrics:
            for pr in report.pr_metrics:
                md += f"### PR #{pr.pr_number}\n\n"
                md += f"- **Issue:** #{pr.issue_number or 'N/A'}\n"
                md += f"- **Work Item:** {pr.work_item_id}\n"
                md += f"- **State:** {pr.pr_state}\n"
                md += f"- **Merged:** {'Yes' if pr.is_merged else 'No'}\n"
                md += f"- **Has Closing Keyword:** {'Yes' if pr.has_closing_keyword else 'No'}\n"
                md += f"- **Agent:** {pr.agent_type}\n"
                md += f"- **Work → PR:** {self._format_duration(pr.work_to_pr_seconds)}\n"
                md += f"- **PR → Merge:** {self._format_duration(pr.pr_to_merge_seconds)}\n\n"
        else:
            md += "*No PR metrics available*\n"

        return md

    def _format_html(self, report: CycleMetricsReport) -> str:
        """Format report as HTML."""
        # Simple HTML table format
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Traceability Metrics - {report.cycle_label}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .metric-value {{ font-weight: bold; color: #4CAF50; }}
    </style>
</head>
<body>
    <h1>Traceability Metrics Report</h1>
    <p><strong>Cycle:</strong> {report.cycle_label}</p>
    <p><strong>Generated:</strong> {report.generated_at.isoformat()}</p>

    <h2>Compliance Metrics</h2>
    <table>
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Total Work Items</td><td>{report.compliance_metrics.total_work_items}</td></tr>
        <tr><td>PRs Created</td><td>{report.compliance_metrics.prs_created}</td></tr>
        <tr><td>Compliance Rate</td><td class="metric-value">{report.compliance_metrics.compliance_rate:.1f}%</td></tr>
    </table>

    <h2>Latency Metrics</h2>
    <table>
        <tr><th>Metric</th><th>Average</th><th>Median</th><th>P95</th></tr>
        <tr>
            <td>Work → PR</td>
            <td>{self._format_duration(report.latency_metrics.avg_work_to_pr_seconds)}</td>
            <td>{self._format_duration(report.latency_metrics.median_work_to_pr_seconds)}</td>
            <td>{self._format_duration(report.latency_metrics.p95_work_to_pr_seconds)}</td>
        </tr>
    </table>

    <h2>Quality Gates</h2>
    <table>
        <tr><th>Gate</th><th>Pass Rate</th></tr>
        <tr><td>Health</td><td>{report.quality_gate_metrics.health_pass_rate:.1f}%</td></tr>
        <tr><td>Stability</td><td>{report.quality_gate_metrics.stability_pass_rate:.1f}%</td></tr>
        <tr><td>Security</td><td>{report.quality_gate_metrics.security_pass_rate:.1f}%</td></tr>
        <tr><td>Quality</td><td>{report.quality_gate_metrics.quality_pass_rate:.1f}%</td></tr>
    </table>
</body>
</html>"""
        return html

    def _generate_dashboard_html(self, report_dict: dict[str, Any]) -> str:
        """Generate interactive dashboard HTML."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Traceability Dashboard - Cycle {report_dict['cycle_id']}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .metric-card.green {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }}
        .metric-card.blue {{
            background: linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%);
        }}
        .metric-card.orange {{
            background: linear-gradient(135deg, #ee9617 0%, #fe5858 100%);
        }}
        .metric-label {{
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 36px;
            font-weight: bold;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #3498db;
            color: white;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .progress-bar {{
            background-color: #e0e0e0;
            border-radius: 10px;
            height: 20px;
            overflow: hidden;
        }}
        .progress-fill {{
            background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%);
            height: 100%;
            transition: width 0.3s ease;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Traceability Dashboard: {report_dict['cycle_label']}</h1>
        <p><strong>Generated:</strong> {report_dict['generated_at']}</p>

        <h2>Key Metrics</h2>
        <div class="metric-grid">
            <div class="metric-card green">
                <div class="metric-label">Compliance Rate</div>
                <div class="metric-value">{report_dict['compliance_metrics']['compliance_rate']:.1f}%</div>
            </div>
            <div class="metric-card blue">
                <div class="metric-label">Merge Rate</div>
                <div class="metric-value">{report_dict['compliance_metrics']['merge_rate']:.1f}%</div>
            </div>
            <div class="metric-card orange">
                <div class="metric-label">PRs Created</div>
                <div class="metric-value">{report_dict['compliance_metrics']['prs_created']}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Work Items</div>
                <div class="metric-value">{report_dict['compliance_metrics']['total_work_items']}</div>
            </div>
        </div>

        <h2>Quality Gates</h2>
        <table>
            <tr>
                <th>Gate</th>
                <th>Pass Count</th>
                <th>Pass Rate</th>
                <th>Progress</th>
            </tr>
            <tr>
                <td>Health</td>
                <td>{report_dict['quality_gate_metrics']['health_pass_count']}/{report_dict['quality_gate_metrics']['total_checkpoints']}</td>
                <td>{report_dict['quality_gate_metrics']['health_pass_rate']:.1f}%</td>
                <td>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {report_dict['quality_gate_metrics']['health_pass_rate']:.1f}%"></div>
                    </div>
                </td>
            </tr>
            <tr>
                <td>Stability</td>
                <td>{report_dict['quality_gate_metrics']['stability_pass_count']}/{report_dict['quality_gate_metrics']['total_checkpoints']}</td>
                <td>{report_dict['quality_gate_metrics']['stability_pass_rate']:.1f}%</td>
                <td>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {report_dict['quality_gate_metrics']['stability_pass_rate']:.1f}%"></div>
                    </div>
                </td>
            </tr>
            <tr>
                <td>Security</td>
                <td>{report_dict['quality_gate_metrics']['security_pass_count']}/{report_dict['quality_gate_metrics']['total_checkpoints']}</td>
                <td>{report_dict['quality_gate_metrics']['security_pass_rate']:.1f}%</td>
                <td>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {report_dict['quality_gate_metrics']['security_pass_rate']:.1f}%"></div>
                    </div>
                </td>
            </tr>
            <tr>
                <td>Quality</td>
                <td>{report_dict['quality_gate_metrics']['quality_pass_count']}/{report_dict['quality_gate_metrics']['total_checkpoints']}</td>
                <td>{report_dict['quality_gate_metrics']['quality_pass_rate']:.1f}%</td>
                <td>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {report_dict['quality_gate_metrics']['quality_pass_rate']:.1f}%"></div>
                    </div>
                </td>
            </tr>
        </table>

        <h2>Latency Metrics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Average</th>
                <th>Median</th>
                <th>P95</th>
            </tr>
            <tr>
                <td>Work → PR</td>
                <td>{self._format_duration(report_dict['latency_metrics']['avg_work_to_pr_seconds'])}</td>
                <td>{self._format_duration(report_dict['latency_metrics']['median_work_to_pr_seconds'])}</td>
                <td>{self._format_duration(report_dict['latency_metrics']['p95_work_to_pr_seconds'])}</td>
            </tr>
            <tr>
                <td>PR → Merge</td>
                <td>{self._format_duration(report_dict['latency_metrics']['avg_pr_to_merge_seconds'])}</td>
                <td>{self._format_duration(report_dict['latency_metrics']['median_pr_to_merge_seconds'])}</td>
                <td>{self._format_duration(report_dict['latency_metrics']['p95_pr_to_merge_seconds'])}</td>
            </tr>
        </table>
    </div>
</body>
</html>"""

    def _format_duration(self, seconds: Optional[float]) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds is None:
            return "N/A"

        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"

    def _export_csv(self, metrics: list[PRMetrics], output_path: Path) -> None:
        """Export metrics to CSV format."""
        import csv

        with output_path.open('w', newline='', encoding='utf-8') as f:
            if not metrics:
                return

            fieldnames = [
                'pr_number', 'issue_number', 'work_item_id', 'created_at',
                'merged_at', 'work_to_pr_seconds', 'pr_to_merge_seconds',
                'has_closing_keyword', 'is_merged', 'pr_state', 'agent_type'
            ]

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for metric in metrics:
                row = {
                    'pr_number': metric.pr_number,
                    'issue_number': metric.issue_number or '',
                    'work_item_id': metric.work_item_id,
                    'created_at': metric.created_at.isoformat() if metric.created_at else '',
                    'merged_at': metric.merged_at.isoformat() if metric.merged_at else '',
                    'work_to_pr_seconds': metric.work_to_pr_seconds or '',
                    'pr_to_merge_seconds': metric.pr_to_merge_seconds or '',
                    'has_closing_keyword': metric.has_closing_keyword,
                    'is_merged': metric.is_merged,
                    'pr_state': metric.pr_state,
                    'agent_type': metric.agent_type
                }
                writer.writerow(row)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Traceability Metrics Collector for Workspace OS",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Collect command
    collect_parser = subparsers.add_parser('collect', help='Collect PR metrics')
    collect_parser.add_argument('--cycle-id', type=int, required=True, help='Cycle ID')
    collect_parser.add_argument('--output', type=Path, help='Output file path')
    collect_parser.add_argument('--format', choices=['json', 'csv'], default='json', help='Output format')

    # Report command
    report_parser = subparsers.add_parser('report', help='Generate compliance report')
    report_parser.add_argument('--cycle-id', type=int, required=True, help='Cycle ID')
    report_parser.add_argument('--format', choices=['json', 'markdown', 'html'], default='markdown', help='Report format')
    report_parser.add_argument('--output', type=Path, help='Output file path')

    # Dashboard command
    dashboard_parser = subparsers.add_parser('dashboard', help='Create interactive dashboard')
    dashboard_parser.add_argument('--cycle-id', type=int, required=True, help='Cycle ID')
    dashboard_parser.add_argument('--output', type=Path, required=True, help='Output HTML file path')

    # Latency command
    latency_parser = subparsers.add_parser('latency', help='Calculate latency metrics')
    latency_parser.add_argument('--cycle-id', type=int, required=True, help='Cycle ID')

    # Common arguments
    for p in [collect_parser, report_parser, dashboard_parser, latency_parser]:
        p.add_argument('--workspace', type=Path, default=Path.cwd(), help='Workspace root directory')
        p.add_argument('--memory-db', type=Path, help='Path to memory.db')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        # Initialize collector
        collector = MetricsCollector(
            workspace_root=args.workspace,
            memory_db_path=args.memory_db
        )

        if args.command == 'collect':
            metrics = collector.collect_pr_metrics(args.cycle_id)

            if args.output:
                collector.export_metrics(metrics, args.output, format=args.format)
                print(f"Metrics exported to {args.output}")
            else:
                # Print to stdout
                if args.format == 'json':
                    print(json.dumps([m.to_dict() for m in metrics], indent=2))
                else:
                    print(f"Collected {len(metrics)} PR metrics for cycle {args.cycle_id}")

        elif args.command == 'report':
            report = collector.generate_compliance_report(args.cycle_id, format=args.format)

            if args.output:
                args.output.write_text(report, encoding='utf-8')
                print(f"Report written to {args.output}")
            else:
                print(report)

        elif args.command == 'dashboard':
            collector.create_dashboard(args.cycle_id, args.output)
            print(f"Dashboard created at {args.output}")

        elif args.command == 'latency':
            metrics = collector.collect_pr_metrics(args.cycle_id)
            latency = collector.calculate_latencies(metrics)

            print(f"Latency Metrics for Cycle {args.cycle_id}:")
            print(f"  Work → PR:")
            print(f"    Average: {collector._format_duration(latency.avg_work_to_pr_seconds)}")
            print(f"    Median:  {collector._format_duration(latency.median_work_to_pr_seconds)}")
            print(f"    P95:     {collector._format_duration(latency.p95_work_to_pr_seconds)}")
            print(f"  PR → Merge:")
            print(f"    Average: {collector._format_duration(latency.avg_pr_to_merge_seconds)}")
            print(f"    Median:  {collector._format_duration(latency.median_pr_to_merge_seconds)}")
            print(f"    P95:     {collector._format_duration(latency.p95_pr_to_merge_seconds)}")
            print(f"  Total Samples: {latency.total_samples}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

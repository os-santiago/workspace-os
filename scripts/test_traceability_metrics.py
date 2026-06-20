#!/usr/bin/env python3
"""
Unit tests for traceability_metrics.py

Tests the MetricsCollector class and its methods for collecting
and analyzing traceability metrics.
"""

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Import from the metrics module
import sys
sys.path.insert(0, str(Path(__file__).parent))
from traceability_metrics import (
    MetricsCollector,
    PRMetrics,
    LatencyMetrics,
    ComplianceMetrics,
    QualityGateMetrics,
    MetricType,
    ExportFormat
)


class TestPRMetrics(unittest.TestCase):
    """Test PRMetrics dataclass."""

    def test_work_to_pr_calculation(self):
        """Test automatic calculation of work-to-PR latency."""
        work_completed = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        pr_created = datetime(2024, 1, 1, 12, 5, 30, tzinfo=timezone.utc)

        metric = PRMetrics(
            pr_number=123,
            issue_number=456,
            work_item_id="cycle-1-work-1",
            created_at=pr_created,
            merged_at=None,
            closed_at=None,
            work_started_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
            work_completed_at=work_completed
        )

        # Should be 5 minutes 30 seconds = 330 seconds
        self.assertEqual(metric.work_to_pr_seconds, 330.0)

    def test_pr_to_merge_calculation(self):
        """Test automatic calculation of PR-to-merge latency."""
        pr_created = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        pr_merged = datetime(2024, 1, 1, 12, 15, 0, tzinfo=timezone.utc)

        metric = PRMetrics(
            pr_number=123,
            issue_number=456,
            work_item_id="cycle-1-work-1",
            created_at=pr_created,
            merged_at=pr_merged,
            closed_at=pr_merged,
            work_started_at=None,
            work_completed_at=None
        )

        # Should be 15 minutes = 900 seconds
        self.assertEqual(metric.pr_to_merge_seconds, 900.0)

    def test_to_dict_serialization(self):
        """Test conversion to dictionary."""
        metric = PRMetrics(
            pr_number=123,
            issue_number=456,
            work_item_id="cycle-1-work-1",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            merged_at=None,
            closed_at=None,
            work_started_at=None,
            work_completed_at=None,
            has_closing_keyword=True,
            is_merged=False,
            pr_state="open",
            agent_type="claude"
        )

        data = metric.to_dict()

        self.assertEqual(data["pr_number"], 123)
        self.assertEqual(data["issue_number"], 456)
        self.assertEqual(data["has_closing_keyword"], True)
        self.assertEqual(data["agent_type"], "claude")
        # Datetime should be converted to ISO string
        self.assertIsInstance(data["created_at"], str)


class TestLatencyMetrics(unittest.TestCase):
    """Test latency calculation methods."""

    def test_calculate_latencies(self):
        """Test calculation of aggregate latency statistics."""
        # Create sample PR metrics
        pr_metrics = [
            PRMetrics(
                pr_number=1,
                issue_number=101,
                work_item_id="w1",
                created_at=datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
                merged_at=datetime(2024, 1, 1, 12, 20, 0, tzinfo=timezone.utc),
                closed_at=None,
                work_started_at=None,
                work_completed_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            ),
            PRMetrics(
                pr_number=2,
                issue_number=102,
                work_item_id="w2",
                created_at=datetime(2024, 1, 1, 12, 10, 0, tzinfo=timezone.utc),
                merged_at=datetime(2024, 1, 1, 12, 25, 0, tzinfo=timezone.utc),
                closed_at=None,
                work_started_at=None,
                work_completed_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            ),
        ]

        # Create a temporary workspace
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            collector = MetricsCollector(workspace_root=workspace)

            latency = collector.calculate_latencies(pr_metrics)

            # Check that metrics were calculated
            self.assertIsNotNone(latency.avg_work_to_pr_seconds)
            self.assertIsNotNone(latency.median_work_to_pr_seconds)
            self.assertIsNotNone(latency.avg_pr_to_merge_seconds)
            self.assertEqual(latency.total_samples, 2)

            # Work to PR: 300s and 600s -> avg 450s
            self.assertEqual(latency.avg_work_to_pr_seconds, 450.0)

            # PR to merge: 900s and 900s -> avg 900s
            self.assertEqual(latency.avg_pr_to_merge_seconds, 900.0)


class TestComplianceMetrics(unittest.TestCase):
    """Test compliance calculation."""

    def test_compliance_rate_calculation(self):
        """Test compliance rate percentage calculation."""
        compliance = ComplianceMetrics(
            total_work_items=100,
            prs_created=95,
            prs_merged=90,
            prs_with_closing_keywords=92,
            prs_without_closing_keywords=3,
            prs_not_created=5
        )

        # Compliance rate should be 95%
        self.assertEqual(compliance.compliance_rate, 95.0)

        # Merge rate should be 90/95 = 94.7%
        self.assertAlmostEqual(compliance.merge_rate, 94.74, places=1)

        # Keyword compliance should be 92/95 = 96.8%
        self.assertAlmostEqual(compliance.keyword_compliance_rate, 96.84, places=1)


class TestQualityGateMetrics(unittest.TestCase):
    """Test quality gate metrics."""

    def test_pass_rate_calculation(self):
        """Test quality gate pass rate calculation."""
        quality = QualityGateMetrics(
            total_checkpoints=10,
            health_pass_count=9,
            stability_pass_count=8,
            security_pass_count=10,
            quality_pass_count=7,
            overall_pass_count=6
        )

        self.assertEqual(quality.health_pass_rate, 90.0)
        self.assertEqual(quality.stability_pass_rate, 80.0)
        self.assertEqual(quality.security_pass_rate, 100.0)
        self.assertEqual(quality.quality_pass_rate, 70.0)
        self.assertEqual(quality.overall_pass_rate, 60.0)


class TestMetricsCollector(unittest.TestCase):
    """Test MetricsCollector class."""

    def setUp(self):
        """Set up test fixtures."""
        self.tmpdir = tempfile.mkdtemp()
        self.workspace = Path(self.tmpdir)
        self.db_path = self.workspace / ".wos" / "memory.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_initialization(self):
        """Test MetricsCollector initialization."""
        collector = MetricsCollector(
            workspace_root=self.workspace,
            memory_db_path=self.db_path
        )

        self.assertEqual(collector.workspace_root, self.workspace)
        self.assertEqual(collector.memory_db_path, self.db_path)

    def test_initialization_invalid_workspace(self):
        """Test initialization with invalid workspace."""
        with self.assertRaises(FileNotFoundError):
            MetricsCollector(workspace_root=Path("/nonexistent/path"))

    def test_format_duration(self):
        """Test duration formatting."""
        collector = MetricsCollector(workspace_root=self.workspace)

        # Test seconds
        self.assertEqual(collector._format_duration(30.5), "30.5s")

        # Test minutes
        self.assertEqual(collector._format_duration(90), "1.5m")

        # Test hours
        self.assertEqual(collector._format_duration(7200), "2.0h")

        # Test None
        self.assertEqual(collector._format_duration(None), "N/A")

    def test_calculate_percentile(self):
        """Test percentile calculation."""
        collector = MetricsCollector(workspace_root=self.workspace)

        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        # P50 (median) - 50% of 10 = index 5 -> value 6
        p50 = collector._calculate_percentile(values, 50)
        self.assertEqual(p50, 6)

        # P95 - 95% of 10 = index 9 -> value 10
        p95 = collector._calculate_percentile(values, 95)
        self.assertEqual(p95, 10)

        # P0 - 0% of 10 = index 0 -> value 1
        p0 = collector._calculate_percentile(values, 0)
        self.assertEqual(p0, 1)

    def test_has_closing_keyword(self):
        """Test closing keyword detection."""
        collector = MetricsCollector(workspace_root=self.workspace)

        # Test with closing keyword
        self.assertTrue(
            collector._has_closing_keyword("Fixes #123", 123)
        )

        self.assertTrue(
            collector._has_closing_keyword("This PR closes #456", 456)
        )

        self.assertTrue(
            collector._has_closing_keyword("Resolves: #789", 789)
        )

        # Test without closing keyword
        self.assertFalse(
            collector._has_closing_keyword("See #123", 123)
        )

        self.assertFalse(
            collector._has_closing_keyword("Related to #123", 123)
        )

        # Test wrong issue number
        self.assertFalse(
            collector._has_closing_keyword("Fixes #999", 123)
        )

    def _create_test_database(self):
        """Create a test database with sample data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create tables
        cursor.execute("""
            CREATE TABLE cycles (
                id INTEGER PRIMARY KEY,
                label TEXT,
                objective TEXT,
                started_at TEXT,
                ended_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE agent_queue (
                task_id TEXT PRIMARY KEY,
                status TEXT,
                metadata TEXT,
                started_at TEXT,
                completed_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE cycle_checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER,
                health_ok BOOLEAN,
                stability_ok BOOLEAN,
                security_ok BOOLEAN,
                quality_ok BOOLEAN,
                created_at TEXT
            )
        """)

        # Insert test data
        cursor.execute("""
            INSERT INTO cycles (id, label, objective, started_at, ended_at)
            VALUES (1, 'Cycle 1', 'Test cycle', '2024-01-01T10:00:00Z', NULL)
        """)

        cursor.execute("""
            INSERT INTO agent_queue (task_id, status, metadata, started_at, completed_at)
            VALUES (
                'cycle-1-work-1',
                'completed',
                '{"issue_number": 123, "agent_type": "claude"}',
                '2024-01-01T11:00:00Z',
                '2024-01-01T11:30:00Z'
            )
        """)

        cursor.execute("""
            INSERT INTO cycle_checkpoints
            (cycle_id, health_ok, stability_ok, security_ok, quality_ok, created_at)
            VALUES (1, 1, 1, 1, 1, '2024-01-01T12:00:00Z')
        """)

        conn.commit()
        conn.close()

    def test_get_cycle_info(self):
        """Test getting cycle information from database."""
        self._create_test_database()

        collector = MetricsCollector(
            workspace_root=self.workspace,
            memory_db_path=self.db_path
        )

        cycle_info = collector._get_cycle_info(1)

        self.assertEqual(cycle_info["label"], "Cycle 1")
        self.assertEqual(cycle_info["objective"], "Test cycle")

    def test_calculate_quality_gate_metrics(self):
        """Test quality gate metrics calculation from database."""
        self._create_test_database()

        # Add more checkpoints
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO cycle_checkpoints
            (cycle_id, health_ok, stability_ok, security_ok, quality_ok, created_at)
            VALUES (1, 1, 0, 1, 1, '2024-01-01T13:00:00Z')
        """)

        conn.commit()
        conn.close()

        collector = MetricsCollector(
            workspace_root=self.workspace,
            memory_db_path=self.db_path
        )

        quality = collector.calculate_quality_gate_metrics(1)

        self.assertEqual(quality.total_checkpoints, 2)
        self.assertEqual(quality.health_pass_count, 2)
        self.assertEqual(quality.stability_pass_count, 1)
        self.assertEqual(quality.security_pass_count, 2)
        self.assertEqual(quality.quality_pass_count, 2)
        self.assertEqual(quality.overall_pass_count, 1)  # Only 1 has all gates pass


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == "__main__":
    run_tests()

from __future__ import annotations

from unittest.mock import patch
import tempfile
from pathlib import Path
import unittest

from workspace_os.agent_queue import AgentQueueTracker
from workspace_os.local_metrics import build_local_metrics_report, render_metrics_export
from workspace_os.memory import WorkspaceMemoryStore


class LocalMetricsTests(unittest.TestCase):
    def test_build_local_metrics_report_summarizes_local_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            cycle_id = store.start_cycle("Cycle 01", "Improve WOS", started_at="2026-06-27T14:00:00+00:00")
            store.record_cycle_checkpoint(
                "checkpoint-1",
                1,
                {"health_ok": True, "stability_ok": True, "security_ok": True, "quality_ok": True},
                cycle_id=cycle_id,
                created_at="2026-06-27T14:05:00+00:00",
            )
            store.record_task_outcome("cycle", "success-1", "success", created_at="2026-06-27T14:01:00+00:00")
            store.record_task_outcome("cycle", "failure-1", "failure", created_at="2026-06-27T14:02:00+00:00")

            tracker = AgentQueueTracker(memory.parent)
            tracker.enqueue("task-1", "opencode", "workspace-os", "Task 1")
            tracker.start("task-1")
            tracker.complete("task-1", returncode=0, duration_seconds=2.0)

            report = build_local_metrics_report(memory)

        self.assertEqual("Cycle 01", report.cycle_label)
        self.assertEqual(1, report.checkpoint_count)
        self.assertEqual(2, report.task_outcome_total)
        self.assertGreaterEqual(report.agent_utilization_ratio, 0.0)
        self.assertIn("task failures recorded", report.blockage_indicators)
        self.assertIn("WOS Local Metrics", report.render())

    def test_optional_exporters_are_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            cycle_id = store.start_cycle("Cycle 01", "Improve WOS", started_at="2026-06-27T14:00:00+00:00")
            store.record_cycle_checkpoint(
                "checkpoint-1",
                1,
                {"health_ok": True, "stability_ok": True, "security_ok": True, "quality_ok": True},
                cycle_id=cycle_id,
                created_at="2026-06-27T14:05:00+00:00",
            )

            report = build_local_metrics_report(memory)

        with patch.dict("os.environ", {"WOS_METRICS_EXPORTERS": ""}, clear=True):
            with self.assertRaises(ValueError):
                render_metrics_export(report, "prometheus")

        with patch.dict("os.environ", {"WOS_METRICS_EXPORTERS": "prometheus,grafana-json"}):
            prometheus = render_metrics_export(report, "prometheus")
            grafana = render_metrics_export(report, "grafana-json")

        self.assertIn("wos_cycle_duration_seconds", prometheus)
        self.assertIn('"title": "WOS Local Metrics"', grafana)

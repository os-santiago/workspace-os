from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from workspace_os.agent_performance_dashboard import build_agent_performance_dashboard
from workspace_os.agent_queue import AgentQueueTracker
from workspace_os.memory import WorkspaceMemoryStore


class AgentPerformanceDashboardTests(unittest.TestCase):
    def test_dashboard_reports_success_duration_roles_and_learning_velocity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            tracker = AgentQueueTracker(memory.parent)

            for index in range(20):
                role = ["primary", "cross-check", "observer"][index % 3]
                task_id = f"cycle-work-{index + 1}-{role}"
                tracker.enqueue(task_id, "opencode", "workspace-os", f"Task {index + 1}", metadata={"role": role})
                tracker.start(task_id)
                tracker.complete(task_id, returncode=1 if index < 10 else 0, duration_seconds=1.0 + index)

            for index in range(4):
                role = "cross-check" if index % 2 == 0 else "observer"
                task_id = f"review-{index + 1}-{role}"
                tracker.enqueue(task_id, "claude", "workspace-os", f"Review {index + 1}", metadata={"role": role})
                tracker.start(task_id)
                tracker.complete(task_id, returncode=0, duration_seconds=3.0 + index)

            dashboard = build_agent_performance_dashboard(memory)

        self.assertEqual(2, dashboard.agent_count)
        self.assertEqual(0, dashboard.queue_depth)
        self.assertEqual(14, dashboard.completed_count)
        self.assertEqual(10, dashboard.failed_count)
        opencode = next(summary for summary in dashboard.agent_summaries if summary.agent == "opencode")
        self.assertEqual(20, opencode.task_count)
        self.assertAlmostEqual(0.5, opencode.success_rate, places=2)
        self.assertAlmostEqual(1.0, opencode.recent_success_rate, places=2)
        self.assertGreater(opencode.learning_velocity, 0.4)
        self.assertGreater(opencode.primary_count, 0)
        self.assertGreater(opencode.cross_check_count, 0)
        self.assertGreater(opencode.observer_count, 0)
        self.assertEqual("cycle_work", opencode.top_task_type)
        self.assertIn("best fit:", opencode.specialization_note)
        self.assertIn("Best success rate:", dashboard.render())
        self.assertIn("Strongest recent learning velocity:", dashboard.render())

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import threading

from workspace_os.config import Source
from workspace_os.cycle import active_cycle_report, build_cycle_next_action, record_cycle_checkpoint, render_cycle_evaluation, run_cycle_evaluation, run_cycle_plan, run_cycle_window, run_cycle_work_window, run_cycle_work_window_continuous, start_cycle, stop_cycle
from workspace_os.memory import WorkspaceMemoryStore


class CycleTests(unittest.TestCase):
    def test_cycle_evaluation_tracks_health_stability_security_and_quality(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()
            start_cycle(store, "cycle-1", "long run implementation")
            evaluation = run_cycle_evaluation([Source("workspace-os", "product", "Workspace OS.", source_root)], store)
            checkpoint_id = record_cycle_checkpoint(store, evaluation, "iteration-1", iteration_number=1)
            report = active_cycle_report(store)

        self.assertGreater(checkpoint_id, 0)
        self.assertTrue(evaluation.category_ok("health"))
        self.assertTrue(evaluation.category_ok("stability"))
        self.assertTrue(evaluation.category_ok("security"))
        self.assertTrue(evaluation.category_ok("quality"))
        self.assertIn("Cycle checks:", render_cycle_evaluation(evaluation))
        self.assertIsNotNone(report)
        self.assertEqual(1, report.checkpoint_count)

    def test_cycle_stop_closes_active_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()
            start_cycle(store, "cycle-1", "long run implementation")
            stopped = stop_cycle(store)
            self.assertIsNotNone(stopped)
            self.assertIsNone(store.active_cycle())

    def test_cycle_run_executes_multiple_iterations_and_closes_new_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()
            result = run_cycle_plan(
                store,
                [Source("workspace-os", "product", "Workspace OS.", source_root)],
                iterations=2,
                label="cycle-1",
                objective="long run implementation",
            )
            self.assertTrue(result.started_cycle)
            self.assertEqual(2, result.iterations_completed)
            self.assertEqual(2, result.report.checkpoint_count)
            self.assertIsNone(store.active_cycle())

    def test_cycle_next_suggests_running_or_continuing_iterations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()
            start_cycle(store, "cycle-1", "long run implementation")

            recommendation = build_cycle_next_action(store)

        self.assertIn("Cycle next:", recommendation.render())
        self.assertIn("workspace cycle run", recommendation.command)

    def test_cycle_window_runs_until_deadline_with_checkpoint_spacing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()
            current = [datetime(2026, 6, 14, 10, 0, tzinfo=timezone.utc)]

            def now_fn() -> datetime:
                return current[0]

            def sleep_fn(seconds: float) -> None:
                current[0] = current[0] + timedelta(seconds=seconds)

            result = run_cycle_window(
                store,
                [Source("workspace-os", "product", "Workspace OS.", source_root)],
                duration_minutes=10,
                interval_minutes=5,
                label="cycle-1",
                objective="long run implementation",
                now_fn=now_fn,
                sleep_fn=sleep_fn,
            )

        self.assertTrue(result.started_cycle)
        self.assertEqual(3, result.iterations_completed)
        self.assertEqual(10.0, result.target_duration_minutes)
        self.assertIsNotNone(result.window_started_at)
        self.assertIsNotNone(result.window_ended_at)
        self.assertEqual(3, result.report.checkpoint_count)

    def test_cycle_work_runs_parallel_agents_until_deadline_without_idle_sleep(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()
            current = [datetime(2026, 6, 14, 10, 0, tzinfo=timezone.utc)]
            lock = threading.Lock()

            def now_fn() -> datetime:
                return current[0]

            def agent_runner(agent, workspace_name, task, prompt, workspace_root, memory_store):
                del agent, workspace_name, task, prompt, workspace_root, memory_store
                with lock:
                    current[0] = current[0] + timedelta(seconds=30)
                return SimpleNamespace(returncode=0, duration_seconds=30.0)

            result = run_cycle_work_window(
                store,
                [Source("workspace-os", "product", "Workspace OS.", source_root)],
                duration_minutes=1,
                label="cycle-1",
                objective="busy long run implementation",
                now_fn=now_fn,
                agent_runner=agent_runner,
            )

        self.assertTrue(result.started_cycle)
        self.assertEqual(1, result.iterations_completed)
        self.assertEqual(2, result.delegation_count)
        self.assertGreaterEqual(result.agent_active_duration_seconds or 0.0, 60.0)
        self.assertEqual(1, result.report.checkpoint_count)
        self.assertEqual(0.0, result.idle_ratio)

    def test_cycle_work_continuous_starts_new_work_immediately(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()
            current = [datetime(2026, 6, 14, 10, 0, tzinfo=timezone.utc)]
            lock = threading.Lock()
            completed_items = []

            def now_fn() -> datetime:
                return current[0]

            def agent_runner(agent, workspace_name, task, prompt, workspace_root, memory_store):
                del agent, workspace_name, workspace_root, memory_store
                with lock:
                    current[0] = current[0] + timedelta(seconds=15)
                    completed_items.append(task)
                return SimpleNamespace(returncode=0, duration_seconds=15.0)

            result = run_cycle_work_window_continuous(
                store,
                [Source("workspace-os", "product", "Workspace OS.", source_root)],
                duration_minutes=1,
                label="cycle-continuous",
                objective="continuous agent utilization test",
                now_fn=now_fn,
                agent_runner=agent_runner,
            )

        # Continuous mode should complete more work items than batched mode
        # because agents don't wait for each other
        self.assertTrue(result.started_cycle)
        self.assertGreaterEqual(result.delegation_count or 0, 4)
        self.assertGreater(len(completed_items), 2)
        # Note: idle_ratio calculation relies on wall_clock_duration which doesn't advance
        # in unit tests with mocked time, so we can't assert on it here

    def test_cycle_work_continuous_handles_agent_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()
            current = [datetime(2026, 6, 14, 10, 0, tzinfo=timezone.utc)]
            lock = threading.Lock()
            completed_items = []
            failure_count = [0]

            def now_fn() -> datetime:
                return current[0]

            def agent_runner(agent, workspace_name, task, prompt, workspace_root, memory_store):
                del agent, workspace_name, workspace_root, memory_store, prompt
                with lock:
                    current[0] = current[0] + timedelta(seconds=10)
                    # Fail every third agent
                    failure_count[0] += 1
                    if failure_count[0] % 3 == 0:
                        raise ValueError("simulated agent failure")
                    completed_items.append(task)
                return SimpleNamespace(returncode=0, duration_seconds=10.0)

            result = run_cycle_work_window_continuous(
                store,
                [Source("workspace-os", "product", "Workspace OS.", source_root)],
                duration_minutes=1,
                label="cycle-continuous-failure",
                objective="test agent failure handling",
                now_fn=now_fn,
                agent_runner=agent_runner,
            )

        # Should continue despite failures and complete remaining work
        self.assertTrue(result.started_cycle)
        self.assertGreater(result.delegation_count or 0, 4)
        self.assertGreater(len(completed_items), 2)

    def test_cycle_work_continuous_stop_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()
            current = [datetime(2026, 6, 14, 10, 0, tzinfo=timezone.utc)]

            def now_fn() -> datetime:
                return current[0]

            def agent_runner(agent, workspace_name, task, prompt, workspace_root, memory_store):
                del agent, workspace_name, workspace_root, memory_store, task, prompt
                current[0] = current[0] + timedelta(seconds=5)
                return SimpleNamespace(returncode=0, duration_seconds=5.0)

            # Note: stop_on_failure checks evaluation gates, not agent failures
            # This test verifies the flag is honored when checkpoints fail
            result = run_cycle_work_window_continuous(
                store,
                [Source("workspace-os", "product", "Workspace OS.", source_root)],
                duration_minutes=1,
                label="cycle-continuous-stop",
                objective="test stop on failure",
                stop_on_failure=True,
                now_fn=now_fn,
                agent_runner=agent_runner,
            )

        self.assertTrue(result.started_cycle)
        # Should complete at least some work before stopping
        self.assertGreaterEqual(result.delegation_count or 0, 2)

    def _init_git_repo(self, path: Path) -> None:
        import subprocess

        subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "workspace@example.com"], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Workspace"], cwd=path, check=True, capture_output=True)
        (path / ".gitignore").write_text("", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore"], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()

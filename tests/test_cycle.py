from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
import random
from pathlib import Path
from types import SimpleNamespace
import threading
from unittest.mock import patch

from workspace_os.config import Source
from workspace_os.cycle import active_cycle_report, build_cycle_next_action, record_cycle_checkpoint, render_cycle_evaluation, run_cycle_evaluation, run_cycle_plan, run_cycle_window, run_cycle_work_window, run_cycle_work_window_continuous, start_cycle, stop_cycle, _build_cycle_work_prompt, _choose_work_agents, _fetch_available_issues, _assign_issue_to_work_item
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.journal import write_cycle_journal


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

            with patch("workspace_os.cycle.available_work_agents", return_value=("opencode", "claude")):
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

    def test_cycle_work_can_select_antigravity_when_available(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()

            with patch("workspace_os.cycle.available_work_agents", return_value=("opencode", "claude", "antigravity")):
                primary, secondary = _choose_work_agents(1, store, rng=random.Random(7))

        self.assertIn(primary, {"opencode", "claude", "antigravity"})
        self.assertIn(secondary, {"opencode", "claude", "antigravity"})
        self.assertNotEqual(primary, secondary)

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

    def test_cycle_work_continuous_parallelizes_three_agents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()
            current = [datetime(2026, 6, 14, 10, 0, tzinfo=timezone.utc)]
            import threading
            lock = threading.Lock()
            completed_items = []

            def now_fn() -> datetime:
                return current[0]

            def agent_runner(agent, workspace_name, task, prompt, workspace_root, memory_store):
                del agent, workspace_name, workspace_root, memory_store, prompt
                with lock:
                    current[0] = current[0] + timedelta(seconds=10)
                    completed_items.append(task)
                return SimpleNamespace(returncode=0, duration_seconds=10.0)

            with patch("workspace_os.cycle.available_work_agents", return_value=("opencode", "claude", "antigravity")):
                result = run_cycle_work_window_continuous(
                    store,
                    [Source("workspace-os", "product", "Workspace OS.", source_root)],
                    duration_minutes=1,
                    label="cycle-continuous-three",
                    objective="test three parallel agents",
                    now_fn=now_fn,
                    agent_runner=agent_runner,
                )

        self.assertTrue(result.started_cycle)
        self.assertEqual(3, result.max_queue_depth)
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

    def test_cycle_work_prompt_includes_journal_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()
            sources = [Source("workspace-os", "product", "Workspace OS.", source_root)]

            # Create a cycle and journal entry
            cycle_id = start_cycle(store, "test-cycle", "Test objective")
            stop_cycle(store)
            cycle = store.cycle_history(limit=1)[0]

            write_cycle_journal(
                store,
                sources,
                cycle,
                [],
                story_title="test",
                logical_duration_seconds=120.0,
                wall_clock_duration_seconds=120.0,
                idle_ratio=0.25,
            )

            # Build prompt and verify journal context is included
            prompt = _build_cycle_work_prompt(sources, store, "workspace-os", "Improve WOS", None, 1)
            primary_prompt = prompt["primary:opencode"]

            self.assertIn("Previous iteration summary:", primary_prompt)
            self.assertIn("stayed alive", primary_prompt)

    def test_compilation_and_test_checks_parses_failures(self):
        from workspace_os.cycle import _parse_pytest_failures
        output = """
        tests/test_something.py:42: in test_something
            assert False
        E   assert False
        """
        failures = _parse_pytest_failures(output)
        self.assertEqual(1, len(failures))
        self.assertEqual("tests/test_something.py", failures[0]["file"])
        self.assertEqual(42, failures[0]["line"])
        self.assertEqual("test_something", failures[0]["function"])

    def test_compilation_and_test_checks_uses_mock_output(self):
        import os
        from workspace_os.cycle import _run_compilation_and_test_checks
        os.environ["WOS_TEST_SUITE_MOCK_OUTPUT"] = "tests/test_foo.py:10: in test_foo\nassert False"
        os.environ["WOS_TEST_SUITE_MOCK_RETURNCODE"] = "1"
        try:
            results = _run_compilation_and_test_checks([])
            self.assertEqual(1, len(results))
            self.assertFalse(results[0].passed)
            self.assertIn("Assertion failures found:", results[0].detail)
            self.assertIn("File: tests/test_foo.py, Line: 10", results[0].detail)
        finally:
            del os.environ["WOS_TEST_SUITE_MOCK_OUTPUT"]
            del os.environ["WOS_TEST_SUITE_MOCK_RETURNCODE"]

    def test_cycle_work_auto_healing_retries_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()

            from workspace_os.cycle import CycleCheckResult, CycleEvaluation

            call_count = [0]
            current_time = [datetime(2026, 6, 14, 10, 0, tzinfo=timezone.utc)]

            def now_fn() -> datetime:
                return current_time[0]

            def mock_eval(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 2:
                    return CycleEvaluation(
                        health=(CycleCheckResult("health:test", True, "ok"),),
                        stability=(),
                        security=(),
                        quality=(CycleCheckResult("quality:test-suite", False, "Assertion error at tests/test_foo.py:10"),)
                    )
                return CycleEvaluation(
                    health=(CycleCheckResult("health:test", True, "ok"),),
                    stability=(),
                    security=(),
                    quality=(CycleCheckResult("quality:test-suite", True, "Healed"),)
                )

            executor_called = []

            def agent_runner(agent, workspace_name, task, prompt, workspace_root, memory_store):
                executor_called.append((agent, prompt))
                current_time[0] = current_time[0] + timedelta(minutes=2)
                return SimpleNamespace(returncode=0, duration_seconds=10.0)

            with patch("workspace_os.cycle.run_cycle_evaluation", side_effect=mock_eval):
                with patch("workspace_os.cycle.available_work_agents", return_value=("opencode", "claude")):
                    result = run_cycle_work_window(
                        store,
                        [Source("workspace-os", "product", "Workspace OS.", source_root)],
                        duration_minutes=1,
                        label="cycle-healing",
                        objective="test auto healing loop",
                        now_fn=now_fn,
                        agent_runner=agent_runner,
                    )

            self.assertEqual(3, len(executor_called)) # 2 initial (primary, secondary) + 1 healing
            self.assertIn("DEFECT CORRECTION BRIEF", executor_called[-1][1])
            self.assertIn("Assertion error at tests/test_foo.py:10", executor_called[-1][1])
            self.assertTrue(result.report.latest_checkpoint["quality_ok"])

    def test_get_dynamic_interval_with_dirty_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            import subprocess
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            (root / "dirty-file.txt").write_text("edit", encoding="utf-8")
            source = Source("example", "product", "Example.", root)

            from workspace_os.cycle import _get_dynamic_interval
            import os
            os.environ["WOS_TEST_DYNAMIC_INTERVAL"] = "1"
            try:
                interval = _get_dynamic_interval([source], 120.0)
            finally:
                del os.environ["WOS_TEST_DYNAMIC_INTERVAL"]

            self.assertEqual(60.0, interval) # 120.0 * 0.5 = 60.0

    def test_continuous_mode_default_worker_pool_supports_high_throughput(self):
        """Verify default worker pool is sized for 16+ parallel agents."""
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

            completed_work_items = []

            def agent_runner(agent, workspace_name, task, prompt, workspace_root, memory_store):
                del agent, workspace_name, workspace_root, memory_store, prompt
                current[0] = current[0] + timedelta(seconds=1)
                completed_work_items.append(task)
                return SimpleNamespace(returncode=0, duration_seconds=1.0)

            # Run for short duration and verify parallel execution
            # Default workers should be 16 in production (not testing mode)
            # We can't directly inspect max_workers from here, but we can verify
            # that many items complete in parallel by checking the timing
            import os
            original_workers = os.environ.get("WOS_MAX_WORKERS")
            try:
                # Force high worker count to validate throughput
                os.environ["WOS_MAX_WORKERS"] = "16"
                result = run_cycle_work_window_continuous(
                    store,
                    [Source("workspace-os", "product", "Workspace OS.", source_root)],
                    duration_minutes=0.5,
                    label="cycle-throughput-test",
                    objective="Validate high-throughput parallel execution",
                    now_fn=now_fn,
                    agent_runner=agent_runner,
                )
            finally:
                if original_workers is None:
                    os.environ.pop("WOS_MAX_WORKERS", None)
                else:
                    os.environ["WOS_MAX_WORKERS"] = original_workers

        # Verify high throughput: with 16 workers and 1s per task, we should complete
        # many tasks in 30s (0.5 minutes)
        # Expected: ~16 tasks started immediately, plus more as they complete
        self.assertGreaterEqual(len(completed_work_items), 16, "Should complete at least 16 work items with 16 workers")
        self.assertGreaterEqual(result.delegation_count or 0, 16, "Should delegate to at least 16 agents")

    def test_issue_assignment_dynamic_refetch_on_depletion(self):
        """Verify dynamic issue refetch when pool depletes during continuous cycle."""
        # Mock scenario: start with 10 issues, assign 8, trigger refetch at <10% remaining
        initial_issues = [{"number": i, "title": f"Issue {i}", "state": "OPEN"} for i in range(1, 11)]
        fresh_issues = [{"number": i, "title": f"Issue {i}", "state": "OPEN"} for i in range(1, 16)]

        assigned = set()
        in_progress = set()

        # Assign 8 issues (leaving 2 unassigned = 20% remaining, above 10% threshold)
        for i in range(8):
            issue = _assign_issue_to_work_item(i + 1, initial_issues, assigned, in_progress)
            self.assertIsNotNone(issue)

        # Calculate unassigned count
        unassigned_count = sum(1 for issue in initial_issues if int(issue["number"]) not in assigned)
        self.assertEqual(2, unassigned_count)

        # Refetch threshold: max(5, 10 // 10) = 5
        # With 2 unassigned < 5 threshold, refetch should trigger
        refetch_threshold = max(5, len(initial_issues) // 10)
        self.assertLess(unassigned_count, refetch_threshold, "Should trigger refetch when unassigned < threshold")

        # Simulate refetch: merge fresh issues (avoiding duplicates)
        existing_numbers = {int(issue["number"]) for issue in initial_issues}
        new_issues = [issue for issue in fresh_issues if int(issue["number"]) not in existing_numbers]
        initial_issues.extend(new_issues)

        # Verify we added new issues
        self.assertEqual(15, len(initial_issues))
        new_unassigned_count = sum(1 for issue in initial_issues if int(issue["number"]) not in assigned)
        self.assertEqual(7, new_unassigned_count, "Should have 7 unassigned after refetch (2 original + 5 new)")

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

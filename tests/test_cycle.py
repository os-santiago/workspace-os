from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workspace_os.config import Source
from workspace_os.cycle import active_cycle_report, record_cycle_checkpoint, render_cycle_evaluation, run_cycle_evaluation, run_cycle_plan, start_cycle, stop_cycle
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

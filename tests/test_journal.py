from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import threading

from workspace_os.config import Source
from workspace_os.cycle import run_cycle_window, run_cycle_work_window
from workspace_os.journal import write_cycle_journal, detect_plan_coverage_from_commits, detect_plan_gaps
from workspace_os.memory import WorkspaceMemoryStore


class JournalTests(unittest.TestCase):
    def test_cycle_watch_writes_narrative_journal_and_metrics(self):
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
                duration_minutes=0,
                interval_minutes=1,
                label="cycle-1",
                objective="journal test",
                now_fn=now_fn,
                sleep_fn=sleep_fn,
            )
            journal = write_cycle_journal(
                store,
                [Source("workspace-os", "product", "Workspace OS.", source_root)],
                result.report.cycle,
                store.cycle_checkpoints(result.cycle_id, limit=1000),
                story_title=result.report.cycle["label"],
            )

            self.assertTrue(journal.entry_path.exists())
            self.assertTrue((journal.entry_path / "journal.json").exists())
            self.assertTrue((journal.entry_path / "journal.md").exists())
            self.assertGreaterEqual(journal.checkpoint_count, 1)
            self.assertTrue(journal.story_lines)
            self.assertIn("Journal entry:", journal.render())
            self.assertIn("wall_clock_duration=", journal.render())
            self.assertIn("idle_ratio=", journal.render())
            self.assertIn("Story:", journal.render())

    def test_cycle_work_writes_narrative_journal_and_delegation_metrics(self):
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
                objective="busy journal test",
                now_fn=now_fn,
                agent_runner=agent_runner,
            )
            journal = write_cycle_journal(
                store,
                [Source("workspace-os", "product", "Workspace OS.", source_root)],
                result.report.cycle,
                store.cycle_checkpoints(result.cycle_id, limit=1000),
                story_title=result.report.cycle["label"],
                logical_duration_seconds=result.logical_duration_seconds,
                wall_clock_duration_seconds=result.wall_clock_duration_seconds,
                sleep_duration_seconds=result.sleep_duration_seconds,
                logical_active_duration_seconds=result.logical_active_duration_seconds,
                wall_clock_active_duration_seconds=result.wall_clock_active_duration_seconds,
                idle_ratio=result.idle_ratio,
                delegation_count=result.delegation_count,
                agent_active_duration_seconds=result.agent_active_duration_seconds,
            )

            self.assertTrue(journal.entry_path.exists())
            self.assertIn("delegation_count=", journal.render())
            self.assertIn("agent_active_duration=", journal.render())
            self.assertIn("Delegations issued:", journal.render())

    def test_plan_coverage_detects_keywords_and_file_patterns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)

            # Create commits with plan-related keywords
            (source_root / "cycle.py").write_text("# cycle orchestration", encoding="utf-8")
            self._git_commit(source_root, "feat: add cycle checkpoint logic")

            (source_root / "agent_adapter.py").write_text("# agent routing", encoding="utf-8")
            self._git_commit(source_root, "feat: improve agent delegation")

            # Use "1 week ago" format which git log accepts reliably
            coverage = detect_plan_coverage_from_commits(
                [Source("workspace-os", "product", "Workspace OS.", source_root)],
                "1 week ago",
                "now",
            )

            self.assertIn("cycle orchestration", coverage)
            self.assertIn("agent orchestration", coverage)

    def test_plan_gaps_identifies_unaddressed_items(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)

            # Only commit cycle-related work
            (source_root / "cycle.py").write_text("# cycle orchestration", encoding="utf-8")
            self._git_commit(source_root, "feat: add cycle checkpoint logic")

            gaps = detect_plan_gaps(
                [Source("workspace-os", "product", "Workspace OS.", source_root)],
                "1 week ago",
                "now",
            )

            # Gaps should include items that received no commits
            self.assertGreater(len(gaps), 0)
            # Cycle orchestration was addressed, so it should NOT be in gaps
            self.assertNotIn("cycle orchestration", gaps)

    def test_journal_includes_plan_gaps_when_no_coverage(self):
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
                duration_minutes=0,
                interval_minutes=1,
                label="cycle-1",
                objective="plan gap test",
                now_fn=now_fn,
                sleep_fn=sleep_fn,
            )

            journal = write_cycle_journal(
                store,
                [Source("workspace-os", "product", "Workspace OS.", source_root)],
                result.report.cycle,
                store.cycle_checkpoints(result.cycle_id, limit=1000),
                story_title=result.report.cycle["label"],
            )

            rendered = journal.render()
            # With no commits in the window, all plan items should be gaps
            self.assertIn("Plan gaps:", rendered)
            self.assertGreater(len(journal.functional_metrics.plan_gaps), 0)

    def _init_git_repo(self, path: Path) -> None:
        import subprocess

        subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "workspace@example.com"], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Workspace"], cwd=path, check=True, capture_output=True)
        (path / ".gitignore").write_text("", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore"], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)

    def _git_commit(self, path: Path, message: str) -> None:
        import subprocess

        subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", message], cwd=path, check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()

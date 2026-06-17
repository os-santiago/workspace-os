from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from workspace_os.config import Source
from workspace_os.cycle import run_cycle_window
from workspace_os.journal import write_cycle_journal
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
            self.assertIn("Story:", journal.render())

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

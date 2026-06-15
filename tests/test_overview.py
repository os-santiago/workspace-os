from pathlib import Path
import tempfile
import unittest

from workspace_os.batch import start_batch, start_process
from workspace_os.config import Source
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.overview import build_workspace_handoff, build_workspace_next_action, build_workspace_overview


class OverviewTests(unittest.TestCase):
    def test_workspace_overview_renders_consolidated_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            memory = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            store.record_preference("tone", "terse")
            start_process(store, "process-1", "overview flow", started_at="2026-06-14T09:00:00+00:00")
            start_batch(store, "batch-1", "overview batch", started_at="2026-06-14T09:05:00+00:00")
            store.record_agent_launch("codex", "review overview", "source", launched_at="2026-06-14T09:06:00+00:00")
            store.record_process_checkpoint(
                "checkpoint-1",
                note="first pass",
                created_at="2026-06-14T09:07:00+00:00",
            )
            store.record_context_snapshot("global", "overview-test", "snapshot summary", "snapshot markdown")

            overview = build_workspace_overview([Source("source", "product", "Product.", source_root)], store, workspace="source")

        rendered = overview.render()

        self.assertIn("Workspace overview:", rendered)
        self.assertIn("Sources:", rendered)
        self.assertIn("Memory:", rendered)
        self.assertIn("Profile:", rendered)
        self.assertIn("Habits:", rendered)
        self.assertIn("Process:", rendered)
        self.assertIn("Batch:", rendered)
        self.assertIn("Context:", rendered)
        self.assertIn("Recent launches:", rendered)
        self.assertIn("process-1", rendered)
        self.assertIn("batch-1", rendered)

    def test_workspace_handoff_renders_concise_closing_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            memory = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_process(store, "process-1", "handoff flow", started_at="2026-06-14T09:00:00+00:00")
            start_batch(store, "batch-1", "handoff batch", started_at="2026-06-14T09:05:00+00:00")
            store.record_agent_launch("claude", "review handoff", "source", launched_at="2026-06-14T09:06:00+00:00")
            store.record_process_checkpoint(
                "checkpoint-1",
                note="first pass",
                created_at="2026-06-14T09:07:00+00:00",
            )
            store.record_context_snapshot("global", "handoff-test", "snapshot summary", "snapshot markdown")

            handoff = build_workspace_handoff([Source("source", "product", "Product.", source_root)], store, workspace="source")

        rendered = handoff.render()

        self.assertIn("Workspace handoff:", rendered)
        self.assertIn("State:", rendered)
        self.assertIn("Profile:", rendered)
        self.assertIn("Habits:", rendered)
        self.assertIn("Process:", rendered)
        self.assertIn("Batch:", rendered)
        self.assertIn("Context:", rendered)
        self.assertIn("Next:", rendered)
        self.assertIn("source", rendered)

    def test_workspace_next_action_renders_operational_step(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            memory = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_process(store, "process-1", "next action flow", started_at="2026-06-14T09:00:00+00:00")
            start_batch(store, "batch-1", "next action batch", started_at="2026-06-14T09:05:00+00:00")

            next_action = build_workspace_next_action([Source("source", "product", "Product.", source_root)], store, workspace="source")

        rendered = next_action.render()

        self.assertIn("Workspace next action:", rendered)
        self.assertIn("Next:", rendered)
        self.assertIn("source", rendered)

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

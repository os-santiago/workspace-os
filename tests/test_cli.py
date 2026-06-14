from pathlib import Path
import json
import tempfile
import unittest

from workspace_os.batch import start_batch, start_process
from workspace_os.cli import main
from workspace_os.memory import WorkspaceMemoryStore


class CliTests(unittest.TestCase):
    def test_handoff_command_writes_markdown_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            output = root / "handoff.md"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_process(store, "process-1", "cli export", started_at="2026-06-14T10:00:00+00:00")
            start_batch(store, "batch-1", "cli export", started_at="2026-06-14T10:05:00+00:00")
            store.record_process_checkpoint("checkpoint-1", note="first pass", created_at="2026-06-14T10:06:00+00:00")

            exit_code = main(["--config", str(config), "handoff", "--output", str(output)])

            self.assertEqual(0, exit_code)
            self.assertTrue(output.exists())
            rendered = output.read_text(encoding="utf-8")
            self.assertIn("Workspace handoff:", rendered)
            self.assertIn("process-1", rendered)

    def test_batch_stop_auto_writes_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            handoff = root / "handoff.md"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_batch(store, "batch-1", "cli auto handoff", started_at="2026-06-14T10:05:00+00:00")

            exit_code = main(["--config", str(config), "batch", "stop"])

            self.assertEqual(0, exit_code)
            self.assertTrue(handoff.exists())
            rendered = handoff.read_text(encoding="utf-8")
            self.assertIn("Workspace handoff:", rendered)
            self.assertIn("batch-1", rendered)

    def test_batch_handoff_command_writes_markdown_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            handoff = root / "batch-handoff.md"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_batch(store, "batch-1", "cli handoff", started_at="2026-06-14T10:05:00+00:00")

            exit_code = main(["--config", str(config), "batch", "handoff", "--output", str(handoff)])

            self.assertEqual(0, exit_code)
            self.assertTrue(handoff.exists())
            rendered = handoff.read_text(encoding="utf-8")
            self.assertIn("Batch report", rendered)
            self.assertIn("Workspace handoff:", rendered)

    def test_process_stop_auto_writes_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            handoff = root / "handoff.md"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_process(store, "process-1", "cli auto handoff", started_at="2026-06-14T10:00:00+00:00")

            exit_code = main(["--config", str(config), "process", "stop"])

            self.assertEqual(0, exit_code)
            self.assertTrue(handoff.exists())
            rendered = handoff.read_text(encoding="utf-8")
            self.assertIn("Workspace handoff:", rendered)
            self.assertIn("process-1", rendered)

    def test_process_handoff_command_writes_markdown_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            handoff = root / "process-handoff.md"
            config.write_text(
                json.dumps(
                    {
                        "workspace_root": ".",
                        "memory_db": "memory.sqlite3",
                        "sources": [
                            {
                                "name": "source",
                                "type": "product",
                                "responsibility": "Product.",
                                "path": "source",
                                "search": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_process(store, "process-1", "cli handoff", started_at="2026-06-14T10:00:00+00:00")

            exit_code = main(["--config", str(config), "process", "handoff", "--output", str(handoff)])

            self.assertEqual(0, exit_code)
            self.assertTrue(handoff.exists())
            rendered = handoff.read_text(encoding="utf-8")
            self.assertIn("Process summary", rendered)
            self.assertIn("Workspace handoff:", rendered)

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

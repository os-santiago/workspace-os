from contextlib import redirect_stdout
from pathlib import Path
import io
import os
import tempfile
import unittest

from workspace_os.config import Source
from workspace_os.shell import WorkspaceShell


class ShellTests(unittest.TestCase):
    def test_shell_switches_workspaces_and_records_chat_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adev = root / "adev"
            kb = root / "kb"
            adev.mkdir()
            kb.mkdir()
            self._init_git_repo(adev)
            self._init_git_repo(kb)
            (adev / "ADEV.md").write_text("ADEV must stay concise.\n", encoding="utf-8")
            memory_path = root / "memory.sqlite3"
            shell = WorkspaceShell(
                [
                    Source("adev", "doctrine", "Doctrine.", adev),
                    Source("kb", "evidence", "Evidence.", kb),
                ],
                memory_path=memory_path,
                session_id="shell-test",
            )

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_ws("adev")
                shell.default("Remember ADEV")

            rendered = buffer.getvalue()
            stats = shell.memory_store.stats()

        self.assertIn("active workspace=adev", rendered)
        self.assertIn("Learning engine: activated", rendered)
        self.assertEqual(2, stats["conversation_turns"])

    def test_shell_lists_workspaces(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")

            self.assertIn("Habits:", shell.intro)

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_workspaces("")

            rendered = buffer.getvalue()

        self.assertIn("source", rendered)

    def test_shell_profile_and_alias_are_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_profile("tone terse")
                shell.do_profile("detail_level minimal")
                shell.do_profile("default_workspace source")
                shell.do_alias("s /status")
                shell.default("Remember this")
                shell.do_habits("")
                expanded = shell.precmd("s")
                shell.do_launches("")

            rendered = buffer.getvalue()

        self.assertIn("saved profile tone", rendered)
        self.assertIn("Style: terse / minimal", rendered)
        self.assertIn("Operator habits", rendered)
        self.assertEqual("/status", expanded)
        self.assertEqual("source", shell.active_workspace)
        self.assertEqual("/status", shell.profile.shortcuts["s"])

    def test_shell_batch_commands_report_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_batch("start sprint-1 keep batches large")
                shell.do_batch("status")
                shell.do_batch("summary")
                shell.do_batch("stop")

            rendered = buffer.getvalue()

        self.assertIn("batch_started=", rendered)
        self.assertIn("Batch report", rendered)
        self.assertIn("delegations=", rendered)
        self.assertIn("batches=", rendered)

    def test_shell_process_commands_report_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_process("start iteration-1 ten-batch window")
                shell.do_process("checkpoint milestone-1 first checkpoint")
                shell.do_process("summary")
                shell.do_process("stop")

            rendered = buffer.getvalue()

        self.assertIn("process_started=", rendered)
        self.assertIn("checkpoint_recorded=", rendered)
        self.assertIn("Process summary", rendered)
        self.assertIn("batch_count=", rendered)
        self.assertIn("Process:", shell.intro)

    def test_shell_inspect_reports_consolidated_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_inspect("2")

            rendered = buffer.getvalue()

        self.assertIn("Workspace overview:", rendered)
        self.assertIn("Sources:", rendered)
        self.assertIn("Memory:", rendered)

    def test_shell_handoff_reports_concise_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_handoff("2")

            rendered = buffer.getvalue()

        self.assertIn("Workspace handoff:", rendered)
        self.assertIn("State:", rendered)
        self.assertIn("Next:", rendered)

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

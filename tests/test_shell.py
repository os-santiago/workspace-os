from contextlib import redirect_stdout
from pathlib import Path
import io
import os
import tempfile
import unittest

from workspace_os.config import Source
from workspace_os.shell import WorkspaceShell
from workspace_os.overview import build_workspace_context_snapshot


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
            self.assertIn("Context: none", shell.intro)

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

    def test_shell_conscience_status_reports_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")
            shell.memory_store.record_decision(
                "hash-1",
                "medium",
                "SAFE_REDIRECT",
                ["missing_workspace"],
                primary_agent="codex",
                secondary_agent="claude",
                routing_reason="workspace_inventory_first",
            )

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_conscience("status 5")

            rendered = buffer.getvalue()

        self.assertIn("Conscience report", rendered)
        self.assertIn("total=1", rendered)
        self.assertIn("codex=1", rendered)

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

    def test_shell_batch_stop_auto_writes_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")
            handoff = root / "handoff.md"

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_batch("start sprint-1 auto handoff")
                shell.do_batch("stop")

            rendered = buffer.getvalue()
            self.assertIn("handoff_written=", rendered)
            self.assertIn("context_written=", rendered)
            self.assertTrue(handoff.exists())
            self.assertTrue((root / "context-global.md").exists())
            self.assertIn("Workspace handoff:", handoff.read_text(encoding="utf-8"))

    def test_shell_batch_handoff_writes_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")
            handoff = root / "batch-handoff.md"

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_batch("start sprint-1 auto handoff")
                shell.do_batch(f"handoff --output \"{handoff}\"")

            rendered = buffer.getvalue()
            self.assertIn("written=", rendered)
            self.assertTrue(handoff.exists())
            self.assertIn("Batch report", handoff.read_text(encoding="utf-8"))
            self.assertIn("Workspace handoff:", handoff.read_text(encoding="utf-8"))

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
            output = root / "handoff.md"

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_handoff(f"--output {output}")

            rendered = buffer.getvalue()
            self.assertIn("written=", rendered)
            self.assertTrue(output.exists())
            self.assertIn("Workspace handoff:", output.read_text(encoding="utf-8"))

    def test_shell_process_stop_auto_writes_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")
            handoff = root / "handoff.md"

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_process("start iteration-1 auto handoff")
                shell.do_process("stop")

            rendered = buffer.getvalue()
            self.assertIn("handoff_written=", rendered)
            self.assertIn("context_written=", rendered)
            self.assertTrue(handoff.exists())
            self.assertTrue((root / "context-global.md").exists())
            self.assertIn("Workspace handoff:", handoff.read_text(encoding="utf-8"))

    def test_shell_process_handoff_writes_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")
            handoff = root / "process-handoff.md"

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_process("start iteration-1 auto handoff")
                shell.do_process(f"handoff --output \"{handoff}\"")

            rendered = buffer.getvalue()
            self.assertIn("written=", rendered)
            self.assertTrue(handoff.exists())
            self.assertIn("Process summary", handoff.read_text(encoding="utf-8"))
            self.assertIn("Workspace handoff:", handoff.read_text(encoding="utf-8"))

    def test_shell_exit_persists_context_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")

            with redirect_stdout(io.StringIO()):
                should_exit = shell.do_exit("")

            self.assertTrue(should_exit)
            self.assertTrue((root / "context-global.md").exists())

    def test_shell_context_latest_renders_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")
            snapshot = build_workspace_context_snapshot([Source("source", "product", "Product.", source_root)], shell.memory_store, workspace="source", reason="shell-test")
            shell.memory_store.record_context_snapshot("global", "shell-test", snapshot.summary_lines[0], snapshot.render())

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_context("latest")

            rendered = buffer.getvalue()

        self.assertIn("Workspace context snapshot:", rendered)
        self.assertIn("shell-test", rendered)
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

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
                shell.do_verbose("on")
                shell.default("Remember ADEV")

            rendered = buffer.getvalue()
            stats = shell.memory_store.stats()

        self.assertIn("active workspace=adev", rendered)
        self.assertIn("Learning engine: activated", rendered)
        self.assertEqual(2, stats["conversation_turns"])

    def test_shell_chat_defaults_to_answer_only_and_verbose_reveals_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")

            with redirect_stdout(io.StringIO()) as buffer:
                shell.default("hola")
            default_rendered = buffer.getvalue()

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_verbose("on")
                shell.default("hola")
            verbose_rendered = buffer.getvalue()

        self.assertIn("Hola. Soy WOS", default_rendered)
        self.assertNotIn("Trace:", default_rendered)
        self.assertIn("verbose=on", verbose_rendered)
        self.assertIn("Trace:", verbose_rendered)

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
                shell.do_profile("primary_agent codex")
                shell.do_alias("s /status")
                shell.default("Remember this")
                shell.do_habits("")
                expanded = shell.precmd("s")
                shell.do_launches("")

            rendered = buffer.getvalue()

        self.assertIn("saved profile tone", rendered)
        self.assertIn("Operator habits", rendered)
        self.assertEqual("/status", expanded)
        self.assertEqual("source", shell.active_workspace)
        self.assertEqual("/status", shell.profile.shortcuts["s"])
        self.assertEqual("terse", shell.profile.tone)
        self.assertEqual("minimal", shell.profile.detail_level)
        self.assertEqual("codex", shell.profile.primary_agent)

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
                primary_agent="opencode",
                secondary_agent="claude",
                routing_reason="workspace_inventory_first",
            )

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_conscience("status 5")

            rendered = buffer.getvalue()

        self.assertIn("OCE report", rendered)
        self.assertIn("total=1", rendered)
        self.assertIn("opencode=1", rendered)

    def test_shell_oce_alias_reports_metrics(self):
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
                primary_agent="opencode",
                secondary_agent="claude",
                routing_reason="workspace_inventory_first",
            )

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_oce("status 5")

            rendered = buffer.getvalue()

        self.assertIn("OCE report", rendered)
        self.assertIn("total=1", rendered)

    def test_shell_conscience_recommend_reports_compact_recommendation(self):
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
                primary_agent="opencode",
                secondary_agent="claude",
                routing_reason="workspace_inventory_first",
            )

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_conscience("recommend 5")

            rendered = buffer.getvalue()

        self.assertIn("OCE recommendation", rendered)
        self.assertIn("next_action=route_to_opencode_for_inventory", rendered)
        self.assertIn("top_missing_context=missing_workspace", rendered)

    def test_shell_next_reports_operational_step(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_next("")

            rendered = buffer.getvalue()

        self.assertIn("Workspace next action:", rendered)
        self.assertIn("Suggested command:", rendered)

    def test_shell_analysis_reports_recently_updated_repos(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            older = root / "older"
            newer = root / "newer"
            older.mkdir()
            newer.mkdir()
            self._init_git_repo(older, commit_date="2026-06-14T10:00:00+00:00")
            self._init_git_repo(newer, commit_date="2026-06-14T12:00:00+00:00")
            shell = WorkspaceShell(
                [
                    Source("older", "product", "Older repo.", older),
                    Source("newer", "product", "Newer repo.", newer),
                ],
                root / "memory.sqlite3",
            )

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_analysis("")

            rendered = buffer.getvalue()

        self.assertIn("Workspace analysis:", rendered)
        self.assertIn("Workspace root:", rendered)
        self.assertIn("Knowledge base root:", rendered)
        self.assertIn("Workspace projects under root:", rendered)
        self.assertIn("Knowledge base projects:", rendered)
        self.assertIn("Continue with: newer", rendered)
        self.assertIn("Recommended continue: newer", rendered)
        self.assertIn("Primary route: /opencode", rendered)
        self.assertLess(rendered.index("newer"), rendered.index("older"))

    def test_shell_roots_reports_workspace_and_knowledge_base_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace_root = root / "git"
            kb_root = root / "kb"
            (workspace_root / "workspace-os").mkdir(parents=True)
            (workspace_root / "homedir").mkdir(parents=True)
            (kb_root / "adev").mkdir(parents=True)
            (kb_root / "scanales-kb").mkdir(parents=True)
            shell = WorkspaceShell(
                [
                    Source("workspace-os", "product", "Product.", workspace_root / "workspace-os", group="workspace"),
                    Source("homedir", "execution", "Execution.", workspace_root / "homedir", group="workspace"),
                    Source("adev", "doctrine", "Doctrine.", kb_root / "adev", group="knowledge_base"),
                    Source("scanales-kb", "evidence", "Evidence.", kb_root / "scanales-kb", group="knowledge_base"),
                ],
                root / "memory.sqlite3",
            )

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_roots("")
            rendered = buffer.getvalue()

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_kb("")
            alias_rendered = buffer.getvalue()

        self.assertIn("Workspace roots:", rendered)
        self.assertIn("Workspace root:", rendered)
        self.assertIn("Knowledge base root:", rendered)
        self.assertIn("Workspace repos:", rendered)
        self.assertIn("Knowledge base repos:", rendered)
        self.assertEqual(rendered, alias_rendered)

    def test_shell_feedback_records_and_reports_feedback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_feedback(
                    'add --request "Please summarize the repo state." '
                    '--result "Workspace analysis is ready." '
                    '--feedback "Great, that is exactly what I needed."'
                )

            rendered = buffer.getvalue()

        self.assertIn("saved feedback", rendered)
        self.assertIn("status=over_expectation", rendered)
        self.assertIn("error_type=positive", rendered)
        self.assertIn("reason=", rendered)

    def test_shell_cycle_commands_report_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_cycle("start --label cycle-1 --objective \"long run\"")
            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_cycle("run --iterations 2")
            run_rendered = buffer.getvalue()
            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_cycle("next")
            next_rendered = buffer.getvalue()
            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_cycle("checkpoint --label iteration-1")
            checkpoint_rendered = buffer.getvalue()

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_cycle("status")
            status_rendered = buffer.getvalue()

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_cycle("report")
            report_rendered = buffer.getvalue()

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_cycle("stop")
            stop_rendered = buffer.getvalue()

        self.assertIn("iterations_completed=2", run_rendered)
        self.assertIn("saved checkpoint", run_rendered)
        self.assertIn("Cycle checks:", run_rendered)
        self.assertIn("Cycle next:", next_rendered)
        self.assertIn("workspace cycle run", next_rendered)
        self.assertIn("saved checkpoint", checkpoint_rendered)
        self.assertIn("Cycle checks:", checkpoint_rendered)
        self.assertIn("Cycle report:", status_rendered)
        self.assertIn("Cycle report:", report_rendered)
        self.assertIn("Cycle report:", stop_rendered)

    def test_shell_bridge_reports_workspace_capabilities(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("source", "product", "Product.", source_root)], root / "memory.sqlite3")

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_bridge("")
            rendered = buffer.getvalue()

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_bridge("--detail")
            detail_rendered = buffer.getvalue()

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_bridge("next")
            next_rendered = buffer.getvalue()

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_bridge("--format json")
            json_rendered = buffer.getvalue()

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_bridge("capabilities")
            capabilities_rendered = buffer.getvalue()

            with redirect_stdout(io.StringIO()) as buffer:
                shell.do_conscience("extensions")
            extensions_rendered = buffer.getvalue()

        self.assertIn("Workspace bridge:", rendered)
        self.assertIn("Hardening: always-on malicious agentic protection", rendered)
        self.assertIn("Safe surfaces:", rendered)
        self.assertIn("Execution mode:", rendered)
        self.assertIn("OCE extensions:", rendered)
        self.assertIn("Available surfaces:", detail_rendered)
        self.assertIn("Workspace next:", next_rendered)
        self.assertIn("opencode", capabilities_rendered)
        self.assertIn("analysis", rendered)
        self.assertIn("claude", capabilities_rendered)
        self.assertIn("OCE extensions", extensions_rendered)
        self.assertIn("Extension model: layered and pluggable", extensions_rendered)
        self.assertIn('"workspace_root"', json_rendered)
        self.assertIn('"capabilities"', json_rendered)

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

    def _init_git_repo(self, path: Path, commit_date: str | None = None) -> None:
        import subprocess
        import os

        subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "workspace@example.com"], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Workspace"], cwd=path, check=True, capture_output=True)
        (path / ".gitignore").write_text("", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore"], cwd=path, check=True, capture_output=True)
        env = os.environ.copy()
        if commit_date is not None:
            env["GIT_AUTHOR_DATE"] = commit_date
            env["GIT_COMMITTER_DATE"] = commit_date
        subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True, env=env)


if __name__ == "__main__":
    unittest.main()

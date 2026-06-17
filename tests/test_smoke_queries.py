from pathlib import Path
import tempfile
import unittest

from workspace_os.batch import start_batch, start_process
from workspace_os.cli import main
from workspace_os.config import Source
from workspace_os.cycle import start_cycle
from workspace_os.conversation import build_workspace_reply
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.shell import WorkspaceShell


class SmokeQueryTests(unittest.TestCase):
    def test_chat_smoke_queries_expect_operational_answers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            memory = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_process(store, "process-1", "smoke query flow", started_at="2026-06-14T10:00:00+00:00")
            start_batch(store, "batch-1", "smoke query batch", started_at="2026-06-14T10:05:00+00:00")
            start_cycle(store, "cycle-1", "smoke query cycle", started_at="2026-06-14T10:10:00+00:00")
            store.record_decision(
                "hash-1",
                "medium",
                "SAFE_REDIRECT",
                ["missing_workspace"],
                primary_agent="opencode",
                secondary_agent="claude",
                routing_reason="workspace_inventory_first",
            )

            cases = [
                (
                    "hola",
                    [
                        "Hola. Soy WOS",
                    ],
                ),
                (
                    "que hace esta aplicacion?",
                    [
                        "Workspace OS is your local workspace control plane.",
                        "routes ambiguous work through OCE",
                        "/oce",
                    ],
                ),
                (
                    "que proyectos tenemos en curso?",
                    [
                        "Workspace status:",
                        "Workspace root:",
                        "Knowledge base root:",
                        "Workspace projects under root:",
                        "Knowledge base projects:",
                        "Next step:",
                        "Primary route: /opencode",
                        "Optional cross-check: /claude",
                    ],
                ),
                (
                    "respondes siempre lo mismo?",
                    [
                        "No. I now answer by intent instead of repeating the same fallback.",
                    ],
                ),
                (
                    "quiero continuar con la implementacion de workspace-os",
                    [
                        "Ready. Continue with workspace-os.",
                        "Fastest path: /inspect, then /next.",
                        "Primary route: /opencode",
                        "Optional cross-check: /claude",
                    ],
                ),
                (
                    "what should we do next?",
                    [
                        "Primary route: /opencode",
                        "Optional cross-check: /claude",
                    ],
                ),
            ]

            for message, expectations in cases:
                with self.subTest(message=message):
                    reply = build_workspace_reply(
                        [Source("workspace-os", "product", "Workspace OS.", source_root)],
                        message,
                        memory_store=store,
                        session_id="smoke",
                        tone="terse",
                        detail_level="minimal",
                    )
                    for expectation in expectations:
                        self.assertIn(expectation, reply.reply)

    def test_cli_smoke_queries_expect_operational_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            config = root / "workspace.json"
            memory = root / "memory.sqlite3"
            config.write_text(
                """
{
  "workspace_root": ".",
  "memory_db": "memory.sqlite3",
  "sources": [
    {
      "name": "workspace-os",
      "type": "product",
      "responsibility": "Workspace OS.",
      "path": "workspace-os",
      "search": true
    }
  ]
}
""".strip(),
                encoding="utf-8",
            )
            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_process(store, "process-1", "smoke cli flow", started_at="2026-06-14T10:00:00+00:00")
            start_cycle(store, "cycle-1", "smoke cli cycle", started_at="2026-06-14T10:10:00+00:00")

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    exit_code = main(["--config", str(config), "next"])
                buffer.seek(0)
                next_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    analysis_exit_code = main(["--config", str(config), "analysis"])
                buffer.seek(0)
                analysis_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    bridge_exit_code = main(["--config", str(config), "bridge", "status"])
                buffer.seek(0)
                bridge_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    bridge_detail_exit_code = main(["--config", str(config), "bridge", "status", "--detail"])
                buffer.seek(0)
                bridge_detail_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    bridge_next_exit_code = main(["--config", str(config), "bridge", "next"])
                buffer.seek(0)
                bridge_next_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    bridge_caps_exit_code = main(["--config", str(config), "bridge", "capabilities"])
                buffer.seek(0)
                bridge_caps_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    exit_code_oce = main(["--config", str(config), "oce", "status"])
                buffer.seek(0)
                oce_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    cycle_run_exit_code = main(["--config", str(config), "cycle", "run", "--iterations", "2"])
                buffer.seek(0)
                cycle_run_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    cycle_status_exit_code = main(["--config", str(config), "cycle", "status"])
                buffer.seek(0)
                cycle_status_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    cycle_checkpoint_exit_code = main(["--config", str(config), "cycle", "checkpoint", "--label", "iteration-1"])
                buffer.seek(0)
                cycle_checkpoint_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    cycle_report_exit_code = main(["--config", str(config), "cycle", "report"])
                buffer.seek(0)
                cycle_report_rendered = buffer.read()

        self.assertEqual(0, exit_code)
        self.assertEqual(0, analysis_exit_code)
        self.assertEqual(0, bridge_exit_code)
        self.assertEqual(0, bridge_detail_exit_code)
        self.assertEqual(0, bridge_next_exit_code)
        self.assertEqual(0, bridge_caps_exit_code)
        self.assertEqual(0, exit_code_oce)
        self.assertEqual(0, cycle_run_exit_code)
        self.assertEqual(0, cycle_status_exit_code)
        self.assertEqual(0, cycle_checkpoint_exit_code)
        self.assertEqual(0, cycle_report_exit_code)
        self.assertIn("Workspace next action:", next_rendered)
        self.assertIn("Suggested command:", next_rendered)
        self.assertIn("Workspace analysis:", analysis_rendered)
        self.assertIn("Workspace root:", analysis_rendered)
        self.assertIn("Knowledge base root:", analysis_rendered)
        self.assertIn("Workspace projects under root:", analysis_rendered)
        self.assertIn("Knowledge base projects:", analysis_rendered)
        self.assertIn("Continue with:", analysis_rendered)
        self.assertIn("Recommended continue:", analysis_rendered)
        self.assertIn("Workspace bridge:", bridge_rendered)
        self.assertIn("Safe surfaces:", bridge_rendered)
        self.assertIn("Available surfaces:", bridge_detail_rendered)
        self.assertIn("Workspace next:", bridge_next_rendered)
        self.assertIn("Suggested command:", bridge_next_rendered)
        self.assertIn("analysis", bridge_rendered)
        self.assertIn("claude", bridge_caps_rendered)
        self.assertIn("OCE report", oce_rendered)
        self.assertIn("recommended_next_action", oce_rendered)
        self.assertIn("iterations_completed=2", cycle_run_rendered)
        self.assertIn("Cycle checks:", cycle_run_rendered)
        self.assertIn("Cycle report", cycle_status_rendered)
        self.assertIn("saved checkpoint", cycle_checkpoint_rendered)
        self.assertIn("Cycle checks:", cycle_checkpoint_rendered)
        self.assertIn("Cycle report", cycle_report_rendered)

    def test_shell_smoke_queries_expect_current_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            memory = root / "memory.sqlite3"
            store = WorkspaceMemoryStore(memory)
            store.ensure_schema()
            start_cycle(store, "cycle-1", "smoke shell cycle", started_at="2026-06-14T10:10:00+00:00")
            shell = WorkspaceShell([Source("workspace-os", "product", "Workspace OS.", source_root)], memory)

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    shell.do_next("")
                    shell.do_analysis("")
                    shell.do_bridge("")
                    shell.do_bridge("--detail")
                    shell.do_bridge("next")
                    shell.do_bridge("capabilities")
                    shell.do_oce("status 5")
                    shell.do_cycle("run --iterations 2")
                    shell.do_cycle("watch --duration-minutes 0 --interval-minutes 1")
                    shell.do_cycle("status")
                    shell.do_cycle("checkpoint --label iteration-1")
                    shell.do_cycle("report")
                    shell.default("que proyectos tenemos en curso?")
                buffer.seek(0)
                rendered = buffer.read()

        self.assertIn("Workspace next action:", rendered)
        self.assertIn("Workspace analysis:", rendered)
        self.assertIn("Workspace bridge:", rendered)
        self.assertIn("Safe surfaces:", rendered)
        self.assertIn("Available surfaces:", rendered)
        self.assertIn("Workspace next:", rendered)
        self.assertIn("Workspace root:", rendered)
        self.assertIn("Knowledge base root:", rendered)
        self.assertIn("Workspace projects under root:", rendered)
        self.assertIn("Knowledge base projects:", rendered)
        self.assertIn("Continue with:", rendered)
        self.assertIn("OCE report", rendered)
        self.assertIn("iterations_completed=2", rendered)
        self.assertIn("target_duration_minutes=0.00", rendered)
        self.assertIn("Cycle report", rendered)
        self.assertIn("Primary route: /opencode", rendered)
        self.assertIn("Optional cross-check: /claude", rendered)

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

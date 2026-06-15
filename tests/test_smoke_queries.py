from pathlib import Path
import tempfile
import unittest

from workspace_os.batch import start_batch, start_process
from workspace_os.cli import main
from workspace_os.config import Source
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
            store.record_decision(
                "hash-1",
                "medium",
                "SAFE_REDIRECT",
                ["missing_workspace"],
                primary_agent="codex",
                secondary_agent="claude",
                routing_reason="workspace_inventory_first",
            )

            cases = [
                (
                    "hola",
                    [
                        "Hola. Soy WOS",
                        "OCE recommendation: /codex",
                        "Suggested command: /codex",
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
                        "Tracked projects:",
                        "Next step: record the first process checkpoint",
                        "OCE recommendation: /codex",
                        "Fallback route: /claude",
                    ],
                ),
                (
                    "respondes siempre lo mismo?",
                    [
                        "No. I now answer by intent instead of repeating the same fallback.",
                        "route it to Codex first",
                        "OCE recommendation: /codex",
                    ],
                ),
                (
                    "what should we do next?",
                    [
                        "OCE recommendation: /codex",
                        "Suggested command: /codex",
                        "Fallback route: /claude",
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

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    exit_code = main(["--config", str(config), "next"])
                buffer.seek(0)
                next_rendered = buffer.read()

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    exit_code_oce = main(["--config", str(config), "oce", "status"])
                buffer.seek(0)
                oce_rendered = buffer.read()

        self.assertEqual(0, exit_code)
        self.assertEqual(0, exit_code_oce)
        self.assertIn("Workspace next action:", next_rendered)
        self.assertIn("Suggested command:", next_rendered)
        self.assertIn("OCE report", oce_rendered)
        self.assertIn("recommended_next_action", oce_rendered)

    def test_shell_smoke_queries_expect_current_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "workspace-os"
            source_root.mkdir()
            self._init_git_repo(source_root)
            shell = WorkspaceShell([Source("workspace-os", "product", "Workspace OS.", source_root)], root / "memory.sqlite3")

            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as buffer:
                from contextlib import redirect_stdout

                with redirect_stdout(buffer):
                    shell.do_next("")
                    shell.do_oce("status 5")
                    shell.default("que proyectos tenemos en curso?")
                buffer.seek(0)
                rendered = buffer.read()

        self.assertIn("Workspace next action:", rendered)
        self.assertIn("OCE report", rendered)
        self.assertIn("OCE recommendation: /codex", rendered)
        self.assertIn("Fallback route: /claude", rendered)

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

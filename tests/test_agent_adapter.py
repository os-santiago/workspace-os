from pathlib import Path
import tempfile
import unittest

from workspace_os.agent_adapter import build_agent_command, launch_agent
from workspace_os.memory import WorkspaceMemoryStore


class AgentAdapterTests(unittest.TestCase):
    def test_build_agent_command_uses_allowlisted_args(self):
        codex = build_agent_command("codex", Path("workspace"), "Do the task.")
        claude = build_agent_command("claude", Path("workspace"), "Do the task.")

        self.assertEqual(["codex", "exec"], codex[:2])
        self.assertIn("--allow-dangerously-skip-permissions", claude)
        self.assertIn("--add-dir", claude)

    def test_launch_agent_records_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()
            captured = {}

            def launcher(command, cwd):
                captured["command"] = command
                captured["cwd"] = cwd
                return 321

            pid = launch_agent(
                "claude",
                "adev",
                "Review the shell.",
                "Prompt text.",
                root,
                store,
                launcher=launcher,
            )

            launches = store.recent_launches(limit=1)

        self.assertEqual(321, pid)
        self.assertEqual("claude", launches[0]["agent"])
        self.assertEqual("adev", launches[0]["workspace"])
        self.assertEqual(root, captured["cwd"])
        self.assertIn("ADEV contract:", captured["command"][-1])
        self.assertIn("Read ADEV.md", captured["command"][-1])
        self.assertIn("Delegated prompt:", captured["command"][-1])


if __name__ == "__main__":
    unittest.main()

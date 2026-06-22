from pathlib import Path
import tempfile
import unittest
import os

from workspace_os.agent_adapter import build_agent_command, launch_agent
from workspace_os.memory import WorkspaceMemoryStore


class AgentAdapterTests(unittest.TestCase):
    def test_build_agent_command_no_dangerous_permissions(self):
        """Security fix: dangerous permission flags must be removed."""
        codex = build_agent_command("codex", Path("workspace"), "Do the task.")
        claude = build_agent_command("claude", Path("workspace"), "Do the task.")
        opencode = build_agent_command("opencode", Path("workspace"), "Do the task.")

        # Clear mock and test with direct antigravity command
        original_mock = os.environ.pop("WOS_ANTIGRAVITY_COMMAND", None)
        try:
            antigravity = build_agent_command("antigravity", Path("workspace"), "Do the task.")
            self.assertEqual("antigravity", antigravity[0])
            self.assertIn("Do the task.", antigravity)
        finally:
            if original_mock is not None:
                os.environ["WOS_ANTIGRAVITY_COMMAND"] = original_mock

        self.assertEqual(["codex", "exec"], codex[:2])
        # Security requirement: dangerous flags must NOT be present
        self.assertNotIn("--allow-dangerously-skip-permissions", claude)
        self.assertNotIn("--dangerously-skip-permissions", opencode)
        self.assertIn("--add-dir", claude)

    def test_launch_agent_records_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()
            captured = {}

            def launcher(command, cwd, *args, **kwargs):
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

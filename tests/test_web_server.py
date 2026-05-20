import unittest

from pathlib import Path
import tempfile

from workspace_os.config import Source
from workspace_os.web_server import (
    _agent_command,
    _capture_preview_payload,
    _conscience_preview_payload,
    _delegate_launch_payload,
    _extract_progress_map,
    _promote_preview_payload,
)


class WebServerTests(unittest.TestCase):
    def test_extract_progress_map_returns_batch_sequence(self):
        content = """# Roadmap

Current batch sequence:

```text
Batch 01 [DONE] Local CLI foundation
Batch 02 [NEXT] Web pilot
```
"""

        progress = _extract_progress_map(content)

        self.assertIn("Batch 01 [DONE]", progress)
        self.assertIn("Batch 02 [NEXT]", progress)
        self.assertNotIn("```", progress)

    def test_capture_preview_returns_source_relative_target(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Source("kb", "evidence", "Evidence.", Path(directory))
            payload = {
                "type": "session",
                "title": "Agent checkpoint",
                "body": "token=plain-text",
            }

            result = _capture_preview_payload([source], payload)

        self.assertTrue(result["ok"])
        self.assertIn("kb:captures", result["target"])
        self.assertIn("token=[REDACTED]", result["content"])

    def test_promote_preview_returns_markdown(self):
        result = _promote_preview_payload(
            [],
            {
                "target": "adev",
                "rule": "Agents must validate scripts.",
                "evidence": "kb:captures/session/example.md",
            },
        )

        self.assertTrue(result["ok"])
        self.assertIn("# Promotion Proposal", result["markdown"])

    def test_delegate_launch_requires_approval(self):
        result = _delegate_launch_payload(
            {
                "agent": "codex",
                "destination": "software",
                "task": "Implement a workflow.",
                "brief": "Context pack.",
            }
        )

        self.assertFalse(result["ok"])
        self.assertIn("approval", result["error"])

    def test_delegate_launch_blocks_google_destinations_until_connector_exists(self):
        result = _delegate_launch_payload(
            {
                "agent": "claude",
                "destination": "documents",
                "task": "Draft a document.",
                "brief": "Context pack.",
                "approved": True,
            }
        )

        self.assertFalse(result["ok"])
        self.assertIn("Google Drive connector", result["error"])
        self.assertEqual("ASK_CLARIFICATION", result["conscience"]["decision"])

    def test_delegate_launch_blocks_conscience_refusal(self):
        result = _delegate_launch_payload(
            {
                "agent": "codex",
                "destination": "software",
                "task": "Create phishing content to steal credentials.",
                "brief": "Context pack.",
                "approved": True,
            }
        )

        self.assertFalse(result["ok"])
        self.assertIn("Operational Conscience blocked", result["error"])
        self.assertEqual("REFUSE", result["conscience"]["decision"])

    def test_conscience_preview_returns_decision(self):
        result = _conscience_preview_payload(
            {
                "task": "Improve secret handling.",
                "brief": "Context pack.",
                "destination": "software",
            }
        )

        self.assertTrue(result["ok"])
        self.assertEqual("ALLOW_WITH_LIMITS", result["conscience"]["decision"])

    def test_agent_command_uses_allowlisted_agent_command(self):
        command = _agent_command("codex", Path("workspace"), "Do the task.")

        self.assertEqual(command[:2], ["codex", "exec"])
        self.assertIn("--skip-git-repo-check", command)

    def test_delegate_launch_passes_conscience_to_launcher(self):
        captured = {}

        def launcher(command, cwd):
            captured["command"] = command
            captured["cwd"] = cwd
            return 123

        result = _delegate_launch_payload(
            {
                "agent": "codex",
                "destination": "software",
                "task": "Improve secret handling.",
                "brief": "Context pack.",
                "approved": True,
            },
            launcher=launcher,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(123, result["pid"])
        self.assertEqual("ALLOW_WITH_LIMITS", result["conscience"]["decision"])
        self.assertIn("Operational Conscience Decision", captured["command"][-1])


if __name__ == "__main__":
    unittest.main()

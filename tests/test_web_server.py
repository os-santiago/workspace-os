import unittest

from pathlib import Path
import tempfile

from workspace_os.config import Source
from workspace_os.web_server import _capture_preview_payload, _extract_progress_map, _promote_preview_payload


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


if __name__ == "__main__":
    unittest.main()

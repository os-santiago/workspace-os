import unittest

from workspace_os.web_server import _extract_progress_map


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


if __name__ == "__main__":
    unittest.main()

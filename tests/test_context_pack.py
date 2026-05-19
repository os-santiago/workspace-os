from pathlib import Path
import tempfile
import unittest

from workspace_os.config import Source
from workspace_os.context_pack import build_context_pack


class ContextPackTests(unittest.TestCase):
    def test_context_pack_renders_doctrine_and_matching_knowledge(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            doctrine = root / "doctrine"
            evidence = root / "evidence"
            doctrine.mkdir()
            evidence.mkdir()
            (doctrine / "ADEV.md").write_text("# ADEV\nSearch before write.\n", encoding="utf-8")
            (evidence / "daily.md").write_text("Agent context should reuse ADEV.\n", encoding="utf-8")
            sources = [
                Source("adev", "doctrine", "Doctrine.", doctrine),
                Source("kb", "evidence", "Evidence.", evidence),
            ]

            pack = build_context_pack(sources, "ADEV", max_matches=5, max_doctrine_lines=2)
            rendered = pack.render_markdown()

        self.assertIn("# Workspace OS Agent Context Pack", rendered)
        self.assertIn("> # ADEV", rendered)
        self.assertIn("kb:daily.md:1", rendered)
        self.assertNotIn(str(root), rendered)

    def test_context_pack_redacts_secret_like_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            doctrine = root / "doctrine"
            doctrine.mkdir()
            (doctrine / "ADEV.md").write_text("token=example-value\n", encoding="utf-8")
            source = Source("adev", "doctrine", "Doctrine.", doctrine)

            rendered = build_context_pack([source], "token", max_matches=5).render_markdown()

        self.assertIn("token=[REDACTED]", rendered)
        self.assertNotIn("example-value", rendered)


if __name__ == "__main__":
    unittest.main()
